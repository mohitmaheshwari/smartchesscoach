# Explain The Move You Played — Scope

**Status:** DRAFT, awaiting Mohit's sign-off. No code until then.
**Date:** 2026-10-29
**Author:** Claude. Every number here was measured against prod on 2026-10-28/29.
**Scope widened 2026-10-29** on Mohit's instruction — "not just mistakes,
inaccuracies too". The numbers below were re-measured for it, and they got
worse: inaccuracies are the majority of faulted cards and the quietest.

---

## Why this, why now

Mohit, on an opponent card in game `461511c5`:

> "it tells my move both captions and arrow, but doens't tell why their move
> is bad, you know?"

That is not one bad card. Measured by **re-rendering 25 of his games through
`generate_game_decryption_v5` on prod at the code that is live today**
(`V5_COACHING_VERSION` 237, LLM polish off, no persistence) and reading every
faulted card that came out — 605 cards:

| grade | cards | explains your move | names a better move only | neither |
|---|---|---|---|---|
| you inaccuracy | 166 | 11% | 12% | **77%** |
| them inaccuracy | 162 | 10% | 18% | **72%** |
| them mistake | 100 | 39% | 40% | 21% |
| you mistake | 89 | 21% | 44% | 35% |
| you blunder | 24 | 58% | 25% | 17% |
| them serious | 23 | 35% | 43% | 22% |
| them blunder | 21 | 67% | 14% | 19% |
| you serious | 20 | 50% | 30% | 20% |
| **all faulted cards** | **605** | **23%** | **25%** | **52%** |

Two things fall out of that table, and the second is new:

1. **The worse the move, the better we explain it.** 67% on their blunders,
   10% on their inaccuracies. The machinery works where the punishment is
   violent and goes quiet where it is not.
2. **Inaccuracies are 54% of all faulted cards (328 of 605) and three
   quarters of them say nothing at all.** Not "names a better move instead" —
   *nothing*. That is the single biggest block of silence in the product, and
   it is the band Mohit asked to include.

Excluding inaccuracies, the mistake-and-worse bands explain 37.5% — which
agrees with the 39.5% measured a day earlier over a different sample (471
queue positions, mistakes and blunders only). The two samples are not the
same games, so the agreement is a sanity check on the classifier, not a
second measurement.

A player who is told "Qd8 would have made things harder for your opponent"
learns a move. A player who is told what their own move gave away learns a
rule. The second is the product. A player told neither has been handed a
grade and no coaching at all.

---

## The cause, measured

There are **two** causes, and the second only appeared once inaccuracies were
measured. Both were measured on the same 25 games as the table above, from the
stored rows, by
`scratchpad/punishment_shape_by_grade.py` and `scratchpad/noline_probe.py`.

### Cause 1 — the fault clause needs a loud punishment

The sentence that explains a played move is built by `reply_gap_sentence` in
`caption_pipeline.py` (line 4087). It requires two facts:

```python
reply  = gap.get("their_reply")
allows = gap.get("allows") or []
if not reply or not allows:
    return ""
```

`allows` only ever holds `check` or `capture`. So the clause can describe a
punishment that gives check, or one that takes something, and nothing else.

What the punishments actually are — the engine's first reply to the move that
was played, pushed on the board and classified, 598 faulted rows:

| grade | faulted | check | capture | quiet | no stored line |
|---|---|---|---|---|---|
| them inaccuracy | 167 | 2% | 11% | 38% | **49%** |
| you inaccuracy | 152 | 2% | 22% | **58%** | 18% |
| them mistake | 98 | 9% | 31% | 60% | 0% |
| you mistake | 91 | 9% | 29% | 62% | 1% |
| them serious | 25 | 20% | 44% | 36% | 0% |
| you blunder | 23 | 39% | 30% | 30% | 0% |
| them blunder | 22 | 32% | 36% | 32% | 0% |
| you serious | 20 | 10% | 25% | 65% | 0% |
| **all** | **598** | **8%** | **23%** | **51%** | **18%** |

Only **39% of your blunders** are punished by a check, and that is the best
case in the whole table. Across all 598 faults, 51% of punishments are quiet
— nothing for the clause to hold. That is why the explains-rate tracks
severity: a blunder is more likely to be answered by force, so it is more
likely to be explainable, which is an accident of the gate rather than a
coaching decision.

This is `c6` exactly. After `1.e4 e5 2.Nf3 c6?!` the punishment is `3.d4`:
no check, no capture, nothing for the clause to hold, so the card graded the
move and then talked about a different move instead.

### Cause 2 — half the opponent's inaccuracies have no engine truth at all

