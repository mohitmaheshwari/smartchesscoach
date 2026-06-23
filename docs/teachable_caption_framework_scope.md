# Teachable Caption Framework — Scope

*Created 2026-06-23. Scope-Driven Development: this is the signed direction (pending Mohit's
sign-off). Parent / sibling docs: [caption_silence_elimination_scope.md](caption_silence_elimination_scope.md),
[why_now_coach_layer_scope.md](why_now_coach_layer_scope.md), [caption_distillation_rollout_scope.md](caption_distillation_rollout_scope.md).
This doc is the architecture layer ABOVE those — they define WHAT a good caption is; this defines
HOW we guarantee every surface produces one.*

## The problem (seen three times now)

Every time a new screen needs a caption, it grows its **own** caption engine. Quality and truth
then exist only where a human hand-fixed that one engine. We have at least three caption surfaces
today and they do not share a brain:

| Surface | Where | Caption engine | Verified? |
|---|---|---|---|
| Game review (V5) | `/game/:id` → GameDecryptionV5 | `build_move_teaching_decision` (the central layer) | Yes — per-FEN verifier runs |
| Play-with-Coach (PWC) | `/play-with-coach` | partly its own (`move_critique`/`coaching_policy`/`coaching_voice`) | Partial |
| Prescribed / puzzle | `/training/prescribed` | `puzzle_miss_coaching.py` + `pv_tactical_analyzer.py` | **No** |

The puzzle surface shipped a **fabricated** caption ("Qxb2 forces the defender to move") on a
position where Qxb2 simply wins an undefended bishop — engine-verified, 2026-06-23. It sailed
through because that surface never calls the central layer and never runs the claim verifier.
This is the recurring single-source-of-truth violation (memory: `single_source_of_truth`,
`one_source_of_truth`, `pwc_second_engine`).

## North star

**Wherever a caption is built — review, PWC, puzzle, or a screen that doesn't exist yet — it is
teachable by construction.** Not "teachable where someone remembered to fix it." A structural
guarantee, enforced by the build, not by vigilance.

## The contract — what "teachable by construction" means

Every user-facing caption, on every surface, satisfies all four:

1. **True.** Every claim passes the per-FEN board verifier (`narrator_claim_verifier`). A claim
   that can't be verified is dropped from the caption — no fabrications, ever.
2. **Never silent.** The tiered fallback (Tier-2 explanation / Tier-3 floor) guarantees a true
   caption always renders. (Inherits `caption_silence_elimination_scope.md`.)
3. **Teaches when derivable.** The four teaching parts — *what was the mistake · why it's bad ·
   the better move · why the better move is better* — attach wherever the board supports them
   (the why-better / why-bad work, 2026-06-23).
4. **Honestly terse otherwise.** Where the why is positional and not deterministically derivable,
   it **abstains** to a true-but-short line rather than inventing. **Abstain is not a failure** —
   it is the truth bar holding.

## The architecture — three structural moves

### Move 1 — One door
`build_move_teaching_decision(MoveInputs, …) → MoveTeachingDecision` is already the central layer
and already powers V5. Make it **the only** way to produce a user-facing caption. Every surface
calls it; nothing assembles caption text on its own.

### Move 2 — The verifier lives *inside* the door
Today the per-FEN claim verifier runs in the V5 *service*, AFTER the central call — so PWC and
puzzle-miss bypass it. Move the verify-then-soften step to be the **final stage inside**
`build_move_teaching_decision`. Result: it becomes physically impossible to emit an unverified
claim from any caller. (The verifier's checker set must cover every claim type any surface can
emit — extend it FIRST when a new claim type is added; distill-skill law.)

### Move 3 — A CI guard makes it stick
A grep-based check that **fails the build** if any file outside the central layer assembles a
user-facing caption (e.g. constructs prose with a SAN + a chess verb, or writes to a known
caption field). Precedent already in the repo: `.githooks/pre-commit` blocks the "cp-loss" phrase,
and `caption_renderer.py` enforces its L1–L4 laws by mechanical grep. This is what stops surface
#4 from quietly reinventing the engine next quarter. Allow an explicit opt-out comment
(`# allow-noncentral-caption`) for audit/test files, same pattern as the existing hook.

## Migration list (the actual work — adapters, not new chess logic)

Both stray surfaces already HAVE the inputs the central layer needs (FEN, played move, best/
solution move, PV, cp_loss). The work is a thin adapter per surface that maps its data →
`MoveInputs`, then routes through the one door.

- [ ] **Puzzle / prescribed** (`puzzle_miss_coaching.py`): build `MoveInputs` from the puzzle
      (fen_before, played_san, best_move_san = solution, pv_after_best, cp_loss), call the central
      layer, render its caption. Retire the bespoke "WHY YOUR MOVE FALLS SHORT / WHY THE BEST MOVE
      WORKS / try it to feel why" templates. *(Highest priority — it's the one shown to fabricate.)*
- [ ] **PWC base narrative**: complete the migration started in `pwc_second_engine` — route the
      always-on per-move narrative through the central layer instead of `move_critique` →
      `coaching_policy` → `coaching_voice`. (Larger; gate behind a flag, diff before/after with
      `snapshot_surface1.py`, present changed captions for sign-off.)
- [ ] **Verifier-inside-the-door** refactor (Move 2) + extend checker coverage for any
      puzzle/PWC-only claim types.
- [ ] **CI guard** (Move 3) + opt-out comment convention + activate in `.githooks`.

## Acceptance / how we'll know it worked

- Re-render every surface fresh; run the per-FEN verifier on 100% of captions → **0 false claims**
  across review + PWC + puzzle (today: V5 ~0, puzzle unmeasured/known-bad).
- The puzzle case from 2026-06-23 now reads true: *"Qxb2 wins the bishop, and the rook on a1 falls
  next — Black wins two pieces."* (double-attack lesson matches the page theme).
- Deleting a surface's bespoke caption code and routing through the door does **not** drop coverage
  (never-silence holds via the central tiers).
- The CI guard fails a deliberately-introduced non-central caption string in a test.

## Explicit non-goals / boundaries (no-yes-man)

- **Not** "every caption becomes a deep lesson." The guarantee is true + never-silent + teaches
  when derivable + abstains honestly. Positional whys still abstain by design.
- **Not** a runtime-LLM path. All of this stays deterministic + board-verified (distillation
  offline only).
- **Not** a one-switch change. It's a small framework + two real per-surface adapter migrations.
  PWC is the larger of the two and ships behind a flag with a before/after diff.
- The CI guard cannot *prove* a caption teaches — only that it went through the one door and the
  verifier. Teaching quality is still measured by the 4-component verifier (`verify_mistake_4parts.py`)
  and human review (Parth), not asserted by the guard.

## Open questions for sign-off

1. Order: puzzle-miss first (small, visibly broken) then PWC (large) — agreed?
2. CI guard strictness: hard-fail the build, or warn-only for a grace period while surfaces migrate?
3. PWC migration is the known big rewrite (`pwc_second_engine`) — fold it into this framework now,
   or land puzzle + the door + the guard first and schedule PWC separately?
