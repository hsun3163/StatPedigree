#!/usr/bin/env python3
"""Validate the curated one-star-per-method aliases without rewriting project files."""
import argparse
from collections import Counter
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = 'alias_id canonical_id kind reason evidence_claims source'.split()
KINDS = {'implementation', 'version', 'same_method', 'tutorial'}


def read(path, required):
    with path.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not set(required) <= set(fields):
            raise ValueError(f'{path.name}: invalid or missing columns')
        if required == COLUMNS and fields != COLUMNS:
            raise ValueError(f'{path.name}: expected columns {COLUMNS}')
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError(f'{path.name}: malformed TSV row')
        return rows


def validate_rows(rows, known_ids, known_claims):
    """Return all structural and row-contract errors; method IDs need not be unique per paper."""
    errors = []
    aliases = [row['alias_id'] for row in rows]
    alias_set = set(aliases)
    canonicals = {row['canonical_id'] for row in rows}
    for alias, count in Counter(aliases).items():
        if count > 1:
            errors.append(f'duplicate alias: {alias}')
    for node in sorted(alias_set & canonicals):
        errors.append(f'alias is also canonical (chain or cycle): {node}')
    for number, row in enumerate(rows, 2):
        prefix = f'row {number}'
        for column in ('alias_id', 'canonical_id'):
            if row[column] not in known_ids:
                errors.append(f'{prefix}: unknown {column}: {row[column]}')
        if row['alias_id'] == row['canonical_id']:
            errors.append(f'{prefix}: self alias: {row["alias_id"]}')
        if row['kind'] not in KINDS:
            errors.append(f'{prefix}: invalid kind: {row["kind"]}')
        if row['source'] not in {'lead', 'codex'}:
            errors.append(f'{prefix}: invalid source: {row["source"]}')
        if not row['reason'].strip() or len(row['reason'].split()) > 25:
            errors.append(f'{prefix}: reason must contain 1 to 25 words')
        evidence = row['evidence_claims']
        if evidence != 'NA':
            claims = evidence.split('; ')
            if not evidence or any(claim not in known_claims for claim in claims):
                errors.append(f'{prefix}: invalid evidence_claims: {evidence}')
    return errors


def check(root=ROOT):
    root = Path(root)
    rows = read(root / 'tables/node_merge.tsv', COLUMNS)
    known_ids = set()
    for table in ('methods', 'map_layout'):
        known_ids.update(row['method_id'] for row in read(root / f'tables/{table}.tsv', ['method_id']))
    known_claims = {row['claim_id'] for row in read(root / 'tables/claims.tsv', ['claim_id'])}
    errors = validate_rows(rows, known_ids, known_claims)
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    counts = Counter(row['kind'] for row in rows)
    print(f'PASS: {len(rows)} aliases; all IDs exist; no chains, cycles, or alias/canonical overlap')
    print('Kinds: ' + ', '.join(f'{kind}={counts[kind]}' for kind in sorted(KINDS)))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True, help='Validate the curated TSV without writing files')
    parser.add_argument('--root', type=Path, default=ROOT, help='Project root (also for isolated fixtures)')
    args = parser.parse_args()
    try:
        return check(args.root)
    except (OSError, ValueError, csv.Error) as error:
        print(f'ERROR: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
