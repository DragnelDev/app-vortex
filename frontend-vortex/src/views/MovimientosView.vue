<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import DataTable, { type DataTablePageEvent } from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import EstadoTag from '@/components/EstadoTag.vue'
import { anularMovimiento, detalleMovimiento, listar } from '@/api/inventario'
import { mensajeError } from '@/api/http'
import { fechaHora, fechaISO, numero } from '@/utils/formato'
import type { Almacen, Movimiento, MovimientoDetalle } from '@/types/inventario'

const toast = useToast()
const router = useRouter()

const filas = ref<Movimiento[]>([])
const total = ref(0)
const primero = ref(0)
const porPagina = ref(20)
const cargando = ref(false)

const busqueda = ref('')
const almacenId = ref<number | null>(null)
const estado = ref<string | null>(null)
const rango = ref<(Date | null)[] | null>(null)
const almacenes = ref<Almacen[]>([])
const estados = [{ label: 'Registrado', value: 'REGISTRADO' }, { label: 'Anulado', value: 'ANULADO' }]
let temporizador: ReturnType<typeof setTimeout> | undefined

const verDetalle = ref<MovimientoDetalle | null>(null)
const dialogoDetalle = ref(false)

const aAnular = ref<Movimiento | null>(null)
const motivo = ref('')
const anulando = ref(false)

async function cargar() {
  cargando.value = true
  const [desde, hasta] = rango.value ?? []
  try {
    const r = await listar<Movimiento>('movimientos', {
      page: primero.value / porPagina.value + 1,
      page_size: porPagina.value,
      search: busqueda.value,
      almacen: almacenId.value,
      estado: estado.value,
      desde: desde ? fechaISO(desde) : undefined,
      hasta: hasta ? fechaISO(hasta) : undefined,
    })
    filas.value = r.results
    total.value = r.count
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error al cargar comprobantes', detail: mensajeError(e), life: 5000 })
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

async function abrirDetalle(m: Movimiento) {
  try {
    verDetalle.value = await detalleMovimiento(m.id)
    dialogoDetalle.value = true
  } catch (e) {
    toast.add({ severity: 'error', summary: 'No se pudo abrir', detail: mensajeError(e), life: 5000 })
  }
}

function pedirAnulacion(m: Movimiento) {
  aAnular.value = m
  motivo.value = ''
}

async function confirmarAnulacion() {
  if (!aAnular.value || !motivo.value.trim()) return
  anulando.value = true
  try {
    const r = await anularMovimiento(aAnular.value.id, motivo.value.trim())
    toast.add({ severity: 'success', summary: 'Comprobante anulado', detail: `Contra-movimiento ${r.numero_comprobante}`, life: 5000 })
    aAnular.value = null
    await cargar()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'No se pudo anular', detail: mensajeError(e), life: 7000 })
  } finally {
    anulando.value = false
  }
}

onMounted(async () => {
  almacenes.value = (await listar<Almacen>('almacenes', { estado: true, page_size: 200 })).results
  cargar()
})
</script>

