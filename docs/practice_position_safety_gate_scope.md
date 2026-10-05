# Practice positions: the answer has to actually work

**Status:** scope. No code until Mohit signs off.

**Where this came from.** Mohit, 2026-10-05, looking at a drill headed *"Let's
Practise Piece Safety"*:

> *"we are not talking about the knight on e7, it is attacked twice and it is
> gone now, so how come we are keeping piece safety"*

He is right, and the position proves it.

---

## 1. The position

`r1bk1r2/ppp1n2N/3p4/6B1/8/1B1P4/PPP3PP/4R1K1 b - - 0 20`

The card says: *"The original move Rf7 put the rook on f7, where Bxf7 could
take it. Rf5 … avoids putting the rook on that unsafe square."* Every word of
that is true. `Bxf7` is real, f7 is undefended, `Rf5` is safe.

And the card is still wrong, because of what it does not say:

| | knight on e7 | what follows |
|---|---|---|
| `Rf7` — the move we call the mistake | 2 attackers, **2 defenders** (the rook now guards it) | loses the rook to `Bxf7` |
| `Rf5` — the move we call **safer** | 2 attackers, **1 defender** | `Bxe7+` wins a clean piece; material 0 → +3 White |

The knight on e7 is attacked by `Re1` and `Bg5` and defended only by the king.
It is lost before the student touches anything. The move we label a blunder is
the one that *defends* it; the move we call safer abandons it.

`Rf5` is still the better move — losing a knight beats losing a rook — so the
engine is not wrong. **The teaching is.** We titled the screen *Piece Safety*
and taught *"calculate every way the opponent can capture it"*, in a position
where a student who calculates perfectly plays our answer and is a piece down
anyway. That does not teach the habit. It discredits it.

---

## 2. How common it is

Every admitted practice position, both pools. For each one: push the move we
accept as correct, then ask what the opponent wins by force on their best
capture. Static exchange on the board — no engine call.

**91,008 positions evaluated.**

| after our accepted answer | positions | share |
|---|---:|---:|
| opponent wins nothing | 52,617 | **57.8%** |
| opponent still wins a pawn (100–299cp) | 25,546 | 28.1% |
| opponent still wins a piece (≥300cp) | 12,845 | **14.1%** |

So in **42% of our practice positions the correct answer does not make the
student safe**, and in 14% they are still a whole piece down.

By concept, share where the answer holds:

| concept | n | answer holds |
|---|---:|---:|
| `tactic:back_rank_mate_exact` | 38 | 100.0% |
| `tactic:forced_mate_exact` | 571 | 89.7% |
| `curriculum:opening_exact_position` | 22 | 86.4% |
| `curriculum:opening_plan_exact_position` | 26 | 80.8% |
| `curriculum:opening_plan_exact_decision` | 345 | 69.3% |
| `gap:piece_safety:simple_hang` | 7,408 | 63.9% |
| `tactic:fork_with_stored_payoff` | 1,620 | 62.3% |
| `gap:piece_safety:destination_safety_exact` | 4,194 | 61.6% |
| `tactic:free_piece_exact` | 2,264 | 61.6% |
| `tactic:aligned_with_stored_payoff` | 706 | 59.5% |
| `curriculum:opening_exact_decision` | 60 | 58.3% |
| **`(none)` — no quality_id** | **73,184** | 56.5% |
| `gap:piece_safety:trapped_piece_exact` | 164 | 48.2% |
| `tactic:discovered_attack_with_stored_payoff` | 302 | 43.0% |
| `tactic:remove_defender_with_stored_payoff` | 78 | 26.9% |
| `curriculum:trap_exact_decision` | 24 | 8.3% |
| `curriculum:trap_exact_position` | 2 | 0.0% |

Two things fall out of that table that are worth more than the gate itself:

- **The mate concepts survive at 90–100%.** That is the shape of a well-chosen
  drill: when the answer ends the game, nothing else on the board matters.
- **`remove_defender` keeps 27% and `trap_exact_decision` keeps 8%.** Those are
  not gate problems. A detector whose positions mostly fail this check is
  selecting moments where its own answer does not fix the position.
- **80% of the admitted pool carries no `quality_id` at all** (73,184 of
  91,008). Whatever we decide here, most of the pool is unclassified, and that
  is its own finding.

---

## 3. What the gate should actually test

The obvious rule — *"reject if the opponent still wins material"* — is too
blunt, and the e7 position shows why. Sometimes the best available move loses
material because the position was already lost, and playing the least-bad move
IS the lesson. A blanket gate throws away every damage-control drill.

