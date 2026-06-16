import { useEffect, useMemo, useRef, useState } from 'react'
import { parts, asset } from '../lib/data.js'
import Preview3D from '../components/Preview3D.jsx'
import thumbs from '../data/part_thumbs.json'
import chassisCells from '../data/chassis_cells.json'

function cellOpen(chassisId, x, y) {
  const m = chassisCells[chassisId]
  return !m || !m[y] || m[y][x] !== 0
}

function thumbOf(partId) {
  const t = thumbs[partId]
  return t ? asset(t) : null
}

const CELL = 64
const PAD = 30
const LEVELS = [
  { z: -1, label: 'HULL' },
  { z: 0, label: 'DECK 1' },
  { z: 1, label: 'DECK 2' },
  { z: 2, label: 'DECK 3' },
]

const CAT_COLOR = {
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
  Other: '#7f96ad',
}

const chassisList = parts.filter((p) => p.category === 'Chassis')
const partById = Object.fromEntries(parts.map((p) => [p.id, p]))

const PALETTE_ORDER = [
  'Cargo', 'Crew', 'CaptainCrew', 'Corridor', 'Crafting', 'Balcony', 'Deck',
  'Armor', 'Reactor', 'Steering', 'Engine', 'Weapon', 'Special', 'Structure', 'Cruise', 'Other',
]

const DEFAULT_STATE = {
  v: 1,
  name: 'UNTITLED RIG',
  chassisId: 'compChassis_Medium4_Metal_4x4',
  placements: [],
}

function footprint(p, rot) {
  return rot % 2 === 1 ? { w: p.d, d: p.w } : { w: p.w, d: p.d }
}

function fits(state, partId, x, y, z, rot, ignoreId = null) {
  const part = partById[partId]
  const ch = partById[state.chassisId] ?? { w: 4, d: 4 }
  const { w, d } = footprint(part, rot)
  if (x < 0 || y < 0 || x + w > ch.w || y + d > ch.d) return false
  const isHatchPart = /hatch/i.test(partId)
  for (let dy = 0; dy < d; dy++)
    for (let dx = 0; dx < w; dx++)
      if (!cellOpen(state.chassisId, x + dx, y + dy) && !isHatchPart) return false
  for (const pl of state.placements) {
    if (pl.z !== z || pl.id === ignoreId) continue
    const op = partById[pl.partId]
    if (!op) continue
    const of = footprint(op, pl.rot)
    if (x < pl.x + of.w && pl.x < x + w && y < pl.y + of.d && pl.y < y + d) return false
  }
  return true
}

function encodeShare(state) {
  return 'SANDBP1.' + btoa(unescape(encodeURIComponent(JSON.stringify(state))))
}
function decodeShare(code) {
  const m = code.trim().match(/^SANDBP1\.(.+)$/s)
  if (!m) throw new Error('not a SANDBP1 code')
  return JSON.parse(decodeURIComponent(escape(atob(m[1]))))
}

