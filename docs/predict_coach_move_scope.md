# Scope — Predict Coach Move

*Feature name:* `predict_coach_move`
*Status:* DRAFT — awaiting Mohit signoff. No code until signed off.
*Created:* 2026-06-10
*Parent:* `docs/pwc_premium_coach_scope.md` (this is S2's prediction mechanic — the keystone)

---

## 0. Existing surfaces audit (EXTEND)

**What already touches this need:**
- **`EscapeSquaresQuiz`** — a working interactive quiz in PWC: `POST /coach/play/escape-squares/check` (detects a teaching moment → returns quiz data) + `POST /coach/play/escape-squares/answer` (validates the guess) + a frontend quiz component (`EscapeSquaresQuiz.jsx`, state in `CoachPlay.jsx`). This is the exact interaction loop the prediction needs: detect-moment → present → validate.
- **`candidate_moves` rendering** (`CoachPlay.jsx:309-345`) — already draws candidate moves as arrows on the board (Lichess-style) and lets the user click one. Reusable as the prediction's tap-options.
- **`active_teaching_engine._generate_before_coach_move_feedback`** (wired at `coach_play.py:8256`) — already asks *"Can you guess my next move? / What do you think I'll play?"* — but it is **rhetorical**: it asks, drops a hint, and plays. No options, no tap, no validation, no record of the answer.
- **`coach_opponent`** — the coach's move is computed and known **before** it is shown (the reveal already has the answer in hand).
- **`coach_move_coaching` / the coach-move describer** (incl. the just-shipped opening names, `a6bc4a74`) — the existing reveal text.

**Overlap vs. genuine-new:**
- *Overlap (reuse, do NOT rebuild):* the quiz interaction loop (EscapeSquares), the candidate-move arrows/click, the "guess my move?" prompt, the known coach move, the reveal commentary.
- *Genuinely new:* (a) turning the rhetorical question into a **real interactive guess** (tap → reveal → hit/miss); (b) the **evidence log** (every hit/miss stored — the future Theory-of-Player's fuel); (c) the **adaptive firing** (when, and at what difficulty, by rating).

**Decision: EXTEND.** Upgrade the rhetorical "guess my move" into a real interactive prediction, built on the `EscapeSquaresQuiz` pattern + the `candidate_moves` rendering. No parallel system. De-risks the build: the interaction plumbing is proven; the new work is the guess logic + the evidence log.

---

## 1. What it is

When it's the coach's turn, PWC sometimes pauses *before* showing its move and asks the student to guess it — picking from a few candidate moves drawn right on the board. The student taps a guess; PWC then reveals its real move, whether the guess was right, and a one-line why. Every guess — right or wrong — is quietly recorded as a read on what this player can actually see, so PWC begins to *know* the player from their very first game, with no past games needed. It turns a passive "coach plays, you watch" beat into an active "call my move" one — and it's always skippable, never a wall.

## 2. What the user sees

Same coaching slot as the "COACH PLAYED" panel — it just becomes *predict → reveal* instead of *reveal*. The candidate options also appear as tappable arrows on the board (reusing `candidate_moves`).

**The prompt (coach about to move):**
```
YOUR COACH
────────────────────────────────
I'm about to move — what do you think I'll play?

      [ Nc6 ]      [ Bc5 ]      [ d6 ]        ← tap one (also arrows on the board)

  Just a read on what you're seeing — no pressure.
```

**Reveal — correct guess:**
```
YOUR COACH
────────────────────────────────
I played Nc6.   ✓  Nice — you saw it.
In the Italian Game, the knight heads for d4 and eyes e5.
                                              [ My move → ]
```

**Reveal — wrong guess:**
```
YOUR COACH
────────────────────────────────
I played Nc6.   ✗  (you guessed Bc5)
I went for Nc6 — it develops toward the center and fights for d4/e5.
Bc5 isn't wrong, just a different plan.
                                              [ My move → ]
```

**Adaptive by rating (same panel, different firing + difficulty):**
- **~900:** fires often; options are the obvious developing move vs. clearly worse tries. Goal: build the habit of looking.
- **~1500:** fires rarely, only at a real decision point; options are close, non-obvious. Goal: test whether they read the *plan*, not a one-mover.

Routine/forced positions (recaptures, only-moves): **no prompt** — it would be trivial and annoying.

## 3. In scope (V1)

- **Predict-then-reveal panel** — extends the COACH PLAYED panel; reuses the `EscapeSquaresQuiz` interaction shape and the `candidate_moves` arrows/click.
- **`POST /coach/play/predict-move/check`** — given session + position, decides whether a prediction should fire, and if so returns 2–3 candidate options (the coach's real move + 1–2 plausible decoys) **without** revealing which is real.
- **`POST /coach/play/predict-move/answer`** — records the guess; returns hit/miss + the coach's actual move + the reveal text (the existing deterministic coach-move commentary, incl. opening names — **no LLM in V1**).
- **Evidence log = the student model's INPUT INTERFACE** (a wiring point, not a side-table). A `move_predictions`
  collection, append-only + over-captured + forward-compatible: one row per fired prediction
  `{session_id, user_id, move_number, fen_before, options[], coach_move, guessed_move, correct, difficulty,
  user_rating, fired_reason, ts}`. V1 **writes** it; the model (next phase) **reads** it — no migration.
- **Firing decision = a SEAM (the conductor's plug point).** One function
  `should_fire_prediction(session, position) -> {fire, difficulty}` decides whether to fire + at what difficulty.
  V1 fills it with a simple rating-banded rule (frequent+easy <1000, rare+hard 1400+; per-game cap; never on
  routine/forced moves). The conductor later **replaces the rule's body — not the seam or its callers.**
- **Reveal teaching = a SEAM (the narrator's plug point).** `reveal_teaching(facts) -> text` returns the
  why-on-reveal. V1 fills it with the existing deterministic coach-move commentary (incl. opening names); the LLM
  narrator swaps into the same seam once the transport is decided. **No caller changes when it's swapped.**
- **Skippable / non-blocking** — ignoring the prompt and just continuing is fine (like EscapeSquares is optional).
- Passes `backend/scripts/pwc_coaching_lint.py` on all reveal text.

## 4. Explicitly out of scope (V1)

**This feature is the CORE.** The student model and conductor are NOT excluded — they **wire around** this. V1
builds the core **plus the wiring points** so they plug in later with no retrofit (this is the "wire it in at the
right place" rule from the morning). The split is *interfaces in V1, logic next*:

**Logic built in the NEXT phase, wiring into V1's seams (NOT disconnected):**
- **Student model / Theory-of-Player** — its *logic* is gated on the separability proof, but its **input interface
  is V1's `move_predictions` evidence log** (§3). When built, it *reads* that log — no schema migration. (Parent S3.)
- **The conductor** — its *arbitration logic* is later, but **V1's firing decision is a single seam** (§3) the
  conductor drops into. V1 fills that seam with a simple banded rule; the conductor replaces the rule, not the wiring.
  (Parent S4.)
- **Separability/validation analysis** — run on the accumulated evidence log; it's what unlocks building the model's logic.
- **LLM-grounded teaching on reveal** — the reveal text is produced by a seam too (V1 = deterministic commentary);
  the grounded narrator swaps into that seam once the transport is decided.

**Genuinely separate features (not this one):**
- **Rate-your-own-move** (the self-mirror) — its own feature; it will feed the *same* evidence model.
- **Predicting the student's *own* move / "which system are you heading into" doorways.**
- **Hit-rate self-calibration** of difficulty — V1 is rating-banded; per-player calibration is later.
- **"Predict the plan/idea" (non-move) variant** — V1 is move-prediction with rating-scaled decoy difficulty.

## 5. Success criteria

- **Firing is sane (behavior, not vanity):** 0 prompts on routine/forced moves; cadence matches band (e.g. ≤1/game at 1500+, more frequent <1000); per-game cap respected. (Measured on a re-render over real games.)
- **The evidence log is clean and complete:** every fired prediction writes a row with options + guess + correct + rating — the row is the contract for the future model. 0 malformed/missing rows.
- **It feels like a coach, not a quiz (the felt test):** Mohit plays it and the predict→reveal reads as the coach engaging him, not interrupting him.
- **Forward-looking (NOT a V1 gate, but the reason it exists):** once enough rows accumulate, hit-rate on matched-difficulty predictions separates a ~900 from a ~1500. This is measured later (parent S3); V1 just produces the data.

## 6. Open questions

- **Question:** How are the 2–3 options (real move + decoys) generated so they're neither trivial nor silly?
  **Why unresolved:** too-obvious decoys make it trivial; random decoys look dumb; the right decoys are *plausible-but-worse* moves. Reuse the engine's top-N candidates, or generate plausible alternatives?
  **Unblocking step:** small probe — pull the engine's top 3–4 moves on real coach-move positions and eyeball whether they make good options at each band.

- **Question:** What exactly triggers a prediction ("teaching-informative OR diagnostic" position)?
  **Why unresolved:** V1 wants a concrete rule (exclude recaptures/only-moves; prefer decision points), banded by rating.
  **Unblocking step:** define the rule + probe how often it would fire across real games (`/lock-via-data`; needs Mongo on :27018).

- **Question:** What is the `move_predictions` schema, made forward-compatible with the future student model?
  **Why unresolved:** the model (S3) isn't designed yet; the log must not need a migration later.
  **Unblocking step:** 30-min design with the S3 validation signals in mind; keep it append-only and over-capture.

- **Question:** Cold-start — for a user with no/unknown rating, what band drives firing + difficulty?
  **Why unresolved:** the firing rule is rating-banded; a brand-new user may have no rating.
  **Unblocking step:** default to a mid band; the data itself calibrates once it accumulates (post-V1).

## 7. Pre-code requirements

- [ ] **Mohit has explicitly signed off on this scope document.**
- [ ] The §2 mockup is signed off as the product contract.
- [ ] Decoy-generation approach decided (Open Q1) — after the candidate-move probe.
- [ ] Firing-trigger rule defined + its fire-rate eyeballed on real games (Open Q2; `/lock-via-data`).
- [ ] `move_predictions` schema decided, forward-compatible with the student model (Open Q3).
- [ ] Mongo on :27018 reachable from a probe context (the firing-rate + decoy probes must run).
- [ ] `/audit-pre-code` run.
