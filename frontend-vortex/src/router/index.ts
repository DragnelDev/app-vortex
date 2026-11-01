import { createRouter, createWebHistory } from 'vue-router'
import { tokens } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { publica: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { titulo: 'Dashboard' },
        },
        {
          path: 'kardex',
          name: 'kardex',
          component: () => import('@/views/KardexView.vue'),
          meta: { titulo: 'Kardex físico-valorado' },
        },
        {
          path: 'movimientos',
          name: 'movimientos',
          component: () => import('@/views/MovimientosView.vue'),
          meta: { titulo: 'Comprobantes' },
        },
        {
          path: 'movimientos/nuevo',
          name: 'movimiento-nuevo',
          component: () => import('@/views/MovimientoNuevoView.vue'),
          meta: { titulo: 'Nuevo movimiento' },
        },
        {
          path: 'stock',
          name: 'stock',
          component: () => import('@/views/StockView.vue'),
          meta: { titulo: 'Stock por almacén' },
        },
        {
          path: 'catalogos/:clave',
          name: 'catalogo',
          component: () => import('@/views/CatalogoView.vue'),
          meta: { titulo: 'Catálogo' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: { name: 'dashboard' } },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.publica) return true
  if (!tokens.access) return { name: 'login', query: { redirect: to.fullPath } }
  const auth = useAuthStore()
  if (!auth.usuario) {
    try {
      await auth.cargarUsuario()
    } catch {
      auth.logout()
      return { name: 'login' }
    }
  }
  return true
})

export default router
