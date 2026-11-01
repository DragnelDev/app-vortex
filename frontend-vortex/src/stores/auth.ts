import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import { API_URL, http, tokens } from '@/api/http'

export interface Usuario {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
  is_staff: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const usuario = ref<Usuario | null>(null)
  const autenticado = computed(() => !!tokens.access)
  const nombre = computed(() => usuario.value?.first_name || usuario.value?.username || '')

  async function cargarUsuario() {
    usuario.value = (await http.get<Usuario>('/auth/me/')).data
  }

  async function login(username: string, password: string) {
    const { data } = await axios.post(`${API_URL}/auth/token/`, { username, password })
    tokens.guardar(data.access, data.refresh)
    await cargarUsuario()
  }

  function logout() {
    tokens.limpiar()
    usuario.value = null
  }

  return { usuario, autenticado, nombre, cargarUsuario, login, logout }
})
