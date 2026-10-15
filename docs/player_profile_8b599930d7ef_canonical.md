# Canonical coaching profile — player 8b599930d7ef

**Status: canonical.** Supersedes the earlier profile, capability report,
investigations and integrity notes for this player; §2 lists what is withdrawn.
Read-only throughout: no code, production write, deployment or migration.

**His stated position** (self-report, 2026-10-15, not independently verified):
target around 2000; feels stuck near 1300; relies on gut feel with limited
calculation; believes stronger opponents understand things he does not.

---

## 1. Scope and exclusions

Two windows, both de-duplicated by platform game id (`games.url`), falling back
to a normalised move-sequence hash.

| | RECENT | FULL |
|---|---|---|
| purpose | current baseline | persistence and change |
| distinct analysed games | **100** | **806** |
| dates | 2026-09-01 → 10-15 | 2026-02-23 → 10-15 |
| his moves | 2,996 | 22,882 |
| platforms | lichess 87, coach 9, chess.com 4 | chess.com 590, lichess 103, coach 113 |

Duplicate handling: 849 analysed records → 806 distinct, **43 dropped**. In
RECENT the rate is higher (13 of 113 records walked). Every count below is
distinct-game based. Earlier figures taken over 100 *records* are superseded.

**Excluded from all conclusions, with reasons:**

| Source | Why excluded |
|---|---|
| mastery stamps (`mastered_at`) | all 33 of his surviving stamps sit on concepts the product **never showed him**; the 42 "stripped" are all `artifact_backfill_cleanup` from a 2026-06-04 bulk backfill |
| `shown_count` | a per-render counter (`$inc` on every v5 render), not exposure |
| my fork-availability detector | fired in 19.5% of positions; a real fork is not available in a fifth of all positions |
| my "hanging piece" detector | engine disagreed on 2 of 5 sampled cases; no cross-player baseline |
| `subtype: missed_generic_tactic` (42), `generic_endgame_slip` (17), `generic_oversight` (10) | a count with no diagnosis — "generic" means the detector could not name the motif |
| `puzzle_attempts` `weakness_type: unknown` (16, 0 correct) | all have `moves_tried: []` and no time recorded: no move was ever submitted. Other users solve the same 6 puzzles |
| `coaching_profile.preferred_learning_style` | `"practice"` on all 128 users; an unmeasured default with no reader |
| chess.com opponent-strength bands | see §3.9 — cannot be distinguished from circular |

**Engine use.** All move-quality figures come from stored `move_evaluations`
(Stockfish at analysis-time settings, not recorded per row). One independent
check was run earlier for a single consequential claim —
`chess.engine.SimpleEngine`, depth 20 (position scan) and depth 18 (per-move
ranking) — and is labelled where used. No new engine analysis was run for this
document.

**Evidence classes** used throughout: **observed** (board-verifiable or a
stored engine figure), **supported** (a reading several independent sources
agree on), **hypothesis** (one plausible reading among others), **unknown**.

---

## 2. Superseded and withdrawn

