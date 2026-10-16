# Canonical coaching profile — player 8b599930d7ef

**Status: canonical, revision 3.** Supersedes the earlier profile, capability
report, investigations and integrity notes, **and revisions 1 and 2 of this
document.** §2 lists the measurement defects; §3 lists every withdrawn claim.
Read-only throughout: no code, production write, deployment or migration. No
candidate file was copied into any container. §9 is the coaching brief.

**His stated position** (self-report, 2026-10-15, not independently verified):
target around 2000; feels stuck near 1300; relies on gut feel with limited
calculation; believes stronger opponents understand things he does not.

**Revision 3 exists because revision 2's headline did not survive its own
controls.** Revision 2 claimed his error rate triples when he is ahead and
called that the mechanism of his plateau. Controlling for phase and clock —
and measuring how many good moves each position actually offers with Stockfish
— **that effect largely dissolves.** What survives is narrower, less dramatic
and more useful: §4.7.

---

## 1. Scope and reconciled denominators

De-duplicated by platform game id (`games.url`), falling back to a normalised
move-sequence hash — which matters, because coach games carry no `url` and 24
of them are duplicates only the hash catches.

| | Count |
|---|---|
| analysed game records | 850 |
| duplicates dropped | 43 |
| **distinct analysed games** | **807** |
| coach games — **excluded from every outcome figure** | 113 |
| **rated games (chess.com 590, lichess 104)** | **694** |
| rated: won / lost / drew | **318 / 356 / 20** |
| rated win rate | **46%** (47% of decided games) |
| his moves, all games | 21,846 |
| his moves, rated | **20,656** |
| his moves, rated, with an eval and mates removed | **19,378** |
| window | 2026-02-23 → 2026-10-15 |

A **RECENT** window (100 distinct games, 2026-09-01 → 10-15, 2,996 moves;
lichess 87, coach 9, chess.com 4) is used only where a surface logged nothing
earlier, and is labelled where used.

**Every figure in §4.6, §4.7 and §4.9 is rated-only.** Revision 2 reported
conversion and loss shapes over all 807 games and 457 losses while §1 said
coach games were excluded; that contradiction is resolved here — the losses
denominator is **356**, not 457.

**Engine use.** Move quality comes from stored `move_evaluations`. Revision 3
adds direct Stockfish 17.1 work, labelled at each use: a 859-position
full-multipv scan at depth 12 (§4.7), a 520-position scan at depth 12 (§4.9),
and depth-14 verification of 240 individual errors (§4.7) and of the item-4
examples (§4.6).

**Evidence classes:** **observed** (board-verifiable or a stored engine
figure), **supported** (several independent sources agree), **hypothesis** (one
plausible reading among others), **unknown**.

### Excluded, with reasons

| Source | Why |
|---|---|
| mastery stamps (`mastered_at`) | all 33 surviving stamps sit on concepts the product **never showed him** |
| `shown_count` | a per-render `$inc`, not exposure |
| my fork-availability detector | fired in 19.5% of positions |
| my hanging-piece detector | engine disagreed on 2 of 5 sampled cases |
| `missed_generic_tactic` (42), `generic_endgame_slip` (17), `generic_oversight` (10) | "generic" means the detector could not name the motif |
| `puzzle_attempts` `weakness_type: unknown` (16, 0 correct) | `moves_tried: []`, no time recorded — no move was submitted |
| `coaching_profile.preferred_learning_style` | `"practice"` on all 128 users; an unmeasured default with no reader |
| `decision_register` | misaligned index join; 78.5% of verdicts change when fixed |
| chess.com opponent-strength bands | circular, see §4.9 |
| **coach games, in any outcome comparison** | they never record a win — see D3 |

---

## 2. The three measurement defects

### D1 — the coach's own moves were counted as his

`is_opponent_move` is `True` on 122 rows, `False` on 12,923, and **absent
(`None`) on 10,006**. The filter was `not m.get("is_opponent_move")`, and
`not None` is `True`.

On chess.com and lichess this is harmless — only his moves are stored, and a
flag filter and a board-turn filter return **identical** counts (17,367 and
3,289). On **coach** games both sides are stored with the flag absent, so
**1,083 of the coach platform's 2,273 rows were the engine's moves**, across
**106 of 113 coach games**. The signature: 91 games with rows numbered
`[1,1,2,2,3,3,4,4,5,5]`.

Corrected by filtering on whose turn it is on the stored board:

| | revision 1 | corrected |
|---|---|---|
| his moves | 22,929 | **21,846** |
| rows numbered 1–5 | 4,406 | **3,954** (ceiling 4,035) |
| games exceeding 5 such rows | 91 | **0** |

### D2 — the mate sentinel was inside every average

Evaluations are stored to ±10,000 with mate in the top band (406 readings at
9,990, 307 at 9,980, …); **2,179 of 43,692 readings are ≥9,000**. All-rows
mean 178.1cp against **ordinary-only 60.1cp**.

And **most mate rows are not errors.** Of 1,278 mate rows, by `mate_info`
transition (white-relative, signed, 0 = delivered):

| transition | rows | mean cp_loss | error? |
|---|---|---|---|
| kept his forced mate | 488 | 6 | no |
| already being mated | 292 | 13 | no |
| **let a mate in** | **225** | **7,551** | **yes** |
| **delivered mate** | **120** | 0 | no — a success |
| **gave up a forced mate** | **117** | **6,730** | **yes** |
| created a forced mate | 35 | 0 | no — a success |
| swapped his mate for theirs | 1 | 19,980 | yes |

**343 mate errors; 643 mate-neutral-or-good rows.**

### D3 — coach games sat in the won/lost split

Coach games record a win **0 times in 113**. Revision 2 named this defect but
applied it only partly; revision 3 applies it everywhere. Removing them
changed the loss-shape distribution materially (§4.7).

### A fourth thing, corrected rather than defective

The stored eval perspective is **white-relative**, not unusable as revision 1
said: white won median +9,975 / 98% positive; black won median −460 / 36%
positive; black lost median +842 / 89% positive. It must be flipped for black.
The **final** stored eval does not predict the result, because his games end by
resignation, timeout and abandonment far more often than by the board.

---

## 3. Superseded and withdrawn

Carried forward:

| Earlier claim | Status |
|---|---|
| "he has a capture-consequence habit" | **withdrawn.** Opportunity-adjusted preference 0.78× — and §4.6 now shows *declining* a best capture costs him more |
| "`time_flag` is miscalibrated" | **withdrawn.** 0.56% firing is by design |
| "knowledge is there, execution is not" | **withdrawn as premature** |
| "his queen had six safe squares" | **withdrawn.** Depth 20: `bxc5` was best of all 38 legal moves |
| "he left a rook hanging and ignored it" | **withdrawn.** His own knight was the shield |
| "never castles in 41 of 100 games" | **withdrawn.** Disjoint recount: 2 |
| "87% right kind of move" | **withdrawn.** `decision_register` index join |
| "most games have no opening identified" | **corrected.** chess.com 98% named, lichess 0% |
| "accuracy collapses through the game (19.4 → 324.0cp)" | **withdrawn (D2).** One step at move 6, then a plateau |
| "his games are decided at moves 6–11" | **withdrawn.** 79% recover; only 9% are clearly losing after it |
| "endgames: a 3.5× spread between endings" | **withdrawn (D2).** 58–68cp in every ending |
| "he plays more accurately in lichess blitz" | **withdrawn (D2).** 59–61cp everywhere |
| "lichess mean loss fell 61% while his win rate stayed flat" | **withdrawn (D2). There is no improvement trend** — he is flat on both platforms |
| "clock coverage is 10%" | **withdrawn.** 587 of 590 chess.com PGNs carry `%clk` |
| "nothing stores a *what did you see* answer" | **withdrawn.** `reflection_sessions` holds 9 |
| "castling: 74% in wins vs 59% in losses" | **withdrawn (D3).** Rated: 74% vs 71% |
| "the ±1500 eval clamp destroys peak-to-trough" | **withdrawn.** No such clamp |

