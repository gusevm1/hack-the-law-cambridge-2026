---
name: ship-feature
description: >-
  Use at the START of any shippable change in this repo, before writing code.
  Triggers on intent to ship: "let's build/ship/implement X", "start a feature",
  "work on <feature>", "fix <bug> and ship it", or any task that ends in a PR.
  Sets up the git workflow: branch off main, commit atomically, open a PR, get CI
  green, resolve conflicts against main intelligently, squash-merge to main. main
  is production — Vercel auto-deploys the frontend; backend deploys via `just
  deploy`. Do NOT use for throwaway exploration or read-only questions.
---

# ship-feature — the workflow

Every feature, fix, or doc change rides the same rails: **branch off `main` →
atomic commits → PR → CI green → conflict-aware squash-merge to `main` → verify.**
`main` is production. There is no dev/prod split — `main` + localhost only.

## Hard rules

- **Never commit directly to `main`.** Always branch first. `main` is the deploy
  branch (Vercel auto-deploys `frontend/`; backend via `just deploy`).
- **Never `git push --force` to `main`.** Force-push only your own feature branch.
- **Keep infra account-portable.** No hardcoded project IDs / regions / accounts
  in code — everything GCP-specific goes through `infra/` env vars or
  `app/settings.py`. We switch GCP accounts soon; the rebuild stays `bootstrap` +
  `deploy` with new values.
- **Commit only real, green work.** Backend: `just lint` + `just test` pass.
  Frontend: `pnpm build` clean.
- **Integrate on the feature branch, never on `main`.** Sync `origin/main` *into*
  the branch, resolve there, re-test, then merge out.

## 0. Scope

1. Pick a **type**: `feat | fix | docs | chore | refactor`.
2. Pick a kebab **slug** (names the branch). Branch: `<type>/<slug>`.
3. Surface the branch name in one line, then go.

## 1. Branch off main

```sh
git fetch origin
git switch -c <type>/<slug> origin/main
```

(For parallel work, a worktree is fine: `git worktree add -b <type>/<slug>
../hack-the-law-cambridge-2026-<slug> origin/main`. Optional — a hackathon usually
runs one stream at a time.)

## 2. Work + commit atomically

- **ponytail first** — run the ladder (YAGNI → stdlib → native → installed dep →
  one line → only then new code). Shortest working diff wins.
- Small, self-contained commits — one logical change each.
- Backend green (`just lint`, `just test`); frontend builds.
- End each commit message with the model co-author trailer, e.g.
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## 3. Push + PR

```sh
git push -u origin <type>/<slug>
gh pr create --base main --title "<type>(<scope>): <summary>" --body "<body>"
gh pr checks --watch        # CI: backend lint+test, frontend build
```

End the PR body with:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

PRs get a **Vercel preview URL** automatically — verify the UI there before merge.

## 4. Sync main in, resolve, retest (before merge)

```sh
git fetch origin
git merge origin/main         # integrate INTO the branch; resolve here
# regenerate lock files (uv.lock, pnpm-lock.yaml) rather than hand-merge
# re-run just lint && just test (and pnpm build if frontend touched)
```

## 5. Squash-merge + verify

```sh
gh pr merge --squash --delete-branch
```

- **Frontend** changed → Vercel deploys `main`. Verify the production URL.
- **Backend** changed → run `just deploy`, then `curl <cloud-run-url>/health`.

## Checklist

```
[ ] type + slug chosen, branch surfaced
[ ] branch off origin/main
[ ] ponytail ladder run; atomic commits; co-author trailer; area green
[ ] no hardcoded GCP project/region/account in code
[ ] pushed, PR opened (base main), CI green, Vercel preview checked
[ ] synced origin/main into branch, resolved + retested
[ ] squash-merged to main
[ ] verified: Vercel prod (frontend) and/or `just deploy` + /health (backend)
```
