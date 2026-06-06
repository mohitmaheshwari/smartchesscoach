# Morning Summary — overnight work 2026-06-06 (Mohit away ~15h)

**TL;DR:** commits on `working-code`, **none deployed**. Metadata fix + PWC flag = clean, ship them. **⚠️ READ §0 FIRST** — a late-night verification found that 2 of my 3 caption detectors DUPLICATE existing machinery, and the real bare-caption problem is stale renders, not missing predicates. Feedback pending 395→312 (cleared, ongoing). Queue draining on its own.

---

## 0. ⚠️ IMPORTANT CORRECTION (verify-before-build failure — my mistake)

Late in the night I finally grepped the existing caption layer (should have done this FIRST). Findings:

- **The user-side why machinery is already rich**: `failure_hangs_piece` ("leaves your {piece} on {square} undefended"), `is_exchange_losing`, `why_user_missed_mate` ("led to mate in N"), `missed_tactic_kind`, `missed_capture_target_piece/square` (v100+), ~17 best-move detectors, + the v104 principle-bank floor.
- **Therefore my `played_hangs_detector` (≈ `failure_hangs_piece`) and `missed_mate_detector` (≈ `why_user_missed_mate`) are REDUNDANT. Do NOT wire them.** They were an avoidable build — I didn't check the existing system first (violates [[feedback_check_for_existing_ui_before_building_offline]]).
- **The 27k user + 32k opp "bare" captions are predominantly STALE pre-v100/v110 renders** — the machinery existed but those games were rendered before it. **Re-analysis (the draining queue) is the fix, not new predicates.** Same pattern as the "loses about N pawns" stale data.

**Revised real work (much smaller than the 59k suggested):**
1. **Let the queue drain** — it clears the stale bare renders. (Main fix, already running.)
2. **Investigate the genuine gap**: re-render a handful of bare games at v110 — if they're STILL bare after v110, that's a real coverage gap (e.g. `pieces_now_undefended_present` not firing on some hangs). That's the targeted work, not new detectors.
3. **`severity_mismatch_guard`** (`57dd1984`) — *likely still net-new*: it guards POSITIVE captions on blunders ("King is safe" on cp_loss 698), which come from a non-R12 positive-move path the existing severity machinery doesn't cover. **Verify where that positive caption originates before wiring**, but this one is probably worth keeping.
4. **Opp V3/V4** — the opp-failure framework IS newer/less-covered, so these remain the most likely genuine additions (V4 detector `5f72086f` v0.1, data-locked designs in §5).

**Net:** keep metadata fix + PWC flag (clean). Treat played_hangs/missed_mate as throwaway learning. Focus on queue-drain + the v110-still-bare investigation + opp V3/V4.

---

---

## 1. What I committed (all pushed to `working-code`, NOT deployed)

| Commit | What | Risk | Deploy |
|---|---|---|---|
| `571d6586` | **Metadata fix** — canonical opponent/white/black + date_played in sync + backfill script | Low (isolated to import path) | safe |
| `3416b4f8` | **PWC telemetry flag** in docker-compose (starts Phase-3 soak; shadow-only) | Low (env-only, no user-facing change) | safe |
| `663fd63b` | **played_hangs_detector** — standalone, tested, **NOT wired** | None (nothing calls it yet) | n/a until wired |
| `57dd1984` | **severity_mismatch_guard** — standalone, tested (4 fires/0 false), **NOT wired** | None (nothing calls it yet) | n/a until wired |
| `5f72086f` | **opp_quiet_threat_detector v0.1** — opp left a piece hanging (154 fires/408g), **NEEDS REVIEW** (gate caveat) | None (nothing calls it yet) | n/a until wired |
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

## 3b. FULL-CORPUS scale of the why-gap (2026-06-07, all 6,610 games)

The flagged 511 was a sample. Scanning every game's stored captions for bare mistakes (cp_loss≥100, no position-specific why):

| | count |
|---|---|
| **USER bare mistakes** | **27,381** |
| **OPP bare mistakes** | **32,198** |

User failure-mode distribution → **prioritized addressable buckets**:
| bucket | N | covered by |
|---|---|---|
| mid_loss_other (100-300cp) | 13,043 | hard — positional drift, often no sharp why |
| big_loss_other (≥300cp) | 6,112 | many are **played_HANGS** (my detector) / discoveries my cheap classifier missed |
| missed_capture (trade) | 3,415 | extend missed_capture predicate |
| missed_check | 2,305 | missed-forcing predicate |
| **missed_FREE_capture** | **1,995** | ⚠️ v110 missed_capture predicate SHOULD cover these — **investigate** (stale pre-v110 renders, or a predicate gap) |
| **missed_MATE** | **511** | ✅ `missed_mate_detector` (`f2cd22e8`, tested) |

**Caveats:** (1) This is an UPPER bound — many are stale pre-v110 renders that re-analysis is actively replacing (same mechanism as the "loses about N pawns" stale data). It shrinks as the queue drains. (2) The 1,995 still-bare missed_FREE_captures are the most actionable anomaly — if they're at v110 and still bare, the missed_capture predicate has a coverage gap worth a focused look.

**Takeaway for prioritizing the build:** wiring `played_hangs` + `missed_mate` + investigating the missed_FREE_capture gap addresses a large, clean slice; the opp buckets (V3/V4) are the other half; `mid_loss_other` is the long-tail hard part.

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

### C. Opp-failure V4 — quiet_when_threatened — lock-via-data DONE
**Corpus probe (same 408 games):** of 2,397 opp mistakes (cp_loss≥100), **571 (23%) IGNORED a pre-existing threat** — a winnable opp piece existed before the move and *survived* it (e.g. Qf6 cpl=288 left bishop on g3; Qxd5 cpl=242 left bishop on h3). Reuses `played_hangs_detector._winnable_squares`. Scales to ~9,300 corpus-wide.
**This is the UPPER bound** — tighten with gates before shipping: (1) ignored piece is a minor/major (not an incidental pawn — pawn cases are noisy), (2) `best_move` actually addresses the threat, (3) the user can punish on their move. **Build WITH review** (shares V3's misfire risk); data substrate + the winnable-square primitive are ready.

### Opp V3+V4 coverage note
Together V3 (19% captures) + V4 (23% ignored-threat) address ~40% of opp mistakes — the bulk of the ~52 opp-move bare bucket and ~15k corpus-wide. The detection primitives exist + are tested (`played_hangs_detector`); the remaining work is the activity classifier (V3) + the 3 gates (V4), both review-gated.

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