<template>
  <div class="space-y-4">
    <section class="panel">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <div>
          <label class="etiqueta">Buscar</label>
          <InputText v-model="busqueda" placeholder="Comprobante, documento o tercero" fluid @input="buscarConRetardo" />
        </div>
        <div>
          <label class="etiqueta">Almacén</label>
          <Select v-model="almacenId" :options="almacenes" option-label="nombre" option-value="id" placeholder="Todos" show-clear fluid @change="refiltrar" />
        </div>
        <div>
          <label class="etiqueta">Estado</label>
          <Select v-model="estado" :options="estados" option-label="label" option-value="value" placeholder="Todos" show-clear fluid @change="refiltrar" />
        </div>
        <div>
          <label class="etiqueta">Fechas</label>
          <DatePicker v-model="rango" selection-mode="range" date-format="dd/mm/yy" show-icon show-button-bar :manual-input="false" fluid @update:model-value="refiltrar" @clear-click="refiltrar" />
        </div>
        <div class="flex items-end">
          <Button label="Nuevo movimiento" icon="pi pi-plus" fluid @click="router.push({ name: 'movimiento-nuevo' })" />
        </div>
      </div>
    </section>

    <section class="panel !p-0 overflow-hidden">
      <DataTable
        :value="filas" data-key="id" lazy paginator :rows="porPagina" :first="primero" :total-records="total"
        :rows-per-page-options="[10, 20, 50, 100]" :loading="cargando" size="small" striped-rows scrollable @page="alPaginar"
      >
        <template #empty><p class="p-6 text-center text-slate-500">No hay comprobantes.</p></template>
        <Column field="numero_comprobante" header="Comprobante" style="min-width: 9rem">
          <template #body="{ data }"><span class="font-mono text-xs">{{ data.numero_comprobante }}</span></template>
        </Column>
        <Column header="Fecha" style="min-width: 9rem"><template #body="{ data }">{{ fechaHora(data.fecha_movimiento) }}</template></Column>
        <Column header="Tipo" style="min-width: 10rem">
          <template #body="{ data }">
            <Tag :value="data.tipo_nombre" :severity="data.signo_efectivo > 0 ? 'success' : 'danger'" />
            <Tag v-if="data.es_anulacion" value="Anulación" severity="warn" class="ml-1" />
          </template>
        </Column>
        <Column field="almacen_nombre" header="Almacén" />
        <Column header="Tercero"><template #body="{ data }">{{ data.tercero_nombre ?? '—' }}</template></Column>
        <Column field="numero_documento" header="Documento" />
        <Column header="Total" body-class="text-right"><template #body="{ data }">{{ numero(data.total) }}</template></Column>
        <Column header="Estado">
          <template #body="{ data }">
            <EstadoTag :estado="data.estado" />
            <p v-if="data.anulado_por" class="mt-1 text-xs text-slate-500">por {{ data.anulado_por }}</p>
          </template>
        </Column>
        <Column header="" style="width: 7rem">
          <template #body="{ data }">
            <div class="flex justify-end gap-1">
              <Button icon="pi pi-eye" text rounded size="small" aria-label="Ver detalle" @click="abrirDetalle(data)" />
              <Button
                icon="pi pi-ban" text rounded size="small" severity="danger" aria-label="Anular"
                :disabled="data.estado === 'ANULADO' || data.es_anulacion" @click="pedirAnulacion(data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </section>

    <Dialog v-model:visible="dialogoDetalle" modal :header="verDetalle?.numero_comprobante" :style="{ width: '56rem', maxWidth: '95vw' }">
      <div v-if="verDetalle" class="space-y-4">
        <div class="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <div><p class="etiqueta">Fecha</p>{{ fechaHora(verDetalle.fecha_movimiento) }}</div>
          <div><p class="etiqueta">Almacén</p>{{ verDetalle.almacen_nombre }}</div>
          <div><p class="etiqueta">Tercero</p>{{ verDetalle.tercero_nombre ?? '—' }}</div>
          <div><p class="etiqueta">Estado</p><EstadoTag :estado="verDetalle.estado" /></div>
        </div>
        <p v-if="verDetalle.motivo_anulacion" class="text-sm"><span class="etiqueta">Motivo de anulación</span>{{ verDetalle.motivo_anulacion }}</p>
        <p v-if="verDetalle.observacion" class="text-sm"><span class="etiqueta">Observación</span>{{ verDetalle.observacion }}</p>
        <DataTable :value="verDetalle.detalles" size="small" scrollable>
          <Column field="producto_sku" header="SKU" />
          <Column field="producto_nombre" header="Producto" />
          <Column field="lote" header="Lote" />
          <Column header="Cantidad" body-class="text-right"><template #body="{ data }">{{ numero(data.cantidad) }} {{ data.unidad_codigo }}</template></Column>
          <Column header="Precio" body-class="text-right"><template #body="{ data }">{{ numero(data.precio_unitario) }}</template></Column>
          <Column header="Costo (PPP)" body-class="text-right"><template #body="{ data }">{{ numero(data.costo_promedio_historico) }}</template></Column>
          <Column header="Subtotal" body-class="text-right"><template #body="{ data }">{{ numero(data.subtotal) }}</template></Column>
        </DataTable>
        <p class="text-right font-semibold">Total: Bs {{ numero(verDetalle.total) }}</p>
      </div>
    </Dialog>

    <Dialog :visible="!!aAnular" modal header="Anular comprobante" :style="{ width: '30rem', maxWidth: '95vw' }" @update:visible="(v: boolean) => { if (!v) aAnular = null }">
      <div class="space-y-3">
        <p class="text-sm">
          Se registrará un contra-movimiento que revierte <strong>{{ aAnular?.numero_comprobante }}</strong>.
          Si es parte de un traspaso se anulan ambos comprobantes.
        </p>
        <div>
          <label class="etiqueta">Motivo (obligatorio)</label>
          <Textarea v-model="motivo" rows="3" auto-resize fluid />
        </div>
      </div>
      <template #footer>
        <Button label="Cancelar" text severity="secondary" @click="aAnular = null" />
        <Button label="Anular" icon="pi pi-ban" severity="danger" :disabled="!motivo.trim()" :loading="anulando" @click="confirmarAnulacion" />
      </template>
    </Dialog>
  </div>
</template>
