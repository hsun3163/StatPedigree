Source: medRxiv v3, 2026-09-04; DOI 10.1101/2025.04.17.25326042.
Access: full_text through the metadata-provided open medRxiv JATS URL.
Raw XML and metadata are retained in sources/colocboost.*.
The existing scripts/fetch_paper.py converter produced the retained text. Equations are image-only in this deposited XML and the converter omits them; claims use prose and no missing formula is reconstructed. Supplementary Note is referenced but no supplementary text was obtained in this light pass.
Native fetch invocation and route errors: tmp/colocboost/fetch.log and fetch_events.jsonl. The shared fetcher hard-codes tmp/fetch_events.jsonl; invocation-only replacement redirected it to tmp/colocboost/fetch_events.jsonl. No shared script was edited.
Native full-text fetch failure: 403 Client Error: Forbidden for url: https://www.medrxiv.org/content/10.1101/2025.04.17.25326042v3.full
PDF route: 403 Client Error: Forbidden for url: https://www.medrxiv.org/content/10.1101/2025.04.17.25326042v3.full.pdf
Europe PMC preprint XML route: 500 Server Error:  for url: https://www.ebi.ac.uk/europepmc/webservices/rest/PPR1007226/fullTextXML
Scope: 15 method/theory claims; named single-trait restriction FineBoost included; no parents step.
Final review: 15 claims, 2 methods, 2 open questions; TSV cell constraints and component/assumption references checked. Native check: colocboost kept=15 rejected=0. All five required TSV outputs exist.
Review correction: an initial TSV cell assertion failed because a source span crossed paragraph lines; whitespace was collapsed within cells and the TSV review passed.
