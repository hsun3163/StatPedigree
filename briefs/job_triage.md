Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — decide which cited works to pull in, from what the citing sentences say

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `scripts/frontier_triage.py`, `tables/frontier_triage.tsv`,
`sources/citations_cache/`, `tmp/triage/`. Leave every other file as it is. No commit. No deletions.

Hao's words: "i think the point is, we should limit the paper by context and paper, but not number of paper scan".

Meaning: a cited work joins the map because of what the citing sentence says and what kind of paper it is, never because
of a count, a rank or a distance from the starting papers.

Inputs: `tables/frontier.tsv` (cited works not yet on the map: cited_first_author, cited_year, cited_title, cited_doi,
cited_label, n_relation_sentences, citing_papers, relations, kind, open_route); `tables/context_links.tsv` (context_id,
citing_paper, citing_method_id, cited_node_id, cited_label, relation, conditions, statement) and
`tables/citation_contexts.tsv` (context_id, ..., cited_first_author, cited_year, cited_title, cited_doi, section, sentence):
join them to read every sentence that cites each frontier work; `seed/seed_list.tsv` (papers already read).

Write `tables/frontier_triage.tsv`, one row per frontier work (all of them, no cut-off):
`cited_first_author  cited_year  cited_title  cited_doi  cited_label  citing_papers  lineage_role  paper_kind  follow  why  context_ids  open_route  proposed_paper_id`
- `lineage_role`: what the citing sentences say the cited work contributes to the citing paper's METHOD:
  `model`, `prior`, `likelihood`, `fitting_algorithm`, `theory` (a result the method's guarantees rest on), `estimand`
  (what is reported, such as credible sets or Bayes factors), `predecessor` (the method it extends, generalizes or
  replaces), or one of the non-lineage roles `evaluation` (benchmark or metric), `data_processing` (phasing, imputation,
  QC, normalization, LD blocks), `data`, `software`, `application`, `background`.
- `paper_kind`: `statistical_method`, `algorithm`, `theory`, `review_or_textbook`, `data_resource`, `software`,
  `applied_study` (your reading of title plus sentences).
- `follow`: `yes` when the role is one of the seven lineage roles AND the paper_kind is statistical_method, algorithm,
  theory or review_or_textbook; otherwise `no`. A work with sentences in both groups follows its lineage sentences.
- `why`: at most 20 words, saying what the sentences state; no more than they say.
- `context_ids`: the sentences you relied on, `; ` separated.
- `open_route`: for every `follow = yes` row (no top-N limit), one metadata lookup through Europe PMC, arXiv or bioRxiv:
  `pmc`, `europepmc`, `arxiv`, `biorxiv` or `none_found`. Cache responses. `NA` for `follow = no`.
- `proposed_paper_id`: snake_case, a known method name when the sentences give one (for example `caviar`), else
  first author + year; must differ from every paper_id in the seed list.

`scripts/frontier_triage.py --check` verifies that every context id exists, every follow value obeys the rule above, and
prints counts by lineage_role, paper_kind, follow and open_route.

Acceptance: the check passes; every row of `tables/frontier.tsv` has a triage row.
Final reply: at most 6 lines, beginning `Δ `: counts by follow, by lineage_role among follow = yes, by open_route among follow = yes. Paste no paper content.
