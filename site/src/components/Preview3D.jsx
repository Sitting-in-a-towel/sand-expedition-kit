import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import meshIndex from '../data/mesh_index.json'
import { asset } from '../lib/data.js'

const LEVEL_H = 0.62
const CELL_M = meshIndex._cell || 4

// lazy geometry cache: partId -> BufferGeometry | 'loading' | null
const geoCache = new Map()
function loadGeometry(partId, onReady) {
  if (geoCache.has(partId)) {
    const g = geoCache.get(partId)
    return g === 'loading' ? null : g
  }
  if (!meshIndex[partId]) {
    geoCache.set(partId, null)
    return null
  }
  geoCache.set(partId, 'loading')
  fetch(asset(`meshes/${partId}.bin`))
    .then((r) => r.arrayBuffer())
    .then((buf) => {
      const geo = new THREE.BufferGeometry()
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(buf), 3))
      geo.computeVertexNormals()
      geoCache.set(partId, geo)
      onReady()
    })
    .catch(() => geoCache.set(partId, null))
  return null
}

export default function Preview3D({ chassis, placements, partById, catColor, level }) {
  const mountRef = useRef(null)
  const stateRef = useRef(null)
  const rebuildRef = useRef(() => {})
  const tickRef = useRef(0)

  // init once
  useEffect(() => {
    const mount = mountRef.current
    const W = mount.clientWidth
    const H = 300
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(42, W / H, 0.1, 100)

    const amb = new THREE.AmbientLight(0xbfd9ff, 0.9)
    const dir = new THREE.DirectionalLight(0xffffff, 1.4)
    dir.position.set(6, 10, 4)
    scene.add(amb, dir)

    const group = new THREE.Group()
    scene.add(group)

    const st = {
      renderer, scene, camera, group,
      theta: Math.PI / 4, phi: 1.05, dist: 9,
      target: new THREE.Vector3(0, 0.8, 0),
      dragging: false, sx: 0, sy: 0,
      raf: 0,
    }
    stateRef.current = st

    function applyCamera() {
      const { theta, phi, dist, target } = st
      camera.position.set(
        target.x + dist * Math.sin(phi) * Math.cos(theta),
        target.y + dist * Math.cos(phi),
        target.z + dist * Math.sin(phi) * Math.sin(theta),
      )
      camera.lookAt(target)
    }

    function render() {
      applyCamera()
      renderer.render(scene, camera)
    }
    st.render = render
    render()

    function onDown(e) {
      st.dragging = true
      st.sx = e.clientX
      st.sy = e.clientY
    }
    function onMove(e) {
      if (!st.dragging) return
      st.theta += (e.clientX - st.sx) * 0.008
      st.phi = Math.min(1.45, Math.max(0.25, st.phi - (e.clientY - st.sy) * 0.006))
      st.sx = e.clientX
      st.sy = e.clientY
      render()
    }
    function onUp() {
      st.dragging = false
    }
    function onWheel(e) {
      e.preventDefault()
      st.dist = Math.min(26, Math.max(4, st.dist * Math.exp(e.deltaY * 0.001)))
      render()
    }
    const el = renderer.domElement
    el.style.cursor = 'grab'
    el.addEventListener('pointerdown', onDown)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    el.addEventListener('wheel', onWheel, { passive: false })

    return () => {
      el.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      el.removeEventListener('wheel', onWheel)
      renderer.dispose()
      mount.removeChild(el)
    }
  }, [])

  // rebuild meshes when build changes (async mesh loads bump the tick)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    rebuildRef.current = () => setTick((t) => t + 1)
  }, [])
  useEffect(() => {
    const st = stateRef.current
    if (!st) return
    const { group } = st
    while (group.children.length) {
      const c = group.children.pop()
      c.traverse?.((o) => {
        if (!o.userData?.shared) o.geometry?.dispose()
        o.material?.dispose?.()
      })
      group.remove(c)
    }

    const cw = chassis.w
    const cd = chassis.d
    const ox = -cw / 2
    const oz = -cd / 2

    // chassis — real mesh when loaded, plate fallback
    const rerenderCh = () => stateRef.current && rebuildRef.current()
    const chGeo = chassis.id ? loadGeometry(chassis.id, rerenderCh) : null
    if (chGeo) {
      const chMesh = new THREE.Mesh(
        chGeo,
        new THREE.MeshStandardMaterial({ color: 0x4a6f96, metalness: 0.45, roughness: 0.55, flatShading: true }),
      )
      chMesh.userData.shared = true
      const sc = 1 / CELL_M
      chMesh.scale.setScalar(sc)
      const cb = meshIndex[chassis.id].b
      chMesh.position.set(-((cb[0] + cb[3]) / 2) * sc, -cb[4] * sc + 0.02, -((cb[2] + cb[5]) / 2) * sc)
      group.add(chMesh)
    }
    const plateGeo = new THREE.BoxGeometry(cw, 0.18, cd)
    const plate = new THREE.Mesh(
      plateGeo,
      new THREE.MeshStandardMaterial({ color: 0x16344f, metalness: 0.4, roughness: 0.6 }),
    )
    plate.position.set(0, -0.09, 0)
    group.add(plate)
    const plateEdges = new THREE.LineSegments(
      new THREE.EdgesGeometry(plateGeo),
      new THREE.LineBasicMaterial({ color: 0x8ec9ff }),
    )
    plateEdges.position.copy(plate.position)
    group.add(plateEdges)

    // grid lines on plate
    const gridMat = new THREE.LineBasicMaterial({ color: 0x3c6f9e, transparent: true, opacity: 0.6 })
    const gpts = []
    for (let i = 0; i <= cw; i++) gpts.push(new THREE.Vector3(ox + i, 0.01, oz), new THREE.Vector3(ox + i, 0.01, oz + cd))
    for (let j = 0; j <= cd; j++) gpts.push(new THREE.Vector3(ox, 0.01, oz + j), new THREE.Vector3(ox + cw, 0.01, oz + j))
    group.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(gpts), gridMat))

    // FRONT arrow (negative Z = front)
    const arrow = new THREE.Mesh(
      new THREE.ConeGeometry(0.28, 0.7, 4),
      new THREE.MeshStandardMaterial({ color: 0xffd166, emissive: 0x664d12 }),
    )
    arrow.rotation.x = -Math.PI / 2
    arrow.position.set(0, 0.06, oz - 0.8)
    group.add(arrow)

    // placements — real game meshes when available, colored box fallback
    const rerender = () => stateRef.current && rebuildRef.current()
    for (const pl of placements) {
      const p = partById[pl.partId]
      if (!p) continue
      const fw = pl.rot % 2 === 1 ? p.d : p.w
      const fd = pl.rot % 2 === 1 ? p.w : p.d
      const col = new THREE.Color(catColor[p.category] ?? '#7f96ad')
      const isCurrent = pl.z === level
      // z=-1 is the HULL: sits ON the chassis plate; decks stack above it
      const yBase = (pl.z + 1) * LEVEL_H
      const cx = ox + pl.x + fw / 2
      const cz = oz + pl.y + fd / 2
      const real = loadGeometry(pl.partId, rerender)
      if (real) {
        const mat = new THREE.MeshStandardMaterial({
          color: col,
          transparent: !isCurrent,
          opacity: isCurrent ? 1 : 0.45,
          metalness: 0.35,
          roughness: 0.6,
          flatShading: true,
        })
        const mesh = new THREE.Mesh(real, mat)
        mesh.userData.shared = true // cached geometry — never dispose
        const s = 1 / CELL_M
        mesh.scale.setScalar(s)
        // center mesh footprint on the cell footprint, base on level floor
        const b = meshIndex[pl.partId].b
        const mcx = (b[0] + b[3]) / 2
        const mcz = (b[2] + b[5]) / 2
        const mby = b[1]
        const a = (pl.rot % 4) * (Math.PI / 2)
        mesh.rotation.y = a
        const offX = mcx * Math.cos(a) + mcz * Math.sin(a)
        const offZ = -mcx * Math.sin(a) + mcz * Math.cos(a)
        mesh.position.set(cx - offX * s, yBase - mby * s, cz - offZ * s)
        group.add(mesh)
      } else {
        const geo = new THREE.BoxGeometry(fw - 0.12, LEVEL_H - 0.1, fd - 0.12)
        const mesh = new THREE.Mesh(
          geo,
          new THREE.MeshStandardMaterial({
            color: col,
            transparent: true,
            opacity: isCurrent ? 0.85 : 0.38,
            metalness: 0.2,
            roughness: 0.7,
          }),
        )
        mesh.position.set(cx, yBase + LEVEL_H / 2, cz)
        group.add(mesh)
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: isCurrent ? 1 : 0.5 }),
        )
        edges.position.copy(mesh.position)
        group.add(edges)
      }
    }

    st.render()
  }, [chassis, placements, partById, catColor, level, tick])

  return (
    <div ref={mountRef} className="preview3d">
      <div className="preview3d-hud">DRAG = ORBIT · SCROLL = ZOOM · ▲ = FRONT</div>
    </div>
  )
}
