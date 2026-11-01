import { describe, expect, it } from 'vitest'
import { escalar, validarSalida } from '../stock'
import { fechaISO } from '../formato'

describe('validarSalida', () => {
  it('acepta salidas dentro del stock', () => {
    expect(validarSalida([{ productoId: 1, cantidad: 5 }], { 1: 10 })).toEqual({})
  })

  it('rechaza una línea que supera el stock', () => {
    const errores = validarSalida([{ productoId: 1, cantidad: 11 }], { 1: 10 })
    expect(errores[0]).toContain('Stock insuficiente')
  })

  it('suma líneas repetidas del mismo producto', () => {
    const errores = validarSalida(
      [{ productoId: 1, cantidad: 6 }, { productoId: 1, cantidad: 5 }, { productoId: 2, cantidad: 1 }],
      { 1: 10, 2: 1 },
    )
    expect(Object.keys(errores)).toEqual(['0', '1'])
  })

  it('no sufre errores de coma flotante (0.1 + 0.2)', () => {
    expect(validarSalida([{ productoId: 1, cantidad: 0.1 }, { productoId: 1, cantidad: 0.2 }], { 1: 0.3 })).toEqual({})
    expect(escalar(0.1) + escalar(0.2)).toBe(escalar(0.3))
  })

  it('trata un producto sin stock registrado como 0', () => {
    expect(validarSalida([{ productoId: 9, cantidad: 1 }], {})[0]).toBeDefined()
  })
})

describe('fechaISO', () => {
  it('usa la fecha local', () => {
    expect(fechaISO(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})
