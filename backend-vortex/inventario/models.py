"""
Modelos de la app `inventario` — Vortex (Control de Inventario y Kardex Físico-Valorado).

Reglas de diseño que gobiernan este módulo
------------------------------------------
1. Precisión numérica: toda cantidad, costo, precio o total es DecimalField(14, 4).
   Está prohibido FloatField y el helper `redondear` rechaza floats.
2. Auditoría: todos los modelos heredan de `AuditoriaBase` (fecha_registro,
   fecha_modificacion, usuario_registro). Los catálogos añaden `estado` (activo/inactivo);
   el comprobante usa `estado` REGISTRADO/ANULADO.
3. Sin borrado físico: MovimientoInventario, DetalleMovimiento y StockAlmacen no
   pueden eliminarse (ni por instancia ni por QuerySet). Las anulaciones se hacen con
   un CONTRA-MOVIMIENTO: el original queda en estado ANULADO y el contra-movimiento
   (REGISTRADO, `movimiento_anulado` apuntando al original) revierte el efecto.
   Por eso el Kardex incluye ambos comprobantes: el libro siempre cuadra.
4. Valoración PPP (Precio Promedio Ponderado): la lógica de cálculo vive en
   `StockAlmacen.aplicar_entrada` / `aplicar_salida`. Cada línea guarda el saldo
   resultante (cantidad, costo promedio y valor) como instantánea del Kardex.
5. Orden del Kardex: el orden cronológico real es el de registro (id de la línea).
   Los saldos guardados en cada línea dependen de ese orden, por lo que la capa de
   servicios debe ejecutar todo dentro de `transaction.atomic` y bloquear la fila de
   StockAlmacen con `select_for_update()` antes de aplicar entradas o salidas.
6. `Model.clean()` no se invoca automáticamente desde DRF: los servicios deben llamar
   a `full_clean()` antes de persistir.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils import timezone

# ---------------------------------------------------------------------------
# Precisión numérica
# ---------------------------------------------------------------------------
MAX_DIGITOS = 14
DECIMALES = 4
CERO = Decimal("0")
UNIDAD_MINIMA = Decimal("0.0001")


def _a_decimal(valor) -> Decimal:
    """Convierte a Decimal rechazando floats (error de precisión garantizado)."""
    if isinstance(valor, float):
        raise TypeError("No se permiten floats en cálculos de inventario; use Decimal o str.")
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def redondear(valor) -> Decimal:
    """Redondea a 4 decimales con ROUND_HALF_UP (criterio contable habitual)."""
    return _a_decimal(valor).quantize(UNIDAD_MINIMA, rounding=ROUND_HALF_UP)


def multiplicar(a, b) -> Decimal:
    """a × b redondeado a 4 decimales."""
    return redondear(_a_decimal(a) * _a_decimal(b))


def campo_decimal(verbose_name: str, minimo: Decimal = CERO, **kwargs) -> models.DecimalField:
    """DecimalField(14, 4) estándar del sistema, con validador de mínimo."""
    kwargs.setdefault("validators", [MinValueValidator(minimo)])
    return models.DecimalField(
        verbose_name=verbose_name,
        max_digits=MAX_DIGITOS,
        decimal_places=DECIMALES,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Excepciones de dominio (la capa de servicios/API las traduce a HTTP 400/409)
# ---------------------------------------------------------------------------
class InventarioError(Exception):
    """Base de los errores de dominio del inventario."""


class BorradoFisicoProhibidoError(InventarioError):
    """Se intentó eliminar físicamente un registro contable."""


class ModificacionProhibidaError(InventarioError):
    """Se intentó modificar un registro contable inmutable."""


class StockInsuficienteError(InventarioError):
    """La salida solicitada supera el stock disponible."""

    def __init__(self, disponible: Decimal, solicitado: Decimal, producto=None):
        self.disponible = disponible
        self.solicitado = solicitado
        self.producto = producto
        etiqueta = f" de «{producto}»" if producto else ""
        super().__init__(
            f"Stock insuficiente{etiqueta}: disponible {disponible}, solicitado {solicitado}."
        )


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------
class TipoTercero(models.TextChoices):
    PROVEEDOR = "PROVEEDOR", "Proveedor"
    CLIENTE = "CLIENTE", "Cliente"
    AMBOS = "AMBOS", "Proveedor y cliente"


class TipoDocumento(models.TextChoices):
    NIT = "NIT", "NIT"
    CI = "CI", "Cédula de identidad"
    PASAPORTE = "PASAPORTE", "Pasaporte"
    OTRO = "OTRO", "Otro"


class Signo(models.IntegerChoices):
    ENTRADA = 1, "Entrada (+)"
    SALIDA = -1, "Salida (−)"


class EstadoMovimiento(models.TextChoices):
    REGISTRADO = "REGISTRADO", "Registrado"
    ANULADO = "ANULADO", "Anulado"


# ---------------------------------------------------------------------------
# Clases base
# ---------------------------------------------------------------------------
class AuditoriaBase(models.Model):
    """Campos de trazabilidad comunes a todos los modelos."""

    fecha_registro = models.DateTimeField("fecha de registro", auto_now_add=True)
    fecha_modificacion = models.DateTimeField("fecha de modificación", auto_now=True)
    usuario_registro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="usuario que registró",
    )

    class Meta:
        abstract = True


class CatalogoBase(AuditoriaBase):
    """Auditoría + `estado` booleano (True = activo) para catálogos con baja lógica."""

    estado = models.BooleanField("activo", default=True, db_index=True)

    class Meta:
        abstract = True


class SinBorradoQuerySet(models.QuerySet):
    def delete(self):
        raise BorradoFisicoProhibidoError(
            "Los registros contables no se eliminan; use anulación (contra-movimiento)."
        )

    delete.queryset_only = True


class SinBorradoMixin(models.Model):
    """Impide el borrado físico (instancia y QuerySet)."""

    objects = SinBorradoQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise BorradoFisicoProhibidoError(
            "Los registros contables no se eliminan; use anulación (contra-movimiento)."
        )


# ---------------------------------------------------------------------------
# Estructura organizativa
# ---------------------------------------------------------------------------
class Sucursal(CatalogoBase):
    codigo = models.CharField("código", max_length=20, unique=True)
    nombre = models.CharField("nombre", max_length=120)
    direccion = models.CharField("dirección", max_length=255, blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)

    class Meta:
        verbose_name = "sucursal"
        verbose_name_plural = "sucursales"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        super().save(*args, **kwargs)


class Almacen(CatalogoBase):
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.PROTECT, related_name="almacenes", verbose_name="sucursal"
    )
    codigo = models.CharField("código", max_length=20)
    nombre = models.CharField("nombre", max_length=120)
    descripcion = models.CharField("descripción", max_length=255, blank=True)

    class Meta:
        verbose_name = "almacén"
        verbose_name_plural = "almacenes"
        ordering = ["sucursal__codigo", "codigo"]
        constraints = [
            models.UniqueConstraint(fields=["sucursal", "codigo"], name="uq_almacen_sucursal_codigo"),
        ]
        indexes = [models.Index(fields=["sucursal", "estado"], name="idx_alm_suc_estado")]

    def __str__(self):
        return f"{self.sucursal.codigo}/{self.codigo} - {self.nombre}"

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Catálogo de productos
# ---------------------------------------------------------------------------
class Categoria(CatalogoBase):
    nombre = models.CharField("nombre", max_length=120)
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    padre = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subcategorias",
        verbose_name="categoría padre",
    )

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(Lower("nombre"), name="uq_categoria_nombre_ci"),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()
        # Evita jerarquías cíclicas (A → B → A).
        actual = self.padre
        visitados = set()
        while actual is not None:
            if actual.pk == self.pk and self.pk is not None:
                raise ValidationError({"padre": "La jerarquía de categorías no puede ser cíclica."})
            if actual.pk in visitados:
                break
            visitados.add(actual.pk)
            actual = actual.padre


class UnidadMedida(CatalogoBase):
    codigo = models.CharField("código", max_length=10, unique=True)
    nombre = models.CharField("nombre", max_length=60)
    permite_decimales = models.BooleanField(
        "permite decimales",
        default=False,
        help_text="Desmarcado para unidades indivisibles (unidad, caja); marcado para kg, litro, metro.",
    )

    class Meta:
        verbose_name = "unidad de medida"
        verbose_name_plural = "unidades de medida"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        super().save(*args, **kwargs)


class Producto(CatalogoBase):
    sku = models.CharField("SKU", max_length=50)
    codigo_barras = models.CharField("código de barras", max_length=50, unique=True, null=True, blank=True)
    nombre = models.CharField("nombre", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="productos", verbose_name="categoría"
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida, on_delete=models.PROTECT, related_name="productos", verbose_name="unidad de medida"
    )
    stock_minimo = campo_decimal("stock mínimo", default=CERO)
    precio_venta = campo_decimal("precio de venta referencial", default=CERO)
    maneja_lotes = models.BooleanField("maneja lotes", default=False)
    maneja_vencimiento = models.BooleanField(
        "maneja fecha de vencimiento",
        default=False,
        help_text="Requiere que el producto maneje lotes (p. ej. farmacia, alimentos).",
    )

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(Lower("sku"), name="uq_producto_sku_ci"),
            models.CheckConstraint(condition=models.Q(stock_minimo__gte=0), name="ck_producto_stock_min_gte0"),
            models.CheckConstraint(condition=models.Q(precio_venta__gte=0), name="ck_producto_precio_gte0"),
            models.CheckConstraint(
                condition=models.Q(maneja_vencimiento=False) | models.Q(maneja_lotes=True),
                name="ck_producto_vencimiento_requiere_lote",
            ),
        ]
        indexes = [
            models.Index(fields=["nombre"], name="idx_prod_nombre"),
            models.Index(fields=["categoria", "estado"], name="idx_prod_cat_estado"),
        ]

    def __str__(self):
        return f"{self.sku} - {self.nombre}"

    def clean(self):
        super().clean()
        if self.maneja_vencimiento and not self.maneja_lotes:
            raise ValidationError(
                {"maneja_vencimiento": "Un producto con vencimiento debe manejar lotes."}
            )

    def save(self, *args, **kwargs):
        self.sku = (self.sku or "").strip().upper()
        self.codigo_barras = (self.codigo_barras or "").strip() or None
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Terceros y tipos de movimiento
# ---------------------------------------------------------------------------
class Tercero(CatalogoBase):
    """Proveedores y/o clientes identificados por NIT o CI."""

    tipo = models.CharField("tipo", max_length=10, choices=TipoTercero.choices, default=TipoTercero.PROVEEDOR)
    tipo_documento = models.CharField(
        "tipo de documento", max_length=10, choices=TipoDocumento.choices, default=TipoDocumento.NIT
    )
    numero_documento = models.CharField("número de documento", max_length=30)
    nombre_razon_social = models.CharField("nombre / razón social", max_length=200)
    direccion = models.CharField("dirección", max_length=255, blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    email = models.EmailField("correo electrónico", blank=True)

    class Meta:
        verbose_name = "tercero"
        verbose_name_plural = "terceros"
        ordering = ["nombre_razon_social"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "numero_documento"], name="uq_tercero_documento"
            ),
        ]
        indexes = [models.Index(fields=["nombre_razon_social"], name="idx_ter_nombre")]

    def __str__(self):
        return f"{self.nombre_razon_social} ({self.tipo_documento} {self.numero_documento})"

    def save(self, *args, **kwargs):
        self.numero_documento = (self.numero_documento or "").strip().upper()
        super().save(*args, **kwargs)


class TipoMovimiento(CatalogoBase):
    """
    Tipo de operación: Compra (+), Venta (−), Ajuste por merma (−), Devolución (±),
    Traspaso salida (−) / Traspaso entrada (+), etc.
    """

    codigo = models.CharField("código", max_length=10, unique=True)
    nombre = models.CharField("nombre", max_length=100)
    signo = models.SmallIntegerField("signo de operación", choices=Signo.choices)
    requiere_tercero = models.BooleanField("requiere tercero", default=False)
    tipo_tercero = models.CharField(
        "tipo de tercero admitido",
        max_length=10,
        choices=[(TipoTercero.PROVEEDOR.value, "Proveedor"), (TipoTercero.CLIENTE.value, "Cliente")],
        blank=True,
        help_text="Vacío = sin restricción. Un tercero 'AMBOS' siempre es válido.",
    )
    es_traspaso = models.BooleanField(
        "es traspaso entre almacenes",
        default=False,
        help_text="Los traspasos generan dos comprobantes enlazados (salida en origen, entrada en destino).",
    )

    class Meta:
        verbose_name = "tipo de movimiento"
        verbose_name_plural = "tipos de movimiento"
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(condition=models.Q(signo__in=[1, -1]), name="ck_tipomov_signo"),
        ]

    def __str__(self):
        return f"{self.nombre} ({'+' if self.signo > 0 else '−'})"

    @property
    def es_entrada(self) -> bool:
        return self.signo == Signo.ENTRADA

    def clean(self):
        super().clean()
        errores = {}
        if self.tipo_tercero and not self.requiere_tercero:
            errores["tipo_tercero"] = "Defina 'requiere tercero' para restringir el tipo de tercero."
        if self.es_traspaso and self.requiere_tercero:
            errores["es_traspaso"] = "Un traspaso entre almacenes no involucra un tercero."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Comprobantes de inventario
# ---------------------------------------------------------------------------
class MovimientoInventario(SinBorradoMixin, AuditoriaBase):
    """
    Cabecera del comprobante. Siempre afecta a UN almacén; los traspasos se modelan con
    dos comprobantes enlazados por `movimiento_relacionado`.

    Anulación: se crea un contra-movimiento con `movimiento_anulado = <original>`; el
    original pasa a ESTADO ANULADO (con fecha, usuario y motivo). Ambos permanecen en el Kardex.
    """

    _CAMPOS_INMUTABLES = ("almacen_id", "tipo_movimiento_id", "fecha_movimiento", "tercero_id")

    numero_comprobante = models.CharField(
        "número de comprobante", max_length=30, unique=True, null=True, blank=True, editable=False
    )
    fecha_movimiento = models.DateTimeField("fecha del movimiento", default=timezone.now)
    almacen = models.ForeignKey(
        Almacen, on_delete=models.PROTECT, related_name="movimientos", verbose_name="almacén"
    )
    tipo_movimiento = models.ForeignKey(
        TipoMovimiento, on_delete=models.PROTECT, related_name="movimientos", verbose_name="tipo de movimiento"
    )
    tercero = models.ForeignKey(
        Tercero,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos",
        verbose_name="tercero",
    )
    numero_documento = models.CharField(
        "nº de documento de respaldo", max_length=50, blank=True, help_text="Factura, nota de entrega, etc."
    )
    observacion = models.TextField("observación", blank=True)
    total = campo_decimal("total del comprobante", default=CERO)
    estado = models.CharField(
        "estado", max_length=12, choices=EstadoMovimiento.choices, default=EstadoMovimiento.REGISTRADO
    )

    # Enlaces entre comprobantes
    movimiento_relacionado = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="traspaso: comprobante par",
    )
    movimiento_anulado = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contramovimiento",
        verbose_name="comprobante que anula",
    )

    # Datos de anulación (se llenan en el comprobante ORIGINAL)
    fecha_anulacion = models.DateTimeField("fecha de anulación", null=True, blank=True)
    usuario_anulacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="usuario que anuló",
    )
    motivo_anulacion = models.TextField("motivo de anulación", blank=True)

    class Meta:
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"
        ordering = ["-fecha_movimiento", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estado=EstadoMovimiento.REGISTRADO) | models.Q(fecha_anulacion__isnull=False),
                name="ck_mov_anulado_con_fecha",
            ),
            models.CheckConstraint(condition=models.Q(total__gte=0), name="ck_mov_total_gte0"),
        ]
        indexes = [
            models.Index(fields=["almacen", "fecha_movimiento"], name="idx_mov_alm_fecha"),
            models.Index(fields=["tipo_movimiento", "fecha_movimiento"], name="idx_mov_tipo_fecha"),
            models.Index(fields=["estado", "fecha_movimiento"], name="idx_mov_estado_fecha"),
            models.Index(fields=["tercero", "fecha_movimiento"], name="idx_mov_tercero_fecha"),
            models.Index(fields=["numero_documento"], name="idx_mov_numdoc"),
        ]

    def __str__(self):
        numero = self.numero_comprobante or "S/N"
        if not self.tipo_movimiento_id:
            return numero
        return f"{numero} · {self.tipo_movimiento.nombre}"

    # -- propiedades ------------------------------------------------------
    @property
    def es_anulacion(self) -> bool:
        return self.movimiento_anulado_id is not None

    @property
    def signo_efectivo(self) -> int:
        """+1 si incrementa stock, −1 si lo reduce (invierte el signo si es anulación)."""
        signo = self.tipo_movimiento.signo
        return -signo if self.es_anulacion else signo

    @property
    def esta_anulado(self) -> bool:
        return self.estado == EstadoMovimiento.ANULADO

    # -- validación -------------------------------------------------------
    def clean(self):
        super().clean()
        errores = {}
        tipo = self.tipo_movimiento if self.tipo_movimiento_id else None
        tercero = self.tercero if self.tercero_id else None
        almacen = self.almacen if self.almacen_id else None

        if almacen is not None and not almacen.estado and not self.es_anulacion:
            errores["almacen"] = "El almacén está inactivo."

        if tipo is not None:
            if not tipo.estado and not self.es_anulacion:
                errores["tipo_movimiento"] = "El tipo de movimiento está inactivo."
            if tipo.requiere_tercero and tercero is None:
                errores["tercero"] = f"El tipo «{tipo.nombre}» requiere indicar un tercero."
            if (
                tercero is not None
                and tipo.tipo_tercero
                and tercero.tipo not in (tipo.tipo_tercero, TipoTercero.AMBOS)
            ):
                errores["tercero"] = f"El tipo «{tipo.nombre}» solo admite terceros de tipo {tipo.tipo_tercero}."
            if tercero is not None and not tercero.estado and not self.es_anulacion:
                errores["tercero"] = "El tercero está inactivo."

        if self.movimiento_relacionado_id:
            if self.movimiento_relacionado_id == self.pk:
                errores["movimiento_relacionado"] = "Un comprobante no puede relacionarse consigo mismo."
            elif self.movimiento_relacionado.almacen_id == self.almacen_id:
                errores["movimiento_relacionado"] = "Los comprobantes de un traspaso deben ser de almacenes distintos."

        if self.movimiento_anulado_id and self.movimiento_anulado_id == self.pk:
            errores["movimiento_anulado"] = "Un comprobante no puede anularse a sí mismo."

        if self.estado == EstadoMovimiento.ANULADO and not self.fecha_anulacion:
            errores["fecha_anulacion"] = "Un comprobante anulado requiere fecha de anulación."

        if errores:
            raise ValidationError(errores)

    # -- persistencia -----------------------------------------------------
    def save(self, *args, **kwargs):
        with transaction.atomic():
            creando = self._state.adding

            if not creando:
                original = (
                    type(self)._base_manager.filter(pk=self.pk).values(*self._CAMPOS_INMUTABLES).first()
                )
                if original is not None:
                    for campo in self._CAMPOS_INMUTABLES:
                        if original[campo] != getattr(self, campo):
                            raise ModificacionProhibidaError(
                                f"El campo «{campo.removesuffix('_id')}» de un comprobante registrado no puede modificarse."
                            )

            super().save(*args, **kwargs)

            if creando and not self.numero_comprobante:
                prefijo = "ANU" if self.es_anulacion else self.tipo_movimiento.codigo
                self.numero_comprobante = f"{prefijo}-{self.pk:08d}"
                type(self)._base_manager.filter(pk=self.pk).update(numero_comprobante=self.numero_comprobante)

    def recalcular_total(self) -> Decimal:
        """Suma los subtotales de las líneas y persiste el total de la cabecera."""
        suma = self.detalles.aggregate(t=models.Sum("subtotal"))["t"] or CERO
        self.total = redondear(suma)
        self.save(update_fields=["total", "fecha_modificacion"])
        return self.total


class DetalleMovimiento(SinBorradoMixin, AuditoriaBase):
    """
    Línea del comprobante.

    - `precio_unitario`: costo de compra (entradas) o precio de venta (salidas).
    - `costo_promedio_historico`: costo unitario con el que la línea movió el inventario.
      En entradas es el costo de ingreso; en salidas es el PPP vigente al momento.
    - `saldo_*`: instantánea del saldo (almacén + producto) DESPUÉS de aplicar la línea.
    Las líneas son inmutables una vez creadas: para corregir se anula el comprobante.
    """

    movimiento = models.ForeignKey(
        MovimientoInventario, on_delete=models.PROTECT, related_name="detalles", verbose_name="movimiento"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="detalles_movimiento", verbose_name="producto"
    )
    cantidad = campo_decimal("cantidad", minimo=UNIDAD_MINIMA)
    precio_unitario = campo_decimal("precio unitario", default=CERO)
    costo_promedio_historico = campo_decimal("costo promedio histórico", default=CERO)
    subtotal = campo_decimal("subtotal", default=CERO, editable=False)
    costo_total = campo_decimal("costo total", default=CERO, editable=False)

    lote = models.CharField("lote", max_length=50, blank=True)
    fecha_vencimiento = models.DateField("fecha de vencimiento", null=True, blank=True)

    saldo_cantidad = campo_decimal("saldo: cantidad", default=CERO)
    saldo_costo_promedio = campo_decimal("saldo: costo promedio", default=CERO)
    saldo_valor = campo_decimal("saldo: valor", default=CERO)

    class Meta:
        verbose_name = "detalle de movimiento"
        verbose_name_plural = "detalles de movimiento"
        ordering = ["movimiento_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["movimiento", "producto", "lote"], name="uq_detalle_mov_prod_lote"),
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="ck_detalle_cantidad_gt0"),
            models.CheckConstraint(condition=models.Q(precio_unitario__gte=0), name="ck_detalle_precio_gte0"),
            models.CheckConstraint(
                condition=models.Q(costo_promedio_historico__gte=0), name="ck_detalle_costo_gte0"
            ),
            models.CheckConstraint(condition=models.Q(saldo_cantidad__gte=0), name="ck_detalle_saldo_gte0"),
        ]
        indexes = [models.Index(fields=["producto", "movimiento"], name="idx_det_prod_mov")]

    def __str__(self):
        return f"{self.producto.sku} × {self.cantidad}"

    def calcular_importes(self):
        """Calcula subtotal (a precio) y costo_total (a costo promedio) con 4 decimales."""
        self.subtotal = multiplicar(self.cantidad, self.precio_unitario)
        self.costo_total = multiplicar(self.cantidad, self.costo_promedio_historico)

    def clean(self):
        super().clean()
        errores = {}
        movimiento = self.movimiento if self.movimiento_id else None
        es_anulacion = movimiento.es_anulacion if movimiento else False

        if self.producto_id:
            producto = self.producto
            if not producto.estado and not es_anulacion:
                errores["producto"] = "El producto está inactivo."

            if (
                isinstance(self.cantidad, Decimal)
                and not producto.unidad_medida.permite_decimales
                and self.cantidad != self.cantidad.to_integral_value()
            ):
                errores["cantidad"] = (
                    f"La unidad «{producto.unidad_medida.codigo}» no admite cantidades decimales."
                )

            if producto.maneja_lotes and not self.lote:
                errores["lote"] = "El producto maneja lotes: indique el lote."
            if not producto.maneja_lotes and self.lote:
                errores["lote"] = "El producto no maneja lotes."
            if (
                producto.maneja_vencimiento
                and movimiento is not None
                and not es_anulacion
                and movimiento.signo_efectivo == Signo.ENTRADA
                and not self.fecha_vencimiento
            ):
                errores["fecha_vencimiento"] = "El producto maneja vencimiento: indique la fecha."

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ModificacionProhibidaError(
                "Las líneas de un comprobante no se modifican; anule el movimiento y registre uno nuevo."
            )
        self.calcular_importes()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Stock consolidado
# ---------------------------------------------------------------------------
class StockAlmacen(SinBorradoMixin, AuditoriaBase):
    """
    Resumen consolidado (almacén + producto) para lecturas rápidas y base del cálculo PPP.

    Uso previsto en la capa de servicios (dentro de `transaction.atomic`):

        stock, _ = StockAlmacen.objects.select_for_update().get_or_create(
            almacen=almacen, producto=producto)
        costo = stock.aplicar_salida(cantidad)     # o stock.aplicar_entrada(cantidad, costo)
        stock.save()
        # ...y copiar stock.cantidad / costo_promedio / valor_total a la línea (saldo_*).
    """

    almacen = models.ForeignKey(
        Almacen, on_delete=models.PROTECT, related_name="stocks", verbose_name="almacén"
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="stocks", verbose_name="producto"
    )
    cantidad = campo_decimal("cantidad", default=CERO)
    costo_promedio = campo_decimal("costo promedio (PPP)", default=CERO)
    valor_total = campo_decimal("valor total", default=CERO)

    class Meta:
        verbose_name = "stock por almacén"
        verbose_name_plural = "stock por almacén"
        ordering = ["almacen_id", "producto_id"]
        constraints = [
            models.UniqueConstraint(fields=["almacen", "producto"], name="uq_stock_almacen_producto"),
            models.CheckConstraint(condition=models.Q(cantidad__gte=0), name="ck_stock_cantidad_gte0"),
            models.CheckConstraint(condition=models.Q(costo_promedio__gte=0), name="ck_stock_costo_gte0"),
            models.CheckConstraint(condition=models.Q(valor_total__gte=0), name="ck_stock_valor_gte0"),
        ]
        indexes = [models.Index(fields=["producto"], name="idx_stock_producto")]

    def __str__(self):
        return f"{self.almacen.codigo} | {self.producto.sku}: {self.cantidad}"

    @property
    def bajo_minimo(self) -> bool:
        return self.cantidad <= self.producto.stock_minimo

    # -- Precio Promedio Ponderado ---------------------------------------
    def aplicar_entrada(self, cantidad, costo_unitario) -> Decimal:
        """
        Entrada: nuevo PPP = (valor actual + cantidad × costo) / (stock actual + cantidad).
        Modifica la instancia en memoria (el llamador la bloquea y guarda) y devuelve el
        costo unitario aplicado.
        """
        cantidad = _a_decimal(cantidad)
        costo_unitario = redondear(costo_unitario)
        if cantidad <= CERO:
            raise ValueError("La cantidad de entrada debe ser mayor que cero.")
        if costo_unitario < CERO:
            raise ValueError("El costo unitario no puede ser negativo.")

        nueva_cantidad = self.cantidad + cantidad
        nuevo_valor = self.valor_total + multiplicar(cantidad, costo_unitario)

        self.cantidad = nueva_cantidad
        self.valor_total = nuevo_valor
        self.costo_promedio = redondear(nuevo_valor / nueva_cantidad)
        return costo_unitario

    def aplicar_salida(self, cantidad) -> Decimal:
        """
        Salida: se valora al PPP vigente, que no cambia. Si el stock llega a cero el valor
        se fija en 0 para no arrastrar residuos de redondeo. Devuelve el PPP aplicado.
        """
        cantidad = _a_decimal(cantidad)
        if cantidad <= CERO:
            raise ValueError("La cantidad de salida debe ser mayor que cero.")
        if cantidad > self.cantidad:
            raise StockInsuficienteError(self.cantidad, cantidad, producto=self.producto)

        costo = self.costo_promedio
        self.cantidad = self.cantidad - cantidad
        if self.cantidad == CERO:
            self.valor_total = CERO
        else:
            self.valor_total = max(self.valor_total - multiplicar(cantidad, costo), CERO)
        return costo

    def revertir_entrada(self, cantidad, costo_unitario) -> Decimal:
        """
        Anulación de una entrada: retira `cantidad` al costo con el que ingresó (no al PPP
        actual) y recalcula el PPP con el saldo restante. Si no ha habido otros movimientos
        entre medio, el PPP vuelve exactamente al valor previo a la entrada.
        """
        cantidad = _a_decimal(cantidad)
        costo_unitario = redondear(costo_unitario)
        if cantidad <= CERO:
            raise ValueError("La cantidad a revertir debe ser mayor que cero.")
        if cantidad > self.cantidad:
            raise StockInsuficienteError(self.cantidad, cantidad, producto=self.producto)

        self.cantidad = self.cantidad - cantidad
        if self.cantidad == CERO:
            self.valor_total = CERO
        else:
            self.valor_total = max(self.valor_total - multiplicar(cantidad, costo_unitario), CERO)
            self.costo_promedio = redondear(self.valor_total / self.cantidad)
        return costo_unitario
