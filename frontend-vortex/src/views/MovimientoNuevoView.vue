<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import AutoComplete, { type AutoCompleteCompleteEvent, type AutoCompleteOptionSelectEvent } from 'primevue/autocomplete'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import DatePicker from 'primevue/datepicker'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import {
  buscarProductos, listar, registrarMovimiento, registrarTraspaso, stockDisponible,
  type ComprobantePayload,
} from '@/api/inventario'
import { mensajeError } from '@/api/http'
import { validarSalida } from '@/utils/stock'
import { decimal4, fechaISO, numero } from '@/utils/formato'
import type { Almacen, Producto, Tercero, TipoMovimiento } from '@/types/inventario'

type Modo = 'ENTRADA' | 'SALIDA' | 'TRASPASO'
interface LineaForm {
  clave: number
  producto: Producto | string | null
  cantidad: number | null
  precio: number | null
  lote: string
  vencimiento: Date | null
}

const toast = useToast()
const modos = [
  { label: 'Entrada', value: 'ENTRADA' },
  { label: 'Salida', value: 'SALIDA' },
  { label: 'Traspaso', value: 'TRASPASO' },
]

const modo = ref<Modo>('ENTRADA')
const almacenes = ref<Almacen[]>([])
const tipos = ref<TipoMovimiento[]>([])
const terceros = ref<Tercero[]>([])

const almacenId = ref<number | null>(null)
const destinoId = ref<number | null>(null)
const tipoId = ref<number | null>(null)
const terceroId = ref<number | null>(null)
const documento = ref('')
const observacion = ref('')
const enviando = ref(false)
const sugerencias = ref<Producto[]>([])
const disponibles = ref<Record<number, number>>({})

let contador = 0
const nuevaLinea = (): LineaForm => ({ clave: ++contador, producto: null, cantidad: null, precio: null, lote: '', vencimiento: null })
const lineas = reactive<LineaForm[]>([nuevaLinea()])

const esEntrada = computed(() => modo.value === 'ENTRADA')
const esTraspaso = computed(() => modo.value === 'TRASPASO')
const tiposDisponibles = computed(() =>
  tipos.value.filter((t) => !t.es_traspaso && t.signo === (esEntrada.value ? 1 : -1)),
)
const tipo = computed(() => tipos.value.find((t) => t.id === tipoId.value) ?? null)
const tercerosFiltrados = computed(() => {
  const requerido = tipo.value?.tipo_tercero
  return requerido ? terceros.value.filter((t) => t.tipo === requerido || t.tipo === 'AMBOS') : terceros.value
})
const productoDe = (l: LineaForm): Producto | null => (typeof l.producto === 'object' ? l.producto : null)
const decimalesDe = (l: LineaForm) => (productoDe(l)?.unidad_permite_decimales ? 4 : 0)

// Validación de stock disponible (salidas y traspasos) antes de llamar a la API
const erroresStock = computed(() => {
  if (esEntrada.value || !almacenId.value) return {}
  return validarSalida(
    lineas.map((l) => ({ productoId: productoDe(l)?.id ?? null, cantidad: l.cantidad })),
    disponibles.value,
  )
})

const problemas = computed(() => {
  const p: string[] = []
  if (!almacenId.value) p.push('Seleccione el almacén.')
  if (esTraspaso.value) {
    if (!destinoId.value) p.push('Seleccione el almacén de destino.')
    else if (destinoId.value === almacenId.value) p.push('El destino debe ser distinto al origen.')
  } else {
    if (!tipoId.value) p.push('Seleccione el tipo de movimiento.')
    if (tipo.value?.requiere_tercero && !terceroId.value) p.push('Este tipo requiere indicar el tercero.')
  }
  lineas.forEach((l, i) => {
    const prod = productoDe(l)
    const n = i + 1
    if (!prod) p.push(`Línea ${n}: seleccione un producto.`)
    else {
      if (!l.cantidad || l.cantidad <= 0) p.push(`Línea ${n}: indique una cantidad mayor que cero.`)
      if (prod.maneja_lotes && !l.lote.trim()) p.push(`Línea ${n}: el producto maneja lotes.`)
      if (esEntrada.value && prod.maneja_vencimiento && !l.vencimiento) p.push(`Línea ${n}: indique el vencimiento.`)
      if (esEntrada.value && l.precio === null) p.push(`Línea ${n}: indique el costo unitario.`)
    }
    if (erroresStock.value[i]) p.push(`Línea ${n}: ${erroresStock.value[i]}`)
  })
  return p
})
const puedeEnviar = computed(() => problemas.value.length === 0 && !enviando.value)
const totalEstimado = computed(() =>
  lineas.reduce((s, l) => s + (l.cantidad ?? 0) * (l.precio ?? 0), 0),
)

