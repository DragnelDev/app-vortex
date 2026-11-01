<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useAuthStore } from '@/stores/auth'
import { mensajeError } from '@/api/http'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const cargando = ref(false)
const error = ref('')

async function ingresar() {
  error.value = ''
  cargando.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    await router.replace((route.query.redirect as string) || { name: 'dashboard' })
  } catch (e) {
    error.value = mensajeError(e).includes('No active account') ? 'Usuario o contraseña incorrectos.' : mensajeError(e)
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <main class="flex min-h-full items-center justify-center p-4">
    <div class="panel w-full max-w-sm space-y-5">
      <div class="text-center">
        <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-white">
          <i class="pi pi-box text-2xl" />
        </div>
        <h1 class="text-2xl font-semibold">Vortex</h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">Control de inventario y Kardex</p>
      </div>

      <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

      <form class="space-y-4" @submit.prevent="ingresar">
        <div>
          <label class="etiqueta" for="usuario">Usuario</label>
          <InputText id="usuario" v-model="username" fluid autocomplete="username" autofocus />
        </div>
        <div>
          <label class="etiqueta" for="clave">Contraseña</label>
          <Password v-model="password" input-id="clave" :feedback="false" toggle-mask fluid autocomplete="current-password" />
        </div>
        <Button type="submit" label="Ingresar" icon="pi pi-sign-in" fluid :loading="cargando" :disabled="!username || !password" />
      </form>
    </div>
  </main>
</template>
