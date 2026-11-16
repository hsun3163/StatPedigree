Access: full_text
Version: medRxiv v1, 2026-09-07
Open source: https://www.medrxiv.org/content/10.64898/2026.09.03.26362206v1.full
Source SHA256: 71216ed5c8c9b7b43eb71fdce51bfdc13313e796724c63dc78c9dd64d216b043
Fetch: python tmp/gene_swap_randomization_gsr/fetch.py
Extraction: python tmp/gene_swap_randomization_gsr/extract.py
Check: python scripts/check_spans.py gene_swap_randomization_gsr
Native fetch bugs: DOI regex accepts only 10.1101; get() hard-codes shared tmp/fetch_events.jsonl. Invocation-only source substitutions accept 10.64898 and redirect that log under this paper tmp folder. Shared scripts unchanged.
Math limitation: displayed equations appear as Embedded Image placeholders; claims use readable prose without reconstructing equations. No supplement text was present; main-text light pass.
