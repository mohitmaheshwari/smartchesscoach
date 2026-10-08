# Board facts, and the lift gate that decides which may speak

**Status:** DRAFT — awaiting Mohit's sign-off. No code written.
**Asked for:** 2026-09-30. "with stockfish backing we could have generated
some understanding... a pawn is about to queen, all these scenarios could be
understood by our python chess, right?"

Yes. The measurements below say the idea works, and also say the obvious
version of it would fill the product with sentences that explain nothing.

---

## 1. What this is

Two things, and the second is the important one.

1. **A fact library.** Small, generic, always-computable statements about a
   position, derived from `python-chess` and the stored evals. Not pattern
   detectors — facts. "Something of mine is now capturable for free."
   "A pawn is one square from promoting." "The reply is a check."

2. **A lift gate.** No fact may appear in a caption until it has been measured
   on real moves and shown to be *more common on mistakes than on good moves*.
   Facts below the threshold are computed, stored, and stay silent.

## 2. Why the gate is the point

Measured over 600 games: 1,936 mistakes (>=200cp) and 12,428 good moves
(<50cp), same extractor run over both.

| fact | on blunders | on good moves | lift |
|---|---:|---:|---:|
| left something free | 22.6% | 7.6% | **2.98x** |
| my pawn near promotion | 8.6% | 6.4% | 1.36x |
| their pawn near promotion | 9.2% | 6.8% | 1.35x |
| their piece had two jobs | 79.4% | 77.6% | **1.02x** |

"A piece has two jobs" is true in four blunders out of five — and in four good
moves out of five. It describes chess, not the mistake. A caption built on it
reads as insight and carries no information.

This is the same failure already recorded in
`project_principles_split_error_state_praise` (7 of 35 principles firing at the
base rate) and `feedback_principle_bank_is_filler`. The gate exists so that
class of filler cannot reach a player again.

**Without the control, presence looks like explanation.** 92.4% of blunders
carry at least one structural fact, which sounds like near-total coverage until
you notice most of that is a fact that fires on everything.

## 3. What goes in the library (V1)

Only facts that are cheap, deterministic and provable from the board or the
stored eval. Each ships with its measured lift.

- something of mine is capturable for free after this move (2.98x — passes)
- the refutation is a check
- a pawn is one square from promoting, either side
- who controls a promotion square, and whether this move changed it
- my king has more attackers than before
- a piece of theirs defends two or more of its own pieces (1.02x — FAILS,
  computed and stored, never spoken)

The last one is listed deliberately. It stays in the library because it is
useful *evidence* when combined with something else; it simply may not be the
sentence.

## 4. The gate

- Every fact carries a measured `lift` = P(fact | mistake) / P(fact | good move).
- A fact may lead a caption only at **lift >= 2.0**.
- A fact may appear as supporting evidence at **lift >= 1.5**.
- Below 1.5 it is stored and silent.
- The threshold is a starting point, not a truth. Per
  `feedback_threshold_before_distribution_is_sin`, it must be re-set from the
  distribution once there are more than six facts to look at.
- Lift is re-measured whenever a fact's implementation changes. A fact whose
  definition moved has an unknown lift until re-run.

## 5. In scope (V1)

- One extractor module, pure functions, board in -> set of facts out.
- One offline script that measures lift for every fact across a sample and
  writes the numbers next to the fact definitions.
- A test that fails if any fact is marked speakable without a recorded lift.
- Wiring into the existing caption path at the point where evidence is already
  assembled. No new caption surface.

## 6. Explicitly out of scope (V1)

- No LLM at runtime. The whole point is that this is computable. A model may
  help author the *sentence* for a fact offline; it never decides whether a
  fact is true.
- No new detectors for rare shapes. See section 7.
- No change to severity or to what counts as a mistake. Stockfish still gates
  THAT a move is bad; these facts only say WHY.
- No caption may assert a fact the extractor did not return for that position.

## 7. What this replaces, and one thing it does not

It replaces the instinct to build a detector per pattern. Worked example from
the same session: a genuinely good card was designed for one position — a rook
that was the second attacker holding an enemy rook in place. Built as a
detector it fires on **6 of 1,891 mistakes (0.3%)**, and two of those six are
positions already lost by 88 pawns. Roughly 1 mistake in 470.

The first version of that detector reported 10.6%. It was wrong: it fired on
ordinary recaptures, because capturing on a defended square always "releases"
the defender. Three gates (no captures, the square must be genuinely contested,
the freed piece must actually leave) took it from 201 fires to 6.

The lesson is not that the card was bad. The card was good, and its shape —
concept first, picture carries the geometry, one transferable line — should be
applied to the facts that fire at 20%+, not at 0.3%.

**What this does not fix:** a high-lift fact still has to be phrased in a way a
900-rated player can use. Lift decides whether a fact may speak. It says
nothing about whether the sentence teaches.

## 8. Success criteria

- Every speakable fact has a recorded lift from a stated sample size.
- No caption asserts a fact absent from that position's extractor output.
  Checkable per position, offline, no model.
- Re-running the measurement on a fresh sample reproduces each lift within a
  stated tolerance. If it does not, the sample was too small.
- A fact whose lift drops below the gate stops appearing, without a code change.

## 9. Open questions

- **What sample size makes a lift trustworthy?** 1,936 mistakes gave stable
  numbers for facts firing above 5%. A fact firing at 0.3% has 6 examples and
  no measurable lift at all. There should be a minimum fire count before a lift
  is quoted.
- **Should lift be measured per rating band?** A fact that discriminates for
  900s may not for 1600s. Not tested.
- **Does lift survive the 4-ply PV cap?** Facts computed from
  `pv_after_played` inherit that horizon. See
  `docs/cold_start_content_findings_2026_09_28.md` for the same issue in
  another guise.
