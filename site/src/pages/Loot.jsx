import { useMemo, useState } from 'react'
import {
  items, lootSources, recipes, recipesByOutput, recipesByInput,
  itemName, itemIcon, fmtCount, whereDrops, RARITY_COLOR, asset, statsFor,
} from '../lib/data.js'
import containerArt from '../data/container_art.json'

function RarityBadge({ rarity }) {
  if (!rarity) return null
  const c = RARITY_COLOR[rarity] ?? '#9aa58f'
  return (
    <span className="badge" style={{ borderColor: c, color: c }}>
      {rarity.toLowerCase()}
    </span>
  )
}

function likelihood(setsWith, setsTotal) {
  const r = setsWith / setsTotal
  if (r >= 0.99) return { label: 'always rolled', cls: 'lk-high' }
  if (r >= 0.5) return { label: `${setsWith} of ${setsTotal} sets`, cls: 'lk-mid' }
  return { label: `${setsWith} of ${setsTotal} sets`, cls: 'lk-low' }
}

// ---------------- gun / ammo / armor stats ----------------
function fmtRange(r) {
  if (!r) return null
  if (!r.falloff) return `${r.max} m · no damage falloff`
  return `${r.full} m full damage → ${Math.round(r.minMult * 100)}% at ${r.max} m`
}

function pairRow(label, p, unit = '') {
  if (!p || (p.hip == null && p.scope == null)) return null
  const fmt = (n) => (n == null ? '—' : `${n}${unit}`)
  if (p.hip === p.scope) return [label, fmt(p.hip)]
  return [label, `hip ${fmt(p.hip)} · aimed ${fmt(p.scope)}`]
}

function StatRow({ label, value }) {
  return (
    <div className="cap-row">
      <span className="cap-types">{label}</span>
      <span className="cap-max">{value}</span>
    </div>
  )
}

function ItemStats({ item }) {
  const s = statsFor(item.id)
  if (!s) return null
  const rows = []
  if (s.kind === 'weapon') {
    if (s.reloadSeconds != null) rows.push(['Reload', `${s.reloadSeconds} s`])
    const r = fmtRange(s.range)
    if (r) rows.push(['Range', r])
    const rc = pairRow('Recoil', s.recoil)
    if (rc) rows.push(rc)
    const sp = pairRow('Spread', s.spread, '°')
    if (sp) rows.push(sp)
  } else if (s.kind === 'ammo') {
    if (s.damagePhysical != null) rows.push(['Damage', `${s.damagePhysical}`])
    const r = fmtRange(s.range)
    if (r) rows.push(['Range', r])
    rows.push(['Armor piercing', s.penetrates ? 'Yes' : 'No'])
    if (s.stack) rows.push(['Stack S / M / L', s.stack.filter((x) => x != null).join(' / ')])
  } else if (s.kind === 'armor') {
    if (s.armorRating != null) rows.push(['Armor rating', `${s.armorRating}`])
    if (s.regen) rows.push(['Regen', `${s.regen.speed}/s after ${s.regen.delay} s`])
    if (s.durability != null) rows.push(['Durability', `${s.durability}`])
  }
  if (!rows.length) return null
  return (
    <>
      <div className="section-label" style={{ margin: '16px 0 8px' }}>Stats</div>
      {rows.map(([l, v]) => <StatRow key={l} label={l} value={v} />)}
    </>
  )
}

