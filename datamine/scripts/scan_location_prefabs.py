"""Scan island/POI prefab hierarchies: per prefab root, collect descendant GameObject names
that indicate spawners (loot crates, mobs, workbenches, treasures).
Output: extracted/json/location_contents.json
"""
import UnityPy, json, re, os, sys

BUNDLES = ['islands_assets_all.bundle', 'pois_assets_all.bundle']
BASE = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/'

INTEREST = re.compile(
    r'workbench|craft|spawner|spawners|loot|treasure|mob|ghoul|ironclad|militia|armybox|contract|'
    r'foodbox|partsbox|shellsbox|medical|safe|aurogen|navalmine|extraction|keyDoor|lockedDoor',
    re.I,
)

result = {}
for b in BUNDLES:
    env = UnityPy.load(BASE + b)
    objs = {}
    transforms = {}
    go_names = {}
    for obj in env.objects:
        if obj.type.name == 'Transform':
            try:
                t = obj.read_typetree()
                transforms[obj.path_id] = t
            except Exception:
                pass
        elif obj.type.name == 'GameObject':
            try:
                go_names[obj.path_id] = obj.read().m_Name
            except Exception:
                pass

    # map transform -> gameobject name, and parent links
    parent = {}
    tf_go = {}
    for pid, t in transforms.items():
        gp = t.get('m_GameObject', {})
        tf_go[pid] = gp.get('m_PathID')
        f = t.get('m_Father', {})
        parent[pid] = f.get('m_PathID', 0)

    # find root transforms (father == 0)
    roots = [pid for pid, par in parent.items() if not par or par == 0]

    # children index
    children = {}
    for pid, par in parent.items():
        if par:
            children.setdefault(par, []).append(pid)

    for r in roots:
        root_name = go_names.get(tf_go.get(r), '?')
        if not root_name or root_name == '?':
            continue
        found = {}
        stack = [r]
        count = 0
        while stack:
            cur = stack.pop()
            count += 1
            stack.extend(children.get(cur, []))
            nm = go_names.get(tf_go.get(cur), '')
            if nm and INTEREST.search(nm):
                key = nm
                found[key] = found.get(key, 0) + 1
        if found:
            entry = result.setdefault(root_name, {'bundle': b, 'nodes': 0, 'found': {}})
            entry['nodes'] += count
            for k, v in found.items():
                entry['found'][k] = entry['found'].get(k, 0) + v
    print(b, 'roots:', len(roots), 'with hits:', len(result))

os.makedirs('extracted/json', exist_ok=True)
json.dump(result, open('extracted/json/location_contents.json', 'w', encoding='utf-8'), indent=1)
print('locations recorded:', len(result))
for name in list(result)[:5]:
    print(name, '->', dict(list(result[name]['found'].items())[:8]))
