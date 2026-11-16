Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — one paper through fetch, claim extraction and span check. PAPER_ID = __PAPER_ID__

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `papers/__PAPER_ID__/*`, `sources/__PAPER_ID__.*`,
temp files in `./tmp/__PAPER_ID__/`, and (only when the paper is absent from `seed/seed_list.tsv`) one appended seed row.
Other jobs run beside you on other papers: leave scripts, tables, vault and other papers' files as they are. No commit. No deletions.

Follow `briefs/extract_paper.md` exactly for PAPER_ID = __PAPER_ID__. Paper hint: __HINT__

Open routes only (PMC, Europe PMC, arXiv, bioRxiv/medRxiv); publisher sites are out of scope. When no open full text
is reachable, store title + abstract, set access `abstract_only`, and extract only what the abstract states.

Then do the parents step in `briefs/parents_step.md` for the same PAPER_ID (it writes `papers/__PAPER_ID__/parents.tsv`).

Acceptance: `papers/__PAPER_ID__/parents.tsv` exists; `python scripts/check_spans.py __PAPER_ID__` prints the kept count with zero fixable rejects;
`papers/__PAPER_ID__/{methods.tsv,claims.tsv,claims.checked.tsv,open_questions.tsv,rejects.tsv}` exist.
Fix and continue on operator failures (if a shared script has a bug, work around it in your invocation and name the bug in your reply).
Final reply: at most 6 lines, beginning `Δ `, as the brief specifies. Paste no paper content.
