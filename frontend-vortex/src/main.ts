import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import Aura from '@primeuix/themes/aura'
import { definePreset } from '@primeuix/themes'

import App from './App.vue'
import router from './router'
import { iniciarTema } from './composables/useTema'

// Paleta primaria: índigo (Aura por defecto usa verde esmeralda)
const VortexPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '{indigo.50}',
      100: '{indigo.100}',
      200: '{indigo.200}',
      300: '{indigo.300}',
      400: '{indigo.400}',
      500: '{indigo.500}',
      600: '{indigo.600}',
      700: '{indigo.700}',
      800: '{indigo.800}',
      900: '{indigo.900}',
      950: '{indigo.950}',
    },
  },
})

iniciarTema()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  locale: {
    firstDayOfWeek: 1,
    dayNames: ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'],
    dayNamesShort: ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'],
    dayNamesMin: ['D', 'L', 'M', 'X', 'J', 'V', 'S'],
    monthNames: [
      'enero',
      'febrero',
      'marzo',
      'abril',
      'mayo',
      'junio',
      'julio',
      'agosto',
      'septiembre',
      'octubre',
      'noviembre',
      'diciembre',
    ],
    monthNamesShort: [
      'ene',
      'feb',
      'mar',
      'abr',
      'may',
      'jun',
      'jul',
      'ago',
      'sep',
      'oct',
      'nov',
      'dic',
    ],
    today: 'Hoy',
    clear: 'Limpiar',
    apply: 'Aplicar',
    accept: 'Sí',
    reject: 'No',
    dateFormat: 'dd/mm/yy',
    emptyMessage: 'Sin resultados',
    emptyFilterMessage: 'Sin resultados',
  },
  theme: {
    preset: VortexPreset,
    options: {
      darkModeSelector: '.app-dark',
      // Permite que las utilidades de Tailwind sobreescriban los estilos de PrimeVue
      cssLayer: { name: 'primevue', order: 'theme, base, primevue' },
    },
  },
})
app.use(ToastService)
app.use(ConfirmationService)

app.mount('#app')
