# Scope — Verified Detector Loop

*Feature name:* `verified_detector_loop`
*Status:* **LOCKED 2026-06-11** — all 4 open questions resolved (Q1 by code review; Q2/Q3/Q4 by Mohit). Building.
*Created:* 2026-06-11

---

## 0. Existing surfaces audit (EXTEND)

**What already touches this need:**

- **`services/caption_facts.py` + `caption_pipeline.py`** already compute structured *facts* per move, then render a template. The verifier inserts a new step **between fact-compute and render**: check each why-fact against engine truth before it's allowed to render. EXTEND, not rebuild.
- **`services/narrator_fallback.py`** (built 2026-06-11) already does abstain→Claude, but gated *crudely* (rule-name list + a filler regex). The verifier **replaces that crude gate** with engine-grounded claim-checking — the proper version of the same idea.
- **`services/severity_mismatch_guard.py`** is a primitive partial verifier (catches "positive line on a blunder"). The new verifier **generalizes and subsumes** it.
- **`authored_caption_overrides`** (human-written captions) — separate, and still win over everything.
- **`.claude/skills/teach-detectors-from-gold`** — the offline improvement loop. The abstention log this scope produces is its input.
- We already **store** the engine ground truth per move (`best_move`, `pv_after_played`, `pv_after_best`, `eval_before/after`). The verifier uses this — **no new Stockfish calls.**

**Decision: EXTEND.** A verify step in the existing fact→render flow + an abstention log + the offline improvement session. No parallel system.

---

## 1. What it is

A truth-check that sits in front of every caption, whether a detector or Claude wrote it. Before any "why" reaches the user, the system checks each concrete claim in it — *"does the rook really attack e3?", "does this piece really hang?", "is that really the engine's best move?"* — against the actual board and the engine line we already stored.

The rule is absolute: **a caption ships only if its claims check out. If they don't, the writer stays silent and hands the move to the next writer.** A detector that can't produce a verified why doesn't guess or pad with filler — it *abstains*, and Claude writes it instead. Claude's output is checked the same way, so a hallucination from Claude is caught too.

Every time a detector abstains and Claude steps in, we **log it** — the position plus Claude's gold caption. That log is the to-do list and the training data for building the next detector. So the system starts leaning on Claude, and gets cheaper and more accurate on its own as detectors are trained from the log. The end state: a detector is never *wrong* — it's either *right* or *silent*.

## 2. What the user sees

No new screen. Same caption slot. The difference is **no caption a user reads is ever an unverified claim.** Behaviour, by case:

```
MOVE Re1 (inaccuracy)
  Detector claims "threatens the bishop on e3"
  -> VERIFIER: does e1-rook attack e3? NO  -> claim rejected -> detector ABSTAINS
  -> Claude writes: "Re1 lets the bishop jump to f2, hitting your rook and knight."
  -> VERIFIER: does Bf2 attack e1 and g1? YES -> ships.   [logged: build a detector here]

MOVE Qe2 (mistake) — a defender moved, d4 now hangs
  Detector claims "Qe2 leaves d4 hanging - your queen was its only defender"
  -> VERIFIER: pre-move defenders of d4 = {Qd1}; post-move = {}; engine line wins d4? YES
  -> ships, FREE, no Claude call.   [verified detector hit]

MOVE Be6 (inaccuracy) — detector has no real reason
  Detector would fall to filler "5 of your pieces are on your side"
  -> filler is not a verifiable why -> detector ABSTAINS -> Claude writes the real why.
                                                          [logged: build a detector here]
```

**The pipeline (the product contract):**
```
move -> detector computes why-facts -> VERIFIER checks each vs engine truth
   any fact verifies      -> render it           (free, instant, RIGHT)
   none verify / filler    -> ABSTAIN -> Claude  -> VERIFIER checks Claude
                                                     verified -> ship  (~gold quality)
                                                     fails    -> retry once, else honest minimal line
   every abstention -> LOG {fen, move, engine facts, gold caption}  (training queue)
```

## 3. In scope (V1)

- **A verifier module** with one checker per concrete claim-type, using python-chess + the stored engine line (no new Stockfish):
  - `attacks_square` — moved/named piece's attack-set contains the target square on the post-move board.
  - `piece_hangs` — attackers > defenders on the square *accounting for pins/x-rays/overload*, AND the stored engine line actually wins it.
  - `wins_material` — eval swing matches the claimed material.
  - `is_engine_best` — the recommended move equals the stored `best_move`.
  - `allows_tactic` (fork/skewer) — the named tactic exists on the post-move board AND the engine line confirms the gain.
