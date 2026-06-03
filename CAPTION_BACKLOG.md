# Caption Backlog — Filed for Future

Items investigated during caption-quality passes that are intentionally deferred. Each has a concrete design sketch; each was filed because the evidence base is one flag (or the fix would create broader noise on routine moves). When a second flag of the same shape arrives, design from the concrete examples.

Do not pre-build any of these on a single flag — that violates [[feedback_build_detectors_on_first_approval]]'s sibling principle: build the detector when an approved caption-rewrite gives you a concrete template, not when a single flag gives you a hypothesis.

See also: [CLAUDE.md](CLAUDE.md), `backend/services/caption_pipeline.py` (central layer), `backend/data/captions/` (R-rule definitions).

---

## 1. Sac-aware R12 why-clauses — extension

**Status:** Partial coverage shipped 2026-05-28. Existing: `best_move_is_sacrifice` / `best_move_sac_near_king` for missed-capture variants.

**Extension scope:**
- User played a non-capture while a sacrifice existed (best move is a piece sac the user didn't see).
- User played the *wrong* sacrifice (a real sac was best, user played a different but still-losing one).

**Why filed:** existing case covered the only flag we have. Wait for ≥2 examples of the extension before designing why-clauses — different sac patterns (clearance sac, deflection sac, king-attack sac) likely need different framings.

---

## 2. "Why played wrong" fact + variant

**Status:** Spec written 2026-06-02 → [docs/why_played_wrong_spec.md](docs/why_played_wrong_spec.md). Awaiting Mohit sign-off. Triggered by feedback batch fb_3efccdbbf15e / fb_3d530eea5dd9 / fb_1cd7562468d1 / fb_79c33cd39b67 (2026-06-01).

**Scope:** two-clause caption — "X walks-into-Y. Z was better — Z-does-W." Each clause grounded in a concrete fact (failure-mode for played, alternative-promotion for best). When only one side has a fact, render single-clause; when neither, stay silent.

**Why filed:** the default direction (silent on near-best) is right per [[no-hollow-coverage]]. This is the opposite-direction addition that fires *only* when both moves are same-piece + same-category + one has a strictly-more-positive signal. Gating must be airtight or it degrades to "could be better" generic template noise. Needs ≥2 concrete approved rewrites to anchor the variant text.

**Prior attempt:** the 2026-06-01 predicate reorder (commit `72f21dfe`, reverted in `b0694980`) showed why this needs the bigger system — reordering alone produces non-sequitur wrappings ("h4 was better — your bishop is under attack") and doesn't cover failure modes that aren't in the existing fact set (m24 Qb8 walking into Nb7 fork on the queen, not the played piece). See the spec doc for the full architecture.

---

## 3. Marginal-cp_loss framing in already-losing positions

**Status:** Investigated 2026-05-28. False alarm.

**Finding:** fb_953fc16dd8f9 turned out to be a balanced position (eval +73 for black, well above the -200cp losing threshold), not losing. R12's existing softening already covers genuine losing positions.

**Why still filed:** if a real "marginal cpl in losing" example does arrive, the design needs a fresh anchor — don't reuse fb_953fc16dd8f9 as the example.

---

## 4. Long-range central-control detector (queen/rook lifts)

**Status:** Investigated 2026-05-28. No clean fix at current detector granularity.

**Flag:** fb_fa464cae3b84 — Qd8 played (cpl=27), Parth's claim: Qc7 would have been better ("controls f4, connects rooks faster").

**Probe results:**
- `good_move_reason` for Qc7 = `None`; caption = `''`
- Qc7 newly attacks **only f4** (Qa5 already covered d5/e5/f3/f5/c5)
- Below `controls_key_squares` piece threshold of 2
- "Connects rooks faster" is incorrect for both Qc7 and Qd8 (back rank: Nb8/Bc8/Ke8/Bf8/Ng8 — neither move clears it)

**Why filed, not fixed:**
- Lowering `controls_key_squares` to 1 would caption every routine queen/rook shuffle that grazes a central square — broad noise.
- Building a new "long-range central control" detector now means designing off one flag.

**Future design sketch:** detector would need (a) the moving piece to be queen/rook, (b) the move to be a relocation (not initial development), (c) the newly-controlled key square to be defended by ≥2 of the mover's pieces afterward (i.e. an actual outpost-prep signal, not just "grazes square once"). Wait for a second flag.

---

## 5. London System Bf4-before-e3 position detector

**Status:** Removed the misclassified `London Move Order` entry from `traps.json` 2026-05-28 (it had `setup_moves: ["d4", "d5"]` and was firing on every d4-d5 opening, including Queen's Gambit / Slav / QGD where the London advice doesn't apply).

**Real teaching to preserve:** in the London System, playing e3 with the c1 bishop still on c1 traps the dark-squared bishop behind the pawn chain. The chess principle is right; it just isn't a "trap" in the move-sequence sense.

**Future design sketch:** position-based detector in `opening_curriculum_engine` — fires when (a) white has played d4 + at least one queenside-system marker (Nf3 / Bf4 / c4), (b) white is about to play e3 OR just played e3, and (c) the c1 bishop is still on c1. Lives in curriculum, not traps. Renders as a curriculum tip, not a `trap_setup` caption.

---

## 6. Moved-piece-was-sole-defender → target now hangs

**Status:** Example #1 anchored 2026-06-03 → `fb_ec0098264c8e` (game `1780f8bc-31c2-490b-a6f4-6bb62f4c8fff`, move 9 Qe2).

**Flag:** White's Qd1 was the sole defender of d4. After 9.Qe2 the d4 pawn hangs to Qxd4 cleanly, and the centralized black queen also threatens the undefended Bf4. cp_loss=174 (mistake severity, eval +30 → -144). Caption rendered: *"Qe2 is a mistake. O-O was better."* User: "why??"

**Approved override (~45 words, principle ending):**

> Qe2 just leaves d4 hanging — your queen was the only piece defending it, so now Qxd4 grabs the pawn for free and also hits Bf4. O-O does the same king-safety job without abandoning d4. Before moving any defender, count what depends on it.

**Predicate sketch (`played_piece_was_sole_defender_of_attacked_target`):**
- Played piece X moves from origin square S₀ to S₁
- There exists a square S_target attacked by ≥1 enemy piece BEFORE the move
- Pre-move defenders of S_target = `{X}` (sole defender)
- Post-move defenders of S_target = `{}` (empty)
- S_target holds a piece/pawn of meaningful value (≥1 pawn)

When fact fires → R12 failure_mode_clause: *"{played} just leaves {target_square} hanging — your {played_piece_type} was the only piece defending it."*

**Why filed, not built today:**
- This is example #1. Per the ≥2-before-designing rule, wait for a second instance.
- Likely needs to fire on mistake severity (not just blunder); current R12 failure-mode clauses may be gated `severity=blunder` only — verify before promotion.
- Suspect [feedback_fix_framing_not_detection.md] applies: the engine detection is fine (cp_loss=174 is correctly flagged), only the caption framing needs the explicit-why predicate.

---

*Last updated: 2026-06-03*
