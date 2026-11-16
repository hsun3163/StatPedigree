Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — papers behind the STATO terms, and a citation lineage from our methods to them

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `scripts/citation_paths.py`, `tables/stato_sources.tsv`,
`tables/citation_nodes.tsv`, `tables/citations.tsv`, `tables/citation_paths.tsv`, `sources/citations_cache/`, `tmp/citations/`.
Other jobs are editing `papers/*`: leave them, and leave every other table and script as it is. No commit. No deletions.

Hao's words: "i think the jumps between stato and our method are too far. I am not sure if the stato term have
publication/citations, but if so, we should be able to see a paper for that stato term, and a citation lineage between the methods."

Inputs (read schemas, not rows, into your reply):
- `tables/stato_terms.tsv`: columns stato_id, label, definition, parents, ancestor_labels, definition_source (as STATO gives it; may hold several sources joined by ` ;; `).
- `tables/map_layout.tsv`: rows with side = `stato` are the STATO terms on the map (method_id is the STATO id lower-cased with `_`).
- `tables/stato_map.tsv`: item_id (a method id), stato_id, match, note. Rows with match `gap` have no term.
- `seed/seed_list.tsv`: our method papers with paper_id, doi, pmcid, preprint_id. `tables/methods.tsv` maps method_id to paper_id.
- `sources/<paper_id>.txt` and raw files beside them: stored full text, including reference lists.

Open metadata services only: Europe PMC REST (search, `/references`, `/citations`), OpenCitations (COCI/index API), Crossref REST,
OpenAlex. Publisher sites are out of scope. Send a generic User-Agent with no name, email or project. Cache every response
under `sources/citations_cache/` and reuse the cache on rerun. Be polite: at most 3 requests per second.

Build one script, `scripts/citation_paths.py` (arguments for tables dir, cache dir, max depth; rerunnable), that writes:

1. `tables/stato_sources.tsv`, one row per source of each STATO term on the map:
   `stato_id  label  source_kind  source_text  node_id  doi  pmid  pmcid  title  first_author  year  resolved_by`
   `source_kind`: `paper`, `book`, `web` (Wikipedia and other pages) or `none`. Resolve `paper` sources to identifiers through
   the services above; record how in `resolved_by`. A source you cannot resolve keeps `NA` identifiers. Add nothing STATO does not name.
2. `tables/citation_nodes.tsv`: every paper that appears in the lineage (our method papers, STATO source papers, and
   intermediate papers): `node_id  kind  title  first_author  year  venue  doi  pmid  pmcid  n_citations`
   `kind`: `method_paper` (node_id = paper_id from the seed list), `stato_source`, `intermediate`. New node ids are
   snake_case `firstauthorYEARword`.
3. `tables/citations.tsv`: every direct citation among the nodes: `citing_id  cited_id  found_in  ref_span`
   `found_in`: the service that reports it, or `stored_text`. `ref_span`: for a citing paper whose text is stored, the
   reference-list entry copied as an exact substring of `sources/<paper_id>.txt` (else `NA`).
   This must include citations between our method papers themselves (the method-to-method citation lineage).
4. `tables/citation_paths.tsv`: for every (method paper, STATO source paper) pair that `stato_map.tsv` links through a term,
   and also for every pair regardless of the map when a path of length 1 exists, the shortest citation path(s), newest paper
   citing older: `method_paper  stato_id  source_node  length  path` with `path` = node ids joined by ` > `.
   Search to depth 3 (method cites A cites B cites source). Meet in the middle: references of the method paper, references of
   those, intersected with the papers that cite the source. Keep at most 2 shortest paths per pair; among ties prefer
   intermediates that are already nodes, then those most cited. Pairs with no path within depth 3 get one row with
   length `NA` and path `NA`.

Acceptance: the four tables exist; every node id used in `citations.tsv` and `citation_paths.tsv` is a row of
`citation_nodes.tsv`; rerunning the script from cache gives byte-identical tables.
Fix and continue on operator failures. If one service is unreachable from this cluster, use the others and say which.
Final reply: at most 8 lines, beginning `Δ `: counts per table, how many STATO terms have a paper source, how many
pairs got a path at each length, services used, anything unreachable. Paste no paper content.
