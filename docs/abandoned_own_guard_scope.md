# You walked away from your own guard

Status: BUILT, MEASURED, AUDITED and WIRED to the screen on the user side.
Opponent side deliberately out — see "What is not done".

## Why it exists

Mohit, 2026-10-21, on move 7 of his own game:

> "hey, while you bulid this, i wnat to give you more issues, so you can plan
> all better , i thihk yo ufixed htings worse"

```
r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7
played e5   best a6   cp_loss 100   inaccuracy
Caption is bullshit: "This move cost you something. Compare it with the
                      engine's line below."
```

That sentence is mine. It went in at v226 as a crash fallback and it is
honest, useless, and worse than silence, because it sits in the slot where the
lesson goes. He is right.

The board says something a player can use. Read with python-chess:

```
BEFORE e5:  d5 guarded by [pawn e6, knight f6]   attacked by [knight c3]
AFTER  e5:  d5 guarded by [knight f6]
line     :  dxe5 Nxe5 Nxd5     -> the d5 pawn is gone
```

The e-pawn was one of two things holding d5. It pushed, and d5 fell. That is
the mirror of the removing-the-defender concept already specced in
[removing_the_defender_strict_v1_scope.md](removing_the_defender_strict_v1_scope.md):
there we take THEIR guard, here we walk away from OUR own.

There is a second cause in that position worth recording, because it is the
reason one remaining guard was not enough: `dxe5` also clears White's d4 pawn
off the d-file, so the queen on d1 joins the attack. After `e5 dxe5 Nxe5` the
d5 pawn is attacked twice and guarded once. The card does not claim this; it
is listed here so nobody later reads the caption as the whole story.

## What already exists — do NOT rebuild it

Measured 2026-10-21 over 3,471 flagged user cards (cp_loss >= 100, with a
stored line), through the real `extract_facts`:

| | |
|---|---|
| shipped `lost_defender_lead_clause` (TAC_HANGING_PIECE / `lost_defender`) | 185 (5.33%) |
| the new engine-verified question | 110 (3.17%) |
| **both** | **90** |
| new only | 20 |
| shipped only | 95 |

So the shipped clause already owns most of this ground. It keeps it. The
extension in `caption_facts.py` fires ONLY where that clause produced nothing
and changes not one word of the text it already ships.

The 20 it misses are the ones worth having, and they are a population, not an
accident: `TAC_HANGING_PIECE` needs the piece to end up actually hanging, so
the entire "it still had a guard and fell anyway" family is invisible to it.
Mohit's e5 card is in that family, which is exactly why it reached him with no
lead and then with the shrug.

## The question

`services/contrastive_reasoner.q_abandoned_own_defender`, CAUSE tier. Eight
clauses, six on two boards and two on the engine's stored line:

1. the moved man was covering one of our own men (never a king)
2. our cover of that square really dropped — counted, so a discovered
   defender, or the same piece still covering from its new home, means silence
3. they attack it once we have moved
4. in THEIR stored line they take it, and we do not win it back on that square
5. the man who walked away is not himself captured for nothing
6. nobody is mated in the line
7. nothing much bigger than the abandoned man falls
8. and the line actually costs us something

Clauses 5–8 are not polish. Each came from reading output, and each was found
on a card where every other clause held:

- **5**: `Nd7` answered by `Qxd7`. "You stopped guarding g4" about a move that
  drops a knight.
- **6**: `Qxc2` at cp_loss 9499 — a pawn explained to a player being mated on
  h7. The material swing cannot catch this one: the stored line WINS us a rook
  on the way to the mate, so only the engine's own number tells the truth.
- **7**: `d6` allowing `Nxc6+` and the queen behind it. The knight claim was
  true; the queen was the lesson.
- **8**: `Qe5`, where the g4 knight goes and the line wins their queen, so we
  end **seven pawns up**. Over 218 firing cards, 16.1% came out even or ahead
  like that: the man was traded, not lost, and "they took it" describes a loss
  the player never suffered. Clause 7 caps the loss from above; this caps it
  from below.

## Numbers

Control written before any rate: `backend/tests/test_abandoned_own_defender.py`
(23 tests), geometry asserted with python-chess independently of the question,
so a wrong question cannot hide behind a wrong control.

| | |
|---|---|
| fires, flagged user cards (cp_loss >= 100) | 3.17% |
| fires, good moves (cp_loss <= 10, full-PV corpus) | 1.27% |
| **lift** | **3.6x** (the shipped-style `blocked_a_plan` question is 2.1x) |
| CAUSE-tier coverage of flagged cards, before | 20.79% |
| CAUSE-tier coverage, after | 23.10% |
| claims re-verified on the board, 10 random cards | 10 / 10 |

The good-move control has to come from the full-PV research corpus, because
production stores a line only for flagged moves: the 281 "good" cards with a
stored line in the DB are a biased sliver, not a control.

## The caption

`services/self_removal_caption.py`. Three shapes, chosen from the
distribution over 435 cases, with piece names filled from the board:

```
no guard left           339   78.0%
still has help, quiet    76   17.5%
still has help, check    20    4.6%
```

Locked by `backend/tests/test_self_removal_caption_voice.py` (17 tests): no
digits outside square names, no counting words, sentences at most sixteen
words, words at most ten letters, no jargon, ends on the principle, and the
exact shrug sentences Mohit sent back are banned by string.

Two wordings died in review and are recorded so they do not come back:

