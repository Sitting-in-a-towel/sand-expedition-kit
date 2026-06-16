import { useMemo, useState } from 'react'
import {
  recipes, recipesByOutput, itemById, itemIcon, itemName,
  whereDrops, locations, KIND_LABEL, KIND_GLYPH, RARITY_COLOR,
} from '../lib/data.js'

const benchKey = (r) => `${r.workbench} T${r.tier}`

// top container sources for a non-craftable ingredient (mode differences are minor for materials)
function dropHint(itemId) {
  const groups = [...new Set(whereDrops(itemId, 'voyage').map((d) => d.group))]
  if (groups.length === 0) return null
  return groups.slice(0, 2).join(', ') + (groups.length > 2 ? ` +${groups.length - 2} more` : '')
}

// recursive raw-material rollup (cycle-guarded); crafts are rounded up to whole batches
function rawTotals(itemId) {
  const agg = new Map()
  const walk = (id, qty, seen) => {
    const rIdx = (recipesByOutput[id] ?? [])[0]
    if (rIdx == null || seen.has(id)) {
      agg.set(id, (agg.get(id) ?? 0) + qty)
      return
    }
    const r = recipes[rIdx]
    const outAmt = r.outputs.find((o) => o.item === id)?.amount ?? 1
    const crafts = Math.ceil(qty / outAmt)
    for (const inp of r.inputs) walk(inp.item, inp.amount * crafts, new Set([...seen, id]))
  }
  const rIdx = (recipesByOutput[itemId] ?? [])[0]
  if (rIdx == null) return []
  for (const inp of recipes[rIdx].inputs) walk(inp.item, inp.amount, new Set([itemId]))
  return [...agg.entries()].sort((a, b) => b[1] - a[1])
}

function IngRow({ item, amount }) {
  const icon = itemIcon(item)
  return (
    <div className="item-row" style={{ padding: '3px 0', flex: 1, minWidth: 0 }}>
      {icon ? <img className="item-icon" src={icon} alt="" loading="lazy" /> : <div className="item-icon ghost">?</div>}
      <span className="item-name" title={item}>{itemName(item)}</span>
      <span className="item-count">×{amount}</span>
    </div>
  )
}

// one ingredient line: craftable → expandable sub-recipe, else "found in" hint
function IngTree({ item, amount, depth = 0 }) {
  const rIdx = (recipesByOutput[item] ?? [])[0]
  if (rIdx == null || depth >= 3) {
    const hint = dropHint(item)
    return (
      <div className="ing-line">
        <IngRow item={item} amount={amount} />
        {hint && <div className="ing-hint">found in: {hint}</div>}
      </div>
    )
  }
  const r = recipes[rIdx]
  const outAmt = r.outputs.find((o) => o.item === item)?.amount ?? 1
  const crafts = Math.ceil(amount / outAmt)
  return (
    <details className="ing-branch">
      <summary>
        <IngRow item={item} amount={amount} />
        <span className="badge teal ing-craft-badge">craftable ▾</span>
      </summary>
      <div className="ing-kids">
        <div className="ing-kids-head">
          ⚒ {r.workbench} T{r.tier} · {crafts > 1 ? `${crafts} crafts` : '1 craft'} ({r.seconds * crafts}s)
        </div>
        {r.inputs.map((x, i) => (
          <IngTree key={i} item={x.item} amount={x.amount * crafts} depth={depth + 1} />
        ))}
      </div>
    </details>
  )
}

