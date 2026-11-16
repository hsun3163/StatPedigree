#!/usr/bin/env python3
"""Render the draft map from tables and seed metadata; personal notes are preserved."""
import argparse
import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = 'Unverified draft map — generated from tables/, do not edit'
COMPONENTS = 'model_likelihood prior inference_algorithm estimand data_input'.split()


def read(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def items(value):
    return [v.strip() for v in value.split(';') if v.strip() not in ('', 'NA')]


def link(kind, ident):
    if ident in ('', 'NA'):
        return 'NA'
    slug = ident.replace(':', '_') if kind in ('claims', 'open-questions') else ident
    return f'[[{kind}/{slug}|{ident}]]'


def claims(value):
    return ', '.join(link('claims', ident) for ident in items(value)) or 'NA'


def method(endpoint):
    return endpoint.split('.', 1)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tables', type=Path, default=ROOT / 'tables')
    parser.add_argument('--out', type=Path, default=ROOT / 'vault')
    parser.add_argument('--html', type=Path, help='Optional self-contained HTML reading copy')
    args = parser.parse_args()
    data = {name: read(args.tables / (name + '.tsv')) for name in
            ('methods', 'claims', 'open_questions', 'relationships', 'lineage_order', 'rejects')}
    seeds = {r['paper_id']: r for r in read(ROOT / 'seed/seed_list.tsv')}
    by_claim = {r['claim_id']: r for r in data['claims']}
    by_method = {r['method_id']: r for r in data['methods']}
    motivations = {}
    for claim in data['claims']:
        if claim['role'] == 'motivation':
            motivations.setdefault((claim['paper_id'], claim['method_id']), []).append(claim)

    def method_motivations(mid):
        row = by_method.get(mid, {})
        return motivations.get((row.get('paper_id'), mid), [])

    notes = {}
    for row in data['methods']:
        mid = row['method_id']
        refs = dict(pair.split('=', 1) for pair in items(row['component_claims']))
        lines = [f'# {row["name"]}', STAMP, '', f'Paper: {row["paper_id"]} — '
                 f'{seeds.get(row["paper_id"], {}).get("title", "NA")}', '', '## Motivating problem']
        lines += [f'- {c["conclusion"]} — {link("claims", c["claim_id"])}; '
                  f'earlier method falling short: {", ".join(link("methods", m) for m in items(c["other_method"])) or "NA"}'
                  for c in method_motivations(mid)] or ['- NA']
        lines += ['', '## Components']
        lines += [f'- {key}: {row[key]} — {claims(refs.get(key, "NA"))}' for key in COMPONENTS]
        lines += ['', '## Assumptions']
        lines += [f'- {link("claims", cid)} — {by_claim.get(cid, {}).get("conclusion", "NA")}'
                  for cid in items(row['assumptions'])] or ['- NA']
        lines += ['', '## Tunable settings', row['tunable_settings'], '', '## Related methods']
        for edge in data['relationships']:
            if mid in (method(edge['from_id']), method(edge['to_id'])):
                other = edge['to_id'] if method(edge['from_id']) == mid else edge['from_id']
                lines.append(f'- {edge["type"]} -> {link("methods", method(other))} '
                             f'({edge["conditions"]}) — supported by {claims(edge["supporting_claims"])} '
                             f'— motivation claims: {claims(edge.get("motivation_claims", "NA"))} '
                             f'[edge {edge["edge_id"]}: {edge["from_id"]} → {edge["to_id"]}]')
        lines += ['', '## Claims by role']
        for role in ('definition', 'assumption', 'guarantee', 'limitation', 'relation', 'setting'):
            lines += [f'### {role}']
            lines += [f'- {link("claims", c["claim_id"])} — {c["conclusion"]}' for c in data['claims']
                      if c['method_id'] == mid and c['role'] == role] or ['- NA']
        notes[f'methods/{mid}.md'] = '\n'.join(lines)
    for row in data['claims']:
        cid = row['claim_id']
        lines = ['---'] + [f'{dict(paper_id="paper", method_id="method").get(key, key)}: {json.dumps(row[key], ensure_ascii=False)}' for key in
                           ('paper_id', 'method_id', 'component', 'role', 'kind', 'tag', 'access')]
        lines += ['---', f'# {cid}', STAMP, '', '## Conclusion', row['conclusion']]
        for title, key in (('Assumptions', 'assumptions'), ('Scope', 'scope'), ('Objects', 'objects')):
            lines += ['', f'## {title}', row[key]]
        lines += ['', '## Span'] + ['> ' + line for line in row['span'].splitlines()]
        lines += ['', f'Equation / theorem: {row["eq_ref"]}', f'Location: {row["location"]}',
                  f'Source file: {row["source_file"]}', '', '## Premises', claims(row['premises']), '', '## Used by']
        lines += [f'- {edge["edge_id"]}: {link("methods", method(edge["from_id"]))} '
                  f'— {edge["type"]} → {link("methods", method(edge["to_id"]))} ({edge["conditions"]})'
                  for edge in data['relationships'] if cid in items(edge['supporting_claims']) + items(edge.get('motivation_claims', 'NA'))] or ['- NA']
        lines += [f'- Premise of {link("claims", c["claim_id"])}' for c in data['claims'] if cid in items(c['premises'])]
        notes['claims/' + cid.replace(':', '_') + '.md'] = '\n'.join(lines)
    sides = ['fsusie', 'prs'] + (['cross'] if any(e['edge_id'].startswith('x:') for e in data['relationships']) else [])
    for side in sides:
        prefix = 'x' if side == 'cross' else side
        edges = [e for e in data['relationships'] if e['edge_id'].startswith(prefix + ':')]
        ordered = sorted((r for r in data['lineage_order'] if r['side'] == side), key=lambda r: float(r['order']))
        lines = [f'# {side} lineage', STAMP, '']
        if not edges or not ordered:
            lines += ['relationships pending', '']
        nodes = sorted({method(e[key]) for e in edges for key in ('from_id', 'to_id')})
        node_ids = {mid: f'n{i}' for i, mid in enumerate(nodes)}
        lines += ['```mermaid', 'graph TD']
        lines += [f'  {node_ids[mid]}["{html.escape(by_method.get(mid, {}).get("name", mid), quote=True)}"]' for mid in nodes]
        lines += [f'  {node_ids[method(e["from_id"])]} -->|{e["type"]}| {node_ids[method(e["to_id"])]}' for e in edges]
        lines += ['```', '', '## Ordered walk']
        for i, r in enumerate(ordered, 1):
            lines.append(f'{i}. {link("methods", r["method_id"])} — {r["note"]}')
            lines += [f'   - Motivating problem: {c["conclusion"]} — {link("claims", c["claim_id"])}'
                      for c in method_motivations(r['method_id'])]
        lines += ['', '## Edges', '| Edge | From | Type | To | Conditions | Supporting claims | Motivation claims | Note |',
                  '| --- | --- | --- | --- | --- | --- | --- | --- |']
        for e in edges:
            cells = [e['edge_id'], link('methods', method(e['from_id'])), e['type'],
                     link('methods', method(e['to_id'])), e['conditions'], claims(e['supporting_claims']), claims(e.get('motivation_claims', 'NA')), e['note']]
            lines.append('| ' + ' | '.join(v.replace('|', '\\|').replace('\n', ' ') for v in cells) + ' |')
        notes[f'lineage/{side}.md'] = '\n'.join(lines)
    index = ['# Open questions', STAMP, '']
    for row in data['open_questions']:
        qid = row['oq_id']
        lines = [f'# {qid}', STAMP, '', row['question'], '', '## Missing premise', row['missing_premise'],
                 '', 'Side: ' + row['side'], '', '## Related claims', claims(row['related_claims']),
                 '', '## Related methods', ', '.join(link('methods', m) for m in items(row['related_methods'])) or 'NA']
        notes['open-questions/' + qid.replace(':', '_') + '.md'] = '\n'.join(lines)
        index.append(f'- {link("open-questions", qid)} — {row["question"]}')
    notes['open-questions/index.md'] = '\n'.join(index)
    notes['README.md'] = '\n'.join(['UNVERIFIED DRAFT MAP', STAMP, '',
        *[f'{name}: {len(data[name])}' for name in data], '', '[[lineage/fsusie]]', '[[lineage/prs]]',
        *(['[[lineage/cross]]'] if 'cross' in sides else []), '', '[[open-questions/index]]'])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'my-notes').mkdir(exist_ok=True)
    for folder in ('methods', 'claims', 'lineage', 'open-questions'):
        (args.out / folder).mkdir(exist_ok=True)
        for old in (args.out / folder).glob('*.md'):
            if old.relative_to(args.out).as_posix() not in notes:
                old.write_text(STAMP + '\n\nRetired generated note: no current table row.\n', encoding='utf-8')
    for path, content in notes.items():
        (args.out / path).write_text(content + '\n', encoding='utf-8')
    if args.html:
        sections = []
        for path, content in notes.items():
            def wikilink(match):
                target, _, label = html.unescape(match[1]).partition('|')
                return '<a href="#' + html.escape(target + '.md', quote=True) + '">' + html.escape(label or target) + '</a>'
            body = re.sub(r'\[\[(.*?)\]\]', wikilink, html.escape(content))
            sections.append(f'<section id="{html.escape(path, quote=True)}"><pre>{body}</pre></section>')
        args.html.write_text('<!doctype html><meta charset="utf-8"><title>UNVERIFIED DRAFT MAP</title>'
                             '<style>body{max-width:1000px;margin:2em auto;font:16px sans-serif}'
                             'pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-bottom:1px solid #ccc}</style>'
                             + '\n'.join(sections), encoding='utf-8')
    print(f'{args.out}: {len(notes)} generated notes; personal notes preserved')


if __name__ == '__main__':
    main()