- **"the only thing guarding it"** — true on 390 of the 395 no-guard cases.
  The other five lose two guards to ONE move, because the move walks one guard
  away and blocks the second one's line (a black pawn to d5 stepping in front
  of its own rook on e5, cutting it off from c5). The card says "nothing is
  guarding it now", which is true in all 395 and plainer besides.
- **"the king had to move first"** — the natural thing to write and false.
  `Qxg4+` was answered by `Qg3` and `Nxc6+` by `Be7`: a block, not a king
  move. A check can be answered three ways and the card may only claim the one
  a clause proved, which is that the piece was never won back.

A fourth shape also died: the no-guard case was split by check as well, and
the card ended on "look for their checks before you call a piece safe" about a
queen that had no guard at all. When nothing guards the piece the check is not
why it fell. The check now earns a shape only where it does real work.

## Getting it onto the screen — three wires, not one

The facts being right bought nothing on their own. The first render through
`build_move_teaching_decision` carried the clause on **3 of 10** cards where it
was set, and chasing the other seven found three separate reasons.

**1. The lead slot and the failure slot are rival families.** There are
`*_with_lead` variants and `*_with_failure_*` variants and **no variant carries
both**, so whenever a failure clause fires it takes the sentence and the lead
has nowhere to go. The failure clauses those cards got state the effect:

```
"lets Rxb2 win your bishop on b2"
"it drops the knight after Bxf4"
```

which is the symptom. So the fix is not a fourth variant saying both things in
two half-sentences — it is to make the failure clause itself carry the cause,
with the payoff still named, in one clause: `failure_abandoned_own_guard`,
placed directly above `failure_allows_capture`. Several cards were saying BOTH
halves badly before, and now say one thing well:

```
WAS: Ng3 is a major blunder — it drops the pawn after dxc3 — you moved your
     knight away from defending c3. Bxc6 was better — ...
NOW: Ng3 moved the knight that was guarding your pawn on c3, and dxc3 wins it.
     Bxc6 was better — ...
```

**2. Mohit's own card does not render through R12 at all.** With its real move
history it goes `R_TIER2_center → R_PROMOTED_basic_mistake`, whose variants had
no cause slot, so it read *"e5 is a mistake. a6 was better. Opening moves earn
their keep by controlling the center, developing a piece, or improving king
safety."* — a true sentence about nothing in that position. That rule needed
its own `with_abandoned_guard` variant, ranked above `with_board_state` and the
position-flavour variants. `with_losing_position` matters here: it renders
"doesn't change much here", which on a card where a pawn is verifiably lost is
not a softer truth but a wrong one.

**3. `promotion_facts` is a whitelist.** Even with the variant added, the
predicate could not be true, because `apply_promotion_ladder_dispatch` builds
an explicit dict of facts and anything absent from it is invisible to every
promoted rule. Six keys had to be added by name. This is the one that would
have been easy to miss: the variant existed, the facts existed, the rule fired,
and the card still said nothing.

Mohit's card now reads:

> e5 is a mistake — you pushed the pawn that was guarding your pawn on d5, and
> Nxd5 wins it. a6 was better.

A measurement note that cost an hour: the first drop diagnosis blamed
`R_VERIFIER_RECOVERY` on two cards. That was my harness passing a hardcoded
`user_color="white"` in games where the user is black, so the claim verifier
correctly rejected every "your <piece>" claim. With the colour derived from the
position, `R_VERIFIER_RECOVERY` disappears from this population entirely. The
verifier was never the problem.

## What is not done

**The opponent side.** The question fires on 24 of 811 opponent flagged cards
(2.96%) and the sentences render correctly with the possessives flipped, but
nothing carries them to a card. An attempt on 2026-10-21 added an
`opp_failure_abandoned_guard` variant plus a `teaching_principles` entry and
made 8 opponent cards read:

> "Opponent's Qxa7 is a major blunder. Before you move a piece, check what it
> is holding - and watch for the same slip from them. They missed Ra8 here."

The principle rendered and the failure clause did not, so the card led with
advice instead of saying what happened. Worse than before, so it was reverted
and `R12_blunder.json`'s opponent half is untouched. The opponent sentence is
built from `opp_failure_clause` and its variant selection needs understanding
first. Mohit asked for both sides explicitly, so this is owed.

**Two cards in the sample lost content** to the word cap when the new clause
displaced longer text — e.g. `Rd8` dropped "You attack a2 more often than they
defend it. That is how a weak pawn falls." Worth a look at whether the cap
should prefer the cause over the trailing principle.

## Gates

1. ~~Control written before the rate~~ — 24 + 17 tests.
2. ~~Every claim re-verified on the board independently~~ — 10/10.
3. ~~Fire rate and good-move lift~~ — 3.17% / 1.27% / 3.6x.
4. ~~Make the clause survive to the screen~~ — three wires, above.
5. ~~Corpus diff showing which caption text moves~~ — see the commit message.
6. Caption text reviewed by Mohit before it reaches a player. **OWED.**

## Open questions for Mohit

1. The "still had help and fell anyway" family is the half the shipped clause
   cannot see. Is "your pawn was short of help" the right way to say that to a
   1200, or does it want the reason the help did not arrive?
2. On an opponent card the principle reads "before you move a piece, check what
   it is holding" — addressed to the reader, about a move they did not make.
   Right, or should the opponent card teach the punish instead?
