Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — refresh the citation lineage and the citation-sentence links after new papers were added

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `scripts/citation_paths.py`, `scripts/citation_contexts.py`,
`tables/stato_sources.tsv`, `tables/citation_nodes.tsv`, `tables/citations.tsv`, `tables/citation_paths.tsv`,
`tables/citation_contexts.tsv`, `tables/context_links.tsv`, `tables/frontier.tsv`, `tables/frontier_triage.tsv`, `scripts/frontier_triage.py`, `tables/link_roles.tsv`, `scripts/link_roles.py`, `sources/citations_cache/`, `tmp/refresh/`.
Leave `papers/`, stored texts and every other table and script as they are. No commit. No deletions.

Context: `briefs/job_citations.md` and `briefs/job_contexts.md` define the seven tables and both scripts; read them and follow
their definitions and Hao's words quoted there. Since those jobs ran, more papers were read in: `seed/seed_list.tsv` and
`tables/methods.tsv` now hold them, with stored text in `sources/`.

Changes for this run:
1. "On the map" now means: every paper_id in `seed/seed_list.tsv`, every method_id in `tables/methods.tsv`, every
   method_id in `tables/map_layout.tsv`, and every node of `tables/citation_nodes.tsv`. A cited work that matches a seed
   paper gets that paper_id as `cited_node_id`.
2. Rerun `scripts/citation_paths.py` so the new papers become `method_paper` nodes with their direct citations (to each
   other, to the older nodes, and from the older nodes). Keep the existing node ids stable. Paths to STATO source papers
   are needed only for pairs that `tables/stato_map.tsv` links, plus any length-1 path.
3. Rerun `scripts/citation_contexts.py` for all papers with stored text (abstract-only texts have few or no citations:
   that is expected). Keep existing `context_id` values stable for sentences that are unchanged, so earlier rows of
   `context_links.tsv` stay valid; add `agent-read` rows for the new papers' sentences and for old sentences whose cited
   work is now on the map.
4. Three papers had unresolved citation markers last time (bridgeprs, mvsusie, susierss). Try once more to resolve them
   from the raw files beside `sources/<paper_id>.txt` (reference list numbering, superscripts, bracketed numbers); report
   which now resolve.
5. Rebuild `tables/frontier.tsv` with works that are still off the map. Add two columns: `kind` (`method` when the
   sentences treat the cited work as a statistical method or algorithm; `data`, `software` or `review` otherwise; your
   reading) and `open_route` (`pmc`, `arxiv`, `biorxiv`, `europepmc`, `none_found`, from one metadata lookup per work
   for the 60 top-ranked `method` rows; `NA` below that).

6. Then redo the triage in `briefs/job_triage.md` on the rebuilt frontier (`tables/frontier_triage.tsv`,
   `scripts/frontier_triage.py`); keep earlier decisions for works whose sentences are unchanged.

7. Last, do the link-role reading in `briefs/job_roles.md` for all candidate links (`tables/link_roles.tsv`,
   `scripts/link_roles.py`).

Acceptance: as in the two earlier briefs (exact-substring sentences, valid ids, byte-identical rerun from cache).
Final reply: at most 10 lines (add link_roles counts by builds_on and component_role, and triage counts by follow and open_route), beginning `Δ `: nodes, citations, contexts, link rows by relation, the three papers' marker
status, frontier size by kind, how many top-60 methods have an open route. Paste no paper content.
