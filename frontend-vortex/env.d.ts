/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL base de la API REST de Vortex, p. ej. http://localhost:8000/api */
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