onMounted(async () => {
  const [a, t, c] = await Promise.all([
    listar<Almacen>('almacenes', { estado: true, page_size: 500 }),
    listar<TipoMovimiento>('tipos-movimiento', { estado: true, page_size: 500 }),
    listar<Tercero>('terceros', { estado: true, page_size: 500 }),
  ])
  almacenes.value = a.results
  tipos.value = t.results
  terceros.value = c.results
  if (almacenes.value.length === 1) almacenId.value = almacenes.value[0]!.id
})

watch(modo, () => {
  tipoId.value = null
  terceroId.value = null
  destinoId.value = null
})
watch(tipoId, () => { terceroId.value = null })
watch(almacenId, () => { void refrescarDisponibles() })

async function refrescarDisponibles() {
  disponibles.value = {}
  if (!almacenId.value) return
  const ids = new Set(lineas.map((l) => productoDe(l)?.id).filter((x): x is number => !!x))
  await Promise.all([...ids].map(async (id) => {
    disponibles.value = { ...disponibles.value, [id]: await stockDisponible(almacenId.value!, id) }
  }))
}

async function sugerir(e: AutoCompleteCompleteEvent) {
  sugerencias.value = (await buscarProductos(e.query)).results
}

async function alElegirProducto(l: LineaForm, e: AutoCompleteOptionSelectEvent) {
  const p = e.value as Producto
  if (modo.value === 'SALIDA' && l.precio === null) l.precio = Number(p.precio_venta)
  if (almacenId.value) {
    disponibles.value = { ...disponibles.value, [p.id]: await stockDisponible(almacenId.value, p.id) }
  }
}

const agregarLinea = () => lineas.push(nuevaLinea())
const quitarLinea = (i: number) => { if (lineas.length > 1) lineas.splice(i, 1) }

function reiniciar() {
  lineas.splice(0, lineas.length, nuevaLinea())
  documento.value = ''
  observacion.value = ''
}

