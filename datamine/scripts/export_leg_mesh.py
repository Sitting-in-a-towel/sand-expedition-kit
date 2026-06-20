"""Leg mesh bake — extract the shared walker leg ('game_ironcladLeg') as ONE static
mesh in its default standing pose, for the builder to instance under every chassis.

Reuses the v4 part-bake machinery (transform graph, LOD pick, layered material/texture
resolver). Output targets the LIVE v3 asset set the builder currently loads:
  ../site/public/meshes3/_leg.bin          (same byte layout as the parts)
  ../site/public/tex3/leg<N>.png           (leg-only slots, prefixed so they can't
                                            clobber the numbered part textures)
  ../site/src/data/mesh_index_v3.json      (gets a "_leg" entry: {t,b,tex,col})

Run from datamine/scripts/:  python export_leg_mesh.py
"""
import UnityPy, json, os, re, sys, glob
import numpy as np
from PIL import Image

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = '../site/public/meshes3'
TEXOUT = '../site/public/tex3'
INDEX = '../site/src/data/mesh_index_v3.json'
MAXTEX = 512
# Player-Trampler leg (NOT game_ironcladLeg — that's the NPC ironclad). The editor
# display prefab (_view) is preferred, then the full leg prefab/model.
LEG_ROOTS = ['walker_legPart_view', 'walker_leg', 'walker_leg_model']
LOD_LEVEL = 1  # legs are background structure — LOD1 keeps instanced tri-count sane

# ---- load walker prefabs/meshes/materials + the shared-asset bundle (textures) ----
_dup = glob.glob(BASE + 'duplicateassetisolation_assets_all_*.bundle')
env = UnityPy.load(BASE + 'walker_assets_all.bundle', *_dup)
objs, objs_by_name = {}, {}
for o in env.objects:
    objs[(o.assets_file, o.path_id)] = o
    objs_by_name[(o.assets_file.name, o.path_id)] = o
print('objects:', len(objs), flush=True)

go_name, go_active, tf_data, filters, renderers = {}, {}, {}, {}, {}

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

for o in env.objects:
    t = o.type.name
    if t == 'GameObject':
        try:
            d = o.read()
            go_name[(o.assets_file, o.path_id)] = d.m_Name
            go_active[(o.assets_file, o.path_id)] = bool(getattr(d, 'm_IsActive', True))
            for c in (d.m_Component if hasattr(d, 'm_Component') else d.m_Components):
                ptr = c['component'] if isinstance(c, dict) else c.component
                co = deref(o, ptr if isinstance(ptr, dict) else {'m_PathID': ptr.path_id})
                if not co:
                    continue
                if co.type.name == 'MeshFilter':
                    filters[(o.assets_file, o.path_id)] = co.read_typetree().get('m_Mesh', {})
                elif co.type.name == 'MeshRenderer':
                    renderers[(o.assets_file, o.path_id)] = co.read_typetree().get('m_Materials', [])
        except Exception:
            pass
    elif t == 'Transform':
        try:
            tf_data[(o.assets_file, o.path_id)] = (o, o.read_typetree())
        except Exception:
            pass

children_of, roots = {}, {}
for k, (o, d) in tf_data.items():
    f = d.get('m_Father', {})
    if f.get('m_PathID', 0):
        fco = deref(o, f)
        if fco:
            children_of.setdefault((fco.assets_file, fco.path_id), []).append(k)
    gp = d.get('m_GameObject', {})
    gco = deref(o, gp)
    if gco:
        nm = go_name.get((gco.assets_file, gco.path_id))
        if nm:
            roots.setdefault(nm, []).append(k)

# ---- texture / material resolver (lifted from export_part_meshes_v4) ----
mat_cache, tex_registry = {}, {}
RES_BAKE = 256

def resolve_texture(texco):
    tid = (texco.assets_file, texco.path_id)
    if tid in tex_registry:
        return tex_registry[tid]['slot']
    slot = len(tex_registry)
    fn = f'leg{slot}.png'
    try:
        img = texco.read().image
        if img is None:
            return None
        w, h = img.size
        sc = MAXTEX / max(w, h)
        if sc < 1:
            img = img.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
        img.convert('RGB').save(f'{TEXOUT}/{fn}')
    except Exception:
        return None
    tex_registry[tid] = {'slot': slot, 'file': f'tex3/{fn}'}
    return slot