**81 of 167 opponent inaccuracies (48.5%) have no `pv_after_played`**, so
there is no reply to describe, loud or quiet. 80 of those 81 are
`derived: "user_evals"` with `engine_backfilled: None` and no `best_move`.
Every opponent mistake, serious and blunder row has a line — 145 of 145.

The reason is a threshold, not missing machinery. The backfill I ran on
2026-10-28 takes `--min-cp`, defaulting to **100**
(`backend/scripts/backfill_opponent_fault_lines.py:95`, skip at :121) — the
mistake floor. Opponent inaccuracies sit at 30–99cp and were excluded by
design.

So roughly half of the worst band in the product is silent because nobody
asked the engine. Re-running the existing script at `--min-cp 30` fills it.
That is step zero of this work and it needs no new code.

---

## Third pass, 2026-10-29: the instrument was starved, and two of my three bugs were mine

> **Everything in the two sections below is measured from a contaminated
> render.** Read this section first. It says which claims survive, which are
> retracted, and which are being re-measured. The old text is left in place
> because a wrong number is corrected, not deleted.

`generate_game_decryption_v5` merges the opponent eval rows with
`await db.game_analyses.find_one(...)`
(`backend/services/game_decryption_v5_service.py:3338`), inside a bare
`except Exception` that falls back to `[]`. My harness passed a **sync
pymongo** client, so that `await` raised `TypeError` on a dict, the handler
swallowed it, and **every opponent row was discarded** — no `best_move`, no
PV, no `cp_loss`. Production uses motor (`server.py:54`). Opponent cards are
about half the corpus, so half of the 619 was measured against a render with
no engine truth on that side at all. Proved by re-running the same trace with
both clients: with pymongo every opponent call reaches the severity gate with
`best_move_san=None`; with motor the same calls get `Qe2`, `Nc4`, `Kg4`,
`Nge5`, `Qxe6+`, `Qd3+`.

**Retracted — `R01_mate→VERIFY_SOFTENED` is not erasing mates.** I reported
that on `game_74fdbd74c468` m44 the floor replaced a deliverable mate with
*"Your opponent repositions the pawn; a more active try was available here"*.
The **stored production card** for that move reads *"Your opponent played e7 —
it allows Qh1#, which is checkmate. Qd3+ was stronger: it gives check, forcing
you to respond."* The softening marker is in the stored rule chain, but it
landed on a different sentence and the mate survived. The bad text existed
only in my harness, because the facts reached the verifier empty for exactly
the reason above. No product change needed; nothing to fix here.

**Retracted in part — "30 of 619 cards fault the engine's own top move."**
20 of the 36 were opponent cards whose gate had nothing to compare, so that
number is not a product measurement. The depth-18 re-check was sound; the
population it ran on was not.

**Survives, and is now measured on stored production rows instead.** There is
a real bug, and a narrower one. **A card ships two grades.** `severity` passes
five sanity gates. `severity_canonical` was re-derived from raw `cp_loss` at
the card dict (`_practical.canonical_tier`) and passed **none** of them. And
`frontend/src/lib/moveSeverity.js` `gradeOf` prefers `severity_canonical`
whenever `severity` reads good — a rule added on 2026-10-28 for the real case
where practical softening files an inaccuracy under good. So the UI undid every
gate: best-move-equals-played, mate delivered, mate still forced, forced
recapture, book move.

Traced by intercepting `compute_severity_for_move` rather than reading the
code, then confirmed against the stored card:

