#!/usr/bin/env python3
"""Check all papers, then rebuild the four merged tables from per-paper TSVs."""
import argparse
from pathlib import Path
from check_spans import ROOT, CLAIMS, METHODS, QUESTIONS, check, items, read, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Project root (also for isolated fixtures)')
    root = parser.parse_args().root
    check(root)
    folders = sorted(p for p in (root / 'papers').iterdir() if p.is_dir() and p.name != '_worked')
    tables = {}
    for name in ('claims', 'methods', 'open_questions', 'rejects'):
        source = 'claims.checked.tsv' if name == 'claims' else name + '.tsv'
        tables[name] = [row for folder in folders for row in read(folder / source)]
    valid = {row['claim_id'] for row in tables['claims']}
    for name, columns in (('methods', ('assumptions', 'component_claims')),
                          ('open_questions', ('related_claims',))):
        for row in tables[name]:
            for column in columns:
                values = []
                for entry in items(row[column]):
                    component, sep, claim = entry.partition('=') if column == 'component_claims' else ('', '', entry)
                    if claim not in valid:
                        print(f'WARNING {name} {row.get("method_id", row.get("oq_id"))} '
                              f'{column}: {claim} absent from merged claims; set to NA')
                        claim = 'NA'
                    values.append(component + sep + claim)
                row[column] = '; '.join(values) or 'NA'
    for name, columns in (('claims', CLAIMS), ('methods', METHODS),
                          ('open_questions', QUESTIONS), ('rejects', CLAIMS + ['reason'])):
        write(root / 'tables' / (name + '.tsv'), columns, tables[name])
        print(f'tables/{name}.tsv rows={len(tables[name])}')


if __name__ == '__main__':
    main()