- **Facts-before-prose rule:** detectors emit structured why-facts; the verifier passes/drops each; render only verified facts. **No why-fact verifies → abstain.**
- **Filler ban:** board-state / piece-count / generic-principle clauses are never accepted as a *why* (they route to abstain).
- **Narrator output runs through the same verifier** (catch Claude hallucination; one retry on failure).
- **Abstention log** (`caption_abstentions` collection or file): every abstention records `{game_id, move_number, move_san, fen, engine facts, narrator caption, timestamp}`.
- **Wire into the existing flow** (`caption_pipeline` / `game_decryption_v5_service` between fact-compute and render); replaces the crude `narrator_fallback.needs_narrator` regex gate.
- **Measure:** verified-wrong rate (target 0), close-to-gold (target ≥85%), abstention rate, narrator-call count.

## 4. Explicitly out of scope (V1)

- **The offline detector-improvement session itself** (mining the log → building new predicates). V1 produces the log and the loop; the *consuming* session is the next, separate scope (uses `/teach-detectors-from-gold`).
- **New why-detectors beyond what exists** — V1 makes the *current* detectors honest (verify-or-abstain) + the narrator safety net. Growing detector coverage is the offline session's job.
- **Live (synchronous-at-user-time) narration** — captions stay generated-at-analysis-time + stored. No change to the live read path.
- **Async/queue infrastructure for the narrator** — batch-sync + circuit-breaker + cache (already built) is sufficient since generation is batch.
- **PWC** — separate engine, separate scope.

## 5. Success criteria

- **Verified-wrong rate = 0** on a re-render of the 500-move set: zero shipped captions contain a claim the verifier would reject. (The whole point — no more confident lies.)
- **Close-to-gold ≥ 85%** (MEASURED by the judge, not projected) on the 500-move set with verified-detectors + narrator.
- **Abstention log captures 100%** of narrator calls with position + gold (so the offline session has complete training data).
- **Narrator-call rate is measured and is the baseline to drive down** in subsequent detector-training rounds (e.g. "V1: Claude wrote N% of captions; target each round to lower it with verified detectors").
- No regression: every move that already had a verified-correct detector caption keeps it.

## 6. Open questions — ALL RESOLVED 2026-06-11

- **Q1 (RESOLVED, by code review — not asked of Mohit):** Detectors **already** expose structured why-facts. `caption_facts.extract_primary_reason(facts)` returns `{category, ref_field, priority_level}`; `ref_field` points to the exact evidence in the facts dict (`mate_threat_evidence`, `multi_target_attack_evidence`, `discovered_attack_evidence`[target_value_cp], `threats_created`[see_cp], `aligned_pieces_evidence`[rear_piece_value_cp], `captured_piece_type`, `material_delta_played_cp`, `is_castling`…). There is already a primitive verifier — the `_tactic_ok` gate (`cp_loss < MAX_CP_LOSS_FOR_TACTIC_CELEBRATION`) blocking tactic/material/king-safety celebration on flagged moves. **The verifier EXTENDS this: one engine-PV-grounded check per category, hooked onto `extract_primary_reason`. No new fact layer.**

- **Q2 (RESOLVED — agreed):** `piece_hangs` (and material/tactic claims) are verified by the **stored engine PV as arbiter** — the claim holds only if the engine line *actually wins the material*, NOT by a static attacker/defender count. Mohit's refinement: the win may come *via a tactic*, not just a simple hang — so the check is "does the engine line win the claimed material," which correctly accepts tactical wins, not only undefended captures.

- **Q3 (RESOLVED — file):** Abstention log is a **file** (e.g. `backend/data/caption_abstentions.jsonl`), not Mongo — more robust given tunnel flakiness, and the offline session reads it directly.

- **Q4 (RESOLVED — hold + flag, for testing):** When Claude's output also fails the verifier (after one retry), **do NOT ship anything** — **hold** the move (no caption) and **write the move to a flag file** (`backend/data/caption_held_moves.jsonl`) so it can be re-run. (Testing posture; revisit a minimal-honest-line fallback before production.)

## 7. Pre-code requirements

- [ ] The §2 pipeline + the per-claim verifier checks are signed off as the contract.
- [ ] The claim-type list (and each one's exact engine/board check) is reviewed — especially `piece_hangs` using the PV as arbiter.
- [ ] Abstention-log location decided (Mongo vs file).
- [ ] Narrator-double-failure behaviour decided (Open Q4).
- [ ] The 500-move set is the locked verification/regression fixture.
- [ ] `/audit-pre-code` run.
- [ ] **Mohit has explicitly signed off on this scope document.**