New in revision 3 — **revision 2's own headline**:

| Revision 2 claim | Status |
|---|---|
| **"his error rate triples when he is ahead — 5.5% at level against 16.5% when clearly better"** | **the numbers stand; the interpretation does not.** Advantage positions occur at median move 18 against move 7 for level positions, and with 372s of clock against 544s. Controlling for phase, the gap at moves 16+ is **12.1% vs 15.7%**. Controlling for phase *and* clock, at moves 16+ with over 3 minutes left, it is **13% vs 13% — no gap at all.** Most of the raw effect was comparing his openings with his middlegames |
| **"he is losing games he has already won"** | **withdrawn.** A +300 position is won 64% of the time and a +500 position 73% — a third and a quarter respectively are *not* won. The phrase asserts something the data denies |
| **"this is where his rating is going / the mechanism his self-report is reaching for"** | **withdrawn as unsupported.** No mechanism was established. Complacency, unfamiliarity with sharp conversion and the positions simply being narrow are all consistent with the observations |
| **"he does not slow down in the sharpest positions"** (the \|eval\| ≥ 500 timing table) | **withdrawn as stated.** Large absolute evaluation is not decision difficulty, so that table could not support the claim. §4.9 re-tests it against an engine difficulty measure and finds a narrower version that *is* supported |
| **"timeouts are the consequence of a bad position, not an independent clock failure"** | **overstated.** The full distribution (§4.9) shows he had over 3 minutes at the moment his position first went bad in 77% of timeout losses — but was already under 2 minutes in **17%**, against 7% of resignation losses. Clock pressure contributed earlier in a measurable minority |
| "no positional measure separates his wins from his losses" | **corrected in emphasis.** True of the twelve *averages*, but averages cannot rule out positional weakness. §4.6 now examines decisions, and finds recurring ones with measured costs |

**One finding killed before it reached print.** A 43-game Giuoco Piano family
showed 9 wins and 31 losses — a 21% win rate. **20 of those 43 were coach
games.** Rated: 9–10, 47%, exactly his baseline.

---

## 4. The player, by area

### 4.1 Opening repertoire, and what happens when familiar moves end

**His repertoire, reconstructed from move sequences** (lichess stores no opening
name on any of his 104 games; `opening_key` is set on 8 of 20,293 games
product-wide):

| First four half-moves | Games |
|---|---|
| **W** `e4 e5 Nf3 Nc6` | **133** |
| **B** `e4 e5 Nf3 Nc6` | **96** |
| B `e4 d5 exd5 Qxd5` (Scandinavian) | 37 |
| W `e4 e5 Nf3 d6` | 33 |
| W `e4 d5 exd5 Qxd5` | 24 |
| B `e4 e5 Bc4 Nf6` | 19 |

An open-games specialist on both sides — `1.e4` and `1…e5`, heading for the
Italian, Scandinavian in reserve. Narrow and consistent.

**What he does well.** Moves 1–5: **21.6cp mean loss, median 1, a 1% blunder
rate, zero mate errors** over 3,954 moves.

**One discontinuity, then a plateau:**

| His move numbers | Moves | Mean cp | Median | Blunder rate | Mate errors / 1000 |
|---|---|---|---|---|---|
| 1–5 | 3,954 | 21.6 | 1 | **1%** | 0.0 |
| **6–10** | 3,602 | **59.3** | **19** | **8%** | 1.4 |
| 11–15 | 3,230 | 68.2 | 16 | 10% | 6.5 |
| 16–20 | 2,831 | 72.3 | 16 | 11% | 16.6 |
| 21–30 | 4,263 | 70.4 | 15 | 10% | 30.0 |
| 31+ | 3,966 | 77.5 | 1 | 11% | 35.8 |

**Supported:** a single sharp step at move 6 — blunder rate ×8, median loss ×19
— and after move 10 a **constant** level. The only thing that keeps rising is
mate errors, a property of games reaching a decided state.

**It does not decide his games.** First 100cp+ error at median move **8** (p25/p75
6/11; 73% by move 10; 693 of 807 games have one, 114 have none). Immediately
after it: still clearly winning **102 (15%)**, still level **218 (31%)**, worse
but playable 303 (44%), clearly losing 63 (9%), a mate error 7 (1%). And of the
300 games where it left him at −100 or worse: **recovered to level or better
236 (79%)**, never recovered 55 (18%), clawed back part 8 (3%).

**Representative.** Recovered: `5c3d7a49` m7 `Nxd7` → −125, later mated, won.
`73140de9` m7 `Bh5` → −184, won by checkmate. Never recovered: `7d2c3b44` m11
`b4` → −363, best later −345, lost; `0f00953e` m3 `Qg5` → −156, best later −170,
lost — genuinely decided at move 3, 47 moves before the end.

**No opening family stands out.** Folding transpositions by keying on the
*position* after three full moves, eight families have ten or more decided rated
games; win rates span **32–58% around a 47% baseline** on 13–26 game samples,
mean cp at moves 6–15 spans 55.8–74.8, and the median first error is move 7–11
in **every one**. The move-6 problem is general, not repertoire-specific.

**Unknown.** Whether his errors cluster on a recurring structural motif rather
than a move order — position-keyed families are too fine-grained to say.

### 4.2 Tactical recognition

Opportunity-paired, rated games, turn-filtered, full corpus:

| | Available | Taken | Rate |
|---|---|---|---|
| mate in one | 163 | **120** | **74%** |
| a free undefended piece worth 3+ | 1,657 positions | **1,314** | **79%** |

246 of the free-material chances arose while he was in check.

**What he played instead of mate**, across the 47 missed mates in one:

| Instead of the mate he played | Count |
|---|---|
| **a different check** | **27 (57%)** |
| something quiet | 13 (28%) |
| a capture | 7 (15%) |

Board-verified: `ad652319` m40 `Re4+` when `Rd4#` mated; `45f946c3` m21 `Bd7+`
when `Qd7#` mated; `0f24e0b6` m61 `Be6+` when `h7#` mated; `100897b9` m24
`Qe7+` when `Qh8#` mated.

**Prompted and untimed, he is stronger than his play.** 32 of 37 diagnostic
items exactly right, no alternatives accepted: fork 4/4, skewer 4/4, mate
patterns 4/4, discovered attack 2/2, calculation 3/3. The five misses cluster at
the top of the tested range (four of five at puzzle ratings 1193–1300).

**Counterexamples and limits.** 11 of 14 items rated 1200+. Low tier 21/22
against mid tier 11/15. `puzzle_attempts` is a different pool: 53 of 118
overall, `skewer` 8/9 and `fork` 10/14 but **`piece_safety` 9 of 24**, `pin` 0/3.

**Unknown.** Anything above a 1300 puzzle rating — nothing harder has been put
to him, while he plays in a 1490 lichess pool.

### 4.3 Calculation and anticipating the reply

**Does well.** The only user of the calculation instrument. His best attempt was
a real three-move line — `Kg8, Nd7, Qd3+` — **sound through 3 ply** against a
required depth of 2, and he judged the resulting position correctly in **both**
attempts where he was asked.

**Where it breaks down.** Four attempts across **two distinct positions**;
**three of four submissions were a single move** where the task asked for a
line; `stopped_early` fired once.

**Hypothesis, not supported — three independent legs.** That he commits once he
has *a* forcing move: the single-move submissions, **57% of missed mates being a
different check**, and the `Rh6+` sequence in §4.7. It stays a hypothesis
because a single-move submission may be an interface misunderstanding, he did
submit a real line once, and nothing measures his search directly. §4.7's
mechanism split gives it partial support and partial contradiction.

**Unknown.** `prediction_correct` is **null on all 232** lesson attempts — he has
never been asked in a lesson to predict the opponent's reply. Candidate-move
generation is recorded nowhere.

### 4.4 Threat recognition and defence

**Observed, over 4,342 rated positions** where one of his pieces worth 3+ was
attacked and underdefended: threat answered in **3,342 (77%)**; coach games
162 of 252 (64%).

