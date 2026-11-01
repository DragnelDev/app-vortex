"""Vistas de la API REST de inventario."""
import csv
from decimal import Decimal

from django.db.models import Case, DecimalField, ExpressionWrapper, F, IntegerField, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .filters import KardexFilter, MovimientoFilter, ProductoFilter, StockFilter
from .models import (
    Almacen,
    Categoria,
    DetalleMovimiento,
    EstadoMovimiento,
    MovimientoInventario,
    Producto,
    StockAlmacen,
    Sucursal,
    Tercero,
    TipoMovimiento,
    UnidadMedida,
)
from .serializers import (
    AlmacenSerializer,
    AnularSerializer,
    CategoriaSerializer,
    KardexFilaSerializer,
    MovimientoCrearSerializer,
    MovimientoDetalleSerializer,
    MovimientoSerializer,
    ProductoSerializer,
    StockSerializer,
    SucursalSerializer,
    TerceroSerializer,
    TipoMovimientoSerializer,
    TraspasoSerializer,
    UnidadMedidaSerializer,
)

DECIMAL_14_4 = DecimalField(max_digits=14, decimal_places=4)
CERO = Value(Decimal("0"), output_field=DECIMAL_14_4)


def _fmt(valor) -> str:
    return format(valor if valor is not None else Decimal("0"), ".4f")


# ---------------------------------------------------------------------------
# Catálogos (DELETE = baja lógica)
# ---------------------------------------------------------------------------
class CatalogoViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        serializer.save(usuario_registro=self.request.user)

    def perform_destroy(self, instance):
        instance.estado = False
        instance.save(update_fields=["estado", "fecha_modificacion"])


class SucursalViewSet(CatalogoViewSet):
    queryset = Sucursal.objects.all()
    serializer_class = SucursalSerializer
    filterset_fields = ["estado"]
    search_fields = ["codigo", "nombre"]
    ordering_fields = ["codigo", "nombre"]


class AlmacenViewSet(CatalogoViewSet):
    queryset = Almacen.objects.select_related("sucursal")
    serializer_class = AlmacenSerializer
    filterset_fields = ["estado", "sucursal"]
    search_fields = ["codigo", "nombre", "sucursal__nombre"]
    ordering_fields = ["codigo", "nombre"]


