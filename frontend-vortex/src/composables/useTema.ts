import { ref } from 'vue'

const CLAVE = 'vortex.tema'
export const oscuro = ref(true)

function aplicar() {
  document.documentElement.classList.toggle('app-dark', oscuro.value)
}

/** Lee la preferencia guardada (por defecto, modo oscuro) y la aplica al <html>. */
export function iniciarTema() {
  try {
    oscuro.value = localStorage.getItem(CLAVE) !== 'claro'
  } catch {
    oscuro.value = true
  }
  aplicar()
}

export function alternarTema() {
  oscuro.value = !oscuro.value
  try { localStorage.setItem(CLAVE, oscuro.value ? 'oscuro' : 'claro') } catch { /* sin almacenamiento */ }
  aplicar()
}
