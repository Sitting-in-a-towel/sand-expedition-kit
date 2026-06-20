// Builder V2 scene — full 3D socket-driven editor viewport (in-game style).
// Real game meshes (v2 pipeline: LOD0/1, real normals, material colours).
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import {
  PART_BY_ID, MESH_INDEX, CELL_XZ, CELL_Y, DIRS,
  worldCells, validate, buildOccupancy, editableSockets, cellKey, chassisLegs,
  isEntrance, entranceLegalCells,
} from '../lib/builderCore.js'
import { asset } from '../lib/data.js'

// ---- shared albedo texture cache (v3) ----
const texCache = new Map()
let onTexLoad = null // set by the scene so async texture loads trigger a re-render
function getTexture(file) {
  if (texCache.has(file)) return texCache.get(file)
  const tx = new THREE.TextureLoader().load(asset(file), () => { if (onTexLoad) onTexLoad() })
  tx.colorSpace = THREE.SRGBColorSpace
  tx.wrapS = tx.wrapT = THREE.RepeatWrapping
  tx.anisotropy = 4
  texCache.set(file, tx)
  return tx
}

// ---- v3 mesh loader: [t*9 f32 pos][t*9 i8 nrm/127][t*6 f32 uv][t*1 u8 texSlot] ----
// geometry carries groups (one per texture slot); geo.userData.tex/col drive materials.
const geoCache = new Map()
function loadGeometry(partId, onReady) {
  if (geoCache.has(partId)) {
    const g = geoCache.get(partId)
    return g === 'loading' ? null : g
  }
  const meta = MESH_INDEX[partId]
  if (!meta) {
    geoCache.set(partId, null)
    return null
  }
  geoCache.set(partId, 'loading')
  fetch(asset(`meshes3/${partId}.bin`))
    .then((r) => r.arrayBuffer())
    .then((buf) => {
      const t = meta.t
      // Float32 views need a 4-byte-aligned offset; the int8 normal block (t*9 bytes)
      // leaves the uv offset misaligned for ~half the parts, which used to throw and
      // drop them to box fallback. Copy the slice when unaligned.
      const f32 = (off, len) => (off % 4 === 0
        ? new Float32Array(buf, off, len)
        : new Float32Array(buf.slice(off, off + len * 4)))
      let off = 0
      const pos = f32(off, t * 9); off += t * 36
      const nrmQ = new Int8Array(buf, off, t * 9); off += t * 9
      const uv = f32(off, t * 6); off += t * 24
      const slot = new Uint8Array(buf, off, t); off += t
      const nrm = new Float32Array(t * 9)
      for (let i = 0; i < t * 9; i++) nrm[i] = nrmQ[i] / 127

      // material slots present: local tex index 0..n-1, plus 255 (flat) -> last index
      const texFiles = meta.tex || []
      const flatIdx = texFiles.length // material index for untextured tris
      // sort triangles by material index so we can emit contiguous groups
      const order = Array.from({ length: t }, (_, i) => i)
      const matOf = (i) => (slot[i] === 255 ? flatIdx : slot[i])
      order.sort((a, b) => matOf(a) - matOf(b))

      const P = new Float32Array(t * 9), N = new Float32Array(t * 9), U = new Float32Array(t * 6)
      for (let k = 0; k < t; k++) {
        const i = order[k]
        P.set(pos.subarray(i * 9, i * 9 + 9), k * 9)
        N.set(nrm.subarray(i * 9, i * 9 + 9), k * 9)
        U.set(uv.subarray(i * 6, i * 6 + 6), k * 6)
      }
      const geo = new THREE.BufferGeometry()
      geo.setAttribute('position', new THREE.BufferAttribute(P, 3))
      geo.setAttribute('normal', new THREE.BufferAttribute(N, 3))
      geo.setAttribute('uv', new THREE.BufferAttribute(U, 2))
      // groups: contiguous runs of same material index
      let start = 0
      for (let k = 1; k <= t; k++) {
        if (k === t || matOf(order[k]) !== matOf(order[start])) {
          geo.addGroup(start * 3, (k - start) * 3, matOf(order[start]))
          start = k
        }
      }
      geo.userData = { tex: texFiles, col: meta.col || [], flatIdx }
      geoCache.set(partId, geo)
      onReady()
    })
    .catch(() => geoCache.set(partId, null))
  return null
}

