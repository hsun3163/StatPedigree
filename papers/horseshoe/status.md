# horseshoe source-access blocker

Europe PMC DOI and title searches: HTTP 200, hitCount=0; arXiv exact-title and DOI searches: HTTP 200, totalResults=0. No abstract retrieved from permitted repositories.

The source contains the supplied title and an empty abstract section. Access is marked abstract_only as the requested fallback ceiling; an abstract was not obtained. Extraction is blocked. Header-only tables preserve the requested schemas; zero checked claims is not a completed scientific extraction.

fetch_paper.py requires --pmcid, --arxiv, or --biorxiv; no matching repository identifier was found. get() writes shared tmp/fetch_events.jsonl, outside this task scope; metadata probes used its PublicSession without get().

Staged in papers/horseshoe/closed_access.ris; shared deferred/closed_access.ris is outside the explicit write allowlist.
