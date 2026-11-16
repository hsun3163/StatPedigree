#!/usr/bin/env python3
"""Check exact source spans and premise closure; retain the submitted claims."""
import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ('claim_id paper_id method_id component role kind objects assumptions conclusion '
          'scope other_method span eq_ref location source_file tag premises access').split()
METHODS = ('method_id paper_id side name model_likelihood prior inference_algorithm estimand '
           'data_input assumptions tunable_settings component_claims').split()
QUESTIONS = 'oq_id side question missing_premise related_claims related_methods'.split()


def read(path):
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, columns, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def items(value):
    return [part.strip() for part in value.split(';') if part.strip() not in ('', 'NA')]


def normalized(value):
    return re.sub(r'\s+', ' ', value).strip()


def check(root=ROOT, selected=None):
    folders = sorted(p for p in (root / 'papers').iterdir() if p.is_dir() and p.name != '_worked')
    papers = {folder.name: read(folder / 'claims.tsv') for folder in folders}
    selected = list(papers) if not selected else selected
    for paper in selected:
        if paper not in papers:
            raise ValueError(f'Unknown paper folder: {paper}')
    records, sources = [], {}
    for paper, rows in papers.items():
        for row in rows:
            reasons = []
            source = row['source_file']
            span = normalized(row['span'])
            if not span or span == 'NA':
                reasons.append('span empty')
            elif source not in ('main', 'supp'):
                reasons.append('source_file outside {main, supp}')
            else:
                key = (paper, source)
                if key not in sources:
                    suffix = '.supp.txt' if source == 'supp' else '.txt'
                    sources[key] = normalized((root / 'sources' / (paper + suffix)).read_text(encoding='utf-8'))
                if span not in sources[key]:
                    reasons.append('span absent from source')
            if row['tag'] not in ('author-stated', 'agent-inferred'):
                reasons.append('tag outside {author-stated, agent-inferred}')
            if row['tag'] == 'agent-inferred' and not items(row['premises']):
                reasons.append('agent-inferred without premises')
            if row['access'] not in ('full_text', 'supplement', 'abstract_only'):
                reasons.append('access outside {full_text, supplement, abstract_only}')
            records.append((paper, row, reasons))
    while True:
        kept_ids = {row['claim_id'] for _, row, reasons in records if not reasons}
        changed = False
        for _, row, reasons in records:
            if not reasons:
                missing = [claim for claim in items(row['premises']) if claim not in kept_ids]
                if missing:
                    reasons.append('premise missing or rejected: ' + '; '.join(missing))
                    changed = True
        if not changed:
            break
    counts = {}
    for paper in selected:
        kept = [row for pid, row, reasons in records if pid == paper and not reasons]
        rejected = [dict(row, reason='; '.join(reasons)) for pid, row, reasons in records
                    if pid == paper and reasons]
        write(root / 'papers' / paper / 'claims.checked.tsv', CLAIMS, kept)
        write(root / 'papers' / paper / 'rejects.tsv', CLAIMS + ['reason'], rejected)
        counts[paper] = (len(kept), len(rejected))
        print(f'{paper} kept={len(kept)} rejected={len(rejected)}')
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paper_ids', nargs='*')
    parser.add_argument('--root', type=Path, default=ROOT, help='Project root (also for isolated fixtures)')
    args = parser.parse_args()
    check(args.root, args.paper_ids)


if __name__ == '__main__':
    main()