The complaint is narrower than that. It is not *"the student still loses
material"*. It is **"we taught the smaller loss and ignored the bigger one"**.

So the rule to implement:

> A position may enter the practice pool only if, after the answer we accept,
> the opponent cannot win **more** material than the loss the drill is about.

On the e7 position: the drill is about a rook (5). After `Rf5` the opponent
wins a knight (3) — less than the rook, so by this rule it passes. That is
wrong, and it is wrong in an instructive way: what makes the card bad is not
the size of the remaining loss but that **the remaining loss is untouched by
the answer**. The knight hangs before and after.

Which gives the rule I actually recommend:

> A position may enter the pool only if the answer we accept **removes the
> material threat the drill is about, and does not leave a different one of
> comparable size untouched.**

Concretely, two checks, both board arithmetic:

1. **The answer works.** The specific loss named in the card (the hanging
   piece, the unsafe destination) is gone after the answer.
2. **Nothing comparable is left behind.** No *other* square where the opponent
   wins ≥ the value of the piece the drill is about, both before and after the
   answer. "Both before and after" is what distinguishes a pre-existing
   problem the drill ignores from a consequence of the move.

Check 1 is almost certainly already true — these are admitted positions with
stored proofs. Check 2 is the new one and is what the e7 card fails.

---

## 3a. The proposed rule, measured (2026-10-05)

Section 2's table measures a BLUNT PROXY -- "does the opponent still win
material". The rule recommended above is different and had no measurement
behind it, which is the kind of gap that makes a scope look finished when it
is not. Measured properly:

> Reject when, after the answer we accept, the opponent wins material on a
> square where they could ALREADY have won it before the student moved.

| | kept | rejected |
|---|---:|---:|
| blunt proxy | 57.8% | 42.2% |
| **this rule** | **72.6%** | **27.4%** (24,976 of 91,009) |

Both controls pass:

- **negative** -- the e7 card returns `pre-existing loss untouched, 300cp`
  and is rejected. That is the position this whole scope exists for.
- **positive** -- `back_rank_mate_exact` stays at 38/38, 100% kept.

Kept per concept: `opening_plan_exact_decision` 98.8%, `forced_mate_exact`
95.8%, `opening_exact_position` 95.5%, `fork` 76.4%, `aligned` 73.8%,
`(none)` 72.6%, `simple_hang` 71.9%, `destination_safety_exact` 70.4%,
`trapped_piece` 65.9%, `free_piece` 65.6%, `discovered_attack` 65.6%,
`remove_defender` 65.4%, `opening_exact_decision` 63.3%,
`trap_exact_decision` 25.0%.

**This corrects section 2.** `remove_defender` was flagged there as a detector
selecting bad moments, on the strength of keeping only 26.9% under the blunt
proxy. Under the rule we would actually ship it keeps 65.4% -- in line with
`free_piece` and `discovered_attack`. There is no detector problem there. The
only remaining outlier is `trap_exact_decision` at 25%, and it is 24 positions.

## 4. Decisions needed from Mohit

1. **The bar.** Recommend check 2 at "≥ the drill's own piece value". The
   alternatives are ≥300cp flat (removes ~14%) or ≥100cp flat (removes ~42%).
2. **What happens to rejected positions.** Drop them, or re-tag them to the
   concept that actually dominates? The e7 position is a genuine piece-safety
   position — the lesson is the knight. Re-tagging keeps the pool and fixes the
   teaching; dropping is one line and loses the position.
3. **Retroactive or not.** A gate on new admissions is cheap. Re-grading 91,008
   existing rows is a migration, and it has to run **after** deploy, never
   before — writing a grade the deployed code does not understand silently
   drops rows from user-facing pools.
4. **The two broken detectors.** `remove_defender` (27%) and
   `trap_exact_decision` (8%) look like selection faults rather than gate
   casualties. Separate piece of work; flagging so it is not lost.

---

## 5. How it gets verified

Same standard as the opponent-clause work:

- the gate decides on board arithmetic only — no engine call, no stored verdict
  taken on trust
- measured before/after across all 91,008 positions, per concept, so the pool
  cost is known rather than estimated
- a positive control: positions the gate keeps must include the ones a human
  would obviously keep (`back_rank_mate_exact` is currently 100% and must stay
  100%)
- a negative control: the e7 position must be rejected, and that is the test
  that proves the gate does what this document says

---

## 6. What this is not

Not a detector rewrite. The detectors find real tactical facts and the stored
proofs hold — 4,193 destination-safety claims were re-verified on the board and
**100%** of them were true. The facts are right. The question this scope
answers is whether the position was worth putting in front of a student, which
nothing currently asks.
