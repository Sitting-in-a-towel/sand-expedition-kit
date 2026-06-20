// Builder V2 — identical in-game builder rebuild (owner-mandated milestone).
// Truth source: the game's CompartmentsDatabase (cells/sockets/limits), real meshes.
import { useEffect, useMemo, useRef, useState } from 'react'
import BuilderScene from '../components/BuilderScene.jsx'
import thumbsV2 from '../data/part_thumbs_v2.json'
import { asset } from '../lib/data.js'
import {
  PARTS, PART_BY_ID, GROUP_LIMITS, MEMBER_LIMIT, ESSENTIALS,
  CAT_COLOR, CATEGORY_ORDER, buildOccupancy, validate, manifest,
  encodeShare, decodeShare, editableSockets, placementValidity,
} from '../lib/builderCore.js'
import { decodeWbt, wbtToState } from '../lib/wbtImport.js'
import { submitBuild } from '../lib/galleryApi.js'

const STORE_KEY = 'sand_blueprint_v2'
const chassisList = PARTS.filter((p) => p.category === 'Chassis')
const lockerParts = PARTS.filter((p) => p.category !== 'Chassis' && !p.id.endsWith('_mirror'))

const DEFAULT_STATE = {
  v: 2,
  name: 'UNTITLED RIG',
  chassisId: 'compChassis_Medium4_Metal_4x4',
  placements: [], // {id, partId, x, y, z, rot, conns:{}}  (y = grid level, 1 = on the plate)
}

const LEVEL_LABELS = ['HULL', 'DECK 2', 'DECK 3', 'DECK 4', 'DECK 5', 'DECK 6']

