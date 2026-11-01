<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import DataTable, { type DataTablePageEvent } from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import EstadoTag from '@/components/EstadoTag.vue'
import { CATALOGOS, type Fila, type Opcion } from '@/config/catalogos'
import { actualizar, crear, darDeBaja, listar } from '@/api/inventario'
import { mensajeError } from '@/api/http'
import { decimal4, numero } from '@/utils/formato'

const route = useRoute()
const toast = useToast()
const confirmar = useConfirm()

const config = computed(() => CATALOGOS[String(route.params.clave)])

const filas = ref<Fila[]>([])
const total = ref(0)
const primero = ref(0)
const porPagina = ref(20)
const cargando = ref(false)
const busqueda = ref('')
const verInactivos = ref(false)
const opciones = ref<Record<string, Opcion[]>>({})
let temporizador: ReturnType<typeof setTimeout> | undefined

const dialogo = ref(false)
const editandoId = ref<number | null>(null)
const guardando = ref(false)
const form = reactive<Fila>({})

async function cargar() {
  const cfg = config.value
  if (!cfg) return
  cargando.value = true
  try {
    const r = await listar<Fila>(cfg.recurso, {
      page: primero.value / porPagina.value + 1,
      page_size: porPagina.value,
      search: busqueda.value,
      estado: verInactivos.value ? undefined : true,
    })
    filas.value = r.results
    total.value = r.count
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error al cargar', detail: mensajeError(e), life: 5000 })
  } finally {
    cargando.value = false
  }
}

async function cargarOpciones() {
  opciones.value = {}
  for (const campo of config.value?.campos ?? []) {
    if (campo.opciones) opciones.value[campo.key] = campo.opciones
    else if (campo.fuente) {
      const { recurso, etiqueta } = campo.fuente
      const r = await listar<Fila>(recurso, { estado: true, page_size: 500 })
      opciones.value[campo.key] = r.results.map((x) => ({ label: etiqueta(x), value: x.id }))
    }
  }
}

watch(
  () => route.params.clave,
  () => {
    primero.value = 0
    busqueda.value = ''
    verInactivos.value = false
    if (config.value) {
      void cargar()
      void cargarOpciones()
    }
  },
  { immediate: true },
)

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

function valorInicial(tipo: string) {
  if (tipo === 'booleano') return false
  if (tipo === 'numero') return 0
  if (tipo === 'select') return null
  return ''
}

function nuevo() {
  editandoId.value = null
  for (const k of Object.keys(form)) delete form[k]
  for (const c of config.value!.campos) form[c.key] = valorInicial(c.tipo)
  dialogo.value = true
}

function editar(fila: Fila) {
  editandoId.value = fila.id
  for (const k of Object.keys(form)) delete form[k]
  for (const c of config.value!.campos) {
    form[c.key] = c.tipo === 'numero' ? Number(fila[c.key] ?? 0) : (fila[c.key] ?? valorInicial(c.tipo))
  }
  dialogo.value = true
}

const formValido = computed(() =>
  (config.value?.campos ?? []).every((c) => !c.requerido || (form[c.key] !== null && form[c.key] !== '' && form[c.key] !== undefined)),
)

async function guardar() {
  const cfg = config.value!
  const datos: Fila = {}
  for (const c of cfg.campos) {
    datos[c.key] = c.tipo === 'numero' && c.key !== 'signo' ? decimal4(form[c.key]) : form[c.key]
  }
  guardando.value = true
  try {
    if (editandoId.value) await actualizar(cfg.recurso, editandoId.value, datos)
    else await crear(cfg.recurso, datos)
    toast.add({ severity: 'success', summary: 'Guardado', detail: `El ${cfg.singular} se guardó correctamente.`, life: 3000 })
    dialogo.value = false
    await cargar()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'No se pudo guardar', detail: mensajeError(e), life: 7000 })
  } finally {
    guardando.value = false
  }
}

function darBaja(fila: Fila) {
  confirmar.require({
    header: 'Dar de baja',
    message: 'El registro quedará inactivo (no se elimina) y dejará de aparecer en los formularios.',
    icon: 'pi pi-exclamation-triangle',
    acceptLabel: 'Dar de baja',
    rejectLabel: 'Cancelar',
    acceptProps: { severity: 'danger' },
    rejectProps: { severity: 'secondary', text: true },
    accept: async () => {
      try {
        await darDeBaja(config.value!.recurso, fila.id)
        await cargar()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'No se pudo dar de baja', detail: mensajeError(e), life: 5000 })
      }
    },
  })
}