// build the material array for a geometry's groups (textured per slot + flat fallback)
function partMaterials(geo, { transparent = false, opacity = 1, selected = false, invalid = false } = {}) {
  const { tex = [], col = [], flatIdx = 0 } = geo.userData || {}
  const mk = (opts) => {
    const m = new THREE.MeshStandardMaterial({
      metalness: 0.3, roughness: 0.7, envMapIntensity: 0.8, side: THREE.DoubleSide,
      transparent, opacity, ...opts,
    })
    if (selected) { m.emissive = new THREE.Color(0x59ffa1); m.emissiveIntensity = 0.16 }
    if (invalid) { m.emissive = new THREE.Color(0xff4444); m.emissiveIntensity = 0.4 } // red = placeable but invalid
    return m
  }
  // the albedo map already carries the colour — don't multiply by the part's base
  // tint (that darkens it). Flat fallback uses the base colour where there's no map.
  const mats = tex.map((file) => mk({ map: getTexture(file), color: 0xffffff }))
  const fc = col[flatIdx] || col[0]
  mats[flatIdx] = mk({ color: fc ? new THREE.Color(`rgb(${fc[0]},${fc[1]},${fc[2]})`) : 0xaaaaaa })
  return mats
}

// position a part mesh so its volume-cell footprint sits on its cells
function placeMesh(mesh, partId, px, py, pz, rot) {
  const part = PART_BY_ID[partId]
  const meta = MESH_INDEX[partId]
  if (!meta) return
  const cells = worldCells(part, px, py, pz, rot)
  const fp = cells.filter((c) => c.vol)
  const use = fp.length ? fp : cells.filter((c) => c.y === py)
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, minY = Infinity
  for (const c of use) {
    minX = Math.min(minX, c.x); maxX = Math.max(maxX, c.x)
    minZ = Math.min(minZ, c.z); maxZ = Math.max(maxZ, c.z)
    minY = Math.min(minY, c.y)
  }
  const cx = ((minX + maxX) / 2) * CELL_XZ
  const cz = ((minZ + maxZ) / 2) * CELL_XZ
  const b = meta.b
  // Footprint centre in mesh space via the game's own GetPosition(cell, cellSize,
  // pivotOffset): cell positions = avgCell*cellSize - pivotOffset. The old AABB centre
  // ((b[0]+b[3])/2 …) breaks for parts whose mesh isn't centred on its footprint (e.g.
  // steering helms sit at one end → landed "between two blocks"). cellSize ≈ CELL_XZ;
  // the v3 export flips Z, so the Z term is negated relative to game space.
  const po = part.pivotOffset || [0, 0, 0]
  const vol = part.cells.filter((c) => !c.noVol)
  const cl = vol.length ? vol : part.cells
  let sx = 0, sz = 0
  for (const c of cl) { sx += c.p[0]; sz += c.p[2] }
  const mcx = (sx / cl.length) * CELL_XZ - po[0]
  const mcz = -((sz / cl.length) * CELL_XZ - po[2])
  const a = (((rot % 4) + 4) % 4) * (Math.PI / 2)
  mesh.rotation.y = a
  const offX = mcx * Math.cos(a) + mcz * Math.sin(a)
  const offZ = -mcx * Math.sin(a) + mcz * Math.cos(a)
  // world y=0 = chassis plate top = floor of grid level 1
  mesh.position.set(cx - offX, (minY - 1) * CELL_Y - b[1], cz - offZ)
}

