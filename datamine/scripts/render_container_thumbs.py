"""Render the loot containers (crates, safes, food/medical boxes, treasure, mines…)
from their real game models WITH albedo textures, for the Loot page picker tiles.

Visual prefab roots live in views_assets_all.bundle; meshes resolve from
geometry_assets_all.bundle; the albedo textures (shared trim/atlas set) resolve
from the duplicateassetisolation bundle. We walk each root's hierarchy, take the
lowest-detail LOD per mesh, and for each triangle sample the material's albedo
texture at the UV centroid (falling back to _BaseColor) so the thumbnail shows the
real surface colours/material — not flat grey.

Output: ../site/public/containers/<key>.png + ../site/src/data/container_art.json
"""
import UnityPy, json, os, re, math
import numpy as np
from PIL import Image, ImageDraw

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = '../site/public/containers'
os.makedirs(OUT, exist_ok=True)

SOURCE_VIEW = {
    'Weapons Crate':     'game_armyBox_t1',
    'Resource Crate':    'game_partsBox_t1',
    'Food Crate':        'game_foodBox_t1',
    'Medical Cabinet':   'game_medicalCabinet_t1',
    'Safe':              'game_safeMiddle_t1',
    'Shell Box':         'game_cannonShellsBox_t1',
    # 'Buried Treasure' visual is a runtime-spawned chest (no static mesh) — keeps icon
    'Buried Treasure':   'game_buriedTreasure',
    'Ironclad Loot Box': 'item_ironcladContainer',
    'Mob Drops':         'game_lootBag',
    'Aurogen Crystal':   'game_aurogenCrystal1',
    'Naval Mine':        'game_navalMine',
    'Militia Box':       'game_militiaBox_40mm',
}

print('loading bundles…', flush=True)
env = UnityPy.load(BASE + 'views_assets_all.bundle',
                   BASE + 'geometry_assets_all.bundle',
                   BASE + 'duplicateassetisolation_assets_all_fb84156cf155cf0afd68566bd5e732f9.bundle')
objs = {(o.assets_file, o.path_id): o for o in env.objects}
key = lambda o: (o.assets_file, o.path_id)

def deref(owner, ptr):
    pid = ptr.get('m_PathID', 0) if isinstance(ptr, dict) else getattr(ptr, 'm_PathID', 0)
    if not pid:
        return None
    try:
        if hasattr(ptr, 'deref'):
            return ptr.deref()
    except Exception:
        pass
    o = objs.get((owner.assets_file, pid))
    if o:
        return o
    for (af, p), oo in objs.items():
        if p == pid:
            return oo
    return None

go_name, tf_tree, filters, renderers = {}, {}, {}, {}
for o in env.objects:
    t = o.type.name
    try:
        if t == 'GameObject':
            d = o.read()
            go_name[key(o)] = d.m_Name
            for c in (d.m_Component if hasattr(d, 'm_Component') else d.m_Components):
                ptr = c['component'] if isinstance(c, dict) else c.component
                co = deref(o, ptr if isinstance(ptr, dict) else {'m_PathID': ptr.path_id})
                if not co:
                    continue
                if co.type.name == 'MeshFilter':
                    filters[key(o)] = co.read_typetree().get('m_Mesh', {})
                elif co.type.name == 'MeshRenderer':
                    renderers[key(o)] = co.read_typetree().get('m_Materials', [])
        elif t == 'Transform':
            tf_tree[key(o)] = (o, o.read_typetree())
    except Exception:
        pass

children_of, root_tf = {}, {}
for k, (o, d) in tf_tree.items():
    f = d.get('m_Father', {})
    if f.get('m_PathID', 0):
        fco = deref(o, f)
        if fco:
            children_of.setdefault((fco.assets_file, fco.path_id), []).append(k)
    else:
        gco = deref(o, d.get('m_GameObject', {}))
        if gco:
            nm = go_name.get((gco.assets_file, gco.path_id))
            if nm:
                root_tf.setdefault(nm, k)

# material -> (albedo PIL image or None, base colour)
mat_cache = {}
tex_img_cache = {}
def tex_image(texco):
    tid = (texco.assets_file, texco.path_id)
    if tid in tex_img_cache:
        return tex_img_cache[tid]
    img = None
    try:
        im = texco.read().image
        if im is not None:
            im = im.convert('RGB')
            if max(im.size) > 256:
                sc = 256 / max(im.size)
                im = im.resize((max(1, int(im.size[0] * sc)), max(1, int(im.size[1] * sc))))
            img = np.asarray(im)
    except Exception:
        img = None
    tex_img_cache[tid] = img
    return img

