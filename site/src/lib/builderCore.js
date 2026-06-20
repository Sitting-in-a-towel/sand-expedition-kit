// Builder V2 core — socket-driven placement engine mirroring the in-game editor.
// Data source: parts_v2.json = the game's own CompartmentsDatabase (cells, sockets,
// groups, limits) extracted verbatim. No name-parsing anywhere.
import partsV2 from '../data/parts_v2.json'
import meshIndex from '../data/mesh_index_v3.json' // v3 = real UVs + albedo textures

export const GROUP_LIMITS = partsV2.groupLimits // { REACTOR:1, STEERING:1, CAPTAIN:1 }
export const SOCKET_STATES = partsV2.socketStates // slotType -> state -> spawned entity
export const PARTS = partsV2.parts.filter((p) => p.enabled)
export const PART_BY_ID = Object.fromEntries(partsV2.parts.map((p) => [p.id, p]))
export const MESH_INDEX = meshIndex

export const CELL_XZ = meshIndex._cell || 4 // metres per grid cell (derived from meshes)
export const CELL_Y = 3.07 // metres per deck level (room height, measured from meshes)
export const MEMBER_LIMIT = 6 // hardcoded in game code (round-3 finding)

// grid bounds (the in-game editor grid; generous — exact size is runtime data)
export const GRID = { x: 13, zMin: -13, zMax: 13, yMax: 9 } // |x| <= 13 etc.

export const DIRS = {
  Left: [-1, 0, 0],
  Right: [1, 0, 0],
  Up: [0, 1, 0],
  Down: [0, -1, 0],
  Forward: [0, 0, 1],
  Back: [0, 0, -1],
}
const ROT_CYCLE = ['Forward', 'Right', 'Back', 'Left'] // 90° steps about Y

export function rotDir(dir, rot) {
  const i = ROT_CYCLE.indexOf(dir)
  if (i === -1) return dir // Up/Down unchanged
  return ROT_CYCLE[(i + rot) % 4]
}
export function rotCell([x, y, z], rot) {
  switch (((rot % 4) + 4) % 4) {
    case 1: return [z, y, -x]
    case 2: return [-x, y, -z]
    case 3: return [-z, y, x]
    default: return [x, y, z]
  }
}

export function cellKey(x, y, z) {
  return `${x},${y},${z}`
}

// world cells of a placement: [{x,y,z, vol, sup, sockets:{WorldDir:[{t,e,sn}]}}]
export function worldCells(part, px, py, pz, rot) {
  return part.cells.map((c) => {
    const [x, y, z] = rotCell(c.p, rot)
    const sockets = {}
    for (const [d, ss] of Object.entries(c.s)) sockets[rotDir(d, rot)] = ss
    return {
      x: x + px, y: y + py, z: z + pz,
      vol: !c.noVol, sup: !!c.sup, ignOOR: !!c.ignOOR, sockets,
      local: c.p,
    }
  })
}

// Leg anchors for a chassis. The chassis footprint encodes legs as a ring of
// `noVol` cells around the deck (`vol`) cells. Cluster those noVol cells into
// connected groups (one per leg) and return {x,z, dir, yaw} per leg:
//   dir = the outward face the leg projects from (axis it sits furthest outboard of)
//   yaw = Y-rotation to aim the leg mesh's natural outward (+X) along `dir`
// (yaw uses the same handed convention as placeMesh: +X -> (cos a, -sin a))
export function chassisLegs(chassis) {
  if (!chassis) return []
  const noVol = chassis.cells.filter((c) => c.noVol).map((c) => [c.p[0], c.p[2]])
  const vol = chassis.cells.filter((c) => !c.noVol).map((c) => [c.p[0], c.p[2]])
  if (!noVol.length || !vol.length) return []
  const dminX = Math.min(...vol.map((c) => c[0])), dmaxX = Math.max(...vol.map((c) => c[0]))
  const dminZ = Math.min(...vol.map((c) => c[1])), dmaxZ = Math.max(...vol.map((c) => c[1]))
  const k = (x, z) => `${x},${z}`
  const set = new Map(noVol.map((c) => [k(c[0], c[1]), c]))
  const seen = new Set()
  const clusters = []
  for (const c of noVol) {
    if (seen.has(k(c[0], c[1]))) continue
    const stack = [c]; seen.add(k(c[0], c[1])); const group = []
    while (stack.length) {
      const [x, z] = stack.pop(); group.push([x, z])
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nk = k(x + dx, z + dz)
        if (set.has(nk) && !seen.has(nk)) { seen.add(nk); stack.push(set.get(nk)) }
      }
    }
    clusters.push(group)
  }
  return clusters.map((g) => {
    const cx = g.reduce((s, c) => s + c[0], 0) / g.length
    const cz = g.reduce((s, c) => s + c[1], 0) / g.length
    const outX = cx < dminX ? dminX - cx : cx > dmaxX ? cx - dmaxX : 0
    const outZ = cz < dminZ ? dminZ - cz : cz > dmaxZ ? cz - dmaxZ : 0
    let fx = 0, fz = 0
    if (outX >= outZ) fx = cx < dminX ? -1 : 1
    else fz = cz < dminZ ? -1 : 1
    return {
      x: cx, z: cz,
      dir: fx ? (fx < 0 ? 'Left' : 'Right') : (fz < 0 ? 'Back' : 'Forward'),
      yaw: Math.atan2(-fz, fx),
    }
  })
}