function thumbOf(partId) {
  const t = thumbsV2[partId]
  return t ? asset(t.replace(/^\//, '')) : null
}

export default function BuilderV2() {
  const [state, setState] = useState(() => {
    try {
      const saved = localStorage.getItem(STORE_KEY)
      if (saved) return { ...DEFAULT_STATE, ...JSON.parse(saved) }
    } catch { /* fresh */ }
    return DEFAULT_STATE
  })
  const [level, setLevel] = useState(1)
  const [activePart, setActivePart] = useState(null)
  const [activeRot, setActiveRot] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [openCat, setOpenCat] = useState('Cargo')
  const [q, setQ] = useState('')
  const [notice, setNotice] = useState('')
  const [hoverInfo, setHoverInfo] = useState('')
  const [shareOpen, setShareOpen] = useState(false)
  const [shareText, setShareText] = useState('')
  const [pubOpen, setPubOpen] = useState(false)
  const [pub, setPub] = useState({ name: '', author: '', description: '' })
  const [pubBusy, setPubBusy] = useState(false)
  const idRef = useRef(Date.now() % 1e7)
  const moveBackup = useRef(null)

  useEffect(() => {
    localStorage.setItem(STORE_KEY, JSON.stringify(state))
  }, [state])

  // handoff: "Open in builder" from the Gallery drops a code in localStorage
  useEffect(() => {
    const code = localStorage.getItem('sand_load_code')
    if (code) {
      localStorage.removeItem('sand_load_code')
      try { setState({ ...DEFAULT_STATE, ...decodeShare(code) }) } catch { /* ignore */ }
    }
  }, [])

  const occ = useMemo(() => buildOccupancy(state), [state])
  const man = useMemo(() => manifest(state), [state])
  const validityMap = useMemo(() => placementValidity(state), [state]) // plId -> {blocked,reasons}
  const invalidIds = Object.keys(validityMap)

  // ---------- actions ----------
  function flash(msg) {
    setNotice(msg)
    window.clearTimeout(flash._t)
    flash._t = window.setTimeout(() => setNotice(''), 2400)
  }

  function place(gx, gz, blocked) {
    if (!activePart) return
    if (blocked) {
      flash('space already taken') // only a solid-on-solid overlap blocks placing
      return
    }
    const id = `p${idRef.current++}`
    setState((s) => ({
      ...s,
      placements: [...s.placements, { id, partId: activePart, x: gx, y: level, z: gz, rot: activeRot, conns: {} }],
    }))
    setSelectedId(id)
    if (!keysDown.current.has('Shift')) setActivePart(null) // auto-deselect (round-3 ask); Shift = keep placing
  }

  function movePlacement(plId, gx, gz, preview) {
    if (preview) {
      setState((s) => {
        const pl = s.placements.find((p) => p.id === plId)
        if (!pl) return s
        if (!moveBackup.current || moveBackup.current.id !== plId) {
          moveBackup.current = { id: plId, x: pl.x, z: pl.z }
        }
        if (pl.x === gx && pl.z === gz) return s
        return {
          ...s,
          placements: s.placements.map((p) => (p.id === plId ? { ...p, x: gx, z: gz } : p)),
        }
      })
    } else {
      // commit: validate final spot, revert if invalid
      setState((s) => {
        const pl = s.placements.find((p) => p.id === plId)
        if (!pl) return s
        const others = { ...s, placements: s.placements.filter((p) => p.id !== plId) }
        const o = buildOccupancy(others)
        const v = validate(others, o, pl.partId, pl.x, pl.y, pl.z, pl.rot)
        // only snap back on a hard overlap; invalid-but-placeable spots are kept (red)
        if (v.blocked && moveBackup.current?.id === plId) {
          flash(`can't move there — ${v.reason}`)
          const bk = moveBackup.current
          moveBackup.current = null
          return {
            ...s,
            placements: s.placements.map((p) => (p.id === plId ? { ...p, x: bk.x, z: bk.z } : p)),
          }
        }
        moveBackup.current = null
        return s
      })
      setSelectedId(plId)
    }
  }

  function rotate() {
    if (activePart) {
      setActiveRot((r) => (r + 1) % 4)
      return
    }
    if (selectedId) {
      setState((s) => {
        const pl = s.placements.find((p) => p.id === selectedId)
        if (!pl) return s
        const rot = (pl.rot + 1) % 4
        const others = { ...s, placements: s.placements.filter((p) => p.id !== selectedId) }
        const v = validate(others, buildOccupancy(others), pl.partId, pl.x, pl.y, pl.z, rot)
        if (v.blocked) { // rotation only refused if it would overlap a solid cell
          flash(`can't rotate — ${v.reason}`)
          return s
        }
        return { ...s, placements: s.placements.map((p) => (p.id === selectedId ? { ...p, rot } : p)) }
      })
    }
  }

  function mirrorSelected() {
    if (!selectedId) return
    setState((s) => {
      const pl = s.placements.find((p) => p.id === selectedId)
      const part = pl && PART_BY_ID[pl.partId]
      const mirrorId = part?.mirror ?? (PART_BY_ID[`${pl?.partId}_mirror`] ? `${pl.partId}_mirror` : null)
      if (!pl || !mirrorId) {
        flash('no mirrored variant for this part')
        return s
      }
      const others = { ...s, placements: s.placements.filter((p) => p.id !== selectedId) }
      const v = validate(others, buildOccupancy(others), mirrorId, pl.x, pl.y, pl.z, pl.rot)
      if (v.blocked) {
        flash(`mirror doesn't fit — ${v.reason}`)
        return s
      }
      return { ...s, placements: s.placements.map((p) => (p.id === selectedId ? { ...p, partId: mirrorId } : p)) }
    })
  }

  function removeSelected() {
    if (!selectedId) return
    setState((s) => ({ ...s, placements: s.placements.filter((p) => p.id !== selectedId) }))
    setSelectedId(null)
  }

  function toggleSocket(plId, key) {
    setState((s) => ({
      ...s,
      placements: s.placements.map((p) => {
        if (p.id !== plId) return p
        const part = PART_BY_ID[p.partId]
        const sock = part && editableSockets(part, p).find((es) => es.key === key)
        const states = sock?.states?.length ? sock.states : ['DEFAULT', 'DOOR', 'OPEN']
        const cur = p.conns?.[key] ?? 'DEFAULT'
        const next = states[(states.indexOf(cur) + 1) % states.length]
        return { ...p, conns: { ...(p.conns ?? {}), [key]: next } }
      }),
    }))
  }

  // keyboard
  const keysDown = useRef(new Set())
  useEffect(() => {
    function down(e) {
      keysDown.current.add(e.key)
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === ' ' || e.code === 'Space') { e.preventDefault(); rotate() } // Space = rotate
      if (e.key === 'r' || e.key === 'R') setLevel((l) => Math.min(LEVEL_LABELS.length, l + 1)) // R = level up
      if (e.key === 'f' || e.key === 'F') setLevel((l) => Math.max(1, l - 1)) // F = level down
      if (e.key === 'Delete' || e.key === 'Backspace') removeSelected()
      if (e.key === 'Escape') {
        setActivePart(null)
        setSelectedId(null)
      }
      if (e.key === 'm' || e.key === 'M') mirrorSelected()
    }
    function up(e) {
      keysDown.current.delete(e.key)
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  })

  // ---------- locker ----------
  const cats = useMemo(() => {
    const byCat = new Map()
    for (const p of lockerParts) {
      if (q && !p.name.toLowerCase().includes(q.toLowerCase()) && !p.id.toLowerCase().includes(q.toLowerCase())) continue
      if (!byCat.has(p.category)) byCat.set(p.category, [])
      byCat.get(p.category).push(p)
    }
    return [...byCat.entries()].sort(
      (a, b) => (CATEGORY_ORDER.indexOf(a[0]) + 99) - (CATEGORY_ORDER.indexOf(b[0]) + 99) ||
        a[0].localeCompare(b[0]),
    )
  }, [q])

  const essentialsState = ESSENTIALS.map((e) => ({ ...e, ok: man.groups.has(e.group) }))
  const selectedPl = state.placements.find((p) => p.id === selectedId)
  const selectedPart = selectedPl && PART_BY_ID[selectedPl.partId]

  // ---------- share ----------
  function doExport() {
    setShareText(encodeShare(state))
    setShareOpen(true)
  }
  function doImport() {
    try {
      const st = decodeShare(shareText)
      setState({ ...DEFAULT_STATE, ...st })
      setShareOpen(false)
      flash('blueprint imported')
    } catch {
      flash('not a valid SANDBP2 code')
    }
  }
  // publish current build to the community gallery (lands pending moderation)
  async function doPublish() {
    const name = (pub.name || state.name || '').trim()
    if (!name) { flash('give your build a name first'); return }
    setPubBusy(true)
    try {
      await submitBuild({
        name,
        author: pub.author,
        description: pub.description,
        shareCode: encodeShare(state),
        chassisId: state.chassisId,
        partCount: state.placements.length,
      })
      setPubOpen(false)
      setPub({ name: '', author: '', description: '' })
      flash('submitted! it’ll appear in the gallery once approved')
    } catch (e) {
      flash(`publish failed — ${e.message || 'try again'}`)
    } finally {
      setPubBusy(false)
    }
  }

  // import an in-game .wbt save file (decoded fully in-browser, nothing uploaded)
  async function doImportWbt(file) {
    if (!file) return
    try {
      const doc = await decodeWbt(await file.arrayBuffer())
      const { state: st, stats } = wbtToState(doc, PART_BY_ID, () => String(idRef.current++))
      setState({ ...DEFAULT_STATE, ...st })
      setShareOpen(false)
      flash(
        stats.skipped
          ? `imported ${stats.total} parts (${stats.skipped} skipped — old game version)`
          : `imported ${stats.total} parts from ${file.name}`,
      )
    } catch (e) {
      flash(`couldn't read .wbt — ${e.message || 'unsupported file'}`)
    }
  }

  return (
    <div className="bv2">
      {/* ---- locker ---- */}
      <aside className="bv2-locker">
        <div className="bv2-locker-head">
          <div className="bv2-title">PARTS LOCKER</div>
          <input
            className="bv2-search" placeholder="search…" value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div className="bv2-cats">
          {cats.map(([cat, items]) => (
            <div key={cat} className={`bv2-cat ${openCat === cat || q ? 'open' : ''}`}>
              <button
                className="bv2-cat-head"
                style={{ '--cat': CAT_COLOR[cat] ?? '#7f96ad' }}
                onClick={() => setOpenCat(openCat === cat ? null : cat)}
              >
                <span className="bv2-cat-dot" />
                {cat}
                <span className="bv2-cat-n">{items.length}</span>
              </button>
              {(openCat === cat || q) && (
                <div className="bv2-cat-items">
                  {items.map((p) => (
                    <button
                      key={p.id}
                      className={`bv2-part ${activePart === p.id ? 'active' : ''}`}
                      onClick={() => {
                        setActivePart(activePart === p.id ? null : p.id)
                        setActiveRot(0)
                        setSelectedId(null)
                      }}
                      title={p.desc ? `${p.name}\n\n${p.desc}` : p.id}
                    >
                      {thumbOf(p.id)
                        ? <img src={thumbOf(p.id)} alt="" loading="lazy" />
                        : <span className="bv2-ghosticon">▦</span>}
                      <span className="bv2-part-name">{p.name}</span>
                      <span className="bv2-part-meta">
                        {p.bounds[0]}×{p.bounds[2]}{p.bounds[1] > 1 ? `·${p.bounds[1]}h` : ''}
                        {p.mirror ? ' ⇋' : ''}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </aside>

      {/* ---- viewport ---- */}
      <div className="bv2-stage">
        <BuilderScene
          state={state}
          level={level}
          activePart={activePart}
          activeRot={activeRot}
          selectedId={selectedId}
          invalidMap={validityMap}
          onPlace={place}
          onSelect={setSelectedId}
          onMove={movePlacement}
          onHoverInfo={setHoverInfo}
          onSocketToggle={toggleSocket}
        />

        {/* level switcher */}
        <div className="bv2-levels">
          <button onClick={() => setLevel((l) => Math.min(LEVEL_LABELS.length, l + 1))}>▲</button>
          <div className="bv2-level-label">{LEVEL_LABELS[level - 1] ?? `LV ${level}`}</div>
          <button onClick={() => setLevel((l) => Math.max(1, l - 1))}>▼</button>
        </div>

        {/* toolbar */}
        <div className="bv2-toolbar">
          <button onClick={rotate} title="rotate (Space)">⟳ ROTATE</button>
          <button onClick={mirrorSelected} disabled={!selectedPart?.mirror && !PART_BY_ID[`${selectedPl?.partId}_mirror`]} title="mirror (M)">⇋ MIRROR</button>
          <button onClick={removeSelected} disabled={!selectedId} title="remove (Del)">✕ REMOVE</button>
        </div>

        {activePart && (
          <div className="bv2-placing">
            placing <b>{PART_BY_ID[activePart]?.name}</b> on {LEVEL_LABELS[level - 1]} — click to place,
            Space rotate, R/F change deck, hold Shift to keep placing, Esc to cancel
            {hoverInfo && <span className="bv2-placing-err"> · {hoverInfo}</span>}
          </div>
        )}
        {selectedPl && !activePart && (
          <div className="bv2-placing">
            <b>{selectedPart?.name}</b> selected — drag to move, Space rotate, M mirror, Del remove ·
            spheres = convertible sockets (click: wall → door → open)
          </div>
        )}
        {notice && <div className="bv2-notice">{notice}</div>}
      </div>

      {/* ---- manifest ---- */}
      <aside className="bv2-manifest">
        <input
          className="bv2-name"
          value={state.name}
          onChange={(e) => setState((s) => ({ ...s, name: e.target.value.toUpperCase().slice(0, 28) }))}
        />

        <div className="bv2-block">
          <div className="bv2-block-title">CHASSIS</div>
          <select
            value={state.chassisId}
            onChange={(e) => setState((s) => ({ ...s, chassisId: e.target.value, placements: [] }))}
          >
            {chassisList.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label ?? c.name}
              </option>
            ))}
          </select>
          <div className="bv2-hint">changing chassis clears the build</div>
        </div>

        <div className="bv2-block">
          <div className="bv2-block-title">BUILD REQUIREMENTS</div>
          {essentialsState.map((e) => (
            <div key={e.group} className={`bv2-req ${e.ok ? 'ok' : ''}`}>
              <span>{e.ok ? '✓' : '○'}</span> {e.label}
              {GROUP_LIMITS[e.group] ? <em> (max {GROUP_LIMITS[e.group]})</em> : null}
            </div>
          ))}
          <div className={`bv2-req ${man.crew <= MEMBER_LIMIT ? 'ok' : 'bad'}`}>
            <span>{man.crew <= MEMBER_LIMIT ? '✓' : '!'}</span> Crew quarters {man.crew}/{MEMBER_LIMIT}
          </div>
          <div className={`bv2-req ${invalidIds.length ? 'bad' : 'ok'}`}>
            <span>{invalidIds.length ? '⚠' : '✓'}</span>{' '}
            {invalidIds.length
              ? `${invalidIds.length} part${invalidIds.length > 1 ? 's' : ''} ${invalidIds.length > 1 ? 'need' : 'needs'} fixing (shown red)`
              : 'All parts valid'}
          </div>
          <div className="bv2-req dim">
            <span>?</span> Weight — server-side data, not in game files
          </div>
        </div>

        <div className="bv2-block bv2-grow">
          <div className="bv2-block-title">MANIFEST · {man.total} parts</div>
          <div className="bv2-man-list">
            {man.rows.length === 0 && <div className="bv2-hint">click a part in the locker, then click the grid</div>}
            {man.rows.map((r) => (
              <div key={r.part.id} className="bv2-man-row">
                {thumbOf(r.part.id) && <img src={thumbOf(r.part.id)} alt="" />}
                <span className="bv2-man-name" style={{ color: CAT_COLOR[r.part.category] }}>{r.part.name}</span>
                <span className="bv2-man-n">×{r.n}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bv2-block">
          <div className="bv2-share-btns">
            <button onClick={doExport}>SHARE CODE</button>
            <button onClick={() => { setShareText(''); setShareOpen(true) }}>IMPORT</button>
            <button
              className="danger"
              onClick={() => {
                setState((s) => ({ ...DEFAULT_STATE, chassisId: s.chassisId }))
                setSelectedId(null)
              }}
            >
              CLEAR
            </button>
          </div>
          <label className="bv2-wbt-btn">
            ⬆ LOAD IN-GAME SAVE (.wbt)
            <input
              type="file"
              accept=".wbt,.wbtb"
              style={{ display: 'none' }}
              onChange={(e) => { doImportWbt(e.target.files[0]); e.target.value = '' }}
            />
          </label>
          <p className="bv2-wbt-hint">
            From <code>…/AppData/LocalLow/Hologryph/Sand/Data/Walkers/</code>. Read in your
            browser — nothing is uploaded.
          </p>

          <button className="bv2-publish-btn" onClick={() => { setPub((p) => ({ ...p, name: p.name || state.name })); setPubOpen((o) => !o) }}>
            ★ PUBLISH TO GALLERY
          </button>
          {pubOpen && (
            <div className="bv2-share" style={{ marginTop: 8 }}>
              <input className="bv2-search" placeholder="build name" value={pub.name}
                onChange={(e) => setPub({ ...pub, name: e.target.value })} />
              <input className="bv2-search" placeholder="your name (optional)" value={pub.author}
                onChange={(e) => setPub({ ...pub, author: e.target.value })} style={{ marginTop: 6 }} />
              <textarea className="bv2-share-text" placeholder="description (optional)" value={pub.description}
                onChange={(e) => setPub({ ...pub, description: e.target.value })} style={{ marginTop: 6 }} rows={3} />
              <div className="bv2-share-btns" style={{ marginTop: 6 }}>
                <button onClick={doPublish} disabled={pubBusy}>{pubBusy ? 'SUBMITTING…' : 'SUBMIT'}</button>
                <button onClick={() => setPubOpen(false)}>CANCEL</button>
              </div>
              <p className="bv2-wbt-hint">Submissions are reviewed before appearing in the gallery.</p>
            </div>
          )}
          {shareOpen && (
            <div className="bv2-share">
              <textarea
                value={shareText}
                onChange={(e) => setShareText(e.target.value)}
                placeholder="SANDBP2.…"
                rows={4}
              />
              <div className="bv2-share-btns">
                <button onClick={() => { navigator.clipboard?.writeText(shareText); flash('copied') }}>COPY</button>
                <button onClick={doImport}>LOAD</button>
                <button onClick={() => setShareOpen(false)}>CLOSE</button>
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
