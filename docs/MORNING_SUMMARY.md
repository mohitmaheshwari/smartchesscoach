# Morning Summary — overnight build (night of 2026-06-10)

## TL;DR
Built **two full PWC features end-to-end, both fail-safe** — `predict-coach-move` ("Call My Move") and
`rate-your-move` ("grade your move") — plus regression tests and a corrected thread-B baseline.
**Nothing is runtime-verified** (I can't run React or a live game). Everything needs **one thing: deploy + play.**

```
git pull working-code && docker compose up -d --build    # on the server
```
Then play a PWC game. If a game ever **breaks**, that's the #1 bug — but everything is fail-open, so it
*should* just play normally and the new bits appear only when they fire.

---

## ✅ Check FIRST, in this order
1. **PWC still plays normally.** Prediction + rating are fail-open (no-op until they fire). A broken game = top priority.
2. **Opening names** in the coach panel ("in the Italian Game, the knight heads for d4") — correct + not mislabeled?
3. **"Call My Move"** overlay fires on some coach moves (often for beginners, rarely at 1500) → tap an option → reveal. Feels premium? Ever hang?
4. **"Rate Your Move"** overlay fires on *your* mistakes/blunders → grade Good/Inaccuracy/Mistake-or-Blunder → reveal. Feels good? Ever hang?

---

## What I built tonight

### 1. predict-coach-move — "Call My Move" (the prediction keystone, your morning vision)
Before the coach reveals its move, you guess it from 2–3 options; tap → reveal (✓/✗ + the why). Every guess is
logged — the evidence that (eventually) tells us *what you can see*, from game one.
- **The CORE with wiring seams** (your "wire around this" point): the evidence log `move_predictions` = the
  student model's input; `should_fire()` = the conductor's seam; the reveal = the LLM-narrator's seam. The model
  + conductor wire in later, **gated on validation** — but their sockets are built now.
- **Fail-safe:** `/move` is **100% untouched**; a new isolated `/predict-move/offer` reads the coach's
  already-played move (no recompute), wrapped try/except → no-op on any error; the overlay can't disrupt the
  board and is always resolvable (can't hang).
- **Design locked from data** (448-position probe): fire only when the coach's move is top-3 (71%), per-game cap
  by band (beginner 3 / improver 2 / intermediate 1), decoy difficulty by eval-closeness.
- Commits: `fea74de2` (scope), `8bdde90a` (core, 14/14 tests), `2c84e3d3` (backend), `34e9b192` (panel), `a8cfd97c` (wiring).

### 2. rate-your-move — "grade your move" (the self-mirror)
After you move, before the verdict shows, you grade your own move. Logs whether you were right — the second
student-model signal (do you *know* when you've erred?).
- **Reuses the already-computed `user_move_quality`** — no new engine call. Logs to `move_self_ratings`.
- **Fail-safe:** additive; `/rate-move/log` is log-only + fail-open; the interception withholds the verdict via
  early-return wrapped in try/catch → normal verdict on any error; overlay can't hang.
- Commits: `b55c4bed` (backend, scope + service 10/10 tests + endpoint), `c8b54bca` (frontend panel + wiring).

### 3. Regression tests — `6668904f`
Pure-logic tests for both features (7/7). `python backend/tests/test_predict_rate.py`.

### (earlier today, same branch, also awaiting deploy)
- **Opening names** in the coach panel — `a6bc4a74` (reliable detector; never mislabels — unknown lines stay unnamed).
- **Caption tools** — `893e2fc4` (offline authoring harness) + `0839bbc3` (Lab before/after fixture).

---

## Thread-B finding (the caption fix — `fact_templated_captions`)
Read-only baseline on the **real** rendered captions (`decryption_v5_data[].caption`, ~400 games):
- **~44%** of flagged-mistake captions have a position-specific why; **~55% bare/filler** (rough — heuristic noise,
  so true bare-rate is likely a bit under 55%).
- Failure modes: *"X is a mistake, Y better"* + a generic principle (filler), and vague *"out alone / in trouble"*.
- (I first measured 98% off the **wrong field** — `decryption_data`, the shallow one — and caught it. The real
  field is `decryption_v5_data[].caption`. The end-to-end-trace discipline did its job.)
- **Your prompt (the verified caption engine) targets exactly these.** This baseline is the success-criteria yardstick.

---

## ⏳ Awaiting you (decisions / signoffs)
- **Sign off (or redline) 3 scopes:** `predict_coach_move`, `rate_your_move`, `fact_templated_captions`.
- **LLM production transport** — `ANTHROPIC_API_KEY` vs the ngrok gateway + rails. Gates the LLM-grounded
  reveal (the prediction/rating reveal seam) and the live caption narrator. Not blocking what's built (all
  deterministic V1), but the next quality step.

## 🚩 Flagged — NOT built (need a morning design pass; not fail-safe to build blind)
- **takeback ("try that again")** — needs move-flow rewind/retry. *Safe design sketch:* a **local practice retry**
  (reset the board to the pre-blunder FEN, let you re-drag, evaluate via the existing `/evaluate`) that does **not**
  un-do the live game. Buildable fail-safe once you confirm that UX.
- **recall ("you did this before")** — depends on `cognitive_gap` accuracy, which the memory flags as questionable
  (detection ~2%). Validate the data first, or it surfaces confidently-wrong recalls.

## Watch-items / known caveats
- Frontend interceptions (poll for prediction; `fetchInteractiveCoaching` for rating) are fail-open but
  **unvalidated** — watch: does the board hold then reveal cleanly, any flash, any hang.
- Prediction multi-PV adds ~0.4s on *fire-candidate* coach moves (fine for testing).
- Rate-your-move cap is a flat **3/game** (V1) — tune by band later.
- The model + conductor only become buildable once **prediction/rating data accumulates from real play** — so
  playing tonight's features is also what unlocks validating the student model.

---

*Everything is on `working-code`, reversible, and fail-open. The honest line: I built the hard, get-it-right-once
logic + verified it as far as is possible without running the app; the live feel is yours to confirm. If something's
off, it's tunable, not structural — `/move` and the core game flow were never touched.*
