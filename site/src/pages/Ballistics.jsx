// Unlisted ballistics sheet — bullet drop / trajectory data per ammo.
// Not in the nav; reached only by its obscure route. Lazy-loaded so this data
// ships as a separate chunk rather than in the main bundle.
import { useMemo, useState } from 'react'
import ballistics from '../data/weapon_ballistics.json'

const RANGES = [50, 100, 200, 400]

// simple no-drag ballistic drop: t = R/v, drop = ½·g·t²  (metres)
function dropAt(velocity, gravity, range) {
  // velocity <= 1 = a non-travelling effect projectile (e.g. post-penetration burst), drop is meaningless
  if (!velocity || velocity <= 1 || !gravity) return null
  const t = range / velocity
  return 0.5 * gravity * t * t
}

export default function Ballistics() {
  const [showDrag, setShowDrag] = useState(true)
  const groups = useMemo(() => {
    const byFam = new Map()
    for (const a of Object.values(ballistics.ammo)) {
      if (!byFam.has(a.family)) byFam.set(a.family, [])
      byFam.get(a.family).push(a)
    }
    for (const [fam, arr] of byFam) {
      if (fam === 'Turrets') {
        // keep each turret type together, then fastest-first within it
        arr.sort((x, y) => (x.turretType || '').localeCompare(y.turretType || '') || (y.velocity ?? 0) - (x.velocity ?? 0))
      } else {
        arr.sort((x, y) => (y.velocity ?? 0) - (x.velocity ?? 0))
      }
    }
    // Turrets first, then the other weapon families alphabetically
    return [...byFam.entries()].sort((a, b) => {
      if (a[0] === 'Turrets') return -1
      if (b[0] === 'Turrets') return 1
      return a[0].localeCompare(b[0])
    })
  }, [])

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1100, margin: '0 auto' }}>
      <h1 style={{ fontFamily: 'var(--font-head)', textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--sand-bright)', fontSize: 28 }}>
        Ballistics Sheet
      </h1>
      <p className="item-desc" style={{ maxWidth: 720 }}>
        Muzzle velocity, gravity and drag per ammo, mined from the projectile blueprints.
        Drop columns are a no-drag estimate (½·g·t², t = range ÷ velocity) for quick comparison,
        real drop is slightly more with drag. Turret ammo is grouped by turret type; each row is
        an ammo variant. A † means that round inherits the turret's base-projectile figures (no
        per-ammo override was found). Unlisted internal sheet.
      </p>

      {groups.map(([fam, rows]) => (
        <div key={fam} className="panel" style={{ padding: 16, margin: '18px 0' }}>
          <div className="section-label" style={{ marginBottom: 10 }}>{fam}</div>
          <table className="drop-matrix" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Ammo</th>
                <th>Velocity</th>
                <th>Gravity</th>
                <th>Drag</th>
                {RANGES.map((r) => <th key={r}>drop @ {r}m</th>)}
                <th>Ricochet</th>
                <th>Pen.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td style={{ textAlign: 'left' }}>
                    {a.label || a.name || a.id}
                    {a.inherited && <span title="Uses the turret's base-projectile figures (no per-ammo override found)" style={{ opacity: 0.5 }}> †</span>}
                  </td>
                  <td>{a.velocity != null ? `${a.velocity} m/s` : '—'}</td>
                  <td>{a.gravity ?? '—'}</td>
                  <td>{a.drag ?? '—'}</td>
                  {RANGES.map((r) => {
                    const d = dropAt(a.velocity, a.gravity, r)
                    return <td key={r}>{d != null ? `${d.toFixed(d < 1 ? 2 : 1)} m` : '—'}</td>
                  })}
                  <td>{a.ricochet?.count ? `${a.ricochet.count}×` : '—'}</td>
                  <td>{a.penetration?.maxCount ? `${a.penetration.maxCount}×` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}
