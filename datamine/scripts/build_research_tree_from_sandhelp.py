"""
Build site/src/data/research_tree.json from a sand-help.com/tech DOM extract.

WHY: the research tree's prerequisite edges + costs are served per-account by the
game's master server (GetResearchTree) and are NOT in the static playtest files
(see ../UPDATE_PIPELINE.md and BACKEND_PLAYFAB.md). The community wiki
sand-help.com has collected the full tree (costs + edges). Owner decision
(2026-06-15): use that as our data source for now; capture our own from the live
master server once the game launches (22 Jun 2026).

INPUT : datamine/sandhelp/sandhelp_tree_exact.json  (DOM extract: node boxes +
        edge path 'd' strings, all in sand-help's layout pixel space, viewBox
        3792x1680). Node boxes carry name, cost, faction colour, glyph icon.
OUTPUT: site/src/data/research_tree.json

Layout geometry is preserved 1:1 from sand-help (the hard part = graph layout);
our renderer restyles it to our theme and swaps in our own part thumbnails.
Attribution to sand-help is stored in the file + shown on the page.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(ROOT, "datamine", "sandhelp", "sandhelp_tree_exact.json")
THUMBS = os.path.join(ROOT, "site", "src", "data", "part_thumbs_v2.json")
OUT = os.path.join(ROOT, "site", "src", "data", "research_tree.json")

# faction colour (sand-help --fac) -> our themed palette + canonical name.
# bands top->bottom on their board are Godlewski, Kaiser, Landwehr.
FAC_BY_COLOR = {
    "#4493f8": {"name": "Godlewski's Expedition", "color": "#5aa9e6"},  # blue
    "#6fb24a": {"name": "Kaiser's Friends", "color": "#7fcf8a"},        # green
    "#e3a008": {"name": "k.k. Landwehr", "color": "#e3b860"},           # amber
}


def parse_path(d):
    """Orthogonal M/H/V/L path -> (start_xy, end_xy)."""
    toks = re.findall(r"[MHVL][^MHVLZ]*", d, re.I)
    x = y = 0.0
    pts = []
    for t in toks:
        c = t[0]
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", t[1:])]
        if c in "ML":
            x, y = nums[0], nums[1]
        elif c == "H":
            x = nums[-1]
        elif c == "V":
            y = nums[-1]
        pts.append((x, y))
    return pts[0], pts[-1]


def comp_of(glyph):
    """/tramplers/walker_compCargo_..._icon.png -> compCargo_..."""
    if not glyph:
        return None
    base = glyph.rsplit("/", 1)[-1]
    base = re.sub(r"\.(png|webp|jpg)$", "", base, flags=re.I)
    base = re.sub(r"_icon$", "", base)
    base = re.sub(r"^walker_", "", base)
    return base


def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    thumbs = json.load(open(THUMBS, encoding="utf-8"))
    nodes = raw["nodes"]

    rights = {round(n["left"] + n["w"]) for n in nodes}

    # exact lookup helpers (coords are integer px in sand-help space)
    def nearest(pt, side):
        bx, by = pt
        best, bd = None, 1e18
        for n in nodes:
            x = n["left"] + n["w"] if side == "r" else n["left"]
            dd = (x - bx) ** 2 + (n["cy"] - by) ** 2
            if dd < bd:
                bd, best = dd, n
        return best, bd ** 0.5

    node_edges = []   # (from_i, to_i)
    roots = set()
    for d in raw["edges"]:
        s, e = parse_path(d)
        if any(abs(s[0] - r) < 2 for r in rights):
            sn, _ = nearest(s, "r")
            tn, _ = nearest(e, "l")
            if sn["i"] != tn["i"]:
                node_edges.append((sn["i"], tn["i"]))
        else:
            # faction-root spine (starts left of column 0) -> target is a root
            tn, _ = nearest(e, "l")
            roots.add(tn["i"])

    # de-dup
    node_edges = sorted(set(node_edges))

    cols = sorted({n["left"] for n in nodes})
    col_idx = {c: i for i, c in enumerate(cols)}

    out_nodes = []
    thumb_hits = 0
    for n in nodes:
        comp = comp_of(n["glyph"])
        thumb = thumbs.get(comp) if comp else None
        if thumb:
            thumb_hits += 1
        fac = FAC_BY_COLOR.get(n["fac"], {"name": "Unknown", "color": "#8a8a8a"})
        out_nodes.append({
            "id": n["i"],
            "name": n["name"],
            "cost": n["cost"],
            "col": col_idx[n["left"]],
            "x": round(n["left"]),
            "y": round(n["top"]),
            "w": round(n["w"]),
            "h": round(n["h"]),
            "faction": fac["name"],
            "color": fac["color"],
            "thumb": thumb,            # our local image, may be None
            "root": n["i"] in roots,
        })

    factions = []
    seen = set()
    for c in ["#4493f8", "#6fb24a", "#e3a008"]:
        f = FAC_BY_COLOR[c]
        if f["name"] not in seen:
            factions.append(f)
            seen.add(f["name"])

    out = {
        "source": "Reconstructed from sand-help.com/tech (community wiki) — "
                   "costs + prerequisite edges that are server-side in the game files. "
                   "To be replaced by our own GetResearchTree capture after launch.",
        "viewBox": {"w": 3792, "h": 1680},
        "factions": factions,
        "nodeCount": len(out_nodes),
        "edgeCount": len(node_edges),
        "nodes": out_nodes,
        "edges": [[a, b] for a, b in node_edges],
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"nodes={len(out_nodes)} edges={len(node_edges)} roots={len(roots)} "
          f"thumb_hits={thumb_hits}/{len(out_nodes)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
