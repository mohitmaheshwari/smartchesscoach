# Explain The Move You Played — Scope

**Status:** DRAFT, awaiting Mohit's sign-off. No code until then.
**Date:** 2026-10-29
**Author:** Claude. Every number here was measured against prod on 2026-10-28/29.

---

## Why this, why now

Mohit, on an opponent card in game `461511c5`:

> "it tells my move both captions and arrow, but doens't tell why their move
> is bad, you know?"

That is not one bad card. Measured over the 471 faulted moves in
`positional_reason_queue` that have a card:

| the card... | cards | share |
|---|---|---|
| explains what YOUR move did **and** names a better move | 164 | 34.8% |
| explains what YOUR move did, only | 22 | 4.7% |
| **names a better move and never says what your move did** | **205** | **43.5%** |
| **explains neither** | **80** | **17.0%** |

**60% of faulted moves are shown the answer and never told the error.**

A player who is told "Qd8 would have made things harder for your opponent"
learns a move. A player who is told what their own move gave away learns a
rule. The second is the product.

---

## The cause, measured

The sentence that explains a played move is built in
`caption_pipeline.py:4103`. It requires two facts:

```python
reply  = gap.get("their_reply")
allows = gap.get("allows") or []
if not reply or not allows:
    return ""
```

`allows` only ever holds `check` or `capture`. So the clause can describe a
punishment that gives check, or one that takes something, and nothing else.

What punishments actually look like, over the same 471 cards:

| the opponent's best reply is a... | cards | card explains the played move |
|---|---|---|
| check | 105 | **96 — 91%** |
| capture | 75 | 40 — 53% |
| **quiet move** | **284 — 60%** | **49 — 17%** |

When the punishment checks, we explain the mistake nine times in ten. When
it is quiet, we explain it fewer than two times in ten.

This is `c6` exactly. After `1.e4 e5 2.Nf3 c6?!` the punishment is `3.d4`:
no check, no capture, nothing for the clause to hold, so the card graded the
move and then talked about a different move instead.

---

## What this will be

For a faulted move whose punishment is quiet, the card says what the quiet
move does to you. In the player's own words, not centipawns.

**Today**

> Your opponent played c6. That was a mistake. Play d4 — it attacks the pawn on e5.

**After**

> Your opponent played c6. It does not defend the pawn on e5 that your knight
> is attacking, and it stands on the square their own knight needs. Play d4.

The second sentence is the product. The move recommendation stays where it is.

---

## How it works

No new architecture. The explanation machinery exists; it is pointed at the
wrong move. Three sources, in order, all board-checkable:

1. **What their quiet reply newly attacks.** Diff the attack sets before and
   after their reply. A quiet move that comes with a threat has a sentence:
   "that lets them play Nd5, hitting your bishop on e7".

2. **What your move abandoned.** `MOVED_MY_ONLY_DEFENDER`, mined and measured
   this week: the piece you moved was the only guard of one of your men, and
   now it is attacked and guarded by nothing. Fires on 26 of 475 faulted
   moves (5.5%); the man is taken in the engine's line 17 times (65%); the
   card already names that square in 15, so it is new information on 11.

3. **What square or line your move gave up.** The `c6` family — your own man
   now stands where your piece needed to go. Prototyped as `SELF_BLOCK`
   (fires on 4.0% of faults, silent on the three moves the engine preferred),
   not built.

Where none of the three can speak, the card says nothing new. Silence is the
current behaviour, so that is not a regression.

---

## What this will NOT do

- **No new positional vocabulary.** The mining run that produced this scope
  built 7 predicates and 5 died against the control (see below). This is not
  the place to add more.
- **No LLM writing chess.** Every sentence comes from a board diff. The model
  phrases, the engine supplies, per the standing rule.
- **No change to move recommendations.** Which move the card recommends and
  which arrows it draws are untouched.
- **No second definition of anything.** `check_that_hits` was built, measured,
  and dropped *because the product already names the same target in 4 of its
  6 cases*. Three definitions of `outpost` already exist and disagree on 545
  of 571 knight moves; that mistake is not being repeated.

---

## The gate every rule must pass

Mined this week and non-negotiable, because it killed five of seven
candidates:

> **A predicate must fire on the mistake and stay quiet on the engine's own
> move.**

| predicate | fires on faults | fires on the ENGINE's move | verdict |
|---|---|---|---|
| `attackers_outnumber` | 142 | **167** | dead |
| `defended_only_by_the_king` | 72 | 55 | dead |
| `pointless_check` | 40 | **57** | dead |
| `overworked_defender` | 11 | 11 | dead |
| `left_it_loose` | 22 | taken 0 of 22 | dead |
| `check_that_hits` | 6 | n/a (engine-gated) | duplicate |
| `moved_my_only_defender` | 26 | 19 | **lives** |

`attackers_outnumber` fires **more often on good moves than on mistakes**. It
would have shipped on a fire rate alone. `knight_outpost` is in the product
today, fires on 52% of all knight moves including `2.Nf3`, and would have
died on day one against this column.

---

## How we will know it worked

One number, measured the same way before and after:

> of faulted cards, the share that say what the played move did wrong

Today: **39.5%** (186 of 471). The target is the quiet-punishment band, which
is 284 cards currently at 17%.

Two guards:
- the claim verifier must pass every new sentence, on the board the claim is
  about — four instruments mis-resolved that board this week, including mine;
- the caption word cap already drops whole `Lesson:` sentences from distilled
  cards, so any added clause must be measured against it, not assumed to fit.

---

## Open questions for Mohit

1. **Is a quiet punishment worth a sentence at all?** 284 cards say the
   opponent's best answer is a quiet move. "That lets them play Nd5, hitting
   your bishop" is true and may still read as weak coaching.
2. **Which of the three sources first**, if they disagree on one card?
3. **Teachability** — some board facts are true and useless ("your king's
   mobility fell by 2"). That call is yours per concept, not mine.

---

## Appendix: what was measured to get here

- 475 positions queued, 403 (85%) explained by no existing predicate
- our entire positional vocabulary is four predicates — `blockade`,
  `king_pawn_cover`, `knight_outpost`, `rook_behind_passer` — covering 72 of 475
- 80 positions explained by four Claude agents: 79 explained, 1 refused,
  **0 false claims** across 286 claims (149 verified on the board, 137
  unverifiable by the checker)
- of the 79, **56 were ordinary tactics, not positional** — the residue is
  not what its name says
- the biggest family is loose-piece / only-defender, 22 of 79
