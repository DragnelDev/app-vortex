/**
 * Validación de stock disponible en el cliente (la API sigue siendo la fuente de verdad).
 * Se opera en enteros escalados (×10⁴) para evitar errores de coma flotante al sumar.
 */
const ESCALA = 10_000

export const escalar = (v: number | string | null | undefined): number => Math.round(Number(v ?? 0) * ESCALA)

export interface LineaStock {
  productoId: number | null
  cantidad: number | null
}

/**
 * Devuelve {índiceDeLínea: mensaje} para las líneas cuyo producto, sumado a lo largo de
 * todo el comprobante, supera el stock disponible.
 */
export function validarSalida(lineas: LineaStock[], disponibles: Record<number, number>): Record<number, string> {
  const solicitado = new Map<number, number>()
  for (const l of lineas) {
    if (l.productoId == null) continue
    solicitado.set(l.productoId, (solicitado.get(l.productoId) ?? 0) + escalar(l.cantidad))
  }
  const errores: Record<number, string> = {}
  lineas.forEach((l, i) => {
    if (l.productoId == null) return
    const total = solicitado.get(l.productoId) ?? 0
    const disp = escalar(disponibles[l.productoId] ?? 0)
    if (total > disp) {
      errores[i] = `Stock insuficiente: disponible ${disp / ESCALA}, solicitado ${total / ESCALA}`
    }
  })
  return errores
}
