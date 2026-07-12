import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const tokenSource = readFileSync(join(process.cwd(), 'src/styles/tokens.css'), 'utf8')
const lightTheme = tokenSource.slice(0, tokenSource.indexOf('html.dark'))

const tokenHex = (name) => {
  const match = lightTheme.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i'))
  if (!match) throw new Error(`Missing hex token: --${name}`)
  return match[1]
}

const tokenRgb = (name) => {
  const pattern = `--${name}:\\s*rgb\\((\\d+)\\s+(\\d+)\\s+(\\d+)\\s*\\/\\s*(\\d+)%\\)`
  const match = lightTheme.match(new RegExp(pattern, 'i'))
  if (!match) throw new Error(`Missing rgb token: --${name}`)
  return {
    channels: match.slice(1, 4).map(Number),
    alpha: Number(match[4]) / 100
  }
}

const compositeHex = ({ channels, alpha }, background) => {
  const backdrop = background.slice(1).match(/.{2}/g).map((value) => parseInt(value, 16))
  return `#${channels.map((value, index) => (
    Math.round((value * alpha) + (backdrop[index] * (1 - alpha)))
      .toString(16)
      .padStart(2, '0')
  )).join('')}`
}

const luminance = (hex) => {
  const channels = hex.slice(1).match(/.{2}/g).map((value) => parseInt(value, 16) / 255)
  const [red, green, blue] = channels.map((value) => (
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  ))
  return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)
}

const contrast = (foreground, background) => {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return (values[0] + 0.05) / (values[1] + 0.05)
}

describe('light theme text contrast', () => {
  it('keeps semantic normal-text colors at WCAG AA contrast on the canvas', () => {
    const canvas = tokenHex('color-canvas')
    const textTokens = [
      'color-text-muted',
      'color-primary-text',
      'color-success-text',
      'color-warning-text',
      'color-danger-text',
      'color-info-text'
    ]

    textTokens.forEach((name) => {
      expect(contrast(tokenHex(name), canvas), name).toBeGreaterThanOrEqual(4.5)
    })
  })

  it('keeps status text readable on its semantic soft background', () => {
    const surface = tokenHex('color-surface')
    const statusTokens = ['success', 'warning', 'danger', 'info']

    statusTokens.forEach((status) => {
      const background = compositeHex(tokenRgb(`color-${status}-soft`), surface)
      expect(contrast(tokenHex(`color-${status}-text`), background), status)
        .toBeGreaterThanOrEqual(4.5)
    })
  })
})
