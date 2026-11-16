Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — one star per statistical method: merge implementations, keep statistical variants apart

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `tables/node_merge.tsv`, `scripts/node_merge.py`,
`tmp/merge/`. Leave every other file as it is. No commit. No deletions.

Hao's words: "For example, same implementation for the same method, fastqtl and tensorQTL should be one stat. While the rss
branch of Susie should still be independent".

Meaning: a star on the map is one statistical method (one model + prior + estimand + fitting principle). Two entries that
are the same statistical method in different software, different software versions, a faster reimplementation, a tutorial
or a generic name for it are ONE star. Two entries that differ statistically stay separate: a different likelihood or
data form (summary statistics instead of individual-level data, as SuSiE-RSS vs SuSiE), a different prior, a different
estimand, an added model component, or a different inference principle (MCMC vs variational counts as different).

Inputs: `tables/methods.tsv` (method_id, paper_id, side, name, model_likelihood, prior, inference_algorithm, estimand,
data_input, ...); `tables/claims.tsv` (claim_id, method_id, role, other_method, conclusion, span); `tables/map_layout.tsv`
(method_id = every node id now on the map, including generic tools with side `gen`); `tables/context_links.tsv`
(statements about how papers describe each other). Existing rows in `tables/node_merge.tsv` with source `lead` stay.

Append rows to `tables/node_merge.tsv`: `alias_id  canonical_id  kind  reason  evidence_claims  source`
- One row per entry that should fold into another star. `canonical_id` is the entry that best carries the statistical
  definition (prefer the original method paper; never a chain: canonical ids are not aliases themselves).
- `kind`: `implementation` (software or reimplementation of the same method), `version` (software release with no
  statistical change), `same_method` (same method under another id or generic name, or described again in another paper),
  `tutorial`.
- `reason`: at most 25 words, stating what is the same. `evidence_claims`: claim ids (`; ` separated) whose text shows it,
  `NA` if only the methods table shows it. `source`: `codex`.
- Merge only when the stored text or the methods table shows the statistics are the same. When a newer entry changes
  anything statistical, do not merge; list it instead in your reply as kept separate (ids only).
`scripts/node_merge.py --check`: no chains, no alias that is also canonical, every id exists in methods.tsv or map_layout.tsv.

Final reply: at most 8 lines, beginning `Δ `: rows added by kind, the pairs merged (ids only), close calls kept separate (ids only). Paste no paper content.
