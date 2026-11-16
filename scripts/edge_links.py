#!/usr/bin/env python3
"""Review paper-stated links using retained sources only.

From the project root:
  python scripts/edge_links.py --prepare
  python scripts/edge_links.py --build
  python scripts/edge_links.py --check

--prepare freezes the three input tables and writes a searchable paragraph index.
Human-reviewed decisions live in tmp/edge_links/decisions.json. Each decision
selects an exact claim span or an exact start/end substring in a retained source;
no relation is inferred by this program. --build materializes those decisions.
--check is read-only and always checks against the current tables and sources.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/edge_links'
FIELDS = 'edge_id from_id to_id type verdict stated_type conditions paper_id location link_span statement existing_claim'.split()
TYPES = set('uses extends special_case_of combines shares_structure_not_equivalent derivable_under_conditions inspired_by'.split())
VERDICTS = {'stated', 'stated_other_type', 'not_stated'}


def norm(value):
    return ' '.join(value.split())


def read_table(name):
    with (ROOT / 'tables' / (name + '.tsv')).open(newline='') as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def source_paths(paper):
    return [ROOT / 'sources' / (paper + suffix) for suffix in ('.txt', '.supp.txt')]


def prepare():
    WORK.mkdir(parents=True, exist_ok=True)
    snapshot = {name: read_table(name) for name in ('relationships', 'methods', 'claims')}
    snapshot['source_hashes'] = {}
    papers = sorted({r['paper_id'] for r in snapshot['methods']} |
                    {e[k].split('.')[0] for e in snapshot['relationships']
                     for k in ('from_id', 'to_id')
                     if any(p.exists() for p in source_paths(e[k].split('.')[0]))})
    with (WORK / 'paragraphs.tsv').open('w', newline='') as handle:
        out = csv.writer(handle, delimiter='\t')
        out.writerow(['paper_id', 'source_file', 'line', 'heading', 'text'])
        for paper in papers:
            for path in source_paths(paper):
                if not path.exists():
                    continue
                snapshot['source_hashes'][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
                heading = 'NA'
                for lineno, line in enumerate(path.read_text().splitlines(), 1):
                    if line.startswith('## '):
                        heading = norm(line[3:])
                    if line.strip():
                        out.writerow([paper, path.name, lineno, heading, norm(line)])
    (WORK / 'inputs.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    print(f"Prepared {len(snapshot['relationships'])} edges; {len(snapshot['methods'])} method rows; {len(papers)} papers.")


def select(decision, snapshot):
    claims = {r['claim_id']: r for r in snapshot['claims']}
    if 'claim' in decision:
        c = claims[decision['claim']]
        paper = c['paper_id']
        path = source_paths(paper)[c['source_file'] == 'supp']
        span = norm(c['span'])
    else:
        paper = decision['paper_id']
        path = source_paths(paper)[decision.get('source_file', 'main') == 'supp']
        text = norm(path.read_text())
        start = norm(decision['start'])
        if text.count(start) != 1:
            raise ValueError(f"Nonunique/missing start ({text.count(start)}): {decision['edge_id']}")
        pos = text.index(start)
        if 'end' in decision:
            end = norm(decision['end'])
            stop = text.index(end, pos) + len(end)
            span = text[pos:stop]
        else:
            span = start
    text = norm(path.read_text())
    if span not in text:
        raise ValueError(f"Missing selected span: {decision['edge_id']}")
    # Heading and source line identify the beginning of the quoted passage.
    heading = 'NA'
    prefix = ''
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if line.startswith('## '):
            heading = norm(line[3:])
        prefix = norm(prefix + ' ' + line)
        if len(prefix) >= text.index(span) + len(span.split()[0]):
            break
    existing = next((c['claim_id'] for c in snapshot['claims']
                     if c['paper_id'] == paper and c['source_file'] == ('supp' if path.name.endswith('.supp.txt') else 'main')
                     and span in norm(c['span'])), 'NA')
    section = claims[existing]['location'] if existing != 'NA' else decision.get('section', heading)
    return paper, f'{path.name} | line {lineno} | {section}', span, existing


def build():
    snapshot = json.loads((WORK / 'inputs.json').read_text())
    decisions = json.loads((WORK / 'decisions.json').read_text())
    edges = {r['edge_id']: r for r in snapshot['relationships']}
    rows = []
    for d in decisions:
        e = edges.get(d['edge_id'], d)
        row = dict.fromkeys(FIELDS, 'NA')
        for key in ('edge_id', 'from_id', 'to_id', 'type'):
            row[key] = e.get(key, 'NA')
        row['verdict'] = d.get('verdict', 'stated')
        if row['verdict'] != 'not_stated':
            row['stated_type'] = d.get('stated_type', row['type'])
            row['conditions'] = d.get('conditions', 'NA')
            row['statement'] = d['statement']
            row['paper_id'], row['location'], row['link_span'], row['existing_claim'] = select(d, snapshot)
        rows.append(row)
    with (ROOT / 'tables/edge_links.tsv').open('w', newline='') as handle:
        out = csv.DictWriter(handle, fieldnames=FIELDS, delimiter='\t', lineterminator='\n')
        out.writeheader()
        out.writerows(rows)
    print(f'Wrote {len(rows)} reviewed rows.')


def check():
    rows = read_table('edge_links')
    edges = {r['edge_id']: r for r in read_table('relationships')}
    claims = {r['claim_id']: r for r in read_table('claims')}
    methods = {r['method_id'] for r in read_table('methods')}
    failures = []
    span_failures = 0
    ids = collections.Counter(r['edge_id'] for r in rows)
    for edge in edges:
        if ids[edge] != 1:
            failures.append(f'{edge}: expected exactly one audited row, found {ids[edge]}')
    cache = {}
    for r in rows:
        eid = r['edge_id']
        if list(r) != FIELDS or None in r or any(v is None or v == '' for v in r.values()):
            failures.append(f'{eid}: malformed header or empty cell')
        if ids[eid] != 1:
            failures.append(f'{eid}: duplicate edge_id')
        if eid in edges:
            for key in ('from_id', 'to_id', 'type'):
                if r[key] != edges[eid][key]:
                    failures.append(f'{eid}: {key} differs from audited edge')
        elif not (re.fullmatch(r'new:\d+', eid) or eid.startswith('none:')):
            failures.append(f'{eid}: unknown edge identity')
        if r['verdict'] not in VERDICTS:
            failures.append(f'{eid}: invalid verdict')
        if r['verdict'] == 'not_stated':
            for key in ('stated_type', 'conditions', 'paper_id', 'location', 'link_span', 'statement', 'existing_claim'):
                if r[key] != 'NA':
                    failures.append(f'{eid}: not_stated {key} must be NA')
            continue
        if r['type'] not in TYPES or r['stated_type'] not in TYPES:
            failures.append(f'{eid}: invalid schema type')
        if (r['verdict'] == 'stated') != (r['type'] == r['stated_type']):
            failures.append(f'{eid}: verdict and stated_type disagree')
        if len(r['statement'].split()) > 30 or r['statement'] == 'NA':
            failures.append(f'{eid}: statement missing or exceeds 30 words')
        paper = r['paper_id']
        if paper not in cache:
            cache[paper] = [norm(p.read_text()) for p in source_paths(paper) if p.exists()]
        if r['link_span'] == 'NA' or not any(norm(r['link_span']) in t for t in cache[paper]):
            failures.append(f'{eid}: span absent from stored sources')
            span_failures += 1
        claim = r['existing_claim']
        if claim != 'NA' and (claim not in claims or claims[claim]['paper_id'] != paper
                                 or norm(r['link_span']) not in norm(claims[claim]['span'])):
            failures.append(f'{eid}: existing_claim does not contain passage')
        if eid.startswith('new:'):
            pair = {r['from_id'], r['to_id']}
            if any(pair == {e['from_id'], e['to_id']} for e in edges.values()):
                failures.append(f'{eid}: duplicates an audited endpoint pair')
    for method in methods:
        if not any(r['verdict'] != 'not_stated' and method in
                   (r['from_id'].split('.')[0], r['to_id'].split('.')[0]) for r in rows):
            if ids['none:' + method] != 1:
                failures.append(f'{method}: lacks positive link or none row')
    print('Verdicts:', dict(collections.Counter(r['verdict'] for r in rows)))
    print('Audited:', dict(collections.Counter(r['verdict'] for r in rows if r['edge_id'] in edges)))
    print('New stated links:', sum(r['edge_id'].startswith('new:') and r['verdict'] == 'stated' for r in rows))
    print('Methods with no stating passage:', ', '.join(r['from_id'] for r in rows if r['edge_id'].startswith('none:')) or 'none')
    print(f'Audited edge coverage: {sum(ids[e] == 1 for e in edges)}/{len(edges)}')
    print(f'Failing spans: {span_failures}; total failures: {len(failures)}')
    for failure in failures:
        print('FAIL:', failure)
    return bool(failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--build', action='store_true')
    modes.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.build:
        build()
    else:
        sys.exit(check())


if __name__ == '__main__':
    main()
