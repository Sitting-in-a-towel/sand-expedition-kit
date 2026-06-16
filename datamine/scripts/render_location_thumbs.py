"""Render isometric art for map locations.

SAND locations are NOT baked meshes — each location prefab is a hierarchy of GameObjects
carrying an Odin 'blueprint' MonoBehaviour whose `blueprintName` names a module prefab
(env_*/prop_*/game_* roots living in the pois bundle, meshes resolving into the geometry
bundle). We assemble a triangle soup per location by stamping each module's cached mesh
soup at the instance's world transform, then software-render it sepia for the parchment
Ops Board. Procedural pieces (houses built at runtime from seeds) can't be reproduced —
islands render as their authored bones (terrain stamps, walls, ships, factories, props).

Output: ../site/public/locart/<root>.png + ../site/src/data/location_art.json
        (keyed by site location id, same matching as build_location_contents.py)
"""
import UnityPy, json, os, re, sys, math
import numpy as np
from PIL import Image, ImageDraw

BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'
OUT = '../site/public/locart'
os.makedirs(OUT, exist_ok=True)

# ---- site location matching (same logic as build_location_contents.py) ----
site_locs = json.load(open('../site/src/data/locations.json', encoding='utf-8'))
extra_locs = json.load(open('../site/src/data/extra_locations.json', encoding='utf-8'))
extra_ids = {e['id'] for e in extra_locs}

def norm(s):
    s = s.lower()
    s = re.sub(r'^(island_|poi_|env_)', '', s)
    s = re.sub(r'(_?demo_?|_noab|_single|_v\d+)', '', s)
    return re.sub(r'[^a-z0-9]', '', s)

by_norm = {norm(l['id']): l['id'] for l in site_locs}

def match_loc(root):
    n = norm(root)
    if n in by_norm:
        return by_norm[n]
    best = None
    for k, v in by_norm.items():
        if len(k) >= 5 and len(n) >= 5 and (k in n or n in k):
            if best is None or len(k) > len(best[0]):
                best = (k, v)
    return best[1] if best else None

def wanted(root_name):
    if re.search(r'test|playground|exhibition', root_name, re.I):
        return None
    if ('extra_' + root_name) in extra_ids:
        return 'extra_' + root_name
    return match_loc(root_name)

print('loading bundles…', flush=True)
env = UnityPy.load(
    BASE + 'islands_assets_all.bundle',
    BASE + 'pois_assets_all.bundle',
    BASE + 'geometry_assets_all.bundle',
)

geo_ids = set()
for path, bf in env.files.items():
    if 'geometry' in str(path).lower():
        for sf in getattr(bf, 'files', {}).values():
            geo_ids.add(id(sf))
            for sub in getattr(sf, 'files', {}).values():
                geo_ids.add(id(sub))

key = lambda o: (id(o.assets_file), o.path_id)

go_name, filters, tf_tree, blueprint_of = {}, {}, {}, {}
print('indexing objects…', flush=True)
for o in env.objects:
    t = o.type.name
    # geometry bundle holds the module prefabs + meshes — index its scene objects,
    # but skip its MonoBehaviours (only islands/pois carry blueprint components)
    if t == 'MonoBehaviour' and id(o.assets_file) in geo_ids:
        continue
    try:
        if t == 'GameObject':
            d = o.read()
            go_name[key(o)] = d.m_Name
            comps = d.m_Component if hasattr(d, 'm_Component') else d.m_Components
            for c in comps:
                ptr = c['component'] if isinstance(c, dict) else c.component
                try:
                    co = ptr.deref() if hasattr(ptr, 'deref') else None
                except Exception:
                    co = None
                if co is not None and co.type.name == 'MeshFilter':
                    filters[key(o)] = co
        elif t == 'Transform':
            tf_tree[key(o)] = o.read_typetree()
        elif t == 'MonoBehaviour':
            tt = o.read_typetree()
            bn = tt.get('blueprintName')
            if bn:
                g = tt.get('m_GameObject', {})
                blueprint_of[(id(o.assets_file), g.get('m_PathID'))] = bn
    except Exception:
        pass

