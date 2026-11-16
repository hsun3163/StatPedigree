#!/usr/bin/env python3
"""Flatten sources/stato/stato.owl into tables/stato_terms.tsv (id, label, definition, parents, ancestors, definition source as STATO gives it).

Usage: python scripts/stato_terms.py [--owl sources/stato/stato.owl] [--out tables/stato_terms.tsv]
"""
import argparse, csv, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = {"owl": "http://www.w3.org/2002/07/owl#", "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      "rdfs": "http://www.w3.org/2000/01/rdf-schema#", "obo": "http://purl.obolibrary.org/obo/"}
RDF = "{%s}" % NS["rdf"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--owl", default=str(ROOT / "sources/stato/stato.owl"))
    ap.add_argument("--out", default=str(ROOT / "tables/stato_terms.tsv"))
    a = ap.parse_args()
    terms = {}
    for c in ET.parse(a.owl).getroot().findall("owl:Class", NS):
        iri = c.get(RDF + "about")
        if not iri:
            continue
        tid = iri.rsplit("/", 1)[-1].replace("_", ":")
        lab = c.find("rdfs:label", NS)
        d = c.find("obo:IAO_0000115", NS)
        par = [p.get(RDF + "resource").rsplit("/", 1)[-1].replace("_", ":") for p in c.findall("rdfs:subClassOf", NS) if p.get(RDF + "resource")]
        clean = lambda e: " ".join((e.text or "").split()) if e is not None else "NA"
        terms[tid] = {"stato_id": tid, "label": clean(lab), "definition": clean(d) or "NA", "parents": par,
                      "source": " ;; ".join(clean(x) for x in c.findall("obo:IAO_0000119", NS) if clean(x)) or "NA"}

    def anc(t, seen=()):
        out = []
        for p in terms.get(t, {}).get("parents", []):
            if p not in seen and p not in out:
                out.append(p)
                out += [x for x in anc(p, seen + (t,)) if x not in out]
        return out

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        w.writerow(["stato_id", "label", "definition", "parents", "ancestor_labels", "definition_source"])
        for t in sorted(terms.values(), key=lambda t: t["stato_id"]):
            w.writerow([t["stato_id"], t["label"], t["definition"].replace("\t", " ") or "NA", "; ".join(t["parents"]) or "NA",
                        " > ".join(terms[x]["label"] for x in anc(t["stato_id"]) if x in terms) or "NA", t["source"].replace("\t", " ")])
    print(len(terms), "terms ->", a.out)


if __name__ == "__main__":
    main()
