import django_filters as df
from django.db.models import F

from .models import DetalleMovimiento, MovimientoInventario, Producto, StockAlmacen


class ProductoFilter(df.FilterSet):
    class Meta:
        model = Producto
        fields = {
            "categoria": ["exact"],
            "unidad_medida": ["exact"],
            "estado": ["exact"],
            "maneja_lotes": ["exact"],
        }


class MovimientoFilter(df.FilterSet):
    desde = df.DateFilter(field_name="fecha_movimiento", lookup_expr="date__gte")
    hasta = df.DateFilter(field_name="fecha_movimiento", lookup_expr="date__lte")
    signo = df.NumberFilter(field_name="tipo_movimiento__signo")

    class Meta:
        model = MovimientoInventario
        fields = ["almacen", "tipo_movimiento", "tercero", "estado"]


class StockFilter(df.FilterSet):
    bajo_minimo = df.BooleanFilter(method="filtrar_bajo_minimo")

    class Meta:
        model = StockAlmacen
        fields = ["almacen", "producto", "producto__categoria"]

    def filtrar_bajo_minimo(self, queryset, name, value):
        condicion = {"cantidad__lte": F("producto__stock_minimo")}
        return queryset.filter(**condicion) if value else queryset.exclude(**condicion)


class KardexFilter(df.FilterSet):
    producto = df.NumberFilter(field_name="producto_id", required=True)
    almacen = df.NumberFilter(field_name="movimiento__almacen_id", required=True)
    desde = df.DateFilter(field_name="movimiento__fecha_movimiento", lookup_expr="date__gte")
    hasta = df.DateFilter(field_name="movimiento__fecha_movimiento", lookup_expr="date__lte")

    class Meta:
        model = DetalleMovimiento
        fields = []
