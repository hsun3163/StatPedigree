# StatPedigree

An unverified draft map of how methods in the SuSiE and polygenic-score families are built from earlier methods. Every claim is a quoted sentence from a paper.
The repository contains merged tables in `tables/`, paper claim tables in `papers/`, tools in `scripts/`, work instructions in `briefs/`, and the public map in `docs/index.html`.
Rebuild the public page from the project root with Python 3: `python scripts/build_page.py --public --out docs/index.html`.
Dashed parent links on the map were placed by the map-maker without a stating sentence.
The following stay local and are ignored by Git:
- `sources/` except `sources/stato/`: stored full texts and abstracts have unclear redistribution rights.
- `codex_logs/`, `tmp/`, `temp_reference/`, `.qtest`: local logs and scratch work.
- `reports/aim3_table.md`, `reports/aim3_phenotype_scout.md`, `reports/combination.md`, `briefs/job_pheno_scout.md`, `STATUS.md`: thesis plans and notes about restricted cohort data.
- `map.html`: embeds thesis tabs; `vault/` and `vault.html`: generated, rebuildable views.
Python caches and notebook checkpoints also stay local.

UNVERIFIED DRAFT MAP

# stattree

## 1. Fetch sources

Step 1 curates statistical methods and theory. The retained raw full papers are faithful repository sources; the reference map describes methods, priors and comparators. Seed identities were resolved with Europe PMC core metadata. Journal DOI, PMCID, online/issue dates and the actual deposited version were checked separately. Relative source paths for the eleven unfetched seeds are planned destinations, explicitly marked in the TSV.

Successful fetch commands, run from `~/sunh14_project/stattree`:

```bash
cd ~/sunh14_project/stattree
module load poppler/22.07.0 libtiff/3.9.7
python scripts/fetch_paper.py --help > tmp/fetch_help.txt
python scripts/fetch_paper.py fsusie --pmcid PMC12363973 > tmp/fsusie_fetch.log 2>&1
python scripts/fetch_paper.py bridgeprs --pmcid PMC10786716 > tmp/bridgeprs_fetch.log 2>&1
python scripts/fetch_paper.py susie --pmcid PMC10201948 > tmp/susie_fetch.log 2>&1
python tmp/build_reference_check.py
python tmp/acceptance.py > tmp/acceptance.json
```

Python: existing conda `py3.11` environment, Python 3.11.11 (conda-forge), requests 2.34.2. Python code uses the standard library and requests. OA-package PDF supplements use the existing external Poppler `pdftotext` 22.07.0 executable. The additional `libtiff/3.9.7` module supplies its required `libtiff.so.3`; loading Poppler alone was insufficient. No Python packages were installed. Commands use the host execution path because bubblewrap failed before shell execution.

Proxy: inherited `http_proxy`, `https_proxy` and `all_proxy` variables worked on this node. `module load proxies` was not needed; direct internet without those variables was not tested. Public repository requests explicitly bypass personal netrc authentication, including redirects, while retaining environment proxy support. Transient repository HTTP failures receive three bounded attempts. Logs record URLs, HTTP statuses and byte counts without proxy credentials.

Metadata-resolution commands run during preparation: `python tmp/resolve.py` and `python -u tmp/reference_metadata.py > tmp/reference_metadata.log 2>&1`. The first metadata pass met a transient HTTP 503; the missing WFMM query was repeated successfully. Raw core responses and selected records are under `tmp/`. `tmp/route_checks.json` records all seed route checks; `tmp/reference_route_checks.json` records ancestor route checks. The SuSiE-variance preprint full-text HEAD was rate-limited (429); its public metadata remained reachable. The dissertation legacy link was replaced by its migrated repository URL. NCBI efetch rejects HEAD (405), so its checks use streamed GET response headers with the response closed unread. Full text was downloaded for exactly fsusie, susie and bridgeprs. No publisher website was used for scripted full-text or supplement downloads.

The script also accepts `--arxiv IDvN` (export.arxiv.org HTML) and `--biorxiv DOIvN` (bioRxiv/medRxiv metadata API and server HTML). Those full-text branches were not exercised in this step. A PMCID whose repository full-text endpoint returns 404 produces the original metadata JSON plus title/abstract text. Other network or conversion errors remain visible failures. OA supplement ZIPs retain all downloaded package members; text is extracted only from document formats. Images remain in their archive. PDF text preserves extracted equation labels and paragraph layout but is not a mathematical typesetting reconstruction. Main JATS equations retain source TeX where provided, otherwise MathML fractions, subscripts and superscripts are rendered as text. Source-native model headings in SuSiE serve as its Methods-like headings.