async function enviar() {
  if (!puedeEnviar.value) return
  enviando.value = true
  const comun: ComprobantePayload = {
    numero_documento: documento.value.trim(),
    observacion: observacion.value.trim(),
    lineas: lineas.map((l) => ({
      producto: productoDe(l)!.id,
      cantidad: decimal4(l.cantidad),
      precio_unitario: decimal4(esTraspaso.value ? 0 : l.precio),
      lote: l.lote.trim(),
      fecha_vencimiento: l.vencimiento ? fechaISO(l.vencimiento) : null,
    })),
  }
  try {
    if (esTraspaso.value) {
      const r = await registrarTraspaso({ ...comun, almacen_origen: almacenId.value!, almacen_destino: destinoId.value! })
      toast.add({ severity: 'success', summary: 'Traspaso registrado', detail: `${r.salida.numero_comprobante} → ${r.entrada.numero_comprobante}`, life: 5000 })
    } else {
      const r = await registrarMovimiento({ ...comun, almacen: almacenId.value!, tipo_movimiento: tipoId.value!, tercero: terceroId.value })
      toast.add({ severity: 'success', summary: 'Movimiento registrado', detail: `Comprobante ${r.numero_comprobante}`, life: 5000 })
    }
    reiniciar()
    await refrescarDisponibles()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'No se pudo registrar', detail: mensajeError(e), life: 7000 })
    await refrescarDisponibles()
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-4">
    <section class="panel space-y-4">
      <SelectButton v-model="modo" :options="modos" option-label="label" option-value="value" :allow-empty="false" />

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div>
          <label class="etiqueta">{{ esTraspaso ? 'Almacén de origen' : 'Almacén' }}</label>
          <Select v-model="almacenId" :options="almacenes" option-label="nombre" option-value="id" placeholder="Seleccione" fluid />
        </div>

        <div v-if="esTraspaso">
          <label class="etiqueta">Almacén de destino</label>
          <Select v-model="destinoId" :options="almacenes.filter((a) => a.id !== almacenId)" option-label="nombre" option-value="id" placeholder="Seleccione" fluid />
        </div>
        <template v-else>
          <div>
            <label class="etiqueta">Tipo de movimiento</label>
            <Select v-model="tipoId" :options="tiposDisponibles" option-label="nombre" option-value="id" placeholder="Seleccione" fluid />
          </div>
          <div v-if="tipo?.requiere_tercero">
            <label class="etiqueta">{{ tipo.tipo_tercero === 'CLIENTE' ? 'Cliente' : tipo.tipo_tercero === 'PROVEEDOR' ? 'Proveedor' : 'Tercero' }}</label>
            <Select
              v-model="terceroId" :options="tercerosFiltrados" option-value="id" filter placeholder="Seleccione" fluid
              :option-label="'nombre_razon_social'"
            />
          </div>
        </template>

        <div>
          <label class="etiqueta">Nº documento de respaldo</label>
          <InputText v-model="documento" maxlength="50" placeholder="Factura, nota de entrega…" fluid />
        </div>
      </div>
    </section>

    <section class="panel space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold">Productos</h2>
        <Button label="Agregar línea" icon="pi pi-plus" size="small" severity="secondary" outlined @click="agregarLinea" />
      </div>

      <div v-for="(l, i) in lineas" :key="l.clave" class="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
        <div class="grid grid-cols-1 items-start gap-3 md:grid-cols-12">
          <div class="md:col-span-5">
            <label class="etiqueta">Producto</label>
            <AutoComplete
              v-model="l.producto" :suggestions="sugerencias" option-label="nombre" placeholder="SKU o nombre" fluid
              :delay="300" force-selection @complete="sugerir" @option-select="alElegirProducto(l, $event)"
            >
              <template #option="{ option }">
                <span class="font-mono text-xs text-slate-500">{{ option.sku }}</span>
                <span class="ml-2">{{ option.nombre }}</span>
              </template>
            </AutoComplete>
            <p v-if="!esEntrada && productoDe(l) && almacenId" class="mt-1 text-xs text-slate-500">
              Disponible: <strong>{{ numero(disponibles[productoDe(l)!.id] ?? 0) }}</strong> {{ productoDe(l)!.unidad_codigo }}
            </p>
          </div>

          <div class="md:col-span-2">
            <label class="etiqueta">Cantidad{{ productoDe(l) ? ` (${productoDe(l)!.unidad_codigo})` : '' }}</label>
            <InputNumber
              v-model="l.cantidad" :min="0" :min-fraction-digits="0" :max-fraction-digits="decimalesDe(l)"
              :invalid="!!erroresStock[i]" fluid
            />
          </div>

          <div v-if="!esTraspaso" class="md:col-span-2">
            <label class="etiqueta">{{ esEntrada ? 'Costo unitario' : 'Precio de venta' }}</label>
            <InputNumber v-model="l.precio" :min="0" :min-fraction-digits="2" :max-fraction-digits="4" fluid />
          </div>

          <div v-if="productoDe(l)?.maneja_lotes" class="md:col-span-2">
            <label class="etiqueta">Lote</label>
            <InputText v-model="l.lote" maxlength="50" fluid />
          </div>
          <div v-if="esEntrada && productoDe(l)?.maneja_vencimiento" class="md:col-span-2">
            <label class="etiqueta">Vencimiento</label>
            <DatePicker v-model="l.vencimiento" date-format="dd/mm/yy" show-icon fluid />
          </div>

          <div class="flex justify-end md:col-span-1 md:pt-5">
            <Button icon="pi pi-trash" severity="danger" text rounded :disabled="lineas.length === 1" aria-label="Quitar línea" @click="quitarLinea(i)" />
          </div>
        </div>
        <Message v-if="erroresStock[i]" severity="error" size="small" variant="simple" class="mt-2">{{ erroresStock[i] }}</Message>
      </div>

      <p v-if="!esTraspaso" class="text-right text-sm text-slate-500">
        Total estimado: <strong class="text-slate-800 dark:text-slate-100">Bs {{ numero(totalEstimado) }}</strong>
      </p>
    </section>

    <section class="panel space-y-4">
      <div>
        <label class="etiqueta">Observación</label>
        <Textarea v-model="observacion" rows="2" auto-resize fluid />
      </div>

      <Message v-if="problemas.length && lineas.some((l) => productoDe(l))" severity="warn" :closable="false">
        <ul class="list-inside list-disc text-sm">
          <li v-for="p in problemas" :key="p">{{ p }}</li>
        </ul>
      </Message>

      <div class="flex justify-end">
        <Button label="Registrar" icon="pi pi-check" :disabled="!puedeEnviar" :loading="enviando" @click="enviar" />
      </div>
    </section>
  </div>
</template>