function ProductDetail({ itemId, onClose }) {
  const item = itemById[itemId] ?? { id: itemId, name: itemName(itemId) }
  const rs = (recipesByOutput[itemId] ?? []).map((i) => recipes[i])
  const raw = rawTotals(itemId)
  const hasCraftableInput = rs.some((r) => r.inputs.some((x) => recipesByOutput[x.item]))
  return (
    <div className="panel" style={{ padding: 18 }}>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
        {itemIcon(itemId) ? (
          <img src={itemIcon(itemId)} alt="" style={{ width: 56, height: 56, objectFit: 'contain' }} />
        ) : (
          <div className="item-icon ghost" style={{ width: 56, height: 56 }}>?</div>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ fontFamily: 'var(--font-head)', textTransform: 'uppercase', letterSpacing: '.05em', fontSize: 20, color: 'var(--sand-bright)', lineHeight: 1.1 }}>
            {item.name}
          </h2>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            {item.rarity && (
              <span className="badge" style={{ borderColor: RARITY_COLOR[item.rarity], color: RARITY_COLOR[item.rarity] }}>
                {item.rarity.toLowerCase()}
              </span>
            )}
            {item.pawnValue && <span className="badge sand">pawn ≈ {item.pawnValue} crowns</span>}
          </div>
        </div>
        <button className="chip" onClick={onClose} style={{ padding: '3px 10px' }}>✕</button>
      </div>

      {rs.map((r, i) => {
        const outAmt = r.outputs.find((o) => o.item === itemId)?.amount ?? 1
        return (
          <div key={i}>
            <div className="section-label" style={{ margin: '16px 0 8px' }}>
              ⚒ {r.workbench} bench T{r.tier} · {r.seconds}s{outAmt > 1 ? ` · makes ×${outAmt}` : ''}
            </div>
            {r.inputs.map((x, j) => (
              <IngTree key={j} item={x.item} amount={x.amount} />
            ))}
          </div>
        )
      })}

      {hasCraftableInput && raw.length > 0 && (
        <>
          <div className="section-label" style={{ margin: '16px 0 8px' }}>From raw materials</div>
          {raw.map(([id, qty]) => {
            const hint = dropHint(id)
            return (
              <div className="ing-line" key={id}>
                <IngRow item={id} amount={qty} />
                {hint && <div className="ing-hint">found in: {hint}</div>}
              </div>
            )
          })}
          <p style={{ marginTop: 6, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
            Totals assume you craft the intermediate parts yourself (whole batches, rounded up).
          </p>
        </>
      )}
    </div>
  )
}

export default function Crafting() {
  const [bench, setBench] = useState('all')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)

  // product-first index: one entry per craftable OUTPUT item, grouped by bench
  const benches = useMemo(() => {
    const map = new Map()
    recipes.forEach((r) => {
      const k = benchKey(r)
      if (!map.has(k)) map.set(k, [])
      for (const o of r.outputs) {
        if (!map.get(k).some((p) => p.id === o.item)) map.get(k).push({ id: o.item, amount: o.amount })
      }
    })
    return [...map.entries()]
  }, [])

  const q = query.trim().toLowerCase()
  const show = benches
    .filter(([k]) => bench === 'all' || k === bench)
    .map(([k, ps]) => [k, ps.filter((p) => !q || itemName(p.id).toLowerCase().includes(q))])
    .filter(([, ps]) => ps.length > 0)

  return (
    <>
      <div className="page-head">
        <div className="page-kicker">Workshop manual</div>
        <div className="page-title">Crafting</div>
        <p className="page-sub">
          Everything you can <strong>make</strong>, straight from the game files — pick a product
          to see what it costs, where to craft it, and where the ingredients come from.
        </p>
      </div>

      <details className="panel craft-where" style={{ padding: '12px 16px', marginBottom: 20 }}>
        <summary className="section-label" style={{ margin: 0 }}>Where do I craft these? ▾</summary>
        <p style={{ fontSize: 13.5, color: 'var(--ink-dim)', maxWidth: '90ch', marginTop: 10 }}>
          Recipes belong to a <strong style={{ color: 'var(--sand)' }}>workbench type + tier</strong>, not to a
          specific machine — every <em>Armament Workbench T1</em> in the world offers the same
          Armament T1 list below, wherever you find it. <strong style={{ color: 'var(--sand)' }}>Utility benches</strong>{' '}
          cover materials, clothing and consumables; <strong style={{ color: 'var(--sand)' }}>Armament benches</strong>{' '}
          cover ammo and weapons, with T2 unlocking the higher-grade recipes. You can also bolt a{' '}
          <em>Crafting compartment</em> onto your own Trampler (see Blueprints).
        </p>
        <div className="section-label" style={{ margin: '14px 0 8px' }}>
          Locations with crafting stations (from their prefabs)
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
          {locations
            .filter((l) => l.contents?.benches > 0)
            .sort((a, b) => b.contents.benches - a.contents.benches)
            .map((l) => (
              <span key={l.id} className="badge teal" title={`${KIND_LABEL[l.kind]} — ${l.contents.benches} station node(s)`}>
                {KIND_GLYPH[l.kind]} {l.name} ×{l.contents.benches}
              </span>
            ))}
        </div>
        <p style={{ marginTop: 8, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
          Counted from each location's prefab (crafting press / workbench placements). Bench TIER
          per location isn't in the prefab names — verify tier in-game.
        </p>
      </details>

      <div className="controls">
        <input
          className="search"
          placeholder="Search products…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className={'chip' + (bench === 'all' ? ' on' : '')} onClick={() => setBench('all')}>
          All benches
        </button>
        {benches.map(([k]) => (
          <button key={k} className={'chip' + (bench === k ? ' on' : '')} onClick={() => setBench(k)}>
            {k}
          </button>
        ))}
      </div>

      <div className="loot-layout">
        <div>
          {show.map(([k, ps]) => (
            <div key={k}>
              <div className="section-label">
                {k} workbench · {ps.length} products
              </div>
              <div className="gallery stagger" style={{ marginBottom: 18 }}>
                {ps.map((p) => (
                  <div
                    key={p.id}
                    className="gallery-card"
                    onClick={() => setSelected(selected === p.id ? null : p.id)}
                    style={selected === p.id ? { borderColor: 'var(--rust)' } : {}}
                  >
                    {itemIcon(p.id) ? <img src={itemIcon(p.id)} alt="" loading="lazy" /> : <div className="ghost-img">?</div>}
                    <div className="gname">
                      {itemName(p.id)}
                      {p.amount > 1 && <span style={{ color: 'var(--ink-faint)' }}> ×{p.amount}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <aside className="loc-drawer">
          {selected ? (
            <ProductDetail itemId={selected} onClose={() => setSelected(null)} />
          ) : (
            <div className="empty-note">
              SELECT A PRODUCT
              <br />
              <span style={{ opacity: 0.6 }}>— cost, bench & ingredient sources will appear here —</span>
            </div>
          )}
        </aside>
      </div>

      <div className="footnote">{recipes.length} recipes datamined · test/debug recipes excluded.</div>
    </>
  )
}
