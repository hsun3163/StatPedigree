# mallat1989 access report

Status: source retrieval blocked; span validation can complete for empty claim tables.
Access classification: abstract_only. Abstract availability: unavailable.

Europe PMC exact-title, DOI and author/year queries returned HTTP 200 with zero records. The broad title query returned other papers. Allowed-domain searches found citations rather than a deposited version of this paper. The retained project reference metadata has no abstract. Its author-site PDF route is outside the explicitly permitted routes and was not fetched.

The source text contains the verified title and an empty Abstract section. Claims, methods and theoretical open-question tables are header-only because neither the full text nor the abstract was retrieved. No theorem, prior, algorithm, limitation or relation has been inferred from the title or another paper.

Native fetch limitation: scripts/fetch_paper.py requires --pmcid, --arxiv, or --biorxiv; no matching identifier was resolved. Its PublicSession was reused for Europe PMC metadata queries, with responses saved in tmp/mallat1989 to avoid the script's shared tmp/fetch_events.jsonl log. Shared scripts are unchanged.

Source provenance and query evidence: sources/mallat1989.metadata.json and tmp/mallat1989/*_search.json.
Restart point: retrieve a verified abstract or full-text deposit through an authorized route, then extract claims and rerun python scripts/check_spans.py mallat1989. The empty span-check result verifies formatting and absence of rejected claims; scientific extraction remains blocked by source availability.