| stored card | `severity` | `severity_canonical` | what the player reads |
|---|---|---|---|
| m44 `Qh1#` (checkmate) | `good` | **`blunder`** | blunder |
| m28 `Nc4` (engine's top move) | `context` | **`inaccuracy`** | inaccuracy |
| m34 `Kf7` (real 89cp inaccuracy) | `good` | `inaccuracy` | inaccuracy ✓ |

Over **500 stored games / 29,802 cards**: 3,054 at risk, **2,746 of them
legitimate** — the band and practical softening put a real inaccuracy under
good deliberately, and recovering it is what that field is for — and **308
wrong**: 275 where the played move IS the engine's best, 33 where the move is
checkmate. **1.03% of cards, 0.62 a game.** A lower bound, because only two of
the five gates are visible in stored data.

The fix is not "gate harder", because the two kinds of gate mean opposite
things:

- a **sanity** gate says the engine did not fault this move — the grade itself
  was wrong, so canonical must follow it;
- a **presentation** gate says we choose not to lead with it — the grade
  stands, and reaching past it is the whole purpose of the field, so canonical
  must not follow, or those 2,746 real inaccuracies stop being recoverable.

Shipped as **v238** (`b5781e2e`), with
`backend/tests/test_canonical_severity_respects_gates.py` locking both
directions and the presentation gate as the negative control. Stored reviews
re-render on next view.

**Being re-measured:** the 4-way caption split, the `R12_blunder` share, the
`R_TIER2_outpost` praise case, and the "31% of the inaccuracy band at or below
39cp" figure all came from the starved run. Re-running the same 25 games with
motor; the table below stands only until that lands.

---

## Re-measured 2026-10-29 (second pass), and it changed the plan

> Superseded in part by the third pass above — the numbers in this section
> were rendered without the opponent eval rows.

The first split used a predicate that lived in a command line. Written down
as `scratchpad/classify_v2.py` and re-run over 619 faulted cards from the
same 25 games, two things changed.

**The first predicate was wrong.** It checked whether a recommended move was
legal in `fen_before`. On an opponent card the recommendation is the *user's
reply*, legal in `fen_after`, so every "Your opponent played Bg3. That was a
mistake. Play f5." scored as saying nothing — which made their blunders look
like the least-explained moves in the game. Same wrong-board class as the
other four instrument bugs this week.

**Three buckets could not separate the two whys**, and that separation IS
the complaint:

| the card says... | cards | share |
|---|---|---|
| **fault** — what the played move did or allowed | 93 | **15%** |
| opportunity — why the recommended move is good | 173 | 28% |
| recommend — names a move, no reason at all | 204 | 33% |
| nothing | 142 | 23% |

So the product does explain things; it mostly explains *the other move*.
61% of faulted cards either name a move with no reason or say nothing.

**One rule owns the surface.** `R12_blunder` produces **406 of 619 cards
(66%)**, and splits 13% fault / 37% opportunity / 43% recommend / 7%
nothing. Any change here is one template, not twenty.

**And `facts:*` captions are a fifth category.** "Bxe6 takes your bishop,
but your queen and your pawn can take back — an even trade" describes what
their move did and never says why it was an inaccuracy. It reads approvingly
of a move the engine docks. Describing is not faulting.

---

## Step zero changed: stop grading non-mistakes as mistakes

> Superseded in part by the third pass above. The reasoning holds and the
> step shipped as v238; the specific counts below were rendered without the
> opponent eval rows, and the honest numbers are 308 of 29,802 stored cards
> (1.03%, 0.62 a game) rather than 30 of 619.

The negative control every candidate predicate must pass — *fires on the
fault, stays quiet on the engine's own move* — was never pointed at the
severity grade itself. Pointing it there:

- **36 of 619 faulted cards fault a move equal to the stored `best_move`,
  and a fresh depth-18 Stockfish confirms 30 of them ARE the top move.**
  Verified by re-running the engine on each card's own FEN
  (`scratchpad/verify_engine_move.py`), not by trusting a stored field.
- The captions say so under a fault grade: *"Nc6 is the best move in this
  position."* → `you inaccuracy`. *"Qh1#. Checkmate."* → `you blunder`,
  cp_loss 0, played move identical to best.
- Of 328 inaccuracy cards, 32 (9.8%) are the engine's own move and **102
  (31%) sit at or below 39cp** — at or under the canonical 30cp floor, and
  inside the noise of a difference between two searches.

This reorders the work. Mining explanations for the inaccuracy band before
gating the grade would hand agents positions where the move was fine and ask
them why it was bad — which is how a mining run produces fiction. Subtract
the non-mistakes first; then the residue is worth explaining.

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
wrong move.

**Step 0, before any of it: give the opponent's inaccuracies engine truth.**
`backfill_opponent_fault_lines.py --min-cp 30`, which is an existing,
already-run script with a different number. 48.5% of opponent inaccuracies
currently have no line to explain from, and no rule below can fire without
one. This is measured, cheap, and has to happen first or every number after
it is measured against missing data.

Then three sources, in order, all board-checkable:

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

One number, measured the same way before and after, by re-rendering the same
25 games through `generate_game_decryption_v5`:

> of faulted cards, the share that say what the played move did wrong

Today: **23%** (138 of 605). Reported **by grade**, never as one blended
number — the grades differ by a factor of six (10% on their inaccuracies,
67% on their blunders) and a single average hides the band that matters most.

Three sub-targets, in the order they should move:
1. **them inaccuracy, 10%** — half of it is the missing backfill, so this
   should move first and furthest for the least work.
2. **you inaccuracy, 11%** — 58% quiet punishments, 18% no line. This is the
   band that needs the new sentences.
3. **you mistake, 21%** — 44% of these already name a better move, so the
   card is there and only the fault clause is missing.

Three guards:
- the claim verifier must pass every new sentence, on the board the claim is
  about — four instruments mis-resolved that board this week, including mine;
- **the word cap will eat the new clause.** Not a prediction: the 25-game
  re-render that produced the table above printed
  `caption truncated: rule=distilled:opp_luft 70 words -> 52 (cap 60);
  dropped: 'Lesson: a small, quiet pawn move is slow, so use your turn to
  bring a piece out instead.'` The cap cut at the last sentence boundary and
  deleted the one sentence that taught anything. Any added clause is measured
  against `max_caption_words`, and if the cap has to choose, it must drop the
  move recommendation before the lesson;
- the measurement must be a re-render, never the stored cards. Counted over
  the whole collection on 2026-10-29: **18,561 of 19,576 `game_analyses`
  (94.8%) hold cards rendered at v230**, against code at v237 — plus 437
  unset, 418 at v233 and only 40 at v237. A query against stored caption
  text measures a product seven versions old. (An earlier draft of this doc
  said "113 unset and 87 at v230"; that was one user's games read as the
  collection, and it was wrong by two orders of magnitude.)

  The same fact is the good news about shipping: the lazy path re-renders
  whenever the stored version is behind the code's, so a fix reaches those
  18,561 games on next view without a migration.

---

## The on-demand button has the same gap, and answers anyway

The "why, with engine" button (`/api/.../why/{game_id}/{move_number}`,
`services/why_on_demand.py`) is the escape hatch for exactly these cards: it
runs a fresh search and explains. It has the same blind spot, and it does not
go quiet — it finds the nearest move it *can* describe and talks about that
one instead.

Traced on `1.c4 e5 2.Nc3 Nf6 3.g3 Bc5 4.e4` (FEN
`rnbqk2r/pppp1ppp/5n2/2b1p3/2P5/2N3P1/PP1PPP1P/R1BQKBNR w KQkq - 1 4`), by
running the endpoint's own logic with its own constants:

```
engine offered : Nf3 +34 | Bg2 +31 | d3 +16 | a3 +10 | e3 0 | Na4 -7 | ...
answer         : "Na4 chases their bishop."   mechanism FORCES_RETREAT
arrows         : c3->a4, c5->e7, f1->g2
```

`Nf3`, `Bg2`, `d3`, `a3` and `e3` are quiet developing moves with no
mechanism, so all five were skipped. `Na4` is the engine's **sixth** choice,
41cp below `Nf3`, and it won by being explicable. Three gates let it through:

- `CANDIDATE_COUNT = 8` — it looks eight deep for something to say;
- `CLOSENESS_CP = 50` — anything within 50cp of best is treated as
  interchangeable, and 41 < 50;
- `FORCES_RETREAT` pays a tempo proxy, `max(1, value // 10)`, so
  `_explains_the_loss` (which demands a mechanism cover 25% of the loss)
  barely tests it. A material mechanism has to earn its sentence; a
  "chases their bishop" answer effectively does not.

A confident wrong answer with arrows is worse than silence, because the
player cannot tell. Two cheap fixes, either acceptable: name the top move in
the sentence when the explained move is not it ("Nf3 was the move; Na4 also
chases the bishop"), or refuse when the gap is non-zero *and* the mechanism
is a tempo proxy rather than material.

Not verified: whether this misranking is common or specific to quiet opening
positions. It was traced on one position Mohit supplied. What would settle it
is running the endpoint's candidate loop over the 598 faulted rows above and
counting how often the kept candidate is not the top one.

---

## Open questions for Mohit

1. **Is a quiet punishment worth a sentence at all?** 51% of all faults are
   answered by a quiet move. "That lets them play Nd5, hitting your bishop"
   is true and may still read as weak coaching.
2. **Which of the three sources first**, if they disagree on one card?
3. **Teachability** — some board facts are true and useless ("your king's
   mobility fell by 2"). That call is yours per concept, not mine.
4. **New: should an inaccuracy get a card at all?** 328 of 605 faulted cards
   are inaccuracies, so including them doubles the surface. The alternative
   is to say nothing on a 30–99cp drift and spend the work on the mistake
   bands. You asked for inaccuracies in, so that is what this scope covers —
   but it is the one decision that changes the size of the job, not just its
   quality.
5. **New: when the cap has to choose**, does the lesson sentence beat the
   move recommendation? The cap already dropped a whole `Lesson:` line in the
   measurement run above.

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

Added 2026-10-29, for the inaccuracy band:

- 25 games re-rendered through `generate_game_decryption_v5` at v237, LLM
  polish off, nothing persisted → 605 faulted cards, split by grade
- the same 25 games' stored rows, graded by canonical
  `services.severity.classify_severity` → 598 faulted rows. The two counts
  agree grade by grade to within a few cards, which is what says the render
  table and the punishment table describe the same population
- opponent rows are a **separate array** (`opponent_move_evaluations`). The
  first run of the punishment script read `move_evaluations` alone, trusted
  its `is_opponent_move` flag, and produced a table with no opponent rows at
  all — it would have reported the user half as the whole product
