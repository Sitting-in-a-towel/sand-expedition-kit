"""Build the site's data JSONs from extracted game data.
Outputs to ../site/src/data/ and copies matched icons to ../site/public/icons/.
Run from datamine/: python scripts/build_site_data.py
"""
import json, os, re, shutil

EXT = 'extracted/json'
SITE = '../site'
DATA_OUT = f'{SITE}/src/data'
ICON_SRC = 'extracted/icons'
ICON_OUT = f'{SITE}/public/icons'
os.makedirs(DATA_OUT, exist_ok=True)
os.makedirs(ICON_OUT, exist_ok=True)

# ---------- ItemType flags (from dump.cs, Hologryph.Sand.Shared.Inventory.ItemType) ----------
ITEM_TYPE = {
    2: 'Weapon', 4: 'Ammo', 8: 'Turret Ammo', 16: 'Food', 32: 'Container',
    64: 'Small Valuable', 128: 'Large Valuable', 256: 'Money', 512: 'Armor',
    1024: 'Backpack', 2048: 'Raid Explosives', 4096: 'Utility Consumable',
    8192: 'Attack Consumable', 16384: 'Energy', 32768: 'Lock Box',
    65536: 'Lock Box Key', 131072: 'Alarm Box', 262144: 'Resource T1',
    524288: 'Resource T2', 1048576: 'Resource T3',
    2097152: 'Food Crate', 4194304: 'Med Crate', 8388608: 'Resource Crate',
    16777216: 'Valuables Crate', 33554432: 'Weapon Crate', 67108864: 'Shell Crate',
    134217728: 'Explosive Barrel',
}

def decode_flags(mask):
    if mask == 0:
        return ['Undefined']
    return [name for bit, name in ITEM_TYPE.items() if mask & bit]

# ---------- helpers ----------
def prettify(ident):
    """item_resourceMetalParts -> Metal Parts ; MedKit -> Med Kit"""
    s = ident
    for pre in ('item_resource', 'item_', 'game_'):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    s = s.replace('_', ' ')
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', s)
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', s)  # POIShip -> POI Ship
    s = re.sub(r'\bt(\d)\b', r'T\1', s, flags=re.I)
    return ' '.join(w if w.isupper() else w.capitalize() for w in s.split())

# ---------- official item defs (from data.unity3d TextAssets, see extracted/textassets/) ----------
ITEM_DEFS = {}
try:
    ITEM_DEFS = json.load(open(f'{EXT}/item_defs.json', encoding='utf-8'))
except FileNotFoundError:
    pass

# ---------- authoritative names+descriptions from the I2 Localization table ----------
# (build_localization.py — the devs' real strings; supersedes prettify() + hand overrides)
LOC_ITEMS = {}
try:
    LOC_ITEMS = json.load(open(f'{DATA_OUT}/localization.json', encoding='utf-8'))['items']
except FileNotFoundError:
    print('WARNING: localization.json missing — run build_localization.py first; using fallback names')
CHASSIS_LEGS = {}
try:
    CHASSIS_LEGS = json.load(open(f'{EXT}/chassis_legs.json', encoding='utf-8'))
except FileNotFoundError:
    pass

# ---------- items + icon matching ----------
icons = {f[:-4] for f in os.listdir(ICON_SRC) if f.endswith('.png')}

def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

icon_by_norm = {}
for ic in icons:
    icon_by_norm.setdefault(norm(ic), ic)

MANUAL_ICON = {
    'MedKit': 'icon_medkit',
    'item_coinCrown': 'icon_item_coinCrown',
    'item_smallValuables': 'icon_item_smallValuables',
    'item_valuablePapers': 'icon_item_valuablePapers',
    'item_rifleMusket': 'icon_rifleMusketClip',
    'Old_Jacket': 'icon_jacket',
    'Old_JacketT2': 'icon_jacket_2',
    'Old_JacketT3': 'icon_jacket_3',
    'ArtefactCrystal': 'icon_artefact_crystal',
    'game_keyIslandDoorGreen': 'icon_item_game_keyLockedDoorGreen',
    'game_treasureShovel': 'icon_item_treasureShovel',
    'item_foodCan': 'icon_item_game_fishCan',
    'item_grenadeContact': 'icon_grenade',
    'game_coinCrownPile_10': 'icon_crownCoins',
    'game_ValuablePiles01_mobDrop': 'icon_item_smallValuables',
}

