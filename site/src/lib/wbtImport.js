// Import an in-game .wbt Trampler save into the builder. Fully client-side / offline.
//
// Envelope (cipher recovered by the community SandTools project, verified against
// GameAssembly.dll XorCryptography.Encrypt):
//   load: gunzip -> XOR(6-byte key, reset every 0xA000 chunk) -> Newtonsoft BSON
// We only read the structural `walker` doc (chassis + compartments + their cell
// coords/rotation) and skip the embedded 512x512 icon blob.

const KEY = [0x70, 0xdd, 0x1f, 0x2a, 0x0b, 0x4a]
const CHUNK = 0xa000

function xorDecode(bytes) {
  const out = new Uint8Array(bytes.length)
  for (let i = 0; i < bytes.length; i++) out[i] = bytes[i] ^ KEY[(i % CHUNK) % 6]
  return out
}

async function gunzip(buf) {
  // native browser gzip — no dependency
  const ds = new DecompressionStream('gzip')
  const stream = new Response(buf).body.pipeThrough(ds)
  return new Uint8Array(await new Response(stream).arrayBuffer())
}

// ---- minimal BSON reader (the subset Newtonsoft writes for these saves) ----
function readBson(buf) {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength)
  let p = 0
  const dec = new TextDecoder()
  function cstr() {
    const s = p
    while (buf[p] !== 0) p++
    const str = dec.decode(buf.subarray(s, p))
    p++
    return str
  }
  function doc() {
    const len = dv.getInt32(p, true); const end = p + len
    p += 4
    const obj = {}
    while (p < end - 1) {
      const type = buf[p++]
      const key = cstr()
      obj[key] = value(type)
    }
    p = end
    return obj
  }
  function value(type) {
    switch (type) {
      case 0x01: { const v = dv.getFloat64(p, true); p += 8; return v }
      case 0x02: { const n = dv.getInt32(p, true); p += 4; const s = dec.decode(buf.subarray(p, p + n - 1)); p += n; return s }
      case 0x03: return doc()
      case 0x04: { const a = doc(); return Object.keys(a).sort((x, y) => x - y).map((k) => a[k]) }
      case 0x05: { const n = dv.getInt32(p, true); p += 4; p += 1 /*subtype*/; const b = buf.subarray(p, p + n); p += n; return b }
      case 0x08: { const v = buf[p] !== 0; p += 1; return v }
      case 0x09: { const v = Number(dv.getBigInt64(p, true)); p += 8; return v } // datetime ms
      case 0x0a: return null
      case 0x10: { const v = dv.getInt32(p, true); p += 4; return v }
      case 0x12: { const v = Number(dv.getBigInt64(p, true)); p += 8; return v }
      default: throw new Error('unsupported BSON type 0x' + type.toString(16))
    }
  }
  return doc()
}

const pidOf = (epb) => (epb || '').replace(/^walker_/, '').replace(/_epb$/, '')

export async function decodeWbt(arrayBuffer) {
  const raw = await gunzip(new Uint8Array(arrayBuffer))
  const dec = xorDecode(raw)
  return readBson(dec)
}

// Map a decoded .wbt doc into builder state. Returns { state, stats }.
// PART_BY_ID is passed in to validate ids + skip unknown/legacy parts.
export function wbtToState(doc, PART_BY_ID, makeId) {
  const w = doc.walker
  if (!w || !w.Chassis) throw new Error('not a walker save (no chassis)')
  const chassisId = pidOf(w.Chassis.EpbId)
  if (!PART_BY_ID[chassisId]) {
    throw new Error(`chassis "${chassisId}" not in this build — the save is from a different game version`)
  }
  const c0 = w.Chassis.CellCoordinate || { x: 0, y: 0, z: 0 }
  const placements = []
  let skipped = 0
  for (const comp of w.Compartments || []) {
    const pid = pidOf(comp.EpbId)
    if (!PART_BY_ID[pid]) { skipped++; continue }
    const cc = comp.CellCoordinate || { x: 0, y: 0, z: 0 }
    placements.push({
      id: makeId(),
      partId: pid,
      // relative to the chassis origin (our builder renders chassis at 0,0,0)
      x: cc.x - c0.x,
      y: cc.y - c0.y,
      z: cc.z - c0.z,
      rot: Math.round(((comp.Rotation || 0) / 90)) & 3,
      conns: {},
    })
  }
  return {
    state: { chassisId, placements, name: (doc.name || '').trim() || 'Imported Trampler' },
    stats: { total: placements.length, skipped },
  }
}
