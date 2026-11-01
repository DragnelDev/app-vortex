<script setup lang="ts">
import { computed } from 'vue'
import Tag from 'primevue/tag'

/** Badge de estado: comprobante (REGISTRADO/ANULADO) o catálogo (activo/inactivo). */
const props = defineProps<{ estado: string | boolean }>()

const info = computed(() => {
  if (props.estado === true) return { texto: 'Activo', severity: 'success' as const }
  if (props.estado === false) return { texto: 'Inactivo', severity: 'secondary' as const }
  if (props.estado === 'ANULADO') return { texto: 'Anulado', severity: 'danger' as const }
  return { texto: 'Registrado', severity: 'success' as const }
})
</script>

<template>
  <Tag :value="info.texto" :severity="info.severity" />
</template>
