# Caption Coverage (Never-Silence) — Scope

*Created 2026-06-18, reframed 2026-06-19 after Mohit reviewed the 5-game comparison
table. Was "silence elimination"; now centered on **coverage as a first-class metric**.
Scope-Driven Development: this is the signed direction. Parent:
[why_now_coach_layer_scope.md](why_now_coach_layer_scope.md).*

## North star (Mohit, 2026-06-19)
**Every move teaches something. A mediocre caption beats silence for a learning product.**
Coverage is a business metric, co-equal with quality — they are related but NOT the same
problem. The most visible weakness in the comparison wasn't detector quality; it was the
learner repeatedly hitting `(silent — nothing shown)`.

Locked metrics (fresh re-render, `fresh_render_compare.py`):
- coverage (system teaches) **~69% → target 98%**
- quality may dip **~7 → ~6.5** during the coverage push, then recovered by the selector (P2).
- per-tier **verified-truth = 100%** — never-silence must NOT mean shipping a false claim.

## The three tiers (binary detector→caption / else→silence is the bug)
Today it's `detector fires → caption`, else silence. Replace with three tiers, **all
deterministic, all board-verified, NO runtime LLM** (the `narrator_fallback.py` Claude path
stays only as a narrow batch-time enrichment for flagged user-mistakes — it is NOT the
coverage mechanism: it's per-move LLM cost and user-mistakes-only):

- **Tier 1 — Strong teaching.** A real, transferable lesson. *"Qxc4 wins a free pawn. Always
  check for undefended pieces before a quiet move."* Detectors + selector.
- **Tier 2 — Move explanation.** No lesson; explain what the move DOES, from facts we already
  compute. *"Nc6 develops your knight and brings another piece into the game."*
- **Tier 3 — Fallback (never silence).** When nothing interesting, still say something TRUE by
  construction. *"Be7 moves the bishop to safety and keeps your position solid." / "The position
  stays about level after this move."* A small set of **verified micro-templates** chosen by
  what's checkable (bishop-to-safety only if e7 isn't attacked after; "about level" only if
  |eval| small). If somehow none verify, the most generic always-true ("a quiet developing
  move") — but it is gated on truth, never freeform filler.

**Reconciliation of last hour's "stay silent" rule:** OVERRIDDEN. Coverage is the goal, so we
never go silent — but the truth bar still binds every tier. Never-silence is achieved by
*verified* Tier-2/3 micro-templates, not by relaxing truth. (Supersedes the strict reading of
`feedback_principle_bank_is_filler`: filler that LIES is still banned; a true, board-anchored
Tier-3 line is coverage, not filler.)

**Render with visual hierarchy** so coverage doesn't cause banner-blindness: Tier-1 prominent,
Tier-3 muted/secondary. Coverage everywhere; emphasis only where there's a real lesson.

## The selector matters more than detector #51 (Qxd5 canonical case)
`1.e4 d5 2.exd5 Qxd5` — system said *"Qxd5 — takes the pawn"* (move narration, learner
learns 0). Gold taught *"early queens get pushed around."* **The system already HAD both facts**
(takes-pawn AND queen-developed-early); the selector picked `CAPTURE` over
`EARLY_QUEEN_DEVELOPMENT`. Not a detector gap — a **selection** gap.

**Selector objective (THE ranking rule):** *If the student remembers exactly ONE thing from
this move a week later, what should it be?* → the transferable concept, not the visible fact.
This is the teaching-score of the locked two-score selector (urgency × teaching, rating-weighted).
Note: even gold over-indexes on engine moves ("Nf6 was cleaner") — we go further than gold:
prefer the **principle** ("queen out early lets him gain time chasing it"), no engine dependency.

## Caption tone & structure rules (from the comparison review)
1. **Undramatic.** Kill "you were already losing / the problem started earlier / this only slows
   the loss." Gold says *"Bf6 is okay, but f5 was more active."* The learner can still learn.
2. **Structure: what happened → why → better-move (optional).** Explain the move PLAYED first;
   don't open with "Play e5 / Play h4." *"You played Bc5, aiming at the kingside. Pushing e4 was
   even stronger because it gained space."*
3. **cp-gate the better-move.** Marginal pref (small cp: Qd7>Qd8, Nc6>Nf6) → **principle/explanation
   only, name no engine move, invent no fake lesson** (*"Qd8 keeps the queen safe; the engine
   preferred Qc7 for activity"* — short, honest). Real mistake (big cp) → name the better move + why.
4. **Eval-state aware** (surfaced in the 25-sample): frame by who's winning. Winning → "convert /
   stay safe"; lost → honest + brief morale. Derivable from eval; without it captions sound
   tone-deaf in decided positions.

## Cross-move memory — the real moat (P3, where we beat Claude)
Claude scores each move in isolation; we see the whole game. Build trackers:
- `missed_free_pawn_tracker`, `missed_tactic_tracker`, `missed_development_tracker`.
- *"You missed the free pawn again." → "You finally took it."* That is **teaching**, not
  evaluation, and Claude structurally cannot do it per-move. Extend `CrossMoveState`
  (caption_pipeline) — no new engine.

## Assets to EXTEND (single-source-of-truth)
- silence point: `caption_renderer.py:45` (`caption=""`, R_FALLBACK_no_primary) — Tier-3 plugs in here.
- `narrator_fallback.py` — keep as batch-time LLM enrichment for flagged user-mistakes ONLY.
- tiers: `caption_classifier` (HIGH/MID/LOW + `classify_freetext`). severity: `severity.py`.
  openings: `opening_book.recognize_opening_from_history`. facts: `caption_facts`.
  state: `CrossMoveState`. No second engine, no parallel detector file.

## Priority order (Mohit)
- **P1 — Eliminate silence.** Tier-2 + Tier-3 deterministic coverage. coverage 69→~98%.
- **P2 — Selector.** "remember one thing" ranking; fixes Qxd5-class (had the fact, said the boring one).
- **P3 — Cross-move memory.** missed_* trackers.

## Acceptance (on `fresh_render_compare.py`)
- coverage ≥ 98%; empty `R_FALLBACK` ~0.
- per-tier verified-truth = 100% (held-out slice); `pwc_coaching_lint` clean.
- selector: on a labeled slice, % of moves where the chosen lesson = gold's chosen lesson goes up
  (the Qxd5-class flips from CAPTURE → EARLY_QUEEN).
- `log()` any residual silence (should be ~0).
