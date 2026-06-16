// Build-sharing gallery API client. Same-origin: the site is served from
// /sand-wormpit-7x2k/ and the API from /api/sand on the same host (Netlify proxy),
// so plain /api/sand/* fetches resolve correctly in production.
const BASE = '/api/sand'

// stable per-browser token so a person can only vote once per build
export function voterToken() {
  let t = localStorage.getItem('sand_voter')
  if (!t) {
    t = 'v' + Math.random().toString(36).slice(2) + Date.now().toString(36)
    localStorage.setItem('sand_voter', t)
  }
  return t
}

async function jfetch(url, opts) {
  const r = await fetch(url, opts)
  if (!r.ok) {
    const e = await r.json().catch(() => ({}))
    throw new Error(e.error || `request failed (${r.status})`)
  }
  return r.json()
}

export const listBuilds = (sort = 'top') => jfetch(`${BASE}/builds?sort=${sort}`)

export const submitBuild = (build) =>
  jfetch(`${BASE}/builds`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(build),
  })

export const voteBuild = (id) =>
  jfetch(`${BASE}/builds/${id}/vote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ voter: voterToken() }),
  })

// --- moderation (admin key) ---
export const listPending = (key) =>
  jfetch(`${BASE}/admin/pending`, { headers: { 'x-sand-admin-key': key } })

export const moderate = (id, action, key) =>
  jfetch(`${BASE}/admin/builds/${id}?action=${action}`, {
    method: 'POST',
    headers: { 'x-sand-admin-key': key },
  })