// ---------------- item detail (side panel) ----------------
function ItemDetail({ item, mode, onClose }) {
  const drops = whereDrops(item.id, mode)
  const crafts = (recipesByOutput[item.id] ?? []).map((i) => recipes[i])
  const usedIn = (recipesByInput[item.id] ?? []).map((i) => recipes[i])
  // tier matrix: rows = group, cols = tiers present
  const tiers = [1, 2, 3]
  const byGroup = new Map()
  for (const d of drops) {
    if (!byGroup.has(d.group)) byGroup.set(d.group, {})
    byGroup.get(d.group)[d.tier ?? 0] = d
  }
  return (
    <div className="panel" style={{ padding: 18 }}>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
        {itemIcon(item.id) ? (
          <img src={itemIcon(item.id)} alt="" style={{ width: 56, height: 56, objectFit: 'contain' }} />
        ) : (
          <div className="item-icon ghost" style={{ width: 56, height: 56 }}>?</div>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ fontFamily: 'var(--font-head)', textTransform: 'uppercase', letterSpacing: '.05em', fontSize: 20, color: 'var(--sand-bright)', lineHeight: 1.1 }}>
            {item.name}
          </h2>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            <RarityBadge rarity={item.rarity} />
            {item.type && <span className="badge">{item.type.replaceAll('_', ' ').toLowerCase()}</span>}
            {item.pawnValue && <span className="badge sand">pawn ≈ {item.pawnValue} crowns</span>}
          </div>
        </div>
        <button className="chip" onClick={onClose} style={{ padding: '3px 10px' }}>✕</button>
      </div>

      {item.desc && <p className="item-desc">{item.desc}</p>}
      {item.short && <pre className="item-stats">{item.short}</pre>}

      <ItemStats item={item} />

      <div className="section-label" style={{ margin: '16px 0 8px' }}>Where it drops</div>
      {byGroup.size === 0 ? (
        <div className="empty-note" style={{ padding: 14 }}>
          Not in any container table — crafted, bought or special.
        </div>
      ) : (
        <table className="drop-matrix">
          <thead>
            <tr>
              <th>Container</th>
              {tiers.map((t) => <th key={t}>T{t} zone</th>)}
            </tr>
          </thead>
          <tbody>
            {[...byGroup.entries()].map(([group, row]) => (
              <tr key={group}>
                <td>
                  {group}
                  {row[Object.keys(row)[0]]?.effort && (
                    <span className="dm-effort"> · {row[Object.keys(row)[0]].effort} grade</span>
                  )}
                </td>
                {tiers.map((t) => {
                  const d = row[t] ?? (row[0] && t === 1 ? row[0] : null)
                  if (!d) return <td key={t} className="dm-none">—</td>
                  const lk = likelihood(d.setsWith, d.setsTotal)
                  return (
                    <td key={t} className={lk.cls}>
                      <div className="dm-count">×{fmtCount(d.min, d.max)}</div>
                      <div className="dm-sets">{lk.label}</div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p style={{ marginTop: 8, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
        Each container rolls ONE of its sets — "2 of 3 sets" ≈ 2-in-3 chance the rolled set
        contains this item. Exact set weights are a future mining pass.
      </p>

      {(crafts.length > 0 || usedIn.length > 0) && (
        <>
          <div className="section-label" style={{ margin: '14px 0 8px' }}>Crafting</div>
          {crafts.map((r, i) => (
            <div className="cap-row" key={'c' + i}>
              <span style={{ fontSize: 12.5 }}>
                ⚒ {r.workbench} bench T{r.tier}: {r.inputs.map((x) => `${x.amount}× ${itemName(x.item)}`).join(' + ')}
              </span>
              <span className="cap-max">{r.seconds}s</span>
            </div>
          ))}
          {usedIn.map((r, i) => (
            <div className="cap-row" key={'u' + i}>
              <span style={{ fontSize: 12.5 }}>
                ▸ ingredient for {r.outputs.map((x) => `${x.amount}× ${itemName(x.item)}`).join(', ')}
              </span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

// ---------------- containers: picker grid → drill-down detail ----------------
function pctColor(p) {
  if (p >= 99) return 'var(--teal)'
  if (p >= 50) return '#8db971'
  if (p >= 20) return 'var(--sand)'
  return 'var(--rust)'
}

// representative game icon per container (no container art in the icon dump)
const SRC_ICON = {
  'Weapons Crate': 'icons/icon_rifle.png',
  'Resource Crate': 'icons/icon_metalParts.png',
  'Food Crate': 'icons/icon_food.png',
  'Medical Cabinet': 'icons/icon_medkit.png',
  'Safe': 'icons/icon_item_smallValuables.png',
  'Shell Box': 'icons/icon_ammo_smallCannon.png',
  'Buried Treasure': 'icons/icon_item_treasureShovel.png',
  'Ironclad Loot Box': 'icons/icon_item_alloySteel.png',
  'Mob Drops': 'icons/icon_weirdCoral.png',
  'Aurogen Crystal': 'icons/icon_artefact_crystal.png',
  'Naval Mine': 'icons/icon_highGradeGunpowder.png',
  'Militia Box': 'icons/icon_item_game_keyLockedBox.png',
}

function sourceDiffers(src) {
  return Object.values(src.cells).some(
    (c) => JSON.stringify(c.voyage ?? []) !== JSON.stringify(c.storm ?? []),
  )
}

function sourceItemCount(src, mode) {
  const set = new Set()
  for (const c of Object.values(src.cells)) for (const e of c[mode] ?? []) set.add(e.item)
  for (const m of src.mandatory ?? []) set.add(m.item)
  return set.size
}

const LOOT_GRADES = ['low', 'mid', 'high']

function srcImage(name) {
  // real game model thumbnail if we rendered one, else the stand-in item icon
  return containerArt[name] ? asset(containerArt[name]) : (SRC_ICON[name] ? asset(SRC_ICON[name]) : null)
}

function SourceTile({ src, mode, onOpen }) {
  const count = sourceItemCount(src, mode)
  const img = srcImage(src.name)
  const isModel = !!containerArt[src.name]
  return (
    <button className="src-tile" onClick={onOpen}>
      {img ? <img className={isModel ? 'src-model' : ''} src={img} alt="" loading="lazy" /> : <div className="ghost-img">▦</div>}
      <div className="src-name">{src.name}</div>
      <div className="src-meta">
        {count} possible items
        {src.tiers.length > 0 && ` · ${src.tiers.length === 3 ? '3 zones' : `${src.tiers.length} tiers`}`}
      </div>
      <div className="src-badges">
        {(src.mandatory?.length ?? 0) > 0 && <span className="badge teal">guaranteed loot</span>}
        {sourceDiffers(src) && <span className="badge sand">voyage ≠ storm</span>}
        {src.approx && <span className="badge rust">approx odds</span>}
      </div>
    </button>
  )
}

function SourceDetail({ src, mode, query, onBack }) {
  const zoneTiers = src.tiers.length === 3 // T1/T2/T3 = map ZONE tier, not a container variant
  const [tier, setTier] = useState(src.tiers[0] ?? null)
  const [effort, setEffort] = useState(src.efforts.includes('mid') ? 'mid' : src.efforts[0] ?? null)
  const graded = src.efforts.length > 0 && src.efforts.every((e) => LOOT_GRADES.includes(e))

  const cell = src.cells[`${tier ?? 0}|${effort ?? ''}`]
  let rows = (cell?.[mode] ?? []).slice().sort((a, b) => b.pct - a.pct)
  if (query) rows = rows.filter((r) => itemName(r.item).toLowerCase().includes(query))

  return (
    <div className="panel sheet" style={{ maxWidth: 880, margin: '0 auto' }}>
      <div className="sheet-head">
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', minWidth: 0 }}>
          <button className="chip" onClick={onBack} style={{ padding: '4px 12px' }}>◀ containers</button>
          {srcImage(src.name) && <img className="src-detail-model" src={srcImage(src.name)} alt="" />}
          <h3>{src.name}</h3>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {sourceDiffers(src) && <span className="badge sand">voyage ≠ storm</span>}
          {src.approx && <span className="badge rust" title="No spawn weights for mobs in files — sets weighted equally">approx odds</span>}
          {src.unknownSets > 0 && <span className="badge red">some values unknown</span>}
        </div>
      </div>

      {(src.tiers.length > 0 || src.efforts.length > 0) && (
        <div className="src-pickers">
          {src.tiers.length > 0 && (
            <div className="src-picker-row">
              <span className="src-picker-label">{zoneTiers ? 'map zone' : 'tier'}</span>
              {src.tiers.map((t) => (
                <button key={t} className={'chip' + (tier === t ? ' on' : '')} onClick={() => setTier(t)}>
                  {zoneTiers ? `T${t} zone` : `Tier ${t}`}
                </button>
              ))}
            </div>
          )}
          {src.efforts.length > 0 && (
            <div className="src-picker-row">
              <span className="src-picker-label">{graded ? 'loot grade' : 'source'}</span>
              {src.efforts.map((e) => (
                <button key={e} className={'chip' + (effort === e ? ' on' : '')} onClick={() => setEffort(e)}>
                  {e}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {graded && (
        <p style={{ margin: '2px 0 4px', fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
          Same crate, three loot grades in the files — higher grade = more &amp; better-tier loot.
          (The game's internal “effort” variants; the exact in-game trigger isn't in the data.)
        </p>
      )}

      {src.mandatory.length > 0 && (
        <div className="sheet-mandatory">
          GUARANTEED:{' '}
          {src.mandatory.map((m, i) => (
            <span key={i}>
              {itemName(m.item)} ×{fmtCount(m.min, m.max)}
              {i < src.mandatory.length - 1 ? ' · ' : ''}
            </span>
          ))}
        </div>
      )}

      {rows.length === 0 ? (
        <div className="empty-note" style={{ padding: 18, marginTop: 10 }}>
          {query ? 'No items match your search in this selection.' : 'No data for this selection.'}
        </div>
      ) : (
        <table className="sheet-table">
          <thead>
            <tr>
              <th style={{ width: '55%' }}>Item</th>
              <th>Drop chance</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const icon = itemIcon(r.item)
              return (
                <tr key={r.item}>
                  <td>
                    <div className="sheet-item">
                      {icon ? <img src={icon} alt="" loading="lazy" /> : <span className="sheet-noicon">?</span>}
                      <span title={r.item}>{itemName(r.item)}</span>
                    </div>
                  </td>
                  <td>
                    <span className="sheet-pct" style={{ color: pctColor(r.pct) }}>
                      {r.pct >= 99.9 ? '100%' : `${r.pct}%`}
                    </span>
                  </td>
                  <td>
                    <span className="sheet-count">×{fmtCount(r.min, r.max)}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      {zoneTiers && (
        <p style={{ marginTop: 10, fontSize: 11.5, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
          T1/T2/T3 = the map ZONE the container sits in (deeper zones, better tables) — not a
          variant of the container itself.
        </p>
      )}
    </div>
  )
}

// ---------------- page ----------------
export default function Loot() {
  const [view, setView] = useState('containers')
  const [mode, setMode] = useState('voyage')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)
  const [srcSel, setSrcSel] = useState(null)

  const q = query.trim().toLowerCase()
  const qFlat = q.replace(/\s+/g, '')
  const filteredItems = useMemo(
    () =>
      items.filter(
        (i) =>
          !q ||
          i.name.toLowerCase().includes(q) ||
          i.id.toLowerCase().replace(/[_\s]+/g, '').includes(qFlat),
      ),
    [q, qFlat],
  )
  const sel = selected ? items.find((i) => i.id === selected) : null
  const srcObj = srcSel ? lootSources.find((s) => s.name === srcSel) : null

  return (
    <>
      <div className="page-head">
        <div className="page-kicker">Quartermaster's ledger</div>
        <div className="page-title">Loot</div>
        <p className="page-sub">
          Pick a <strong>container</strong>, pick the tier, see exactly what can be inside —
          or flip to <strong>Items</strong> and search where a specific item drops.
          Tables marked “voyage ≠ storm” have different values per game mode.
        </p>
      </div>

      <div className="controls sticky-controls">
        <div className="mode-toggle">
          <button className={'voyage' + (view === 'containers' ? ' on' : '')} onClick={() => setView('containers')}>
            Containers
          </button>
          <button className={'voyage' + (view === 'items' ? ' on' : '')} onClick={() => setView('items')}>
            Items
          </button>
        </div>
        <input
          className="search"
          placeholder={
            view === 'items'
              ? 'Search items…'
              : srcObj
                ? `Search inside ${srcObj.name}…`
                : 'Search containers…'
          }
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="mode-toggle">
          <button className={'voyage' + (mode === 'voyage' ? ' on' : '')} onClick={() => setMode('voyage')}>
            Voyage
          </button>
          <button className={'storm' + (mode === 'storm' ? ' on' : '')} onClick={() => setMode('storm')}>
            Storm Dive
          </button>
        </div>
      </div>

      {view === 'items' ? (
        <div className="loot-layout">
          <div className="gallery stagger" style={{ alignContent: 'start' }}>
            {filteredItems.map((i) => (
              <div
                key={i.id}
                className="gallery-card"
                onClick={() => setSelected(selected === i.id ? null : i.id)}
                style={selected === i.id ? { borderColor: 'var(--rust)' } : {}}
              >
                {itemIcon(i.id) ? <img src={itemIcon(i.id)} alt="" loading="lazy" /> : <div className="ghost-img">?</div>}
                <div className="gname">{i.name}</div>
                {i.rarity && (
                  <div className="grar" style={{ color: RARITY_COLOR[i.rarity] ?? 'var(--ink-faint)' }}>
                    {i.rarity.toLowerCase()}
                  </div>
                )}
              </div>
            ))}
          </div>
          <aside className="loc-drawer">
            {sel ? (
              <ItemDetail item={sel} mode={mode} onClose={() => setSelected(null)} />
            ) : (
              <div className="empty-note">
                SELECT AN ITEM
                <br />
                <span style={{ opacity: 0.6 }}>— drop sources & crafting will appear here —</span>
              </div>
            )}
          </aside>
        </div>
      ) : srcObj ? (
        <SourceDetail key={srcObj.name} src={srcObj} mode={mode} query={q} onBack={() => { setSrcSel(null); setQuery('') }} />
      ) : (
        <div className="src-grid stagger">
          {lootSources
            .filter((s) => !q || s.name.toLowerCase().includes(q))
            .map((src) => (
              <SourceTile key={src.name} src={src} mode={mode} onOpen={() => { setSrcSel(src.name); setQuery('') }} />
            ))}
        </div>
      )}

      <div className="footnote">
        {items.length} items · {lootSources.length} loot sources (193 raw tables merged by what
        you actually open in-game) · drop odds computed from each source's real set weights ·
        names/icons/rarity from the game's own item configs.
      </div>
    </>
  )
}
