"""Process location_contents.json into per-location summaries for the site.
Output: site/src/data/location_contents.json keyed by lootset location id where matchable.
"""
import json, re

raw = json.load(open('extracted/json/location_contents.json', encoding='utf-8'))
site_locs = json.load(open('../site/src/data/locations.json', encoding='utf-8'))

def norm(s):
    s = s.lower()
    s = re.sub(r'^(island_|poi_|env_)', '', s)
    s = re.sub(r'(_?demo_?|_noab|_single|_v\d+)', '', s)
    return re.sub(r'[^a-z0-9]', '', s)

CRATE = {
    'armybox': 'Weapons Crate', 'foodbox': 'Food Crate', 'partsbox': 'Resource Crate',
    'shellsbox': 'Shell Crate', 'medicalcabinet': 'Med Crate', 'safemiddle': 'Valuables Crate',
    'safe': 'Valuables Crate', 'militiabox': 'Shell Crate',
}

def classify(name):
    n = name.lower()
    n = re.sub(r'_epb(_\d+)?$', '', n)
    n = re.sub(r'^game_', '', n)
    if 'workbench' in n or 'craftingpress' in n or 'craftingresult' in n or ('craft' in n and 'spawner' not in n):
        return ('bench', 'Crafting station')
    for k, v in CRATE.items():
        if k in n:
            return ('crate', v)
    if 'buriedtreasure' in n or 'treasure' in n:
        return ('treasure', 'Buried Treasure')
    if 'aurogen' in n or 'crystal' in n:
        return ('treasure', 'Aurogen Crystal')
    if 'artefact' in n:
        return ('treasure', 'Artefact')
    if re.search(r'aispawner|ainest|aiambush|ghoul|ironclad|sentinel|mobspawner|nest', n):
        return ('mob', 'Mob spawner')
    if 'supervisor' in n:
        return ('mob', 'Spawn supervisor')
    if 'lockabledoor' in n or 'lockeddoor' in n or 'keydoor' in n or 'lockedbox' in n or 'key' in n:
        return ('locked', 'Locked loot (key)')
    if 'itemspawner' in n:
        m = re.sub(r'^itemspawner', '', n)
        return ('item', m or 'item')
    if 'lootspawner' in n or n in ('lootspawners', 'spawners', 'gamespawners', 'itemspawners'):
        return (None, None)
    return (None, None)

by_norm = {}
for l in site_locs:
    by_norm[norm(l['id'])] = l['id']

def match_loc(root):
    n = norm(root)
    if n in by_norm:
        return by_norm[n]
    # containment both ways (handles Raumnadel vs Raumnadel_Village, VenedigSmall vs Venedig)
    best = None
    for k, v in by_norm.items():
        if len(k) >= 5 and len(n) >= 5 and (k in n or n in k):
            if best is None or len(k) > len(best[0]):
                best = (k, v)
    return best[1] if best else None

out = {}
unmatched = []
for root, data in raw.items():
    summary = {'benches': 0, 'crates': {}, 'treasures': {}, 'mobs': 0, 'locked': 0, 'items': {}}
    for name, count in data['found'].items():
        kind, label = classify(name)
        if kind == 'bench':
            summary['benches'] += count
        elif kind == 'crate':
            summary['crates'][label] = summary['crates'].get(label, 0) + count
        elif kind == 'treasure':
            summary['treasures'][label] = summary['treasures'].get(label, 0) + count
        elif kind == 'mob':
            summary['mobs'] += count
        elif kind == 'locked':
            summary['locked'] += count
        elif kind == 'item':
            summary['items'][label] = summary['items'].get(label, 0) + count
    if not any([summary['benches'], summary['crates'], summary['treasures'], summary['mobs'], summary['locked'], summary['items']]):
        continue
    key = match_loc(root)
    if key:
        prev = out.get(key)
        if prev:
            # merge (multiple prefab roots may map to one location)
            prev['benches'] += summary['benches']
            prev['mobs'] += summary['mobs']
            prev['locked'] += summary['locked']
            for f in ('crates', 'treasures', 'items'):
                for k, v in summary[f].items():
                    prev[f][k] = prev[f].get(k, 0) + v
        else:
            out[key] = summary
    else:
        unmatched.append(root)

json.dump(out, open('../site/src/data/location_contents.json', 'w', encoding='utf-8'), indent=1)

# unmatched real locations (forts, events, factories…) become extra site locations
def pretty_root(r):
    s = re.sub(r'^(island_|loc_event_|env_|poi_|POI)', '', r)
    s = re.sub(r'_?(Demo|NoAB|test\w*)_?', '', s, flags=re.I)
    s = s.replace('_', ' ').strip()
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', s)
    return ' '.join(w.capitalize() if not w.isupper() else w for w in s.split())

def root_kind(r):
    n = r.lower()
    if 'fort' in n:
        return 'fort'
    if 'event' in n:
        return 'event'
    if 'wreck' in n or 'gunboat' in n or 'ship' in n or 'graveyard' in n:
        return 'ship'
    if 'rock' in n or 'underground' in n or 'pollarge' in n:
        return 'rock'
    if n.startswith('poi_') or n.startswith('poi'):
        return 'poi'
    return 'island'

extras = []
seen_names = set()
for root in unmatched:
    if re.search(r'test|playground|exhibition', root, re.I):
        continue
    summary = out.get(root)  # never set; recompute
    # recompute summary for this root
    data = raw[root]
    s2 = {'benches': 0, 'crates': {}, 'treasures': {}, 'mobs': 0, 'locked': 0, 'items': {}}
    for name, count in data['found'].items():
        kind, label = classify(name)
        if kind == 'bench':
            s2['benches'] += count
        elif kind == 'crate':
            s2['crates'][label] = s2['crates'].get(label, 0) + count
        elif kind == 'treasure':
            s2['treasures'][label] = s2['treasures'].get(label, 0) + count
        elif kind == 'mob':
            s2['mobs'] += count
        elif kind == 'locked':
            s2['locked'] += count
        elif kind == 'item':
            s2['items'][label] = s2['items'].get(label, 0) + count
    if not any([s2['benches'], s2['crates'], s2['treasures'], s2['mobs'], s2['locked'], s2['items']]):
        continue
    nm = pretty_root(root)
    if not nm or nm.lower() in seen_names:
        # merge duplicates (Demo vs non-demo variants)
        if nm.lower() in seen_names:
            for e in extras:
                if e['name'].lower() == nm.lower():
                    e['contents']['benches'] += s2['benches']
                    e['contents']['mobs'] += s2['mobs']
                    e['contents']['locked'] += s2['locked']
                    for f in ('crates', 'treasures', 'items'):
                        for k, v in s2[f].items():
                            e['contents'][f][k] = e['contents'][f].get(k, 0) + v
        continue
    seen_names.add(nm.lower())
    extras.append({'id': 'extra_' + root, 'name': nm, 'kind': root_kind(root), 'caps': [], 'contents': s2})

json.dump(extras, open('../site/src/data/extra_locations.json', 'w', encoding='utf-8'), indent=1)
print('matched locations:', len(out), '| extra locations:', len(extras), '| dropped roots:', len(unmatched) - len(extras))
benched = [k for k, v in out.items() if v['benches']] + [e['name'] for e in extras if e['contents']['benches']]
print('locations with crafting stations:', benched)
