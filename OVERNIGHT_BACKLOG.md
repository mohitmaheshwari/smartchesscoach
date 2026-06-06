# Overnight Autonomous Backlog — 2026-06-06 (Mohit away ~15h)

**Authorized:** build + test + commit + (deploy if confident). Spread across all areas.
Conservative acknowledge + re-run with fixed heuristic. Metadata = backend canonical fields + backfill.

**Hard constraints (hold these unattended):**
- **I cannot deploy** — no shell on srv1050112. All work = commit + push; deploy is a runbook for Mohit. (Auto-deploy unknown.)
- **Tunnel likely down** most of the 15h → bias to code/design (tunnel-independent). DB work = best-effort-when-up.
- **No careless infra/compose/port edits** (today's port collision). Validate `docker compose config` before any compose change; never re-touch ports/networking unattended.
- **No new detector ships behavior change without tests** against real FENs.
- Everything checkpointed to files; commit frequently so a tunnel/session drop loses nothing.

## Work items (spread across all)

### P0 — Caption "why" gap (the core product task)
- [ ] **played_HANGS_piece predicate** — user move leaves a piece attacked+undefended that wasn't before. Clean, low-misfire. Build in caption_facts + R12, TEST against saved `/tmp/bare_forensics.json` FENs (python-chess, no engine). Commit.
- [ ] **Severity-mismatch detector** — caption positive/bland while cp_loss is large (e.g. "King is safe" on a 7-pawn blunder). The caption's severity word must track the canonical severity. (Pairs CAPTION_BACKLOG #18.)
- [ ] **Opp-move bucket (~52)** — opp-failure variants 3 (traded_active_for_inactive) & 4 (quiet_when_threatened). Design from corpus; build if confident + testable.

### P1 — Cleanup
- [ ] Fix bare-detector heuristic (misses coords inside capture SANs like `Qxb6`/`gxh3`) → re-run forensics for an accurate bare count.
- [ ] Acknowledge sweep (tunnel-permitting): conservative bar + re-run with fixed heuristic to catch under-acknowledged good captions.

### P2 — Metadata fix (backend canonical fields + backfill)
- [ ] In `journey_service.sync_user_games`: populate `opponent`/`white`/`black` + parse PGN `[UTCDate]`→`date_played`.
- [ ] Backfill script for existing games (run later — needs tunnel).

### Deliverables by morning
- [ ] `MORNING_SUMMARY.md` — what shipped (committed), what's tested, decisions awaiting you, deploy runbook.
- [ ] All code committed + pushed to `working-code`.
- [ ] Data-locked predicate roadmap (failure-mode distribution → coverage).

## Already committed this session, awaiting your deploy
- Backend: V4-LLM gate, worker healthcheck fix, 2 cp_loss reframes (port fix already live)
- Frontend (needs frontend-builder rebuild): eval bar+graph, "Open Game" button, shape-promotion-to-primary
- Deploy runbook will be in MORNING_SUMMARY.md
