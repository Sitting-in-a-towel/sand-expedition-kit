# Trampler Builder → Baal's Sand-wiki: Integration Spec

**Goal:** land the SAND Expedition Kit's 3D Trampler builder inside Baal's Sand-wiki app, cleanly and in reviewable pieces. This doc is the thing Baal + owner mark up before any PR.

**Authority:** the builder is the owner's; Baal's repo is Baal's. Nothing gets committed/merged/PR'd to `Baal-Marduk/Sand-wiki` without Baal's explicit approval and notes. This spec exists to get that approval.

---

## 1. The two stacks

**Source (owner's `sand-expedition-kit`):**
- Vite + React 18 + plain JS (JSX)
- Raw **three.js** (0.184), no react-three-fiber
- Data: static JSON (`parts_v2.json`, `chassis_cells.json`, `mesh_index_v3.json`, `part_thumbs(_v2).json`) imported at build time
- Assets: `public/meshes3/*.bin` (part meshes), `public/tex3/*.png` (~85 MB total incl. screenshots)
- Logic: `lib/builderCore.js` (placement/validation/sockets), `components/BuilderScene.jsx` (three.js scene), `pages/BuilderV2.jsx` (UI), `lib/wbtImport.js` (in-game `.wbt` save import), `lib/galleryApi.js` (standalone build-share API)
- Routing: hash router

**Target (Baal's `Sand-wiki`):**
- Next.js 16 + React 19 + **TypeScript**
- Tailwind v4 + shadcn/Radix
- **Postgres via Prisma** (Neon) + **Directus** CMS
- **Steam OpenID** login + a proposal/moderation system
- Already models trampler parts: `Entity(kind="trampler-part")` + `TramplerStats` (health, weight, weight/energy capacity, ratedPower, crew/item slots)

**Key fact:** the two halves are complementary. Ours has the 3D geometry + meshes Baal's DB lacks; Baal's DB has the part budget stats (weight/power/slots) that aren't in the game files (they're masterserver-sourced).

---

## 2. The five integration problems

1. **Framework port.** Builder must enter as a **client-only component**: `'use client'`, loaded via `next/dynamic` with `{ ssr: false }` (three.js cannot server-render). React 18→19 is low-risk for this code; convert JSX→TSX to fit Baal's TS + eslint-next (or allow JS in that dir, Baal's call).
2. **Data contract.** Ship the builder's geometry data (`parts_v2.json` + `chassis_cells.json` + `mesh_index_v3.json`) as bundled static assets initially (they change rarely). Join to Baal's DB by a **part-id ↔ Entity-slug map** to pull live budget stats from `TramplerStats`. (Our part ids look like `compReactor_Round_Metal_2x1`; need the mapping to his slugs.)
3. **3D assets.** `meshes3/*.bin` + `tex3/*.png` + thumbnails go in Baal's `public/`. ~85 MB — decide hosting: committed (maybe git-lfs) vs CDN/object storage. Mind Next `basePath`. Loader fetches `meshes3/<id>.bin` at runtime, so paths must respect the deployed base.
4. **Build sharing.** Drop our standalone `galleryApi`; use Baal's backend instead — a Prisma `Build` model + a Next route/server action, **gated by Steam auth**, moderated through his existing proposal/admin flow. Reuse our share format (`SANDBP2` code) as the serialized payload.
5. **Styling.** Keep the builder's scoped CSS at first so it works immediately; optional later pass to restyle with Tailwind/shadcn for visual consistency.

---

## 3. Suggested PR breakdown (small, reviewable)

- **PR1 — Vendor the builder, static + offline.** Builder component + `builderCore` + geometry JSON + mesh/tex assets as a self-contained client-only module behind a route. No DB, no auth. Goal: it renders and you can build, using bundled data. Lowest risk, biggest visible win.
- **PR2 — Data join.** Add the part-id ↔ Entity-slug map; pull budget stats (weight/power/capacity/crew/item slots) from `TramplerStats` so the builder shows live validity (weight vs capacity, power balance, slots).
- **PR3 — Build sharing.** `Build` Prisma model + save/load endpoint, Steam-auth gated, moderation via the existing flow. Port `.wbt` import (`decodeWbt`) and the `SANDBP2` share code.
- **PR4 — Polish.** Tailwind/shadcn restyle, nav entry, thumbnails, mobile.

Each PR stands alone and is independently reviewable; PR1 is shippable without 2-4.

---

## 4. Watch-items / risks
- **three.js + Next SSR** — must be `ssr: false` dynamic import, else build/runtime errors.
- **React 18 → 19** — check effects/refs in `BuilderScene` (we use manual refs + a tick); low risk but verify.
- **JS → TS** — typing `builderCore`/`BuilderScene` or relaxing TS for that dir.
- **Bundle size** — three.js (~1.3 MB) + geometry; lazy-load the builder route (Baal already code-splits).
- **id ↔ slug mapping accuracy** — the one piece that must be exact for the stat join.
- **Asset hosting** — 85 MB of meshes/textures; LFS vs CDN.

## 5. Open questions for Baal
1. Asset hosting: commit (git-lfs?) or CDN?
2. Keep our bundled static parts data, or source geometry from your DB too?
3. Your Steam session/auth API surface for gating build saves?
4. Component/dir conventions + TS strictness you want followed?
5. Do you want the builder behind a route now, or feature-flagged until PR2/3 land?

---
*Owner steers the merge; Baal approves anything touching his repo. This spec is the basis for that sign-off.*
