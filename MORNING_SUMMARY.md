# Morning Summary — overnight work 2026-06-06 (Mohit away ~15h)

**TL;DR:** 5 commits, all on `working-code`, **none deployed** (no prod shell — see deploy runbook). Caption "why"-gap forensics done + data-locked roadmap. `played_hangs` predicate built + tested (not wired — needs your review). Metadata fix + PWC telemetry flag shipped to branch. Feedback pending 395→323. Queue draining on its own.

---

## 1. What I committed (all pushed to `working-code`, NOT deployed)

| Commit | What | Risk | Deploy |
|---|---|---|---|
| `571d6586` | **Metadata fix** — canonical opponent/white/black + date_played in sync + backfill script | Low (isolated to import path) | safe |
| `3416b4f8` | **PWC telemetry flag** in docker-compose (starts Phase-3 soak; shadow-only) | Low (env-only, no user-facing change) | safe |
| `663fd63b` | **played_hangs_detector** — standalone, tested, **NOT wired** | None (nothing calls it yet) | n/a until wired |
| `57dd1984` | **severity_mismatch_guard** — standalone, tested (4 fires/0 false), **NOT wired** | None (nothing calls it yet) | n/a until wired |
| earlier | V4-LLM gate (`b3d57cde`), worker healthcheck fix (`ad661644`), 2 cp_loss reframes (`47f017af`) | Low | safe |
| earlier | Frontend: eval bar+graph, "Open Game" btn, shape-promotion | Low (frontend) | needs frontend-builder rebuild |

---

## 2. DEPLOY RUNBOOK (when you're back) — one careful pass

```bash
cd ~/repos/smartchesscoach && git pull

# Backend (picks up V4-LLM gate, cp_loss reframes, metadata sync fix, PWC telemetry flag):
docker compose up -d --force-recreate --no-deps backend
curl -sf http://localhost:8002/api/health && echo " backend OK"

# Frontend (eval bar, Open Game, shape-promotion):
docker compose up -d --build frontend-builder

# Worker healthcheck fix (optional, clears false 'unhealthy'):
docker compose up -d --force-recreate --scale analysis-worker=3 analysis-worker

# One-time backfill of existing games' metadata (after backend is up):
docker exec chess-coach-backend python /app/backend/scripts/backfill_game_metadata.py        # dry-run
docker exec chess-coach-backend python /app/backend/scripts/backfill_game_metadata.py --apply
```
⚠️ Do NOT change ports. backend stays `8002:8002` (8001 = matrimonial). I verified `docker compose config` on every compose edit.

---

## 3. The caption "why"-gap — data-locked roadmap (the core product task)

Forensics on the flagged-bare captions (158→166 true-bare, FENs saved). Failure-mode distribution of the **user-move** bare captions:

| Bucket | ~N | Status |
|---|---|---|
| opp-move (explain what opp missed) | ~52 | opp-failure framework — V1&2 shipped; **V3/V4 designed below** |
| **played hangs a piece** | ~16 | **detector built + tested** (`663fd63b`) — wiring diff in §4 |
| missed capture (trade/defended) | ~10 | extend existing missed_capture predicate |
| missed check / mate | ~6 | missed-forcing predicate (design TBD) |
| small/positional | ~52 | low priority — often genuinely fine |

**Also surfaced (high value):**
- **Severity-mismatch** — captions that say something *positive/bland on a big blunder*: `O-O-O` cp_loss **698** → *"King is safe; rook joins the game."*; `Rxf4` cp_loss **8774** → *"queen is the only piece doing anything."* Actively misleading. Design in §5.
- **Jargon leak** — *"Net 900 cp in the exchange"* (raw centipawns to a 1200 user).
- **Stale "loses about N pawns"** — 28,987 captions / 3,094 games, but it's **stale data, not a code bug** (generator already removed; re-analysis + lazy-regen self-heal it). The 2 *live* secondary surfaces were fixed (`47f017af`).

---

## 4. played_hangs — wiring diff for your review (DON'T ship blind)

The detector is proven (6 fires / 0 misfires on real FENs; test passes). To wire it into the central caption layer:

