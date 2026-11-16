# stattree seed report — 2026-11-13
All 14 seeds have open full text; exactly three were fetched. Two ancillary books remain deferred (no complete open edition located).
fsusie — full_text+supplement; PMC12363973; deposited bioRxiv v1 (2025-08-17); Europe PMC XML.
susie — full_text; PMC10201948; accepted author manuscript; NCBI efetch.
susierss — full_text; PMC9337707; journal OA version; Europe PMC XML HEAD 200; not fetched.
ash — full_text; PMC5379932; journal OA version; Europe PMC XML HEAD 200; not fetched.
wavelet_ss — full_text; PMC5795621; author manuscript; NCBI efetch response headers 200; not fetched.
wfmm — full_text; PMC2744105; author manuscript; NCBI efetch response headers 200; not fetched.
mvsusie — full_text; PMC12900646; 2026 journal OA version; Europe PMC XML HEAD 200; not fetched.
sushie — full_text; PMC12767540; author manuscript; NCBI efetch response headers 200; not fetched.
mash — full_text; PMC6309609; author manuscript; Europe PMC XML HEAD 200; not fetched.
bridgeprs — full_text+supplement; PMC10786716; journal OA version; Europe PMC XML.
prscs — full_text; PMC6467998; journal OA version; Europe PMC XML HEAD 200; not fetched.
prscsx — full_text; PMC9117455; author manuscript; Europe PMC XML HEAD 200; not fetched.
ldpred2 — full_text; PMC8016455; journal OA version; Europe PMC XML HEAD 200; not fetched; online 2020, issue 2021.
ldpred — full_text; PMC4596916; free-to-read journal version; NCBI efetch response headers 200; not fetched.
Supplements: fsusie — one PDF extracted from its 8,995,703-byte Europe PMC OA ZIP; source is explicitly v1.
Supplements: bridgeprs — three PDFs extracted from its 4,743,786-byte Europe PMC OA ZIP (supplementary information, reporting summary, peer review).
Supplements: susie — OA API says “Article with id PMC10201948 is not open access one”; no OA-package supplement obtained. Main manuscript is readable.
Reference check: 25 rows; fSuSiE cites susie, susierss, ash, wavelet_ss and mvsusie; wfmm, sushie and mash are absent from this deposited reference list.
Reference check: supplementary methods add interpolation, mixture optimization, variational inference and empirical Bayes ancestors. mvSuSiE is cited as its 2023 preprint, not the later journal version.
Reference check: BridgePRS benchmarks PRS-CSx, PRS-CS-mult (seeded PRS-CS parent), and PRSice-meta (unseeded PRSice-2); no LDpred/LDpred2 comparator found.
Deferred: Mallat (2009), third-edition Wavelet Tour, and Nason (2008), Wavelet Methods in Statistics with R; DOI-bearing BOOK records in deferred/closed_access.ris. Author sites offer excerpts/code, not a complete open edition.
Failure fixed: “UnicodeDecodeError: 'utf-8' codec can't decode byte 0x93 in position 59: invalid start byte” — public requests now bypass malformed netrc, retaining proxy support.
Failure fixed: “FileNotFoundError: [Errno 2] No such file or directory: 'pdftotext'”; then “libtiff.so.3: cannot open shared object file: No such file or directory” — loaded Poppler and matching libtiff.
Failure fixed: “zipfile.BadZipFile: File is not a zip file” — script recognizes the API's XML error response before attempting ZIP extraction.
Route failures recovered: Europe PMC metadata HTTP 503; non-OA XML HTTP 500; PMC HTML HTTP 403; efetch HEAD HTTP 405; one efetch HTTP 429. Successful repository alternatives are recorded in tmp/route_checks.json.
Initial sandbox failure: “cannot enforce sandbox read-only path /hpc/users/sunh14/.codex because it crosses writable symlink /hpc/users/sunh14/.codex” — host execution succeeded.
Diagnostics: exact errors in tmp/operator_failures.log; request trail in tmp/fetch_events.jsonl; PDF equations remain extracted text, with raw PDFs retained in OA ZIPs.
Acceptance PASS: texts 118,050 / 116,496 / 67,549 bytes (fsusie / susie / bridgeprs); native Methods-like headings and References; NFC; 14 complete seed rows and reached routes; 25 reference rows; CLI help.
Ancillary route diagnostics: SuSiE-variance preprint full-text HEAD HTTP 429 (open API metadata HTTP 200); dissertation legacy URL HTTP 404, migrated repository PDF HEAD HTTP 200.
Acceptance diagnostic fixed: “AssertionError: susie” — successful native fetch evidence now accompanies HEAD records; all declared checks pass.
