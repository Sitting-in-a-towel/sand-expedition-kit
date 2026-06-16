import { useMemo, useState } from 'react'
import { asset } from '../lib/data.js'
import tree from '../data/research_tree.json'

const NODES = tree.nodes
const BY_ID = Object.fromEntries(NODES.map((n) => [n.id, n]))
const VB = tree.viewBox

// adjacency
const PREDS = new Map()
const SUCC = new Map()
for (const [a, b] of tree.edges) {
  if (!SUCC.has(a)) SUCC.set(a, [])
  if (!PREDS.has(b)) PREDS.set(b, [])
  SUCC.get(a).push(b)
  PREDS.get(b).push(a)
}

const fmt = (n) => (n == null ? '—' : n.toLocaleString('en-US'))

// full ancestor set (everything you must research first) + the node itself
function pathToRoot(id) {
  const seen = new Set([id])
  const stack = [id]
  while (stack.length) {
    const cur = stack.pop()
    for (const p of PREDS.get(cur) ?? []) if (!seen.has(p)) { seen.add(p); stack.push(p) }
  }
  return seen
}

const ZOOMS = [0.4, 0.55, 0.7, 0.9]

export default function TechTree() {
  const [q, setQ] = useState('')
  const [fac, setFac] = useState('all')
  const [sel, setSel] = useState(null)
  const [z, setZ] = useState(0.55)

  const query = q.trim().toLowerCase()
  const matches = useMemo(() => {
    if (!query) return null
    return new Set(NODES.filter((n) => n.name.toLowerCase().includes(query)).map((n) => n.id))
  }, [query])

  const path = useMemo(() => (sel == null ? null : pathToRoot(sel)), [sel])

  const totalCost = useMemo(() => {
    if (!path) return 0
    let t = 0
    for (const id of path) t += BY_ID[id].cost ?? 0
    return t
  }, [path])

  const selNode = sel == null ? null : BY_ID[sel]
  const facActive = (n) => fac === 'all' || n.faction === fac

  // edges: highlighted when both ends are on the selected path
  const edgePaths = useMemo(() => {
    return tree.edges.map(([a, b], i) => {
      const s = BY_ID[a], t = BY_ID[b]
      const sx = s.x + s.w, sy = s.y + s.h / 2
      const tx = t.x, ty = t.y + t.h / 2
      const midx = sx + Math.max(14, (tx - sx) / 2)
      const d = `M ${sx} ${sy} H ${midx} V ${ty} H ${tx}`
      const on = path && path.has(a) && path.has(b)
      return { key: i, d, on, dim: !!path && !on }
    })
  }, [path])

  return (
    <>
      <div className="page-head">
        <div className="page-kicker">Research &amp; unlocks</div>
        <div className="page-title">Tech Tree</div>
        <p className="page-sub">
          The full Trampler research tree — {NODES.length} techs with real{' '}
          <strong>costs and prerequisite links</strong>. Click any tech to light up the full path
          you'd need to research to reach it, with the running total.
        </p>
      </div>

      <div className="panel warn-banner" style={{ borderColor: 'var(--line-strong)', background: 'rgba(146,196,255,0.05)' }}>
        <span className="warn-icon" style={{ color: 'var(--blueprint-accent)' }}>ⓘ</span>
        <div>
          Costs and prerequisite edges are served per-account by the game's master server
          (<code>GetResearchTree</code>) and aren't in the static files. This tree is reconstructed
          from the community wiki{' '}
          <a href="https://sand-help.com/tech" target="_blank" rel="noreferrer" style={{ color: 'var(--sand)' }}>sand-help.com</a>{' '}
          — credit to them. We'll swap in our own capture after launch.
        </div>
      </div>

      <div className="controls sticky-controls">
        <input className="search" placeholder="Search techs…" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className={'chip' + (fac === 'all' ? ' on' : '')} onClick={() => setFac('all')}>All factions</button>
        {tree.factions.map((f) => (
          <button
            key={f.name}
            className={'chip' + (fac === f.name ? ' on' : '')}
            onClick={() => setFac(fac === f.name ? 'all' : f.name)}
            style={fac === f.name ? { borderColor: f.color, color: f.color } : { color: f.color }}
          >
            {f.name}
          </button>
        ))}
        <span className="tt-zoom">
          <button className="chip" onClick={() => setZ((v) => ZOOMS[Math.max(0, ZOOMS.indexOf(v) - 1)] ?? v)}>−</button>
          <span className="tt-zoom-val">{Math.round(z * 100)}%</span>
          <button className="chip" onClick={() => setZ((v) => ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(v) + 1)] ?? v)}>+</button>
        </span>
      </div>

      <div className="tech-layout">
        <div className="tt-viewport">
          <div className="tt-board" style={{ width: VB.w * z, height: VB.h * z }}>
            <div className="tt-scale" style={{ width: VB.w, height: VB.h, transform: `scale(${z})` }}>
              <svg className="tt-wires" width={VB.w} height={VB.h} aria-hidden="true">
                {edgePaths.map((e) => (
                  <path key={e.key} d={e.d} className={'tt-wire' + (e.on ? ' on' : '') + (e.dim ? ' dim' : '')} />
                ))}
              </svg>

              {NODES.map((n) => {
                const dimmed =
                  (matches && !matches.has(n.id)) ||
                  !facActive(n) ||
                  (path && !path.has(n.id))
                const onPath = path && path.has(n.id)
                return (
                  <button
                    key={n.id}
                    className={
                      'ttn' +
                      (sel === n.id ? ' sel' : '') +
                      (onPath ? ' onpath' : '') +
                      (dimmed ? ' dim' : '') +
                      (n.root ? ' root' : '')
                    }
                    style={{ left: n.x, top: n.y, width: n.w, height: n.h, '--fac': n.color }}
                    onClick={() => setSel(sel === n.id ? null : n.id)}
                    title={`${n.name} — ${fmt(n.cost)}`}
                  >
                    <span className="ttn-rail" />
                    <span className="ttn-glyph">
                      {n.thumb ? <img src={asset(n.thumb)} alt="" loading="lazy" /> : <span className="ttn-ghost">◈</span>}
                    </span>
                    <span className="ttn-body">
                      <span className="ttn-name">{n.name}</span>
                      <span className="ttn-cost"><i className="ttn-scrap" />{fmt(n.cost)}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <aside className="loc-drawer">
          {selNode ? (
            <div className="panel" style={{ padding: 18 }}>
              <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                {selNode.thumb ? (
                  <img src={asset(selNode.thumb)} alt="" style={{ width: 64, height: 64, objectFit: 'contain' }} />
                ) : (
                  <div className="item-icon ghost" style={{ width: 64, height: 64 }}>◈</div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h2 style={{ fontFamily: 'var(--font-head)', textTransform: 'uppercase', letterSpacing: '.05em', fontSize: 19, color: 'var(--sand-bright)', lineHeight: 1.1 }}>
                    {selNode.name}
                  </h2>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                    <span className="badge" style={{ borderColor: selNode.color + '88', color: selNode.color }}>{selNode.faction}</span>
                    {selNode.root && <span className="badge sand">root tech</span>}
                  </div>
                </div>
                <button className="chip" onClick={() => setSel(null)} style={{ padding: '3px 10px' }}>✕</button>
              </div>

              <div className="tech-drawer-rows">
                <div className="tech-drawer-row">
                  <span className="k">Cost</span>
                  <span className="v"><i className="ttn-scrap" />{fmt(selNode.cost)}</span>
                </div>
                <div className="tech-drawer-row">
                  <span className="k">Total w/ path</span>
                  <span className="v" style={{ color: 'var(--sand)' }}><i className="ttn-scrap" />{fmt(totalCost)} <span className="faint">({path.size} techs)</span></span>
                </div>
                <div className="tech-drawer-row">
                  <span className="k">Requires</span>
                  <span className="v">
                    {(PREDS.get(sel) ?? []).length
                      ? (PREDS.get(sel)).map((p) => <span key={p} className="chainlink" onClick={() => setSel(p)}>{BY_ID[p].name}</span>)
                      : <span className="faint">— none (root tech) —</span>}
                  </span>
                </div>
                <div className="tech-drawer-row">
                  <span className="k">Unlocks</span>
                  <span className="v">
                    {(SUCC.get(sel) ?? []).length
                      ? (SUCC.get(sel)).map((s) => <span key={s} className="chainlink" onClick={() => setSel(s)}>{BY_ID[s].name}</span>)
                      : <span className="faint">— tree leaf —</span>}
                  </span>
                </div>
              </div>

              <p style={{ marginTop: 12, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
                "Total w/ path" sums this tech and every prerequisite back to a root — the full
                research spend to unlock it. Highlighted on the board.
              </p>
            </div>
          ) : (
            <div className="empty-note">
              SELECT A TECH
              <br />
              <span style={{ opacity: 0.6 }}>— its prerequisite path &amp; total cost light up here —</span>
            </div>
          )}
        </aside>
      </div>

      <div className="footnote">
        {NODES.length} techs · {tree.edges.length} prerequisite links · {tree.factions.length} factions ·
        costs + edges via sand-help.com (community), pending our own post-launch capture.
      </div>
    </>
  )
}