async function reactivar(fila: Fila) {
  try {
    await actualizar(config.value!.recurso, fila.id, { estado: true })
    await cargar()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'No se pudo reactivar', detail: mensajeError(e), life: 5000 })
  }
}

const decimalesCampo = (clave: string) => (clave === 'signo' ? 0 : 4)
</script>

<template>
  <div v-if="config" class="space-y-4">
    <section class="panel">
      <div class="flex flex-wrap items-end gap-4">
        <div class="min-w-64 flex-1">
          <label class="etiqueta">Buscar</label>
          <InputText v-model="busqueda" placeholder="Escriba para buscar…" fluid @input="buscarConRetardo" />
        </div>
        <div class="flex items-center gap-2 pb-2">
          <ToggleSwitch v-model="verInactivos" input-id="inactivos" @change="refiltrar" />
          <label for="inactivos" class="text-sm">Ver inactivos</label>
        </div>
        <Button :label="`Nuevo ${config.singular}`" icon="pi pi-plus" @click="nuevo" />
      </div>
    </section>

    <section class="panel !p-0 overflow-hidden">
      <DataTable
        :value="filas" data-key="id" lazy paginator :rows="porPagina" :first="primero" :total-records="total"
        :rows-per-page-options="[10, 20, 50, 100]" :loading="cargando" size="small" striped-rows scrollable @page="alPaginar"
      >
        <template #empty><p class="p-6 text-center text-slate-500">Sin registros.</p></template>
        <Column v-for="c in config.columnas" :key="c.key" :header="c.label" :body-class="c.tipo === 'numero' ? 'text-right' : ''">
          <template #body="{ data }">
            <i v-if="c.tipo === 'bool'" class="pi" :class="data[c.key] ? 'pi-check text-emerald-500' : 'pi-minus text-slate-400'" />
            <template v-else-if="c.tipo === 'numero'">{{ numero(data[c.key]) }}</template>
            <template v-else>{{ data[c.key] ?? '—' }}</template>
          </template>
        </Column>
        <Column header="Estado"><template #body="{ data }"><EstadoTag :estado="data.estado" /></template></Column>
        <Column header="" style="width: 7rem">
          <template #body="{ data }">
            <div class="flex justify-end gap-1">
              <Button icon="pi pi-pencil" text rounded size="small" aria-label="Editar" @click="editar(data)" />
              <Button v-if="data.estado" icon="pi pi-trash" text rounded size="small" severity="danger" aria-label="Dar de baja" @click="darBaja(data)" />
              <Button v-else icon="pi pi-replay" text rounded size="small" severity="success" aria-label="Reactivar" @click="reactivar(data)" />
            </div>
          </template>
        </Column>
      </DataTable>
    </section>

    <Dialog v-model:visible="dialogo" modal :header="`${editandoId ? 'Editar' : 'Nuevo'} ${config.singular}`" :style="{ width: '34rem', maxWidth: '95vw' }">
      <form class="space-y-4" @submit.prevent="guardar">
        <div v-for="c in config.campos" :key="c.key">
          <label v-if="c.tipo !== 'booleano'" class="etiqueta">{{ c.label }}<span v-if="c.requerido"> *</span></label>

          <InputText v-if="c.tipo === 'texto' || c.tipo === 'email'" v-model="form[c.key]" :type="c.tipo === 'email' ? 'email' : 'text'" fluid />
          <Textarea v-else-if="c.tipo === 'textarea'" v-model="form[c.key]" rows="2" auto-resize fluid />
          <InputNumber v-else-if="c.tipo === 'numero'" v-model="form[c.key]" :min-fraction-digits="0" :max-fraction-digits="decimalesCampo(c.key)" fluid />
          <Select
            v-else-if="c.tipo === 'select'" v-model="form[c.key]" :options="opciones[c.key] ?? []"
            option-label="label" option-value="value" :show-clear="!c.requerido" filter fluid placeholder="Seleccione"
          />
          <div v-else class="flex items-center gap-3">
            <ToggleSwitch v-model="form[c.key]" :input-id="`f-${c.key}`" />
            <label :for="`f-${c.key}`" class="text-sm">{{ c.label }}</label>
          </div>

          <p v-if="c.ayuda" class="mt-1 text-xs text-slate-500">{{ c.ayuda }}</p>
        </div>
      </form>
      <template #footer>
        <Button label="Cancelar" text severity="secondary" @click="dialogo = false" />
        <Button label="Guardar" icon="pi pi-check" :disabled="!formValido" :loading="guardando" @click="guardar" />
      </template>
    </Dialog>
  </div>
  <p v-else class="panel">Catálogo no encontrado.</p>
</template>
