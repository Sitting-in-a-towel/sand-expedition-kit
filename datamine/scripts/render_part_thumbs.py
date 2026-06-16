"""Render isometric thumbnails for walker parts from their actual game meshes.
EPB -> ViewDataComponent name -> prefab in walker bundle -> meshes (lowest LOD) -> PNG.
Output: ../site/public/parts/<part_id>.png + parts_thumbs.json
"""
import UnityPy, json, os, re, sys, math
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from odin_parser import decode

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = '../site/public/parts'
os.makedirs(OUT, exist_ok=True)

# ---- 1. part -> view name from EPBs ----
parts = json.load(open('../site/src/data/parts.json', encoding='utf-8'))
part_ids = {p['id'] for p in parts}

env_epb = UnityPy.load(BASE + 'epb_assets_all.bundle')
objs_epb = {o.path_id: o for o in env_epb.objects}
view_of = {}
for obj in env_epb.objects:
    if obj.type.name != 'GameObject':
        continue
    go = obj.read()
    nm = go.m_Name
    if not nm.startswith('walker_') or not nm.endswith('_epb'):
        continue
    pid = nm[len('walker_'):-len('_epb')]
    if pid not in part_ids:
        continue
    comps = go.m_Component if hasattr(go, 'm_Component') else go.m_Components
    for c in comps:
        ptr = c['component'] if isinstance(c, dict) else c.component
        o = objs_epb.get(ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id)
        if not o or o.type.name != 'MonoBehaviour':
            continue
        t = o.read_typetree()
        sb = t.get('serializationData', {}).get('SerializedBytes')
        if not sb:
            continue
        try:
            doc = decode(sb)
        except Exception:
            continue
        for comp in doc.get('components', {}).get('$items', []):
            if isinstance(comp, dict) and 'ViewDataComponent' in str(comp.get('$type', '')):
                view_of[pid] = comp.get('name')
print('views resolved:', len(view_of), '/', len(part_ids))

# ---- 2. walker bundle scene graph ----
env_w = UnityPy.load(BASE + 'walker_assets_all.bundle')
objs = {o.path_id: o for o in env_w.objects}
go_name, go_tf, tf_data, mesh_cache = {}, {}, {}, {}
filters = {}  # gameobject pid -> mesh pid
for o in env_w.objects:
    t = o.type.name
    if t == 'GameObject':
        try:
            d = o.read()
            go_name[o.path_id] = d.m_Name
            comps = d.m_Component if hasattr(d, 'm_Component') else d.m_Components
            for c in comps:
                ptr = c['component'] if isinstance(c, dict) else c.component
                pid = ptr['m_PathID'] if isinstance(ptr, dict) else ptr.path_id
                co = objs.get(pid)
                if co and co.type.name == 'Transform':
                    go_tf[o.path_id] = pid
                elif co and co.type.name == 'MeshFilter':
                    mf = co.read_typetree()
                    filters[o.path_id] = mf.get('m_Mesh', {}).get('m_PathID', 0)
        except Exception:
            pass
    elif t == 'Transform':
        try:
            d = o.read_typetree()
            tf_data[o.path_id] = d
        except Exception:
            pass

children_of = {}
for pid, d in tf_data.items():
    f = d.get('m_Father', {}).get('m_PathID', 0)
    if f:
        children_of.setdefault(f, []).append(pid)

def trs(d):
    p = d['m_LocalPosition']; r = d['m_LocalRotation']; s = d['m_LocalScale']
    px, py, pz = p['x'], p['y'], p['z']
    qx, qy, qz, qw = r['x'], r['y'], r['z'], r['w']
    sx, sy, sz = s['x'], s['y'], s['z']
    R = np.array([
        [1-2*(qy*qy+qz*qz), 2*(qx*qy-qz*qw), 2*(qx*qz+qy*qw)],
        [2*(qx*qy+qz*qw), 1-2*(qx*qx+qz*qz), 2*(qy*qz-qx*qw)],
        [2*(qx*qz-qy*qw), 2*(qy*qz+qx*qw), 1-2*(qx*qx+qy*qy)],
    ])
    M = np.eye(4)
    M[:3, :3] = R @ np.diag([sx, sy, sz])
    M[:3, 3] = [px, py, pz]
    return M

