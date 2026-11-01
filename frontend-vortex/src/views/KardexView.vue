<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import DataTable, { type DataTablePageEvent } from 'primevue/datatable'
import Column from 'primevue/column'
import ColumnGroup from 'primevue/columngroup'
import Row from 'primevue/row'
import Select from 'primevue/select'
import AutoComplete, { type AutoCompleteCompleteEvent } from 'primevue/autocomplete'
import DatePicker from 'primevue/datepicker'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import EstadoTag from '@/components/EstadoTag.vue'
import { buscarProductos, exportarKardexCsv, kardex, listar, type FiltroKardex } from '@/api/inventario'
import { mensajeError } from '@/api/http'
import { fechaHora, fechaISO, numero } from '@/utils/formato'
import type { Almacen, KardexFila, KardexResumen, Producto } from '@/types/inventario'

const toast = useToast()

const almacenes = ref<Almacen[]>([])
const almacenId = ref<number | null>(null)
const producto = ref<Producto | string | null>(null)
const sugerencias = ref<Producto[]>([])
const rango = ref<(Date | null)[] | null>(null)

const filas = ref<KardexFila[]>([])
const resumen = ref<KardexResumen | null>(null)
const total = ref(0)
const primero = ref(0)
const porPagina = ref(20)
const cargando = ref(false)
const consultado = ref(false)

const productoSeleccionado = computed(() => (typeof producto.value === 'object' ? producto.value : null))
const puedeConsultar = computed(() => !!almacenId.value && !!productoSeleccionado.value)

onMounted(async () => {
  almacenes.value = (await listar<Almacen>('almacenes', { estado: true, page_size: 200 })).results
  if (almacenes.value.length === 1) almacenId.value = almacenes.value[0]!.id
})

async function sugerir(e: AutoCompleteCompleteEvent) {
  sugerencias.value = (await buscarProductos(e.query)).results
}

function filtro(): FiltroKardex {
  const [desde, hasta] = rango.value ?? []
  return {
    producto: productoSeleccionado.value!.id,
    almacen: almacenId.value!,
    desde: desde ? fechaISO(desde) : undefined,
    hasta: hasta ? fechaISO(hasta) : undefined,
  }
}

async function cargar() {
  if (!puedeConsultar.value) return
  cargando.value = true
  try {
    const r = await kardex(filtro(), primero.value / porPagina.value + 1, porPagina.value)
    filas.value = r.results
    total.value = r.count
    resumen.value = r.resumen
    consultado.value = true
  } catch (e) {
    toast.add({ severity: 'error', summary: 'No se pudo cargar el Kardex', detail: mensajeError(e), life: 5000 })
  } finally {
    cargando.value = false
  }
}

function consultar() {
  primero.value = 0
  cargar()
}

function alCambiarPagina(e: DataTablePageEvent) {
  primero.value = e.first
  porPagina.value = e.rows
  cargar()
}

function limpiarFechas() {
  rango.value = null
  if (consultado.value) consultar()
}

async function exportar() {
  try {
    await exportarKardexCsv(filtro())
  } catch (e) {
    toast.add({ severity: 'error', summary: 'No se pudo exportar', detail: mensajeError(e), life: 5000 })
  }
}

const esEntrada = (f: KardexFila) => Number(f.entrada_cantidad) > 0
</script>

