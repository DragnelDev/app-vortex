/** Los decimales (14,4) llegan de la API como string para no perder precisión. */
export type Decimal = string

export interface Paginado<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Sucursal { id: number; codigo: string; nombre: string; estado: boolean }
export interface Almacen { id: number; sucursal: number; sucursal_nombre: string; codigo: string; nombre: string; estado: boolean }
export interface Categoria { id: number; nombre: string; padre: number | null; estado: boolean }
export interface UnidadMedida { id: number; codigo: string; nombre: string; permite_decimales: boolean; estado: boolean }

export interface Producto {
  id: number
  sku: string
  nombre: string
  codigo_barras: string | null
  categoria: number
  categoria_nombre: string
  unidad_medida: number
  unidad_codigo: string
  unidad_permite_decimales: boolean
  stock_minimo: Decimal
  precio_venta: Decimal
  stock_total?: Decimal
  maneja_lotes: boolean
  maneja_vencimiento: boolean
  estado: boolean
}

export type TipoTercero = 'PROVEEDOR' | 'CLIENTE' | 'AMBOS'
export interface Tercero {
  id: number
  tipo: TipoTercero
  tipo_documento: string
  numero_documento: string
  nombre_razon_social: string
  estado: boolean
}

export interface TipoMovimiento {
  id: number
  codigo: string
  nombre: string
  signo: 1 | -1
  requiere_tercero: boolean
  tipo_tercero: '' | 'PROVEEDOR' | 'CLIENTE'
  es_traspaso: boolean
  estado: boolean
}

export type EstadoMovimiento = 'REGISTRADO' | 'ANULADO'

export interface Movimiento {
  id: number
  numero_comprobante: string
  fecha_movimiento: string
  almacen: number
  almacen_nombre: string
  tipo_movimiento: number
  tipo_nombre: string
  signo_efectivo: 1 | -1
  es_anulacion: boolean
  tercero: number | null
  tercero_nombre: string | null
  numero_documento: string
  observacion: string
  total: Decimal
  estado: EstadoMovimiento
  anulado_por: string | null
  motivo_anulacion: string
}

export interface DetalleMovimiento {
  id: number
  producto: number
  producto_sku: string
  producto_nombre: string
  unidad_codigo: string
  cantidad: Decimal
  precio_unitario: Decimal
  costo_promedio_historico: Decimal
  subtotal: Decimal
  lote: string
  saldo_cantidad: Decimal
}
export interface MovimientoDetalle extends Movimiento { detalles: DetalleMovimiento[] }

export interface Stock {
  id: number
  almacen: number
  almacen_nombre: string
  producto: number
  producto_sku: string
  producto_nombre: string
  unidad_codigo: string
  stock_minimo: Decimal
  cantidad: Decimal
  costo_promedio: Decimal
  valor_total: Decimal
  bajo_minimo: boolean
}

export interface KardexFila {
  id: number
  movimiento_id: number
  fecha: string
  comprobante: string
  tipo: string
  tercero: string | null
  documento: string
  estado: EstadoMovimiento
  es_anulacion: boolean
  lote: string
  entrada_cantidad: Decimal; entrada_costo: Decimal; entrada_total: Decimal
  salida_cantidad: Decimal; salida_costo: Decimal; salida_total: Decimal
  saldo_cantidad: Decimal; saldo_costo: Decimal; saldo_valor: Decimal
}

export interface SaldoKardex { cantidad: Decimal; costo: Decimal; valor: Decimal }
export interface KardexResumen {
  saldo_inicial: SaldoKardex
  entradas: { cantidad: Decimal; valor: Decimal }
  salidas: { cantidad: Decimal; valor: Decimal }
  saldo_final: SaldoKardex
}
export interface KardexRespuesta extends Paginado<KardexFila> { resumen: KardexResumen }

export interface DashboardResumen {
  productos_activos: number
  valor_inventario: Decimal
  items_bajo_minimo: number
  movimientos_mes: number
}

export interface LineaPayload {
  producto: number
  cantidad: string
  precio_unitario: string
  lote: string
  fecha_vencimiento: string | null
}
