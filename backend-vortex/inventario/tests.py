from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from . import services
from .models import (
    Almacen, Categoria, EstadoMovimiento, Producto, StockAlmacen, StockInsuficienteError,
    Sucursal, Tercero, TipoMovimiento, UnidadMedida,
)
from .services import LineaMovimiento


class BaseInventarioTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_inventario", verbosity=0)
        cls.user = get_user_model().objects.create_user("tester", password="x")
        cls.suc = Sucursal.objects.get(codigo="CENTRAL")
        cls.a1 = Almacen.objects.get(codigo="PRINCIPAL")
        cls.a2 = Almacen.objects.create(sucursal=cls.suc, codigo="SEC", nombre="Secundario")
        cls.cat = Categoria.objects.get(nombre="General")
        cls.un = UnidadMedida.objects.get(codigo="UN")
        cls.kg = UnidadMedida.objects.get(codigo="KG")
        cls.p = Producto.objects.create(sku="P1", nombre="Producto 1", categoria=cls.cat, unidad_medida=cls.un, stock_minimo=D("5"))
        cls.pkg = Producto.objects.create(sku="HAR", nombre="Harina", categoria=cls.cat, unidad_medida=cls.kg)
        cls.prov = Tercero.objects.create(tipo="PROVEEDOR", numero_documento="1", nombre_razon_social="Prov")
        cls.cli = Tercero.objects.create(tipo="CLIENTE", tipo_documento="CI", numero_documento="2", nombre_razon_social="Cli")
        cls.compra = TipoMovimiento.objects.get(codigo="COMPRA")
        cls.venta = TipoMovimiento.objects.get(codigo="VENTA")

    def comprar(self, cant, costo, producto=None, almacen=None):
        return services.registrar_movimiento(
            usuario=self.user, almacen=almacen or self.a1, tipo=self.compra, tercero=self.prov,
            lineas=[LineaMovimiento(producto or self.p, D(cant), D(costo))])

    def vender(self, cant, producto=None):
        return services.registrar_movimiento(
            usuario=self.user, almacen=self.a1, tipo=self.venta, tercero=self.cli,
            lineas=[LineaMovimiento(producto or self.p, D(cant), D("20"))])

    def stock(self, producto=None, almacen=None):
        return StockAlmacen.objects.get(almacen=almacen or self.a1, producto=producto or self.p)


class ServiciosTest(BaseInventarioTest):
    def test_ppp_entradas_y_salida(self):
        self.comprar("10", "5")
        self.comprar("20", "8")
        s = self.stock()
        self.assertEqual((s.cantidad, s.costo_promedio, s.valor_total), (D("30"), D("7"), D("210")))
        mov = self.vender("12")
        det = mov.detalles.get()
        self.assertEqual(det.costo_promedio_historico, D("7"))
        self.assertEqual(det.saldo_cantidad, D("18"))
        self.assertEqual(self.stock().valor_total, D("126"))

    def test_stock_insuficiente_no_deja_rastro(self):
        self.comprar("3", "5")
        total = self.a1.movimientos.count()
        with self.assertRaises(StockInsuficienteError):
            self.vender("4")
        self.assertEqual(self.a1.movimientos.count(), total)
        self.assertEqual(self.stock().cantidad, D("3"))

    def test_unidad_sin_decimales(self):
        with self.assertRaises(ValidationError):
            self.comprar("1.5", "5")
        self.comprar("1.5", "5", producto=self.pkg)

    def test_anular_compra_restituye_ppp(self):
        self.comprar("10", "5")
        m2 = self.comprar("10", "9")
        self.assertEqual(self.stock().costo_promedio, D("7"))
        contra = services.anular_movimiento(usuario=self.user, movimiento=m2, motivo="Error de digitación")
        m2.refresh_from_db()
        self.assertEqual(m2.estado, EstadoMovimiento.ANULADO)
        self.assertTrue(contra.es_anulacion)
        s = self.stock()
        self.assertEqual((s.cantidad, s.costo_promedio, s.valor_total), (D("10"), D("5"), D("50")))
        with self.assertRaises(Exception):
            services.anular_movimiento(usuario=self.user, movimiento=m2, motivo="otra vez")

    def test_no_se_anula_compra_ya_consumida(self):
        m = self.comprar("5", "5")
        self.vender("5")
        with self.assertRaises(StockInsuficienteError):
            services.anular_movimiento(usuario=self.user, movimiento=m, motivo="x")
        m.refresh_from_db()
        self.assertEqual(m.estado, EstadoMovimiento.REGISTRADO)

    def test_anular_venta_devuelve_stock_al_costo_original(self):
        self.comprar("10", "5")
        v = self.vender("4")
        services.anular_movimiento(usuario=self.user, movimiento=v, motivo="Devuelto")
        s = self.stock()
        self.assertEqual((s.cantidad, s.costo_promedio), (D("10"), D("5")))

    def test_traspaso_y_su_anulacion(self):
        self.comprar("10", "6")
        sal, ent = services.registrar_traspaso(
            usuario=self.user, origen=self.a1, destino=self.a2,
            lineas=[LineaMovimiento(self.p, D("4"))])
        self.assertEqual(sal.movimiento_relacionado_id, ent.pk)
        self.assertEqual(ent.movimiento_relacionado_id, sal.pk)
        self.assertEqual(self.stock().cantidad, D("6"))
        self.assertEqual((self.stock(almacen=self.a2).cantidad, self.stock(almacen=self.a2).costo_promedio), (D("4"), D("6")))
        services.anular_movimiento(usuario=self.user, movimiento=sal, motivo="Error")
        self.assertEqual(self.stock().cantidad, D("10"))
        self.assertEqual(self.stock(almacen=self.a2).cantidad, D("0"))