export default function Builder() {
  const [state, setState] = useState(() => {
    try {
      const saved = localStorage.getItem('sand_blueprint')
      if (saved) return { ...DEFAULT_STATE, ...JSON.parse(saved) }
    } catch { /* fall through */ }
    return DEFAULT_STATE
  })
  const [level, setLevel] = useState(0)
  const [activePart, setActivePart] = useState(null) // part id being placed
  const [rot, setRot] = useState(0)
  const [selectedPl, setSelectedPl] = useState(null) // placement id
  const [hoverCell, setHoverCell] = useState(null)
  const [paletteQ, setPaletteQ] = useState('')
  const [openCat, setOpenCat] = useState('Cargo')
  const [shareOpen, setShareOpen] = useState(false)
  const [chassisOpen, setChassisOpen] = useState(false)
  const [shareText, setShareText] = useState('')
  const [notice, setNotice] = useState('')
  const idRef = useRef(1)
  const svgRef = useRef(null)
  const moveRef = useRef(null)

  useEffect(() => {
    localStorage.setItem('sand_blueprint', JSON.stringify(state))
  }, [state])

  function rotateSelected() {
    setState((s) => {
      const pl = s.placements.find((p) => p.id === selectedPl)
      if (!pl) return s
      const nr = (pl.rot + 1) % 4
      if (!fits(s, pl.partId, pl.x, pl.y, pl.z, nr, pl.id)) {
        flash('no room to rotate')
        return s
      }
      return { ...s, placements: s.placements.map((p) => (p.id === selectedPl ? { ...p, rot: nr } : p)) }
    })
  }

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'r' || e.key === 'R') {
        if (selectedPl != null) rotateSelected()
        else setRot((r) => (r + 1) % 4)
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedPl != null) {
        setState((s) => ({ ...s, placements: s.placements.filter((p) => p.id !== selectedPl) }))
        setSelectedPl(null)
      }
      if (e.key === 'Escape') {
        setActivePart(null)
        setSelectedPl(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedPl])

  const chassis = partById[state.chassisId] ?? { w: 4, d: 4, name: 'Unknown chassis' }
  const boardW = chassis.w * CELL + PAD * 2
  const boardH = chassis.d * CELL + PAD * 2 + 14

  const placementsHere = state.placements.filter((p) => p.z === level)

  function cellFromEvent(e) {
    const rect = svgRef.current.getBoundingClientRect()
    const sx = ((e.clientX - rect.left) / rect.width) * boardW
    const sy = ((e.clientY - rect.top) / rect.height) * boardH
    const x = Math.floor((sx - PAD) / CELL)
    const y = Math.floor((sy - PAD) / CELL)
    if (x < 0 || y < 0 || x >= chassis.w || y >= chassis.d) return null
    return { x, y }
  }

  function hitAt(cell) {
    return placementsHere.findLast((pl) => {
      const f = footprint(partById[pl.partId], pl.rot)
      return cell.x >= pl.x && cell.x < pl.x + f.w && cell.y >= pl.y && cell.y < pl.y + f.d
    })
  }

  function onBoardClick(e) {
    if (moveRef.current?.didMove) {
      moveRef.current = null
      return
    }
    moveRef.current = null
    const cell = cellFromEvent(e)
    if (!cell) return
    if (activePart) {
      if (fits(state, activePart, cell.x, cell.y, level, rot)) {
        const id = Date.now() * 10 + idRef.current++
        setState((s) => ({
          ...s,
          placements: [...s.placements, { id, partId: activePart, x: cell.x, y: cell.y, z: level, rot }],
        }))
        setActivePart(null) // auto-deselect after placing (owner feedback)
      } else {
        flash('does not fit there')
      }
      return
    }
    const hit = hitAt(cell)
    setSelectedPl(hit ? hit.id : null)
  }

  // drag-to-move placed parts
  function onBoardPointerDown(e) {
    if (activePart) return
    const cell = cellFromEvent(e)
    if (!cell) return
    const hit = hitAt(cell)
    if (hit) {
      moveRef.current = { id: hit.id, offX: cell.x - hit.x, offY: cell.y - hit.y, didMove: false }
      setSelectedPl(hit.id)
    }
  }
  function onBoardPointerMove(e) {
    setHoverCell(cellFromEvent(e))
    const mv = moveRef.current
    if (!mv) return
    const cell = cellFromEvent(e)
    if (!cell) return
    const nx = cell.x - mv.offX
    const ny = cell.y - mv.offY
    setState((s) => {
      const pl = s.placements.find((p) => p.id === mv.id)
      if (!pl || (pl.x === nx && pl.y === ny)) return s
      if (!fits(s, pl.partId, nx, ny, pl.z, pl.rot, pl.id)) return s
      mv.didMove = true
      return { ...s, placements: s.placements.map((p) => (p.id === mv.id ? { ...p, x: nx, y: ny } : p)) }
    })
  }
  function onBoardPointerUp() {
    if (moveRef.current && !moveRef.current.didMove) moveRef.current = null
  }

  function flash(msg) {
    setNotice(msg)
    setTimeout(() => setNotice(''), 1600)
  }

  function changeChassis(id) {
    const ch = partById[id]
    setState((s) => {
      const keep = s.placements.filter((pl) => {
        const f = footprint(partById[pl.partId], pl.rot)
        return pl.x + f.w <= ch.w && pl.y + f.d <= ch.d
      })
      if (keep.length !== s.placements.length) flash(`${s.placements.length - keep.length} parts dropped (out of bounds)`)
      return { ...s, chassisId: id, placements: keep }
    })
  }

  const manifest = useMemo(() => {
    const counts = new Map()
    for (const pl of state.placements) {
      const p = partById[pl.partId]
      if (!p) continue
      counts.set(p.id, (counts.get(p.id) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([id, n]) => ({ part: partById[id], n }))
      .sort((a, b) => b.n - a.n || a.part.name.localeCompare(b.part.name))
  }, [state.placements])

  const paletteGroups = useMemo(() => {
    const q = paletteQ.trim().toLowerCase()
    const usable = parts.filter(
      (p) => p.category !== 'Chassis' && (!q || p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)),
    )
    return PALETTE_ORDER.map((cat) => [cat, usable.filter((p) => p.category === cat)]).filter(([, l]) => l.length)
  }, [paletteQ])

  const selPlacement = state.placements.find((p) => p.id === selectedPl)
  const ghost = activePart && hoverCell ? { part: partById[activePart], ...hoverCell } : null
  const ghostFits = ghost ? fits(state, activePart, ghost.x, ghost.y, level, rot) : false

  return (
    <div className="builder">
      <div className="page-head">
        <div className="page-kicker" style={{ color: 'var(--blueprint-accent)' }}>Engineering bay</div>
        <div className="page-title" style={{ color: 'var(--blueprint-ink)' }}>Trampler Blueprints</div>
        <p className="page-sub">
          Plan a build on the real compartment grid — every part name, variant and footprint is
          datamined from the game. Lay out each deck separately, then share the exact manifest
          instead of a screenshot.
        </p>
      </div>

      <div className="bp-toolbar">
        <input
          className="bp-input"
          value={state.name}
          onChange={(e) => setState((s) => ({ ...s, name: e.target.value.toUpperCase() }))}
          style={{ minWidth: 220 }}
          maxLength={32}
        />
        <button className="bp-btn" onClick={() => setChassisOpen((o) => !o)}>
          ⬡ Chassis: {chassis.label ?? `${chassis.w}×${chassis.d}`}
        </button>
        <button
          className="bp-btn"
          onClick={() => (selectedPl != null ? rotateSelected() : setRot((r) => (r + 1) % 4))}
          title={selectedPl != null ? 'Rotate the selected part 90°' : 'Rotate the part you are placing'}
        >
          Rotate [R] {selectedPl != null ? '⟳ part' : ['→', '↓', '←', '↑'][rot]}
        </button>
        <button
          className="bp-btn"
          onClick={() => {
            setShareText(encodeShare(state))
            setShareOpen((o) => !o)
          }}
        >
          Share / Import
        </button>
        <button
          className="bp-btn danger"
          onClick={() => {
            if (confirm('Clear the whole blueprint?')) setState({ ...DEFAULT_STATE, name: state.name })
          }}
        >
          Wipe
        </button>
        {notice && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: '#e8927e', alignSelf: 'center' }}>
            ⚠ {notice}
          </span>
        )}
      </div>

      {chassisOpen && (
        <div className="bp-panel" style={{ marginBottom: 14 }}>
          <h3>Chassis bay</h3>
          <p style={{ fontSize: 12, opacity: 0.75, marginBottom: 10 }}>
            Footprint defines your build grid. “Cargo hatch” hulls have a floor opening for
            drop-loading. Leg count is from the game's chassis rigs. (Size nicknames are ours —
            the game only numbers them.)
          </p>
          <div className="chassis-grid">
            {chassisList.map((c) => {
              const on = state.chassisId === c.id
              return (
                <button
                  key={c.id}
                  className={'chassis-card' + (on ? ' on' : '')}
                  onClick={() => {
                    changeChassis(c.id)
                    setChassisOpen(false)
                  }}
                >
                  {thumbOf(c.id) && <img src={thumbOf(c.id)} alt="" style={{ width: 64, height: 64, objectFit: 'contain' }} />}
                  <svg viewBox={`0 0 ${c.w * 10 + 4} ${c.d * 10 + 4}`} style={{ width: c.w * 13, height: c.d * 13 }}>
                    <rect x="1" y="1" width={c.w * 10 + 2} height={c.d * 10 + 2} fill="rgba(90,169,230,0.12)" stroke="#8ec9ff" strokeWidth="1.5" />
                    {Array.from({ length: c.w * c.d }, (_, i) => (
                      <rect
                        key={i}
                        x={2 + (i % c.w) * 10}
                        y={2 + Math.floor(i / c.w) * 10}
                        width="10" height="10"
                        fill="none" stroke="rgba(146,196,255,0.35)" strokeDasharray="2 2"
                      />
                    ))}
                    {c.material.includes('Hole') && (
                      <rect
                        x={2 + Math.floor((c.w - 1) / 2) * 10} y={2 + Math.floor((c.d - 1) / 2) * 10}
                        width="10" height="10" fill="rgba(8,19,32,0.9)" stroke="#8ec9ff"
                      />
                    )}
                  </svg>
                  <div className="cc-label">{c.label ?? `${c.w}×${c.d}`}</div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {shareOpen && (
        <div className="bp-panel" style={{ marginBottom: 14 }}>
          <h3>Share code</h3>
          <p style={{ fontSize: 12, opacity: 0.75 }}>
            Copy this code to share your build, or paste someone else’s code and hit Load.
          </p>
          <textarea
            className="share-area"
            value={shareText}
            onChange={(e) => setShareText(e.target.value)}
            spellCheck={false}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button
              className="bp-btn"
              onClick={() => {
                navigator.clipboard?.writeText(shareText)
                flash('copied to clipboard')
              }}
            >
              Copy
            </button>
            <button
              className="bp-btn"
              onClick={() => {
                try {
                  const st = decodeShare(shareText)
                  if (!partById[st.chassisId]) throw new Error('unknown chassis')
                  setState({ ...DEFAULT_STATE, ...st })
                  setShareOpen(false)
                  flash('blueprint loaded')
                } catch {
                  flash('invalid share code')
                }
              }}
            >
              Load
            </button>
          </div>
        </div>
      )}

      <div className="builder-layout">
        {/* palette */}
        <div className="bp-panel" style={{ maxHeight: '74vh', overflowY: 'auto' }}>
          <h3>Parts locker</h3>
          <input
            className="bp-input"
            placeholder="Search parts…"
            value={paletteQ}
            onChange={(e) => setPaletteQ(e.target.value)}
            style={{ width: '100%', marginBottom: 8 }}
          />
          {activePart && (
            <button className="bp-btn" style={{ width: '100%', marginBottom: 8 }} onClick={() => setActivePart(null)}>
              ✕ stop placing
            </button>
          )}
          {paletteGroups.map(([cat, list]) => {
            const open = paletteQ.trim() !== '' || openCat === cat
            return (
              <div key={cat}>
                <button
                  className={'cat-toggle' + (open ? ' open' : '')}
                  onClick={() => setOpenCat(openCat === cat ? null : cat)}
                >
                  <span><span style={{ color: CAT_COLOR[cat] }}>■</span> {cat}</span>
                  <span className="part-size">{list.length} {open ? '▾' : '▸'}</span>
                </button>
                {open &&
                  list.map((p) => (
                    <button
                      key={p.id}
                      className={'part-btn' + (activePart === p.id ? ' on' : '')}
                      onClick={() => {
                        setActivePart(activePart === p.id ? null : p.id)
                        setSelectedPl(null)
                      }}
                      title={p.id}
                    >
                      {thumbOf(p.id) ? (
                        <img className="part-thumb" src={thumbOf(p.id)} alt="" loading="lazy" />
                      ) : (
                        <span className="part-thumb ghost">▦</span>
                      )}
                      <span style={{ flex: 1 }}>
                        {p.variant}
                        {p.material ? ` · ${p.material}` : ''}
                        {p.mirror ? ' · mirrored' : ''}
                      </span>
                      <span className="part-size">{p.w}×{p.d}</span>
                    </button>
                  ))}
              </div>
            )
          })}
        </div>

        {/* board */}
        <div>
          <div className="level-tabs">
            {LEVELS.map((lv) => {
              const n = state.placements.filter((p) => p.z === lv.z).length
              return (
                <button key={lv.z} className={level === lv.z ? 'on' : ''} onClick={() => setLevel(lv.z)}>
                  {lv.label}
                  <span className="lvl-count">[{n}]</span>
                </button>
              )
            })}
          </div>
          <div className="bp-board-wrap">
            <svg
              ref={svgRef}
              className="bp-grid"
              viewBox={`0 0 ${boardW} ${boardH}`}
              style={{ maxWidth: boardW, width: '100%' }}
              onClick={onBoardClick}
              onPointerDown={onBoardPointerDown}
              onPointerMove={onBoardPointerMove}
              onPointerUp={onBoardPointerUp}
              onMouseLeave={() => setHoverCell(null)}
            >
              <defs>
                <pattern id="woodHatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(191,224,255,0.25)" strokeWidth="1.4" />
                </pattern>
                <pattern id="metalFill" width="6" height="6" patternUnits="userSpaceOnUse">
                  <rect width="6" height="6" fill="rgba(146,196,255,0.10)" />
                </pattern>
              </defs>
              {thumbOf(state.chassisId) && (
                <image
                  href={thumbOf(state.chassisId)}
                  x={PAD}
                  y={PAD}
                  width={chassis.w * CELL}
                  height={chassis.d * CELL}
                  preserveAspectRatio="xMidYMid meet"
                  opacity="0.28"
                  pointerEvents="none"
                />
              )}
              {/* chassis outline */}
              <rect
                x={PAD - 6}
                y={PAD - 6}
                width={chassis.w * CELL + 12}
                height={chassis.d * CELL + 12}
                fill="none"
                stroke="rgba(191,224,255,0.8)"
                strokeWidth="2.5"
              />
              {/* FRONT indicator */}
              <g transform={`translate(${PAD + (chassis.w * CELL) / 2} ${PAD - 14})`}>
                <path d="M-7 0 L0 -9 L7 0 Z" fill="#ffd166" />
                <text x="14" y="1" fill="#ffd166" fontFamily="Big Shoulders Text" fontWeight="800" fontSize="13" letterSpacing="2.5">
                  FRONT
                </text>
              </g>
              <text
                x={PAD + (chassis.w * CELL) / 2}
                y={PAD + chassis.d * CELL + 32}
                textAnchor="middle"
                fill="rgba(191,224,255,0.45)"
                fontFamily="IBM Plex Mono"
                fontSize="10"
                letterSpacing="3"
              >
                — REAR —
              </text>
              {/* cells */}
              {Array.from({ length: chassis.w * chassis.d }, (_, i) => {
                const cx = i % chassis.w
                const cy = Math.floor(i / chassis.w)
                const open = cellOpen(state.chassisId, cx, cy)
                return open ? (
                  <rect
                    key={i}
                    x={PAD + cx * CELL}
                    y={PAD + cy * CELL}
                    width={CELL}
                    height={CELL}
                    fill="transparent"
                    stroke="rgba(146,196,255,0.28)"
                    strokeDasharray="3 4"
                  />
                ) : (
                  <g key={i}>
                    <rect x={PAD + cx * CELL} y={PAD + cy * CELL} width={CELL} height={CELL} fill="rgba(3,8,15,0.85)" stroke="rgba(146,196,255,0.4)" />
                    <text x={PAD + cx * CELL + CELL / 2} y={PAD + cy * CELL + CELL / 2 + 4} textAnchor="middle" fill="rgba(146,196,255,0.4)" fontFamily="IBM Plex Mono" fontSize="9" letterSpacing="1">HATCH</text>
                  </g>
                )
              })}
              {/* coordinates */}
              {Array.from({ length: chassis.w }, (_, i) => (
                <text key={'cx' + i} x={PAD + i * CELL + CELL / 2} y={PAD + chassis.d * CELL + 16} textAnchor="middle" fill="rgba(191,224,255,0.5)" fontFamily="IBM Plex Mono" fontSize="11">
                  {String.fromCharCode(65 + i)}
                </text>
              ))}
              {Array.from({ length: chassis.d }, (_, i) => (
                <text key={'cy' + i} x={PAD - 14} y={PAD + i * CELL + CELL / 2 + 4} textAnchor="middle" fill="rgba(191,224,255,0.5)" fontFamily="IBM Plex Mono" fontSize="11">
                  {i + 1}
                </text>
              ))}

              {/* placements on this level */}
              {placementsHere.map((pl) => {
                const p = partById[pl.partId]
                if (!p) return null
                const f = footprint(p, pl.rot)
                const col = CAT_COLOR[p.category] ?? '#8da9c4'
                const isSel = selectedPl === pl.id
                const open = p.material === 'Open' || p.material === 'Frame'
                const thumb = thumbOf(pl.partId)
                return (
                  <g key={pl.id}>
                    <rect
                      x={PAD + pl.x * CELL + 3}
                      y={PAD + pl.y * CELL + 3}
                      width={f.w * CELL - 6}
                      height={f.d * CELL - 6}
                      fill={p.material === 'Wood' ? 'url(#woodHatch)' : open ? 'transparent' : 'url(#metalFill)'}
                      stroke={col}
                      strokeWidth={isSel ? 3 : 1.8}
                      strokeDasharray={open ? '6 4' : 'none'}
                    />
                    {thumb && (
                      <image
                        href={thumb}
                        x={PAD + pl.x * CELL + (f.w * CELL) / 2 - Math.min(f.w, f.d) * CELL * 0.32}
                        y={PAD + pl.y * CELL + (f.d * CELL) / 2 - Math.min(f.w, f.d) * CELL * 0.32}
                        width={Math.min(f.w, f.d) * CELL * 0.64}
                        height={Math.min(f.w, f.d) * CELL * 0.64}
                        opacity="0.9"
                        pointerEvents="none"
                        transform={`rotate(${pl.rot * 90} ${PAD + pl.x * CELL + (f.w * CELL) / 2} ${PAD + pl.y * CELL + (f.d * CELL) / 2})`}
                      />
                    )}
                    <text
                      x={PAD + pl.x * CELL + (f.w * CELL) / 2}
                      y={PAD + pl.y * CELL + f.d * CELL - 14}
                      textAnchor="middle"
                      fill={col}
                      fontFamily="Chakra Petch"
                      fontWeight="600"
                      fontSize={Math.min(14, f.w * CELL * 0.19)}
                      paintOrder="stroke"
                      stroke="rgba(8,19,32,0.85)"
                      strokeWidth="4"
                    >
                      {p.variant.length > 14 ? p.variant.slice(0, 13) + '…' : p.variant}
                    </text>
                    <text
                      x={PAD + pl.x * CELL + (f.w * CELL) / 2}
                      y={PAD + pl.y * CELL + f.d * CELL - 4}
                      textAnchor="middle"
                      fill="rgba(191,224,255,0.6)"
                      fontFamily="IBM Plex Mono"
                      fontSize="10.5"
                      paintOrder="stroke"
                      stroke="rgba(8,19,32,0.85)"
                      strokeWidth="4"
                    >
                      {p.category}{p.material ? ` · ${p.material}` : ''}
                    </text>
                  </g>
                )
              })}

              {/* ghost preview */}
              {ghost && (
                <rect
                  x={PAD + ghost.x * CELL + 3}
                  y={PAD + ghost.y * CELL + 3}
                  width={footprint(ghost.part, rot).w * CELL - 6}
                  height={footprint(ghost.part, rot).d * CELL - 6}
                  fill={ghostFits ? 'rgba(90,169,230,0.18)' : 'rgba(226,76,61,0.2)'}
                  stroke={ghostFits ? '#8ec9ff' : '#e26d5a'}
                  strokeWidth="2"
                  strokeDasharray="5 4"
                  pointerEvents="none"
                />
              )}
            </svg>
            <div className="bp-title-block">
              {state.name || 'UNTITLED'} · {chassis.variant} {chassis.w}×{chassis.d} ·{' '}
              {LEVELS.find((l) => l.z === level)?.label} · SAND BP REV.1
            </div>
          </div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, opacity: 0.6, marginTop: 8 }}>
            pick a part → click to place (auto-deselects) · R rotate · drag placed parts to move ·
            Del removes · Esc cancels
          </p>

          <div className="bp-panel" style={{ marginTop: 14, padding: 8 }}>
            <h3 style={{ padding: '6px 8px 0' }}>Hull preview — all decks</h3>
            <Preview3D
              chassis={chassis}
              placements={state.placements}
              partById={partById}
              catColor={CAT_COLOR}
              level={level}
            />
          </div>
        </div>

        {/* manifest */}
        <div className="bp-panel" style={{ maxHeight: '74vh', overflowY: 'auto' }}>
          <h3>Manifest</h3>
          {selPlacement && (
            <div style={{ border: '1px solid rgba(146,196,255,0.4)', padding: 10, marginBottom: 12 }}>
              <div style={{ fontSize: 12.5, marginBottom: 6 }}>
                <strong style={{ color: CAT_COLOR[partById[selPlacement.partId]?.category] }}>
                  {partById[selPlacement.partId]?.name}
                </strong>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, opacity: 0.7, marginBottom: 8 }}>
                {String.fromCharCode(65 + selPlacement.x)}
                {selPlacement.y + 1} · {LEVELS.find((l) => l.z === selPlacement.z)?.label}
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  className="bp-btn"
                  onClick={rotateSelected}
                >
                  Rotate
                </button>
                <button
                  className="bp-btn danger"
                  onClick={() => {
                    setState((s) => ({ ...s, placements: s.placements.filter((p) => p.id !== selectedPl) }))
                    setSelectedPl(null)
                  }}
                >
                  Remove
                </button>
              </div>
            </div>
          )}

          <div className="weight-box">
            <div className="weight-row">
              <span>TOTAL WEIGHT</span>
              <span className="m-count">? kg</span>
            </div>
            <div className="weight-row">
              <span>CAPACITY ({chassis.label ?? 'chassis'})</span>
              <span className="m-count">? kg</span>
            </div>
            <div className="weight-bar"><div style={{ width: '0%' }} /></div>
            <div style={{ fontSize: 10, opacity: 0.55, fontFamily: 'var(--font-mono)', marginTop: 4 }}>
              live-updates once weight data lands (server-side — see note below)
            </div>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, opacity: 0.7, marginBottom: 8 }}>
            {state.placements.length} parts · {manifest.length} distinct
          </div>
          {manifest.length === 0 && (
            <div style={{ border: '1px dashed rgba(146,196,255,0.3)', padding: 16, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, opacity: 0.6 }}>
              EMPTY HULL — place parts from the locker
            </div>
          )}
          {manifest.map(({ part, n }) => (
            <div className="manifest-row" key={part.id}>
              <span>
                <span style={{ color: CAT_COLOR[part.category] }}>■ </span>
                {part.variant}
                {part.material ? ` · ${part.material}` : ''} ({part.w}×{part.d})
              </span>
              <span className="m-count">×{n}</span>
            </div>
          ))}

          {LEVELS.map((lv) => {
            const n = state.placements.filter((p) => p.z === lv.z).length
            if (!n) return null
            return (
              <div key={lv.z} className="manifest-row" style={{ borderBottom: 'none', opacity: 0.65 }}>
                <span>{lv.label}</span>
                <span className="m-count">{n} parts</span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="bp-panel" style={{ marginTop: 16 }}>
        <h3>Build requirements (from the game's analyzer code)</h3>
        <ul style={{ fontSize: 12.5, opacity: 0.85, paddingLeft: 18, lineHeight: 1.7 }}>
          <li><strong>Crew limit: 6</strong> — hardcoded in the build analyzer (MEMBER_LIMIT).</li>
          <li><strong>Weight capacity</strong> and <strong>energy budget</strong> are enforced — the in-game editor blocks saves past either limit ("limit reached: weight/energy"). The per-part values are server-side (see below).</li>
          <li><strong>Stability</strong> is computed from your chassis + centre of mass — top-heavy or lopsided builds move worse (the analyzer literally calculates a velocity multiplier from it).</li>
          <li><strong>Maneuver</strong> degrades as total weight approaches capacity; Weight Compensation parts offset it.</li>
          <li>Functionally you need a <strong>reactor</strong> (powers everything), <strong>steering</strong> (to pilot), and a <strong>captain's cabin / crew beds</strong> (respawn count comes from them) — the editor flags builds with "building errors" until the essentials are in.</li>
        </ul>
      </div>

      <div className="bp-panel" style={{ marginTop: 16 }}>
        <h3>About part weights & stats</h3>
        <p style={{ fontSize: 12.5, opacity: 0.8, maxWidth: '95ch' }}>
          Part weight, HP and prices are NOT in the game files — the game downloads them from its
          master server at match time (we verified this in the code: <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>GetCompartmentDefinitions</span>).
          Three ways we can get them: ① the devs share data (enquiry already sent), ② we record
          them manually from the in-game builder a part at a time, or ③ a future update ships them
          on disk. The builder is wired to display weights the moment we have a data file — nothing
          here will need rebuilding.
        </p>
      </div>

      <div className="footnote" style={{ borderTopColor: 'rgba(146,196,255,0.2)', color: 'rgba(191,224,255,0.4)' }}>
        Part catalogue: {parts.length} compartments datamined from walker EPBs (playtest) — names,
        variants and footprints are exact; in-game thumbnails are generated at runtime (not stored
        on disk), so parts render as schematic blocks for now. Blueprint autosaves to this browser.
      </div>
    </div>
  )
}