def get_mesh_arrays(mesh_pid):
    if mesh_pid in mesh_cache:
        return mesh_cache[mesh_pid]
    o = objs.get(mesh_pid)
    out = None
    if o and o.type.name == 'Mesh':
        try:
            m = o.read()
            obj_txt = m.export()
            vs, fs = [], []
            for line in obj_txt.splitlines():
                if line.startswith('v '):
                    _, x, y, z = line.split()[:4]
                    vs.append((float(x), float(y), float(z)))
                elif line.startswith('f '):
                    idx = [int(p.split('/')[0]) - 1 for p in line.split()[1:4]]
                    fs.append(idx)
            if vs and fs:
                out = (np.array(vs), np.array(fs))
        except Exception:
            out = None
    mesh_cache[mesh_pid] = out
    return out

roots_by_name = {}
for pid, d in tf_data.items():
    if not d.get('m_Father', {}).get('m_PathID', 0):
        g = d.get('m_GameObject', {}).get('m_PathID')
        nm = go_name.get(g)
        if nm:
            roots_by_name.setdefault(nm, pid)

def collect(tf_pid, parent_M, acc, lod_groups):
    d = tf_data.get(tf_pid)
    if d is None:
        return
    M = parent_M @ trs(d)
    g = d.get('m_GameObject', {}).get('m_PathID')
    nm = go_name.get(g, '')
    mesh_pid = filters.get(g)
    if mesh_pid:
        m = re.search(r'_LOD(\d)', nm)
        key = re.sub(r'_LOD\d', '', nm)
        lod = int(m.group(1)) if m else -1
        cur = lod_groups.get(key)
        if cur is None or lod > cur[0]:
            lod_groups[key] = (lod, mesh_pid, M.copy())
    for ch in children_of.get(tf_pid, []):
        collect(ch, M, acc, lod_groups)

LIGHT = np.array([0.5, 0.8, 0.35])
LIGHT = LIGHT / np.linalg.norm(LIGHT)

def render(tris, path, size=160):
    # tris: (N,3,3) world coords. Isometric cam.
    yaw, pitch = math.radians(225), math.radians(-30)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    R = Rx @ Ry
    pts = tris.reshape(-1, 3) @ R.T
    pts = pts.reshape(-1, 3, 3)
    n = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
    nl = np.linalg.norm(n, axis=1)
    ok = nl > 1e-9
    pts, n, nl = pts[ok], n[ok], nl[ok]
    if len(pts) == 0:
        return False
    shade = np.abs((n / nl[:, None]) @ (R @ LIGHT))
    depth = pts[:, :, 2].mean(axis=1)
    order = np.argsort(depth)  # back to front (camera looks down -z after rotation? use ascending)
    xy = pts[:, :, :2]
    mn = xy.reshape(-1, 2).min(0)
    mx = xy.reshape(-1, 2).max(0)
    span = max((mx - mn).max(), 1e-6)
    scale = (size - 18) / span
    off = (size - (mx - mn) * scale) / 2
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    base = np.array([191, 224, 255])
    for i in order:
        p2 = (xy[i] - mn) * scale + off
        c = (base * (0.25 + 0.75 * shade[i])).astype(int)
        dr.polygon([tuple(p) for p in p2], fill=(c[0], c[1], c[2], 255))
    img.save(path)
    return True

thumbs = {}
done = 0
for pid, view in sorted(view_of.items()):
    root = roots_by_name.get(view)
    if not root:
        continue
    lod_groups = {}
    collect(root, np.eye(4), None, lod_groups)
    tris_all = []
    for lod, mesh_pid, M in lod_groups.values():
        arr = get_mesh_arrays(mesh_pid)
        if not arr:
            continue
        vs, fs = arr
        if len(fs) > 60000:
            continue
        vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
        tris_all.append(vw[fs])
    if not tris_all:
        continue
    tris = np.concatenate(tris_all)
    if len(tris) > 120000:
        tris = tris[:: max(1, len(tris) // 120000)]
    if render(tris, f'{OUT}/{pid}.png'):
        thumbs[pid] = f'/parts/{pid}.png'
        done += 1
        if done % 40 == 0:
            print(done, 'rendered…')

json.dump(thumbs, open('../site/src/data/part_thumbs.json', 'w'), indent=0)
print('thumbnails rendered:', done, '/', len(part_ids))
