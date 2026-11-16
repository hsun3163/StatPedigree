# Parents step: what does this paper's method lean on? (shared by all per-paper jobs)

Hao's words: "pull in the methods those papers lean on, and jump. I think the track back should be able to ultimately
tracked back to generic stuff like regress and stuff."

Goal for PAPER_ID: list every earlier method or generic statistical tool that the authors state their method is built
from, extends, reduces to, contains as a special case, uses as a component, or was inspired by, so the pedigree can be
followed upward until it reaches generic statistics (regression, Bayes, shrinkage, wavelets, sampling, and so on).

Work only from `sources/PAPER_ID.txt` (+ `.supp.txt`). Read `SCHEMA.md` for the claim columns and edge types.

1. For each dependency the authors state, make sure `papers/PAPER_ID/claims.tsv` holds a claim row with role `relation`
   whose span states it and whose `other_method` is the parent id. Reuse an existing row when one states it; otherwise
   append a new row continuing the numbering. Existing rows stay byte-identical. Spans are exact substrings of the
   stored text. Tag `author-stated` only; skip dependencies you would have to infer.
2. Write `papers/PAPER_ID/parents.tsv` (tab-separated, header):
   `child_method_id  parent_id  parent_name  parent_kind  proposed_type  conditions  supporting_claims  citation  note`
   - `child_method_id`: a method id from this paper's `methods.tsv` (add `.prior`, `.inference_algorithm`,
     `.model_likelihood`, `.data_input` when the dependency concerns one component).
   - `parent_kind`: `method_paper` (a specific published method with its own paper) or `generic` (textbook statistics).
   - `proposed_type`: one of the SCHEMA edge types, read as "child TYPE parent" (for a parent that is a special case
     of the child, write `contains_special_case`).
   - `supporting_claims`: claim ids from this paper, `; ` separated. A row with no span-checked claim is dropped.
   - `citation`: for `method_paper`, first author, year, title as the reference list gives them; `NA` for generic.
   - `conditions`: the stated condition under which the relation holds, or `NA`.
3. Parent ids. Use an existing id when the parent is one of:
   fsusie, sfr, susie, ser, susierss, ash, smash, wavelet_ss, wfmm, mvsusie, mser, mash, sushie, finemap, bvsr,
   bridgeprs, bridgeprs_stage1, bridgeprs_stage2, prscs, prscs_auto, prscsx, ldpred, ldpred_inf, ldpred2, prsice2, horseshoe.
   For generic statistics use this vocabulary (add a new snake_case id only when none fits, and say so in `note`):
   simple_linear_regression, multiple_linear_regression, multivariate_regression, bayesian_linear_regression,
   conjugate_normal_model, ridge, lasso, spike_and_slab, scale_mixture_of_normals, global_local_shrinkage,
   mixture_model, normal_means, empirical_bayes, bayes_factor, fdr, variational_inference, coordinate_ascent,
   em_algorithm, gibbs_sampling, mcmc, wavelet_transform, wavelet_shrinkage, linear_mixed_model, blup, infinitesimal,
   meta_analysis, marginal_gwas_regression, clumping_thresholding, cross_validation, summary_statistics_likelihood.
   Any other published method gets a new snake_case id and `parent_kind = method_paper`.
4. Aim for completeness over the method's core construction (model, prior, fitting, data input): typically 5 to 15 rows.
   Benchmark-only comparators are out of scope.
5. Run `python scripts/check_spans.py PAPER_ID`; zero fixable rejects.