export default function BuilderScene({
  state, level, activePart, activeRot, selectedId, invalidMap, onPlace, onSelect, onMove, onHoverInfo, onSocketToggle,
}) {
  const mountRef = useRef(null)
  const stRef = useRef(null)
  const propsRef = useRef({})
  const [tick, setTick] = useState(0)
  propsRef.current = { state, level, activePart, activeRot, selectedId, invalidMap, onPlace, onSelect, onMove, onHoverInfo, onSocketToggle }

  // ---------- init ----------
  useEffect(() => {
    const mount = mountRef.current
    const W = mount.clientWidth
    const H = mount.clientHeight
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x0d1320)
    // filmic tone mapping + correct colour management for a "rendered" look
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    // soft shadows
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x0d1320, 90, 220)
    const camera = new THREE.PerspectiveCamera(46, W / H, 0.5, 400)

    // image-based lighting: a neutral room env gives metal/brass something to
    // reflect (procedural, no asset needed) — biggest single quality win
    const pmrem = new THREE.PMREMGenerator(renderer)
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture

    scene.add(new THREE.HemisphereLight(0xcfe4ff, 0x2a2118, 0.4))
    const dir = new THREE.DirectionalLight(0xfff1d6, 1.5)
    dir.position.set(40, 70, 25)
    dir.castShadow = true
    dir.shadow.mapSize.set(2048, 2048)
    dir.shadow.camera.near = 1
    dir.shadow.camera.far = 220
    dir.shadow.camera.left = -70
    dir.shadow.camera.right = 70
    dir.shadow.camera.top = 70
    dir.shadow.camera.bottom = -70
    dir.shadow.bias = -0.0004
    dir.shadow.normalBias = 0.02
    scene.add(dir)
    const dir2 = new THREE.DirectionalLight(0x88aaff, 0.3)
    dir2.position.set(-30, 20, -40)
    scene.add(dir2)

    // sand ground
    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(180, 48),
      new THREE.MeshStandardMaterial({ color: 0x8a6f47, roughness: 1 }),
    )
    ground.rotation.x = -Math.PI / 2
    ground.position.y = -7
    ground.receiveShadow = true
    scene.add(ground)

    const rigGroup = new THREE.Group()
    const helperGroup = new THREE.Group()
    const ghostGroup = new THREE.Group()
    scene.add(rigGroup, helperGroup, ghostGroup)

    const st = {
      renderer, scene, camera, rigGroup, helperGroup, ghostGroup,
      theta: Math.PI * 0.28, phi: 1.0, dist: 42,
      target: new THREE.Vector3(0, 4, 0),
      drag: null, // {mode:'orbit'|'pan'|'movePl', sx, sy, plId, moved}
      raycaster: new THREE.Raycaster(),
      pointer: new THREE.Vector2(),
      hoverCell: null,
      ghostValid: false,
      placedMeshes: new Map(), // plId -> mesh
      socketSprites: [],
      raf: 0,
    }
    stRef.current = st

    const applyCamera = () => {
      const { theta, phi, dist, target } = st
      camera.position.set(
        target.x + dist * Math.sin(phi) * Math.cos(theta),
        target.y + dist * Math.cos(phi),
        target.z + dist * Math.sin(phi) * Math.sin(theta),
      )
      camera.lookAt(target)
    }
    const render = () => {
      applyCamera()
      renderer.render(scene, camera)
    }
    st.render = render
    onTexLoad = () => stRef.current && stRef.current.render()
    render()

    const el = renderer.domElement
    el.style.cursor = 'grab'

    function planeHit(e, yLevel) {
      const r = el.getBoundingClientRect()
      st.pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      st.raycaster.setFromCamera(st.pointer, camera)
      const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -((yLevel - 1) * CELL_Y))
      const out = new THREE.Vector3()
      return st.raycaster.ray.intersectPlane(plane, out) ? out : null
    }

    function pickPlacement(e) {
      const r = el.getBoundingClientRect()
      st.pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      st.raycaster.setFromCamera(st.pointer, camera)
      const sprites = st.raycaster.intersectObjects(st.socketSprites, false)
      if (sprites.length) return { socket: sprites[0].object.userData }
      const hits = st.raycaster.intersectObjects([...st.placedMeshes.values()], false)
      if (hits.length) return { plId: hits[0].object.userData.plId }
      return null
    }

    function onDown(e) {
      const P = propsRef.current
      if (e.button === 2 || e.button === 1) {
        st.drag = { mode: 'pan', sx: e.clientX, sy: e.clientY }
        return
      }
      if (P.activePart) {
        // placement click handled on up (so you can still orbit while placing)
        st.drag = { mode: 'orbit', sx: e.clientX, sy: e.clientY, sx0: e.clientX, sy0: e.clientY, place: true }
        return
      }
      const hit = pickPlacement(e)
      if (hit?.socket) {
        st.drag = { mode: 'socket', socket: hit.socket, sx0: e.clientX, sy0: e.clientY }
        return
      }
      if (hit?.plId) {
        st.drag = { mode: 'movePl', plId: hit.plId, sx: e.clientX, sy: e.clientY, sx0: e.clientX, sy0: e.clientY, moved: false }
        return
      }
      st.drag = { mode: 'orbit', sx: e.clientX, sy: e.clientY, sx0: e.clientX, sy0: e.clientY, deselect: true }
    }

    function onMove(e) {
      const P = propsRef.current
      const d = st.drag
      if (d && (d.mode === 'orbit')) {
        st.theta += (e.clientX - d.sx) * 0.006
        st.phi = Math.min(1.5, Math.max(0.15, st.phi - (e.clientY - d.sy) * 0.005))
        d.sx = e.clientX
        d.sy = e.clientY
        render()
      } else if (d && d.mode === 'pan') {
        const k = st.dist * 0.0016
        const fwd = new THREE.Vector3().subVectors(st.target, camera.position).setY(0).normalize()
        const right = new THREE.Vector3(-fwd.z, 0, fwd.x)
        st.target.addScaledVector(right, -(e.clientX - d.sx) * k)
        st.target.addScaledVector(fwd, (e.clientY - d.sy) * k)
        d.sx = e.clientX
        d.sy = e.clientY
        render()
      } else if (d && d.mode === 'movePl') {
        const hit = planeHit(e, P.level)
        if (hit) {
          const gx = Math.round(hit.x / CELL_XZ)
          const gz = Math.round(hit.z / CELL_XZ)
          if (Math.abs(e.clientX - d.sx0) + Math.abs(e.clientY - d.sy0) > 6) d.moved = true
          if (d.moved) P.onMove?.(d.plId, gx, gz, true) // preview move
        }
      }
      // ghost tracking while placing
      if (P.activePart) {
        const hit = planeHit(e, P.level)
        if (hit) {
          const gx = Math.round(hit.x / CELL_XZ)
          const gz = Math.round(hit.z / CELL_XZ)
          if (!st.hoverCell || st.hoverCell[0] !== gx || st.hoverCell[1] !== gz) {
            st.hoverCell = [gx, gz]
            updateGhost()
            render()
          }
        }
      }
    }

    function onUp(e) {
      const P = propsRef.current
      const d = st.drag
      st.drag = null
      if (!d) return
      const movedFar = Math.abs(e.clientX - (d.sx0 ?? e.clientX)) + Math.abs(e.clientY - (d.sy0 ?? e.clientY)) > 6
      if (d.mode === 'socket' && !movedFar) {
        P.onSocketToggle?.(d.socket.plId, d.socket.key)
        return
      }
      if (d.mode === 'orbit' && d.place && !movedFar && st.hoverCell) {
        P.onPlace?.(st.hoverCell[0], st.hoverCell[1], st.ghostBlocked) // place unless overlap-blocked
        return
      }
      if (d.mode === 'orbit' && d.deselect && !movedFar) {
        P.onSelect?.(null)
      }
      if (d.mode === 'movePl') {
        if (d.moved) {
          P.onMove?.(d.plId, null, null, false) // commit
        } else {
          P.onSelect?.(d.plId)
        }
      }
    }

    function onWheel(e) {
      e.preventDefault()
      st.dist = Math.min(140, Math.max(10, st.dist * Math.exp(e.deltaY * 0.001)))
      render()
    }

    el.addEventListener('pointerdown', onDown)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('contextmenu', (e) => e.preventDefault())

    const onResize = () => {
      const w = mount.clientWidth
      const h = mount.clientHeight
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      render()
    }
    window.addEventListener('resize', onResize)

    // ---- ghost rebuild (uses propsRef so it always sees latest) ----
    function updateGhost() {
      const P = propsRef.current
      const { ghostGroup } = st
      ghostGroup.clear()
      st.ghostValid = false
      if (!P.activePart || !st.hoverCell) return
      const [gx, gz] = st.hoverCell
      const occ = buildOccupancy(P.state)
      const v = validate(P.state, occ, P.activePart, gx, P.level, gz, P.activeRot)
      st.ghostValid = v.ok
      st.ghostBlocked = v.blocked
      P.onHoverInfo?.(v.ok ? '' : v.reason)
      // grey = blocked (can't place), green = valid, red = placeable but invalid
      const col = v.blocked ? 0x8b94a3 : v.ok ? 0x59ffa1 : 0xff5964
      const part = PART_BY_ID[P.activePart]
      // cell outlines
      const cellMat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.22, side: THREE.DoubleSide })
      for (const c of worldCells(part, gx, P.level, gz, P.activeRot)) {
        const q = new THREE.Mesh(new THREE.PlaneGeometry(CELL_XZ * 0.96, CELL_XZ * 0.96), cellMat)
        q.rotation.x = -Math.PI / 2
        q.position.set(c.x * CELL_XZ, (c.y - 1) * CELL_Y + 0.04, c.z * CELL_XZ)
        ghostGroup.add(q)
      }
      // ghost mesh
      const geo = geoCache.get(P.activePart)
      if (geo && geo !== 'loading') {
        const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
          color: col, transparent: true, opacity: 0.45, vertexColors: false,
          side: THREE.DoubleSide, depthWrite: false,
        }))
        placeMesh(m, P.activePart, gx, P.level, gz, P.activeRot)
        ghostGroup.add(m)
      }
    }
    st.updateGhost = updateGhost

    return () => {
      el.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      el.removeEventListener('wheel', onWheel)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      mount.removeChild(el)
    }
  }, [])

  // ---------- rebuild rig on state change ----------
  useEffect(() => {
    const st = stRef.current
    if (!st) return
    const { rigGroup, helperGroup } = st
    rigGroup.clear()
    helperGroup.clear()
    st.placedMeshes.clear()
    st.socketSprites = []

    const bump = () => stRef.current && setTick((t) => t + 1)

    // chassis
    const ch = PART_BY_ID[state.chassisId]
    if (ch) {
      const g = loadGeometry(state.chassisId, bump)
      if (g) {
        const m = new THREE.Mesh(g, partMaterials(g))
        m.castShadow = true
        m.receiveShadow = true
        // chassis: align mesh TOP to deck-0 floor (plate hangs below, legs to ground)
        const meta = MESH_INDEX[state.chassisId]
        const b = meta.b
        m.position.set(-(b[0] + b[3]) / 2, -b[4], -(b[2] + b[5]) / 2)
        rigGroup.add(m)
      }

      // legs: render-only walker legs under the chassis (instanced from one mesh).
      // foot planted on the sand plane (ground y=-7); not added to placedMeshes so
      // they're never selectable/pickable.
      // SHOW_LEGS: the real walker leg mesh (game_ironcladLeg_model) is an articulated
      // foot/lower-leg assembly in a shallow rig pose — it doesn't read as a clean
      // standing leg when isolated + re-posed rigidly. Gated off pending owner input on
      // approach (fix real-mesh pose vs procedural strut). Anchors below are correct.
      const SHOW_LEGS = true // flip true to preview the real player leg (pose WIP)
      const legGeo = SHOW_LEGS ? loadGeometry('_leg', bump) : null
      const legMeta = MESH_INDEX['_leg']
      if (legGeo && legMeta) {
        // The player leg (walker_leg) is authored lying near-flat (hip ~(-0.8,-2.08),
        // foot ~(5.2,-3.37) → only ~12° below horizontal). It's planar in local XY and
        // already has a knee in it. Rotate it about Z (pivoting at the hip) so the
        // hip->foot line is near-vertical — foot lands just under the edge, knee bows
        // out → the "spider" C pose. Then yaw the whole leg to its outward face.
        const HIP = new THREE.Vector3(-0.8, -2.08, 0)
        const TILT = -1.15 // rad about Z: ~12° -> ~78° (near vertical, slight outward splay)
        const FOOT_DROP = 6.0 // vertical hip->foot after the tilt (m), keeps foot on sand
        const GROUND = -7
        const rz = new THREE.Matrix4().makeRotationZ(TILT)
        const hipAfter = HIP.clone().applyMatrix4(rz) // where the hip lands after tilt
        for (const leg of chassisLegs(ch)) {
          const legGroup = new THREE.Group()
          const lm = new THREE.Mesh(legGeo, partMaterials(legGeo))
          lm.castShadow = true
          lm.receiveShadow = true
          lm.rotation.z = TILT
          lm.position.set(-hipAfter.x, -hipAfter.y, -hipAfter.z) // pin hip to group origin
          legGroup.add(lm)
          legGroup.rotation.y = leg.yaw
          // hip sits just under the deck; height chosen so the tilted foot meets GROUND
          legGroup.position.set(leg.x * CELL_XZ, GROUND + FOOT_DROP, leg.z * CELL_XZ)
          rigGroup.add(legGroup)
        }
      }
    }

    // placements
    for (const pl of state.placements) {
      const part = PART_BY_ID[pl.partId]
      if (!part) continue
      const isSel = pl.id === selectedId
      const onLevel = pl.y === level
      const g = loadGeometry(pl.partId, bump)
      const isInvalid = !!invalidMap?.[pl.id]
      if (g) {
        const mats = partMaterials(g, {
          transparent: !onLevel && !isSel, opacity: onLevel || isSel ? 1 : 0.35, selected: isSel, invalid: isInvalid,
        })
        const m = new THREE.Mesh(g, mats)
        m.castShadow = true
        m.receiveShadow = true
        placeMesh(m, pl.partId, pl.x, pl.y, pl.z, pl.rot)
        m.userData.plId = pl.id
        rigGroup.add(m)
        st.placedMeshes.set(pl.id, m)
      } else {
        // box fallback while loading
        const cells = worldCells(part, pl.x, pl.y, pl.z, pl.rot).filter((c) => c.vol)
        for (const c of cells) {
          const bx = new THREE.Mesh(
            new THREE.BoxGeometry(CELL_XZ * 0.92, CELL_Y * 0.9, CELL_XZ * 0.92),
            new THREE.MeshStandardMaterial({ color: 0x44566b, transparent: true, opacity: 0.5 }),
          )
          bx.position.set(c.x * CELL_XZ, (c.y - 1) * CELL_Y + CELL_Y / 2, c.z * CELL_XZ)
          bx.castShadow = true
          bx.userData.plId = pl.id
          rigGroup.add(bx)
          st.placedMeshes.set(pl.id, bx)
        }
      }
    }

    // ---- helpers: active-level grid over chassis extent + front arrow ----
    const occ = buildOccupancy(state)
    const gridMat = new THREE.LineBasicMaterial({ color: 0x3f6f9e, transparent: true, opacity: 0.55 })
    const pts = []
    if (ch) {
      for (const c of worldCells(ch, 0, 0, 0, 0)) {
        const x = c.x * CELL_XZ
        const z = c.z * CELL_XZ
        const y = (level - 1) * CELL_Y + 0.03
        const h = CELL_XZ / 2
        pts.push(
          new THREE.Vector3(x - h, y, z - h), new THREE.Vector3(x + h, y, z - h),
          new THREE.Vector3(x + h, y, z - h), new THREE.Vector3(x + h, y, z + h),
          new THREE.Vector3(x + h, y, z + h), new THREE.Vector3(x - h, y, z + h),
          new THREE.Vector3(x - h, y, z + h), new THREE.Vector3(x - h, y, z - h),
        )
      }
    }
    helperGroup.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), gridMat))

    // FRONT arrow (in-game: -Z = front)
    const arrow = new THREE.Mesh(
      new THREE.ConeGeometry(1.1, 2.6, 4),
      new THREE.MeshStandardMaterial({ color: 0xffd166, emissive: 0x664d12 }),
    )
    arrow.rotation.x = -Math.PI / 2
    const chMinZ = ch ? Math.min(...worldCells(ch, 0, 0, 0, 0).map((c) => c.z)) : -3
    arrow.position.set(0, 0.6, (chMinZ - 1.2) * CELL_XZ)
    helperGroup.add(arrow)
    const rear = new THREE.Mesh(
      new THREE.BoxGeometry(1.6, 0.3, 0.3),
      new THREE.MeshStandardMaterial({ color: 0x5aa9e6 }),
    )
    const chMaxZ = ch ? Math.max(...worldCells(ch, 0, 0, 0, 0).map((c) => c.z)) : 3
    rear.position.set(0, 0.6, (chMaxZ + 1.2) * CELL_XZ)
    helperGroup.add(rear)

    // ---- entrance legal-spot pads: when placing an entrance, light up every cell on
    // this deck where it would legally take (edge overhang, clear ladder, off the legs) ----
    if (activePart && isEntrance(PART_BY_ID[activePart])) {
      const padMat = new THREE.MeshBasicMaterial({
        color: 0x59ffa1, transparent: true, opacity: 0.32, side: THREE.DoubleSide,
      })
      for (const cell of entranceLegalCells(state, activePart, level)) {
        const q = new THREE.Mesh(new THREE.PlaneGeometry(CELL_XZ * 0.88, CELL_XZ * 0.88), padMat)
        q.rotation.x = -Math.PI / 2
        q.position.set(cell.x * CELL_XZ, (level - 1) * CELL_Y + 0.05, cell.z * CELL_XZ)
        helperGroup.add(q)
      }
    }

    // ---- editable socket badges on the selected placement ----
    if (selectedId) {
      const pl = state.placements.find((p) => p.id === selectedId)
      const part = pl && PART_BY_ID[pl.partId]
      if (part) {
        for (const s of editableSockets(part, pl)) {
          const stateNow = pl.conns?.[s.key] ?? 'DEFAULT'
          const colByState = { DEFAULT: 0x9aa7b8, DOOR: 0x59c2ff, OPEN: 0x59ffa1 }
          const sp = new THREE.Mesh(
            new THREE.SphereGeometry(0.55, 12, 10),
            new THREE.MeshBasicMaterial({ color: colByState[stateNow] ?? 0x9aa7b8 }),
          )
          const v = DIRS[s.dir]
          sp.position.set(
            (s.x + v[0] * 0.5) * CELL_XZ,
            (s.y - 1) * CELL_Y + (v[1] === 0 ? CELL_Y * 0.45 : (v[1] > 0 ? CELL_Y : 0)),
            (s.z + v[2] * 0.5) * CELL_XZ,
          )
          sp.userData = { plId: pl.id, key: s.key, type: s.type }
          helperGroup.add(sp)
          st.socketSprites.push(sp)
        }
      }
    }

    st.updateGhost?.()
    st.render()
  }, [state, level, selectedId, activePart, activeRot, invalidMap, tick])

  return (
    <div ref={mountRef} className="bv2-canvas">
      <div className="bv2-hud">
        LMB drag = orbit · RMB = pan · scroll = zoom · click part = select · Space = rotate · R/F = deck up/down · Del = remove
      </div>
    </div>
  )
}
