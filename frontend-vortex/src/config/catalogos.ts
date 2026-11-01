/** Definición declarativa de los catálogos: una sola vista genérica los gestiona todos. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Fila = Record<string, any>

export interface Opcion { label: string; value: string | number }

export interface CampoCatalogo {
  key: string
  label: string
  tipo: 'texto' | 'textarea' | 'email' | 'numero' | 'booleano' | 'select'
  requerido?: boolean
  opciones?: Opcion[]
  /** Opciones cargadas desde otro recurso de la API. */
  fuente?: { recurso: string; etiqueta: (r: Fila) => string }
  ayuda?: string
}

export interface ColumnaCatalogo {
  key: string
  label: string
  tipo?: 'bool' | 'numero'
}

export interface ConfigCatalogo {
  titulo: string
  singular: string
  recurso: string
  columnas: ColumnaCatalogo[]
  campos: CampoCatalogo[]
}

export const CATALOGOS: Record<string, ConfigCatalogo> = {
  productos: {
    titulo: 'Productos', singular: 'producto', recurso: 'productos',
    columnas: [
      { key: 'sku', label: 'SKU' }, { key: 'nombre', label: 'Nombre' },
      { key: 'categoria_nombre', label: 'Categoría' }, { key: 'unidad_codigo', label: 'Unidad' },
      { key: 'stock_minimo', label: 'Mínimo', tipo: 'numero' }, { key: 'stock_total', label: 'Stock total', tipo: 'numero' },
      { key: 'maneja_lotes', label: 'Lotes', tipo: 'bool' },
    ],
    campos: [
      { key: 'sku', label: 'SKU', tipo: 'texto', requerido: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'codigo_barras', label: 'Código de barras', tipo: 'texto' },
      { key: 'descripcion', label: 'Descripción', tipo: 'textarea' },
      { key: 'categoria', label: 'Categoría', tipo: 'select', requerido: true, fuente: { recurso: 'categorias', etiqueta: (r) => r.nombre } },
      { key: 'unidad_medida', label: 'Unidad de medida', tipo: 'select', requerido: true, fuente: { recurso: 'unidades', etiqueta: (r) => `${r.nombre} (${r.codigo})` } },
      { key: 'stock_minimo', label: 'Stock mínimo', tipo: 'numero' },
      { key: 'precio_venta', label: 'Precio de venta referencial', tipo: 'numero' },
      { key: 'maneja_lotes', label: 'Maneja lotes', tipo: 'booleano' },
      { key: 'maneja_vencimiento', label: 'Maneja vencimiento', tipo: 'booleano', ayuda: 'Requiere que maneje lotes.' },
    ],
  },
  categorias: {
    titulo: 'Categorías', singular: 'categoría', recurso: 'categorias',
    columnas: [{ key: 'nombre', label: 'Nombre' }, { key: 'descripcion', label: 'Descripción' }],
    campos: [
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'descripcion', label: 'Descripción', tipo: 'texto' },
      { key: 'padre', label: 'Categoría padre', tipo: 'select', fuente: { recurso: 'categorias', etiqueta: (r) => r.nombre } },
    ],
  },
  unidades: {
    titulo: 'Unidades de medida', singular: 'unidad', recurso: 'unidades',
    columnas: [{ key: 'codigo', label: 'Código' }, { key: 'nombre', label: 'Nombre' }, { key: 'permite_decimales', label: 'Decimales', tipo: 'bool' }],
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', requerido: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'permite_decimales', label: 'Permite decimales', tipo: 'booleano', ayuda: 'Marcado para kg, litros, metros; desmarcado para unidades indivisibles.' },
    ],
  },
  terceros: {
    titulo: 'Proveedores y clientes', singular: 'tercero', recurso: 'terceros',
    columnas: [
      { key: 'nombre_razon_social', label: 'Nombre / razón social' }, { key: 'tipo', label: 'Tipo' },
      { key: 'tipo_documento', label: 'Doc.' }, { key: 'numero_documento', label: 'Número' }, { key: 'telefono', label: 'Teléfono' },
    ],
    campos: [
      { key: 'tipo', label: 'Tipo', tipo: 'select', requerido: true, opciones: [{ label: 'Proveedor', value: 'PROVEEDOR' }, { label: 'Cliente', value: 'CLIENTE' }, { label: 'Proveedor y cliente', value: 'AMBOS' }] },
      { key: 'tipo_documento', label: 'Tipo de documento', tipo: 'select', requerido: true, opciones: [{ label: 'NIT', value: 'NIT' }, { label: 'CI', value: 'CI' }, { label: 'Pasaporte', value: 'PASAPORTE' }, { label: 'Otro', value: 'OTRO' }] },
      { key: 'numero_documento', label: 'Número de documento', tipo: 'texto', requerido: true },
      { key: 'nombre_razon_social', label: 'Nombre / razón social', tipo: 'texto', requerido: true },
      { key: 'direccion', label: 'Dirección', tipo: 'texto' },
      { key: 'telefono', label: 'Teléfono', tipo: 'texto' },
      { key: 'email', label: 'Correo electrónico', tipo: 'email' },
    ],
  },
  almacenes: {
    titulo: 'Almacenes', singular: 'almacén', recurso: 'almacenes',
    columnas: [{ key: 'codigo', label: 'Código' }, { key: 'nombre', label: 'Nombre' }, { key: 'sucursal_nombre', label: 'Sucursal' }],
    campos: [
      { key: 'sucursal', label: 'Sucursal', tipo: 'select', requerido: true, fuente: { recurso: 'sucursales', etiqueta: (r) => r.nombre } },
      { key: 'codigo', label: 'Código', tipo: 'texto', requerido: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'descripcion', label: 'Descripción', tipo: 'texto' },
    ],
  },
  sucursales: {
    titulo: 'Sucursales', singular: 'sucursal', recurso: 'sucursales',
    columnas: [{ key: 'codigo', label: 'Código' }, { key: 'nombre', label: 'Nombre' }, { key: 'direccion', label: 'Dirección' }, { key: 'telefono', label: 'Teléfono' }],
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', requerido: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'direccion', label: 'Dirección', tipo: 'texto' },
      { key: 'telefono', label: 'Teléfono', tipo: 'texto' },
    ],
  },
  'tipos-movimiento': {
    titulo: 'Tipos de movimiento', singular: 'tipo de movimiento', recurso: 'tipos-movimiento',
    columnas: [
      { key: 'codigo', label: 'Código' }, { key: 'nombre', label: 'Nombre' }, { key: 'signo', label: 'Signo', tipo: 'numero' },
      { key: 'requiere_tercero', label: 'Tercero', tipo: 'bool' }, { key: 'es_traspaso', label: 'Traspaso', tipo: 'bool' },
    ],
    campos: [
      { key: 'codigo', label: 'Código', tipo: 'texto', requerido: true },
      { key: 'nombre', label: 'Nombre', tipo: 'texto', requerido: true },
      { key: 'signo', label: 'Operación', tipo: 'select', requerido: true, opciones: [{ label: 'Entrada (+)', value: 1 }, { label: 'Salida (−)', value: -1 }] },
      { key: 'requiere_tercero', label: 'Requiere tercero', tipo: 'booleano' },
      { key: 'tipo_tercero', label: 'Tipo de tercero admitido', tipo: 'select', opciones: [{ label: 'Cualquiera', value: '' }, { label: 'Proveedor', value: 'PROVEEDOR' }, { label: 'Cliente', value: 'CLIENTE' }] },
      { key: 'es_traspaso', label: 'Es traspaso entre almacenes', tipo: 'booleano' },
    ],
  },
}
