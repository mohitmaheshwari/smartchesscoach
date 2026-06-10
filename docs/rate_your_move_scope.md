# Scope — Rate Your Move

*Feature name:* `rate_your_move`
*Status:* DRAFT — built overnight 2026-06-10 under Mohit's "keep building" mandate. Awaiting morning signoff.
*Parent:* `docs/pwc_premium_coach_scope.md` · *Twin of:* `docs/predict_coach_move_scope.md`

---

## 0. Existing surfaces audit (EXTEND)
- **No existing self-rating mechanic** (grep empty) — genuinely new.
- **The move quality is ALREADY computed:** the V5 interactive feedback returns `user_move_quality`
  (best/good/inaccuracy/mistake/blunder) + a severity, consumed by the frontend (`CoachPlay.jsx:1181/1199`).
- **`PredictMovePanel`** + the `move_predictions` evidence pattern already exist (the twin).
- **Decision: EXTEND.** Rate-your-move reuses the panel style + the evidence-log pattern + the *already-computed*
  quality. It's the **self-mirror** of predict-coach-move and feeds the **same** student-model evidence. Simpler than
  prediction: no Stockfish needed — the answer (the quality) already exists; we just withhold → prompt → reveal.

## 1. What it is
After you make a move, before the coach shows whether it was good or a mistake, PWC sometimes asks **you** to grade it:
"How was that — solid, a slip, or a blunder?" You pick; then it reveals the real verdict + the why. Every grade is
logged as evidence of a core skill: **do you know when you've gone wrong?** (A 900 often doesn't; a 1500 usually does.)
Works from game one, no history needed. Always skippable.

## 2. What the user sees
Same coaching slot, becomes *grade → reveal*:
```
YOUR COACH
──────────────────────────────
You just played Nf6. How was that move?

   [ Good ]      [ Inaccuracy ]      [ Mistake / Blunder ]      ← tap one

  No pressure — this is about training your eye.
```
Reveal (got it):
```
✓ Right — that was a mistake.
It drops the pawn on e5; Black takes for free. Nbd7 held it.
                                                   [ Got it → ]
```
Reveal (missed it — thought it was fine, it was a blunder):
```
Actually, that was a blunder.
Nf6 leaves your knight on d4 hanging — White wins it with c3. Worth a second look next time.
                                                   [ Got it → ]
```

## 3. In scope (V1)
- **`RateMovePanel`** — premium grade-then-reveal component (reuses `PredictMovePanel`'s style; 3 quality buttons).
- **`POST /coach/play/rate-move/log`** — records the guess to the evidence log `move_self_ratings`
  `{session_id, user_id, move_number, fen_before, played_move, options, guessed_quality, actual_quality, correct, rating, ts}`.
  This is the student model's **second input interface** (alongside `move_predictions`). LOG only.
- **Firing (frontend, simple + capped):** fire only when the actual quality is **instructive to self-assess** —
  a real mistake/blunder, or a clearly-best move — and under a per-game cap by band. Never on routine moves.
- **The "answer" reuses the existing `user_move_quality`** — no new engine call.
- **Fail-open:** any problem → the normal quality coaching just shows as today. Overlay can't disrupt the board;
  always resolvable (can't hang).

## 4. Explicitly out of scope (V1) — wires AROUND the core, like its twin
- **Student model logic / conductor / validation** — built later; this LOGS evidence into the same model interface.
- **Grounded-LLM reveal** — V1 reuses the existing deterministic quality coaching (the reveal seam).
- **Predicting the *coach's* move** — that's the twin (`predict_coach_move`), already built.
- **Numeric self-confidence scale / streaks / "rate every move"** — V1 is the 3-bucket grade, fired selectively.

## 5. Success criteria
- Fires only on instructive moves (0 on routine), capped per band; logs a clean `move_self_ratings` row every fire.
- Feels like training the eye, not a pop quiz (felt test, Mohit on deploy).
- Forward-looking (not a V1 gate): rating-accuracy separates a ~900 from a ~1500 — measured later with the twin's data.

## 6. Open questions
- **Firing rule per band** (which qualities + what cap) — eyeball on real games before locking (`/lock-via-data`).
- **3 buckets vs 4** (merge mistake+blunder into one button, or split?) — UX call on deploy.
- **`move_self_ratings` vs reuse `move_predictions`** — separate collection for clarity (decided: separate).

## 7. Pre-code requirements
- [ ] Mohit signoff (morning).
- [ ] Firing rule eyeballed on real games (Open Q1).
- [ ] §2 mockup confirmed.
- [ ] `/audit-pre-code`.
