"""Render isometric thumbnails from the v2 mesh bins (real material colours).
Output: ../site/public/parts2/<part_id>.png + ../site/src/data/part_thumbs_v2.json
Also prints which parts have no mesh (for the ghost-icon fallback).
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw

IDX = json.load(open('../site/src/data/mesh_index_v2.json', encoding='utf-8'))
PARTS = json.load(open('../site/src/data/parts_v2.json', encoding='utf-8'))['parts']
SRC = '../site/public/meshes2'
OUT = '../site/public/parts2'
os.makedirs(OUT, exist_ok=True)

LIGHT = np.array([0.5, 0.8, 0.35])
LIGHT = LIGHT / np.linalg.norm(LIGHT)

def load_bin(pid, t):
    raw = open(f'{SRC}/{pid}.bin', 'rb').read()
    pos_n = t * 9 * 4
    nrm_n = t * 9
    pos = np.frombuffer(raw[:pos_n], dtype=np.float32).reshape(t, 3, 3)
    nrm = np.frombuffer(raw[pos_n:pos_n + nrm_n], dtype=np.int8).reshape(t, 3, 3).astype(np.float32) / 127
    col = np.frombuffer(raw[pos_n + nrm_n:], dtype=np.uint8).reshape(t, 3)
    return pos, nrm, col

def render(tris, nrms, cols, path, size=160):
    yaw, pitch = math.radians(225), math.radians(-30)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    R = Rx @ Ry
    pts = (tris.reshape(-1, 3) @ R.T).reshape(-1, 3, 3)
    pts = pts.copy()
    pts[:, :, 1] *= -1  # world y-up -> screen y-down
    fn = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
    nl = np.linalg.norm(fn, axis=1)
    ok = nl > 1e-9
    pts, fn, nl, cols = pts[ok], fn[ok], nl[ok], cols[ok]
    if len(pts) == 0:
        return False
    shade = np.abs((fn / nl[:, None]) @ (R @ LIGHT))
    order = np.argsort(pts[:, :, 2].mean(axis=1))
    xy = pts[:, :, :2]
    mn = xy.reshape(-1, 2).min(0)
    mx = xy.reshape(-1, 2).max(0)
    span = max((mx - mn).max(), 1e-6)
    scale = (size - 18) / span
    off = (size - (mx - mn) * scale) / 2
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    base = cols.astype(np.float64)
    for i in order:
        p2 = (xy[i] - mn) * scale + off
        c = (base[i] * (0.35 + 0.65 * shade[i])).astype(int)
        dr.polygon([tuple(p) for p in p2], fill=(c[0], c[1], c[2], 255))
    img.save(path)
    return True

thumbs, missing = {}, []
for p in PARTS:
    pid = p['id']
    meta = IDX.get(pid)
    if not meta:
        missing.append(pid)
        continue
    pos, nrm, col = load_bin(pid, meta['t'])
    # cap render load for speed: stride-sample big ones (render only, bins untouched)
    if len(pos) > 30000:
        step = len(pos) // 30000 + 1
        pos, nrm, col = pos[::step], nrm[::step], col[::step]
    if render(pos, nrm, col, f'{OUT}/{pid}.png'):
        thumbs[pid] = f'/parts2/{pid}.png'

json.dump(thumbs, open('../site/src/data/part_thumbs_v2.json', 'w'), indent=0)
print('thumbnails:', len(thumbs), '| missing mesh:', missing)