`seed/reference_check.tsv` has 25 rows, grounded only in the stored fSuSiE/BridgePRS main text and obtained fSuSiE supplementary methods. PRS-CS-mult is mapped to its seeded parent PRS-CS; PRSice-meta and PRSice-2 share the PRSice comparator row. Two cited books have no complete open edition located and remain abstract-only/deferred in the DOI-bearing RIS file. Author pages provide excerpts or code, which were not treated as complete books. Reference identity metadata are in `tmp/reference_identities.json` and `tmp/reference_metadata.json`. No replacement content was substituted.

Review: [seed report](http://127.0.0.1:30548/lab/tree/sunh14_project/stattree/reports/seed_report.md) at `~/sunh14_project/stattree/reports/seed_report.md`. `JUPYTER_PORT` was unset in the command environment; 30548 comes from the latest user Jupyter live log.


## 2. Extract one paper

From the project root, follow `briefs/extract_paper.md` with `PAPER_ID=fsusie` (or `bridgeprs`). Read the retained main text and supplement and the worked claim before writing the paper's three TSVs. This is a manual evidence-extraction step; the brief is the exact instruction to a human or agent. Keep the worked `c01` unchanged. Separate assumptions, tunable settings and open theoretical questions. The source spans must be copied verbatim; do not infer a theorem from an empirical observation.

```bash
cd ~/sunh14_project/stattree
cat SCHEMA.md papers/_worked/worked_claims.tsv briefs/extract_paper.md
```

Write `papers/PAPER_ID/claims.tsv`, `methods.tsv` and `open_questions.tsv` using the schema. Both smoke papers are already extracted. Main source text is `sources/PAPER_ID.txt`; supplementary source text is `sources/PAPER_ID.supp.txt`. No fetch or third-party Python packages are needed for steps 3–5. Run the commands from the project root with Python 3.

## 3. Check spans

```bash
python scripts/check_spans.py fsusie bridgeprs
```

Omit paper IDs to check every paper folder except `_worked`. Whitespace runs are collapsed in the span and source; punctuation and characters are otherwise unchanged. Bad spans, tags, access values and unresolved or rejected premises are rejected. Premise checking considers all papers and iterates until stable, including when only selected papers' outputs are requested. `claims.tsv` stays unchanged; each paper receives `claims.checked.tsv` and `rejects.tsv` (with rejection reasons). Rejection counts are printed; finding rejected rows is a data outcome, not an operator exception. Fix source-backed rows in the per-paper table and repeat this command.

## 4. Merge

```bash
python scripts/merge_tables.py
```

This runs the check for every paper, then rewrites `tables/claims.tsv`, `methods.tsv`, `open_questions.tsv` and `rejects.tsv` from the per-paper TSVs. Unknown claim references in method assumptions, component citations or open questions become `NA` in the merged copies, with a warning. The paper files retain the original references. The lead authors `tables/relationships.tsv` and `tables/lineage_order.tsv` by hand; this step leaves them as found. An absent relationship table is valid and yields pending lineage notes.

## 5. Build vault

```bash
python scripts/build_vault.py --html vault.html
```

The builder reads `tables/*.tsv` and `seed/seed_list.tsv`. The tables are the source of truth. Every generated note is marked as an unverified draft; regenerate after changing tables, and never hand-edit generated notes. `vault/my-notes/` is created empty and thereafter left exactly as found. The four generated folders and `vault/README.md` are refreshed. To honor the no-deletion policy, stale generated Markdown notes are overwritten with a retirement notice. The optional self-contained HTML file is a linked reading copy of the same Markdown content, including Mermaid source; Obsidian renders the graph from the vault notes.

To review the two-edge rendering fixture without changing shared tables:

```bash
python scripts/build_vault.py --tables tmp/sample_tables --out tmp/sample_vault
```

`tmp/sample_tables/relationships.tsv` contains two clearly labeled smoke-fixture edges. It is not a scientific relationship table. The fixture also supplies an ordered walk and exercises component endpoints, a method without a table row and a cross-side edge. `vault/lineage/fsusie.md` and `vault/lineage/prs.md` say `relationships pending` until the lead supplies shared edges and ordered walks.

Repeat the retained acceptance checks (fixtures and all temporary files stay in `tmp/`):

```bash
PYTHONDONTWRITEBYTECODE=1 python tmp/smoke_acceptance.py > tmp/smoke_acceptance.log 2>&1
```

The acceptance check creates a temporary marker in `vault/my-notes/` for the preservation test and relocates the marker under `tmp/` after verifying its content, metadata and directory contents survived. It verifies the submitted per-paper claim files remain unchanged, as well as premise rejection, missing-reference warnings, generated notes, isolated lineage rendering and repeatable output. The smoke report is `reports/smoke_report.md`.

## 6. Lead-authored tables and reports
- `tables/relationships.tsv`, `tables/lineage_order.tsv`, `papers/lead/open_questions.tsv`: written by hand from `tables/claims.tsv`; `merge_tables.py` leaves the first two alone and merges the third.
- `reports/aim3_table.md`, `reports/combination.md`: written by hand; every bracketed ID is a row of `tables/claims.tsv`.
- Full rebuild: `python scripts/merge_tables.py && python scripts/build_vault.py --html vault.html`. Open `vault/` as an Obsidian vault; `vault/my-notes/` is yours and is never rewritten.

## 7. How this differs from STATO (draft paragraph)
STATO (https://stato-ontology.org/) and this map overlap in subject and differ in scope, depth and form. Scope: STATO is a general-purpose ontology of statistical tests, models, inference methods, study designs and their conditions of application across statistics; this map covers two small neighborhoods (the fSuSiE lineage and BridgePRS with its comparators), 14 papers. Hao's preliminary look at the 2026-04-20 STATO release found models, inference methods and some machine-readable application conditions, and found no SuSiE-family or wavelet entries by name search; that look was a name search, so absence of these names is the only thing it shows. Depth: STATO gives each term a curated definition and, for some, formal application conditions; this map goes below the method name to conditional claims (objects, assumptions, conclusion, scope, the motivating problem) and to typed relations between methods that hold only under stated conditions, each tied to a quoted span, and it keeps unresolved theoretical questions as first-class rows. Form: STATO is an OWL ontology with logical axioms, curated and versioned by a community and usable by reasoners; this map is three flat text tables and a generated Obsidian vault, produced in two days by an AI pipeline with a string-match source check and no expert validation. The two are complementary: STATO terms could serve as stable identifiers for the model, prior and inference components in `tables/methods.tsv`, and the claims here are the kind of paper-level evidence an ontology entry does not carry.

## 8. Second pass: what to fetch next
- Held from the seed discussion: Morris & Carroll 2006 wavelet-based functional mixed models (`wfmm`, PMC2744105), mash (Urbut 2019, PMC6309609). Both already appear as edge targets.
- Named by stored papers as comparators or ancestors: SuSiEx, MESuSiE, XMAP (SuShiE comparators); FINEMAP, CAVIAR, DAP-G (SuSiE-RSS); CAFEH (mvSuSiE); Johnstone & Silverman EB wavelet thresholding (smash); lassosum (PRSice-2); BSLMM, BayesR (LDpred); wavelet spike-and-slab priors (Crouse 1998, Ma & Soriano 2018; fSuSiE).
- Named only in `reports/combination.md` from background knowledge: SuSiE-inf, PolyPred, mr.ash, SBayesRC, PolyFun, SDPRX, X-Wing, PROSPER, CT-SLEB, JointPRS, MultiSuSiE.
- Supplements that the open route refused: susie (PMC10201948), wavelet_ss (PMC5795621), sushie and prscsx (HTTP 403). Add them through Zotero full-text retrieval.
- Deferred closed-access items: `deferred/closed_access.ris` (two wavelet textbooks).
- Cleanup: strip LaTeX markup from PMC equation text in `fetch_paper.py` (ash, mvsusie spans carry it); fix the hard-coded shared temp path the per-paper jobs reported.

## 9. Readable page
`python scripts/build_page.py` writes `map.html`: a phone-first reading view (lineage walks, Aim 3 cards, combination, open questions, claim search) built from `tables/` and `reports/` with `scripts/page_template.html`. It replaces `vault.html` as the page to read.

The first tab of `map.html` is a zoomable pedigree map: one star per method, ancestors above descendants, a few key
labels per star when zoomed in, and the full method card on tap. Star positions, tiers and labels are hand-written
in `tables/map_layout.tsv` (labels are the lead's short paraphrases of `tables/methods.tsv`); edit that file and rerun
`python scripts/build_page.py` to move or relabel a star.
