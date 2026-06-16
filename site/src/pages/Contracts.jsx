import { useState } from 'react'
import contracts from '../data/contracts.json'
import { itemIcon, itemName } from '../lib/data.js'

function Bundle({ b }) {
  return (
    <div className="card">
      <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
        <span className="badge sand">reward tier {b.tier}</span>
      </div>
      {b.items.map((e, i) => {
        const icon = itemIcon(e.item)
        return (
          <div className="item-row" key={i}>
            {icon ? <img className="item-icon" src={icon} alt="" loading="lazy" /> : <div className="item-icon ghost">?</div>}
            <span className="item-name" title={e.item}>{itemName(e.item)}</span>
            <span className="item-count">×{e.count}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function Contracts() {
  const [view, setView] = useState('rewards')
  const [tier, setTier] = useState('all')
  const list = (view === 'rewards' ? contracts.rewards : contracts.lockedBox).filter(
    (b) => tier === 'all' || b.tier === tier,
  )
  const tiers = [...new Set((view === 'rewards' ? contracts.rewards : contracts.lockedBox).map((b) => b.tier))].sort()
  return (
    <>
      <div className="page-head">
        <div className="page-kicker">Field assignments</div>
        <div className="page-title">Contracts</div>
        <p className="page-sub">
          Contracts are SAND's missions: find a <strong>contract platform</strong> in the world,
          deliver the requested items into its slots, and a tiered <strong>reward drop</strong>{' '}
          comes in (no active extraction can be nearby). These are the real reward bundles from
          the game files — one is rolled per completion from your reward tier. The same config
          drives <strong>key-locked box</strong> loot, shown in the second tab.
        </p>
      </div>

      <div className="panel warn-banner">
        <span className="warn-icon">⚠</span>
        <div>
          <strong>UNVERIFIED — possibly legacy config.</strong> This reward data sits in the
          current playtest files, but community testers suspect it's an older build's table
          (the Tier&nbsp;4 bundle looks like 2024-era lockbox loot) and it's unclear whether the
          contract system is fully live. Treat as historical until verified in-game — we'll
          re-mine at release.
        </div>
      </div>

      <div className="controls sticky-controls">
        <div className="mode-toggle">
          <button className={'voyage' + (view === 'rewards' ? ' on' : '')} onClick={() => { setView('rewards'); setTier('all') }}>
            Contract rewards
          </button>
          <button className={'voyage' + (view === 'locked' ? ' on' : '')} onClick={() => { setView('locked'); setTier('all') }}>
            Locked boxes
          </button>
        </div>
        <button className={'chip' + (tier === 'all' ? ' on' : '')} onClick={() => setTier('all')}>All tiers</button>
        {tiers.map((t) => (
          <button key={t} className={'chip' + (tier === t ? ' on' : '')} onClick={() => setTier(t)}>
            Tier {t}
          </button>
        ))}
      </div>

      <div className="panel" style={{ padding: 16, marginBottom: 20 }}>
        <div className="section-label" style={{ margin: '0 0 8px' }}>Where to find contract platforms (from the prefabs)</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
          <span className="badge teal">⚒ Little Factory (all 3 variants) ×1 each</span>
          <span className="badge teal">⚒ Little Factory Armory (all 3 variants) ×1 each</span>
          <span className="badge teal">● Basic Contract field sites (4 types) ×2 each</span>
        </div>
        <p style={{ marginTop: 8, fontSize: 12, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)' }}>
          Reward tier scales with the zone tier you're in — deeper zones, better bundles.
        </p>
      </div>

      <div className="grid-cards stagger">
        {list.map((b, i) => <Bundle key={i} b={b} />)}
      </div>

      <div className="footnote">
        {contracts.rewards.length} contract reward bundles · {contracts.lockedBox.length} locked-box
        bundles · which items each contract REQUESTS is decided server-side per match — bring
        valuables and watch the platform's slots.
      </div>
    </>
  )
}
