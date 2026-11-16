Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — method papers by three authors that belong on the method tree

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `scripts/author_papers.py`, `tables/author_papers.tsv`,
`sources/citations_cache/`, `tmp/authors/`. Leave every other file as it is. No commit. No deletions.

Hao's words: "paul orelliey 的全部要加上，同样susie 方向mathew stephens 的和gao wang 的相关的要加上"
(add all of Paul O'Reilly's; likewise, in the SuSiE direction, add the related work of Matthew Stephens and Gao Wang).
Standing rule: the tree is "purely for theory and method development"; a star is one statistical method (a class), and
software versions, tutorials, applications, data papers and reviews are not stars.

Authors (disambiguate by affiliation and co-authors; these are public researcher names):
- Paul F. O'Reilly (Icahn School of Medicine at Mount Sinai; earlier King's College London): polygenic risk score methods.
- Matthew Stephens (University of Chicago): statistical genetics and empirical Bayes methods.
- Gao Wang (Columbia University; earlier University of Chicago): fine-mapping and multivariate methods.

Use open metadata services only (Europe PMC, OpenAlex, Crossref, arXiv, bioRxiv); generic User-Agent, no personal
details; cache responses; at most 3 requests per second. Include preprints; when a preprint and a journal version are the
same work keep one row (the journal version, with the preprint id noted).

Write `tables/author_papers.tsv`, one row per distinct work found (all of them, no cut-off):
`author  year  title  venue  doi  pmcid  preprint_id  paper_kind  direction  include  why  method_name  proposed_paper_id  already_seed  open_route`
- `author`: which of the three (`; ` separated when shared).
- `paper_kind`: `statistical_method` (proposes or extends a model, prior, estimator, test or fitting algorithm),
  `software_or_version`, `tutorial_or_review`, `application`, `data_resource`, `other`. Read title and abstract.
- `direction`: `prs` (polygenic scores and genetic prediction), `susie` (variable selection, fine-mapping, multiple
  regression, empirical Bayes shrinkage and normal means, matrix factorization priors used by those, multivariate,
  functional or summary-statistic extensions, colocalization built on them), or `other`.
- `include`: for O'Reilly: `yes` for every `statistical_method` paper in any direction, plus software papers that are the
  only description of a method (say so in `why`). For Stephens and Wang: `yes` for `statistical_method` papers with
  direction `susie` or `prs`. Otherwise `no`.
- `why`: at most 20 words. `method_name`: the method's name as the paper gives it, else `NA`.
- `proposed_paper_id`: snake_case method name; for a paper already in `seed/seed_list.tsv` (match by DOI, PMCID or title)
  give that paper_id and set `already_seed` to `yes`.
- `open_route`: `pmc`, `europepmc`, `arxiv`, `biorxiv` or `none_found` for every `include = yes` row; `NA` otherwise.

`scripts/author_papers.py --check` prints counts by author, paper_kind, include and open_route.
Final reply: at most 8 lines, beginning `Δ `: works found per author, include = yes per author, how many of those are already
in the seed list, open routes among the rest, and the method names of the new include = yes rows (names only).
