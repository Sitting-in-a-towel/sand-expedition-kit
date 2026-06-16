import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PART_BY_ID } from '../lib/builderCore.js'
import { listBuilds, voteBuild, voterToken } from '../lib/galleryApi.js'

function chassisName(id) {
  return PART_BY_ID[id]?.name || id || 'Unknown chassis'
}

export default function Gallery() {
  const [sort, setSort] = useState('top')
  const [builds, setBuilds] = useState(null)
  const [err, setErr] = useState('')
  const [voted, setVoted] = useState(() => new Set(JSON.parse(localStorage.getItem('sand_voted') || '[]')))
  const nav = useNavigate()

  useEffect(() => {
    let live = true
    setBuilds(null); setErr('')
    listBuilds(sort)
      .then((d) => live && setBuilds(d.builds))
      .catch((e) => live && setErr(e.message))
    return () => { live = false }
  }, [sort])

  async function vote(id) {
    if (voted.has(id)) return
    try {
      const r = await voteBuild(id)
      setBuilds((bs) => bs.map((b) => (b.id === id ? { ...b, votes: r.votes } : b)))
      const next = new Set(voted); next.add(id)
      setVoted(next)
      localStorage.setItem('sand_voted', JSON.stringify([...next]))
    } catch { /* ignore */ }
  }

  function openInBuilder(code) {
    localStorage.setItem('sand_load_code', code)
    nav('/builder2')
  }

  return (
    <>
      <div className="page-head">
        <div className="page-kicker">Community blueprints</div>
        <div className="page-title">Build Gallery</div>
        <p className="page-sub">
          Tramplers shared by the community. Open any one straight into the builder to inspect,
          tweak or fork it. Vote up the ones you like. Submit your own from the{' '}
          <strong>Builder V2</strong> page.
        </p>
      </div>

      <div className="controls sticky-controls">
        <div className="mode-toggle">
          <button className={'voyage' + (sort === 'top' ? ' on' : '')} onClick={() => setSort('top')}>Top voted</button>
          <button className={'voyage' + (sort === 'new' ? ' on' : '')} onClick={() => setSort('new')}>Newest</button>
        </div>
      </div>

      {err && <div className="empty-note" style={{ padding: 18 }}>Couldn’t load the gallery: {err}</div>}
      {!err && builds === null && <div className="empty-note" style={{ padding: 18 }}>Loading…</div>}
      {!err && builds && builds.length === 0 && (
        <div className="empty-note" style={{ padding: 26 }}>
          NO BUILDS YET
          <br />
          <span style={{ opacity: 0.6 }}>— be the first: build a Trampler and hit “Publish to gallery” —</span>
        </div>
      )}

      {builds && builds.length > 0 && (
        <div className="gallery-grid stagger">
          {builds.map((b) => (
            <div className="build-card" key={b.id}>
              <div className="build-card-head">
                <h3>{b.name}</h3>
                <button
                  className={'vote-btn' + (voted.has(b.id) ? ' on' : '')}
                  onClick={() => vote(b.id)}
                  title={voted.has(b.id) ? 'you voted' : 'vote up'}
                >
                  ▲ {b.votes}
                </button>
              </div>
              {b.author && <div className="build-author">by {b.author}</div>}
              {b.description && <p className="build-desc">{b.description}</p>}
              <div className="build-meta">
                <span>⬡ {chassisName(b.chassis_id)}</span>
                <span>{b.part_count} parts</span>
              </div>
              <button className="bp-btn build-open" onClick={() => openInBuilder(b.share_code)}>
                OPEN IN BUILDER →
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="footnote">
        Community-submitted builds are reviewed before they appear here. Builds load entirely in
        your browser — share codes carry the whole design.
      </div>
    </>
  )
}
