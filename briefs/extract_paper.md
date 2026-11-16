# Brief: one paper -> per-paper claim files (reusable; PAPER_ID is given in the job prompt)

Project root: /sc/arion/projects/load/users/sunh14/stattree. Read `SCHEMA.md` and `papers/_worked/worked_claims.tsv` first:
the three worked records are the template for depth, wording and span choice.

Purpose: a knowledge map of statistical theory. The unit is a conditional theoretical claim, not a method name.
Hao's words: "Content is methods and theory only: no software, APIs, or usage instructions." "Keep assumptions separate from
tunable settings: a parameter the user can set is a degree of freedom, not an assumption." "Never settle a theoretical
question by your own reasoning: record it as an open question with the missing premise."

## Steps for PAPER_ID
1. Source text: if `sources/PAPER_ID.txt` is absent, fetch it with `scripts/fetch_paper.py` using the row for PAPER_ID in
   `seed/seed_list.tsv` (README section 1 has the environment). Papers missing from the seed list: append one row in the same format.
2. Read the methods/theory parts of `sources/PAPER_ID.txt` (and `sources/PAPER_ID.supp.txt` when present): model, prior,
   inference, estimand, data input, stated assumptions, stated guarantees, stated limitations, and every statement relating
   the method to another method (reduces to, generalizes, differs from, borrows). Skip data applications, software, and
   benchmark numbers, except one or two rows of kind `empirical_observation` when the authors use a simulation result to
   state where the method works or fails.
3. Write `papers/PAPER_ID/methods.tsv` (schema `methods.tsv`): one row for the paper's main method, plus one row for each
   building-block model the paper itself defines and names (for example a single-effect model inside a sum-of-effects model,
   or stage 1 and stage 2 of a two-stage method). Every component cell is backed by a claim ID in `component_claims`.
   `tunable_settings` lists what the user sets or what is tuned by validation (number of effects, grids, thresholds);
   `assumptions` lists claim IDs with role `assumption`.
4. Write `papers/PAPER_ID/claims.tsv` (schema `claims.tsv`, same column order as the worked file). Target 15 to 30 rows:
   - every component of every method row has a `definition` claim;
   - every assumption the authors state (independence, Gaussianity, LD reference matches the GWAS population, at most one
     causal variant per effect, sample overlap, ...) is its own row with role `assumption`;
   - every proposition, theorem, corollary, convergence or calibration statement is a row with role `guarantee` and its
     number in `eq_ref`; state its conditions in `assumptions`;
   - approximations the authors make (variational, mean-field, summary-statistic sufficiency, LD from a reference panel) are
     rows of kind `approximation`;
   - the motivating problem: 1 to 3 rows with role `motivation`, component `whole_method`, kind `author_interpretation`,
     for each method row. What problem the authors say the method was built to solve, and what they say earlier methods
     could not do (fill `other_method` when a specific earlier method is named as falling short). `conclusion` states the
     problem; `assumptions` states the setting in which it arises. Spans usually come from the Introduction or the
     opening of the Methods.
   - every limitation the authors state is a row with role `limitation`;
   - every explicit statement about another method is a row with role `relation` and `other_method` filled. Use these
     method IDs when they apply: fsusie, sfr, susie, ser, susierss, ash, wavelet_ss, smash, mvsusie, sushie, mash, wfmm,
     bridgeprs, prscs, prscsx, ldpred, ldpred2, prsice2, bvsr, ridge, lasso; otherwise a short free name.
   - `span`: copy an exact contiguous substring from the source file, one to three sentences, containing the statement
     itself (for math: the sentence that states or introduces it, with the equation or theorem number in `eq_ref`).
     Copy, never retype: spans are string-matched after whitespace collapsing only.
   - `conclusion`, `assumptions`, `scope`, `objects` are your paraphrase of what the span and its immediate context say.
   - `tag`: `author-stated` when the conclusion is what the span says. `agent-inferred` when you combine author statements
     into something the authors do not say outright; then `premises` lists the author-stated claim IDs it rests on, and the
     span is the closest supporting sentence. Keep inferred rows few (at most 4).
   - claim IDs: `PAPER_ID:c01`, `PAPER_ID:c02`, ... For the papers fsusie, susie, bridgeprs, start from the worked record
     (keep its ID and content as c01).
5. Write `papers/PAPER_ID/open_questions.tsv` (schema `open_questions.tsv`, IDs `PAPER_ID:q01`...): theoretical questions the
   paper raises or leaves unsettled (e.g. a guarantee stated for the exact model but used with an approximation), each with
   the missing premise. 0 to 6 rows. Header-only file when there are none.
6. Run `python scripts/check_spans.py PAPER_ID`. It writes `papers/PAPER_ID/rejects.tsv` and prints kept/rejected counts.
   For each rejected row, re-copy the span from the source and rerun; a row whose statement is absent from the source
   stays rejected. Finish with zero fixable rejects.

## Rules
- Write only `papers/PAPER_ID/*`, `sources/PAPER_ID.*`, and (for an unseeded paper) one appended seed row. The shared
  tables in `tables/` are built by a separate merge step.
- TSV: tab-separated, one header line, no tabs or newlines inside cells, `NA` for empty, `; ` between list items.

## Report
Final reply only (at most 6 lines, beginning `Δ `): claim count, rejected count, method rows, open-question count, access
level used, and any failure with its exact error text. Paste no paper content.
