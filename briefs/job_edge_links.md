Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — every link on the map must be one quoted sentence from a paper

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `scripts/edge_links.py`, `tables/edge_links.tsv`,
`tmp/edge_links/`. Other jobs are editing `papers/*`: leave `papers/`, `sources/`, every other table and script as they are.
No commit. No deletions.

Hao's words: "for the detached node, how is that connect to the main tree, this should be based on paper, not you drawing it"
and "i dont understand how is ash connected to fsusie, the links should be a claim".

Inputs: `SCHEMA.md`; `tables/relationships.tsv` (edge_id, from_id, to_id, type, conditions, supporting_claims,
motivation_claims, note; ids may carry a `.component` suffix); `tables/claims.tsv` (claim_id, paper_id, method_id, role,
other_method, conclusion, span, location, source_file, ...); `tables/methods.tsv` (method_id, paper_id, name, ...);
`sources/<paper_id>.txt` and `sources/<paper_id>.supp.txt` (stored text; the only admissible evidence).

Definition. A link is *stated* when one passage of at most two consecutive sentences in a stored paper names or
unambiguously refers to both endpoint methods and says how they relate (built from, extends, reduces to, special case,
uses as a component, equivalent under a condition, differs from in a named way, inspired by). A sentence that only
defines one endpoint, or a bare citation, does not state a link. Do not infer a link from two separate definitions.

Write `tables/edge_links.tsv` (tab-separated, header):
`edge_id  from_id  to_id  type  verdict  stated_type  conditions  paper_id  location  link_span  statement  existing_claim`

1. Audit: one row for every edge in `relationships.tsv`. Read the supporting claims' spans, then search the stored texts of
   both endpoints' papers for the best stating passage.
   - `verdict`: `stated` (the passage supports the edge's type), `stated_other_type` (the passage links the two but supports
     a different SCHEMA type: put it in `stated_type`), or `not_stated` (no such passage in the stored texts).
   - `link_span`: the passage copied as an exact substring of the stored text after collapsing whitespace runs (`NA` when not_stated).
   - `statement`: one plain sentence, at most 30 words, saying what the passage states about the two methods. No more than the passage says.
   - `conditions`: the condition the passage states for the relation, or `NA`.
   - `existing_claim`: the claim_id whose span contains or equals `link_span`, else `NA`.
2. Discovery: for every method_id in `methods.tsv` (all papers now in `tables/`), look in its own paper for passages that
   state how it connects to any other method_id in `methods.tsv` or to a method named in `relationships.tsv`. For each stated
   link that is not already an audited edge between the same two ids, add a row with edge_id `new:NN`, your proposed
   `type`, verdict `stated`. Priority: methods that have no `stated` row after step 1 (the detached building blocks:
   bpred, simple_bfr, wavelet_ss_wc, poisson_multiscale, rss_z, mv_simple, mv_simple_normal, mv_simple_intercept,
   mv_simple_mixture, mser, sfr, ldpred2_inf, ldpred2_sparse, ldpred2_auto, prscs_auto, mvsusie_rss).
   A method for which the paper has no stating passage gets one row: edge_id `none:<method_id>`, verdict `not_stated`.
3. `scripts/edge_links.py --check` verifies every `link_span` is an exact substring (whitespace-collapsed) of
   `sources/<paper_id>.txt` or `.supp.txt` and prints counts per verdict; rows that fail are fixed or set to not_stated.

Acceptance: `python scripts/edge_links.py --check` passes with zero failing spans; every edge_id of `relationships.tsv` has a row.
Final reply: at most 8 lines, beginning `Δ `: counts per verdict for audited edges, number of new stated links, methods
with no stating passage (ids only). Paste no paper content.