export function buildOccupancy(state) {
  const occ = new Map() // key -> {plId, vol, sockets}
  const ch = PART_BY_ID[state.chassisId]
  if (ch) {
    for (const c of worldCells(ch, 0, 0, 0, 0)) {
      occ.set(cellKey(c.x, c.y, c.z), { plId: '_chassis', vol: c.vol, sockets: c.sockets })
    }
  }
  for (const pl of state.placements) {
    const part = PART_BY_ID[pl.partId]
    if (!part) continue
    for (const c of worldCells(part, pl.x, pl.y, pl.z, pl.rot)) {
      occ.set(cellKey(c.x, c.y, c.z), { plId: pl.id, vol: c.vol, sockets: c.sockets })
    }
  }
  return occ
}

const OPP = { Left: 'Right', Right: 'Left', Up: 'Down', Down: 'Up', Forward: 'Back', Back: 'Forward' }

function facesConnect(mySockets, theirSockets) {
  if (!mySockets || !theirSockets) return false
  const mine = new Set(mySockets.map((s) => s.t))
  return theirSockets.some((s) => mine.has(s.t))
}

// Validate placement. Non-blocking model: the ONLY hard block is two solid (vol)
// cells in the same spot (`blocked`). Everything else — disconnected, unsupported,
// out of grid, over the group limit — is a soft problem (`reasons`) that still places
// and renders red, to be fixed by rearranging. Returns:
//   { ok, blocked, reasons:[...], reason }   (ok = not blocked AND no soft reasons)
export function validate(state, occ, partId, px, py, pz, rot, ignoreId = null) {
  const part = PART_BY_ID[partId]
  if (!part) return { ok: false, blocked: true, reasons: ['unknown part'], reason: 'unknown part' }
  const cells = worldCells(part, px, py, pz, rot)
  const reasons = []
  let blocked = false
  let outOfGrid = false

  for (const c of cells) {
    if (c.ignOOR) continue // ladder/clearance cells (e.g. entrance shaft) are exempt from bounds + overlap
    if (Math.abs(c.x) > GRID.x || c.z < GRID.zMin || c.z > GRID.zMax || c.y < 0 || c.y > GRID.yMax) {
      if (!(!c.vol && c.y > GRID.yMax)) outOfGrid = true // tall clearance may poke out the top
    }
    const own = occ.get(cellKey(c.x, c.y, c.z))
    if (own && own.plId !== ignoreId && own.vol && c.vol) blocked = true // solid-on-solid only
  }
  if (outOfGrid) reasons.push('outside build grid')

  // group limits (REACTOR/STEERING/CAPTAIN = 1) — soft (placeable, flagged red)
  for (const g of part.groups) {
    const lim = GROUP_LIMITS[g]
    if (lim != null) {
      const count = state.placements.filter(
        (pl) => pl.id !== ignoreId && PART_BY_ID[pl.partId]?.groups.includes(g),
      ).length
      if (count + 1 > lim) reasons.push(`${g} limit (${lim}) reached`)
    }
  }

  // support + connectivity (socket-driven, mirrors EditorGrid neighbour checks)
  let connected = false
  let supportOk = true
  for (const c of cells) {
    const below = occ.get(cellKey(c.x, c.y - 1, c.z))
    const belowMine = below && below.plId !== ignoreId
    const hasVolBelow = belowMine && below.vol
    if (hasVolBelow) connected = true
    let faceConn = false
    for (const [dir, vec] of Object.entries(DIRS)) {
      const n = occ.get(cellKey(c.x + vec[0], c.y + vec[1], c.z + vec[2]))
      if (!n || n.plId === ignoreId) continue
      if (facesConnect(c.sockets[dir], n.sockets?.[OPP[dir]])) {
        connected = true
        faceConn = true
      }
    }
    if (c.sup && !hasVolBelow && !faceConn) supportOk = false
  }
  if (!connected) reasons.push('not connected to the rig')
  if (!supportOk) reasons.push('needs support underneath')

  // entrance-specific rule: the vestibule must overhang an open edge — its ladder
  // column (straight down to the ground) must be clear of solid cells — and it can't
  // sit over a leg.
  if (part.groups.includes('ENTRANCE')) {
    const vest = cells.find((c) => c.vol) // the single volume cell (vestibule)
    if (vest) {
      for (let y = py - 1; y >= 0; y--) {
        const o = occ.get(cellKey(vest.x, y, vest.z))
        if (o && o.plId !== ignoreId && o.vol) { reasons.push('ladder blocked below'); break }
      }
      // leg cells = chassis noVol footprint. TODO(owner verify): make this directional
      // — a corner leg may still allow a ladder on the face it doesn't point out of.
      const ch = PART_BY_ID[state.chassisId]
      if (ch && ch.cells.some((c) => c.noVol && c.p[0] === vest.x && c.p[2] === vest.z)) {
        reasons.push('leg in the way')
      }
    }
  }

  return {
    ok: !blocked && reasons.length === 0,
    blocked,
    reasons,
    reason: blocked ? 'space already taken' : (reasons[0] || ''),
  }
}

