import { useState } from 'react'
import { PART_BY_ID } from '../lib/builderCore.js'
import { listPending, moderate } from '../lib/galleryApi.js'

// Lightweight moderation view (not in nav). Paste the SAND_ADMIN_KEY once; it's
// kept in localStorage. Approve/reject pending community build submissions.
export default function Moderate() {
  const [key, setKey] = useState(() => localStorage.getItem('sand_admin_key') || '')
  const [builds, setBuilds] = useState(null)
  const [err, setErr] = useState('')

  async function load() {
    setErr('')
    try {
      const d = await listPending(key)
      localStorage.setItem('sand_admin_key', key)
      setBuilds(d.builds)
    } catch (e) {
      setErr(e.message)
      setBuilds(null)
    }
  }

  async function act(id, action) {
    try {
      await moderate(id, action, key)
      setBuilds((bs) => bs.filter((b) => b.id !== id))
    } catch (e) {
      setErr(e.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-kicker">Admin</div>
        <div className="page-title">Moderate Submissions</div>
        <p className="page-sub">Approve or reject community build submissions before they reach the gallery.</p>
      </div>

      <div className="controls">
        <input
          className="search"
          type="password"
          placeholder="SAND_ADMIN_KEY"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        <button className="chip on" onClick={load}>Load pending</button>
      </div>

      {err && <div className="empty-note" style={{ padding: 18 }}>{err}</div>}
      {builds && builds.length === 0 && <div className="empty-note" style={{ padding: 18 }}>No pending submissions.</div>}

      {builds && builds.length > 0 && (
        <div className="gallery-grid">
          {builds.map((b) => (
            <div className="build-card" key={b.id}>
              <div className="build-card-head"><h3>{b.name}</h3></div>
              {b.author && <div className="build-author">by {b.author}</div>}
              {b.description && <p className="build-desc">{b.description}</p>}
              <div className="build-meta">
                <span>⬡ {PART_BY_ID[b.chassis_id]?.name || b.chassis_id}</span>
                <span>{b.part_count} parts</span>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button className="bp-btn" style={{ flex: 1 }} onClick={() => act(b.id, 'approve')}>✓ APPROVE</button>
                <button className="bp-btn danger" style={{ flex: 1 }} onClick={() => act(b.id, 'reject')}>✕ REJECT</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
