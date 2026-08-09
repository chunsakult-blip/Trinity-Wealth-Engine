import { describe, it, expect } from 'vitest'
import {
  VIBRANT_BUCKET_PALETTE,
  normalizeHex,
  hexToHsl,
  hslToHex,
  getUniqueBucketColor,
  getRandomizedBucketColor,
  randomizeAllBucketColors,
} from './bucketColors'

describe('bucketColors utility', () => {
  it('normalizes hex strings correctly', () => {
    expect(normalizeHex('#3b82f6')).toBe('#3B82F6')
    expect(normalizeHex('#abc')).toBe('#AABBCC')
    expect(normalizeHex(null)).toBe('#3B82F6')
    expect(normalizeHex('invalid')).toBe('#3B82F6')
  })

  it('converts hex to hsl and back accurately', () => {
    const hex = '#3B82F6'
    const [h, s, l] = hexToHsl(hex)
    expect(h).toBeGreaterThanOrEqual(0)
    expect(s).toBeGreaterThanOrEqual(0)
    expect(l).toBeGreaterThanOrEqual(0)

    const backHex = hslToHex(h, s, l)
    expect(backHex).toBe('#3B82F6')
  })

  it('returns an unused color from palette when available', () => {
    const existing = ['#3B82F6', '#8B5CF6']
    const unique = getUniqueBucketColor(existing)
    expect(existing).not.toContain(unique)
    expect(VIBRANT_BUCKET_PALETTE).toContain(unique)
  })

  it('calculates maximal hue distance when palette is exhausted', () => {
    // Fill palette completely
    const existing = VIBRANT_BUCKET_PALETTE.slice()
    const unique = getUniqueBucketColor(existing)
    expect(typeof unique).toBe('string')
    expect(unique).toMatch(/^#[0-9A-F]{6}$/)
  })

  it('getRandomizedBucketColor returns unused color different from current', () => {
    const existing = ['#3B82F6']
    const current = '#3B82F6'
    const randomColor = getRandomizedBucketColor(existing, current)
    expect(randomColor).not.toBe(current)
  })

  it('randomizeAllBucketColors assigns distinct colors to all items', () => {
    const items = [
      { name: 'Item 1', color: '#3B82F6' },
      { name: 'Item 2', color: '#3B82F6' },
      { name: 'Item 3', color: '#3B82F6' },
    ]
    const result = randomizeAllBucketColors(items)
    expect(result).toHaveLength(3)
    const assignedColors = result.map((r) => r.color)
    const uniqueSet = new Set(assignedColors)
    expect(uniqueSet.size).toBe(3)
  })
})
