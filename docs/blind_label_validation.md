# Checking the traits against a human coach

*Built 2026-09-29.*

## The gap this closes

Every behavioural trait in `services/behaviour_profile.py` and both layers in
`services/two_layer_diagnosis.py` were validated the same way: stable within a
player across halves of their games, and spread across players. Thinks-too-long
sits at 0.88, the clock shape at 0.87, conversion climbs 0.43 → 0.59 → 0.72 as
the bar rises.

All of that is **internal consistency**. None of it is evidence that the reading
is **correct**. A measure can be perfectly reliable and measure the wrong thing,
and nothing in the system has ever been checked against a person who knows chess
saying "yes, that is this player".

This is that check.

## How it runs

```bash
python scripts/build_blind_label_packet.py --apply --out DIR   # make the packet
#   ... coach fills form_1_freetext.md, then form_2_choices.csv ...
python scripts/score_blind_labels.py --form FILLED.csv --key DIR_ANSWER_KEY.json
```

The packet is 13 entries, 8 games each, ~100 games. About three hours of a
coach's time.

## Four design choices, and what each one is protecting

**Blind, with the key written outside the packet directory.** Nothing we
produce reaches the coach. The leak check is not a matter of trust: usernames
are scrubbed from the whole header block, not tag by tag, because chess.com
writes the winner's name into `Termination` ("aydin_yashar won by resignation")
and one username is enough to look a player up and read their entire history.
`Date` is dropped and the rating is rounded to the nearest hundred.

`Termination` itself is kept, name swapped. "THE PLAYER won on time" is the most
direct evidence there is for two of the clock traits, and dropping the tag to
remove the name would take that with it.

**Free text before forced choice, in two files.** If the coach sees our six
categories before writing their own, the agreement measures suggestion. File 1
asks only "what kind of player is this, and what would you tell them".

**A repeat, with different games.** One player appears twice under two ids,
their games split odd-even from the same 16. Interleaved rather than first-half
against second-half: consecutive blocks would put the two appearances in
different months, and the rating drift and the run of results between them are
exactly the tell that lets a coach spot the repeat. It also matches how the
traits themselves were validated.

The coach's agreement with **themselves** is the ceiling on their agreement with
us. It is printed first for that reason. If it is poor, nothing else in the
report can be read.

**Chance by permutation.** The coach's own answers are reassigned to the wrong
players 10,000 times. This preserves their marginals — a coach who answers "A"
most of the time gets the high baseline they deserve — and assumes nothing about
what random answering looks like.

## What is scored

Not raw agreement. Most of our answers are "-": a trait inside the middle half
of the population is never rendered, and scoring those would reward the system
for saying nothing. The measure covers only the rows where **we would show the
player a sentence**, and each lands in one of three places:

| | meaning |
|---|---|
| **CONFIRMED** | the coach picked the same end |
| **NOT SEEN** | the coach said "in between" or "cannot tell" |
| **CONTRADICTED** | the coach picked the **other** end |

Only the third is evidence that we are wrong, and it is the number to watch. A
low confirmed rate with a high not-seen rate means the packet was too small; a
high contradicted rate means the trait is wrong.

The behavioural traits and the tactical-misses layer are aggregated **apart**.
"They find most of what is there" is a real decision — it is why a player is
shown no tactical card at all — but it is a different kind of claim, and pooling
them lets a strong result on one hide a weak one on the other.

## What this packet cannot tell us

**Prevalence.** The 12 players were chosen to carry at least two high and two
low exemplars of every trait, both knowledge-layer players we have, three
attention-layer and seven with no gap. The base rates are destroyed on purpose.
It can say whether a claim is right. It cannot say how many players it applies
to.

**Whose fault a disagreement is.** The coach reads 8 games; we measure over a
whole history, a median of 145 clocked games. A disagreement can mean our
reading is wrong, or that 8 games are too few to see the trait. Eight is chosen
to clear our own `MIN_TIMED_MOVES` of 200, so the coach is not asked to judge
from less evidence than we demand of ourselves — but that narrows the gap rather
than closing it, and the report must not read a disagreement as our error alone.

This is why the "cannot tell" option matters and why the README asks for it
explicitly. A guess and a judgement are indistinguishable to us afterwards.

**Conversion, probably.** `throws_away_won_games` needs 60 winning positions
before we will speak it. A coach seeing 8 games sees a handful. If that column
comes back mostly "cannot tell", that is the honest result and not a failure.

## Reading the outcome

- **Contradicted is near zero and the permutation test rejects chance** — the
  traits describe something a coach recognises. Widening the diagnosis cut from
  the lower quartile becomes defensible.
- **Contradicted is high on one trait** — that trait is wrong, whatever its
  split-half stability. Read the named players' games before deciding which of
  us is right.
- **Not seen is high across the board** — the packet was too small, not the
  traits. Rebuild with more games per player before concluding anything.
- **The coach disagrees with themselves** — stop. Nothing else is interpretable.

## The free text is the more valuable half

Three of the things Mohit most wanted to measure — is this player too
aggressive, do they calculate, do they play with a plan — we failed to measure
at all. Aggression failed twice, at 0.23 as forcing-move share and 0.06 measured
through wrong-register.

A sentence from a coach about what is **observable** in those is worth more than
any agreement number in the scored half, and the README says so.

## Testing

`tests/test_blind_label_scoring.py` shows the scorer four coaches whose truth we
already know: one who agrees, one answering at random, one who says "cannot
tell" throughout, and one who says the opposite. The random coach is the one
that matters — a permutation test that cannot fail to reject is not a test, and
"the coach agreed with us" is worthless unless the same machinery would have
said so when they did not.

Verified end to end against the real key: the agreeing coach scores 56/56 at
p < 0.0001, the random coach 16/56 at p = 0.22, correctly reported as
indistinguishable from chance.
