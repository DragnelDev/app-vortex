from django.contrib import admin

from .models import (
    Almacen, Categoria, DetalleMovimiento, MovimientoInventario, Producto,
    StockAlmacen, Sucursal, Tercero, TipoMovimiento, UnidadMedida,
)


class SoloLecturaAdmin(admin.ModelAdmin):
    """Registros contables: solo consulta (se modifican únicamente vía servicios/API)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DetalleInline(admin.TabularInline):
    model = DetalleMovimiento
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MovimientoInventario)
class MovimientoAdmin(SoloLecturaAdmin):
    list_display = ("numero_comprobante", "fecha_movimiento", "almacen", "tipo_movimiento", "total", "estado")
    list_filter = ("estado", "tipo_movimiento", "almacen")
    search_fields = ("numero_comprobante", "numero_documento")
    inlines = [DetalleInline]


@admin.register(StockAlmacen)
class StockAdmin(SoloLecturaAdmin):
    list_display = ("almacen", "producto", "cantidad", "costo_promedio", "valor_total")
    list_filter = ("almacen",)
    search_fields = ("producto__sku", "producto__nombre")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("sku", "nombre", "categoria", "unidad_medida", "stock_minimo", "estado")
    list_filter = ("estado", "categoria")
    search_fields = ("sku", "nombre", "codigo_barras")


for modelo in (Sucursal, Almacen, Categoria, UnidadMedida, Tercero, TipoMovimiento):
    admin.site.register(modelo)