| Earlier claim | Status |
|---|---|
| "the opening is his strongest phase (41.9cp, 5% blunders)" | **misleading, superseded by §3.1.** That averaged moves 1–10; moves 1–5 run at 19.4cp/1% and moves 6–10 at 68.3cp/**8%** |
| "he has a capture-consequence habit (13% of captures)" | **withdrawn.** Opportunity-adjusted preference 0.78× — he plays material-losing captures *less* often than they are available — and the engine clears 53 of the 95 |
| "`time_flag` is miscalibrated" | **withdrawn.** 0.56% firing is by design: mistakes only, speed relative to his own pace, already-losing positions skipped |
| "knowledge is there, execution is not" | **withdrawn as premature.** The prompted set tops out at a 1300 puzzle rating, ~190 points below his lichess play |
| "his queen had six safe squares and he took a pawn instead" | **withdrawn.** Depth-20 ranking: `bxc5` was the best of all 38 legal moves (−374) and the best queen retreat `Qxe6` was −482 |
| "he left a rook hanging and ignored it" | **withdrawn.** The rook was attacked by nobody until his own knight left g5 |
| "never castles in 41 of 100 games" | **withdrawn.** Disjoint recount: 17 games over by move 15, 10 lost the right early, 11 later, **2** had it throughout |
| "87% / 86% right kind of move" | **withdrawn.** `decision_register` is computed from a misaligned index join; 78.5% of its verdicts change when fixed |
| "most of his games have no opening identified" | **corrected.** Per-platform: chess.com 98% named, **lichess 0%**, coach 3% |

---

## 3. The player, by area

### 3.1 Opening repertoire, and what happens when familiar moves end

**Does well.** Moves 1–5 are close to free: **19.4cp mean loss, 1% blunder
rate** over 4,401 moves (FULL). A narrow, consistent repertoire — RECENT, read
from the moves because lichess stores no opening name: as White `1.e4 e5` (23
games), as Black `1…e5` vs e4 (20), `d4 d5` (7), Scandinavian (6), Sicilian
(6). He castles in **543 of 806** games (67%), median move 9.

**Where it breaks down — this is the sharpest finding in the profile.**
Accuracy collapses the moment memory runs out (FULL, 22,882 moves):

| His move numbers | Moves | Mean cp lost | Blunder rate |
|---|---|---|---|
| 1–5 | 4,401 | 19.4 | **1%** |
| **6–10** | 3,806 | **68.3** | **8%** |
| 11–15 | 3,353 | 114.6 | 10% |
| 16–20 | 2,910 | 201.2 | 12% |
| 21–30 | 4,363 | 289.5 | 12% |
| 31+ | 4,049 | 324.0 | 12% |

And his **first move costing 100cp+ lands at median move 8** — p25 move 6, p75
move 11. **73% of his games have it by move 10; 92% by move 15.** 114 of 806
games never contain one.

The blunder rate multiplies by eight between moves 1–5 and 6–10, then
plateaus. **Supported interpretation:** his games are decided in a narrow
window just after theory ends, and the rest of the game is played from a
position already compromised. That is a different problem from "he is weak in
the middlegame".

**Persistence.** Stable across both windows and both platforms — it is the
oldest and most consistent pattern in his record.

**Representative.** `7d2c3b44` (lichess CnATF3rC): level at move 10 (−11cp),
then `11.b4` costs 352cp, the engine wanted `d4`. `0f00953e`: the summary names
move **4** (`Qf5`) as where the game was really decided, 47 moves before it
ended.

**Counterexample.** 114 games contain no 100cp+ error at all, so this is not
universal. And the 1% blunder rate over the first five moves is genuinely good.

**Unknown.** *Which* openings fail. `opening_name` is null on all 676 lichess
games and `opening_key` is set on 8 of 20,293 games product-wide, so his 52
`opening_knowledge` flags (RECENT, 43 games) cannot be tied to a line.

### 3.2 Tactical recognition

**Does well, opportunity-paired (RECENT, observed).** A free undefended piece
worth 3+ taken in **182 of 215** chances (85%). Mate in one delivered in **22
of 31** (71%). Opponent errors punished **108 of 171** (63%).

Prompted and untimed, he produced the **exact** solution move in **32 of 37**
diagnostic items, with the grader accepting no alternatives: fork 4/4, skewer
4/4, mate_patterns 4/4, discovered_attack 2/2, calculation 3/3.

**Where it breaks down.** The five diagnostic misses cluster at the top of the
tested range — four of five at puzzle ratings 1193–1300 — and share a shape:

| Concept | Rating | He played | Solution |
|---|---|---|---|
| opening | 1298 | `dxc3` | **`Bxc3`** |
| piece_safety | 1300 | `Rxe2` | **`Bxd6+`** |
| pin | 1261 | `Qxd8` | **`Ng5+`** |
| threat_response | 1193 | `Kd6` | **`e7+`** |
| threat_response | 838 | `Kh6` | **`c5`** |

Three times he played a capture when the answer was a different move; twice he
moved his king when the answer was a pawn push.

Nine missed mates in RECENT, **all mate-in-one**, and in **five** of them he
played a *different check* (`Re4+`, `Bd7+`, `Be6+`, `Rxd7+`, `Be5+`).

**Persistence.** The prompted strength and the in-game shortfall coexist across
both windows.

**Counterexamples and limits.** He took **11 of 14** items rated 1200+, so
recognition does not collapse at his rating. Low tier 21/22 vs mid tier 11/15
is 95% against 73% — a real gradient, on 37 trials. Puzzle attempts are a
different pool: 53 of 118 correct overall, `skewer` 8/9 and `fork` 10/14 but
`piece_safety` **9 of 24**.

**Unknown.** Anything above a 1300 puzzle rating: nothing harder has been put
to him, while he plays in a 1490 lichess pool.

### 3.3 Calculation and anticipating the reply

**Does well.** He is the only user who has used the calculation instrument.
On his best attempt he submitted a genuine three-move line — `Kg8, Nd7, Qd3+`
— **sound through 3 ply** against a required depth of 2, and judged the
resulting position correctly. He judged the final position correctly in **both
attempts where he was asked** (2 of 2).

**Where it breaks down.** Four attempts across only **two distinct positions**:

| Submitted | Found the idea | Sound through | Required | Note |
|---|---|---|---|---|
| `Kg8, Nd7, Qd3+` | yes | 3 | 2 | correct end judgement |
| `Qxe5` | no | 0 | 2 | 3 seconds after the above |
| `Qd3+` | yes | 1 | 2 | **`stopped_early: true`** |
| `h4` | no | 0 | **8** | correct end judgement |

**Three of four submissions were a single move** when the task asked for a
line. **Hypothesis, not supported:** he commits once he has *a* forcing move.
It fits these submissions, the five alternative checks in §3.2, and the
sequence in §3.7 — but a single-move submission may equally be a
misunderstanding of the interface, and he did submit a real line once.

**Unknown, and this is a hole in the product not in him.**
`prediction_correct` is **null on all 232** lesson attempts: he has never once
been asked in a lesson to predict the opponent's reply. Candidate-move
generation is recorded nowhere.

### 3.4 Threat recognition and defence

**Where it breaks down — the most corroborated weakness in the profile.**
RECENT: threats answered **162 of 268 (60%)**. `missed_pattern: king_safety`
fires **112 times across 60 of the 100 games** — his largest single signal —
with `subtype: ignored_king_attack` 38 times in 29 games.

Independently, in the prompted condition `threat_response` is his **weakest
concept**: 5 of 7, and **2 of his 5 total diagnostic misses**.

**Supported interpretation:** two instruments that share nothing — a
board-derived in-game detector and an untimed puzzle set — put threat handling
at the bottom. That agreement is what raises this above the other patterns.

**Does well.** He still answers three threats in five, and `concept_type:
defense` is 3 of 3 in recorded concepts (too few rows to weigh).

**Unknown — and it decides the teaching.** Whether he *fails to see* the
threat, *sees it and misjudges* the answer, or *sees it and rejects* the answer
for a reason. `missed_pattern` is a count of unmade moves and cannot separate
those three. Nothing in the product stores a "what do you see" answer
(`user_misconceptions`, `home_today_answers`, `concept_tests` all hold 0 rows).

### 3.5 Planning and whether successive moves serve one objective

**Unknown, and I will not fill it.** There is no evidence either way:

- `pawn_structure` and `piece_activity` appear **zero times** in his 2,958
  RECENT observation rows.
- All five of his `positional` concept rows were artifacts.
- No instrument in the product asks for a plan, and no collection stores an
  answer to one.
- `concept_used` is written **only on good moves**, so it can congratulate and
  can never show the converse.

One sequence *looks* like plan incoherence and is offered as **hypothesis
only** — see §3.7. Engine disagreement is not evidence of having no plan.

### 3.6 Positional play: activity, coordination, pawns, exchanges, king safety

**Exchanges — a weakness I previously claimed and now withdraw.** RECENT: of
744 captures he initiated, 392 had no recapture available, 204 were even, 53
won material, and 95 lost material to the immediate recapture. But a
material-losing capture was *available* in 1,817 of 2,986 positions (61%) and
he chose one 95 times: **3.18% of his moves against 4.10% of legal moves — a
0.78× preference.** He avoids them relative to opportunity. The engine then
clears 53 of the 95 at under 50cp. What survives is 42 genuinely costly cases
in 2,996 moves (1.4%), below base rate.

**Style, opportunity-adjusted (RECENT, observed).** Captures **4.14×** and
checks **2.84×** more often than the positions offer. These are the two traits
that survived denominator testing; "forward movement" did not (1.10×).

**King safety** is covered in §3.4. Castling: 67% of games, median move 9.

**Unknown.** Pawn decisions entirely — no stored evidence, no instrument.
Piece coordination and activity likewise.

### 3.7 Converting advantages, resisting, recovering

**Where it breaks down.** RECENT: he reached +3 in **76** games and won **45**
(59%).

His 49 RECENT losses, classified from the eval curve between each game's own
peak and the following trough:

| Shape | Losses |
|---|---|
| one move ≥60% of the fall (**cliff**) | 11 (22%) |
| mixed | 10 (20%) |
| worst move ≤40% (**slide**) | 2 (4%) |
| **no decisive fall at all** (<200cp peak→trough) | **26 (53%)** |

Of the 23 with a real fall, the worst single move accounts for a **median 58%**
of it, and the median lost game contains **6 moves costing 100cp or more**.
**Supported:** naming one move as "the blunder" captures about half of what
happened, and over half his losses had no collapse to explain — he was never
meaningfully better.

**Does well — demonstrated recovery, which a results-first reading hides.**

- `73140de9` (RECENT, Black, 1322 v 1433): at move 19 the eval was **−9970** —
  he was facing forced mate — and he played the engine's best move anyway
  (`Qg3`, 0cp). **The opponent did not deliver it.** By move 23 he was +396. He
  punished **both** errors offered, missed none, and **won by checkmate** — all
  while also missing mate in 3 at move 20.
- `66ac48e5` (RECENT, White, 1293 v 1190): move 9 took him from +491 to −197;
  he then played **eight consecutive engine-approved moves** (m11–m20, all 0cp)
  and rebuilt the eval from −208 to **+509**. He also made 11 blunders in that
  game and punished 1 of 8 opponent errors. Both halves are true.

**Representative sequence, and the hypothesis it supports.** `2af810fd`
(lichess LFLLI2MK, blitz 300+3, 1290 v 1329, lost on time), every step
board-verified:

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

He supplied both halves of the discovered attack and then removed his own
screen. Worst single move = 29% of a 1,205cp fall. **Hypothesis:** the check at
move 16 is the same shape as the five alternative checks in §3.2. Intention
unknown; only asking at move 16 settles it.

### 3.8 Endgames, separated by the ending actually reached

New analysis for this profile (FULL, classified from the pieces on the board).
The single endgame figure I reported earlier hid a 3.5× spread:

| Ending reached | Games | His moves | Mean cp lost | Blunder rate |
|---|---|---|---|---|
| **queens still on** | 92 | 864 | **482.8** | 11% |
| minor pieces only | 26 | 545 | 221.9 | 8% |
| rook plus a minor piece | 112 | 1,562 | 196.7 | 9% |
| **rook endgame** | 34 | 689 | **135.5** | 9% |
| king and pawns only | 3 | 100 | — (too few) | — |

**Supported:** pure rook endings are his most accurate ending and
queens-still-on positions his least, by a factor of 3.5 in mean loss. **Not
supported:** that he "is good at rook endings" in an absolute sense — 135.5cp
per move is still high; it is his best *relative* ending.

**Unknown.** King-and-pawn endings: three games, 100 moves. His taught endgame
material is almost entirely king-and-pawn and Lucena, which he therefore
practically never reaches.

### 3.9 Opponent strength, platform, time control, clock

**Platform and time control (FULL, observed).** These are different rating
pools and are not comparable as skill measures:

| Platform | Control | Games | Moves | Win % | Mean cp | Blunder % |
|---|---|---|---|---|---|---|
| chess.com | rapid | 508 | 14,976 | 46% | 192.0 | 10% |
| lichess | blitz | 103 | 3,242 | 52% | **108.2** | 9% |
| chess.com | blitz | 51 | 1,498 | **27%** | 213.3 | 10% |
| coach | untimed | 113 | 2,273 | 0% | 100.9 | **4%** |

His own rating: lichess median **1310** (range 1202–1391), chess.com median
**1161** (824–1367). Separate pools.

**He plays more accurately in lichess blitz (108.2cp) than in chess.com rapid
(192.0cp), despite less time.** **Limit:** platform is confounded with date —
the lichess games are the recent ones (§4) — so this cannot be attributed to
the platform or the time control on its own.

**Opponent strength — lichess only (101 of 103 games with both ratings):**

| Band | Games | Won | Win % | Mean cp |
|---|---|---|---|---|
| opponent 100+ weaker | 3 | 3 | 100% | 79.4 |
| 25–99 weaker | 24 | 12 | 50% | 113.4 |
| within 25 points | 44 | 24 | 55% | 121.8 |
| 25–99 stronger | 24 | 12 | 50% | 79.5 |
| 100+ stronger | 6 | 3 | 50% | 145.0 |

**Flat.** Against opponents 25–99 points stronger he scores the same 50% as
against equals, with a *lower* mean loss (79.5 vs 121.8). On this evidence —
and it is only 101 games, with 6 in the top band — **his self-report that
stronger opponents understand things he does not is not visible in the lichess
results.**

**The chess.com bands are excluded, not reported as a finding.** They read
100% against weaker (65 of 65), 50% at level, 11% against stronger (13 of 116)
— an odds ratio near 21 between winning and the opponent appearing weaker. That
is far too deterministic for a 25–99 point gap. Stored `user_rating` is
identical to the PGN `WhiteElo`/`BlackElo` in **400 of 400** sampled games and
**no PGN carries a `RatingDiff` tag**, so I cannot establish whether those Elo
values are pre- or post-game. If post-game, the band *encodes* the result and
the table is circular. **Unresolvable from our data**; it needs chess.com's own
rating history.

**Clock: unknown.** A reading survives on only **309 of his 2,996** RECENT
moves (10%) against ~82% product-wide. Two bands are readable — over 3 min:
210 moves, 53.4cp, 6%; 1–3 min: 66 moves, 82.7cp, 14% — and two are not
(30–60s: 10 moves; under 30s: 23). His own pace, from 297 readings: median
**5 seconds** per move. **No claim about his clock behaviour is supportable**,
and the earlier "30–60s is his danger band" rested on ten moves and is
withdrawn.

### 3.10 Learning: independent vs assisted, retries, unfamiliarity, delay

**232 attempt records** recovered from `learning_sessions.events[].attempt` —
the richest learner evidence in the product, and a source I twice wrongly
called absent.

**Independent vs assisted (graded attempts only):**

| | Correct | Incorrect |
|---|---|---|
| unassisted | 22 | 62 (26%) |
| assisted | 18 | 22 (45%) |

First answers unassisted: 17 of 58 (29%). **Untimed is not assisted** — 184 of
232 attempts record no assistance, and `assistance_measured` is true on 209.
Assistance used: `hint` 24, `guided_line` 10, `answer_revealed` 8,
`hint`+`answer_revealed` 6. `retry_index` reaches **7**; one item drew **15**
`show_on_board` requests.

**What he says about his own choices** — observed self-report on 82 trials, not
a general habit:

| Reason he selected | Times |
|---|---|
| **`looks_active`** | **34** |
| `not_sure` | 20 |
| `keeps_piece_safe` | 18 |
| `uses_rule` | 6 |
| **`checked_landing_square`** | **4** |

`reasoning_consistent` false on 54, true on 28. Recorded misconceptions:
`piece_left_unsafe` **51**, `endgame_rule_not_applied` 18,
`activity_before_safety` 8, `piece_safety_relationship_unclear` 6,
`reason_does_not_match_move` 2.

**Supported, with its limit stated:** on the trials where he was asked, the
reason he chose most often was that a move *looked active*, and the reason
naming the missing check was his least chosen. That is consistent with his own
"gut feel" self-report. It does **not** by itself establish a general habit or
a cause — 82 trials, mostly on familiar positions (`distinct_position` true on
only 35 of 232).

**Delayed application — the one real before/after chain, `piece_safety`:**

| Date | Stage | Unfamiliar | Unassisted | First answer | Result |
|---|---|---|---|---|---|
| 09-02 | transfer | yes | yes | — | ✗ |
| 09-07 | retain | yes | 7 attempts, then hint + 12 help | yes, then no | ✗ ×7, then ✓ assisted |
| **09-10** | **transfer** | **yes** | **yes** | **yes** | **✓** |
| 09-17, 09-24, 09-28 | recall | no | mostly | mixed | mostly ✗ |
| **09-25** | **transfer** | **yes** | **yes** | **yes** | **✓** |

**Supported:** his first transfer attempt, on the day teaching began, failed;
two later transfer attempts — **8 days and 23 days after** — were unassisted
first answers on unfamiliar positions and both succeeded. **Not supported:**
"he has learned piece safety" — familiar recall drills kept failing unassisted
*after* both transfer successes, and three transfer attempts is a small base.

**The in-game half of that chain is empty.** All 95 game observations fed to
the learning ledger carry `correct: null` — exposure, not outcome.

**Also unscored:** his diagnostic sessions are all marked `abandoned` or
`in_progress`, yet hold **37 scored attempts** (32 understood). One session
reached all 20 puzzles. No diagnosis was ever produced from them.

---

## 4. Change over time

Within platform, so a platform switch is not mistaken for improvement.

| Platform | Period | Games | Dates | Win % | Mean cp | Blunder % |
|---|---|---|---|---|---|---|
| lichess | oldest third | 34 | 26-04→26-09 | 56% | **171.5** | 7% |
| lichess | middle | 34 | 26-09→26-09 | 50% | **88.3** | 11% |
| lichess | newest | 35 | 26-09→26-10 | 51% | **66.7** | 9% |
| chess.com | oldest third | 196 | 26-02→26-05 | 49% | 189.6 | 9% |
| chess.com | middle | 196 | 26-05→26-06 | 39% | 206.6 | 10% |
| chess.com | newest | 198 | 26-06→26-09 | 45% | 174.6 | 10% |

**Supported, and it speaks directly to "stuck":** on lichess his mean
centipawn loss fell by about 61% across the window — 171.5 → 66.7 — while his
win rate stayed flat at 50–51%. **He is playing measurably more accurately and
not winning more.** On chess.com the same window is roughly flat.

**Limits.** The oldest lichess third spans five months and 34 games while the
other two sit inside six weeks, so the comparison is uneven; blunder rate did
*not* fall (7% → 9%), which means the improvement is in the many small
inaccuracies, not in the decisive errors. That is consistent with §3.7: his
losses are decided by a handful of big moves, and those have not changed.

---

## 5. Plain-English description

He is a classical, narrow-repertoire player — `1.e4` as White, `1…e5` against
it — who plays his first five moves almost perfectly and then falls off a
cliff. His first serious error arrives at **median move 8**, and in nearly
three games in four it has arrived by move 10. Everything after that is played
from a position already compromised, which is why "weak middlegame" is the
wrong description: the middlegame is where the damage shows, not where it
starts.

He is sharp and forcing by temperament — he plays captures four times and
checks nearly three times more often than the positions offer them — and that
temperament is both his strength and the shape of his errors. He takes free
material four times in five and converts two mates in three. But when he is
wrong in a prompted test he reaches for a capture or a king move; and in five
of nine positions where mate was available in one move he played a *different*
check. He has told us, on the trials where he was asked, that his most common
reason for a move is that it **looks active**, and his least common is that he
**checked the square he was moving to**.

Given a position and no clock, he is better than his results: 32 of 37
diagnostic items exactly right, including every fork, skewer and mate pattern
put to him, and 11 of 14 at the top of the tested range. His defence is the
weakest part of his game and it is the one thing two unrelated instruments
agree on — he answers three threats in five, and threat response is also his
worst prompted concept.

He is more resilient than his record suggests. He has won from a position
assessed as a forced loss, punishing both chances the opponent gave him, and he
has rebuilt a lost advantage with eight consecutive engine-approved moves.
Those games also contain eleven blunders between them.

And he is improving in a way he cannot feel: over his recent lichess games his
average error has fallen by about 61% while his win rate has not moved,
because his blunder rate has not moved. He is getting quieter, not safer.

---

## 6. Best-supported barriers to improvement

Ordered by strength of evidence. Each carries its uncertainty.

1. **His games are decided in the window just after theory ends** — moves
   6–11. Blunder rate multiplies eightfold from moves 1–5 to 6–10; median first
   100cp+ error at move 8; 73% by move 10. *Strongest and most consistent
   finding; stable across 806 games and both platforms.* What is unknown is
   **which positions** — no opening is identifiable on his lichess games.
2. **Threat handling.** 162 of 268 answered; `king_safety` in 60 of 100 recent
   games; weakest prompted concept. *Two independent instruments agree.* The
   cause is unknown and the three candidate causes need different teaching.
3. **Decisive errors are not improving even though accuracy is.** Mean loss
   −61% on lichess, blunder rate 7%→9%, win rate flat. *Supported, with an
   uneven window.* This is the mechanism of feeling stuck.
4. **Conversion.** 45 of 76 +3 positions won, and the median lost game holds
   six 100cp+ errors with no single dominant one. *Observed.*
5. **Queens-on endings cost him 3.5× what pure rook endings do** (482.8 vs
   135.5cp). *Observed over 92 and 34 games.* Meanwhile the endgame material he
   has been taught is king-and-pawn and Lucena, which he reaches in 3 games of
   806.
6. **A possible single mechanism, hypothesis only:** that he commits to the
   first forcing move he sees. It would explain the five alternative checks,
   the three single-move calculation submissions, `stopped_early`, and the
   `Rh6+` sequence. It is not measured, and a single-move submission may be an
   interface misunderstanding.

**Not a barrier, on current evidence:** stronger opponents. His lichess results
are flat across rating bands, including 50% against opponents 100+ points
above him. His self-report is not visible in the data — though 6 games in that
band is thin, and the chess.com picture is unresolvable.

---

## 7. The few questions that would change the coaching decision

Each checked against existing records first.

1. **Does he calculate further when asked to?** *Records checked:* the
   instrument exists and is wired, with **4 attempts over 2 positions** — not
   enough. Twenty positions, with some where the first forcing move is *not*
   best, would separate "stops early" from "cannot see further" and would
   settle barrier 6. This is the highest-value question.
2. **What does he see when the opponent threatens something?** *Records
   checked:* nothing stores it — `prediction_correct` is null on all 232
   attempts and the three misconception collections hold 0 rows. Until asked,
   barrier 2 cannot be turned into teaching, because "did not see it", "saw and
   misjudged" and "saw and declined" need different lessons.
3. **Which positions fail at moves 6–11?** *Records checked:* his lichess games
   carry no opening identity, and `opening_key` exists on 8 of 20,293 games. The
   positions themselves are available in the PGNs; grouping his first-error
   positions by line is read-only work that has not been done.
4. **Are the chess.com Elo values pre- or post-game?** *Records checked:*
   stored rating equals the PGN header in 400 of 400 games and no RatingDiff
   tag exists. Not resolvable from our data; it needs chess.com's rating
   history. Until then no claim about his performance by opponent strength on
   that platform is usable.
5. **His clock.** 10% coverage. Not answerable until clock extraction works for
   lichess imports.

---

## 8. What ChessGuru can responsibly personalise now, and what it cannot

**Can, on current evidence:**

- **Target the move 6–11 window.** It is the best-evidenced thing about him,
  and his own first-error positions are available to drill.
- **His actual repertoire by move sequence** (`1.e4`, `1…e5`), without naming
  openings it cannot identify.
- **Threat positions from his own games**, as questions rather than verdicts —
  the evidence supports the weakness, not yet a cause.
- **Piece-safety landing squares**, sourced from his own stated reasons
  (`looks_active` 34, `checked_landing_square` 4, `piece_left_unsafe` 51),
  stated as what he selected on those trials.
- **Queens-still-on endings** rather than the king-and-pawn material he has
  been taught and almost never reaches.
- **Tell him he is improving**, with the honest caveat: smaller errors, same
  blunder rate.

**Cannot claim:**

- That he has **mastered** anything — every surviving mastery stamp sits on a
  concept he was never shown.
- **Retention**, beyond two unassisted transfer successes 8 and 23 days apart
  on one idea.
- Any **planning or positional** ability or deficit — there is no evidence in
  either direction.
- Anything about his **clock**.
- That stronger opponents beat him more — the lichess data says otherwise and
  the chess.com data is unusable.
- A **single rating** for him. Four exist (920 resolved by the app, 1199, 1241,
  1490) and they are not from one pool.
- That any of his `decision_register` figures mean anything until the index
  join is fixed.

**One thing it should stop doing:** coaching him at the rating the app
resolves. `resolve_coaching_rating` returns **920**, from the median of three
chess.com games, while 87 of his last 100 games are lichess blitz where his
rating is 1490. The puzzles he was served sat at a median rating of 898.
