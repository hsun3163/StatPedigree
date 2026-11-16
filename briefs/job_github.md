Read first and follow ~/.claude/CLAUDE.md and ~/.codex/skills/human-runner/SKILL.md.

# Task: stattree — put the project on GitHub from the terminal

Project root: /sc/arion/projects/load/users/sunh14/stattree. Target: https://github.com/hsun3163/StatPedigree (public, empty).

Hao's words: "把整个东西放github 上面吧。https://github.com/hsun3163/StatPedigree 让codex gitclone and push" and
"通过github terminal 不要通过插件" (use git and the gh CLI in the terminal; no plugin or connector).

Do it with plain `git` (and `gh` only for authentication, e.g. `gh auth setup-git`, and for a final check):
1. `git clone` the empty repository into `tmp/StatPedigree_clone` to confirm access, then make the project root itself the
   working tree: `git init -b main` in the project root, `git remote add origin https://github.com/hsun3163/StatPedigree.git`.
   Use the git identity already configured for this user; change no global git settings beyond what `gh auth setup-git` does.
2. The repository is PUBLIC. Write `.gitignore` so these stay local, and say so in the README:
   - `sources/` except `sources/stato/` (stored full texts and abstracts of papers: redistribution rights are unclear);
   - `codex_logs/`, `tmp/`, `temp_reference/`, `.qtest`;
   - `reports/aim3_table.md`, `reports/aim3_phenotype_scout.md`, `reports/combination.md`, `briefs/job_pheno_scout.md`,
     `STATUS.md` (thesis-specific plans and notes about restricted cohort data);
   - `map.html` (it embeds the thesis tabs), `vault/`, `vault.html` (generated, rebuildable).
   `docs/index.html` IS committed: it is the public build of the map (`python scripts/build_page.py --public --out docs/index.html`).
3. Before committing, list every file staged and check: no file over 50 MB; none of the ignored paths is staged; no staged
   file contains a token, password or key (search for obvious patterns). A staged file that fails is unstaged and named in your reply.
4. Add to `README.md`, at the top, a short section "StatPedigree" (at most 15 lines, plain words): what the repository is
   (an unverified draft map of how statistical methods in the SuSiE and polygenic-score families are built from earlier
   methods; every claim is a quoted sentence from a paper), what is in it (tables/, papers/, scripts/, briefs/, docs/index.html),
   how to rebuild the page, what is deliberately left out (the list in step 2) and why, and that parent links marked dashed
   on the map were placed by the map-maker without a stating sentence. Keep the existing README sections below it.
5. One commit on `main` with the message below, then `git push -u origin main`.

   Add StatPedigree: sourced claim tables, ontology tree and map page

   Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_01QCoDL8bbwznstShchYAH4Y

6. Verify with `git ls-remote origin main` and `gh repo view hsun3163/StatPedigree --json isEmpty,defaultBranchRef`.

No force push. No deletion of local project files (the clone under `tmp/` stays). Fix and continue on operator failures; if
authentication fails, stop and report the exact error text.
Final reply: at most 6 lines, beginning `Δ `: commit hash, number of files and total size pushed, what was left out, the
verification result, and anything unstaged in step 3.
