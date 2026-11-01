import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

const CLAVE_ACCESS = 'vortex.access'
const CLAVE_REFRESH = 'vortex.refresh'

/** Almacén de tokens JWT (localStorage con tolerancia a fallos). */
export const tokens = {
  get access(): string | null {
    try { return localStorage.getItem(CLAVE_ACCESS) } catch { return null }
  },
  get refresh(): string | null {
    try { return localStorage.getItem(CLAVE_REFRESH) } catch { return null }
  },
  guardar(access: string, refresh?: string) {
    try {
      localStorage.setItem(CLAVE_ACCESS, access)
      if (refresh) localStorage.setItem(CLAVE_REFRESH, refresh)
    } catch { /* almacenamiento no disponible */ }
  },
  limpiar() {
    try {
      localStorage.removeItem(CLAVE_ACCESS)
      localStorage.removeItem(CLAVE_REFRESH)
    } catch { /* almacenamiento no disponible */ }
  },
}

export const http = axios.create({ baseURL: API_URL })

http.interceptors.request.use((config) => {
  const token = tokens.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refrescando: Promise<string | null> | null = null

async function refrescarAccess(): Promise<string | null> {
  const refresh = tokens.refresh
  if (!refresh) return null
  try {
    const { data } = await axios.post(`${API_URL}/auth/token/refresh/`, { refresh })
    tokens.guardar(data.access, data.refresh)
    return data.access as string
  } catch {
    return null
  }
}

http.interceptors.response.use(
  (respuesta) => respuesta,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _reintento?: boolean }) | undefined
    const esLogin = original?.url?.includes('/auth/token')
    if (error.response?.status === 401 && original && !original._reintento && !esLogin) {
      original._reintento = true
      refrescando ??= refrescarAccess().finally(() => { refrescando = null })
      const nuevo = await refrescando
      if (nuevo) {
        original.headers.Authorization = `Bearer ${nuevo}`
        return http(original)
      }
      tokens.limpiar()
      const { default: router } = await import('@/router')
      router.push({ name: 'login' })
    }
    return Promise.reject(error)
  },
)

/** Convierte cualquier error de la API (DRF) en un mensaje legible. */
export function mensajeError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'No se pudo conectar con el servidor.'
    const data = error.response.data
    if (typeof data === 'string') return data.slice(0, 200)
    if (data && typeof data === 'object') {
      if ('detail' in data && typeof data.detail === 'string') return data.detail
      const partes = Object.entries(data as Record<string, unknown>).map(([campo, valor]) => {
        const texto = Array.isArray(valor) ? valor.map((v) => (typeof v === 'object' ? JSON.stringify(v) : String(v))).join(' ') : String(valor)
        return campo === 'non_field_errors' ? texto : `${campo}: ${texto}`
      })
      if (partes.length) return partes.join(' · ')
    }
    return `Error ${error.response.status}`
  }
  return error instanceof Error ? error.message : 'Error inesperado.'
}