def _kv(lst):
    d = {}
    for e in lst or []:
        if isinstance(e, dict):
            n, v = e.get('first'), e.get('second')
        elif isinstance(e, (list, tuple)) and len(e) == 2:
            n, v = e
        else:
            continue
        if isinstance(n, dict):
            n = n.get('name')
        d[n] = v
    return d

def resolve_img(matco, ptr):
    if not isinstance(ptr, dict):
        return None
    fid, pid = ptr.get('m_FileID', 0), ptr.get('m_PathID', 0)
    if not pid:
        return None
    if fid == 0:
        cab = matco.assets_file.name
    else:
        exts = matco.assets_file.externals
        if fid - 1 >= len(exts):
            return None
        cab = (getattr(exts[fid - 1], 'path', '') or '').split('/')[-1]
    o = objs_by_name.get((cab, pid))
    if not o or o.type.name != 'Texture2D':
        return None
    try:
        return o.read().image.convert('RGB')
    except Exception:
        return None

def bake_layered(matco, mt):
    props = mt.get('m_SavedProperties', {})
    tex = _kv(props.get('m_TexEnvs', []))
    if not any(k and k.startswith('_DetailColorMap') for k in tex):
        return None
    flt = _kv(props.get('m_Floats', []))
    colp = _kv(props.get('m_Colors', []))

    def color(name, dflt=(1, 1, 1)):
        c = colp.get(name)
        return np.array([c['r'], c['g'], c['b']]) if isinstance(c, dict) else np.array(dflt)

    def scale_of(name):
        te = tex.get(name)
        s = te.get('m_Scale') if isinstance(te, dict) else None
        return (s.get('x', 1), s.get('y', 1)) if isinstance(s, dict) else (1, 1)

    R = RES_BAKE
    gy, gx = np.mgrid[0:R, 0:R].astype(np.float64)
    u, v = gx / R, gy / R

    def sample(img, sx, sy):
        a = np.asarray(img.resize((R, R), Image.LANCZOS), dtype=np.float64) / 255.0
        iu = ((u * sx) % 1.0 * R).astype(int) % R
        iv = ((v * sy) % 1.0 * R).astype(int) % R
        return a[iv, iu]

    result = np.ones((R, R, 3)) * color('_BaseColor')
    bm = resolve_img(matco, (tex.get('_BaseColorMap') or {}).get('m_Texture'))
    if bm is not None:
        result = result * sample(bm, *scale_of('_BaseColorMap'))
    mask_img = resolve_img(matco, (tex.get('_DetailMask') or {}).get('m_Texture'))
    mask = sample(mask_img, *scale_of('_DetailMask')) if mask_img else np.ones((R, R, 3))
    CH = {0: mask[..., 0], 1: mask[..., 1], 2: mask[..., 2], 3: np.ones((R, R))}
    applied = False
    for i in range(4):
        if not flt.get(f'_DetailHasMask{i}', 0):
            continue
        dimg = resolve_img(matco, (tex.get(f'_DetailColorMap{i}') or {}).get('m_Texture'))
        if dimg is None:
            continue
        d = sample(dimg, *scale_of(f'_DetailColorMap{i}')) * color(f'_DetailColor{i}') * flt.get(f'_DetailColorScale{i}', 1.0)
        w = np.clip(CH[i], 0, 1)[..., None]
        if flt.get(f'_DetailBlendReplace{i}', 1.0) >= 0.5:
            result = result * (1 - w) + d * w
        else:
            result = result * ((1 - w) + d * w)
        applied = True
    if not applied and bm is None:
        return None
    return Image.fromarray(np.clip(result * 255, 0, 255).astype(np.uint8))

def register_baked(matco, img):
    key = ('BAKED', matco.assets_file, matco.path_id)
    if key in tex_registry:
        return tex_registry[key]['slot']
    slot = len(tex_registry)
    fn = f'leg{slot}.png'
    img.save(f'{TEXOUT}/{fn}')
    tex_registry[key] = {'slot': slot, 'file': f'tex3/{fn}'}
    return slot

def register_solid(mt):
    colp = _kv(mt.get('m_SavedProperties', {}).get('m_Colors', []))
    c = colp.get('_BaseColor') or colp.get('_Color')
    if not isinstance(c, dict):
        return None
    rgb = (int(min(c.get('r', 0.66), 1) * 255), int(min(c.get('g', 0.66), 1) * 255), int(min(c.get('b', 0.66), 1) * 255))
    key = ('SOLID', rgb)
    if key in tex_registry:
        return tex_registry[key]['slot']
    slot = len(tex_registry)
    Image.new('RGB', (4, 4), rgb).save(f'{TEXOUT}/leg{slot}.png')
    tex_registry[key] = {'slot': slot, 'file': f'tex3/leg{slot}.png'}
    return slot

