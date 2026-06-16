"""Extract all icon_* sprites (and a few named extras) from the UI bundle to PNG."""
import os, UnityPy

SRC = 'gamefiles/Sand_Data/StreamingAssets/aa/StandaloneWindows64/ui_assets_all.bundle'
OUT = 'extracted/icons'
os.makedirs(OUT, exist_ok=True)

env = UnityPy.load(SRC)
saved, failed = 0, 0
seen = set()
for obj in env.objects:
    if obj.type.name != 'Sprite':
        continue
    try:
        d = obj.read()
        name = d.m_Name
        if not (name.startswith('icon') or name.startswith('gameModeIcon')):
            continue
        if name in seen:
            continue
        seen.add(name)
        img = d.image
        img.save(f'{OUT}/{name}.png')
        saved += 1
    except Exception:
        failed += 1
print(f'saved {saved} icons, {failed} failed -> {OUT}')
