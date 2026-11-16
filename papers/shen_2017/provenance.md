# shen_2017 extraction

Access: abstract_only. DOI 10.1093/bioinformatics/btx467; PMCID PMC6355111.

Native fetch: scripts/fetch_paper.py shen_2017 --pmcid PMC6355111, executed through an in-memory invocation that redirects its shared temporary log destinations into tmp/shen_2017/. Shared scripts are unchanged. The retained extraction invocation is tmp/shen_2017/extract.py.

Fetcher limitation: successful NCBI XML is treated as full text even when it contains only an abstract and no body. The returned pmc-articleset has zero body paragraphs; this extraction explicitly uses abstract_only. The fetched text contains the title and structured abstract.

Repository checks: Europe PMC fullTextXML returned HTTP 500; PMC article page returned HTTP 403. Responses are retained under tmp/shen_2017/. Supplement response: SUPPLEMENT unavailable in Europe PMC OA package: Article with id PMC6355111 is not open access one

Eight author-stated claims, one method row, two open questions; no benchmark claims. Prior, fitting algorithm, assumptions and tunable settings remain NA because they are unspecified in the available abstract. Relations record the two named model families without claiming equivalence. Parents step skipped as requested.