parent, children_of, tf_go = {}, {}, {}
for k, d in tf_tree.items():
    g = d.get('m_GameObject', {})
    tf_go[k] = (k[0], g.get('m_PathID'))
    f = d.get('m_Father', {}).get('m_PathID', 0)
    fk = (k[0], f) if f else None
    parent[k] = fk
    if fk:
        children_of.setdefault(fk, []).append(k)

# transform pid by gameobject key (for module-root lookup)
tf_of_go = {g: k for k, g in tf_go.items()}

# module prefab roots by name (pois bundle mostly)
module_root = {}
for k, par in parent.items():
    if par is None:
        nm = go_name.get(tf_go.get(k), '')
        if nm and nm not in module_root:
            module_root[nm] = k

mesh_cache = {}

def get_mesh(mf_obj):
    try:
        mf = mf_obj.read()
        mptr = mf.m_Mesh
        mk = (getattr(mptr, 'file_id', 0), getattr(mptr, 'path_id', 0), id(mf_obj.assets_file))
        if mk in mesh_cache:
            return mesh_cache[mk]
        m = mptr.read()
        obj_txt = m.export()
        vs, fs = [], []
        for line in obj_txt.splitlines():
            if line.startswith('v '):
                _, x, y, z = line.split()[:4]
                vs.append((float(x), float(y), float(z)))
            elif line.startswith('f '):
                idx = [int(p.split('/')[0]) - 1 for p in line.split()[1:4]]
                fs.append(idx)
        out = (np.array(vs), np.array(fs)) if vs and fs else None
        mesh_cache[mk] = out
        return out
    except Exception:
        return None


def trs(d):
    p = d['m_LocalPosition']; r = d['m_LocalRotation']; s = d['m_LocalScale']
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


SKIP_NODE = re.compile(r'water|ocean|cloud|fog|volume|light|probe|collider|trigger|navmesh|audio', re.I)

module_soup_cache = {}

