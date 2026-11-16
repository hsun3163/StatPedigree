Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — add the motivating problem to every paper that lacks it, and show it in the vault

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only inside it; temp files in ./tmp. No commit. No deletions.
Read `SCHEMA.md` and `briefs/extract_paper.md` (the `motivation` bullet in step 4 is new).

Hao's words: the map "should also include motivational problem".

1. For every folder in `papers/` (except `_worked`) whose `claims.tsv` has no row with role `motivation` for one of its
   method rows: append the motivation rows described in `briefs/extract_paper.md` step 4 to that `claims.tsv`, continuing
   the paper's claim numbering. Existing rows stay byte-identical. Spans are copied from `sources/ID.txt`.
2. `scripts/build_vault.py`: each method note opens with a "Motivating problem" section listing its `motivation` claims
   (conclusion + claim link + the earlier method named as falling short). Each lineage note's "Ordered walk" shows, under
   each method, its motivation conclusion(s) in one line each. `relationships.tsv` now has a column `motivation_claims`
   after `supporting_claims` (may be absent in old sample files: treat as NA); show it in the edge table and on method notes.
3. Run `python scripts/merge_tables.py` and `python scripts/build_vault.py`.

Acceptance: every method row in `tables/methods.tsv` whose paper has full text has at least one kept `motivation` claim;
`python scripts/check_spans.py` shows zero fixable rejects; `vault/methods/fsusie.md` shows the new section.
Final reply: at most 6 lines, beginning `Δ `: papers touched, rows added, rejects. Paste no paper content.
