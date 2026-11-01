<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import { RouterLink } from 'vue-router'
import { dashboard, listar } from '@/api/inventario'
import { numero } from '@/utils/formato'
import type { DashboardResumen, Stock } from '@/types/inventario'

const resumen = ref<DashboardResumen | null>(null)
const criticos = ref<Stock[]>([])
const cargando = ref(true)

onMounted(async () => {
  try {
    const [r, s] = await Promise.all([dashboard(), listar<Stock>('stock', { bajo_minimo: true, page_size: 10, ordering: 'cantidad' })])
    resumen.value = r
    criticos.value = s.results
  } finally {
    cargando.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <section class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <div class="panel">
        <p class="etiqueta">Valor del inventario</p>
        <p class="text-2xl font-semibold">Bs {{ numero(resumen?.valor_inventario) }}</p>
      </div>
      <div class="panel">
        <p class="etiqueta">Productos activos</p>
        <p class="text-2xl font-semibold">{{ resumen?.productos_activos ?? '—' }}</p>
      </div>
      <div class="panel">
        <p class="etiqueta">Ítems bajo el mínimo</p>
        <p class="text-2xl font-semibold" :class="resumen?.items_bajo_minimo ? 'text-amber-500' : ''">{{ resumen?.items_bajo_minimo ?? '—' }}</p>
      </div>
      <div class="panel">
        <p class="etiqueta">Comprobantes del mes</p>
        <p class="text-2xl font-semibold">{{ resumen?.movimientos_mes ?? '—' }}</p>
      </div>
    </section>

    <section class="panel !p-0 overflow-hidden">
      <div class="flex items-center justify-between px-4 pt-4">
        <h2 class="font-semibold">Stock crítico</h2>
        <RouterLink to="/stock" class="text-sm text-indigo-500 hover:underline">Ver todo</RouterLink>
      </div>
      <DataTable :value="criticos" :loading="cargando" size="small" class="mt-2">
        <template #empty><p class="p-6 text-center text-slate-500">Todo el stock está por encima del mínimo.</p></template>
        <Column field="producto_sku" header="SKU" />
        <Column field="producto_nombre" header="Producto" />
        <Column field="almacen_nombre" header="Almacén" />
        <Column header="Disponible" body-class="text-right" header-class="justify-end">
          <template #body="{ data }">{{ numero(data.cantidad) }} {{ data.unidad_codigo }}</template>
        </Column>
        <Column header="Mínimo" body-class="text-right">
          <template #body="{ data }">{{ numero(data.stock_minimo) }}</template>
        </Column>
        <Column header="">
          <template #body="{ data }"><Tag :value="Number(data.cantidad) === 0 ? 'Agotado' : 'Bajo mínimo'" :severity="Number(data.cantidad) === 0 ? 'danger' : 'warn'" /></template>
        </Column>
      </DataTable>
    </section>
  </div>
</template>
