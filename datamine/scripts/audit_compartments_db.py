"""Audit CompartmentsDatabase vs current parts.json name-parsed footprints."""
import json, re
from collections import Counter

db = json.load(open('extracted/json/compartments_database.json', encoding='utf-8-sig'))
comps = db['compartments']
parts = {p['id']: p for p in json.load(open('../site/src/data/parts.json', encoding='utf-8'))}

print('total compartments:', len(comps))
print('enabled:', sum(1 for c in comps if c['enabled']))
print('rotationEnabled=False:', [c['entityId'] for c in comps if not c['rotationEnabled']])
print('with mirror:', sum(1 for c in comps if c.get('mirrorEntityId')))
print('groups:', Counter(g for c in comps for g in c['group']))
print()

mismatch, nomatch, multilevel = [], [], []
for c in comps:
    eid = c['entityId']
    pid = re.sub(r'^walker_', '', re.sub(r'_epb$', '', eid))
    cells = c['cells']
    xs = [cl['position']['x'] for cl in cells]
    ys = [cl['position']['y'] for cl in cells]
    zs = [cl['position']['z'] for cl in cells]
    w = max(xs) - min(xs) + 1
    h = max(ys) - min(ys) + 1
    d = max(zs) - min(zs) + 1
    n = len(cells)
    if h > 1:
        multilevel.append((pid, w, h, d, n))
    p = parts.get(pid)
    if not p:
        nomatch.append(pid)
        continue
    # name-parsed footprint w x d; true bounding w x d (x=width, z=depth)
    if {p['w'], p['d']} != {w, d}:
        mismatch.append((pid, f"name {p['w']}x{p['d']}", f"true {w}x{d} ({n} cells, {h} lvl)"))

print('FOOTPRINT MISMATCHES (name vs DB):', len(mismatch))
for m in mismatch:
    print('  ', *m)
print()
print('multi-level parts (h>1):', len(multilevel))
for m in multilevel:
    print('  ', m)
print()
print('DB parts missing from parts.json:', len(nomatch), nomatch)
print()
site_only = [pid for pid in parts if 'walker_' + pid + '_epb' not in {c['entityId'] for c in comps}
             and not any(c.get('mirrorEntityId') == 'walker_' + pid + '_epb' for c in comps)]
print('site parts NOT in DB (not placeable in-game):', len(site_only))
print(sorted(site_only)[:60])

# editable socket stats (door/window conversion points)
ed = Counter()
for c in comps:
    for cl in c['cells']:
        for dirn, socks in cl['sockets'].items():
            for st, si in socks.items():
                if si.get('editable'):
                    ed[st] += 1
print()
print('editable sockets across DB by type:', dict(ed))