export const isEntrance = (part) => !!part?.groups?.includes('ENTRANCE')

// Cells where the given entrance part would be a fully-valid placement at `level`.
// Scans only empty cells orthogonally adjacent to the rig (so it can connect) — cheap.
export function entranceLegalCells(state, partId, level) {
  const part = PART_BY_ID[partId]
  if (!isEntrance(part)) return []
  const occ = buildOccupancy(state)
  const cand = new Set()
  for (const key of occ.keys()) {
    const [x, y, z] = key.split(',').map(Number)
    if (y !== level) continue
    for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nk = cellKey(x + dx, level, z + dz)
      if (!occ.has(nk)) cand.add(`${x + dx},${z + dz}`)
    }
  }
  const out = []
  for (const c of cand) {
    const [x, z] = c.split(',').map(Number)
    if (validate(state, occ, partId, x, level, z, 0).ok) out.push({ x, z })
  }
  return out
}

// Validity of every placement in a state (each checked against all the others).
// Returns { plId: { blocked, reasons } } for placements that aren't fully ok.
export function placementValidity(state) {
  const map = {}
  for (const pl of state.placements) {
    const others = { ...state, placements: state.placements.filter((p) => p.id !== pl.id) }
    const v = validate(others, buildOccupancy(others), pl.partId, pl.x, pl.y, pl.z, pl.rot)
    if (!v.ok) map[pl.id] = { blocked: v.blocked, reasons: v.reasons }
  }
  return map
}

// Editable sockets of a placement (world-space) for door/hatch toggles.
// -> [{key, x,y,z, dir, type, states:[...] }]
export function editableSockets(part, pl) {
  const out = []
  const cells = worldCells(part, pl.x, pl.y, pl.z, pl.rot)
  cells.forEach((c, ci) => {
    for (const [dir, ss] of Object.entries(c.sockets)) {
      for (const s of ss) {
        if (!s.e) continue
        const states = Object.keys(SOCKET_STATES[s.t] ?? { DEFAULT: '' })
          .filter((st) => !(s.bl ?? []).includes(st))
        out.push({
          key: `${ci}|${dir}`,
          x: c.x, y: c.y, z: c.z, dir, type: s.t, states,
        })
      }
    }
  })
  return out
}

// ---- essentials / manifest ----
export const ESSENTIALS = [
  { group: 'REACTOR', label: 'Reactor' },
  { group: 'STEERING', label: 'Steering' },
  { group: 'CAPTAIN', label: "Captain's cabin" },
  { group: 'ENTRANCE', label: 'Entrance' },
]

export function manifest(state) {
  const counts = new Map()
  for (const pl of state.placements) {
    counts.set(pl.partId, (counts.get(pl.partId) ?? 0) + 1)
  }
  const rows = [...counts.entries()]
    .map(([partId, n]) => ({ part: PART_BY_ID[partId], n }))
    .filter((r) => r.part)
    .sort((a, b) => a.part.category.localeCompare(b.part.category) || a.part.name.localeCompare(b.part.name))
  const groups = new Set(state.placements.flatMap((pl) => PART_BY_ID[pl.partId]?.groups ?? []))
  const crew = state.placements.filter((pl) => PART_BY_ID[pl.partId]?.groups.includes('CREW')).length
  return { rows, groups, crew, total: state.placements.length }
}

// ---- share codes ----
export function encodeShare(state) {
  return 'SANDBP2.' + btoa(unescape(encodeURIComponent(JSON.stringify(state))))
}
export function decodeShare(code) {
  const m = code.trim().match(/^SANDBP2\.(.+)$/s)
  if (!m) throw new Error('not a SANDBP2 code')
  return JSON.parse(decodeURIComponent(escape(atob(m[1]))))
}

export const CAT_COLOR = {
  Cargo: '#ffc971',
  Crew: '#7ae582',
  CaptainCrew: '#3ddc97',
  Corridor: '#e8edf2',
  Crafting: '#ff9770',
  Balcony: '#70d6ff',
  Deck: '#9aa7d8',
  Armor: '#aab6c2',
  Reactor: '#ff70a6',
  Steering: '#ffd670',
  Engine: '#ff8c42',
  Weapon: '#ef476f',
  Special: '#b388eb',
  Structure: '#8da9c4',
  Cruise: '#62b6cb',
  Medical: '#e36868',
  Chassis: '#4a6f96',
  Other: '#7f96ad',
}

export const CATEGORY_ORDER = [
  'Cargo', 'Crew', 'CaptainCrew', 'Corridor', 'Crafting', 'Medical', 'Balcony', 'Deck',
  'Armor', 'Reactor', 'Steering', 'Engine', 'Weapon', 'Special', 'Structure', 'Cruise', 'Other',
]