**`backend/services/caption_facts.py`** — in `extract_facts`, after the opp-failure block (~line 4858), add:
```python
    # USER played a move that leaves a piece hanging (2026-06-06)
    played_hangs = None
    if mover_is_user is True and cp_loss is not None:
        from services.played_hangs_detector import detect_played_hangs, clause_for
        _h = detect_played_hangs(board_before, played_move, cp_loss=cp_loss)
        if _h:
            played_hangs = _h
```
Then add to the returned facts dict: `"played_hangs_clause": clause_for(played_hangs) if played_hangs else None`.

**`backend/data/captions/R12_blunder.json`** — add a user-side `failure_mode_clauses` entry consuming `{played_hangs_clause}` (mirror the opp-side `failure_mode_clauses_opp` pattern). `caption_rules.py` threads the fact like the opp ones.

**Before shipping:** add the discovered-attack guard (the Be4→Qf4+ limitation — ~2 of 6 fires give a simplistic "no defender" when it's actually a discovery). Either suppress when an origin-ray-walk finds a discovery, or accept the simplistic framing (still better than bare). Your call.

---

## 5. Designs ready to build (data-locked, NOT shipped unattended)

### A. Severity-mismatch guard (CAPTION_BACKLOG #18) — ✅ BUILT + TESTED (`57dd1984`), NOT wired
`backend/services/severity_mismatch_guard.py` + test. `is_severity_mismatch(caption, cp_loss, is_user)` returns True when a user move's caption positively frames a real blunder. Validated: 4 fires / 0 false-fires on a 29-caption control.
**Wiring (your review):** in the V5 render, after the caption is built, if `is_severity_mismatch(caption, cp_loss, is_user)` → suppress the positive caption and fall to an honest `"{move} is a {severity}."` (a why-predicate then fills the reason). Low misfire — correction, not new explanation. **Highest value/risk ratio of the remaining work — recommend wiring first.**

### B. Opp-failure V3 — traded_active_for_inactive (the Nxf7 class) — lock-via-data DONE
**Corpus probe (408 re-analyzed games, the available opp-PV subset):** 2,396 opp mistakes (cp_loss≥100); **456 (19%) are captures**; given-up piece = bishop 116 / knight 92 / queen 85 / pawn 83 / rook 68; **recapture PV present for 444/456**. So the addressable bucket (capture-mistakes by a minor/major with a recapture chain) is ~361/408 games ≈ **~5,800 corpus-wide** once fully re-analyzed.
**Still needs (the hard, high-risk part):** the active/inactive piece *classifier* — what makes a piece "active" (off home rank? attacks enemy half? mobility count?). This must be locked on the activity distribution, then the predicate fires only on the "gave up active, kept inactive" slice + punishable-by-user gate. **Recommend building WITH review — it's the highest-misfire predicate; data substrate is ready, classifier is not.**

### C. Opp-failure V4 — quiet_when_threatened
Opp had a piece under attack, played a non-defending move, engine best was the defense, threat is punishable-by-user. Concrete gating needed; ~part of the 52.

---

## 6. Feedback acknowledge — current state
- Pending **395 → 323** (62 acknowledged + 125 valid). All auto-acks tagged `reviewed_by: claude_batch_audit_2026-06-06`, reversible by status flip.
- Conservative bar held: only override-exists or strong position-specific why. Re-ran with the fixed heuristic (caught under-acknowledged "winning your pawn"-type captions).
- Remaining 323 = the genuine backlog (the bare buckets above + non-game feedback). They clear as predicates ship + queue drains.

## 7. Queue
- Re-analysis pending ~539 and dropping (3 workers, the safe count for the 4-core shared box). Drains on its own — no action. As games re-render at v110, more bare captions self-resolve and more feedback becomes acknowledgeable.

## 8. Decisions waiting on you
1. **Wire played_hangs?** (with or without the discovered-attack guard)
2. **Build severity-mismatch guard?** (recommended — highest value/risk ratio)
3. **Opp V3/V4** — want the active/inactive corpus lock-via-data probe run first?
4. Deploy timing (runbook in §2).
