Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — links from the sentences where each citation occurs

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `scripts/citation_contexts.py`,
`tables/citation_contexts.tsv`, `tables/context_links.tsv`, `tables/frontier.tsv`, `tmp/contexts/`.
Other jobs are editing `papers/*`: leave `papers/`, `sources/` and every other table and script as they are. No commit. No deletions.

Hao's words: "you don't actually need to do the scanning and comparison, you can just looks for the sentences that the
citation occurs and start from there".

Idea: a paper's own in-text citation sentences are the evidence for how its method relates to earlier work. Take every
sentence in which a stored paper cites another work, and build the links from those sentences.

Inputs: `sources/<paper_id>.txt`, `.supp.txt` and the raw files beside them (PMC XML/HTML or arXiv source where stored; use the
raw file's citation markup such as `xref ref-type="bibr"` when present, else numbered or author-year markers in the text);
`seed/seed_list.tsv`; `tables/methods.tsv` (method_id, paper_id, name); `tables/citation_nodes.tsv` (node_id, title,
first_author, year, doi: the papers already on the map); `tables/map_layout.tsv` (method_id = every node id on the map,
`short` = its display name); `SCHEMA.md` (edge types).

1. `scripts/citation_contexts.py` (rerunnable, arguments for paper ids and output dir) writes `tables/citation_contexts.tsv`,
   one row per (citing paper, in-text citation sentence, cited reference), for every paper with stored text:
   `context_id  citing_paper  ref_key  cited_node_id  cited_first_author  cited_year  cited_title  cited_doi  section  sentence`
   - `sentence`: the sentence containing the citation marker, an exact substring of `sources/<citing_paper>.txt` (or
     `.supp.txt`) after collapsing whitespace runs; the script verifies this and drops rows that fail, reporting the count.
   - `cited_node_id`: the map node id when the cited work is a paper already on the map (match by DOI, else by normalized
     title, else first author + year + title words), otherwise `NA`. `ref_key`: the reference's number or label in that paper.
   - `context_id`: `<citing_paper>:x<NNN>`.
2. `tables/context_links.tsv`, your reading of the sentences (tag every row `agent-read`; say only what the sentence says):
   `context_id  citing_paper  citing_method_id  cited_node_id  cited_label  relation  conditions  statement`
   Rows: every context whose cited work is on the map, plus every context (cited work on or off the map) whose sentence
   says the citing paper's method is built from, extends, generalizes, reduces to, contains as a special case, uses as a
   component, follows, adapts, is equivalent to under a condition, or is inspired by the cited work.
   - `relation`: a SCHEMA edge type read as "citing method RELATION cited work" (`contains_special_case` when the cited
     work is the special case), or `benchmark` (compared in experiments only), `data_or_tool`, `background` (general mention).
   - `citing_method_id`: the method_id of the citing paper that the sentence is about (with a `.component` suffix when the
     sentence concerns the prior, likelihood, fitting algorithm or data input), `NA` when the sentence is not about a method of the paper.
   - `cited_label`: for off-map works, a short method name as the sentence gives it, else first author + year.
   - `statement`: one plain sentence, at most 30 words.
3. `tables/frontier.tsv`: cited works that are not on the map and have at least one `context_links` row with a SCHEMA
   relation: `cited_first_author  cited_year  cited_title  cited_doi  cited_label  n_relation_sentences  citing_papers  relations`
   sorted by `n_relation_sentences` descending. These are the next papers to pull in.

Acceptance: the script reruns to byte-identical `citation_contexts.tsv`; every `context_id` in `context_links.tsv` exists in
`citation_contexts.tsv`; every sentence passes the exact-substring check.
Fix and continue on operator failures. A paper whose citation markers cannot be resolved to references is listed in your reply.
Final reply: at most 8 lines, beginning `Δ `: papers processed, contexts, contexts per paper range, link rows by relation,
frontier size, papers with unresolved markers. Paste no paper content.
