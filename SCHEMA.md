# stattree schema (UNVERIFIED DRAFT MAP)

Three flat TSV tables in `tables/`, built by one merge step from per-paper files in `papers/<paper_id>/`.
The tables are the source of truth; the vault in `vault/` is generated from them.

Multi-valued cells use `; ` as separator. Empty is `NA`. IDs are stable and prefixed with the paper ID.

## Source text
`sources/<paper_id>.txt` (main) and `sources/<paper_id>.supp.txt` (supplement): UTF-8, NFC, one paragraph per line,
headings as `## ` lines. A span matches when it is an exact substring of the source file after collapsing every run of
whitespace to one space in both strings. Nothing else is normalised.

## methods.tsv — one row per method
| column | meaning |
|---|---|
| method_id | short slug, e.g. `susie`, `bridgeprs` |
| paper_id | paper that defines it (seed/seed_list.tsv) |
| side | `fsusie` or `prs` |
| name | display name |
| model_likelihood | sampling model for the data given the parameters |
| prior | prior on the effects and its hyperparameter structure |
| inference_algorithm | how the posterior or estimate is computed |
| estimand | what the method reports (PIPs, credible sets, posterior mean weights, ...) |
| data_input | individual-level, summary statistics + LD reference, ... |
| assumptions | claim IDs of kind-independent rows whose `role` is `assumption` |
| tunable_settings | degrees of freedom the user sets (L, grid of phi, purity threshold, ...); not assumptions |
| component_claims | claim IDs that source each component cell, as `component=claim_id` pairs |

## claims.tsv — one row per conditional claim
| column | meaning |
|---|---|
| claim_id | `<paper_id>:c<NN>` |
| paper_id | source paper |
| method_id | method the claim is about |
| component | `model_likelihood`, `prior`, `inference_algorithm`, `estimand`, `data_input`, or `whole_method` |
| role | `motivation` (the problem the method was built to solve and what earlier methods could not do, as the authors state it), `definition`, `assumption`, `guarantee`, `limitation`, `relation` (says something about another method), `setting` (a tunable) |
| kind | `theorem`, `approximation`, `empirical_observation`, `author_interpretation` (definitions of a model are recorded as `author_interpretation` with role `definition`) |
| objects | the mathematical objects involved, in plain notation |
| assumptions | the conditions under which the conclusion is stated to hold; `none stated` when the source gives none |
| conclusion | the claim itself, in one sentence, paraphrased |
| scope | where it applies and where the source says it stops |
| other_method | for role `relation`: the method_id (or free name) of the other method |
| span | exact substring of the source text |
| eq_ref | equation / theorem / proposition number when the claim is mathematical, else `NA` |
| location | `<paper_id> | <version_used> | <section heading>` |
| source_file | `main` or `supp` |
| tag | `author-stated` or `agent-inferred` |
| premises | for `agent-inferred`: claim IDs of the author-stated rows it rests on; else `NA` |
| access | `full_text`, `supplement`, `abstract_only` |

Removal rules (script `scripts/check_spans.py`): a row whose span is absent from its source file, or an
`agent-inferred` row with no premises (or premises that are missing or themselves removed), goes to `tables/rejects.tsv`
with a `reason` column.

## relationships.tsv — one row per typed edge
| column | meaning |
|---|---|
| edge_id | `<side>:e<NN>` (`x:eNN` for cross-neighborhood edges) |
| from_id, to_id | method_id, or `method_id.component` |
| type | `uses`, `extends`, `special_case_of`, `combines`, `shares_structure_not_equivalent`, `derivable_under_conditions`, `inspired_by` |
| conditions | the stated conditions under which the edge holds, `NA` when unconditional in the source |
| supporting_claims | claim IDs; at least one, and a bare citation is insufficient |
| motivation_claims | for `extends`, `combines`, `inspired_by`: the `motivation` claim IDs stating the problem the newer method addresses; else `NA` |
| note | one line |

## open_questions.tsv
`oq_id  side  question  missing_premise  related_claims  related_methods`
A theoretical question the sources leave unsettled is recorded here with the premise that would settle it.