def find_icon(item_id):
    if item_id in MANUAL_ICON and MANUAL_ICON[item_id] in icons:
        return MANUAL_ICON[item_id]
    base = item_id
    for pre in ('item_resource', 'item_'):
        if base.startswith(pre):
            base = base[len(pre):]
            break
    base = re.sub(r'(_mobDrop|_mineDrop|MobDrop|MineDrop)$', '', base)
    cands = [
        'icon_' + base,
        'icon_item_' + base,
        'icon_item_resource' + base,
        'icon_' + re.sub(r'_t(\d)$', r'_t\1', base),
    ]
    # ammo special: item_pistolAmmo -> icon_ammo_pistol ; pistolAmmo_Armor -> icon_ammo_pistol_armor
    m = re.match(r'(.+?)Ammo(?:_?(.+))?$', base)
    if m:
        if m.group(2):
            cands.insert(0, f'icon_ammo_{m.group(1)}_{m.group(2)}')
        else:
            cands.insert(0, 'icon_ammo_' + m.group(1))
    for c in cands:
        n = norm(c)
        if n in icon_by_norm:
            return icon_by_norm[n]
    # fuzzy: icon whose norm contains the norm'd base
    nb = norm(base)
    if len(nb) >= 4:
        for ic in sorted(icons, key=len):
            if nb in norm(ic):
                return ic
    return None

# ---------- loot tables (both modes) ----------
def load_tables(path):
    doc = json.load(open(path, encoding='utf-8'))
    out = []
    for t in doc['_lootTables']['$items']:
        out.append({
            'id': t['lootTableId'],
            'items': [
                {'item': i['itemBlueprint'], 'min': i['countMin'], 'max': i['countMax']}
                for i in t['items']['$items']
            ],
        })
    return out

voyage = load_tables(f'{EXT}/loottables_voyage.json')
storm = load_tables(f'{EXT}/loottables_storm.json')

CAT_GROUP = {
    'med': 'Medical Crate', 'resource': 'Resource Crate', 'food': 'Food Crate',
    'valuables': 'Valuables Crate', 'weapons': 'Weapons Crate',
}

def classify_table(tid):
    m = re.match(r'(med|resource|food|valuables|weapons)_container_(low|mid|high)Effort_T(\d)_set(\d+)', tid)
    if m:
        return {
            'category': m.group(1), 'effort': m.group(2), 'tier': int(m.group(3)), 'set': int(m.group(4)),
            'group': CAT_GROUP[m.group(1)],
        }
    # specials: buriedTreasure_T2_set3 / navalMine / aurogenCrystal_set ...
    m = re.match(r'([a-zA-Z]+?)(?:_T(\d))?(?:_set(\d+)?)?$', tid)
    base = m.group(1) if m else tid
    tier = int(m.group(2)) if m and m.group(2) else None
    setn = int(m.group(3)) if m and m.group(3) else 1
    return {'category': 'special', 'effort': None, 'tier': tier, 'set': setn, 'group': prettify(base)}

tables = {}
for mode, tlist in (('voyage', voyage), ('storm', storm)):
    for t in tlist:
        e = tables.setdefault(t['id'], {'id': t['id'], **classify_table(t['id'])})
        e[mode] = t['items']

json.dump(sorted(tables.values(), key=lambda x: x['id']), open(f'{DATA_OUT}/loot_tables.json', 'w', encoding='utf-8'), indent=1)

# ---------- items ----------
item_ids = set()
for t in tables.values():
    for mode in ('voyage', 'storm'):
        for i in t.get(mode, []):
            item_ids.add(i['item'])

