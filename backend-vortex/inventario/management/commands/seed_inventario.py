"""Datos iniciales: unidades, tipos de movimiento, sucursal/almacén/categoría por defecto. Idempotente."""
from django.core.management.base import BaseCommand
from django.db import transaction

from inventario.models import Almacen, Categoria, Sucursal, TipoMovimiento, UnidadMedida

UNIDADES = [
    ("UN", "Unidad", False), ("CJ", "Caja", False), ("PQ", "Paquete", False),
    ("KG", "Kilogramo", True), ("LT", "Litro", True), ("MT", "Metro", True),
]

# codigo, nombre, signo, requiere_tercero, tipo_tercero, es_traspaso
TIPOS = [
    ("COMPRA", "Compra", 1, True, "PROVEEDOR", False),
    ("SALDO-INI", "Saldo inicial", 1, False, "", False),
    ("DEV-CLI", "Devolución de cliente", 1, True, "CLIENTE", False),
    ("AJ-POS", "Ajuste positivo", 1, False, "", False),
    ("VENTA", "Venta", -1, True, "CLIENTE", False),
    ("DEV-PRO", "Devolución a proveedor", -1, True, "PROVEEDOR", False),
    ("MERMA", "Ajuste por merma", -1, False, "", False),
    ("AJ-NEG", "Ajuste negativo", -1, False, "", False),
    ("TRASP-S", "Traspaso (salida)", -1, False, "", True),
    ("TRASP-E", "Traspaso (entrada)", 1, False, "", True),
]


class Command(BaseCommand):
    help = "Carga los catálogos base del inventario (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        for codigo, nombre, decimales in UNIDADES:
            UnidadMedida.objects.update_or_create(
                codigo=codigo, defaults={"nombre": nombre, "permite_decimales": decimales})
        for codigo, nombre, signo, req, tipo_t, trasp in TIPOS:
            TipoMovimiento.objects.update_or_create(
                codigo=codigo,
                defaults={"nombre": nombre, "signo": signo, "requiere_tercero": req,
                          "tipo_tercero": tipo_t, "es_traspaso": trasp})
        sucursal, _ = Sucursal.objects.get_or_create(codigo="CENTRAL", defaults={"nombre": "Casa central"})
        Almacen.objects.get_or_create(sucursal=sucursal, codigo="PRINCIPAL", defaults={"nombre": "Almacén principal"})
        Categoria.objects.get_or_create(nombre="General")
        self.stdout.write(self.style.SUCCESS("Catálogos base cargados."))
