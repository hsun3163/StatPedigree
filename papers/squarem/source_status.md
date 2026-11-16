Status: source acquisition blocked; extraction has zero claims.

Access label: abstract_only (upper bound on access); only the supplied title is retained. The Abstract section is empty because no target abstract was reachable. No full text, abstract content, theoretical claims, method components or open theoretical questions were fabricated.

Allowed Europe PMC DOI and exact-title searches returned HTTP 200 with hitCount=0. Raw responses: sources/squarem.raw.json. Allowed-domain web searches on PMC, Europe PMC, arXiv, bioRxiv and medRxiv located citations or unrelated papers, not target text. Retained project metadata contained a citation only. Publisher routes were not accessed.

Native fetch limitation: scripts/fetch_paper.py requires --pmcid, --arxiv or --biorxiv; it has no DOI-only metadata/abstract route. Invocation workaround: load the unchanged script with runpy, call its get function for Europe PMC metadata, redirect its ROOT to tmp/squarem so its request log stays scoped, and retain a title-only source.

Extraction tables are header-only; span-check acceptance measures only empty-table consistency. Content extraction remains blocked until a target abstract or allowed open text is available. Parents step skipped as requested.
