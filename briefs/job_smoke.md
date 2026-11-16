Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree step 2 — smoke test: scripts + two papers through the whole chain

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only inside it; temp files in ./tmp. No commit. No deletions.
Read `SCHEMA.md`, `README.md`, `briefs/extract_paper.md`, `papers/_worked/worked_claims.tsv`.

Hao's words: "Keep the project small: one thin script per step, written the way a person would by hand, and a README from
which I can rerun everything without you or this chat. No framework, no orchestration layer." "The tables stay the source of
truth; never hand-edit the vault." "my-notes/: left empty for me. Regeneration must never touch it."

## A. Three scripts (Python standard library only, each under about 200 lines)
1. `scripts/check_spans.py PAPER_ID [PAPER_ID ...]` (no argument: every folder in `papers/` except `_worked`).
   For each row of `papers/ID/claims.tsv`: collapse whitespace runs to one space in the span and in the source file
   (`sources/ID.txt` for `source_file=main`, `sources/ID.supp.txt` for `supp`) and require the span to be a substring.
   Reject: span absent or empty; `tag` outside {author-stated, agent-inferred}; agent-inferred with `premises` NA; a premise
   ID that is missing from the kept rows of any paper's claims or is itself rejected (iterate until stable); `access`
   outside {full_text, supplement, abstract_only}. Rejected rows go to `papers/ID/rejects.tsv` (same columns + `reason`);
   kept rows go to `papers/ID/claims.checked.tsv`. `claims.tsv` stays as written. Print `ID kept=N rejected=M`.
2. `scripts/merge_tables.py`: runs the check for all papers, then writes `tables/claims.tsv` (concatenated
   `claims.checked.tsv`), `tables/methods.tsv`, `tables/open_questions.tsv`, `tables/rejects.tsv` from the per-paper files.
   It leaves `tables/relationships.tsv` and `tables/lineage_order.tsv` alone: the lead writes those by hand. In
   `methods.tsv` and `open_questions.tsv` it blanks out (to NA, with a printed warning) claim IDs that are absent from the
   merged claims. Prints row counts.
3. `scripts/build_vault.py`: reads only `tables/*.tsv` and `seed/seed_list.tsv`, writes `vault/`:
   - `vault/README.md`: first line "UNVERIFIED DRAFT MAP", counts, links to the two lineage notes.
   - `vault/methods/<method_id>.md`: name, paper, components (each with its claim link), assumptions (claim links with the
     one-line conclusion), tunable settings, a "Related methods" list built from `relationships.tsv` in both directions as
     `type -> [[other]] (conditions) — supported by [[claim]], ...`, and a list of all claims for the method grouped by role.
   - `vault/claims/<claim_id with ":" replaced by "_">.md`: front matter (paper, method, component, role, kind, tag,
     access), conclusion, assumptions, scope, objects, the span as a blockquote, eq_ref, location, source file, premises as
     links, and "Used by" edges.
   - `vault/lineage/<side>.md` for side in fsusie, prs (and `cross.md` for edge IDs starting `x:` when present): a
     ```mermaid``` `graph TD` with one node per method in that side's edges and one labelled arrow per edge (label = type),
     then "Ordered walk" from `tables/lineage_order.tsv` (columns `side  order  method_id  note`) as a numbered list of
     method links with the note, then an edge table with conditions and supporting claim links. When `relationships.tsv`
     or `lineage_order.tsv` is absent or has no rows for the side, the note says "relationships pending". Edge endpoints
     may be `method_id.component`; the node is the method. An endpoint with no method row still gets a node.
   - `vault/open-questions/<oq_id with ":" replaced by "_">.md` and `vault/open-questions/index.md`.
   - `vault/my-notes/`: created when absent, otherwise left exactly as found. Regeneration rewrites only methods/, claims/,
     lineage/, open-questions/ and README.md (stale generated notes inside those four folders are overwritten or removed).
   - Obsidian wikilinks `[[claims/fsusie_c01|fsusie:c01]]`; every generated note carries the line "Unverified draft map —
     generated from tables/, do not edit".
   - Optional flag `--html vault.html`: one self-contained HTML page of the same content. Implement only if it costs
     under 60 lines; otherwise leave the flag out.

## B. Run the chain for two papers
Follow `briefs/extract_paper.md` for PAPER_ID = `fsusie` and for PAPER_ID = `bridgeprs` (sources are already stored, both
with supplements). Then run `scripts/merge_tables.py` and `scripts/build_vault.py`.
To exercise the lineage note, write a two-row sample `tmp/sample_tables/relationships.tsv` and check the generator against
it through a `--tables DIR --out DIR` option; leave `tables/relationships.tsv` unwritten.

## C. README
Extend `README.md`: sections 2 (extract one paper: points at `briefs/extract_paper.md`), 3 (check spans), 4 (merge),
5 (build vault), each with the exact command. Add at the top: "UNVERIFIED DRAFT MAP".

## Acceptance check (run before reporting)
- `python scripts/check_spans.py fsusie bridgeprs` ends with zero fixable rejects, and both papers keep at least 15
  claims; a deliberately broken copy of one row in `tmp/` is rejected by the script.
- `tables/claims.tsv`, `tables/methods.tsv`, `tables/open_questions.tsv`, `tables/rejects.tsv` exist with headers.
- `vault/methods/fsusie.md`, `vault/methods/bridgeprs.md`, `vault/claims/fsusie_c01.md`, `vault/claims/bridgeprs_c01.md`
  exist; each claim note shows span and tag; a file placed in `vault/my-notes/` survives a rebuild.

Fix and continue on operator failures. Stop only when a source file mismatches its paper.

## Report
`reports/smoke_report.md`, at most 25 lines: counts per paper, script line counts, what broke and how it was fixed
(exact error text), whether `--html` was implemented. Paste no paper content.
Final reply: at most 8 lines, beginning `Δ `, with `~/sunh14_project/stattree/...` paths.
