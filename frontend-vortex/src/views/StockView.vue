<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DataTable, { type DataTablePageEvent, type DataTableSortEvent } from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { listar } from '@/api/inventario'
import { mensajeError } from '@/api/http'
import { numero } from '@/utils/formato'
import type { Almacen, Stock } from '@/types/inventario'

const toast = useToast()
const filas = ref<Stock[]>([])
const total = ref(0)
const primero = ref(0)
const porPagina = ref(20)
const cargando = ref(false)
const busqueda = ref('')
const almacenId = ref<number | null>(null)
const soloBajo = ref(false)
const orden = ref<string | undefined>(undefined)
const almacenes = ref<Almacen[]>([])
let temporizador: ReturnType<typeof setTimeout> | undefined

async function cargar() {
  cargando.value = true
  try {
    const r = await listar<Stock>('stock', {
      page: primero.value / porPagina.value + 1,
      page_size: porPagina.value,
      search: busqueda.value,
      almacen: almacenId.value,
      bajo_minimo: soloBajo.value ? true : undefined,
      ordering: orden.value,
    })
    filas.value = r.results
    total.value = r.count
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error al cargar stock', detail: mensajeError(e), life: 5000 })
  } finally {
    cargando.value = false
  }
}

function refiltrar() {
  primero.value = 0
  cargar()
}
function buscarConRetardo() {
  clearTimeout(temporizador)
  temporizador = setTimeout(refiltrar, 350)
}
function alPaginar(e: DataTablePageEvent) {
  primero.value = e.first
  porPagina.value = e.rows
  cargar()
}
function alOrdenar(e: DataTableSortEvent) {
  orden.value = e.sortField ? `${e.sortOrder === -1 ? '-' : ''}${e.sortField}` : undefined
  refiltrar()
}

onMounted(async () => {
  almacenes.value = (await listar<Almacen>('almacenes', { estado: true, page_size: 200 })).results
  cargar()
})
</script>

<template>
  <div class="space-y-4">
    <section class="panel">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div>
          <label class="etiqueta">Buscar</label>
          <InputText v-model="busqueda" placeholder="SKU o nombre" fluid @input="buscarConRetardo" />
        </div>
        <div>
          <label class="etiqueta">Almacén</label>
          <Select v-model="almacenId" :options="almacenes" option-label="nombre" option-value="id" placeholder="Todos" show-clear fluid @change="refiltrar" />
        </div>
        <div class="flex items-end gap-3 pb-2">
          <ToggleSwitch v-model="soloBajo" input-id="bajo" @change="refiltrar" />
          <label for="bajo" class="text-sm">Solo bajo el mínimo</label>
        </div>
      </div>
    </section>

    <section class="panel !p-0 overflow-hidden">
      <DataTable
        :value="filas" data-key="id" lazy paginator :rows="porPagina" :first="primero" :total-records="total"
        :rows-per-page-options="[10, 20, 50, 100]" :loading="cargando" size="small" striped-rows
        @page="alPaginar" @sort="alOrdenar"
      >
        <template #empty><p class="p-6 text-center text-slate-500">Sin existencias registradas.</p></template>
        <Column field="producto_sku" header="SKU" />
        <Column field="producto_nombre" header="Producto" sortable sort-field="producto__nombre" />
        <Column field="almacen_nombre" header="Almacén" sortable sort-field="almacen__nombre" />
        <Column field="cantidad" header="Cantidad" sortable body-class="text-right">
          <template #body="{ data }">{{ numero(data.cantidad) }} {{ data.unidad_codigo }}</template>
        </Column>
        <Column header="Mínimo" body-class="text-right"><template #body="{ data }">{{ numero(data.stock_minimo) }}</template></Column>
        <Column header="PPP" body-class="text-right"><template #body="{ data }">{{ numero(data.costo_promedio) }}</template></Column>
        <Column field="valor_total" header="Valor" sortable body-class="text-right"><template #body="{ data }">{{ numero(data.valor_total) }}</template></Column>
        <Column header="Estado">
          <template #body="{ data }">
            <Tag v-if="data.bajo_minimo" :value="Number(data.cantidad) === 0 ? 'Agotado' : 'Bajo mínimo'" :severity="Number(data.cantidad) === 0 ? 'danger' : 'warn'" />
            <Tag v-else value="Normal" severity="success" />
          </template>
        </Column>
      </DataTable>
    </section>
  </div>
</template>
