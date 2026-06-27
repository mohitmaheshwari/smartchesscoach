# Coach Blunder Guard — Scope

**Status:** awaiting sign-off (no code until Mohit signs)
**Owner:** Mohit · **Date:** 2026-06-27
**Philosophy chosen:** **B** — a hard floor against free material hangs at *every* level, with calibrated teaching-mistakes allowed above the floor.

---

## The problem (data-grounded, 2026-06-27)

The coach opponent weakens via Stockfish **Skill Level / UCI_Elo** ([coach_opponent.py:170](../backend/coach_play/coach_opponent.py#L170)). There is **no soundness floor** — whatever the weakened engine returns is played. Stockfish's weakening works by *randomly* injecting bad moves, and "bad" sometimes means **hanging a queen** — which no human 800–1500 does in a quiet position. A coach that hangs its queen instantly loses the student's trust (Mohit, 2026-06-27: "if a coach does blunder, student right away lose their trust").

Measured hang-rate (50 real middlegame positions, weakened engine moves, strong engine grades cp_loss):

| Coach Skill | hangs material (≥300cp) | catastrophe (≥900cp, ~queen) |
|---|---|---|
| 0 (~800) | **8%** | yes (a `Qxe5`, 9983cp) |
| 5 (~1200) | **2%** | rare but real (live `Qxf6` case) |
| 10 (~1600) | 0% | 0 |

Two findings: (1) the problem is **real**; (2) it's **worst at the lowest levels** — beginners get the most queen-hanging coach, the exact inverse of who can least afford it. Above ~Skill 10 the engine is already sound.

The live trigger that prompted this: in session `981c107d` the coach played `Qxf6` (recapture with the queen instead of `gxf6`), hanging it to `Bxf6` — engine swing −3.5 → −6.0. The sidebar then **praised** it as "Good — Double Attack." Two bugs: the coach hung material, and the caption lied about it.

---

## What it WILL be (plain English)

When the coach is about to move, if its chosen move **hands the student free material in one move** (a hang the student can just take), the coach **won't play it** — it quietly picks a sound move instead. The coach still plays below the student's level and is still beatable — it just loses by being *outplayed* or by leaving *deeper* tactics for the student to find, never by dropping a piece for nothing.

And the coach's move narration will **never praise a move that hangs material**. If the coach makes a (calibrated, allowed) mistake, the caption is honest about it — never "Good — Double Attack" on a queen give-away.

### What's allowed above the floor (philosophy B)
- Dropping a **pawn** (a teachable "can you win the pawn?" moment).
- Leaving a **2+ move tactic** the student must actually calculate (not a one-move freebie).
- General positional inaccuracy / passivity (the normal weak-play texture).

### What's blocked (the hard floor, all levels)
- Any move after which the opponent has a **one-move capture winning ≥ a minor piece** (SEE ≥ ~300cp) with no compensation — i.e. a free hang of a piece, rook, or queen.

---

## Mechanism

A guard layered on top of the existing weakened move selection — **no change to how strength is set**, only a soundness floor on top:

1. Weakened engine proposes its move (unchanged — this is the "human-level" choice).
2. **Static one-move SEE scan** (free, no extra engine call): after the proposed move, compute the opponent's best Static-Exchange-Eval capture across all squares. If it wins ≥ FLOOR cp → the move hangs material.
3. If it hangs → **resample**: take the engine's top-N candidate moves (moderate depth), filter out the SEE-hangers, and play the weakest *sound* candidate (keeps the coach weak but not self-destructing). If every candidate hangs (rare, forced), play the least-bad.

Why SEE-one-move (not an eval-drop check): it draws the line exactly where philosophy B wants it — *one-move free hangs* are blocked, *deeper tactics and pawn-drops* pass through. It's also static (zero added latency), which matters on the live move path.

### Honest-caption layer (the bug you caught)
The coach-move narrator (R17 / double-attack teaching moment) must verify the moved piece is **safe on its landing square** (SEE ≥ 0) before calling a move a "Good" double-attack / fork. A fork whose own piece is hanging is not a tactic — narrate it honestly or stay silent.

---

## Thresholds (to be data-locked, not guessed)

- **FLOOR = 300cp** (a minor piece) is the working hypothesis — block one-move hangs of a piece or more, allow pawn-drops. To be confirmed by re-running the measurement with candidate floors {200, 300} and reading the resulting hang-rate + beatability curve before locking. ([[feedback_threshold_before_distribution_is_sin]])
- Resample candidate pool size N and "weakest sound candidate" selection: tuned so post-guard strength ≈ pre-guard strength minus the hangs (i.e. we remove blunders without making the coach noticeably stronger).

---

## Acceptance (how we prove it works)

Re-run the same measurement harness **with the guard on**, at Skill 0 / 5 / 10:
1. **Hang-rate (≥300cp) → ~0%** at every level. **Catastrophe (≥900cp) → exactly 0.** (Primary bar.)
2. **Beatability preserved:** the guard fires only on the ~2–8% of moves that would have hung; overall coach strength (avg cp_loss vs best across a game) stays within a small delta of pre-guard — it must NOT play like full-strength Stockfish. Verify by win-rate / avg-accuracy on replayed games staying in the target band.
3. **No latency regression** on the live move path (SEE is static; confirm the resample only triggers on the small blunder fraction).
4. **Caption honesty:** the double-attack/fork narrator no longer praises a hanging-piece move — verified on the `Qxf6` FEN + a sweep of coach-move captions.

---

## Rollout

Behind `PWC_COACH_BLUNDER_GUARD` (default **off**). A/B the feel, measure the acceptance bars, then flip on. Kill-switch = set false. Pairs with `PWC_COACH_CONDUCTOR`.

---

## Out of scope (v1)

- Eval-based catastrophe detection (walking into mate / a crushing non-material attack with no immediate capture) — rarer at these levels; possible v2 with a shallow verification search.
- Changing the underlying strength model (Skill Level vs UCI_Elo) — orthogonal; the guard sits on top of whichever is active.
- "Own the mistake" coach voice ("I left something — can you find it?") — a nice teaching layer for the *allowed* mistakes; separate follow-up once the floor is in.

---

## IMPLEMENTED (2026-06-27) — data-driven pivot + results

**Signed off ("go"). Built behind `PWC_COACH_BLUNDER_GUARD=true`.**

The build measurement forced one change to the mechanism. A **pure one-move SEE** floor
caught only **2 of 6** real material hangs at Skill 0 — it MISSES *multi-move*
catastrophes (a combination that wins the queen reads SEE=0). So the floor is a **hybrid**:

- **One-move SEE floor = 300cp** — never hang a piece+ to a single capture (static, free).
- **Multi-move eval floor = 500cp** — never lose a rook+ / walk into mate via a *forced
  sequence* (needs a full-strength engine eval). Set above a minor piece so the student
  is still ALLOWED to win up to ~a piece via a tactic they calculate (philosophy B).
- **Resample = weakest CLEARLY-safe candidate** (within 120cp of best). "Weakest sound"
  alone sat on the catastrophe edge and depth-noise tipped 2 replacements into new
  catastrophes; the margin fixed it.

Cost: this means **one full-strength depth-14 analyse per coach move** (the latency I'd
hoped to avoid — the data changed it). The guard's analysis is full-strength (accurate),
separate from the weakened play.

**Acceptance — MET** (50 real positions, guard graded at depth 16 > guard's depth 14):

| | Skill 0 | Skill 5 |
|---|---|---|
| catastrophe (≥500cp): base → guarded | 3 → **0** | 1 → **0** |
| one-move hang (≥300): base → guarded | 2 → **0** | 4 → **0** |
| avg cp_loss (beatability), guarded | 87 (weak, in-band) | 73 |
| teaching mistakes (150–500cp) surviving | 13/50 | 10/50 |

Guard fires on ~5/50 (10%) of moves. **Honest-caption layer** also shipped: the central
pipeline stamps `coach_move_is_sound` (SEE), and R17 routes an unsound coach move to a
new `coach_overreach` variant ("…but the piece it just moved can be taken — look for the
capture") instead of praising it as a "Good — Double Attack". Verified on the live `Qxf6`
FEN; a genuine sound fork (control `Nc7+`) still narrates as a fork.

Files: `coach_play/coach_blunder_guard.py` (SEE + hybrid guard), `coach_play/coach_opponent.py`
(`_apply_blunder_guard`), `services/caption_pipeline.py` (`coach_move_is_sound`),
`data/captions/R17_coach_move.json` (`coach_overreach`).