class CategoriaViewSet(CatalogoViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    filterset_fields = ["estado", "padre"]
    search_fields = ["nombre"]


class UnidadMedidaViewSet(CatalogoViewSet):
    queryset = UnidadMedida.objects.all()
    serializer_class = UnidadMedidaSerializer
    filterset_fields = ["estado"]
    search_fields = ["codigo", "nombre"]


class ProductoViewSet(CatalogoViewSet):
    queryset = Producto.objects.select_related("categoria", "unidad_medida").annotate(
        stock_total=Coalesce(Sum("stocks__cantidad"), CERO)
    )
    serializer_class = ProductoSerializer
    filterset_class = ProductoFilter
    search_fields = ["sku", "nombre", "codigo_barras"]
    ordering_fields = ["sku", "nombre", "stock_total"]


class TerceroViewSet(CatalogoViewSet):
    queryset = Tercero.objects.all()
    serializer_class = TerceroSerializer
    filterset_fields = ["estado", "tipo", "tipo_documento"]
    search_fields = ["nombre_razon_social", "numero_documento"]


class TipoMovimientoViewSet(CatalogoViewSet):
    queryset = TipoMovimiento.objects.all()
    serializer_class = TipoMovimientoSerializer
    filterset_fields = ["estado", "signo", "es_traspaso"]
    search_fields = ["codigo", "nombre"]


# ---------------------------------------------------------------------------
# Comprobantes
# ---------------------------------------------------------------------------
class MovimientoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = MovimientoInventario.objects.select_related(
        "almacen", "tipo_movimiento", "tercero", "contramovimiento"
    )
    filterset_class = MovimientoFilter
    search_fields = ["numero_comprobante", "numero_documento", "tercero__nombre_razon_social"]
    ordering_fields = ["fecha_movimiento", "numero_comprobante", "total"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MovimientoDetalleSerializer
        if self.action == "create":
            return MovimientoCrearSerializer
        if self.action == "traspaso":
            return TraspasoSerializer
        if self.action == "anular":
            return AnularSerializer
        return MovimientoSerializer

    def _responder(self, movimiento, codigo=status.HTTP_201_CREATED):
        movimiento = self.get_queryset().prefetch_related("detalles__producto__unidad_medida").get(pk=movimiento.pk)
        return Response(MovimientoDetalleSerializer(movimiento).data, status=codigo)

    def create(self, request):
        """Registra una entrada o salida con cálculo PPP."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        movimiento = services.registrar_movimiento(
            usuario=request.user, almacen=d["almacen"], tipo=d["tipo_movimiento"],
            tercero=d.get("tercero"), fecha=d.get("fecha_movimiento"),
            numero_documento=d["numero_documento"], observacion=d["observacion"],
            lineas=ser.lineas_validadas(),
        )
        return self._responder(movimiento)

    @action(detail=False, methods=["post"])
    def traspaso(self, request):
        """Traspaso entre almacenes: crea dos comprobantes enlazados."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        salida, entrada = services.registrar_traspaso(
            usuario=request.user, origen=d["almacen_origen"], destino=d["almacen_destino"],
            fecha=d.get("fecha_movimiento"), numero_documento=d["numero_documento"],
            observacion=d["observacion"], lineas=ser.lineas_validadas(),
        )
        return Response(
            {
                "salida": self._responder(salida).data,
                "entrada": self._responder(entrada).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        """Anula el comprobante mediante un contra-movimiento."""
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        contra = services.anular_movimiento(
            usuario=request.user, movimiento=self.get_object(), motivo=ser.validated_data["motivo"]
        )
        return self._responder(contra)


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------
class StockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockAlmacen.objects.select_related("almacen", "producto__unidad_medida")
    serializer_class = StockSerializer
    filterset_class = StockFilter
    search_fields = ["producto__sku", "producto__nombre", "almacen__nombre"]
    ordering_fields = ["cantidad", "valor_total", "producto__nombre", "almacen__nombre"]


# ---------------------------------------------------------------------------
# Kardex físico-valorado
# ---------------------------------------------------------------------------
class KardexView(ListAPIView):
    """
    GET /api/kardex/?producto=<id>&almacen=<id>[&desde=YYYY-MM-DD&hasta=YYYY-MM-DD]
    Orden cronológico = orden de registro (id de la línea). Incluye `resumen` con saldo
    inicial, totales del periodo y saldo final.
    """

    queryset = DetalleMovimiento.objects.select_related(
        "movimiento__tipo_movimiento", "movimiento__tercero", "movimiento__almacen", "producto"
    ).order_by("id")
    serializer_class = KardexFilaSerializer
    filterset_class = KardexFilter
    filter_backends = [DjangoFilterBackend]

    def _resumen(self, qs, request):
        producto = request.query_params["producto"]
        almacen = request.query_params["almacen"]
        desde = request.query_params.get("desde")

        previo = None
        if desde:
            previo = (
                DetalleMovimiento.objects.filter(
                    producto_id=producto, movimiento__almacen_id=almacen,
                    movimiento__fecha_movimiento__date__lt=desde,
                ).order_by("-id").first()
            )
        inicial = (
            {"cantidad": previo.saldo_cantidad, "costo": previo.saldo_costo_promedio, "valor": previo.saldo_valor}
            if previo else {"cantidad": Decimal("0"), "costo": Decimal("0"), "valor": Decimal("0")}
        )

        signo_tipo = F("movimiento__tipo_movimiento__signo")
        signo = Case(
            When(
                movimiento__movimiento_anulado__isnull=False,
                then=ExpressionWrapper(-signo_tipo, output_field=IntegerField()),
            ),
            default=ExpressionWrapper(signo_tipo, output_field=IntegerField()),
            output_field=IntegerField(),
        )
        agg = qs.annotate(signo_ef=signo).aggregate(
            ent_cant=Coalesce(Sum(Case(When(signo_ef__gt=0, then="cantidad"), output_field=DECIMAL_14_4)), CERO),
            ent_val=Coalesce(Sum(Case(When(signo_ef__gt=0, then="costo_total"), output_field=DECIMAL_14_4)), CERO),
            sal_cant=Coalesce(Sum(Case(When(signo_ef__lt=0, then="cantidad"), output_field=DECIMAL_14_4)), CERO),
            sal_val=Coalesce(Sum(Case(When(signo_ef__lt=0, then="costo_total"), output_field=DECIMAL_14_4)), CERO),
        )
        ultimo = qs.order_by("-id").first()
        final = (
            {"cantidad": ultimo.saldo_cantidad, "costo": ultimo.saldo_costo_promedio, "valor": ultimo.saldo_valor}
            if ultimo else inicial
        )
        return {
            "saldo_inicial": {k: _fmt(v) for k, v in inicial.items()},
            "entradas": {"cantidad": _fmt(agg["ent_cant"]), "valor": _fmt(agg["ent_val"])},
            "salidas": {"cantidad": _fmt(agg["sal_cant"]), "valor": _fmt(agg["sal_val"])},
            "saldo_final": {k: _fmt(v) for k, v in final.items()},
        }

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["resumen"] = self._resumen(self.filter_queryset(self.get_queryset()), request)
        return response


class KardexExportarView(KardexView):
    """GET /api/kardex/exportar/ — mismos filtros que el Kardex, devuelve CSV completo."""

    pagination_class = None

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = (
            f'attachment; filename="kardex_{request.query_params["producto"]}_{timezone.localdate()}.csv"'
        )
        respuesta.write("\ufeff")  # BOM para que Excel respete UTF-8
        w = csv.writer(respuesta)
        w.writerow([
            "Fecha", "Comprobante", "Tipo", "Tercero", "Documento", "Estado", "Lote",
            "Entrada cant.", "Entrada costo", "Entrada total",
            "Salida cant.", "Salida costo", "Salida total",
            "Saldo cant.", "Saldo costo", "Saldo valor",
        ])
        for f in KardexFilaSerializer(qs, many=True).data:
            w.writerow([
                timezone.localtime(f["fecha"]).strftime("%Y-%m-%d %H:%M"), f["comprobante"], f["tipo"],
                f["tercero"] or "", f["documento"], f["estado"], f["lote"],
                f["entrada_cantidad"], f["entrada_costo"], f["entrada_total"],
                f["salida_cantidad"], f["salida_costo"], f["salida_total"],
                f["saldo_cantidad"], f["saldo_costo"], f["saldo_valor"],
            ])
        return respuesta


# ---------------------------------------------------------------------------
# Dashboard y usuario actual
# ---------------------------------------------------------------------------
class DashboardResumenView(APIView):
    def get(self, request):
        hoy = timezone.localdate()
        stocks = StockAlmacen.objects.all()
        return Response({
            "productos_activos": Producto.objects.filter(estado=True).count(),
            "valor_inventario": _fmt(stocks.aggregate(t=Coalesce(Sum("valor_total"), CERO))["t"]),
            "items_bajo_minimo": stocks.filter(cantidad__lte=F("producto__stock_minimo"), producto__estado=True).count(),
            "movimientos_mes": MovimientoInventario.objects.filter(
                estado=EstadoMovimiento.REGISTRADO,
                fecha_movimiento__year=hoy.year, fecha_movimiento__month=hoy.month,
            ).count(),
        })


class MeView(APIView):
    def get(self, request):
        u = request.user
        return Response({
            "id": u.id, "username": u.get_username(), "first_name": u.first_name,
            "last_name": u.last_name, "email": u.email, "is_staff": u.is_staff,
        })