`missed_pattern: king_safety` fires **112 times across 60 of the 100 RECENT
games** — his largest stored signal — `subtype: ignored_king_attack` 38 times in
29 games. Independently, `threat_response` is his **weakest prompted concept**:
5 of 7, and 2 of his 5 total diagnostic misses.

**Supported:** two instruments that share nothing both put threat handling at
the bottom. A 77% answer rate is nonetheless not a collapse.

**Unknown, and it decides the teaching.** Whether he fails to see the threat,
sees it and misjudges, or sees it and declines. §4.10's nine reflection answers
split 2–2 between the first two.

### 4.5 Planning and whether successive moves serve one objective

**His intended plan remains unrecoverable** from moves, and no instrument asks
for one: `user_misconceptions`, `home_today_answers` and `concept_tests` hold 0
rows, and `concept_used` is written **only on good moves**, so it can
congratulate and never show the converse.

What revision 3 adds is that the question is no longer *unexamined*. §4.6 moves
from averages to decisions and finds recurring, costed decision types. Those are
observable choices, not intentions, and they are reported as such.

### 4.6 Positional play, through actual decisions

**First, the twelve averages — a null that is real but limited.** Replaying all
694 rated games and reading the board, split by outcome:

| Measure | Won | Lost |
|---|---|---|
| minor + rook pieces off home by move 10 | 2.35 | 2.32 |
| move number he castled on | 9.54 | 10.01 |
| castling rate | 74% | 71% |
| queen moves in his first 10 | 0.83 | 0.75 |
| flank pawn moves (a,b,g,h) by m15 | 0.99 | **1.21** |
| centre pawn moves (d,e) by m15 | 2.80 | 2.64 |
| heavy pieces on an own-pawn-free file at m20 | 0.93 | 0.91 |
| undefended own pieces per position | 1.66 | 1.59 |
| captures per move | 0.273 | 0.233 |
| losing captures per move | **0.043** | **0.034** |
| checks per move | 0.115 | 0.054 |
| his moves in the game | 28.8 | 29.5 |

No average separates his wins from his losses. **But an average cannot rule out
a positional weakness** — a player can make the same number of pawn moves in
wins and losses and still choose the wrong ones. So:

**Second, the decisions themselves.** Every rated move where a stored
`best_move` could be resolved on the board — **19,378 decisions** — classified
by what kind of move he chose against what kind was best:

| Decision | n | Share | Mean cp lost | Blunder% |
|---|---|---|---|---|
| played the engine's move | 7,827 | 40.4% | 0.0 | 0.0% |
| moved a piece when a pawn move was best | 2,374 | 12.3% | 84.8 | 10.2% |
| put a knight/bishop where a pawn can hit it † | 2,166 | 11.2% | 71.1 | 9.3% |
| moved a pawn when a piece move was best | 1,726 | 8.9% | 99.8 | 14.8% |
| captured when the best move was not a capture | 1,349 | 7.0% | 118.2 | 18.4% |
| **declined a capture that WAS the best move** | **1,019** | **5.3%** | **161.7** | **26.5%** |
| checked when the best move was not a check | 597 | 3.1% | 104.7 | 16.4% |

† This row is not conditioned on deviating from best — it includes moves that
*were* the engine's — so its mean is diluted and it is not comparable with the
others. The other six are all deviations and are comparable.

**Supported:** of the ways he deviates from the best move, **declining a capture
that was best is the most expensive** — 161.7cp mean and a 26.5% blunder rate,
the highest of any category, over 1,019 instances. Capturing when he should not
is next (118.2cp, 18.4%) and is **1.3× more frequent** (1,349). Both matter;
the costlier one is the one revision 1 and 2 never looked for.

**This also closes the capture question for a third time.** Revision 1 claimed a
capture habit; the opportunity denominator refuted it (0.78×); §4.6's averages
showed losing captures are *more* frequent in his wins. Now the decision data
shows the larger cost sits on the other side — **not taking** when taking was
right.

**Engine-verified examples**, depth 14, with the two preceding moves and the
reply that punishes:

**Declined a capture that was best** (365 such moves cost 150cp+):
- `8516ea23` m33, after `31.Rb1 32.Ra1` — he played **`Bb4`**, appropriate was
  **`Bxa3`**; +768 → −580, cost 1,348cp; `Rb3` punishes it. Lost.
- `3a41fb4c` m28, after `26.Kf1 27.Qxb7` — he played **`R8e7`**, appropriate was
  **`Qxc7`**; +924 → −414, cost 1,338cp; `Qxc4` punishes it. Lost.
- `game_8e1294767490` m18, after `16.Nc7+ 17.Nxa8` — he played **`Qf3`**,
  appropriate was **`Bxd6`**; +455 → −775; `Qb4+` punishes it. Lost.

**Captured when the best move was not a capture** (346 cost 150cp+):
- `8519d4b8` m37, after `35.Kf1 36.Qc4` — he played **`Qxe5`**, appropriate was
  **`Kg8`**; +1130 → −364, cost 1,494cp; `Ng6+` punishes it. **He won anyway.**
- `ff3f130a` m18, after `16.Nc3 17.g3` — he played **`hxg3`**, appropriate was
  **`Re2`**; +403 → −700; `Qxg3+` punishes it. **Won anyway.**
- `7b2535a1` m15, after `13.Nf3 14.Qh4` — he played **`Qxh7`**, appropriate was
  **`Rd8+`**; +725 → −356; `Bxf3` punishes it. **Won anyway.**

**Placed a knight or bishop where a pawn can hit it** (313 cost 150cp+):
- `e5f72b71` m16, after `14.O-O-O 15.exd5` — he played **`Bf5`**, appropriate was
  **`Qf6`**; +304 → −945, cost 1,249cp; `Qxf7+` punishes it. Won anyway.
- `game_692ab776c5b1` m24, after `22.Rad1 23.Rfe1` — he played **`Neg4`**,
  appropriate was **`Qc6+`**; +570 → −567; `Qxc5` punishes it. Lost.
- `56b6c294` m16, after `14.e4 15.Kg2` — he played **`Ng5`**, appropriate was
  **`Bxc3`**; +615 → −287; `Rh1` punishes it. Won anyway.

**Observed across all three groups:** in every example the punishing reply is
the opponent's *immediate next move*, and in every case it is a capture or a
check. **Not intention — observable play.** What these decisions have in common
is one ply of unchecked consequence, not a strategic misconception.

**Style, opportunity-adjusted (RECENT).** He captures **4.14×** and checks
**2.84×** more often than the positions offer. Forward movement did not survive
the same test (1.10×).

**Unknown.** Pawn-structure *quality* as distinct from pawn-move direction; and
whether the flank-pawn difference (1.21 vs 0.99) is anything more than noise on
a 0.22-move base.

### 4.7 Converting advantages — what revision 2 got wrong, and what is left

**Conversion, rated only.**

| Reached | Games | Won | Lost | Drew |
|---|---|---|---|---|
| +300 or better (non-mate) | **442** | 282 (64%) | 144 (33%) | 16 |
| +500 or better | **314** | 229 (73%) | 77 (25%) | 8 |

**So a large evaluation advantage is not an already-won game** — a third of +300
positions and a quarter of +500 positions end in defeat. Revision 2's phrase
"games he has already won" is withdrawn.

**Loss shapes, 356 rated losses** (coach games removed, which changed this
materially — cliffs rose from 25% to 33% and the unclassifiable fell from 11% to 1%):

| Shape | Losses |
|---|---|
| one move ≥60% of the fall (**cliff**) | 116 (33%) |
| mixed | 90 (25%) |
| worst move ≤40% (**slide**) | 87 (24%) |
| no decisive fall (<200cp peak→trough) | 59 (17%) |
| too few non-sentinel evals | 4 (1%) |

Median **5** moves costing 100cp+ per lost game. A third of his losses have one
dominant move; two thirds do not.