recipes_raw = json.load(open(f'{EXT}/craftingrecipes.json', encoding='utf-8'))
for o in recipes_raw:
    for r in o['data'].get('recipes', []):
        for ing in r['inputIngredients'] + r['outputIngredients']:
            item_ids.add(ing['itemId'])

items = []
matched = 0
for iid in sorted(item_ids):
    d = ITEM_DEFS.get(iid, {})
    # exact icon from game config beats heuristics
    ic = d.get('icon') if d.get('icon') in icons else find_icon(iid)
    if ic:
        matched += 1
        shutil.copyfile(f'{ICON_SRC}/{ic}.png', f'{ICON_OUT}/{ic}.png')
    # name priority: I2 localization (authoritative) > item config NiceName > prettified id
    loc = LOC_ITEMS.get(iid, {})
    name = loc.get('name') or d.get('name') or prettify(iid)
    # for config-name fallbacks (no loc entry), disambiguate shared variant NiceNames
    if not loc.get('name') and d.get('name'):
        m = re.search(r'_(highVelocity|lowRecoil|longRange|EMP|Armor|armorPiercing|highPenetration|highExplosive|slug|explosive|smoke|toxic|fire|interiorExplosion|delayedDetonation)$', iid)
        if m:
            name += f' ({prettify(m.group(1))})'
    items.append({
        'id': iid,
        'name': name,
        'icon': ic and f'/icons/{ic}.png',
        'rarity': d.get('rarity'),
        'type': d.get('type'),
        'pawnValue': d.get('pawnValue'),
        'short': loc.get('short'),
        'desc': loc.get('desc'),
    })
json.dump(items, open(f'{DATA_OUT}/items.json', 'w', encoding='utf-8'), indent=1)
print(f'items: {len(items)}, icons matched: {matched}, loc names: {sum(1 for i in items if LOC_ITEMS.get(i["id"], {}).get("name"))}, with descriptions: {sum(1 for i in items if i.get("desc"))}')

# ---------- recipes ----------
recipes = []
for o in recipes_raw:
    name = o['data'].get('m_Name', '')
    if name == 'TestRecipesBundle':
        continue
    m = re.match(r'Recipes_(\w+?)_Workbench_T(\d)', name)
    bench, tier = (m.group(1), int(m.group(2))) if m else (name, None)
    for r in o['data'].get('recipes', []):
        recipes.append({
            'workbench': bench, 'tier': tier,
            'inputs': [{'item': i['itemId'], 'amount': i['amount']} for i in r['inputIngredients']],
            'outputs': [{'item': i['itemId'], 'amount': i['amount']} for i in r['outputIngredients']],
            'seconds': r['craftingTimeSeconds'],
        })
json.dump(recipes, open(f'{DATA_OUT}/recipes.json', 'w', encoding='utf-8'), indent=1)
print(f'recipes: {len(recipes)}')

# ---------- locations (lootsets) ----------
lootsets = json.load(open(f'{EXT}/lootsets.json', encoding='utf-8'))

def classify_location(name):
    n = name.lower()
    if 'event' in n:
        return 'event'
    if name.startswith('POI'):
        if 'ship' in n or 'gunboat' in n:
            return 'ship'
        if 'rock' in n or 'underground' in n:
            return 'rock'
        return 'poi'
    if 'fort' in n or 'fortress' in n:
        return 'fort'
    if 'test' in n:
        return 'test'
    return 'island'

raw_locs = {}
for o in lootsets:
    d = o['data']
    name = d.get('m_Name', '')
    if not name:
        continue
    msi = d.get('maxSpawnedItems', {})
    keys, vals = msi.get('_keys', []), msi.get('_values', [])
    caps = []
    for k, v in zip(keys, vals):
        if v and v > 0:
            caps.append({'types': decode_flags(k), 'mask': k, 'max': v})
    raw_locs[name] = caps

