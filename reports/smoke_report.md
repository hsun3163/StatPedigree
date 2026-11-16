UNVERIFIED DRAFT MAP
# Step 2 smoke report
Acceptance: PASS; both stored source titles match their seed identities; worked c01 rows retained exactly.
fsusie: 30 kept, 0 rejected; 3 methods; 3 open questions; full_text and supplement claims.
bridgeprs: 30 kept, 0 rejected; 3 methods; 3 open questions; full_text claims; supplement inspected (figures/tables and peer review).
Merged: claims=60; methods=6; open_questions=6; rejects=0; all four TSVs have headers.
Scripts (standard library): check_spans.py=100 lines; merge_tables.py=39; build_vault.py=149.
Vault: 76 generated notes; required method and c01 notes contain source spans and tags.
HTML: implemented (12 lines); vault.html is a self-contained linked Markdown reading copy, with Mermaid source.
Fault injection: broken/empty spans, invalid tags/access, missing premises and cascading cross-paper premises rejected.
Checks: whitespace collapse and supplementary spans pass; merge warns and substitutes NA for unknown claim IDs.
Lineage: two-row sample in tmp/sample_tables; isolated fsusie/cross graphs, component endpoints, unknown node, ordered walk and both method directions pass; PRS graph tested separately.
Shared relationships.tsv and lineage_order.tsv remain unwritten; production lineage notes say relationships pending.
Personal-note marker survived rebuild byte-for-byte with inode, mode, mtime and directory contents preserved; relocated into tmp/ afterward; vault/my-notes/ is empty.
Stale generated fixture note was overwritten with a retirement notice; no deletion was used.
Operator failure: error building bubblewrap command: Fatal error: cannot enforce sandbox read-only path /hpc/users/sunh14/.codex because it crosses writable symlink /hpc/users/sunh14/.codex
Fix: required reads and project commands used the approved host execution path.
Test failure: AssertionError (lineage fixture expected an unescaped wikilink pipe in a Markdown table).
Fix: assertion accounts for Markdown table escaping; the retained log includes the failed assertion and complete passing rerun.
Evidence: tmp/smoke_acceptance.log and tmp/smoke_acceptance.json; repeat with the README command.
JUPYTER_PORT is unset; review links use the existing README tunnel port 30548 (not refreshed).
Final review: all requested acceptance checks pass; writes stayed inside the project; source claim files preserved by checking/merging; no commit or deletion.