**The raw band table, rated** — and the two columns revision 2 did not print:

| Position before his move | Moves | Mean cp | Blunder% | Median move no. | Median clock |
|---|---|---|---|---|---|
| losing badly (< −500) | 1,771 | 47.9 | 4.9% | 28 | 264s |
| worse (−500 … −100) | 3,632 | 59.6 | 8.3% | 18 | 390s |
| **level (−100 … +100)** | 7,933 | 42.4 | **5.5%** | **7** | **544s** |
| better (+100 … +300) | 2,115 | 81.8 | 12.3% | 13 | 484s |
| **clearly better (+300 … +500)** | 1,870 | 97.1 | **16.5%** | **18** | **372s** |
| winning (+500 … +1000) | 1,975 | 72.5 | 10.3% | 25 | 315s |

**Level positions are concentrated in the opening (median move 7) and come with
three minutes more clock.** Both are confounds, and both run the right way to
manufacture the effect.

**Control 1 — phase.** Blunder rate by band within move-number bucket:

| Band | moves 1–15 | 16–25 | 26–40 | 41+ |
|---|---|---|---|---|
| losing badly | 4% (153) | 4% (558) | 4% (743) | 8% (317) |
| worse | 8% (1386) | 8% (1337) | 8% (761) | 14% (148) |
| **level** | **3% (6008)** | **14% (920)** | 11% (632) | 9% (373) |
| better | 11% (1323) | 13% (515) | 17% (239) | — |
| **clearly better** | **18% (699)** | **13% (656)** | 16% (396) | 27% (119) |
| winning | 13% (294) | 10% (743) | 9% (716) | 13% (222) |

At moves 16–25 the gap is **14% level against 13% clearly better — reversed and
gone.** The 3%-versus-18% comparison that produced revision 2's headline was
largely his openings against his middlegames.

**Control 2 — phase and clock together.** Moves 16+ only:

| Band | clock > 3 min | 1–3 min | under 60s |
|---|---|---|---|
| **level** | **13% (1018)** | 12% (345) | 11% (342) |
| better | 14% (521) | 14% (118) | 17% (86) |
| **clearly better** | **13% (735)** | 18% (205) | **28% (158)** |
| winning | 8% (976) | 10% (285) | 16% (256) |

Pooled over moves 16+: level **12.1%** (n=1,925), better 14.6% (792), clearly
better **15.7%** (1,171), winning **9.8%** (1,681).

**With over three minutes on the clock and past move 15, level and clearly-better
are both 13%.** The advantage-specific effect is gone.

**Control 3 — how many good moves the position actually offers.** 859 positions
sampled across bands, Stockfish 17.1, depth 12, multipv over every legal move:

| Band | Positions | Avg legal moves | **% of legal moves that blunder** | His blunder rate here | Positions with only 1–2 good moves | His rate ÷ position's density |
|---|---|---|---|---|---|---|
| losing badly | 130 | 21.7 | 31.6% | 5.4% | 22% | 0.17× |
| worse | 130 | 30.9 | 49.1% | 4.6% | 25% | 0.09× |
| **level** | 130 | 33.1 | **40.0%** | 5.4% | **11%** | **0.13×** |
| better | 130 | 35.0 | 54.2% | 17.7% | 31% | 0.33× |
| **clearly better** | 130 | 34.7 | **69.6%** | 20.8% | **47%** | **0.30×** |
| winning +500–1000 | 130 | 34.9 | 57.0% | 10.0% | 37% | 0.18× |
| winning big > +1000 | 79 | 34.0 | 50.6% | 31.6% | 41% | 0.62× |

**Observed:** the positions where he is clearly better are intrinsically far
less forgiving. **69.6% of their legal moves blunder, against 40.0% in level
positions, and 47% of them have only one or two good moves against 11%.**
Converting an advantage means finding one of very few moves.

**Supported:** against what the position permits, he still degrades — 0.13× at
level to 0.30× when clearly better, a **2.3× relative** fall. That is real and
worth teaching to. It is **not** the 3× absolute collapse revision 2 reported,
and it is **not** evidence of complacency: nothing here distinguishes
complacency from inexperience with narrow positions, or from narrow positions
simply being hard. (The >+1000 row's 0.62× should be read cautiously — a 200cp
loss from +1500 often changes nothing, so the blunder threshold is less
meaningful there.)

**What he actually does in these positions — the counterexample set.** His
3,927 moves from a +300…+1500 position:

| Cost | Moves |
|---|---|
| engine-best or near (<50cp) | **2,614 (67%)** |
| 50–199cp | 776 (20%) |
| 200–399cp | 297 (8%) |
| **400cp+** | **240 (6%)** |

**He plays two thirds of his winning positions at or near engine strength.** The
problem is not his general handling of advantages; it is a 6% tail.

And that tail is where the games go:

| Of the 442 rated games that reached +300 | Games | Won |
|---|---|---|
| contained **no** 400cp+ slip from a winning position | **255 (58%)** | **78%** (199) |
| contained at least one | **187 (42%)** | **44%** (83) |

**Supported:** a single 400cp+ slip from a winning position is associated with a
**34 percentage-point** drop in conversion. This is the largest identified swing
in the profile, and unlike revision 2's claim it is a statement about
consequence, not about rates.

**The 240 slips: 240 moves in 187 distinct games.**

Immediate outcome:

| | Moves |
|---|---|
| position turned losing | 110 (46%) |
| advantage lost to equality | 97 (40%) |
| advantage reduced to +100…+300 | 19 (8%) |
| advantage reduced but still ≥ +300 | 14 (6%) |

What happened afterwards:

| | Moves |
|---|---|
| **later regained +300 or better** | **148 (62%)** |
| later got back to level | 48 (20%) |
| never got back to level | 35 (15%) |
| no later eval | 9 (4%) |

Final result of the 187 distinct games: **won 83 (44%), lost 94 (50%), drew 10**.
So 86% of these moves cost the advantage entirely or worse, yet he regained a
winning position in 62% of cases and still won nearly half the games. **They are
damaging, not fatal.**

**Mechanism, engine-verified at depth 14:**

| Mechanism | Moves | Median cost |
|---|---|---|
| **left material to the opponent's reply** (sub-split below) | **90 (38%)** | 475–676cp |
| unclassified | 72 (30%) | 529cp |
| **missed the forcing continuation** | **44 (18%)** | 539cp |
| **exchange decision** (two shapes below) | **34 (14%)** | 621–768cp |

The material group: left a piece to the reply 52, moved a piece into a loss 10,
moved a defender away 10, unsafe check left a piece loose 9, lost a pawn to the
reply 9. The exchange group: his capture let a bigger one back 18, a recapture
won material 16.

**Supported:** the single commonest way his advantages disappear is **leaving
material to the opponent's immediate next move** — 38% of cases, and the
examples in §4.6 show the punishing reply is always one ply deep and is always a
capture or a check. The second is **missing the move that would have ended the
game** (18%). Exchange errors are third (14%). Thirty per cent resist
classification by these rules and are left unclassified rather than forced into
a category.

**Partial support and partial contradiction for the forcing-move hypothesis.**
"Missed the forcing continuation" at 18% fits it. But 38% is the opposite shape
— he played a move and did not check the reply, which is a failure to look
*forward* rather than a premature commitment to a forcing move. Both are
"one ply of unchecked consequence"; neither establishes the other.

**Representative sequences**, with the two preceding moves:
- `3a41fb4c` m28, after `26.Kf1 27.Qxb7` — `R8e7` at +924, best `Qxc7`; cost
  1,338cp; `Qxc4` is the reply. Lost.
- `20250391` m26, after `24.Qxe7 25.Qxf7+` — `f6` at +786, best `Qe6`; cost
  1,311cp; `Rxf7` is the reply. Lost.
- `8516ea23` m33, after `31.Rb1 32.Ra1` — `Bb4` at +768, best `Bxa3`; cost
  1,348cp; `Rb3` is the reply. Lost.