def module_soup(name):
    """Triangle soup (module-local space) for a module prefab, lowest-detail LOD."""
    if name in module_soup_cache:
        return module_soup_cache[name]
    root = module_root.get(name)
    out = None
    if root is not None:
        lod_groups = {}
        stack = [(root, np.eye(4))]
        while stack:
            cur, parent_M = stack.pop()
            d = tf_tree.get(cur)
            if d is None:
                continue
            M = parent_M @ trs(d)
            gk = tf_go.get(cur)
            nm = go_name.get(gk, '')
            if not SKIP_NODE.search(nm or ''):
                mf = filters.get(gk)
                if mf is not None:
                    m = re.search(r'_LOD(\d)', nm)
                    gname = (parent.get(cur), re.sub(r'_LOD\d', '', nm)) if m else (cur, nm)
                    lod = int(m.group(1)) if m else -1
                    cur_best = lod_groups.get(gname)
                    if cur_best is None or lod > cur_best[0]:
                        lod_groups[gname] = (lod, mf, M.copy())
                for ch in children_of.get(cur, []):
                    stack.append((ch, M))
            else:
                continue
        tris_all = []
        for lod, mf, M in lod_groups.values():
            arr = get_mesh(mf)
            if not arr:
                continue
            vs, fs = arr
            if len(fs) > 20000:
                fs = fs[:: max(1, len(fs) // 20000)]
            vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
            tris_all.append(vw[fs])
        if tris_all:
            out = np.concatenate(tris_all)
    module_soup_cache[name] = out
    return out


LIGHT = np.array([0.5, 0.8, 0.35])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
BASE_COL = np.array([122, 84, 38])
HI_COL = np.array([226, 196, 138])


def render(tris, path, size=240):
    yaw, pitch = math.radians(225), math.radians(-32)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    R = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    pts = (tris.reshape(-1, 3) @ R.T).reshape(-1, 3, 3)
    n = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
    nl = np.linalg.norm(n, axis=1)
    ok = nl > 1e-9
    pts, n, nl = pts[ok], n[ok], nl[ok]
    if len(pts) == 0:
        return False
    shade = np.abs((n / nl[:, None]) @ (R @ LIGHT))
    order = np.argsort(pts[:, :, 2].mean(axis=1))
    xy = pts[:, :, :2]
    mn = xy.reshape(-1, 2).min(0)
    mx = xy.reshape(-1, 2).max(0)
    span = max((mx - mn).max(), 1e-6)
    scale = (size - 22) / span
    off = (size - (mx - mn) * scale) / 2
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for i in order:
        p2 = (xy[i] - mn) * scale + off
        c = (BASE_COL + (HI_COL - BASE_COL) * shade[i]).astype(int)
        dr.polygon([tuple(p) for p in p2], fill=(c[0], c[1], c[2], 255))
    img.save(path)
    return True


loc_roots = []
for k, par in parent.items():
    if par is None:
        nm = go_name.get(tf_go.get(k), '')
        if nm:
            loc_id = wanted(nm)
            if loc_id:
                loc_roots.append((k, nm, loc_id))
print('wanted location roots:', len(loc_roots), flush=True)

missing_modules = {}
results, art = {}, {}
done = 0
for root_k, root_name, loc_id in sorted(loc_roots, key=lambda x: x[1]):
    fn = re.sub(r'[^A-Za-z0-9_-]', '_', root_name)
    out_path = f'{OUT}/{fn}.png'
    if os.path.exists(out_path):
        results[root_name] = f'locart/{fn}.png'
        art.setdefault(loc_id, f'locart/{fn}.png')
        continue
    tris_all = []
    total = 0
    stack = [(root_k, np.eye(4))]
    nodes = 0
    while stack and total < 900000:
        cur, parent_M = stack.pop()
        d = tf_tree.get(cur)
        if d is None:
            continue
        nodes += 1
        if nodes > 200000:
            break
        M = parent_M @ trs(d)
        gk = tf_go.get(cur)
        nm = go_name.get(gk, '')
        if SKIP_NODE.search(nm or ''):
            continue
        # direct meshes (rare) — e.g. terrain plates
        mf = filters.get(gk)
        if mf is not None:
            arr = get_mesh(mf)
            if arr:
                vs, fs = arr
                if len(fs) > 40000:
                    fs = fs[:: max(1, len(fs) // 40000)]
                vw = (np.c_[vs, np.ones(len(vs))] @ M.T)[:, :3]
                tris_all.append(vw[fs])
                total += len(fs)
        # blueprint module instance
        bn = blueprint_of.get(gk)
        if bn:
            soup = module_soup(bn)
            if soup is None:
                missing_modules[bn] = missing_modules.get(bn, 0) + 1
            else:
                t4 = np.c_[soup.reshape(-1, 3), np.ones(len(soup) * 3)] @ M.T
                tris_all.append(t4[:, :3].reshape(-1, 3, 3))
                total += len(soup)
        for ch in children_of.get(cur, []):
            stack.append((ch, M))
    if not tris_all:
        continue
    tris = np.concatenate(tris_all)
    if len(tris) > 220000:
        tris = tris[:: max(1, len(tris) // 220000)]
    try:
        if render(tris, out_path):
            results[root_name] = f'locart/{fn}.png'
            art.setdefault(loc_id, f'locart/{fn}.png')
            done += 1
            print(f'{done}: {root_name} -> {loc_id} ({len(tris)} tris)', flush=True)
    except Exception as e:
        print('FAIL', root_name, e, flush=True)

json.dump(results, open('extracted/json/location_art_roots.json', 'w', encoding='utf-8'), indent=1)
json.dump(art, open('../site/src/data/location_art.json', 'w', encoding='utf-8'), indent=1)
print('rendered:', done, '| art entries:', len(art))
if missing_modules:
    top = sorted(missing_modules.items(), key=lambda x: -x[1])[:15]
    print('missing modules (top):', top)
