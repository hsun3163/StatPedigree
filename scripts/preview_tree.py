#!/usr/bin/env python3
"""Draw a static PNG of the tree layout stored in map.html (no browser needed). Usage: python scripts/preview_tree.py [map.html] [out.png]"""
import json, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src = sys.argv[1] if len(sys.argv) > 1 else "map.html"
out = sys.argv[2] if len(sys.argv) > 2 else "tree_preview.png"
g = json.loads(re.search(r"const G = (\{.*?\});\n", open(src).read(), re.S).group(1))
col = {"fsusie": "#2aa198", "prs": "#d98c1f", "gen": "#6aa84f", "stato": "#3d6fd9", "cite": "#c2557a"}
xs = [p[0] for e in g["edges"] for p in e["pts"]]; ys = [n["y"] for n in g["nodes"]]
fig, ax = plt.subplots(figsize=(max(14, (max(xs) - min(xs)) * 0.42), max(10, (max(ys) - min(ys)) * 0.5)))
for e in g["edges"]:
    if e.get("sec"):
        continue
    ax.plot([p[0] for p in e["pts"]], [p[1] for p in e["pts"]], color="#b9d7a0" if e.get("ge") else "#9bb5ee" if e.get("st") else "#555", lw=.6 if e.get("ge") else .9, zorder=1)
for n in g["nodes"]:
    ax.scatter(n["x"], n["y"], s=30 + 24 * n["c"] ** .5, color=col[n["side"]], zorder=2)
    ax.text(n["x"], n["y"] + 0.22, n["n"][:24], ha="center", va="top", fontsize=6.5, zorder=3)
for r in g["rows"]:
    ax.text(min(xs) - 1.2, r["y"], r["t"], ha="right", va="center", fontsize=9, color="#555")
ax.invert_yaxis(); ax.axis("off"); plt.tight_layout(); plt.savefig(out, dpi=int(min(70, 2000 / fig.get_size_inches()[0])))
print(out, fig.get_size_inches())
