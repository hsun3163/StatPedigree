# Link roles: is the earlier method a component the later method builds upon? (step used by job_refresh.md)

Hao's words: "the current graph have links that are connected too randomly, the connection should be more selective, with
only the former method is a component that the later method build upon, otherwise it is pointless".

Write `tables/link_roles.tsv` and `scripts/link_roles.py` (`--check`). One row per candidate link sentence. Candidates, with
their `link_id`:
- every row of `tables/context_links.tsv` whose relation is a SCHEMA edge type or `contains_special_case` and whose
  `citing_method_id` is not `NA` (link_id = `context_id`; the sentence is in `tables/citation_contexts.tsv`);
- every row of `tables/edge_links.tsv` with verdict `stated` or `stated_other_type` (link_id = `edge_id`; the passage is `link_span`);
- every row of `tables/parents.tsv` (link_id = `par:<N>` with N the zero-based row index in file order; the passage is the
  span of the first `supporting_claims` id found in `tables/claims.tsv`).

Columns: `link_id  later_method  earlier_method  component_role  builds_on  role_statement`
- `component_role`: what the earlier method (or generic tool) IS inside the later method, as the passage states it:
  `model` (the later method's model is the earlier model, or the earlier model with a stated change),
  `prior` (the earlier method supplies the prior or penalty),
  `likelihood` (supplies the likelihood or the summary-data form),
  `fitting_algorithm` (the later method is fitted by the earlier algorithm, or by a stated modification of it),
  `building_block` (the later method is assembled from repeated copies or a sum of the earlier one, e.g. a single-effect regression),
  `generalizes` (the later method contains the earlier one as a stated special or limiting case, or extends it),
  `output` (the later method's reported quantity is defined by the earlier work, e.g. credible sets, Bayes factors),
  `theory` (a result of the earlier work is what a stated guarantee of the later method rests on);
  or a non-component role: `similar` (shares structure, analogous, related), `inspired` (motivated by, in the spirit of),
  `compared` (contrasted or benchmarked), `tool_step` (used in a data-analysis or preprocessing step, software, data,
  hyperparameter default), `alternative` (could be used instead), `mention`.
- `builds_on`: `yes` only for the eight component roles AND when the passage says so about the later method itself
  (not about an analysis the authors ran with it). Otherwise `no`. When in doubt, `no`.
- `later_method` / `earlier_method`: method or node ids as in the source row; the later method is the one that builds.
  For a special-case sentence, the general method is `later_method` only if it was published later or in the same paper;
  if the special case is the newer method (it restricts an older general method), role is `similar`, builds_on `no`.
- `role_statement`: at most 20 words, e.g. "SuSiE is a sum of L single-effect regressions". No more than the passage says.

`--check`: every link_id exists in its source table; builds_on obeys the rule; prints counts by component_role and builds_on.