- `750d3539` m28, after `26.e6 27.Qf3` — `Kh7` at +470, best `Rxd5`; cost
  1,162cp; `Qe4+` is the reply. Lost.

**Does well — demonstrated resilience.** He **delivered mate 120 times and
created a forced mate 35 times**, against 343 mate errors. `73140de9`: at move
19 the eval was **−9,970** — facing forced mate — and he played the engine's
best move anyway (`Qg3`, 0cp); the opponent did not deliver it; by move 23 he
was +396 and he **won by checkmate**, punishing both errors offered.
`66ac48e5`: move 9 took him from +491 to −197, then **eight consecutive
engine-approved moves** (m11–m20) rebuilt it from −208 to **+509**.

**A sequence that fits the material mechanism.** `2af810fd` (lichess LFLLI2MK,
blitz 300+3, lost on time), every step board-verified:

```
m15 Rxe6   the engine's own move, +492. The rook on e6 is attacked by nobody.
m16 Rh6+   a CHECK, -432cp. It moves the rook to a square the g7 pawn attacks
           and nothing defends. The check created the weakness.
m18 Rh4    rescues the now-hanging rook for 1cp. Good move; still unprotected.
m19 Ng5    -180cp, and incidentally blocks the f6-h4 diagonal.
19...Qf6   the queen bears on h4 THROUGH the knight; the rook is still safe.
m20 Nxf7   -180cp. Moving the knight unblocks the diagonal; 20...Qxh4 wins the
           rook. 34 of his 38 legal moves kept it safe.
```

### 4.8 Endgames, separated by the ending actually reached

Classified from the pieces on the board, ordinary loss only:

| Ending reached | Games | Ordinary moves | Mean cp | Median | Mate rows | Mate share of moves |
|---|---|---|---|---|---|---|
| rook plus a minor piece | 112 | 1,368 | 58.5 | 0 | 122 | 8% |
| rook endgame | 35 | 620 | 61.2 | 0 | 84 | 12% |
| **queens still on** | 92 | 565 | 67.0 | 0 | **301** | **35%** |
| minor pieces only | 26 | 456 | 68.1 | 4 | 62 | 12% |
| king and pawns only | 3 | 89 | 63.3 | 0 | 11 | 11% |

Ordinary accuracy is **58–68cp in every ending** — indistinguishable, median 0 in
four of five. **What differs is mate involvement:** with queens on the board,
**35% of his moves are mate-related against 8% in rook-and-minor endings.**
Queens-on endings are where his games reach mating positions, in both
directions. Whether he is more often the one being mated there is **unknown** —
the transition split was not computed per ending.

**Unknown.** King-and-pawn endings: 3 games, 89 moves. His taught endgame
material is almost entirely king-and-pawn and Lucena, which he reaches in **3 of
807 games**.

### 4.9 Opponent strength, platform, time control, and the clock

**Platform and time control, ordinary loss only.** Different rating pools, not
comparable as skill measures:

| Platform | Control | Games | Moves | Mean cp | Blunder% | Win% |
|---|---|---|---|---|---|---|
| chess.com | rapid | 508 | 14,091 | 59.4 | 8% | 46% |
| lichess | blitz | 104 | 3,021 | 59.8 | 8% | 53% |
| chess.com | blitz | 51 | 1,408 | 60.9 | 9% | 27% |
| coach | untimed | 113 | 1,176 | 73.7 | 6% | — |

His accuracy is the same on every platform and at every time control. Ratings:
lichess median **1310** (1202–1391), chess.com median **1161** (824–1367).

**Opponent strength — lichess only** (101 games with both ratings): **flat.**
100+ weaker 3/3; 25–99 weaker 12/24 (50%); within 25 24/44 (55%); 25–99 stronger
12/24 (50%); 100+ stronger 3/6 (50%). Against opponents 25–99 points stronger he
scores the same as against equals, with a *lower* mean loss. **His belief that
stronger opponents understand things he does not is not visible in his results**
— on 101 games with 6 in the top band.

**chess.com bands remain excluded.** 100% against weaker (65/65) and 11% against
stronger (13/116) is an odds ratio near 21, far too deterministic for a 25–99
point gap. Stored `user_rating` equals the PGN Elo on **400 of 400** sampled
games and **no PGN carries a `RatingDiff` tag**, so pre- versus post-game cannot
be established from our data.

**How his games end:** lichess (104) — timeout **41**, checkmate 40, resignation
23. chess.com (590) — checkmate 170, resignation 145, timeout **141**,
abandonment **115**.

**Did clock pressure contribute before the position went bad?** Revision 2 said
no on the strength of a median. The full distribution, measuring his clock at
the move where his evaluation **first** fell to −100:

| Loss type | n | Median | p10 | p25 | Already under 2 min | Under 60s |
|---|---|---|---|---|---|---|
| **timeout** | 111 | 440s | 87s | 189s | **19 (17%)** | 9 (8%) |
| resignation | 55 | 466s | 160s | 268s | 4 (7%) | 1 (2%) |
| checkmate | 74 | 397s | 91s | 181s | 8 (11%) | 5 (7%) |

**Corrected:** in **77%** of timeout losses he had over three minutes when his
position first went bad, so the usual case is a lost position followed by a
flag. But he was **already under two minutes in 17% of timeout losses against 7%
of resignation losses** — more than double. **Clock pressure did contribute
earlier in a measurable minority.** Revision 2's blanket "not an independent
clock failure" is withdrawn.

**The clock itself, recovered from the source PGNs.** The analysis pipeline
discards it — **0 of 23,735 analysis rows carry any clock field** — but the
annotation is in the imported PGN:

| Stage | Coverage |
|---|---|
| `%clk` in the stored PGN — chess.com | **587 of 590 (99%)** |
| `%clk` — lichess | 44 of 104 stored, **+2 recovered** |
| `%clk` — coach | 0 of 113 |
| parsed and halfmove-aligned | **17,379 moves** |
| of those, ordinary (non-mate) | **16,350** |

*Retrieval attempt:* all 60 lichess games whose stored PGN lacked clocks were
requested from `lichess.org/game/export/{id}?clocks=true`. **2 returned PGN; 58
were redirected to lichess's registration page** — re-tested individually with
15-second gaps, so it is gating, not rate-limiting. Those need an authenticated
token. 13 games had a *duplicate* record holding the richer PGN.

His pace: median **5.0s** per move, p25 2.3s, p75 11.8s, p95 40.8s.

**Move quality by time remaining**, mates removed:

| Clock left | Moves | Mean cp | Blunder% |
|---|---|---|---|
| under 10s | 213 | 118.3 | **22%** |
| 10–30s | 422 | 95.8 | 16% |
| 30–60s | 577 | 80.7 | 13% |
| 1–3 min | 2,089 | 73.2 | 11% |
| 3–10 min | 12,629 | 58.1 | **8%** |
| over 10 min | 420 | 51.5 | 5% |

**Observed and monotonic.** With the limits stated: the mate-row share also
rises at low clock (25% under 10s against 4% at 3–10 min), causation runs both
ways, and the lowest band is 213 moves.

**The clock interaction worth keeping.** From Control 2 in §4.7, at moves 16+:
**level positions are flat across the clock (13% → 12% → 11%) while
clearly-better positions are steep (13% → 18% → 28%).** His handling of a
winning position is clock-sensitive in a way his handling of a level position is
not. *Supported*, on n=735 / 205 / 158 — and consistent with Control 3: narrow
positions need time he does not always have.

**Does he slow down for difficult decisions?** Revision 2's table used |eval| ≥
500 as a difficulty proxy, which conflates "winning big" with "losing big" and
is not a difficulty measure at all. That conclusion is withdrawn. Re-tested on
520 clock-aligned positions with an engine difficulty measure:

| Share of the position's legal moves that blunder | Positions | Median time | Mean cp | Blunder% |
|---|---|---|---|---|
| forgiving (<25%) | 146 | 3.8s | 28.0 | 0% |
| 25–45% | 131 | 5.0s | 56.3 | 5% |
| 45–65% | 53 | **6.9s** | 67.9 | 11% |
| unforgiving (65%+) | 190 | **4.8s** | 79.2 | 12% |

