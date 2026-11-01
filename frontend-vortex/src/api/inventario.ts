import { http } from './http'
import type {
  DashboardResumen, KardexRespuesta, LineaPayload, MovimientoDetalle, Paginado, Producto, Stock,
} from '@/types/inventario'

export type Params = Record<string, string | number | boolean | undefined | null>

function limpiar(params: Params = {}): Params {
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
}

// --- CRUD genérico de catálogos (DELETE = baja lógica en el backend) -----------
export async function listar<T>(recurso: string, params?: Params): Promise<Paginado<T>> {
  return (await http.get<Paginado<T>>(`/${recurso}/`, { params: limpiar(params) })).data
}
export async function crear<T>(recurso: string, datos: unknown): Promise<T> {
  return (await http.post<T>(`/${recurso}/`, datos)).data
}
export async function actualizar<T>(recurso: string, id: number, datos: unknown): Promise<T> {
  return (await http.patch<T>(`/${recurso}/${id}/`, datos)).data
}
export async function darDeBaja(recurso: string, id: number): Promise<void> {
  await http.delete(`/${recurso}/${id}/`)
}

// --- Búsquedas y consultas --------------------------------------------------
export const buscarProductos = (texto: string) =>
  listar<Producto>('productos', { search: texto, estado: true, page_size: 15 })

export async function stockDisponible(almacen: number, producto: number): Promise<number> {
  const r = await listar<Stock>('stock', { almacen, producto, page_size: 1 })
  return Number(r.results[0]?.cantidad ?? 0)
}

export const dashboard = async () => (await http.get<DashboardResumen>('/dashboard/resumen/')).data

// --- Kardex ---------------------------------------------------------------------
export interface FiltroKardex { producto: number; almacen: number; desde?: string; hasta?: string }

export async function kardex(filtro: FiltroKardex, page: number, pageSize: number): Promise<KardexRespuesta> {
  return (await http.get<KardexRespuesta>('/kardex/', { params: limpiar({ ...filtro, page, page_size: pageSize }) })).data
}

export async function exportarKardexCsv(filtro: FiltroKardex): Promise<void> {
  const r = await http.get<Blob>('/kardex/exportar/', { params: limpiar({ ...filtro }), responseType: 'blob' })
  const url = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `kardex_${filtro.producto}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// --- Comprobantes ---------------------------------------------------------------
export interface ComprobantePayload {
  fecha_movimiento?: string
  numero_documento: string
  observacion: string
  lineas: LineaPayload[]
}
export interface MovimientoPayload extends ComprobantePayload {
  almacen: number
  tipo_movimiento: number
  tercero: number | null
}
export interface TraspasoPayload extends ComprobantePayload {
  almacen_origen: number
  almacen_destino: number
}

export const registrarMovimiento = async (datos: MovimientoPayload) =>
  (await http.post<MovimientoDetalle>('/movimientos/', datos)).data

export const registrarTraspaso = async (datos: TraspasoPayload) =>
  (await http.post<{ salida: MovimientoDetalle; entrada: MovimientoDetalle }>('/movimientos/traspaso/', datos)).data

export const detalleMovimiento = async (id: number) => (await http.get<MovimientoDetalle>(`/movimientos/${id}/`)).data

export const anularMovimiento = async (id: number, motivo: string) =>
  (await http.post<MovimientoDetalle>(`/movimientos/${id}/anular/`, { motivo })).data
