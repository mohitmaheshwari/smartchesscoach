# The reasoning framework

Status: BUILT and TESTED. **Wired to nothing** — it is inert until the Why
endpoint calls it. Nothing a player sees changes from this commit.

## What it is

One question: *what is true of this move and NOT true of the move the engine
wanted?* Everything else here follows from that.

```
"Your opponent missed castling"   true, and true after every move
"Nc3 blocks your own c-pawn"      true, and FALSE after O-O
```

Only the second is a reason. The first is the shape of complaint Mohit has
been sending back for months, and no surface in this repo could tell them
apart, because every one of them answers "what is true of this move" and none
answers "and would it still be true if they had found the better one".

So every finding now carries a `differential`:

| value | meaning |
|---|---|
| `distinguishes` | true after the played move, absent after the best — a reason |
| `present_after_both` | true either way — a fact about the position, refused |
| `inherent` | the question already compares the two moves |
| `not_tested` | no better move to compare against |

`Finding.usable` is false for `present_after_both`, and the caption layer is
expected to read that rather than the claim.

## What it is not

**Not a caption generator.** It emits findings with slots; prose stays in the
caption layer, which is voice-tested and verified, and the repo has a CI guard
against teaching text appearing anywhere else. A test asserts no fact value
runs past three words.

**Not a new question bank.** The questions live in `contrastive_reasoner` and
are imported. A concept whose answer is computed twice eventually gives two
answers — the same reason the shape of `abandoned_own_defender` is decided in
one place and read in two.

## Measured, 500 games / 3,521 flagged cards, both sides

| | |
|---|---|
| resolved | 377 (10.7%) |
| **unresolved** | **3,144 (89.3%)** |
| primary finding is CAUSE | 214 |
| primary finding is EVIDENCE | 71 |
| primary finding is SYMPTOM | 92 |
| findings tested by the differential | 73% |
| **rejected as a fact about the position** | **8 (1.6%)** |

### The differential catches real things, and not many

Two of the first eight rejections were captions shipped the same day:

```
Qd7   "you moved your queen away from defending e5"
      played line  Bxe5 ...
      BEST line    Rc1 Qg4 h3 Qd7 Bxe5 ...     the pawn falls either way

Nxf2  "the knight that was guarding your bishop on b2, and Rxb2 wins it"
      played line  Rxb2 ...
      BEST line    Rxb2 ...                     the bishop falls either way
```

Both claims are true. Neither is what the move cost. That is the failure mode
this framework exists to stop, and it was live.

But 1.6% is the honest rate, and it reframes the problem: **the existing
questions were already about 98% causal.** The differential validates them
rather than culling them. It earns its place as a cheap guard on every future
question — especially engine-backed ones, which will assert board properties
freely — not as a filter that cleans up today's output.

### The real gap is coverage, not correctness

**89.3% of flagged cards get no finding at all**, and of the ones that do, a
quarter are led by a SYMPTOM — "your piece came back" — which is the exact
card Mohit objected to on move 6 Nc3. We are not often wrong. We are usually
silent, and when we do speak it is too often about the consequence.

## Design notes worth keeping

**Confidence is ordinal and only ever goes down.** `high` / `medium` / `low`,
never a number, because a heuristic presented as a probability is one nobody
can defend. A finding that does not distinguish the two moves never rates
above `low` however stable the engine is.

**Stability lowers confidence, it does not hide.** `check_stability` asks the
engine whether it still prefers the same move when asked harder. An unstable
preference is not something to teach a 1200 a lesson about.

**The budget is counted, not hoped for.** `Budget.take()` decrements. With no
engine the probe reports unavailable and the board questions still run, which
is also how the tests run in CI.

**One exploding detector cannot take the card down.** Each question is called
inside its own guard, and a test adds a deliberately raising question to prove
the run survives it.

**`inherent` must be earned.** I first marked three of four questions
inherent, which left the differential running on 19% of findings and rejecting
two. Only `blocked_a_plan` genuinely cannot be true of the better move. The
retreat questions assert a property — they just assert it about whichever
piece moved — so they now face the test on an empty subject, which compares on
existence: if the engine walks a piece home after the better move too, then
shuffling is what the position does, not what the move cost. A test pins the
exempt set to exactly `{blocked_a_plan}` so nothing gets quietly exempted
again.

## The eight steps, and where each one lives

Mohit asked for the framework to be built through the procedure I used by hand
on his Nc3 card. Mapped honestly:

| step | where |
|---|---|
| 1. the engine says THAT, not WHY — size expectation | `_size_is_consistent` |
| 2. two futures; the reason is in the difference | `MoveUnderStudy` + the differential |
| 3. what WE get to do in the better line | `q_blocked_a_plan` |
| 4. legal before, illegal after | same question |
| 5. is my move physically in the way | `in_the_way` |
| 6. attack the story already on the card | `Question.challenge` |
| 7. does my answer match the engine's number | `_size_is_consistent` |
| 8. one sentence a 1200 would use | deliberately the caption layer |

Steps 1, 6 and 7 were added on 2026-10-21. Before that, step 7 lived inside a
single question — so it protected one concept and every future question would
have had to remember it — and step 6 did not exist at all.

### What they remove, measured over 500 games

| | |
|---|---|
| findings | 488 |
| usable after all rules | 347 (71.1%) |
| cut by SIZE (steps 1+7) | **51 (10.5%)** |
| cut by CHALLENGE (step 6) | **102 (20.9%)** |
| cards resolved | 304 (8.6%), from 377 |

The challenge cut is the striking one: **102 of 264 retreat findings (39%)**
fail their own premise. Mohit on the Nc3 card — *"why would nC3 comes back to
b1, there is no attack on nc3 in coming future, it's safe there"* — turns out
to describe four cards in ten, not one. "The move loses time" was reading a
deliberate regrouping backwards at scale.

The size rule catches the other shape: a positional lesson offered on a
19,950cp position, which is to say to somebody being mated.

Coverage falls from 377 resolved cards to 304. Those 73 cards now say nothing
rather than saying something that does not hold, which is the one trade this
repo's rules make in that direction: silence beats a confident wrong answer,
even though a mediocre answer beats silence.

### Thresholds, and one that is a judgement

`POSITIONAL_MAX_CP = 900` comes from a real gap. The cp_loss under each
finding tops out near 1,200 for the well-behaved body and the rest is a
separate population of mate scores at 8,500 and up.

`CLAIM_SLACK_CP = 200` does **not** come from a gap, and that is recorded
rather than hidden. Over 92 material findings, claim minus cp_loss runs
p50 −48, p75 +21, p90 +167, p95 +202, p99 +399, with 71.7% at or below the
engine's number. The tail is smooth, so the bar is a judgement at the 95th
percentile. Some gap is legitimate by construction: a claim measures material
in the line while cp_loss prices the whole position.

## Next

1. **Wire it behind the Why button.** `why_on_demand.explain()` currently asks
   one question (material). This is the thing that makes it ask several and
   rank them. Until then this module changes nothing.
2. **Coverage, not more verification.** 89.3% silent is where the value is.
   The questions to add should come from the silent cards, censused as a
   family — not from the ~60 concept names in the spec.
3. **Engine-backed questions.** The probe exists and is budgeted but nothing
   uses it except the stability check. The counterfactual probes Part 7 asks
   for are the first real use.