| Moves that keep the evaluation (within 100cp of best) | Positions | Median time | Blunder% |
|---|---|---|---|
| only 1 | 80 | **3.8s** | 10% |
| 2 | 57 | **4.0s** | 16% |
| 3–5 | 96 | 5.5s | 6% |
| 6 or more | 287 | 4.7s | 4% |

Controlling for clock (over 3 minutes left): **1–2 good moves — 4.2s, 8%
blunder; 6+ good moves — 4.4s, 4% blunder.**

**Supported, and this is the defensible version of the claim:** with ample
clock, he spends **the same time** on a position with one or two good moves as on
one with six or more, and blunders at double the rate in the former. His time
allocation does not track how narrow the position is. **Limit:** some only-move
positions are forced and genuinely quick (a recapture, a king move out of
check), which would depress the time figure without any failure on his part;
n=101 against 233.

### 4.10 Learning: independent vs assisted, retries, unfamiliarity, delay

**232 lesson attempt records** from `learning_sessions.events[].attempt`.

| | Correct | Incorrect |
|---|---|---|
| unassisted | 22 | 62 (26%) |
| assisted | 18 | 22 (45%) |

First answers unassisted: 17 of 58 (29%). **Untimed is not assisted** — 184 of
232 record no assistance, `assistance_measured` true on 209. Assistance: `hint`
24, `guided_line` 10, `answer_revealed` 8, both 6. `retry_index` reaches **7**;
one item drew 15 `show_on_board` requests. `distinct_position` true on only 35.

**What he says about his own choices** — 82 trials:

| Reason he selected | Times |
|---|---|
| **`looks_active`** | **34** |
| `not_sure` | 20 |
| `keeps_piece_safe` | 18 |
| `uses_rule` | 6 |
| **`checked_landing_square`** | **4** |

`reasoning_consistent` false on 54, true on 28. Misconceptions:
`piece_left_unsafe` **51**, `endgame_rule_not_applied` 18,
`activity_before_safety` 8, `piece_safety_relationship_unclear` 6,
`reason_does_not_match_move` 2.

**Nine direct answers to "What were you thinking before this move?"** —
`reflection_sessions`, 9 records across 7 games, all `answered_before_reveal`:

| Date | Concept | He chose | Took |
|---|---|---|---|
| 09-01 | `calculation.verified_stored_line` | `not_sure` | 44.9s |
| 09-05 | `calculation.legal_material_loss` | **`thought_piece_safe`** — "I did not notice the knight on a3 attacking my knight on c2" | 10.1s |
| 09-05 | `piece_safety.simple_hang` | **`thought_piece_safe`** — "I did not notice the bishop on d2 attacking my bishop on b4" | 8.6s |
| (two further) | | `not_sure`; `missed_capture` — "I did not consider the full capture sequence" | 17.5s |
| 09-09 | `calculation.legal_material_loss` | **`chose_attack_over_safety`** — "I was trying to continue the attack" | 28.4s |
| 09-11 | `calculation.verified_stored_line` | **`chose_attack_over_safety`** — "I was focused on continuing my attack" | 136.6s |
| 09-16 | `piece_safety.simple_hang` | `none_of_these` | 112.9s |
| 10-02 | `calculation.verified_stored_line` | **`missed_check`** — "I didn't see the check" | 26.5s |

**Observed, on these nine trials only:** twice he reported not seeing an
attacker, twice choosing to continue his attack. Those are different diagnoses —
perception versus prioritisation — and on this evidence they are equally common.
Both align with §4.7's dominant mechanism of material left to the reply.

`intent`, `intent_confidence` and `free_text` are **not populated anywhere in
the nesting** (recursive walk over all 9 records). The capture is
`selected_option_id` from five offered options.

**Delayed application — the one real before/after chain, `piece_safety`:**

| Date | Stage | Unfamiliar | Unassisted | First answer | Result |
|---|---|---|---|---|---|
| 09-02 | transfer | yes | yes | — | ✗ |
| 09-07 | retain | yes | 7 tries, then hint + 12 helps | yes, then no | ✗ ×7, then ✓ assisted |
| **09-10** | **transfer** | **yes** | **yes** | **yes** | **✓** |
| 09-17, 09-24, 09-28 | recall | no | mostly | mixed | mostly ✗ |
| **09-25** | **transfer** | **yes** | **yes** | **yes** | **✓** |

**Supported:** his first transfer attempt failed; two later ones — **8 and 23
days after** — were unassisted first answers on unfamiliar positions and both
succeeded. **Not supported:** that he has learned piece safety — familiar recall
drills kept failing unassisted *after* both successes, on a base of three
transfer attempts.

**The in-game half is empty.** All 95 game observations fed to the learning
ledger carry `correct: null` — exposure, not outcome.

**Also unscored:** his diagnostic sessions are marked `abandoned` or
`in_progress` yet hold **37 scored attempts** (32 understood), one session
reaching all 20 puzzles. No diagnosis was ever produced.

---

## 5. Plain-English description

He is a classical, narrow-repertoire player — `1.e4` as White, `1…e5` against
it, into the Italian, with the Scandinavian in reserve. He plays his first five
moves almost perfectly: a one-in-a-hundred blunder rate. At move six, when the
remembered moves run out, his blunder rate jumps eightfold in a single step —
and then stays there, unchanged, for the rest of the game. He has one
discontinuity, not a decline. That move-eight error arrives in nearly three
games in four, and four times in five he recovers from it.

He is a competent player of level positions and a competent player of winning
positions, and the difference between those two is smaller than I claimed last
time. Past move fifteen, with three minutes on his clock, he blunders on about
one move in eight whether the game is level or he is a piece up. What is true is
that winning positions are genuinely harder than they look: when he is clearly
ahead, almost seven in ten of his legal moves would throw away a chunk of the
advantage, and in nearly half those positions only one or two moves hold it. He
finds one of them two thirds of the time.

The games go in the remaining tail. Six per cent of his moves from a winning
position cost 400 centipawns or more — 240 moves across 187 games. Games where
that happens are won 44% of the time; games where it doesn't, 78%. And the
commonest way it happens is specific and shallow: in 38% of cases he left
material to the opponent's very next move, and the punishing reply was always a
capture or a check one ply deep. In another 18% he missed the move that would
have finished the game. Even then these are damaging rather than fatal — he
climbed back to a winning position in 62% of them.

The same shallowness shows in his routine decisions. Of all the ways he departs
from the best move, the most expensive is declining a capture that was right —
over a thousand instances at 162 centipawns each, and a blunder rate of 26%,
higher than any other kind of departure. Capturing when he shouldn't is more
frequent but cheaper. Either way, the error sits one move ahead, not five.

He is sharp and forcing by temperament, capturing four times and checking nearly
three times more often than positions offer. He takes free material four times
in five and delivers three mates in four. But of the 47 times mate in one was on
the board and he missed it, in 27 he played a different check.

His clock matters in a particular way. Two in five of his lichess games end on
time, and in most of them he was already losing when the flag fell — though in
one timeout loss in six he was already under two minutes when the position first
turned, which is more than twice the rate for games he resigned. More tellingly:
with plenty of time on the clock he spends the same four seconds on a position
with one good move as on a position with six, and blunders twice as often in the
first. And his play in winning positions degrades sharply as the clock drains
(13% to 28%) while his play in level positions does not (13% to 11%).

Two corrections to my own earlier accounts. He is not quietly improving — his
error rate is flat on both platforms. And he is not losing games he had already
won: a +300 position is won 64% of the time, not 100%.

---

## 6. Best-supported difficulties

Ordered by strength of evidence, each with its uncertainty, and none of them a
psychological claim.

1. **A 400cp+ slip from a winning position costs him 34 percentage points of
   conversion** (78% → 44%). 240 moves, 187 games, rated only. *This is the
   largest measured consequence in the profile.* It is a statement about
   consequence, not rate: the same moves are only 6% of his winning-position
   play, and he is near-best in 67%.