# X and X_NoAB are the same island, with/without the Alarm Box (alarmed large-valuable)
# spawn — verified: caps differ ONLY on mask 131200 (ALARM_BOX|LARGE_VALUABLE). Merge.
locations = []
for name, caps in raw_locs.items():
    if name.endswith('_NoAB') and name[:-5] in raw_locs:
        continue  # folded into the base version
    has_noab_twin = f'{name}_NoAB' in raw_locs
    has_ab = any(c['mask'] & 131072 for c in caps)
    locations.append({
        'id': name,
        'name': prettify(name.removesuffix('_NoAB')),
        'kind': classify_location(name),
        'caps': sorted(caps, key=lambda c: -c['max']),
        # null = never; 'sometimes' = AB/NoAB variants exist; 'always' = AB with no twin
        'alarmBox': ('sometimes' if has_noab_twin else 'always') if has_ab else None,
    })
locations.sort(key=lambda l: (l['kind'], l['name']))
json.dump(locations, open(f'{DATA_OUT}/locations.json', 'w', encoding='utf-8'), indent=1)
from collections import Counter
print('locations:', len(locations), Counter(l['kind'] for l in locations))

# ---------- walker parts ----------
epbs = open(f'{EXT}/walker_epbs.txt', encoding='utf-8').read().split()
parts = []
seen = set()
for e in epbs:
    if not e.endswith('_epb') or e.endswith('_epb_1') or '_placeholder' in e:
        continue
    base = e[len('walker_'):-len('_epb')]
    if base in seen:
        continue
    seen.add(base)
    m = re.match(r'comp(?P<cat>[A-Za-z]+?)_(?P<variant>.+?)_(?P<mat>Metal|Wood|Open|Frame|MetalHole|WoodHole)_(?P<w>\d)x(?P<d>\d)(?P<mirror>_mirror)?$', base)
    if m:
        entry = {
            'id': base,
            'category': m.group('cat'),
            'variant': m.group('variant').replace('_', ' '),
            'material': m.group('mat'),
            'w': int(m.group('w')), 'd': int(m.group('d')),
            'mirror': bool(m.group('mirror')),
            'name': f"{prettify(m.group('cat'))} — {m.group('variant').replace('_',' ')} ({m.group('mat')}, {m.group('w')}x{m.group('d')})",
        }
        if m.group('cat') == 'Chassis':
            legs = CHASSIS_LEGS.get('walker_' + base)
            if legs:
                entry['legs'] = legs
            size_word = {'Small4': 'Scout', 'SmallLong4': 'Mule', 'Medium4': 'Standard',
                         'Wide4': 'Wide', 'Long4': 'Hauler', 'Long6': 'Long Hauler',
                         'Long8': 'Freighter', 'Large6': 'Fortress'}.get(m.group('variant'), m.group('variant'))
            hole = 'Hole' in m.group('mat')
            entry['label'] = f"{size_word} {m.group('w')}×{m.group('d')}" + (f" · {legs} legs" if legs else '') + (' · cargo hatch' if hole else '')
        parts.append(entry)
    else:
        # non-comp parts (turrets, beds, legacy chassis etc.)
        mm = re.match(r'(?P<n>.+?)_(?P<w>\d)x(?P<d>\d)$', base)
        w = int(mm.group('w')) if mm else 1
        d = int(mm.group('d')) if mm else 1
        nm = mm.group('n') if mm else base
        parts.append({
            'id': base, 'category': 'Other', 'variant': prettify(nm),
            'material': None, 'w': w, 'd': d, 'mirror': False,
            'name': prettify(nm) + (f' ({w}x{d})' if mm else ''),
        })
json.dump(sorted(parts, key=lambda p: (p['category'], p['variant'], p['material'] or '')),
          open(f'{DATA_OUT}/parts.json', 'w', encoding='utf-8'), indent=1)
print('parts:', len(parts), Counter(p['category'] for p in parts).most_common(15))

unmatched = [i['id'] for i in items if not i['icon']]
print('unmatched icons:', len(unmatched), unmatched[:20])
