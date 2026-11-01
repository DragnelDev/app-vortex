"""
Capa de servicios del inventario: ÚNICO punto de entrada para modificar stock y Kardex.

Todas las operaciones son atómicas (`transaction.atomic`) y bloquean las filas de
StockAlmacen con `select_for_update()` en orden determinista (almacén, producto) para
evitar condiciones de carrera y deadlocks. Valoración: Precio Promedio Ponderado.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    CERO,
    DetalleMovimiento,
    EstadoMovimiento,
    InventarioError,
    MovimientoInventario,
    Producto,
    Signo,
    StockAlmacen,
    TipoMovimiento,
)

CODIGO_TRASPASO_SALIDA = "TRASP-S"
CODIGO_TRASPASO_ENTRADA = "TRASP-E"


@dataclass
class LineaMovimiento:
    """Línea de entrada/salida. En entradas `precio_unitario` es el costo de ingreso."""

    producto: Producto
    cantidad: Decimal
    precio_unitario: Decimal = CERO
    lote: str = ""
    fecha_vencimiento: date | None = None


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------
def _validar_lineas(lineas):
    if not lineas:
        raise ValidationError({"lineas": "El comprobante debe tener al menos una línea."})
    vistos = set()
    for linea in lineas:
        clave = (linea.producto.pk, linea.lote)
        if clave in vistos:
            raise ValidationError(
                {"lineas": f"Producto repetido en el comprobante: {linea.producto.sku} (mismo lote)."}
            )
        vistos.add(clave)


def _bloquear_stocks(pares, usuario):
    """
    `pares`: iterable de (almacen, producto). Devuelve {(almacen_id, producto_id): StockAlmacen}
    con las filas bloqueadas (creándolas si no existen), en orden determinista.
    """
    unicos = {(a.pk, p.pk): (a, p) for a, p in pares}
    stocks = {}
    for clave in sorted(unicos):
        almacen, producto = unicos[clave]
        stock, _ = StockAlmacen.objects.select_for_update(of=("self",)).get_or_create(
            almacen=almacen, producto=producto, defaults={"usuario_registro": usuario}
        )
        stock.producto = producto  # evita consultas extra (mensajes de error, mínimos)
        stocks[clave] = stock
    return stocks


def _crear_detalle(movimiento, stock, linea, costo, precio, usuario):
    detalle = DetalleMovimiento(
        movimiento=movimiento,
        producto=linea.producto,
        cantidad=linea.cantidad,
        precio_unitario=precio,
        costo_promedio_historico=costo,
        lote=linea.lote,
        fecha_vencimiento=linea.fecha_vencimiento,
        saldo_cantidad=stock.cantidad,
        saldo_costo_promedio=stock.costo_promedio,
        saldo_valor=stock.valor_total,
        usuario_registro=usuario,
    )
    detalle.full_clean()
    detalle.save()
    return detalle


def _aplicar_linea(movimiento, signo, stock, linea, usuario, precio_forzado=None):
    """Aplica la línea al stock (PPP) y registra el detalle con su instantánea de saldo."""
    if signo == Signo.ENTRADA:
        costo = stock.aplicar_entrada(linea.cantidad, linea.precio_unitario)
        precio = linea.precio_unitario
    else:
        costo = stock.aplicar_salida(linea.cantidad)
        precio = linea.precio_unitario
    if precio_forzado is not None:
        precio = costo
    return _crear_detalle(movimiento, stock, linea, costo, precio, usuario), costo


def _guardar_stocks(stocks):
    for clave in sorted(stocks):
        stocks[clave].save()


# ---------------------------------------------------------------------------
# Entradas y salidas
# ---------------------------------------------------------------------------
@transaction.atomic
def registrar_movimiento(
    *, usuario, almacen, tipo: TipoMovimiento, lineas, tercero=None, fecha=None,
    numero_documento="", observacion="",
) -> MovimientoInventario:
    """Registra una entrada o una salida (según el signo del tipo) con cálculo PPP."""
    if tipo.es_traspaso:
        raise ValidationError({"tipo_movimiento": "Los traspasos se registran con el flujo de traspaso."})
    _validar_lineas(lineas)

    stocks = _bloquear_stocks([(almacen, l.producto) for l in lineas], usuario)

    movimiento = MovimientoInventario(
        almacen=almacen,
        tipo_movimiento=tipo,
        tercero=tercero,
        fecha_movimiento=fecha or timezone.now(),
        numero_documento=numero_documento,
        observacion=observacion,
        usuario_registro=usuario,
    )
    movimiento.full_clean()
    movimiento.save()

    for linea in lineas:
        stock = stocks[(almacen.pk, linea.producto.pk)]
        _aplicar_linea(movimiento, tipo.signo, stock, linea, usuario)

    _guardar_stocks(stocks)
    movimiento.recalcular_total()
    return movimiento


# ---------------------------------------------------------------------------
# Traspaso entre almacenes
# ---------------------------------------------------------------------------
@transaction.atomic
def registrar_traspaso(
    *, usuario, origen, destino, lineas, fecha=None, numero_documento="", observacion="",
):
    """
    Crea DOS comprobantes enlazados: salida en `origen` (al PPP de origen) y entrada en
    `destino` (al mismo costo). Devuelve (movimiento_salida, movimiento_entrada).
    """
    if origen.pk == destino.pk:
        raise ValidationError({"almacen_destino": "El almacén de destino debe ser distinto al de origen."})
    _validar_lineas(lineas)

    try:
        tipo_s = TipoMovimiento.objects.get(codigo=CODIGO_TRASPASO_SALIDA)
        tipo_e = TipoMovimiento.objects.get(codigo=CODIGO_TRASPASO_ENTRADA)
    except TipoMovimiento.DoesNotExist as exc:
        raise InventarioError("Faltan los tipos de traspaso. Ejecute: python manage.py seed_inventario") from exc

    pares = [(origen, l.producto) for l in lineas] + [(destino, l.producto) for l in lineas]
    stocks = _bloquear_stocks(pares, usuario)
    fecha = fecha or timezone.now()
    comunes = dict(fecha_movimiento=fecha, numero_documento=numero_documento,
                   observacion=observacion, usuario_registro=usuario)

    mov_s = MovimientoInventario(almacen=origen, tipo_movimiento=tipo_s, **comunes)
    mov_s.full_clean()
    mov_s.save()
    costos = {}
    for linea in lineas:
        stock = stocks[(origen.pk, linea.producto.pk)]
        _, costo = _aplicar_linea(mov_s, Signo.SALIDA, stock, linea, usuario, precio_forzado=True)
        costos[(linea.producto.pk, linea.lote)] = costo

    mov_e = MovimientoInventario(almacen=destino, tipo_movimiento=tipo_e,
                                 movimiento_relacionado=mov_s, **comunes)
    mov_e.full_clean()
    mov_e.save()
    for linea in lineas:
        costo = costos[(linea.producto.pk, linea.lote)]
        entrada = LineaMovimiento(linea.producto, linea.cantidad, costo, linea.lote, linea.fecha_vencimiento)
        stock = stocks[(destino.pk, linea.producto.pk)]
        _aplicar_linea(mov_e, Signo.ENTRADA, stock, entrada, usuario)

    mov_s.movimiento_relacionado = mov_e
    mov_s.save(update_fields=["movimiento_relacionado", "fecha_modificacion"])

    _guardar_stocks(stocks)
    mov_s.recalcular_total()
    mov_e.recalcular_total()
    return mov_s, mov_e


# ---------------------------------------------------------------------------
# Anulación (contra-movimiento)
# ---------------------------------------------------------------------------
@transaction.atomic
def anular_movimiento(*, usuario, movimiento: MovimientoInventario, motivo: str) -> MovimientoInventario:
    """
    Anula un comprobante creando su contra-movimiento. Si es parte de un traspaso se anulan
    ambos comprobantes. Devuelve el contra-movimiento del comprobante solicitado.
    Falla con StockInsuficienteError si el stock ya fue consumido (p. ej. compra ya vendida).
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError({"motivo": "Indique el motivo de la anulación."})

    qs = MovimientoInventario.objects.select_for_update(of=("self",)).select_related(
        "tipo_movimiento", "almacen", "tercero"
    )
    original = qs.get(pk=movimiento.pk)
    originales = [original]
    if original.movimiento_relacionado_id:
        originales.append(qs.get(pk=original.movimiento_relacionado_id))
    originales.sort(key=lambda m: m.pk)

    for o in originales:
        if o.es_anulacion:
            raise InventarioError("Un contra-movimiento no puede anularse.")
        if o.esta_anulado:
            raise InventarioError(f"El comprobante {o.numero_comprobante} ya está anulado.")

    detalles = {o.pk: list(o.detalles.select_related("producto__unidad_medida")) for o in originales}
    stocks = _bloquear_stocks(
        [(o.almacen, d.producto) for o in originales for d in detalles[o.pk]], usuario
    )

    ahora = timezone.now()
    contras = {}
    for o in originales:
        contra = MovimientoInventario(
            almacen=o.almacen,
            tipo_movimiento=o.tipo_movimiento,
            tercero=o.tercero,
            fecha_movimiento=ahora,
            numero_documento=o.numero_documento,
            observacion=f"Anulación de {o.numero_comprobante}: {motivo}",
            movimiento_anulado=o,
            usuario_registro=usuario,
        )
        contra.full_clean()
        contra.save()

        for d in detalles[o.pk]:
            stock = stocks[(o.almacen_id, d.producto_id)]
            if o.tipo_movimiento.signo == Signo.ENTRADA:
                costo = stock.revertir_entrada(d.cantidad, d.costo_promedio_historico)
            else:
                costo = stock.aplicar_entrada(d.cantidad, d.costo_promedio_historico)
            _crear_detalle(
                contra, stock,
                LineaMovimiento(d.producto, d.cantidad, d.precio_unitario, d.lote, d.fecha_vencimiento),
                costo, d.precio_unitario, usuario,
            )
        contras[o.pk] = contra

    _guardar_stocks(stocks)

    for o in originales:
        contras[o.pk].recalcular_total()
        o.estado = EstadoMovimiento.ANULADO
        o.fecha_anulacion = ahora
        o.usuario_anulacion = usuario
        o.motivo_anulacion = motivo
        o.save(update_fields=["estado", "fecha_anulacion", "usuario_anulacion",
                              "motivo_anulacion", "fecha_modificacion"])

    return contras[original.pk]
