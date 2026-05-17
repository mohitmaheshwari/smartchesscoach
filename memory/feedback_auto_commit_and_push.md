---
name: Auto-commit and push after every change
description: User wants every code change committed and pushed to origin without being asked
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
After making code changes, commit them with a clear message AND push to the remote (the deploy server reads from git). Do this proactively — don't wait to be asked.

**Why:** User asked explicitly: "can you also commit and sync to server on git after every change, so i don't do it manually". The deploy server reads from git, so a change that isn't pushed isn't deployed.

**How to apply:**
- Commit after each logical unit of work (a feature, a fix, a refactor) — not after every single Edit call. Group related changes into one commit.
- Always `git push` after the commit so the server picks it up.
- Use the standard commit-message style + Co-Authored-By trailer.
- Still ask before destructive git operations (force push, reset --hard, amending published commits) — autonomy applies to commit+push, not to rewriting history.
- Diagnostic scripts and one-off backfill scripts get committed too (the user has been running them inside Docker on the server, so they need to land in the repo to be available).
