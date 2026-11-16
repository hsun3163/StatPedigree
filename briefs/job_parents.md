Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — parents step for one already-extracted paper. PAPER_ID = __PAPER_ID__

Project root: /sc/arion/projects/load/users/sunh14/stattree. Write only `papers/__PAPER_ID__/*` and temp files in
`./tmp/__PAPER_ID__/`. Other jobs run beside you on other papers: leave scripts, tables, vault and other papers' files
as they are. No commit. No deletions.

Follow `briefs/parents_step.md` exactly for PAPER_ID = __PAPER_ID__. (__HINT__)

Acceptance: `papers/__PAPER_ID__/parents.tsv` exists with every `supporting_claims` id present in
`papers/__PAPER_ID__/claims.checked.tsv`; `python scripts/check_spans.py __PAPER_ID__` shows zero fixable rejects.
Final reply: at most 5 lines, beginning `Δ `: rows in parents.tsv, claims added, rejects, any new parent ids. Paste no paper content.