2. **The commonest mechanism is one ply deep** — 38% left material to the
   opponent's immediate reply, always to a capture or a check; 14% were exchange
   errors. Engine-verified at depth 14. *30% resisted classification and are
   recorded as unclassified.*
3. **Declining a capture that was best is his costliest routine departure** —
   161.7cp, 26.5% blunder rate, 1,019 instances, the worst of six comparable
   decision types. *Observed.*
4. **One discontinuity at move 6** — 1% to 8% blunder rate in a single step, then
   flat; median first error at move 8. *Stable across 807 games and both
   platforms, and phase-defined so not a phase artifact.* But 79% recovery means
   low consequence per instance, and no opening line stands out.
5. **Winning positions are intrinsically narrow** — 69.6% of their legal moves
   blunder, 47% have only one or two good moves. *A fact about conversion, not
   about him*, but it is why item 1 happens and what any training must respect.
6. **His time allocation does not track how narrow a position is** — with over
   three minutes left, 4.2s on 1–2-good-move positions against 4.4s on
   6+-good-move positions, at double the blunder rate. *Supported; limited by
   forced-move positions being genuinely quick, n=101.*
7. **Threat handling** — 77% answered over 4,342 positions; the largest stored
   signal and the weakest prompted concept. *Two independent instruments agree.*
   The nine reflection answers split 2–2 between not seeing and deprioritising.
8. **He is not improving.** Error rate flat across the whole window on both
   platforms. *Observed.* This is the honest content of "stuck".

**Not a difficulty, on current evidence:** an advantage-specific error rate
(13% vs 13% once phase and clock are held); stronger opponents (lichess results
flat across bands); his opening repertoire (no family deviates from baseline);
material-losing captures (refuted three times); any positional *average*.

---

## 7. The few questions that would change the coaching decision

1. **What are the 72 unclassified slips?** *Records checked:* all 240 are
   identified with FEN, played move, best move and engine reply; the rule set
   named 168 of them. The residue is 30% of the most consequential moves in the
   profile and reading them individually is read-only work on data in hand.
   **Highest-value question.**
2. **Does he see the opponent's reply at all?** *Records checked:*
   `prediction_correct` is null on all 232 lesson attempts — he has never been
   asked. The nine reflection answers are the only direct evidence and split 2–2
   between perception and prioritisation. The 90 "left material to the reply"
   positions are the natural instrument; asking him in those positions
   distinguishes the two.
3. **Is the time allocation finding real or an artifact of forced moves?**
   *Records checked:* the 520 sampled positions have both the engine difficulty
   measure and his time. Excluding positions where the only good move is a
   recapture or a check-evasion would settle it. Not yet done.
4. **Are the chess.com Elo values pre- or post-game?** *Records checked:* stored
   rating equals the PGN header on 400 of 400 games, no `RatingDiff` tag. Needs
   chess.com's rating history; until then no claim about his results by opponent
   strength on that platform is usable.
5. **The 58 lichess games whose clocks are gated.** *Attempted and failed:*
   anonymous export redirects to a sign-up page. Needs an authenticated token.

---

## 8. What ChessGuru can responsibly personalise, and what it cannot

**Can:**

- **The 240 identified positions**, grouped by the four verified mechanisms —
  concrete, his own, and the mechanism is named for 70% of them.
- **One-ply consequence checking**, as the content rather than a slogan: in every
  verified example the refutation was the opponent's next move and was a capture
  or a check.
- **Capture decisions in both directions** — 1,019 declined-best-captures at
  161.7cp and 1,349 unsound captures at 118.2cp, with engine-verified examples.
- **Narrow winning positions**, respecting that 47% of them have only one or two
  good moves — this is a find-the-only-move skill, not a "don't relax" message.
- **The move 6–11 transition**, as a general skill rather than opening theory.
- **Threat positions from his own games, as questions** — the prompt that asks
  the right question already exists and already works, nine times.
- **Piece-safety landing squares**, from his own stated reasons (`looks_active`
  34, `checked_landing_square` 4, `piece_left_unsafe` 51).
- **Queens-still-on positions** rather than the king-and-pawn material he is
  taught and reaches in 3 games of 807 — as mating-attack awareness, not accuracy.

**Cannot claim:**

- That he **plays worse when ahead**. Once phase and clock are held, he does not.
- Any **psychological mechanism** — complacency, over-confidence, relaxing. The
  observations do not distinguish these from inexperience with narrow positions.
- That he is **improving**. He is flat.
- That he has **mastered** anything, or any **retention** beyond two unassisted
  transfer successes on one idea.
- Any **planning** ability or deficit, or any positional weakness stated as an
  average.
- That stronger opponents beat him more, or that any opening line is a weakness.
- A **single rating** for him — four exist (920 resolved by the app, 1199, 1241,
  1490) and they are not from one pool.

**Two things it should stop doing.** `resolve_coaching_rating` returns **920**
from the median of three chess.com games while 87 of his last 100 games are
lichess blitz at 1490, and the puzzles he was served sat at a median rating of
898. And the import path discards the clock: present on 99% of his chess.com
PGNs, retained on **0 of 23,735** analysis rows.

---

## 9. Coaching brief

### Demonstrated strengths

- **Opening accuracy.** 1% blunder rate over his first five moves, 3,954 moves.
  A narrow, coherent repertoire he knows.
- **Simple tactical execution.** Takes a free piece in 79% of 1,657 chances;
  delivers mate in one in 74% of 163; delivered mate 120 times and created a
  forced mate 35 times.
- **Winning positions, in the main.** Engine-best or within 50cp in **67%** of
  his 3,927 moves from a winning position — against positions where 70% of legal
  moves would have thrown it away.
- **Resilience.** Recovers to level or better from 79% of his first big errors,
  and regained a winning position after 62% of even his worst slips. Won a game
  from a position assessed as forced mate against him.
- **Untimed strength above his results.** 32 of 37 diagnostic items exactly
  right, including every fork, skewer and mate pattern put to him.

### Most consequential recurring difficulties

1. **A 400cp+ slip from a winning position.** 240 moves, 187 games; conversion
   falls from 78% to 44% when one occurs.
2. **Failing to check the opponent's immediate reply.** 38% of those slips, with
   the refutation always one ply deep and always a capture or a check.
3. **Capture decisions.** Declining a best capture is his costliest departure
   (161.7cp, 26.5% blunder, n=1,019); unsound capturing is more frequent and
   cheaper (118.2cp, 18.4%, n=1,349).
4. **Threat response.** 77% answered; weakest prompted concept; largest stored
   signal.
5. **Time not allocated to narrowness.** Same ~4.2s on a one-good-move position
   as on a six-good-move position, at double the blunder rate.

### The first coaching priority, and the evidence for it

**Teach him to check the opponent's immediate reply before committing, using his
own 240 positions, starting with the 90 where material was left to that reply.**

The evidence:

- **Consequence is measured, not assumed.** 187 games contain such a slip and
  conversion falls 78% → 44%. Closing even part of that gap is the largest
  available swing in his record; the 94 lost games among them are 13.5% of his
  694 rated games.
- **The mechanism is engine-verified and shallow.** In 90 of 240 cases the
  refutation is the opponent's next move, and it is a capture or a check every
  time — a one-ply check, not a calculation programme. A further 34 are exchange
  errors with the same structure.
- **It is corroborated by independent instruments.** His own most-selected
  reason for a move is that it *looks active* (34 of 82) and his least-selected
  is that he *checked the square he was moving to* (4 of 82). Two of his nine
  reflection answers are "I did not notice the piece attacking mine". His
  recorded misconception `piece_left_unsafe` has 51 instances. Four separate
  sources point at the same one-ply gap.
- **It is narrow enough to be teachable.** This is 6% of his winning-position
  moves, not a rebuild of his game. He already plays 67% of those positions at
  near-engine strength.
