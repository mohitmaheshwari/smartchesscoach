# Cause before symptom

Status: BUILT and WIRED. Numbers below are from the corpus diff; the opponent
half works here, unlike the abandoned-guard shape.

## Why this exists

Mohit, 2026-10-21, on move 6 `Nc3` of game 56b6c294, which read:

> Their knight comes straight back to b1. The move loses time. Opponent's Nc3
> is an inaccuracy. Play a6. They missed O-O — it tucks their king away from
> the middle.

His two complaints, weeks apart, are the same bug:

> "I think the NC3 blocks your own c pawn gives a better study, of chess you
> know, the other caption is more to just to dhwatever wihtout any learning,
> that's more of cramming part... we are teaching them the concepts"

> "and secondly why would nC3 comes back to b1, there is no attack on nc3 in
> coming future, it's safe there"

Both are right, and the board proves both. On
`r2qkb1r/ppp2ppp/2n1pn2/3p1b2/3P4/P3PN2/1PP1BPPP/RNBQK2R w KQkq - 0 6`:

```
c4 legal BEFORE Nc3 : True
c4 legal AFTER  Nc3 : False        the knight stands on c3, the pawn on c2
engine's best line  : O-O Bd6 c4 dxc4 ...   it plays c4 on its next turn
attackers on c3     : none, ever    the retreat is a regroup via d2
```

So "loses time" reads a deliberate manoeuvre backwards, and the actual reason
the move is an inaccuracy was one square away the whole time.

## What was already there

`services/contrastive_reasoner.py` returns **all three** answers on that
position:

```
CAUSE    (3)  blocked_a_plan     c4
EVIDENCE (2)  engine_undoes_it   knight to b1, UNATTACKED
SYMPTOM  (1)  returns_home       b1
```

The shipped caption spoke the symptom, because the symptom rule
(`MOVE_UNDONE`) was wired and the cause was wired to nothing. That is the
whole finding: the ranking existed on paper and nothing enforced it.

## The change

One splice, in the block that already owns these cards
(`caption_pipeline.py`, gated on `_story == "neither"` and no mate on the
board). It asks `q_blocked_a_plan` first and, when that answers, the cause
leads and the undone narration is **dropped rather than appended** — two
explanations of one move read as a card that cannot make up its mind. The rule
label becomes `→PLAN_BLOCKED` so the two are distinguishable in any audit.

```
Their knight on c3 blocks their own c-pawn. The better line plays c4.
```

This splice sits after the overwrite chain, which is why it survives where the
R12 lead clause did not (see
[abandoned_own_guard_scope.md](abandoned_own_guard_scope.md)). It also handles
**both sides** already, because `MOVE_UNDONE` does.

## Numbers

Measured over 150 games / 1,273 cards at `cp_loss >= 50`, both sides:

| | |
|---|---|
| captions changed | **9 (0.71%)** — 7 user, 2 opponent |
| of those, replaced the symptom narration | 0 |
| spoke where the card had no cause at all | 9 |
| firing cards re-verified on the board (300 games) | **26 of 26** |

Control: `backend/tests/test_blocked_plan_outranks_the_symptom.py`, 20 tests,
geometry asserted with python-chess independently of the question.

## Two bugs the corpus found that reasoning did not

Both would have shipped from a question validated on a single position, and
both came from reading rendered sentences rather than clauses.

**A move cannot block itself.** The better line often plays the SAME move a
few plies later; having played it we cannot play it again, which is legally
true and says nothing:

> Your pawn on h5 blocks your own h-pawn. The better line plays h5.

**A man cannot stand in his own way.** `d7-d6` makes `d7-d5` illegal, and the
card had the pawn talking about itself:

> Your pawn on d6 blocks your own d-pawn. The better line plays d5.

Before those two guards the splice changed **108 of 1,273** cards, most of
them nonsense. After, **9**. The Nc3 card never showed either, because there
the blocked move is a different move made by a different man — which is what
comes of validating on one position.

## The precision gate

`in_the_way`: our move's destination must sit on the blocked move's path. A
move of the better line that became illegal for some unrelated reason is a
coincidence, not a lesson, and the sentence would be a confident wrong claim
about it. The question still reports the block; the sentence refuses it.

That gate is why this is safe to lead with despite `blocked_a_plan` firing on
20.8% of flagged cards at only 2.1x lift against good moves. The rate is not
doing detection work here: the engine has already ruled the move an
inaccuracy, and the board only explains it. Engine gates, board explains.

## Open

- The generic branch ("takes the square your own {piece} wanted for {san}")
  is written and **deliberately silent**. It is a real idea — a queen landing
  on d7 where the knight belonged is a lesson — but in the corpus it produced
  "Your bishop on b2 takes the square your own bishop wanted for Bb2", and the
  claim is weaker anyway because the piece usually has another square. It
  stays quiet until it has been read through on its own terms.
- `q_engine_undoes_it` (EVIDENCE tier) is still unwired. It knows the thing
  Mohit noticed — that nothing attacks the piece — and `_say_the_move_is_undone`
  will still say "comes straight back" on cards where the cause stays quiet.
  The honest version of that sentence names the chaser or says the retreat was
  voluntary.