def mat_info(matco):
    key = (matco.assets_file, matco.path_id)
    if key in mat_cache:
        return mat_cache[key]
    slot, col = None, (170, 170, 170)
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
                    slot = resolve_texture(texco)
                    break
        if slot is None:
            baked = bake_layered(matco, mt)
            slot = register_baked(matco, baked) if baked is not None else register_solid(mt)
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
    mat_cache[key] = (slot, col)
    return mat_cache[key]

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
def mesh_arrays(meshco):
    mid = (meshco.assets_file, meshco.path_id)
    if mid in mesh_cache:
        return mesh_cache[mid]
    out = None
    try:
        vs, vts, vns, faces = [], [], [], []
        sub = -1
        for line in meshco.read().export().splitlines():
            if line.startswith('g '):
                m = re.search(r'_(\d+)$', line.strip())
                sub = int(m.group(1)) if m else -1
            elif line.startswith('vt '):
                _, u, v = line.split()[:3]
                vts.append((float(u), float(v)))
            elif line.startswith('v '):
                _, x, y, z = line.split()[:4]
                vs.append((float(x), float(y), float(z)))
            elif line.startswith('vn '):
                _, x, y, z = line.split()[:4]
                vns.append((float(x), float(y), float(z)))
            elif line.startswith('f '):
                toks = line.split()[1:]
                vi, ti = [], []
                for p in toks:
                    pp = p.split('/')
                    vi.append(int(pp[0]) - 1)
                    ti.append(int(pp[1]) - 1 if len(pp) > 1 and pp[1] else -1)
                for k in range(1, len(vi) - 1):
                    faces.append((max(sub, 0), vi[0], vi[k], vi[k + 1], ti[0], ti[k], ti[k + 1]))
        if vs and faces:
            out = (np.array(vs, dtype=np.float64),
                   np.array(vns, dtype=np.float64) if len(vns) == len(vs) else None,
                   np.array(vts, dtype=np.float64) if vts else None,
                   faces)
    except Exception:
        out = None
    mesh_cache[mid] = out
    return out

def collect(tfk, M, lods):
    item = tf_data.get(tfk)
    if item is None:
        return
    o, d = item
    M2 = M @ trs(d)
    gco = deref(o, d.get('m_GameObject', {}))
    gk = (gco.assets_file, gco.path_id) if gco else None
    nm = go_name.get(gk, '') if gk else ''
    if gk and (not go_active.get(gk, True) or 'Damaged' in nm):
        return
    mf = filters.get(gk)
    if mf and mf.get('m_PathID'):
        m = re.search(r'_LOD(\d)', nm)
        key = (re.sub(r'_LOD\d', '', nm),
               round(float(M2[0, 3]), 2), round(float(M2[1, 3]), 2), round(float(M2[2, 3]), 2))
        lod = int(m.group(1)) if m else -1
        lods.setdefault(key, {})[lod] = (mf, gk, M2.copy())
    for ch in children_of.get(tfk, []):
        collect(ch, M2, lods)

def pick_lod(group, level):
    prefs = {0: (0, -1, 1, 2, 3), 1: (1, 0, -1, 2, 3), 2: (2, 1, 0, -1, 3)}[level]
    for want in prefs:
        if want in group:
            return group[want]
    return group[min(group)]

# ---- find the leg root (pick the candidate transform with the most descendant meshes) ----
def count_meshes(tfk, seen=None):
    if seen is None:
        seen = set()
    if tfk in seen:
        return 0
    seen.add(tfk)
    o, d = tf_data[tfk]
    gco = deref(o, d.get('m_GameObject', {}))
    gk = (gco.assets_file, gco.path_id) if gco else None
    n = 1 if (gk and filters.get(gk, {}).get('m_PathID')) else 0
    for ch in children_of.get(tfk, []):
        n += count_meshes(ch, seen)
    return n

leg_root = None
for cand in LEG_ROOTS:
    best = None
    for tfk in roots.get(cand, []):
        c = count_meshes(tfk)
        if best is None or c > best[1]:
            best = (tfk, c)
    if best and best[1] > 0:
        leg_root = best[0]
        print(f'leg root: {cand} ({best[1]} descendant meshes)', flush=True)
        break
