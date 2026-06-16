import { useMemo, useState } from 'react'
import { locationGroups, KIND_LABEL, KIND_GLYPH, crateProfile, CRATE_COLOR, locArt } from '../lib/data.js'

// The real map is procedural — this is a schematic field map. Location ARCHETYPES are
// grouped by category; loot-flavour / numbered-instance variants live inside each card.

function hashStr(s) {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}
function mulberry32(a) {
  return function () {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// ink colors per kind (drawn on parchment)
const INK = {
  island: '#7a4a14',
  ship: '#2e5d52',
  rock: '#5c4a32',
  poi: '#9c4a16',
  fort: '#8a2f1c',
  event: '#6b4687',
}

const BOARD = 1100
// zone layout: fixed board (no zoom/pan), labels always on — sized to content
const ZONES = {
  island: { x: 55, y: 135, w: 480, h: 720, label: 'ISLANDS', cols: 5 },
  ship: { x: 575, y: 135, w: 475, h: 470, label: 'SHIPWRECKS', cols: 4 },
  rock: { x: 575, y: 645, w: 475, h: 210, label: 'ROCK FORMATIONS', cols: 4 },
  poi: { x: 55, y: 895, w: 330, h: 110, label: 'FIELD POIs', cols: 4 },
  fort: { x: 420, y: 895, w: 220, h: 110, label: 'FORTS', cols: 3 },
  event: { x: 680, y: 895, w: 370, h: 110, label: 'FINAL ZONE', cols: 4 },
}

function computePositions() {
  const byKind = {}
  for (const g of locationGroups) (byKind[g.kind] ??= []).push(g)
  const pts = []
  for (const [kind, groups] of Object.entries(byKind)) {
    const z = ZONES[kind]
    if (!z) continue
    groups.sort((a, b) => a.displayName.localeCompare(b.displayName))
    const cols = z.cols
    const rows = Math.ceil(groups.length / cols)
    const cw = z.w / cols
    const ch = z.h / Math.max(rows, 1)
    groups.forEach((g, i) => {
      const rnd = mulberry32(hashStr(g.id))
      const cx = i % cols
      const cy = Math.floor(i / cols)
      pts.push({
        g,
        x: z.x + cx * cw + cw / 2 + (rnd() - 0.5) * Math.min(8, cw * 0.1),
        y: z.y + cy * ch + ch / 2 - 4 + (rnd() - 0.5) * 5,
      })
    })
  }
  return pts
}

function inkBlot(seed, x, y, r) {
  const rnd = mulberry32(seed)
  let d = ''
  const segs = 9
  for (let i = 0; i <= segs; i++) {
    const a = (i / segs) * Math.PI * 2
    const rr = r * (0.75 + rnd() * 0.5)
    d += (i === 0 ? 'M' : 'L') + (x + rr * Math.cos(a)).toFixed(1) + ' ' + (y + rr * Math.sin(a)).toFixed(1)
  }
  return d + 'Z'
}

const ALL_KINDS = ['island', 'ship', 'rock', 'poi', 'fort', 'event']

export default function MapPage() {
  const positions = useMemo(computePositions, [])
  const [kinds, setKinds] = useState(new Set(ALL_KINDS))
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)
  const [hovered, setHovered] = useState(null)

  const q = query.trim().toLowerCase()
  const visible = (g) =>
    kinds.has(g.kind) &&
    (!q || g.displayName.toLowerCase().includes(q) || g.members.some((m) => m.name.toLowerCase().includes(q)))

  function toggleKind(k) {
    setKinds((prev) => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })
  }

  const sel = selected ? locationGroups.find((g) => g.id === selected) : null

  return (
    <>
      <div className="page-head">
        <div className="page-kicker">Field map</div>
        <div className="page-title">Operations Board</div>
        <p className="page-sub">
          SAND worlds are procedurally generated — real positions change every match. This field
          map shows <strong>one card per location type</strong>; loot variants and size variants
          are inside each card. Names are the internal file names until the community confirms
          the in-game ones.
        </p>
      </div>

      <div className="controls">
        <input
          className="search"
          placeholder="Search locations…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {ALL_KINDS.map((k) => (
          <button
            key={k}
            className={'chip' + (kinds.has(k) ? ' on' : '')}
            style={kinds.has(k) ? { background: INK[k], borderColor: INK[k], color: '#f2e3bf', boxShadow: 'none' } : {}}
            onClick={() => toggleKind(k)}
          >
            {KIND_GLYPH[k]} {KIND_LABEL[k]} ({locationGroups.filter((g) => g.kind === k).length})
          </button>
        ))}
      </div>

      <div className="map-layout">
        <div className="map-board parchment locked">
          <svg viewBox={`0 0 ${BOARD} ${BOARD}`}>
            <defs>
              <radialGradient id="paper" cx="50%" cy="42%" r="75%">
                <stop offset="0%" stopColor="#dcc596" />
                <stop offset="62%" stopColor="#d2b988" />
                <stop offset="88%" stopColor="#bb9f6c" />
                <stop offset="100%" stopColor="#a3854f" />
              </radialGradient>
              <filter id="rough">
                <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" result="n" />
                <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0.6 0.2 0 0 0" result="alpha" />
                <feComposite operator="in" in="alpha" in2="SourceGraphic" result="grain" />
                <feBlend in="SourceGraphic" in2="grain" mode="multiply" />
              </filter>
              {/* dune ridges — stretched ridge noise, like the in-game sand chart */}
              <filter id="dunes" x="0" y="0" width="100%" height="100%">
                <feTurbulence type="turbulence" baseFrequency="0.012 0.045" numOctaves="3" seed="7" result="n" />
                <feComponentTransfer in="n" result="ridge">
                  <feFuncA type="discrete" tableValues="0 0 0 0.5 0 0 0.3 0 0 0 0.45 0 0" />
                </feComponentTransfer>
                <feComposite operator="in" in="ridge" in2="SourceGraphic" result="cut" />
                <feFlood floodColor="#8a6a38" result="ink" />
                <feComposite operator="in" in="ink" in2="cut" />
              </filter>
            </defs>

            {/* paper */}
            <rect width={BOARD} height={BOARD} fill="url(#paper)" />
            <rect width={BOARD} height={BOARD} fill="#fff" filter="url(#dunes)" opacity="0.35" />
            <rect width={BOARD} height={BOARD} fill="transparent" filter="url(#rough)" opacity="0.5" />
            {/* worn edge */}
            <rect x="14" y="14" width={BOARD - 28} height={BOARD - 28} fill="none" stroke="#5a3e1e" strokeWidth="3" opacity="0.75" />
            <rect x="22" y="22" width={BOARD - 44} height={BOARD - 44} fill="none" stroke="#5a3e1e" strokeWidth="1" opacity="0.45" />

            <g>
              {/* title + compass */}
              <text x="56" y="76" fill="#5a3e1e" fontFamily="Big Shoulders Stencil Text" fontSize="40" letterSpacing="4" opacity="0.9">
                SOPHIE — RAIDER'S INDEX
              </text>
              <text x="58" y="96" fill="#7a5a30" fontFamily="IBM Plex Mono" fontSize="11" letterSpacing="2" opacity="0.8">
                LOCATIONS GROUPED BY TYPE — NOT ACTUAL POSITIONS
              </text>
              <g transform={`translate(${BOARD - 90} 78)`} opacity="0.8">
                <circle r="26" fill="none" stroke="#5a3e1e" strokeWidth="1.5" />
                <path d="M0 -24 L6 0 L0 24 L-6 0 Z" fill="#5a3e1e" opacity="0.8" />
                <text y="-32" textAnchor="middle" fill="#5a3e1e" fontFamily="IBM Plex Mono" fontSize="12">N</text>
              </g>

              {/* zones */}
              {Object.entries(ZONES).map(([kind, z]) => (
                <g key={kind} opacity={kinds.has(kind) ? 1 : 0.28}>
                  <rect
                    x={z.x} y={z.y} width={z.w} height={z.h}
                    fill={INK[kind]} opacity="0.05"
                  />
                  <rect
                    x={z.x} y={z.y} width={z.w} height={z.h}
                    fill="none" stroke={INK[kind]} strokeWidth="1.4" strokeDasharray="7 5" opacity="0.55"
                  />
                  <text x={z.x + 10} y={z.y - 8} fill={INK[kind]} fontFamily="Big Shoulders Text" fontWeight="800" fontSize="19" letterSpacing="3" opacity="0.9">
                    {z.label}
                  </text>
                </g>
              ))}

              {/* markers — art stamp when we have a render, ink circle otherwise */}
              {positions.map(({ g, x, y }) => {
                const on = visible(g)
                const isSel = selected === g.id
                const isHov = hovered === g.id
                const ink = INK[g.kind]
                const label = g.displayName.length > 17 && !isSel && !isHov ? g.displayName.slice(0, 16) + '…' : g.displayName
                const r = g.art ? 21 : 9.5
                return (
                  <g
                    key={g.id}
                    className={'map-marker' + (on ? '' : ' dim')}
                    transform={`translate(${x} ${y})`}
                    onClick={() => on && setSelected(isSel ? null : g.id)}
                    onMouseEnter={() => setHovered(g.id)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <title>{g.displayName}</title>
                    <path d={inkBlot(hashStr(g.id), 0, 0, r + 3)} fill={ink} opacity={isSel ? 0.3 : 0.13} />
                    {isSel && <circle r={r + 5} fill="none" stroke={ink} strokeWidth="2" strokeDasharray="4 3" />}
                    {g.art ? (
                      <image
                        href={g.art}
                        x={-r}
                        y={-r}
                        width={r * 2}
                        height={r * 2}
                        preserveAspectRatio="xMidYMid meet"
                        opacity={isSel || isHov ? 1 : 0.92}
                      />
                    ) : (
                      <>
                        <circle r="9.5" fill="#e9d6a8" stroke={ink} strokeWidth={isSel || isHov ? 2.4 : 1.5} />
                        <text y="3.8" textAnchor="middle" fill={ink} fontSize="10" fontWeight="700">
                          {KIND_GLYPH[g.kind]}
                        </text>
                      </>
                    )}
                    {g.members.length > 1 && (
                      <g transform={`translate(${r - 2} ${-r + 2})`}>
                        <circle r="8" fill={ink} />
                        <text y="3" textAnchor="middle" fill="#f2e3bf" fontFamily="IBM Plex Mono" fontSize="9" fontWeight="700">
                          {g.members.length}
                        </text>
                      </g>
                    )}
                    <text
                      y={r + 12}
                      textAnchor="middle"
                      fill={isSel || isHov ? '#1f1407' : '#42301a'}
                      fontFamily="Chakra Petch"
                      fontSize={isSel || isHov ? 12 : 11}
                      fontWeight="600"
                      paintOrder="stroke"
                      stroke="#dcc596"
                      strokeWidth="3.5"
                    >
                      {label}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        </div>

        <aside className="loc-drawer">
          {sel ? <GroupDetail group={sel} onClose={() => setSelected(null)} /> : (
            <div className="empty-note">
              SELECT A MARKER
              <br />
              <span style={{ opacity: 0.6 }}>— location intel will appear here —</span>
            </div>
          )}
        </aside>
      </div>

      <div className="footnote">
        {locationGroups.length} location archetypes (merged from the raw per-variant lists) ·
        names, kinds, spawn caps and crate splits datamined from playtest LootSet + roster
        assets · art assembled from each location's actual prefab modules.
      </div>
    </>
  )
}

function ContentsSection({ c }) {
  const crateRows = Object.entries(c.crates).sort((a, b) => b[1] - a[1])
  const treasureRows = Object.entries(c.treasures)
  return (
    <>
      <div className="section-label" style={{ margin: '16px 0 8px' }}>What's placed here</div>
      {c.benches > 0 && (
        <div className="cap-row" style={{ borderColor: 'rgba(111,191,174,0.5)' }}>
          <span className="cap-types" style={{ color: 'var(--teal)' }}>⚒ Crafting station{c.benches > 1 ? 's' : ''}</span>
          <span className="cap-max">×{c.benches}</span>
        </div>
      )}
      {crateRows.map(([k, v]) => (
        <div className="cap-row" key={k}>
          <span className="cap-types">{k}</span>
          <span className="cap-max">×{v}</span>
        </div>
      ))}
      {treasureRows.map(([k, v]) => (
        <div className="cap-row" key={k}>
          <span className="cap-types">✦ {k}</span>
          <span className="cap-max">×{v}</span>
        </div>
      ))}
      {c.locked > 0 && (
        <div className="cap-row">
          <span className="cap-types">🔒 Locked loot (needs key)</span>
          <span className="cap-max">×{c.locked}</span>
        </div>
      )}
      {c.mobs > 0 && (
        <div className="cap-row" style={{ borderColor: 'rgba(194,69,46,0.5)' }}>
          <span className="cap-types" style={{ color: '#e08a76' }}>☠ Mob spawners</span>
          <span className="cap-max">×{c.mobs}</span>
        </div>
      )}
      <p style={{ marginTop: 8, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
        Counted from this location's actual prefab (spawner placements). Spawners roll their
        loot per match.
      </p>
    </>
  )
}

function MemberBody({ loc }) {
  const profile = crateProfile(loc)
  return (
    <>
      {loc.alarmBox && (
        <div className="cap-row" style={{ marginTop: 14, borderColor: 'rgba(232,161,61,0.55)', background: 'rgba(232,161,61,0.06)' }}>
          <span className="cap-types" style={{ color: '#e8a33d' }}>
            🔔 Alarm Box (alarmed high-value loot)
          </span>
          <span className="cap-max" style={{ color: '#e8a33d', fontSize: 11 }}>
            {loc.alarmBox === 'sometimes' ? 'SOME MATCHES' : 'SPAWNS HERE'}
          </span>
        </div>
      )}
      {loc.alarmBox === 'sometimes' && (
        <p style={{ marginTop: 6, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
          This island has two variants in the files — with and without the Alarm Box. The match
          rolls which one you get.
        </p>
      )}

      {profile.entries.length > 1 && (
        <>
          <div className="section-label" style={{ margin: '16px 0 8px' }}>Crate split</div>
          <div className="crate-bar">
            {profile.entries.map((e) => (
              <div
                key={e.type}
                style={{ width: `${(e.max / profile.total) * 100}%`, background: CRATE_COLOR[e.type] }}
                title={`${e.type}: cap ${e.max} (${Math.round((e.max / profile.total) * 100)}%)`}
              />
            ))}
          </div>
          <div className="crate-legend">
            {profile.entries.map((e) => (
              <span key={e.type}>
                <i style={{ background: CRATE_COLOR[e.type] }} /> {e.type.replace(' Crate', '')}{' '}
                {Math.round((e.max / profile.total) * 100)}%
              </span>
            ))}
          </div>
        </>
      )}

      {loc.contents && <ContentsSection c={loc.contents} />}

      <div className="section-label" style={{ margin: '16px 0 10px' }}>
        Spawn caps
      </div>
      {loc.caps.length === 0 ? (
        <div className="empty-note" style={{ padding: 18 }}>
          {loc.contents ? 'No category caps — see placed spawners above.' : 'No item caps recorded — likely decorative or event-driven.'}
        </div>
      ) : (
        loc.caps.map((c, i) => (
          <div className="cap-row" key={i}>
            <span className="cap-types">{c.types.join(' + ')}</span>
            <span className="cap-max">≤ {c.max}</span>
          </div>
        ))
      )}
      <p style={{ marginTop: 12, fontSize: 12, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
        Caps = the maximum of each item category this location can spawn per match. Crate split =
        share of this location's crate caps by type.
      </p>
    </>
  )
}

export function GroupDetail({ group, onClose }) {
  const [memberIdx, setMemberIdx] = useState(0)
  const member = group.members[Math.min(memberIdx, group.members.length - 1)]
  const art = locArt(member.id) ?? group.art
  return (
    <div className="panel" style={{ padding: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 8 }}>
        <div>
          <div className="page-kicker">
            {KIND_GLYPH[group.kind]} {KIND_LABEL[group.kind]}
          </div>
          <h2 style={{ fontFamily: 'var(--font-head)', textTransform: 'uppercase', letterSpacing: '.06em', fontSize: 22, color: 'var(--sand-bright)', lineHeight: 1.1 }}>
            {group.displayName}
          </h2>
          {!group.nameConfirmed && (
            <span className="badge rust" title="This is the internal file name. If you know the real in-game name, note it so we can update the site.">
              ⚙ internal name — confirm in-game
            </span>
          )}
        </div>
        {onClose && (
          <button className="chip" onClick={onClose} style={{ padding: '3px 10px' }}>
            ✕
          </button>
        )}
      </div>

      {art && (
        <div className="loc-art">
          <img src={art} alt="" loading="lazy" />
        </div>
      )}

      {group.members.length > 1 && (
        <div className="src-picker-row" style={{ margin: '12px 0 2px' }}>
          <span className="src-picker-label">
            {group.variantType === 'loot' ? 'loot focus' : 'variant'}
          </span>
          {group.members.map((m, i) => (
            <button
              key={m.id}
              className={'chip' + (i === memberIdx ? ' on' : '')}
              onClick={() => setMemberIdx(i)}
              style={{ padding: '4px 10px', fontSize: 11 }}
            >
              {m.variantLabel ?? 'base'}
            </button>
          ))}
        </div>
      )}
      {group.variantType === 'loot' && group.members.length > 1 && (
        <p style={{ marginTop: 6, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
          Same physical place — the match rolls which loot focus it gets.
        </p>
      )}

      <MemberBody loc={member} />
    </div>
  )
}
