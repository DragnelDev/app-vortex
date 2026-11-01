const formatoNumero = new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
const formatoFecha = new Intl.DateTimeFormat('es-BO', { dateStyle: 'short', timeStyle: 'short' })

/** Formatea un decimal de la API (string) para mostrarlo. */
export function numero(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return formatoNumero.format(Number(valor))
}

export function fechaHora(iso: string | null | undefined): string {
  return iso ? formatoFecha.format(new Date(iso)) : '—'
}

/** YYYY-MM-DD en hora local (evita el desfase de toISOString()). */
export function fechaISO(d: Date): string {
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

/** Decimal con 4 decimales fijos para enviar a la API. */
export function decimal4(valor: number | null | undefined): string {
  return (valor ?? 0).toFixed(4)
}