if leg_root is None:
    sys.exit('ERROR: no leg root found among ' + str(LEG_ROOTS))

lods = {}
collect(leg_root, np.eye(4), lods)
any_owner = next(iter(tf_data.values()))[0]

pos_chunks, nrm_chunks, uv_chunks, slot_chunks = [], [], [], []
part_tex, part_tex_files, part_tex_cols = {}, [], []
for key, group in lods.items():
    mf, gk, M = pick_lod(group, LOD_LEVEL)
    mco = deref(any_owner, mf)
    if not mco:
        continue
    arr = mesh_arrays(mco)
    if not arr:
        continue
    vs, vns, vts, faces = arr
    mats = renderers.get(gk, [])
    vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
    R = M[:3, :3]
    if vns is not None:
        nw = vns @ np.linalg.inv(R).T if abs(np.linalg.det(R)) > 1e-9 else vns
        nw = nw / np.maximum(np.linalg.norm(nw, axis=1, keepdims=True), 1e-9)
    f_arr = np.array([(f[1], f[2], f[3]) for f in faces])
    t_arr = np.array([(f[4], f[5], f[6]) for f in faces])
    sub_arr = np.array([f[0] for f in faces])
    tri_pos = vw[f_arr]
    if vns is not None:
        tri_nrm = nw[f_arr]
    else:
        e1 = tri_pos[:, 1] - tri_pos[:, 0]
        e2 = tri_pos[:, 2] - tri_pos[:, 0]
        fn = np.cross(e1, e2)
        fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
        tri_nrm = np.repeat(fn[:, None, :], 3, axis=1)
    if vts is not None and (t_arr >= 0).all():
        tri_uv = vts[t_arr]
    else:
        tri_uv = np.zeros((len(faces), 3, 2))
    slots = np.zeros(len(faces), dtype=np.uint8)
    for si in np.unique(sub_arr):
        matref = mats[min(si, len(mats) - 1)] if mats else None
        gslot, col = (None, (170, 170, 170))
        if matref and matref.get('m_PathID'):
            matco = deref(any_owner, matref)
            if matco and matco.type.name == 'Material':
                gslot, col = mat_info(matco)
        if gslot is None:
            local = 255
        else:
            if gslot not in part_tex:
                part_tex[gslot] = len(part_tex_files)
                reg = next(r for r in tex_registry.values() if r['slot'] == gslot)
                part_tex_files.append(reg['file'])
                part_tex_cols.append(list(col))
            local = part_tex[gslot]
        slots[sub_arr == si] = local
    pos_chunks.append(tri_pos)
    nrm_chunks.append(tri_nrm)
    uv_chunks.append(tri_uv)
    slot_chunks.append(slots)

if not pos_chunks:
    sys.exit('ERROR: leg root had no meshes to bake')

tris = np.concatenate(pos_chunks)
nrms = np.concatenate(nrm_chunks)
uvs = np.concatenate(uv_chunks)
slots = np.concatenate(slot_chunks)
# match the v3/v4 part convention: flip Z + reverse winding so it sits in the same space
tris[:, :, 2] *= -1
nrms[:, :, 2] *= -1
tris = tris[:, ::-1, :]
nrms = nrms[:, ::-1, :]
uvs = uvs[:, ::-1, :]
t = len(tris)
nrm_q = np.clip(np.round(nrms * 127), -127, 127).astype(np.int8)
buf = (tris.astype(np.float32).tobytes() + nrm_q.tobytes() +
       uvs.astype(np.float32).tobytes() + slots.astype(np.uint8).tobytes())
open(f'{OUT}/_leg.bin', 'wb').write(buf)
b = tris.reshape(-1, 3)
mn, mx = b.min(0), b.max(0)

idx = json.load(open(INDEX, encoding='utf-8'))
idx['_leg'] = {'t': int(t), 'b': [round(float(v), 3) for v in (*mn, *mx)], 'l': LOD_LEVEL,
               'tex': part_tex_files, 'col': part_tex_cols}
json.dump(idx, open(INDEX, 'w'), separators=(',', ':'))
print(f'_leg baked: tris={t} bbox={[round(float(v),2) for v in (*mn,*mx)]} '
      f'tex={len(part_tex_files)} -> {OUT}/_leg.bin')
