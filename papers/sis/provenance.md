Source: https://export.arxiv.org/html/math/0612857v2
Version: arXiv math/0612857v2, 2008-08-27; full_text.
Native fetch: scripts/fetch_paper.py sis --arxiv math/0612857v2, invoked through runpy with ROOT routing only temporary paths into tmp/sis. The fetcher hardcodes a shared tmp/fetch_events.jsonl; the invocation confines that log to tmp/sis/fetch_events.jsonl without changing the script.
PMC2709408 and sources/sis.raw.xml are the Zhang discussion and were excluded; sources/sis.raw.html and sources/sis.txt are the Fan-Lv arXiv source used by every claim. An HTML rendering date of August 24, 2026 is not treated as a publication or revision date.
Scope: light ancestor pass, 15 claims, 2 methods, 2 open questions, no parents step.
Rerun extraction: PYTHONDONTWRITEBYTECODE=1 python tmp/sis/extract.py
Validation: python scripts/check_spans.py sis
Operator deviation: importlib-based fetcher inspection wrote scripts/__pycache__/fetch_paper.cpython-311.pyc outside the authorized paper paths. Retained because deletions are prohibited; later Python invocations disable bytecode writes.
Final review: required files exist; native span check sis kept=15 rejected=0; 2 method rows and 2 open questions; exactly one sis seed row. The bytecode-cache scope deviation above remains.