<template>
  <div class="space-y-4">
    <!-- Filtros -->
    <section class="panel">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div>
          <label class="etiqueta">Almacén</label>
          <Select v-model="almacenId" :options="almacenes" option-label="nombre" option-value="id" placeholder="Seleccione" fluid />
        </div>
        <div>
          <label class="etiqueta">Producto</label>
          <AutoComplete
            v-model="producto" :suggestions="sugerencias" option-label="nombre" placeholder="Buscar por SKU o nombre" fluid
            :delay="300" force-selection @complete="sugerir"
          >
            <template #option="{ option }">
              <span class="font-mono text-xs text-slate-500">{{ option.sku }}</span>
              <span class="ml-2">{{ option.nombre }}</span>
            </template>
          </AutoComplete>
        </div>
        <div>
          <label class="etiqueta">Rango de fechas</label>
          <DatePicker v-model="rango" selection-mode="range" date-format="dd/mm/yy" show-icon show-button-bar :manual-input="false" placeholder="Todo el historial" fluid @clear-click="limpiarFechas" />
        </div>
        <div class="flex items-end gap-2">
          <Button label="Consultar" icon="pi pi-search" :disabled="!puedeConsultar" :loading="cargando" @click="consultar" />
          <Button label="Exportar CSV" icon="pi pi-download" severity="secondary" outlined :disabled="!consultado" @click="exportar" />
        </div>
      </div>
    </section>

    <!-- Resumen valorado -->
    <section v-if="resumen" class="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <div class="panel">
        <p class="etiqueta">Saldo inicial</p>
        <p class="text-xl font-semibold">{{ numero(resumen.saldo_inicial.cantidad) }}</p>
        <p class="text-sm text-slate-500">Bs {{ numero(resumen.saldo_inicial.valor) }}</p>
      </div>
      <div class="panel">
        <p class="etiqueta">Entradas</p>
        <p class="text-xl font-semibold text-emerald-500">+{{ numero(resumen.entradas.cantidad) }}</p>
        <p class="text-sm text-slate-500">Bs {{ numero(resumen.entradas.valor) }}</p>
      </div>
      <div class="panel">
        <p class="etiqueta">Salidas</p>
        <p class="text-xl font-semibold text-rose-500">−{{ numero(resumen.salidas.cantidad) }}</p>
        <p class="text-sm text-slate-500">Bs {{ numero(resumen.salidas.valor) }}</p>
      </div>
      <div class="panel">
        <p class="etiqueta">Saldo final · PPP {{ numero(resumen.saldo_final.costo) }}</p>
        <p class="text-xl font-semibold">{{ numero(resumen.saldo_final.cantidad) }}</p>
        <p class="text-sm text-slate-500">Bs {{ numero(resumen.saldo_final.valor) }}</p>
      </div>
    </section>

    <!-- Tabla -->
    <section class="panel !p-0 overflow-hidden">
      <DataTable
        :value="filas" data-key="id" lazy paginator :rows="porPagina" :first="primero" :total-records="total"
        :rows-per-page-options="[10, 20, 50, 100]" :loading="cargando" size="small" striped-rows scrollable
        @page="alCambiarPagina"
      >
        <template #empty>
          <p class="p-6 text-center text-slate-500">
            {{ consultado ? 'No hay movimientos en el periodo seleccionado.' : 'Seleccione almacén y producto, y pulse «Consultar».' }}
          </p>
        </template>

        <ColumnGroup type="header">
          <Row>
            <Column header="Fecha" :rowspan="2" />
            <Column header="Comprobante" :rowspan="2" />
            <Column header="Detalle" :rowspan="2" />
            <Column header="Estado" :rowspan="2" />
            <Column header="Entradas" :colspan="3" class="!text-center" />
            <Column header="Salidas" :colspan="3" class="!text-center" />
            <Column header="Saldo" :colspan="3" class="!text-center" />
          </Row>
          <Row>
            <Column header="Cant." /><Column header="Costo" /><Column header="Total" />
            <Column header="Cant." /><Column header="Costo" /><Column header="Total" />
            <Column header="Cant." /><Column header="PPP" /><Column header="Valor" />
          </Row>
        </ColumnGroup>

        <Column field="fecha" style="min-width: 9rem">
          <template #body="{ data }">{{ fechaHora(data.fecha) }}</template>
        </Column>
        <Column field="comprobante" style="min-width: 9rem">
          <template #body="{ data }"><span class="font-mono text-xs">{{ data.comprobante }}</span></template>
        </Column>
        <Column style="min-width: 12rem">
          <template #body="{ data }">
            <div class="flex flex-wrap items-center gap-1">
              <Tag :value="data.tipo" :severity="esEntrada(data) ? 'success' : 'danger'" />
              <Tag v-if="data.es_anulacion" value="Anulación" severity="warn" />
            </div>
            <p v-if="data.tercero" class="mt-1 text-xs text-slate-500">{{ data.tercero }}</p>
            <p v-if="data.lote" class="text-xs text-slate-500">Lote {{ data.lote }}</p>
          </template>
        </Column>
        <Column field="estado">
          <template #body="{ data }"><EstadoTag :estado="data.estado" /></template>
        </Column>

        <Column field="entrada_cantidad" body-class="text-right"><template #body="{ data }">{{ esEntrada(data) ? numero(data.entrada_cantidad) : '' }}</template></Column>
        <Column field="entrada_costo" body-class="text-right"><template #body="{ data }">{{ esEntrada(data) ? numero(data.entrada_costo) : '' }}</template></Column>
        <Column field="entrada_total" body-class="text-right"><template #body="{ data }">{{ esEntrada(data) ? numero(data.entrada_total) : '' }}</template></Column>

        <Column field="salida_cantidad" body-class="text-right"><template #body="{ data }">{{ !esEntrada(data) ? numero(data.salida_cantidad) : '' }}</template></Column>
        <Column field="salida_costo" body-class="text-right"><template #body="{ data }">{{ !esEntrada(data) ? numero(data.salida_costo) : '' }}</template></Column>
        <Column field="salida_total" body-class="text-right"><template #body="{ data }">{{ !esEntrada(data) ? numero(data.salida_total) : '' }}</template></Column>

        <Column field="saldo_cantidad" body-class="text-right font-semibold"><template #body="{ data }">{{ numero(data.saldo_cantidad) }}</template></Column>
        <Column field="saldo_costo" body-class="text-right"><template #body="{ data }">{{ numero(data.saldo_costo) }}</template></Column>
        <Column field="saldo_valor" body-class="text-right font-semibold"><template #body="{ data }">{{ numero(data.saldo_valor) }}</template></Column>
      </DataTable>
    </section>
  </div>
</template>
