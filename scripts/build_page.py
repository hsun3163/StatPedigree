#!/usr/bin/env python3
"""Build one phone-first HTML page (map.html) from tables/ and reports/: a zoomable pedigree map plus reading views.

Usage: python scripts/build_page.py [--out map.html]
The page is a reading view: lineage walks first, evidence (quoted spans) one tap away.
The tables stay the source of truth.
"""
import argparse, csv, html, json, re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "tables"


LEAD_TABLES = {"relationships.tsv", "lineage_order.tsv", "map_layout.tsv", "stato_map.tsv", "stato_terms.tsv", "parents.tsv"}


def _raw(name):
    with open(T / name, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t", **({"quoting": csv.QUOTE_NONE} if name in LEAD_TABLES else {})))


# One star per statistical method: tables/node_merge.tsv folds implementations, versions and other names into one id.
ALIAS = {r["alias_id"]: r for r in _raw("node_merge.tsv")} if (T / "node_merge.tsv").exists() else {}
# A statistical method is one class: its stages, building blocks and options (tables/node_parts.tsv) are parts of it, not stars.
for _r in (_raw("node_parts.tsv") if (T / "node_parts.tsv").exists() else []):
    ALIAS[_r["part_id"]] = {"alias_id": _r["part_id"], "canonical_id": _r["method_id"], "kind": "part of this method", "reason": _r["what"]}
ID_COLS = {"methods.tsv": ["method_id"], "claims.tsv": ["method_id", "other_method"], "relationships.tsv": ["from_id", "to_id"],
           "lineage_order.tsv": ["method_id"], "stato_map.tsv": ["item_id"], "parents.tsv": ["child_method_id", "parent_id"],
           "edge_links.tsv": ["from_id", "to_id"], "context_links.tsv": ["citing_method_id", "cited_node_id"],
           "citations.tsv": ["citing_id", "cited_id"], "citation_paths.tsv": ["method_paper"], "link_roles.tsv": ["later_method", "earlier_method"]}


def canon(x):
    base, dot, comp = (x or "").partition(".")
    return (ALIAS[base]["canonical_id"] + dot + comp) if base in ALIAS else x


def read(name):
    """Pipeline tables use standard CSV quoting (spans may hold quotes and line breaks); hand-written ones are plain."""
    rows = [{k: " ".join(v.split()) if isinstance(v, str) else v for k, v in r.items()} for r in _raw(name)]
    for r in rows:
        if name == "methods.tsv":
            r["_orig"] = r["method_id"]
        for c in ID_COLS.get(name, []):
            r[c] = canon(r[c])
    if name == "map_layout.tsv":
        rows = [r for r in rows if r["method_id"] not in ALIAS]
    return rows


claims = read("claims.tsv")
methods = read("methods.tsv")
edges = read("relationships.tsv")
order = read("lineage_order.tsv")
questions = read("open_questions.tsv")
layout = read("map_layout.tsv")  # hand-placed star positions, tiers and short labels
LAY = {r["method_id"]: r for r in layout}
stato_map = read("stato_map.tsv")  # lead-written links from methods and generic roots to STATO terms
STATO = {r["stato_id"]: r for r in read("stato_terms.tsv")}
sid = lambda x: x.lower().replace(":", "_")
# citation lineage (scripts/citation_paths.py): papers behind STATO terms, citations among papers, shortest paths
CNODE = {r["node_id"]: r for r in read("citation_nodes.tsv")}
cites_raw = read("citations.tsv")
cpaths = [r for r in read("citation_paths.tsv") if r["length"] != "NA"]
ssrc = [r for r in read("stato_sources.tsv")]
HAS_PATH = {(r["method_paper"], r["stato_id"]) for r in cpaths}
CL = {c["claim_id"]: c for c in claims}

# one row per method: prefer the paper that defines it
M = {}
for m in methods:
    if m["method_id"] not in M or (m["paper_id"] == m["method_id"] and m["_orig"] == m["method_id"]) or (m["_orig"] == m["method_id"] and M[m["method_id"]]["_orig"] != m["method_id"]):
        M[m["method_id"]] = m
by_method = defaultdict(list)
for c in claims:
    by_method[c["method_id"]].append(c)

EDGE_WORDS = {
    "extends": "extends", "special_case_of": "is a special case of", "uses": "uses",
    "combines": "combines", "shares_structure_not_equivalent": "shares structure with (not equivalent to)",
    "derivable_under_conditions": "can be derived from", "inspired_by": "was inspired by",
}
# ---- automatic placement: any method or seed paper without a hand-written row in map_layout.tsv is put next to
# the star that cites it (ancestors above, descendants below). Hand-written rows always win.
PAPER2M = {}
for _m in methods:
    PAPER2M.setdefault(_m["paper_id"], _m["method_id"])
seed = {r["paper_id"]: r for r in csv.DictReader(open(ROOT / "seed" / "seed_list.tsv", newline=""), delimiter="\t")}
node_of = lambda x: canon(x) if canon(x) in LAY or canon(x) in M else PAPER2M.get(x, canon(x))  # a paper id stands for its first method
OFF = {"fsusie": 0.0, "prs": 8.0, "cite": 0.0, "gen": 0.0}


AUTO = set()
NSIDE = defaultdict(str)


def auto_place():
    import math
    todo = [m for m in M if m not in LAY] + [p for p in seed if p not in LAY and p not in M and p not in PAPER2M and p not in ALIAS]
    if not todo:
        return
    raw = []  # (descendant, ancestor) pairs from the raw link tables
    for r in read("context_links.tsv"):
        if r["citing_method_id"] != "NA" and r["relation"] in EDGE_WORDS or r["relation"] == "contains_special_case":
            raw.append((r["citing_method_id"].split(".")[0], node_of(r["cited_node_id"])))
    for r in read("parents.tsv"):
        raw.append((r["child_method_id"].split(".")[0], node_of(r["parent_id"].split(".")[0])))
    pos = {k: (float(v["x"]) + OFF[v["side"]], float(v["y"])) for k, v in LAY.items() if v["side"] in OFF}
    free = lambda x, y: (-2.7 <= y <= 7.8 and -0.6 <= x <= 14.6 and not (-1.2 < y < -0.4 and (1.4 < x < 5.2 or 8.7 < x < 12.6))
                         and all((x - a) ** 2 + (y - b) ** 2 >= 0.72 ** 2 for a, b in pos.values()))
    stack = {"fsusie": 0, "prs": 0}
    pending, progress = list(todo), True
    while pending and progress:
        progress = False
        for u in list(pending):
            side = M[u]["side"] if u in M else seed[u]["side"]
            up = [d for d, a in raw if a == u and d in pos]      # stars that cite u: u goes above them
            down = [a for d, a in raw if d == u and a in pos]    # stars u cites: u goes below them
            if not up and not down:
                continue
            bx, by = pos[(up or down)[0]]
            by += -1.0 if up else 1.0
            spot = next(((bx + r * math.cos(t), by + r * math.sin(t)) for r in [i * 0.35 for i in range(30)]
                         for t in [k * math.pi / 6 for k in range(12)] if free(bx + r * math.cos(t), by + r * math.sin(t))), None)
            if spot is None:
                continue
            pos[u] = spot; pending.remove(u); progress = True
            place(u, side, spot)
    for u in pending:  # nothing on the map names it yet: park it in a row under its family
        side = M[u]["side"] if u in M else seed[u]["side"]
        spot = (OFF[side] + 0.4 + 0.8 * (stack[side] % 8), 7.4 + 0.7 * (stack[side] // 8)); stack[side] += 1
        pos[u] = spot; place(u, side, spot)


def place(u, side, spot):
    nm = re.sub(r"\s*\(.*?\)", "", M[u]["name"] if u in M else seed[u]["method"]).strip()
    acc = seed.get(M[u]["paper_id"] if u in M else u, {}).get("access", "")
    lab = (seed.get(M[u]["paper_id"] if u in M else u, {}).get("year", "") + "|" if True else "") + ("no open copy: title only" if u not in M else "abstract only" if acc == "abstract_only" else "pulled in by citation")
    row = {"method_id": u, "side": side, "x": "%.2f" % (spot[0] - OFF[side]), "y": "%.2f" % spot[1], "tier": "3",
           "short": nm if len(nm) <= 30 else nm[:28] + "…", "labels": lab.strip("|")}
    LAY[u] = row; layout.append(row); AUTO.add(u)


auto_place()

# link audit (tables/edge_links.tsv): a link is drawn only when one passage in a stored paper states it
cites = [dict(r, citing_id=node_of(r["citing_id"]), cited_id=node_of(r["cited_id"])) for r in cites_raw]
cites = [r for r in cites if r["citing_id"] in LAY and r["cited_id"] in LAY and r["citing_id"] != r["cited_id"]]
_links = read("edge_links.tsv")
# links from in-text citation sentences (tables/context_links.tsv): the primary evidence between papers
_ctx = {r["context_id"]: r for r in read("citation_contexts.tsv")}
ctx_edges, _n = [], defaultdict(int)
for r in read("context_links.tsv"):
    c, par, t = r["citing_method_id"], node_of(r["cited_node_id"]), r["relation"]
    if c == "NA" and t in EDGE_WORDS:
        c = node_of(r["citing_paper"])  # the reader left the method blank: the sentence is about the citing paper's own method
    if c == "NA" or par not in LAY or c.split(".")[0] not in LAY or c.split(".")[0] == par or r["context_id"] not in _ctx:
        continue
    if t == "contains_special_case":
        c, par, t = par, c, "special_case_of"
    if t not in EDGE_WORDS:
        continue  # benchmark, data_or_tool, background: a mention, not a theory link
    k = (tuple(sorted((c.split(".")[0], par.split(".")[0]))), t)
    _n[k] += 1
    if _n[k] > 2:
        continue  # at most two sentences per pair and type
    x = _ctx[r["context_id"]]
    ctx_edges.append({"edge_id": r["context_id"], "from_id": c, "to_id": par, "type": t, "conditions": r["conditions"],
                      "statement": r["statement"], "span": x["sentence"], "paper": x["citing_paper"], "location": x["section"] + " (citation sentence)"})
_ctx_pairs = {tuple(sorted((e["from_id"].split(".")[0], e["to_id"].split(".")[0]))) for e in ctx_edges}
tedges = ctx_edges + [{"edge_id": r["edge_id"], "from_id": r["from_id"], "to_id": r["to_id"],
           "type": r["stated_type"] if r["verdict"] == "stated_other_type" else r["type"], "conditions": r["conditions"],
           "statement": r["statement"], "span": r["link_span"], "paper": r["paper_id"], "location": r["location"]}
          for r in _links if r["verdict"] in ("stated", "stated_other_type")
          and tuple(sorted((r["from_id"].split(".")[0], r["to_id"].split(".")[0]))) not in _ctx_pairs]
# parents step (papers/*/parents.tsv pooled in tables/parents.tsv): what each paper says its method is built from
_seen = {tuple(sorted((e["from_id"].split(".")[0], e["to_id"].split(".")[0]))) for e in tedges}
for _i, r in enumerate(read("parents.tsv")):
    c, par = r["child_method_id"], r["parent_id"]
    if par.split(".")[0] not in LAY and node_of(par.split(".")[0]) in LAY:
        par = node_of(par.split(".")[0])
    cl = next((CL[x] for x in r["supporting_claims"].split("; ") if x in CL), None)
    k = tuple(sorted((c.split(".")[0], par.split(".")[0])))
    if cl is None or c.split(".")[0] not in LAY or par.split(".")[0] not in LAY or k in _seen or k[0] == k[1]:
        continue
    _seen.add(k)
    t = r["proposed_type"]
    if t == "contains_special_case":
        c, par, t = par, c, "special_case_of"
    if t not in EDGE_WORDS:
        continue
    tedges.append({"edge_id": "par:%d" % _i, "from_id": c, "to_id": par, "type": t, "conditions": r["conditions"],
                   "statement": cl["conclusion"], "span": cl["span"], "paper": cl["paper_id"], "location": cl["location"]})
unstated = [r for r in _links if r["verdict"] == "not_stated" and r["to_id"] != "NA"
            and tuple(sorted((r["from_id"].split(".")[0], r["to_id"].split(".")[0]))) not in _seen]
CID = re.compile(r"\b([a-z0-9_]+:c\d+)\b")


def esc(s):
    return html.escape(s, quote=True)


def chip(cid):
    if cid not in CL:
        return f'<span class="chip dead">{esc(cid)}</span>'
    return f'<button class="chip" data-c="{esc(cid)}">{esc(cid.replace(":", " "))}</button>'


def chips(cell):
    return " ".join(chip(c) for c in cell.split("; ") if c and c != "NA")


def fmt(text):
    """Inline markdown subset + claim IDs to chips."""
    s = esc(text)
    s = re.sub(r"\[((?:[a-z0-9_]+:c\d+(?:, )?)+)\]", lambda m: " ".join(chip(c) for c in m.group(1).split(", ")), s)
    s = CID.sub(lambda m: m.group(0) if 'data-c="' + m.group(1) in s[max(0, m.start() - 12):m.start() + 1] or s[m.start() - 1:m.start()] in '">' else chip(m.group(1)), s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*]+)\*(?![*\w])", r"<em>\1</em>", s)
    return s


def name(mid):
    mid = mid.split(".")[0]
    return M[mid]["name"] if mid in M else (LAY[mid]["short"] if mid in LAY else mid)


EDGE_SHORT = {"extends": "extends", "special_case_of": "special case", "uses": "uses", "combines": "combines",
              "shares_structure_not_equivalent": "similar, not equal", "derivable_under_conditions": "derivable", "inspired_by": "inspired by"}
SOFT = {"shares_structure_not_equivalent", "inspired_by"}


# Only "builds on" relations are drawn: the earlier method is a component of the later one, or the later one extends or
# generalizes it. Similarity, inspiration and bare citation stay in the cards, not on the map.
BUILD = {"uses", "extends", "special_case_of", "derivable_under_conditions", "combines"}
ROLES = {}
if (T / "link_roles.tsv").exists():  # per-sentence reading: is the cited method a component the citing method builds on?
    ROLES = {r["link_id"]: r for r in read("link_roles.tsv")}


def drawn(e):
    r = ROLES.get(e["edge_id"])
    return (r["builds_on"] == "yes") if r else e["type"] in BUILD


def node_year(nid):
    """Publication year that orders the tree: earlier is higher. STATO terms and generic tools sit above all papers."""
    if nid in YEARS:
        return YEARS[nid]
    side = LAY[nid]["side"]
    if side == "stato":
        return -2
    if side == "gen":
        return -1
    pid = M[nid]["paper_id"] if nid in M else nid
    for src in (seed.get(pid, {}).get("year"), CNODE.get(nid, {}).get("year")):
        m = re.search(r"\d{4}", src or "")
        if m:
            return int(m.group(0))
    return None


def graph():
    """A top-down tree: one directed edge component -> method that builds on it, earlier methods above later ones,
    and no edge A -> C when A -> B -> C already says it (transitive reduction)."""
    cand = {}

    def add(comp, builder, word, ev, st=0):
        if comp == builder or comp not in LAY or builder not in LAY:
            return
        e = cand.setdefault((comp, builder), {"a": comp, "b": builder, "w": [], "ev": [], "st": st})
        if word not in e["w"]:
            e["w"].append(word)
        e["ev"].append(ev)

    for e in tedges:
        if not drawn(e):
            continue
        f, t = e["from_id"].split(".")[0], e["to_id"].split(".")[0]
        role = ROLES.get(e["edge_id"])
        comp, builder = (t, f) if e["type"] != "special_case_of" else (f, t)   # "f uses/extends t": t is the component
        if role and role["earlier_method"] != "NA" and role["later_method"] != "NA":
            rc, rb = node_of(role["earlier_method"].split(".")[0]), node_of(role["later_method"].split(".")[0])
            if {rc, rb} == {f, t}:
                comp, builder = rc, rb
        word = role["component_role"].replace("_", " ") if role else EDGE_SHORT[e["type"]]
        add(comp, builder, word, {"t": name(comp) + " → " + name(builder) + ": " + word + ((" when " + e["conditions"]) if e["conditions"] != "NA" else ""),
                                  "s": role["role_statement"] if role else e["statement"], "q": clean_span(e["span"]), "src": name(e["paper"]) + " · " + e["location"]})
    for r in stato_map:
        if r["match"] in ("exact", "close"):
            add(sid(r["stato_id"]), r["item_id"], "STATO " + r["match"], {"t": "STATO match: " + r["match"], "s": r["note"], "q": STATO[r["stato_id"]]["definition"],
                "src": "The map-maker's reading of STATO's definition (quoted). Not a sentence from a paper."}, st=1)
    # years: unknown years are inferred from neighbours so the node still lands between them
    year = {n: node_year(n) for n in LAY}
    for _ in range(3):
        for (c, b) in cand:
            if year.get(c) is None and year.get(b) is not None:
                year[c] = year[b] - 1
            if year.get(b) is None and year.get(c) is not None:
                year[b] = year[c] + 1
    # a generic tool or STATO term has no date: it floats to just above the earliest method built on it
    for _ in range(3):
        for n in LAY:
            if LAY[n]["side"] in ("gen", "stato"):
                ys = [year[b] for (c, b) in cand if c == n and year.get(b) is not None and (year[b] > 0 or LAY[b]["side"] in ("gen", "stato"))]
                ys = [y for y in ys if y > 0]
                if ys:
                    year[n] = min(ys)
    dropped_time = [k for k in cand if year.get(k[0]) is None or year.get(k[1]) is None or year[k[0]] > year[k[1]]]
    for k in dropped_time:
        del cand[k]
    for (c, b) in list(cand):  # both directions inside one year: keep the better-supported one
        if (b, c) in cand and (c, b) in cand:
            del cand[(c, b) if len(cand[(c, b)]["ev"]) < len(cand[(b, c)]["ev"]) else (b, c)]
    kids = defaultdict(set)
    for (c, b) in cand:
        kids[c].add(b)
    state = {}

    def dfs(u):  # drop back edges so the same-year part is acyclic
        state[u] = 1
        for v in sorted(kids[u]):
            if state.get(v) == 1:
                kids[u].discard(v); cand.pop((u, v), None)
            elif v not in state:
                dfs(v)
        state[u] = 2

    import sys
    sys.setrecursionlimit(10000)
    for u in sorted(kids):
        if u not in state:
            dfs(u)
    reach = {}

    def desc(u):
        if u not in reach:
            reach[u] = set()
            for v in kids[u]:
                reach[u] |= {v} | desc(v)
        return reach[u]

    redundant = [(u, v) for (u, v) in cand if any(v in desc(w) for w in kids[u] if w != v)]
    for k in redundant:
        del cand[k]
    out = list(cand.values())
    linked = {x for e in out for x in (e["a"], e["b"])}
    # a STATO term stays only when it leads to a method or generic tool that has a paper-stated link
    core = {x for e in out if not e["st"] for x in (e["a"], e["b"])}
    out = [e for e in out if not e["st"] or e["b"] in core]
    linked = {x for e in out for x in (e["a"], e["b"])}
    # rows: by year, then by depth inside the year
    par = defaultdict(set)
    for e in out:
        par[e["b"]].add(e["a"])
    depth = {}

    def dep(u):
        if u not in depth:
            depth[u] = 0
            depth[u] = max([dep(p) + 1 for p in par[u] if year[p] == year[u]] or [0])
        return depth[u]

    keys = sorted({(year[n], dep(n)) for n in linked})
    rowof = {k: i for i, k in enumerate(keys)}
    rows = defaultdict(list)
    for n in sorted(linked, key=lambda n: (LAY[n]["side"], n)):
        rows[rowof[(year[n], dep(n))]].append(n)
    # ontology tree: every star hangs under ONE parent (its primary component); other components show only on selection
    RANK = ["generalizes", "model", "building block", "extends", "special case", "prior", "likelihood", "derivable", "uses", "combines",
            "fitting algorithm", "output", "theory", "STATO exact", "STATO close"]
    rk = lambda e: min([RANK.index(w) for w in e["w"] if w in RANK] or [len(RANK)])
    sidek = lambda n: {"stato": 2, "gen": 1}.get(LAY[n]["side"], 0)
    inc = defaultdict(list)
    for e in out:
        inc[e["b"]].append(e)
    for b, es in inc.items():
        best = min(es, key=lambda e: (sidek(e["a"]), rk(e), -year[e["a"]], e["a"]))
        for e in es:
            if e is not best:
                e["sec"] = 1
    prim = [e for e in out if not e.get("sec")]
    linked = {x for e in prim for x in (e["a"], e["b"])}
    out = [e for e in out if e["a"] in linked and e["b"] in linked]
    par = defaultdict(set); kid = defaultdict(list)
    for e in prim:
        par[e["b"]].add(e["a"]); kid[e["a"]].append(e["b"])
    depth.clear()
    keys = sorted({(year[n], dep(n)) for n in linked})
    rowof = {k: i for i, k in enumerate(keys)}
    nrow = {n: rowof[(year[n], dep(n))] for n in linked}
    xpos, cursor = {}, [0.0]

    def place_tree(u):
        ks = sorted(kid[u], key=lambda n: (nrow[n], n))
        if not ks:
            xpos[u] = cursor[0]; cursor[0] += 1.7
        else:
            for k in ks:
                place_tree(k)
            xpos[u] = sum(xpos[k] for k in ks) / len(ks)

    order = {"stato": 0, "gen": 1, "cite": 2, "fsusie": 3, "prs": 4}
    for root in sorted([n for n in linked if not par[n]], key=lambda n: (order[LAY[n]["side"]], nrow[n], n)):
        place_tree(root); cursor[0] += 1.2
    for e in out:
        a, b = e["a"], e["b"]
        if e.get("sec") or nrow[b] - nrow[a] <= 1:
            e["pts"] = [[round(xpos[a], 2), float(nrow[a])], [round(xpos[b], 2), float(nrow[b])]]
        else:  # drop straight down the child's own column, then one slanted step up to the parent
            e["pts"] = [[round(xpos[a], 2), float(nrow[a])], [round(xpos[b], 2), float(nrow[a] + 1)], [round(xpos[b], 2), float(nrow[b])]]
    nodes = []
    for r in layout:
        n = r["method_id"]
        if n not in linked:
            continue
        side = r["side"]
        cnt = len(by_method.get(n, [])) if side in ("fsusie", "prs") else 3 * sum(1 for e in out if n in (e["a"], e["b"]))
        yr = year[n]
        labels = [x for x in r["labels"].split("|") if x and x != "NA" and not re.fullmatch(r"\d{4}", x)]
        nodes.append({"id": n, "side": side, "x": round(xpos[n], 2), "y": float(rowof[(year[n], dep(n))]), "t": int(r["tier"]), "n": r["short"],
                      "l": ([str(yr)] if yr and yr > 0 else []) + labels, "c": cnt, "ext": n not in M and side not in ("stato", "cite", "gen")})
    rowlab = [{"y": float(min(i for kk, i in rowof.items() if kk[0] == yv)), "t": str(yv)} for yv in sorted({k[0] for k in rowof}) if yv > 0]
    for e in out:
        e["x"], e["soft"] = 0, 0
        pass
    print(f"tree: {len(nodes)} stars, {len(prim)} tree links + {len(out) - len(prim)} secondary; dropped {len(dropped_time)} against time order, {len(redundant)} implied by a longer chain")
    return {"nodes": nodes, "edges": out, "rows": rowlab}


def graph_ontology():
    """The tree as an ontology (tables/ontology.tsv): every class has one parent class, earlier above later.
    A parent link carries a quoted sentence when the stored papers state it; otherwise it is dashed and says so.
    Other paper-stated components between two classes show when a star is tapped."""
    onto = [r for r in _raw("ontology.tsv") if canon(r["class_id"]) in LAY]
    for r in _raw("ontology.tsv"):
        if canon(r["class_id"]) not in LAY:
            print("WARNING: ontology class not on the map:", r["class_id"])
    cls = {canon(r["class_id"]): r for r in onto}
    stated = defaultdict(list)
    for e in tedges:
        f, t = e["from_id"].split(".")[0], e["to_id"].split(".")[0]
        if f in cls and t in cls and f != t:
            role = ROLES.get(e["edge_id"])
            word = role["component_role"].replace("_", " ") if role else EDGE_SHORT[e["type"]]
            stated[frozenset((f, t))].append((drawn(e), {"t": name(f) + " " + EDGE_WORDS[e["type"]] + " " + name(t) + ((" when " + e["conditions"]) if e["conditions"] != "NA" else ""),
                                              "s": role["role_statement"] if role else e["statement"], "q": clean_span(e["span"]), "src": name(e["paper"]) + " · " + e["location"]}, word))
    out, kid, par = [], defaultdict(list), {}
    for c, r in cls.items():
        p = canon(r["parent_id"])
        if p == "NA" or p not in cls:
            continue
        ev = [x[1] for x in stated.get(frozenset((c, p)), [])]
        soft = 0
        if not ev and LAY[p]["side"] == "stato":
            ev = [{"t": "STATO class", "s": r["differentia"], "q": STATO[next(k for k in STATO if sid(k) == p)]["definition"], "src": "STATO definition (quoted). The placement under it is the map-maker's."}]
        elif not ev:
            soft = 1
            ev = [{"t": "is a kind of", "s": r["differentia"], "q": "", "src": "Placed by the map-maker. No sentence in the stored papers states this link yet."}]
        out.append({"a": p, "b": c, "w": ["is a"], "ev": ev, "st": 0, "x": 0, "soft": soft})
        kid[p].append(c); par[c] = p
    cokids = set()
    for c, r in cls.items():  # co-parents: other classes whose core component this class inherits (a shared child)
        for p in [canon(x) for x in r.get("co_parents", "NA").split("; ") if x and x != "NA"]:
            if p not in cls:
                continue
            lst = [x for x in stated.get(frozenset((c, p)), [])]
            ev = [x[1] for x in lst] or [{"t": "core component", "s": "Listed as a core component by the map-maker.", "q": "", "src": "No sentence in the stored papers states this link yet."}]
            out.append({"a": p, "b": c, "w": sorted({x[2] for x in lst}) or ["component"], "ev": ev, "st": 0, "x": 0, "soft": 0 if lst else 1, "co": 1})
            cokids.add(c)
    prim = {frozenset((e["a"], e["b"])) for e in out}
    for k, lst in stated.items():  # other paper-stated build-on links between two classes: shown on selection only
        good = [x for x in lst if x[0]]
        if k in prim or not good:
            continue
        a, b = sorted(k)
        out.append({"a": a, "b": b, "w": sorted({x[2] for x in good}), "ev": [x[1] for x in good], "st": 0, "x": 0, "soft": 0, "sec": 1})
    year = {n: node_year(n) for n in cls}

    def yr(n):  # a class without a date sits just above its earliest child
        if year[n] is None or year[n] < 0:
            ys = [yr(k) for k in kid[n]]
            year[n] = (min(ys) if ys else 2000)
        return year[n]

    for n in cls:
        yr(n)
    depth = {}

    def dep(n):
        if n not in depth:
            p = par.get(n)
            depth[n] = dep(p) + 1 if p and year[p] >= year[n] else 0
            if p and year[p] > year[n]:
                year[n] = year[p]
        return depth[n]

    for n in cls:
        dep(n)
    keys = sorted({(year[n], depth[n]) for n in cls})
    rowof = {k: i for i, k in enumerate(keys)}
    nrow = {n: rowof[(year[n], depth[n])] for n in cls}
    xpos, cursor = {}, [0.0]

    def has_co(u):
        return u in cokids or any(has_co(k) for k in kid[u])

    def place_tree(u):
        ks = sorted(kid[u], key=lambda n: (has_co(n), nrow[n], n))  # shared children go to the right, next to their other parents
        if not ks:
            xpos[u] = cursor[0]; cursor[0] += 1.9
        else:
            for k in ks:
                place_tree(k)
            xpos[u] = sum(xpos[k] for k in ks) / len(ks)

    for root in [c for c in cls if c not in par]:
        place_tree(root); cursor[0] += 1.0
    for e in out:
        a, b = e["a"], e["b"]
        if e.get("sec") or nrow[b] - nrow[a] <= 1:
            e["pts"] = [[round(xpos[a], 2), float(nrow[a])], [round(xpos[b], 2), float(nrow[b])]]
        else:
            e["pts"] = [[round(xpos[a], 2), float(nrow[a])], [round(xpos[b], 2), float(nrow[a] + 1)], [round(xpos[b], 2), float(nrow[b])]]
    nodes = []
    for n, r in cls.items():
        L = LAY[n]
        side = L["side"]
        dated = node_year(n) is not None and node_year(n) > 0
        nodes.append({"id": n, "side": side, "x": round(xpos[n], 2), "y": float(nrow[n]), "t": 1 if side in ("fsusie", "prs") else 2, "n": L["short"],
                      "l": ([str(year[n])] if dated else []) + [r["differentia"]], "c": len(by_method.get(n, [])) if side in ("fsusie", "prs") else 12,
                      "ext": n not in M and side not in ("stato", "cite", "gen")})
    rowlab = [{"y": float(min(i for kk, i in rowof.items() if kk[0] == yv)), "t": str(yv)} for yv in sorted({k[0] for k in rowof})]
    print(f"ontology tree: {len(nodes)} classes, {len(prim)} parent links incl. {sum(1 for e in out if e.get('co'))} co-parent ({sum(e['soft'] for e in out)} without a stating sentence), {sum(1 for e in out if e.get('sec'))} secondary")
    return {"nodes": nodes, "edges": out, "rows": rowlab}


YEARS = {r["node_id"]: int(r["year"]) for r in _raw("node_years.tsv")}
FINAL = set()  # pairs drawn on the tree; cards list the same links


for _r in layout:
    NSIDE[_r["method_id"]] = _r["side"]


def mlink(x):
    return f'<a href="#m-{esc(x)}" class="mref">{esc(name(x))}</a>'


def cite_lines(mid):
    """Citation lineage of a paper node: what it cites, what cites it, and its paths to STATO source papers."""
    out = [(r["cited_id"]) for r in cites if r["citing_id"] == mid]
    inn = [(r["citing_id"]) for r in cites if r["cited_id"] == mid]
    ps = [r for r in cpaths if r["method_paper"] == mid]
    if not (out or inn or ps):
        return ""
    h = '<section><h4>Citation lineage</h4><p class="note">From open citation indexes. A citation shows contact between papers, not a theoretical relationship.</p><dl class="comp">'
    if out:
        h += "<dt>Cites</dt><dd>" + ", ".join(mlink(x) for x in out) + "</dd>"
    if inn:
        h += "<dt>Cited by</dt><dd>" + ", ".join(mlink(x) for x in inn) + "</dd>"
    h += "</dl>"
    if ps:
        h += '<ul class="edges">' + "".join(f'<li>to <a href="#m-{sid(r["stato_id"])}" class="mref">{esc(STATO[r["stato_id"]]["label"])}</a>: ' + " → ".join(mlink(x) for x in r["path"].split(" > ")) + "</li>" for r in ps) + "</ul>"
    return h + "</section>"


def cite_card(r):
    n = CNODE[r["method_id"]]
    terms = [x for x in ssrc if x["node_id"] == r["method_id"]]
    h = f'<article class="method" id="m-{esc(r["method_id"])}"><header><h3>{esc(n["title"])}</h3><p class="note">{esc(n["first_author"])} {esc(n["year"])} · {esc(n["venue"])}{(" · doi " + esc(n["doi"])) if n["doi"] != "NA" else ""}</p></header>'
    h += f'<section><h4>Method it is known for</h4><p>{esc(r["short"])}</p><p class="note">Named by the map-maker from background knowledge; the paper is not read into the map.</p></section>'
    if terms:
        h += '<section><h4>STATO cites this paper for</h4><ul class="edges">' + "".join(f'<li><a href="#m-{sid(x["stato_id"])}" class="mref">{esc(x["label"])}</a></li>' for x in terms) + "</ul></section>"
    else:
        h += '<section><h4>Why it is here</h4><p>It lies on a shortest citation path between one of our method papers and a paper that STATO cites for a term. It has not been read into the map.</p></section>'
    return h + cite_lines(r["method_id"]) + "</article>"


def stato_card(r):
    """Detail card for a STATO star: the ontology's own definition plus what is anchored to it."""
    nid = r["method_id"]
    if nid == "stato_gap":
        rows = [x for x in stato_map if x["match"] == "gap" and x["item_id"] in LAY]
        h = f'<article class="method" id="m-{nid}"><header><h3>Not in STATO</h3><p class="note">Methods and tools in this map for which the STATO ontology has no term. These are the places where the map goes beyond the ontology.</p></header><section><h4>Gaps</h4><ul class="edges">'
        return h + "".join(f'<li><a href="#m-{esc(x["item_id"])}" class="mref">{esc(name(x["item_id"]))}</a><div class="enote">{esc(x["note"])}</div></li>' for x in rows) + "</ul></section></article>"
    t = next(v for k, v in STATO.items() if sid(k) == nid)
    rows = [x for x in stato_map if sid(x["stato_id"]) == nid and x["item_id"] in LAY]
    h = f'<article class="method" id="m-{nid}"><header><h3>{esc(t["label"])}</h3><p class="note">{esc(t["stato_id"])} · a term of the STATO statistics ontology</p></header>'
    h += f'<section><h4>STATO definition</h4><p>{esc(t["definition"])}</p></section>'
    src = t.get("definition_source", "NA")
    h += f'<section><h4>STATO\'s source for this term</h4><p>{esc(src) if src != "NA" else "STATO names no source for this term."}</p></section>'
    papers = [x["node_id"] for x in ssrc if x["stato_id"] == t["stato_id"] and x["node_id"] in LAY]
    if papers:
        h += '<section><h4>Source papers on the map</h4><p>' + ", ".join(mlink(x) for x in papers) + "</p></section>"
    if t["ancestor_labels"] != "NA":
        h += f'<section><h4>Sits under</h4><p>{esc(t["ancestor_labels"].replace(" > ", " → "))}</p></section>'
    h += '<section><h4>Methods anchored here</h4><p class="note">Links written by the lead from labels and definitions; not checked by a statistician.</p><ul class="edges">'
    h += "".join(f'<li><a href="#m-{esc(x["item_id"])}" class="mref">{esc(name(x["item_id"]))}</a> <span class="lbl">{esc(x["match"])}</span><div class="enote">{esc(x["note"])}</div></li>' for x in rows)
    return h + "</ul></section></article>"


def stato_lines(mid):
    rows = [x for x in stato_map if x["item_id"] == mid]
    if not rows:
        return ""
    li = ""
    for x in rows:
        if x["match"] == "gap":
            li += f'<li><a href="#m-stato_gap" class="mref">Not in STATO</a><div class="enote">{esc(x["note"])}</div></li>'
        elif sid(x["stato_id"]) in LAY:
            li += f'<li><a href="#m-{sid(x["stato_id"])}" class="mref">{esc(STATO[x["stato_id"]]["label"])}</a> <span class="lbl">{esc(x["match"])}</span><div class="enote">{esc(x["note"])}</div></li>'
    return f'<section><h4>Where it sits in STATO</h4><ul class="edges">{li}</ul></section>' if li else ""


def part(mid):
    return (" (" + mid.split(".")[1].replace("_", " ") + ")") if "." in mid else ""


def claim_li(c):
    badge = ' <span class="kind">theorem</span>' if c["kind"] == "theorem" else ""
    return f'<li>{esc(c["conclusion"])}{badge} {chip(c["claim_id"])}</li>'


def fold(title, items):
    if not items:
        return ""
    return f'<details class="fold"><summary>{title} <span class="n">{len(items)}</span></summary><ul>{"".join(claim_li(c) for c in items)}</ul></details>'


def edge_lines(mid):
    out = []
    for e in tedges:
        f, t = e["from_id"].split(".")[0], e["to_id"].split(".")[0]
        if (f != mid and t != mid) or not drawn(e) or frozenset((f, t)) not in FINAL:
            continue  # auxiliary analysis, benchmark, similarity and inspiration are left out of the card too
        if f == mid:
            line = f'<strong>{EDGE_WORDS[e["type"]]}</strong> <a href="#m-{esc(t)}" class="mref">{esc(name(t))}</a>{esc(part(e["to_id"]))}'
        else:
            line = f'<a href="#m-{esc(f)}" class="mref">{esc(name(f))}</a>{esc(part(e["from_id"]))} <strong>{EDGE_WORDS[e["type"]]}</strong> this'
        if e["conditions"] != "NA":
            line += f'<span class="when"> when {esc(e["conditions"])}</span>'
        line += f'<div class="enote">{esc(e["statement"])}</div><blockquote>“{esc(clean_span(e["span"]))}”</blockquote><div class="enote">{esc(name(e["paper"]))} · {esc(e["location"])}</div>'
        out.append(f"<li>{line}</li>")
    return out


def unstated_lines(mid):
    rows = [r for r in unstated if mid in (r["from_id"].split(".")[0], r["to_id"].split(".")[0])]
    if not rows:
        return ""
    li = "".join(f'<li>{mlink(r["from_id"].split(".")[0])} and {mlink(r["to_id"].split(".")[0])}: {esc(EDGE_WORDS.get(r["type"], r["type"]))}</li>' for r in rows)
    return f'<details class="fold"><summary>Ideas not stated in any stored paper <span class="n">{len(rows)}</span></summary><p class="note">The map-maker\'s own suggestions. No passage in the stored papers names both methods, so these are not drawn.</p><ul>{li}</ul></details>'


def method_card(mid, note="", num=None):
    m = M.get(mid)
    cs = by_method.get(mid, [])
    role = lambda r: [c for c in cs if c["role"] == r]
    h = f'<article class="method" id="m-{esc(mid)}">'
    h += f'<header><h3>{("<span class=step>%d</span> " % num) if num else ""}{esc(name(mid))}</h3>'
    if note:
        h += f'<p class="note">{esc(note)}</p>'
    h += "</header>"
    folded = [a for a, r in ALIAS.items() if r["canonical_id"] == mid]
    if folded:
        h += '<section><h4>Parts and other names of this method</h4><ul class="plain">' + "".join(f'<li><strong>{esc(a.replace("_", " "))}</strong> <span class="lbl">{esc(ALIAS[a]["kind"].replace("_", " "))}</span><div class="enote">{esc(ALIAS[a]["reason"])}</div></li>' for a in folded) + "</ul></section>"
    mot = role("motivation")
    if mot:
        h += '<section><h4>The problem it answers</h4><ul class="plain">' + "".join(claim_li(c) for c in mot) + "</ul></section>"
    if m:
        h += '<section><h4>What it is</h4><dl class="comp">'
        for key, lab in [("model_likelihood", "Model"), ("prior", "Prior"), ("inference_algorithm", "Fitting"), ("estimand", "Reports"), ("data_input", "Data")]:
            if m[key] != "NA":
                h += f"<dt>{lab}</dt><dd>{esc(m[key])}</dd>"
        if m["tunable_settings"] != "NA":
            h += f'<dt>You set</dt><dd>{esc(m["tunable_settings"])}</dd>'
        h += "</dl></section>"
    el = edge_lines(mid)
    if not el and m:
        h += '<section><h4>How it connects</h4><p class="note">Detached on purpose: no passage in the stored paper names this method together with another method on the map, so no link is drawn.</p></section>'
    if el:
        h += '<section><h4>How it connects</h4><ul class="edges">' + "".join(el) + "</ul></section>"
    h += stato_lines(mid)
    h += fold("Assumes", role("assumption")) + fold("Guarantees and stated results", role("guarantee"))
    h += fold("Stated limits", role("limitation")) + fold("What the authors say about other methods", role("relation"))
    return h + "</article>"


def mermaid(side):
    es = [e for e in edges if e["edge_id"].startswith(side + ":")]
    ids = []
    for e in es:
        for x in (e["from_id"].split(".")[0], e["to_id"].split(".")[0]):
            if x not in ids:
                ids.append(x)
    short = lambda x: re.sub(r"\s*\(.*?\)", "", name(x))[:28]
    lines = ["graph TD"] + [f'  n{i}["{short(x)}"]' for i, x in enumerate(ids)]
    for e in es:
        a, b = ids.index(e["from_id"].split(".")[0]), ids.index(e["to_id"].split(".")[0])
        lines.append(f'  n{a} -->|{e["type"].replace("_", " ").replace(" not equivalent", "")}| n{b}')
    return '<details class="fold diagram"><summary>Diagram of all typed relationships</summary><div class="scroll"><pre class="mermaid">' + esc("\n".join(lines)) + "</pre></div></details>"


ONTO_WALK = False


def onto_walk(G, targets, side):
    """Reading path from the roots of the ontology down to the target classes, oldest first."""
    onto = {canon(r["class_id"]): r for r in _raw("ontology.tsv")}
    row = {n["id"]: n["y"] for n in G["nodes"]}
    seen = []

    def up(c):
        if c in seen or c not in onto:
            return
        r = onto[c]
        for p in [canon(r["parent_id"])] + [canon(x) for x in r.get("co_parents", "NA").split("; ")]:
            if p and p != "NA":
                up(p)
        seen.append(c)

    for t in targets:
        up(t)
    seen.sort(key=lambda c: row.get(c, 0))
    out = []
    for i, c in enumerate(seen, 1):
        r = onto[c]
        ps = [canon(r["parent_id"])] + [canon(x) for x in r.get("co_parents", "NA").split("; ")]
        ps = [name(p) for p in ps if p and p != "NA"]
        note = (("Built on " + " and ".join(ps) + ". What is new: ") if ps else "Starting point: ") + r["differentia"] + "."
        out.append({"side": side, "order": str(i), "method_id": c, "note": note})
    return out


def lineage(side, title, lead):
    walk = sorted([o for o in order if o["side"] == side], key=lambda o: int(o["order"]))
    inwalk = {o["method_id"] for o in walk}
    h = f'<section class="view" id="v-{side}"><h2>{title}</h2><p class="lead">{lead}</p>'
    h += '<p class="hint">Read top to bottom: oldest ancestor first. Tap any <span class="chip demo">id</span> to see the quoted sentence behind a statement.</p>'
    for i, o in enumerate(walk, 1):
        if o["method_id"] in M:
            h += method_card(o["method_id"], o["note"], i)
        else:  # a generic class: its full card lives with the map; here it is one step of the path
            h += f'<article class="method"><header><h3><span class="step">{i}</span> {esc(name(o["method_id"]))}</h3><p class="note">{esc(o["note"])}</p></header></article>'
    rest = [] if ONTO_WALK else [mid for mid, m in M.items() if m["side"] == side and mid not in inwalk]
    if rest:
        h += f'<details class="fold blocks"><summary>Building blocks and variants <span class="n">{len(rest)}</span></summary>' + "".join(method_card(x) for x in rest) + "</details>"
    return h + "</section>"


def md(text):
    """Small markdown-to-HTML converter for the lead's reports."""
    out, para, lst, tbl = [], [], [], []

    def flush():
        nonlocal para, lst, tbl
        if para:
            out.append("<p>" + fmt(" ".join(para)) + "</p>")
        if lst:
            out.append("<ul>" + "".join("<li>" + fmt(x) + "</li>" for x in lst) + "</ul>")
        if tbl:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl if not re.match(r"^\|[-| ]+\|$", r.strip())]
            if len(rows[0]) > 5:  # wide table: one card per row
                for r in rows[1:]:
                    out.append('<article class="rowcard"><h3>' + fmt(r[0]) + "</h3><dl class=\"comp\">" + "".join(f"<dt>{esc(k)}</dt><dd>{fmt(v)}</dd>" for k, v in zip(rows[0][1:], r[1:])) + "</dl></article>")
            else:
                out.append('<div class="scroll"><table><thead><tr>' + "".join(f"<th>{fmt(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{fmt(c)}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</tbody></table></div>")
        para, lst, tbl = [], [], []

    for line in text.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush(); out.append("<h3>" + fmt(line[3:]) + "</h3>")
        elif line.startswith("|"):
            if not tbl:
                flush()
            tbl.append(line)
        elif re.match(r"^(\d+\.|-) ", line):
            if para or tbl:
                flush()
            lst.append(re.sub(r"^(\d+\.|-) ", "", line))
        elif line.startswith("  ") and lst:
            lst[-1] += " " + line.strip()
        elif not line.strip():
            flush()
        else:
            if lst or tbl:
                flush()
            para.append(line.strip())
    flush()
    return "\n".join(out)


def questions_view():
    h = '<section class="view" id="v-questions"><h2>Open questions</h2><p class="lead">Theoretical questions the sources leave unsettled. Each one names the missing premise that would settle it. None has been answered by reasoning here.</p>'

    def card(q):
        return f'<article class="q"><p class="qq">{esc(q["question"])}</p><p><span class="lbl">missing premise</span> {esc(q["missing_premise"])}</p><p>{chips(q["related_claims"])}</p></article>'

    mine = [q for q in questions if q["oq_id"].startswith("lead")]
    h += "<h3>Across methods</h3>" + "".join(card(q) for q in mine)
    groups = defaultdict(list)
    for q in questions:
        if not q["oq_id"].startswith("lead"):
            groups[q["oq_id"].split(":")[0]].append(q)
    h += "<h3>Raised while reading each paper</h3>"
    for p, qs in groups.items():
        h += f'<details class="fold"><summary>{esc(name(p))} <span class="n">{len(qs)}</span></summary>' + "".join(card(q) for q in qs) + "</details>"
    return h + "</section>"


def clean_span(s):
    s = re.sub(r"\\documentclass\[12pt\]\{minimal\}.*?\\begin\{document\}", " ", s)
    return s.replace("\\end{document}", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "map.html"))
    ap.add_argument("--public", action="store_true", help="standalone copy for a public site: no Aim 3 or combination tabs, with a doctype")
    a = ap.parse_args()
    G = graph_ontology() if (T / "ontology.tsv").exists() else graph()
    FINAL.update(frozenset((e["a"], e["b"])) for e in G["edges"])
    data = {c["claim_id"]: {"m": name(c["method_id"]), "role": c["role"], "kind": c["kind"].replace("_", " "), "tag": c["tag"],
                            "k": c["conclusion"], "a": c["assumptions"], "s": c["scope"], "q": clean_span(c["span"]),
                            "e": c["eq_ref"], "l": c["location"], "p": c["premises"]} for c in claims}
    n_edges = len(edges)
    body = (ROOT / "scripts" / "page_template.html").read_text()
    aim3 = "" if a.public else md((ROOT / "reports" / "aim3_table.md").read_text().replace("Hao's", "your"))
    combo = "" if a.public else md((ROOT / "reports" / "combination.md").read_text())
    cross = "".join(f'<li><a href="#m-{esc(e["from_id"].split(".")[0])}" class="mref">{esc(name(e["from_id"]))}</a>{esc(part(e["from_id"]))} <strong>{EDGE_WORDS[e["type"]]}</strong> <a href="#m-{esc(e["to_id"].split(".")[0])}" class="mref">{esc(name(e["to_id"]))}</a>{esc(part(e["to_id"]))}<div class="enote">{esc(e["note"])} {chips(e["supporting_claims"])}</div></li>' for e in edges if e["edge_id"].startswith("x:"))
    ext = "".join(method_card(r["method_id"], ("No open copy of this paper was found: only its title is stored. It needs a Zotero copy to be read in." if r["method_id"] in seed else "Named in the stored papers. Its own paper is not in this map yet.")) for r in layout if r["method_id"] not in M and r["side"] not in ("stato", "cite", "gen"))
    ext += "".join(method_card(r["method_id"], "A generic statistical tool. It has no paper of its own on this map: each link below is a sentence from the paper that says it uses it.") for r in layout if r["side"] == "gen")
    ext += "".join(cite_card(r) for r in layout if r["side"] == "cite")
    ext += "".join(stato_card(r) for r in layout if r["side"] == "stato")
    views = f'<div id="extcards" hidden>{ext}</div>'
    if (T / "ontology.tsv").exists():  # the two walks follow the tree: every step says what it is built on and what is new
        global ONTO_WALK
        ONTO_WALK = True
        order[:] = onto_walk(G, ["fsusie"], "fsusie") + onto_walk(G, ["bridgeprs", "prscsx", "ldpred", "prsice2"], "prs")
    views += lineage("fsusie", "The SuSiE lineage", "The path down the tree to fSuSiE, one step at a time. Each step says what it is built on and what is new.")
    views += lineage("prs", "BridgePRS and its neighbors", "The paths down the tree to BridgePRS, PRS-CSx, LDpred and C+T, one step at a time.")
    views += f'<section class="view" id="v-aim3"><h2>Aim 3: the PRS methods side by side</h2>{aim3}</section>'
    views += f'<section class="view" id="v-combination"><h2>Candidate combination</h2><h3>Hypothesised bridges between the two families</h3><p class="note">None of these is stated in any stored paper, so none is drawn on the map. They are suggestions by the map-maker.</p><ul class="edges">{cross}</ul>{combo}</section>'
    if a.public:  # thesis-specific material stays out of the public copy
        views = re.sub(r'<section class="view" id="v-aim3">.*?</section>\s*(?=<section class="view" id="v-combination">)', '<section class="view" id="v-aim3"><h2>Not in the public copy</h2></section>', views, flags=re.S)
        views = views[:views.index('<section class="view" id="v-combination">')] + '<section class="view" id="v-combination"><h2>Not in the public copy</h2></section>'
    views += questions_view()
    views += '<section class="view" id="v-claims"><h2>All claims</h2><p class="lead">Search every sourced statement.</p><div class="search"><input id="q" type="search" placeholder="Search, for example: convergence, LD, tau" aria-label="Search claims"><select id="role" aria-label="Kind of statement"><option value="">Any kind</option><option>motivation</option><option>definition</option><option>assumption</option><option>guarantee</option><option>limitation</option><option>relation</option><option>setting</option></select></div><div id="results"></div></section>'
    stats = f"{len({c['paper_id'] for c in claims})} papers · {len(claims)} sourced claims · {n_edges} typed relationships · {len(questions)} open questions"
    page = body.replace("{{VIEWS}}", views).replace("{{STATS}}", stats).replace("{{GRAPH}}", json.dumps(G)).replace("{{DATA}}", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    if a.public:
        page = re.sub(r'<a href="#aim3">[^<]*</a><a href="#combination">[^<]*</a>', "", page)
        page = '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + page + "\n</html>\n"
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(page)
    print(f"{a.out}: {len(page) // 1024} kB")


if __name__ == "__main__":
    main()