- **It does not require a psychological claim.** No complacency, no
  over-confidence — a procedural habit with a measured cost.

**What not to tell him.** That he plays worse when he is ahead: controlling for
phase and clock he does not. That he is losing games he had already won: a +300
position is won 64% of the time. That he is improving: he is flat.

**Second priority, and the condition to watch.** His winning-position accuracy
degrades sharply under time pressure (13% → 28% as the clock drains) while his
level-position accuracy does not (13% → 11%). Any conversion training should be
practised with a clock, because that is where the skill fails.

---

## 11. The sitting of 2026-10-16, and what 694 games say about it

Added after the reply-check session was run. §9's first priority is **marked
provisional** at the end of this section.

### 11.1 What the sitting recorded

Fourteen positions, 2026-10-16, 01:48–02:11. Every answer given before any
evidence was shown.

**Assistance: none.** The page offers no hint, no engine line and no evaluation
before recording, so nothing was assisted. **Revisions: 0 of 14** — offered
every time, taken never. **Reason and reflection choices: 0 of 14** — both
optional in the page, both skipped, so neither existing instrument captured
anything. **Recognised: 1 of 14** (position 1), and I had described that
position in detail in conversation beforehand, so it is excluded below.

**Move accuracy**

| | chose a holding move |
|---|---|
| treatment — positions he got wrong before | 4 of 8 |
| control — positions he got right before | 5 of 6 |
| the fair sub-comparison (§7 limit 2: 5+ holding moves only) | treatment **1 of 5**, control **3 of 4** |

**Predicted replies.** The page's own summary said "4/14 named the capture".
**That is the wrong denominator.** A material-winning reply existed after the
move he chose on only **6 of the 14** trials; on the other eight there was
nothing to take and the measure could not score. He named it on **4 of those 6**.

The three trials marked *pending verification* were checked afterwards and were
all sound: `d5`, `Bf7+` and `Kc6` are legal and reasonable — two leave him
+65cp and +77cp better off than the engine's own reply, one is within 50cp of
it. They were pending only for sitting outside the stored top six. The holding
mechanism worked; the summary tile made it look like a fault.

**Position assessments — and the distinction that matters.** Six of fourteen
were below the engine's figure, but they are not one thing:

| | n | which |
|---|---|---|
| directionally wrong | **2** | #3 called it *"losing"* at **+786**; #10 called it *"worse"* at **+486** |
| understated, same direction | 4 | *"level"* at +312, +411, +458, +570 |
| about right | 7 | |
| over-rated | 1 | |

**The four understated ones are not errors.** Calling a +312 position *"level"*
is a reasonable verbal description of an engine advantage; words and centipawns
are not the same scale, and the mapping I compared them against was my own
invention. Only the two directional ones are unambiguous.

And one of those two is explained. On #3 he had chosen `h3`, which takes the
position from +786 to **−364** — *"losing"* describes what he was about to
produce. On four trials his "now" answer fits the position **after** his move
better than the one in front of him. **#10 is the only unexplained directional
misread in the sitting: +486 before, +469 after, and he said "worse" to both.**

He gave the **same rating before and after the reply on 14 of 14**. With the
above, the two questions probably collapsed into one — a fault in my page, not
a finding about him, and it cost the session's cleanest measurement.

### 11.2 What the 694 rated games say

Final positions replayed from the PGN and evaluated directly at depth 16, not
taken from the last stored evaluation, which belongs to a different position.
`termination` is crossed with his result, because it does not say who stopped.

| termination | he won | he lost | reading |
|---|---|---|---|
| resignation | 111 | **58** | a resignation he lost is his |
| abandonment | 64 | **51** | |
| timeout | 24 | **157** | |
| checkmate | 120 | 91 | decided on the board |

**Resignations — the clearest result here.** Of the 58 he resigned, 17 ended
with a forced mate against him and 41 had an ordinary evaluation. **All 41 were
losing. Not one was at +100 or better.** *Observed: he has never resigned a
position that favoured him.* That contradicts the reading that he fails to
register an advantage.

**Abandonments.** Of the 51 he lost this way, 2 ended facing mate and 49 had an
ordinary evaluation: 23 losing, 7 worse, 11 level, 7 better, **1 clearly
better** (+378, with 484 seconds still on his clock). **8 of 49 (16%) were at
+100 or better.** *Bounded:* chess.com reports abandonment without saying why,
so the board can be read but a disconnection cannot be told from a decision to
stop playing.

**Timeouts.** Of the 157 he lost, 13 ended with mate against him, 2 with a
forced mate **for** him, and 142 had an ordinary evaluation. **31 of 142 (22%)
were at +100 or better; 21 at +300 or better or holding mate.** Split by the
clock he last had:

| clock at his last recorded move | games | of which +300 or better |
|---|---|---|
| under 10 seconds — a flag falling | 14 | 10 |
| 10–60 seconds | 2 | 1 |
| 1–3 minutes | 3 | 3 |
| **over 3 minutes** | **13** | **6** |

Those 13 are all chess.com rapid with **333 to 577 seconds remaining**. Two of
the scrambles ended with a forced mate available and one second on the clock.
*Bounded:* a timeout while ahead is as consistent with clock management, or with
walking away from the board, as with anything about how he reads a position —
and the two halves of that table are plainly different events.

**Exchange decisions, per decision rather than by frequency.** In positions
where he was already clearly better (+300 and up, mates excluded):

| the engine's best move was | decisions | he found it | missing it costs | 300cp+ |
|---|---|---|---|---|
| a capture | 1,374 | **66%** | mean 215.3cp | 25% |
| not a capture | 2,602 | **33%** | mean 137.5cp | 14% |

Within the capture half: he played the engine's capture 907 times (66%), played
a *different* capture 171 times (12%, mean 175.0cp), and **did not capture at
all 296 times (22%, mean 238.6cp, 29% of them costing 300cp or more).**

Verified examples of an exchange that damaged a winning position: `ff3f130a`
m18 `hxg3` at +403 → −700 when `Re2` held it; `e915cd2f` m34 `Qxg5+` at +907 →
−109 when `Qb8+` held it; `2de0f441` m26 `cxd6` at +430 → −439 when `hxg3` held
it. Against those, `22464363` is a game where he took four times in a row
exactly as the engine wanted (`Nxd6+`, `Qxd6`, `Qxc3`, `Rxe8+`) and won it.

*A correction to my own first pass:* I compared "a capture he made cost 58cp"
with "a capture he declined cost 239cp". That pair is not fair — declining the
best move is a deviation by construction, so it cannot help but cost more. The
table above compares two deviations and is the honest version.

So his exchanges when winning are mostly good: he plays the engine's own
capture two times in three. The damage sits in the third where he does not.

### 11.3 Where the next coaching focus should go

| candidate | verdict |
|---|---|
| **position assessment** | **not supported.** The sitting's six under-rates reduce to one unexplained trial, and 58 resignations contradict it outright |
| **reply checking** (§9's priority) | **weakened.** On 3 of the 4 treatment trials where his move gave ground he named a reply as damaging as the engine's own. He was looking |
| **candidate generation** | **the strongest of the three, and not established.** 296 decisions where the winning move was a capture and he played something else, mean 238.6cp; plus the one sitting trial where he named the refutation, rated the outcome correctly, and played the move anyway |

**The honest answer is that it is unresolved between candidate generation and
evaluation.** Nothing here separates *he never considered the capture* from *he
considered it and judged it wrong*. Both produce the same record. That
distinction needs his answer, on the positions where he gives ground, and it is
the one question worth a second sitting.

**§9's first priority is therefore provisional.** Not withdrawn — eight
treatment trials cannot overturn a pattern measured across 240 moves — but the
direct test went against it, and it should not be taught as settled.

**And the 78% / 44% figure is an association, not a proven cost.** Games
containing a 400cp+ slip differ from games without one in more ways than the
slip: they are sharper, longer, and more often against stronger opposition. The
difference is real and worth acting on; "closing that gap would recover 34
points of conversion" does not follow from it.