def mat_info(matco):
    k = (matco.assets_file, matco.path_id)
    if k in mat_cache:
        return mat_cache[k]
    img, col = None, (170, 165, 150)
    try:
        mt = matco.read_typetree()
        props = mt.get('m_SavedProperties', {})
        slots = {}
        for te in props.get('m_TexEnvs', []):
            if isinstance(te, dict):
                slots[te.get('first')] = te.get('second')
            elif isinstance(te, (list, tuple)) and len(te) == 2:
                slots[te[0]] = te[1]
        for s in ('_BaseMap', '_MainTex', '_BaseColorMap'):
            te = slots.get(s)
            if te and te.get('m_Texture', {}).get('m_PathID'):
                texco = deref(matco, te['m_Texture'])
                if texco and texco.type.name == 'Texture2D':
                    img = tex_image(texco)
                    break
        cols = {}
        for c in props.get('m_Colors', []):
            if isinstance(c, dict):
                cols[c.get('first')] = c.get('second')
            elif isinstance(c, (list, tuple)) and len(c) == 2:
                cols[c[0]] = c[1]
        v = cols.get('_BaseColor') or cols.get('_Color')
        if v:
            col = (int(min(v['r'], 1) * 255), int(min(v['g'], 1) * 255), int(min(v['b'], 1) * 255))
    except Exception:
        pass
    mat_cache[k] = (img, col)
    return mat_cache[k]

def sample(img, u, v):
    if img is None:
        return None
    h, w = img.shape[:2]
    x = int((u % 1.0) * (w - 1)); y = int(((1 - (v % 1.0)) % 1.0) * (h - 1))
    px = img[y, x]
    return (int(px[0]), int(px[1]), int(px[2]))

def trs(d):
    p, r, s = d['m_LocalPosition'], d['m_LocalRotation'], d['m_LocalScale']
    qx, qy, qz, qw = r['x'], r['y'], r['z'], r['w']
    R = np.array([
        [1-2*(qy*qy+qz*qz), 2*(qx*qy-qz*qw), 2*(qx*qz+qy*qw)],
        [2*(qx*qy+qz*qw), 1-2*(qx*qx+qz*qz), 2*(qy*qz-qx*qw)],
        [2*(qx*qz-qy*qw), 2*(qy*qz+qx*qw), 1-2*(qx*qx+qy*qy)],
    ])
    M = np.eye(4)
    M[:3, :3] = R @ np.diag([s['x'], s['y'], s['z']])
    M[:3, 3] = [p['x'], p['y'], p['z']]
    return M

mesh_cache = {}
def get_mesh(meshco):
    mid = (meshco.assets_file, meshco.path_id)
    if mid in mesh_cache:
        return mesh_cache[mid]
    out = None
    try:
        vs, vts, faces = [], [], []
        sub = -1
        for line in meshco.read().export().splitlines():
            if line.startswith('g '):
                m = re.search(r'_(\d+)$', line.strip()); sub = int(m.group(1)) if m else -1
            elif line.startswith('vt '):
                _, u, v = line.split()[:3]; vts.append((float(u), float(v)))
            elif line.startswith('v '):
                _, x, y, z = line.split()[:4]; vs.append((float(x), float(y), float(z)))
            elif line.startswith('f '):
                toks = line.split()[1:]
                vi, ti = [], []
                for p in toks:
                    pp = p.split('/')
                    vi.append(int(pp[0]) - 1)
                    ti.append(int(pp[1]) - 1 if len(pp) > 1 and pp[1] else -1)
                for k in range(1, len(vi) - 1):
                    faces.append((max(sub, 0), vi[0], vi[k], vi[k+1], ti[0], ti[k], ti[k+1]))
        if vs and faces:
            out = (np.array(vs), np.array(vts) if vts else None, faces)
    except Exception:
        out = None
    mesh_cache[mid] = out
    return out

LIGHT = np.array([0.5, 0.85, 0.4]); LIGHT = LIGHT / np.linalg.norm(LIGHT)
SKIP = re.compile(r'vfx|fps|decal|smoke|fire|light|shadow|collider|_door', re.I)

