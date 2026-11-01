"""Serializers de la API de inventario (decimales siempre como DecimalField 14,4)."""
import copy
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    Almacen,
    Categoria,
    DetalleMovimiento,
    MovimientoInventario,
    Producto,
    StockAlmacen,
    Sucursal,
    Tercero,
    TipoMovimiento,
    UnidadMedida,
)
from .services import LineaMovimiento

CAMPOS_AUDITORIA = ("fecha_registro", "fecha_modificacion", "usuario_registro")


def decimal_api(**kwargs):
    return serializers.DecimalField(max_digits=14, decimal_places=4, **kwargs)


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
class CatalogoSerializer(serializers.ModelSerializer):
    """Ejecuta `Model.clean()` (reglas de negocio del modelo) durante la validación."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instancia = copy.copy(self.instance) if self.instance else self.Meta.model()
        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)
        try:
            instancia.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
        return attrs


class SucursalSerializer(CatalogoSerializer):
    class Meta:
        model = Sucursal
        fields = "__all__"
        read_only_fields = CAMPOS_AUDITORIA


class AlmacenSerializer(CatalogoSerializer):
    sucursal_nombre = serializers.CharField(source="sucursal.nombre", read_only=True)

    class Meta:
        model = Almacen
        fields = "__all__"
        read_only_fields = CAMPOS_AUDITORIA


class CategoriaSerializer(CatalogoSerializer):
    class Meta:
        model = Categoria
        fields = "__all__"
        read_only_fields = CAMPOS_AUDITORIA


class UnidadMedidaSerializer(CatalogoSerializer):
    class Meta:
        model = UnidadMedida
        fields = "__all__"
        read_only_fields = CAMPOS_AUDITORIA


class ProductoSerializer(CatalogoSerializer):
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)
    unidad_codigo = serializers.CharField(source="unidad_medida.codigo", read_only=True)
    unidad_permite_decimales = serializers.BooleanField(source="unidad_medida.permite_decimales", read_only=True)
    stock_total = decimal_api(read_only=True)

    class Meta:
        model = Producto
        fields = "__all__"
        read_only_fields = CAMPOS_AUDITORIA


class TerceroSerializer(CatalogoSerializer):
    class Meta:
        model = Tercero
        fields = "__all__"
        read_only_fields = CAMPOS_AUDITORIA


class TipoMovimientoSerializer(CatalogoSerializer):
    es_entrada = serializers.BooleanField(read_only=True)

    class Meta:
        model = TipoMovimiento
        fields = "__all__"
        read_only_fields = CAMPOS_AUDITORIA


# ---------------------------------------------------------------------------
# Comprobantes (lectura)
# ---------------------------------------------------------------------------
class DetalleSerializer(serializers.ModelSerializer):
    producto_sku = serializers.CharField(source="producto.sku", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    unidad_codigo = serializers.CharField(source="producto.unidad_medida.codigo", read_only=True)

    class Meta:
        model = DetalleMovimiento
        exclude = ("movimiento",)


class MovimientoSerializer(serializers.ModelSerializer):
    almacen_nombre = serializers.CharField(source="almacen.nombre", read_only=True)
    tipo_nombre = serializers.CharField(source="tipo_movimiento.nombre", read_only=True)
    signo_efectivo = serializers.IntegerField(read_only=True)
    es_anulacion = serializers.BooleanField(read_only=True)
    tercero_nombre = serializers.CharField(source="tercero.nombre_razon_social", read_only=True, default=None)
    anulado_por = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoInventario
        fields = (
            "id", "numero_comprobante", "fecha_movimiento", "almacen", "almacen_nombre",
            "tipo_movimiento", "tipo_nombre", "signo_efectivo", "es_anulacion", "tercero",
            "tercero_nombre", "numero_documento", "observacion", "total", "estado",
            "movimiento_relacionado", "movimiento_anulado", "anulado_por", "fecha_anulacion",
            "motivo_anulacion", "fecha_registro", "usuario_registro",
        )
        read_only_fields = fields

    def get_anulado_por(self, obj):
        contra = getattr(obj, "contramovimiento", None)
        return contra.numero_comprobante if contra else None


class MovimientoDetalleSerializer(MovimientoSerializer):
    detalles = DetalleSerializer(many=True, read_only=True)

    class Meta(MovimientoSerializer.Meta):
        fields = MovimientoSerializer.Meta.fields + ("detalles",)
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Comprobantes (entrada de datos)
# ---------------------------------------------------------------------------
class LineaSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(estado=True))
    cantidad = decimal_api(min_value=Decimal("0.0001"))
    precio_unitario = decimal_api(min_value=Decimal("0"), default=Decimal("0"))
    lote = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True, default=None)


class _ComprobanteBase(serializers.Serializer):
    fecha_movimiento = serializers.DateTimeField(required=False)
    numero_documento = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    observacion = serializers.CharField(required=False, allow_blank=True, default="")
    lineas = LineaSerializer(many=True, allow_empty=False)

    def lineas_validadas(self):
        return [
            LineaMovimiento(d["producto"], d["cantidad"], d["precio_unitario"], d["lote"], d["fecha_vencimiento"])
            for d in self.validated_data["lineas"]
        ]


class MovimientoCrearSerializer(_ComprobanteBase):
    almacen = serializers.PrimaryKeyRelatedField(queryset=Almacen.objects.filter(estado=True))
    tipo_movimiento = serializers.PrimaryKeyRelatedField(
        queryset=TipoMovimiento.objects.filter(estado=True, es_traspaso=False)
    )
    tercero = serializers.PrimaryKeyRelatedField(queryset=Tercero.objects.filter(estado=True), required=False, allow_null=True)


class TraspasoSerializer(_ComprobanteBase):
    almacen_origen = serializers.PrimaryKeyRelatedField(queryset=Almacen.objects.filter(estado=True))
    almacen_destino = serializers.PrimaryKeyRelatedField(queryset=Almacen.objects.filter(estado=True))


class AnularSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)


# ---------------------------------------------------------------------------
# Stock y Kardex
# ---------------------------------------------------------------------------
class StockSerializer(serializers.ModelSerializer):
    almacen_nombre = serializers.CharField(source="almacen.nombre", read_only=True)
    producto_sku = serializers.CharField(source="producto.sku", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    unidad_codigo = serializers.CharField(source="producto.unidad_medida.codigo", read_only=True)
    stock_minimo = decimal_api(source="producto.stock_minimo", read_only=True)
    bajo_minimo = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockAlmacen
        fields = (
            "id", "almacen", "almacen_nombre", "producto", "producto_sku", "producto_nombre",
            "unidad_codigo", "stock_minimo", "cantidad", "costo_promedio", "valor_total",
            "bajo_minimo", "fecha_modificacion",
        )
        read_only_fields = fields


def _fmt(valor) -> str:
    return format(valor, ".4f")


class KardexFilaSerializer(serializers.BaseSerializer):
    """Fila del Kardex físico-valorado: entradas | salidas | saldo (cantidad, costo, total)."""

    def to_representation(self, d: DetalleMovimiento):
        m = d.movimiento
        signo = m.signo_efectivo
        cero = _fmt(Decimal("0"))
        fila = {
            "id": d.id,
            "movimiento_id": m.id,
            "fecha": m.fecha_movimiento,
            "comprobante": m.numero_comprobante,
            "tipo": m.tipo_movimiento.nombre,
            "tercero": m.tercero.nombre_razon_social if m.tercero_id else None,
            "documento": m.numero_documento,
            "estado": m.estado,
            "es_anulacion": m.es_anulacion,
            "lote": d.lote,
            "entrada_cantidad": cero, "entrada_costo": cero, "entrada_total": cero,
            "salida_cantidad": cero, "salida_costo": cero, "salida_total": cero,
            "saldo_cantidad": _fmt(d.saldo_cantidad),
            "saldo_costo": _fmt(d.saldo_costo_promedio),
            "saldo_valor": _fmt(d.saldo_valor),
        }
        prefijo = "entrada" if signo > 0 else "salida"
        fila[f"{prefijo}_cantidad"] = _fmt(d.cantidad)
        fila[f"{prefijo}_costo"] = _fmt(d.costo_promedio_historico)
        fila[f"{prefijo}_total"] = _fmt(d.costo_total)
        return fila
