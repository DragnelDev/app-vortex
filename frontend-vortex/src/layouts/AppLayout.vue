<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import { useAuthStore } from '@/stores/auth'
import { alternarTema, oscuro } from '@/composables/useTema'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const menuAbierto = ref(false)

interface Item { to: string; label: string; icon: string }
const principal: Item[] = [
  { to: '/', label: 'Dashboard', icon: 'pi-chart-bar' },
  { to: '/kardex', label: 'Kardex', icon: 'pi-book' },
  { to: '/movimientos/nuevo', label: 'Nuevo movimiento', icon: 'pi-plus-circle' },
  { to: '/movimientos', label: 'Comprobantes', icon: 'pi-file' },
  { to: '/stock', label: 'Stock', icon: 'pi-warehouse' },
]
const catalogos: Item[] = [
  { to: '/catalogos/productos', label: 'Productos', icon: 'pi-tag' },
  { to: '/catalogos/categorias', label: 'Categorías', icon: 'pi-sitemap' },
  { to: '/catalogos/unidades', label: 'Unidades de medida', icon: 'pi-calculator' },
  { to: '/catalogos/terceros', label: 'Proveedores y clientes', icon: 'pi-users' },
  { to: '/catalogos/almacenes', label: 'Almacenes', icon: 'pi-building' },
  { to: '/catalogos/sucursales', label: 'Sucursales', icon: 'pi-map-marker' },
  { to: '/catalogos/tipos-movimiento', label: 'Tipos de movimiento', icon: 'pi-arrows-h' },
]

function activo(to: string) {
  return to === '/' ? route.path === '/' : route.path === to || (to !== '/movimientos' && route.path.startsWith(to + '/'))
}

function salir() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="flex h-full">
    <div v-if="menuAbierto" class="fixed inset-0 z-30 bg-black/50 lg:hidden" @click="menuAbierto = false" />

    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform dark:border-slate-800 dark:bg-slate-900 lg:static lg:translate-x-0"
      :class="menuAbierto ? 'translate-x-0' : '-translate-x-full'"
    >
      <div class="flex h-16 items-center gap-3 px-5">
        <span class="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white"><i class="pi pi-box" /></span>
        <span class="text-lg font-semibold tracking-tight">Vortex</span>
      </div>

      <nav class="flex-1 space-y-6 overflow-y-auto px-3 py-2" @click="menuAbierto = false">
        <div class="space-y-1">
          <RouterLink
            v-for="i in principal" :key="i.to" :to="i.to"
            class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
            :class="activo(i.to) ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'"
          >
            <i class="pi" :class="i.icon" /> {{ i.label }}
          </RouterLink>
        </div>
        <div>
          <p class="etiqueta px-3">Catálogos</p>
          <div class="space-y-1">
            <RouterLink
              v-for="i in catalogos" :key="i.to" :to="i.to"
              class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
              :class="activo(i.to) ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'"
            >
              <i class="pi" :class="i.icon" /> {{ i.label }}
            </RouterLink>
          </div>
        </div>
      </nav>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900">
        <Button class="lg:hidden" icon="pi pi-bars" text rounded aria-label="Menú" @click="menuAbierto = true" />
        <h1 class="truncate text-lg font-semibold">{{ route.meta.titulo }}</h1>
        <div class="ml-auto flex items-center gap-2">
          <span class="hidden text-sm text-slate-500 dark:text-slate-400 sm:inline">{{ auth.nombre }}</span>
          <Button :icon="oscuro ? 'pi pi-sun' : 'pi pi-moon'" text rounded severity="secondary" aria-label="Cambiar tema" @click="alternarTema" />
          <Button icon="pi pi-sign-out" text rounded severity="secondary" aria-label="Salir" @click="salir" />
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-4 lg:p-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
