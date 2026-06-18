import itemsRaw from '../data/items.json'
import tablesRaw from '../data/loot_tables.json'
import recipesRaw from '../data/recipes.json'
import locationsRaw from '../data/locations.json'
import partsRaw from '../data/parts.json'
import lootSourcesRaw from '../data/loot_sources.json'
import locationContents from '../data/location_contents.json'
import extraLocationsRaw from '../data/extra_locations.json'
import locationArtRaw from '../data/location_art.json'
import weaponStatsRaw from '../data/weapon_stats.json'
import turretStatsRaw from '../data/turret_stats.json'

export const items = itemsRaw
export const tables = tablesRaw
export const recipes = recipesRaw
export const parts = partsRaw
export const lootSources = lootSourcesRaw

// asset helper — respects vite `base` (deployed under /sand/)
export function asset(path) {
  return import.meta.env.BASE_URL + path.replace(/^\//, '')
}

// locations: lootset-backed + extra prefab-only locations (forts, events, factories)
export const locations = [
  ...locationsRaw
    .filter((l) => l.kind !== 'test')
    .map((l) => ({ ...l, contents: locationContents[l.id] ?? null })),
  ...extraLocationsRaw.map((l) => ({ ...l, contents: l.contents ?? null })),
]

export const itemById = Object.fromEntries(items.map((i) => [i.id, i]))

export function itemName(id) {
  return itemById[id]?.name ?? id
}
export function itemIcon(id) {
  const ic = itemById[id]?.icon
  return ic ? asset(ic) : null
}

// gun / ammo / armor stats (range, reload, damage, penetration, armor rating)
// mined from data.unity3d weapon-family blueprints — see datamine/scripts/extract_weapon_stats.py
export const weaponStats = weaponStatsRaw
export const turretStats = turretStatsRaw
export function statsFor(id) {
  if (weaponStatsRaw.weapons[id]) return { kind: 'weapon', ...weaponStatsRaw.weapons[id] }
  if (weaponStatsRaw.ammo[id]) return { kind: 'ammo', ...weaponStatsRaw.ammo[id] }
  if (weaponStatsRaw.armor[id]) return { kind: 'armor', ...weaponStatsRaw.armor[id] }
  if (turretStatsRaw.turrets[id]) {
    const t = turretStatsRaw.turrets[id]
    // turret damage = its primary ammo's damage (lives in weapon_stats.json)
    const damage = (t.ammoTypes ?? [])
      .map((a) => weaponStatsRaw.ammo[a]?.damagePhysical)
      .find((d) => d != null) ?? null
    return { kind: 'turret', ...t, damage }
  }
  return null
}

export const RARITY_COLOR = {
  COMMON: '#9aa58f',
  UNCOMMON: '#6fbf73',
  NOTEWORTHY: '#5aa9e6',
  RARE: '#b388eb',
  REMARKABLE: '#e8a33d',
  EXCEPTIONAL: '#ef476f',
}

export const TABLE_CATEGORIES = ['med', 'resource', 'food', 'valuables', 'weapons', 'special']
export const EFFORTS = ['low', 'mid', 'high']

export const CATEGORY_LABEL = {
  med: 'Medical',
  resource: 'Resources',
  food: 'Food',
  valuables: 'Valuables',
  weapons: 'Weapons',
  special: 'Special',
}

export const KIND_LABEL = {
  island: 'Island',
  ship: 'Wrecked Ship',
  rock: 'Rock Formation',
  poi: 'Point of Interest',
  fort: 'Fort',
  event: 'Final Zone', // endgame locations — spawn in the final circle (renamed from "World Event", round 6)
}

export const KIND_GLYPH = {
  island: '◆',
  ship: '⚓',
  rock: '▲',
  poi: '●',
  fort: '■',
  event: '✦',
}

export const KIND_COLOR = {
  island: '#8a5e2b',
  ship: '#3f6f64',
  rock: '#6b5d49',
  poi: '#a4501f',
  fort: '#8c3a26',
  event: '#7d5a96',
}

// ---------- container groups (sets merged) ----------
// group key = `${group}|${tier}` ; each group has sets per mode
export const tableGroups = (() => {
  const map = new Map()
  for (const t of tables) {
    const key = `${t.group}|${t.tier ?? ''}`
    if (!map.has(key)) {
      map.set(key, { key, group: t.group, category: t.category, effort: t.effort, tier: t.tier, sets: [] })
    }
    map.get(key).sets.push(t)
  }
  for (const g of map.values()) g.sets.sort((a, b) => (a.set ?? 0) - (b.set ?? 0))
  return [...map.values()].sort((a, b) => a.group.localeCompare(b.group) || (a.tier ?? 0) - (b.tier ?? 0))
})()

// ---------- per-item lookup: where does item drop ----------
// returns [{group, category, effort, tier, setsWith, setsTotal, min, max, modes:{voyage:bool,storm:bool}}]
export function whereDrops(itemId, mode = 'voyage') {
  const out = []
  for (const g of tableGroups) {
    let withItem = 0
    let mn = Infinity
    let mx = -Infinity
    for (const s of g.sets) {
      const entry = (s[mode] ?? []).find((e) => e.item === itemId)
      if (entry) {
        withItem++
        mn = Math.min(mn, entry.min)
        mx = Math.max(mx, entry.max)
      }
    }
    if (withItem > 0) {
      out.push({
        ...g,
        setsWith: withItem,
        setsTotal: g.sets.length,
        min: mn,
        max: mx,
      })
    }
  }
  return out.sort((a, b) => b.setsWith / b.setsTotal - a.setsWith / a.setsTotal)
}

// does this group differ between modes?
export function groupDiffers(g) {
  for (const s of g.sets) {
    const v = JSON.stringify(s.voyage ?? [])
    const st = JSON.stringify(s.storm ?? [])
    if (v !== st) return true
  }
  return false
}

// ---------- Ops Board: condensed location archetypes (round 6) ----------
// The raw lists carry the same physical place many times: once per loot-flavour
// (Utility/Valuables/Weapons/Turret Ammo) and once per numbered prefab instance
// (Gunboat Big1-5, Rock Group1-7…). One group per archetype; variants live inside.
export const locationArt = locationArtRaw

export function locArt(locId) {
  const p = locationArt[locId]
  return p ? asset(p) : null
}

// known duplicate spellings across the two mining passes
const MERGE_ALIAS = {
  Schwalbenlnsel: 'Schwalbeninsel', // typo variant of the same island
}

// display names: in-game names go here as the community verifies them.
// Everything else displays its (cleaned) internal file name.
const DISPLAY_ALIAS = {
  'Living Sand': 'Living Sand (Worm Pit)',
  'Living Sand Jr': 'Living Sand Jr (Small Worm Pit)',
  'Ship Graveyard Living Sand': 'Ship Graveyard (Worm Pit)',
}

const LOOT_FLAVOUR_RE = /^(.*?)\s+(Turret Ammo|Utility|Valuables|Weapons)$/
const INSTANCE_RE = /^(.*\D)\s*0*(\d+)$/

export const locationGroups = (() => {
  const groups = new Map()
  for (const loc of locations) {
    if (loc.kind === 'test') continue
    let name = MERGE_ALIAS[loc.name] ?? loc.name
    name = name.replace(/^POI /, '').replace(/^Event /, '')
    let variant = null
    let vtype = null
    let m = name.match(LOOT_FLAVOUR_RE)
    if (m) {
      name = m[1]
      variant = m[2]
      vtype = 'loot'
    } else if ((m = name.match(INSTANCE_RE))) {
      name = m[1].trim()
      variant = '#' + m[2]
      vtype = 'instance'
    }
    const gkey = `${loc.kind}|${name.toLowerCase()}`
    let g = groups.get(gkey)
    if (!g) {
      g = { id: 'grp_' + gkey.replace(/\W+/g, '_'), name, kind: loc.kind, variantType: null, members: [] }
      groups.set(gkey, g)
    }
    if (vtype && !g.variantType) g.variantType = vtype
    g.members.push({ ...loc, variantLabel: variant })
  }
  for (const g of groups.values()) {
    g.displayName = DISPLAY_ALIAS[g.name] ?? g.name
    // confirmed = we have a verified in-game name (alias); else it's the raw file name
    g.nameConfirmed = !!DISPLAY_ALIAS[g.name]
    // merge true duplicates (Little Factory1 lootset entry + Little Factory01 prefab entry)
    const seen = new Map()
    const merged = []
    for (const mem of g.members) {
      const vk = mem.variantLabel ?? '·'
      const prev = seen.get(vk)
      if (prev) {
        prev.contents = prev.contents ?? mem.contents
        prev.caps = prev.caps?.length ? prev.caps : mem.caps
        prev.altIds = [...(prev.altIds ?? []), mem.id]
      } else {
        seen.set(vk, mem)
        merged.push(mem)
      }
    }
    g.members = merged.sort((a, b) =>
      (a.variantLabel ?? '').localeCompare(b.variantLabel ?? '', undefined, { numeric: true }),
    )
    g.art = g.members.map((mem) => locArt(mem.id) ?? (mem.altIds ?? []).map(locArt).find(Boolean)).find(Boolean) ?? null
  }
  return [...groups.values()]
})()

// crate-type profile for a location (normalized split of crate caps)
const CRATE_TYPES = ['Food Crate', 'Med Crate', 'Resource Crate', 'Valuables Crate', 'Weapon Crate', 'Shell Crate']
export const CRATE_COLOR = {
  'Food Crate': '#6fbf73',
  'Med Crate': '#e36868',
  'Resource Crate': '#c9a96a',
  'Valuables Crate': '#e8c14d',
  'Weapon Crate': '#5aa9e6',
  'Shell Crate': '#b388eb',
}
export function crateProfile(loc) {
  const out = []
  let total = 0
  for (const c of loc.caps) {
    if (c.types.length === 1 && CRATE_TYPES.includes(c.types[0])) {
      out.push({ type: c.types[0], max: c.max })
      total += c.max
    }
  }
  return { entries: out.sort((a, b) => b.max - a.max), total }
}

// reverse index: item id -> table ids
export const tablesByItem = {}
for (const t of tables) {
  for (const mode of ['voyage', 'storm']) {
    for (const e of t[mode] ?? []) {
      ;(tablesByItem[e.item] ??= new Set()).add(t.id)
    }
  }
}

// recipes index
export const recipesByOutput = {}
export const recipesByInput = {}
recipes.forEach((r, idx) => {
  for (const o of r.outputs) (recipesByOutput[o.item] ??= []).push(idx)
  for (const i of r.inputs) (recipesByInput[i.item] ??= []).push(idx)
})

export function fmtCount(min, max) {
  return min === max ? `${min}` : `${min}–${max}`
}
