# wu_2009 extraction provenance
Access: full_text. Open source: https://pmc.ncbi.nlm.nih.gov/articles/PMC2732298/
Retrieved 2026-11-14 through the web reader after direct repository HTML requests failed. The retained source combines contiguous article lines 91-429 (abstract, body, references), strips web-reader line numbers and link markup, and normalizes Unicode to NFC. Equation images remain labeled placeholders; no equation transcription or Bayesian prior equivalence was inferred. Raw web-reader responses and original abstract-only XML are retained beside the normalized source.
Europe PMC reports no open supplementary package. Publisher routes were outside scope. No parent extraction was performed.
The existing fetcher was invoked with its two shared temporary output paths redirected into tmp/wu_2009 in memory. Its XML success detection accepts an abstract-only article as full text; source inspection caught this and PMC web-reader text replaced the normalized abstract-only source.
The checker scans all paper folders even for one selected paper. Another concurrently populated folder lacked claims.tsv. The supported --root argument provides an isolated paper view through symlinks; checker outputs are written to the actual wu_2009 paper folder. Claims have no external premises.

Reproduction from project root:
PYTHONDONTWRITEBYTECODE=1 python tmp/wu_2009/extract.py
PYTHONDONTWRITEBYTECODE=1 python scripts/check_spans.py wu_2009 --root tmp/wu_2009/span_root

Recovered operator errors (verbatim):
error building bubblewrap command: Fatal error: cannot enforce sandbox read-only path /hpc/users/sunh14/.codex because it crosses writable symlink /hpc/users/sunh14/.codex
403 Client Error: Forbidden for url: https://pmc.ncbi.nlm.nih.gov/articles/PMC2732298/
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x93 in position 59: invalid start byte
FileNotFoundError: [Errno 2] No such file or directory: '/sc/arion/projects/load/users/sunh14/stattree/papers/mandozzi_2016/claims.tsv'