def render(tris, cols, path, size=256):
    yaw, pitch = math.radians(228), math.radians(-30)
    cy, sy = math.cos(yaw), math.sin(yaw); cp, sp = math.cos(pitch), math.sin(pitch)
    R = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    pts = (tris.reshape(-1, 3) @ R.T).reshape(-1, 3, 3)
    n = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
    nl = np.linalg.norm(n, axis=1)
    ok = nl > 1e-9
    pts, n, nl, cols = pts[ok], n[ok], nl[ok], cols[ok]
    if len(pts) == 0:
        return False
    shade = 0.62 + 0.5 * np.abs((n / nl[:, None]) @ (R @ LIGHT))  # higher ambient floor + gain
    order = np.argsort(pts[:, :, 2].mean(axis=1))
    xy = pts[:, :, :2]
    mn = xy.reshape(-1, 2).min(0); mx = xy.reshape(-1, 2).max(0)
    span = max((mx - mn).max(), 1e-6)
    scale = (size - 30) / span
    off = (size - (mx - mn) * scale) / 2
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for i in order:
        p2 = (xy[i] - mn) * scale + off
        c = np.clip(cols[i] * shade[i] * 1.35, 0, 255).astype(int)  # brighten muddy prop albedo
        dr.polygon([tuple(p) for p in p2], fill=(int(c[0]), int(c[1]), int(c[2]), 255))
    img.save(path)
    return True

art = {}
for name, root_name in SOURCE_VIEW.items():
    rtf = root_tf.get(root_name)
    if rtf is None:
        print('  MISSING view root:', root_name, '->', name, flush=True)
        continue
    lod_groups = {}
    stack = [(rtf, np.eye(4))]
    while stack:
        cur, pM = stack.pop()
        item = tf_tree.get(cur)
        if item is None:
            continue
        o, d = item
        M = pM @ trs(d)
        gco = deref(o, d.get('m_GameObject', {}))
        gk = (gco.assets_file, gco.path_id) if gco else None
        nm = go_name.get(gk, '') if gk else ''
        if not SKIP.search(nm or ''):
            mf = filters.get(gk)
            if mf and mf.get('m_PathID'):
                m = re.search(r'_LOD(\d)', nm)
                gname = re.sub(r'_LOD\d', '', nm) + f'@{cur[1]}'
                lod = int(m.group(1)) if m else -1
                cur_best = lod_groups.get(gname)
                if cur_best is None or lod > cur_best[0]:
                    lod_groups[gname] = (lod, mf, gk, M.copy())
            for ch in children_of.get(cur, []):
                stack.append((ch, M))
    tris_all, cols_all = [], []
    for lod, mf, gk, M in lod_groups.values():
        mco = deref(next(iter(tf_tree.values()))[0], mf)
        if not mco:
            continue
        arr = get_mesh(mco)
        if not arr:
            continue
        vs, vts, faces = arr
        mats = renderers.get(gk, [])
        vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
        f_arr = np.array([(f[1], f[2], f[3]) for f in faces])
        t_arr = np.array([(f[4], f[5], f[6]) for f in faces])
        sub_arr = np.array([f[0] for f in faces])
        tri = vw[f_arr]
        cols = np.zeros((len(faces), 3))
        for si in np.unique(sub_arr):
            matref = mats[min(si, len(mats) - 1)] if mats else None
            img, base = (None, (170, 165, 150))
            if matref and matref.get('m_PathID'):
                matco = deref(next(iter(tf_tree.values()))[0], matref)
                if matco and matco.type.name == 'Material':
                    img, base = mat_info(matco)
            idxs = np.where(sub_arr == si)[0]
            for i in idxs:
                c = None
                if img is not None and vts is not None and (t_arr[i] >= 0).all():
                    uv = vts[t_arr[i]].mean(axis=0)
                    c = sample(img, uv[0], uv[1])
                cols[i] = c if c else base
        tris_all.append(tri)
        cols_all.append(cols)
    if not tris_all:
        print('  no meshes for', name, flush=True)
        continue
    tris = np.concatenate(tris_all)
    cols = np.concatenate(cols_all)
    fn = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_').lower()
    if render(tris, cols, f'{OUT}/{fn}.png'):
        art[name] = f'containers/{fn}.png'
        print(f'  {name} -> {fn}.png ({len(tris)} tris, textured)', flush=True)

json.dump(art, open('../site/src/data/container_art.json', 'w', encoding='utf-8'), indent=1)
print('container art entries:', len(art))