class ApiTest(BaseInventarioTest):
    def setUp(self):
        self.client = APIClient()
        r = self.client.post("/api/auth/token/", {"username": "tester", "password": "x"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_requiere_autenticacion(self):
        self.assertEqual(APIClient().get("/api/productos/").status_code, 401)

    def test_flujo_movimiento_y_kardex(self):
        r = self.client.post("/api/movimientos/", {
            "almacen": self.a1.pk, "tipo_movimiento": self.compra.pk, "tercero": self.prov.pk,
            "numero_documento": "F-1", "lineas": [{"producto": self.p.pk, "cantidad": "10", "precio_unitario": "5"}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post("/api/movimientos/", {
            "almacen": self.a1.pk, "tipo_movimiento": self.venta.pk, "tercero": self.cli.pk,
            "lineas": [{"producto": self.p.pk, "cantidad": "99", "precio_unitario": "9"}],
        }, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "stock_insuficiente")
        self.client.post("/api/movimientos/", {
            "almacen": self.a1.pk, "tipo_movimiento": self.venta.pk, "tercero": self.cli.pk,
            "lineas": [{"producto": self.p.pk, "cantidad": "4", "precio_unitario": "9"}],
        }, format="json")

        k = self.client.get(f"/api/kardex/?producto={self.p.pk}&almacen={self.a1.pk}")
        self.assertEqual(k.status_code, 200)
        self.assertEqual(k.data["count"], 2)
        self.assertEqual(k.data["results"][1]["saldo_cantidad"], "6.0000")
        self.assertEqual(k.data["resumen"]["entradas"]["cantidad"], "10.0000")
        self.assertEqual(k.data["resumen"]["salidas"]["valor"], "20.0000")
        self.assertEqual(k.data["resumen"]["saldo_final"]["valor"], "30.0000")
        self.assertEqual(self.client.get("/api/kardex/").status_code, 400)

        csv = self.client.get(f"/api/kardex/exportar/?producto={self.p.pk}&almacen={self.a1.pk}")
        self.assertEqual(csv.status_code, 200)
        self.assertIn("text/csv", csv["Content-Type"])

        stock = self.client.get("/api/stock/?bajo_minimo=false")
        self.assertEqual(stock.data["count"], 1)  # 6 > mínimo 5
        self.assertEqual(self.client.get("/api/dashboard/resumen/").data["valor_inventario"], "30.0000")

    def test_soft_delete_catalogo(self):
        r = self.client.delete(f"/api/productos/{self.p.pk}/")
        self.assertEqual(r.status_code, 204)
        self.p.refresh_from_db()
        self.assertFalse(self.p.estado)

    def test_validacion_modelo_en_catalogo(self):
        r = self.client.post("/api/productos/", {
            "sku": "X", "nombre": "X", "categoria": self.cat.pk, "unidad_medida": self.un.pk,
            "maneja_vencimiento": True, "maneja_lotes": False}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/productos/", {"sku": "p1", "nombre": "dup", "categoria": self.cat.pk,
                                                 "unidad_medida": self.un.pk}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_anular_por_api(self):
        m = self.comprar("5", "2")
        r = self.client.post(f"/api/movimientos/{m.pk}/anular/", {"motivo": "Prueba"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.client.get(f"/api/movimientos/{m.pk}/").data["estado"], "ANULADO")
