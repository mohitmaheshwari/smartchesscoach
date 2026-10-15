# Canonical coaching profile — player 8b599930d7ef

**Status: canonical, revision 2.** Supersedes the earlier profile, capability
report, investigations and integrity notes for this player, **and revision 1 of
this document.** §2 lists the measurement defects found in revision 1 and §3
lists every withdrawn claim. Read-only throughout: no code, production write,
deployment or migration. No candidate file was copied into any container.

**His stated position** (self-report, 2026-10-15, not independently verified):
target around 2000; feels stuck near 1300; relies on gut feel with limited
calculation; believes stronger opponents understand things he does not.

**Revision 2 exists because the counting did not add up.** Revision 1 reported
4,401 of his moves numbered 1–5 across 806 games, where the ceiling is 4,030.
Tracing that contradiction to the actual rows uncovered three measurement
defects, and correcting them overturned five of revision 1's headline findings.
The numbers below are the corrected ones.

---

## 1. Scope

Two windows, de-duplicated by platform game id (`games.url`), falling back to a
normalised move-sequence hash — which matters, because coach games carry no
`url` and 24 of them are duplicates only the hash catches.

| | FULL | RECENT |
|---|---|---|
| purpose | the baseline for everything below | the surfaces that only logged recently |
| distinct analysed games | **807** (of 850 records, 43 dropped) | 100 |
| dates | 2026-02-23 → 10-15 | 2026-09-01 → 10-15 |
| his moves | **21,846** | 2,996 |
| platforms | chess.com 590, coach 113, lichess 104 | lichess 87, coach 9, chess.com 4 |

**Rated record** (coach games excluded, see defect D3): **694 games, 318 won,
356 lost, 20 drew — a 46% win rate, 47% over decided games.**

**Engine use.** Move quality comes from stored `move_evaluations`. Two
independent checks were run with `chess.engine.SimpleEngine` (depth 20 position
scan, depth 18 per-move ranking) and are labelled where used. `move_number` was
verified to equal the board's `fullmove_number` on 22,897 of 22,929 rows.

**Evidence classes:** **observed** (board-verifiable or a stored engine
figure), **supported** (several independent sources agree), **hypothesis** (one
plausible reading among others), **unknown**.

### Excluded, with reasons

| Source | Why |
|---|---|
| mastery stamps (`mastered_at`) | all 33 surviving stamps sit on concepts the product **never showed him**; the 42 "stripped" are all `artifact_backfill_cleanup` from a 2026-06-04 bulk backfill |
| `shown_count` | a per-render `$inc`, not exposure |
| my fork-availability detector | fired in 19.5% of positions |
| my hanging-piece detector | engine disagreed on 2 of 5 sampled cases |
| `subtype: missed_generic_tactic` (42), `generic_endgame_slip` (17), `generic_oversight` (10) | "generic" means the detector could not name the motif |
| `puzzle_attempts` `weakness_type: unknown` (16, 0 correct) | `moves_tried: []` and no time recorded — no move was ever submitted; other users solve the same 6 puzzles |
| `coaching_profile.preferred_learning_style` | `"practice"` on all 128 users; an unmeasured default with no reader |
| `decision_register` | computed from a misaligned index join; 78.5% of its verdicts change when fixed |
| chess.com opponent-strength bands | circular, see §4.9 |
| **coach games, in any won/lost comparison** | they never record a win — see D3 |

---

## 2. The three measurement defects, and what each one was

### D1 — the coach's own moves were counted as his

`move_evaluations` rows carry `is_opponent_move` as `True` on 122 rows, `False`
on 12,923, and **absent (`None`) on 10,006**. The filter was
`not m.get("is_opponent_move")`, and `not None` is `True`, so every row with the
field absent was kept as his.

On chess.com and lichess this is harmless — only his moves are stored, and the
flag filter and a board-turn filter return **identical** counts (17,367 and
3,289). On **coach** games both sides are stored with the flag absent, so
**1,083 of the coach platform's 2,273 rows were the engine's moves**, across
**106 of 113 coach games**. The signature is unmistakable: 91 games had rows
numbered `[1,1,2,2,3,3,4,4,5,5]`.

Corrected by filtering on whose turn it is on the stored board — a maths test,
not a flag read:

| | revision 1 | corrected |
|---|---|---|
| his moves | 22,929 | **21,846** |
| rows numbered 1–5 | 4,406 | **3,954** (ceiling 4,035) |
| games exceeding 5 such rows | 91 | **0** |

### D2 — the mate sentinel was inside every average

Evaluations are stored to ±10,000, with mate encoded in the top band (406
readings at exactly 9,990, 307 at 9,980, …). **2,179 of 43,692 readings are
≥9,000.** Revision 1's phase, endgame, platform and trend averages all included
them, so they were partly measuring *mate prevalence*, not accuracy:

| | all rows | ordinary rows only |
|---|---|---|
| mean cp lost | 178.1 | **60.1** |
| median | 8 | 9 |

Worse, **most mate rows are not errors.** Of 1,278 mate rows on his moves,
derived from `mate_info` (white-relative, signed, 0 = delivered):

| transition | rows | mean cp_loss | is it an error? |
|---|---|---|---|
| kept his forced mate | 488 | 6 | no |
| already being mated | 292 | 13 | no |
| **let a mate in** | **225** | **7,551** | **yes** |
| **delivered mate** | **120** | 0 | no — a success |
| **gave up a forced mate** | **117** | **6,730** | **yes** |
| created a forced mate | 35 | 0 | no — a success |
| swapped his mate for theirs | 1 | 19,980 | yes |

So **343 mate errors and 643 mate-neutral-or-good rows.** Averaging all 1,278
at 2,055cp inflated every aggregate by roughly 110cp per move.

### D3 — coach games sat in the won/lost split

Coach games record a win **0 times in 113**. Including them puts 113 games in
the "lost" bucket of every outcome comparison. Every won/lost figure in §4.6 is
now rated-games-only, and this defect alone killed two revision-1 claims and one
finding that never reached print (§3).

### A fourth thing, corrected rather than defective

Revision 1 said the stored eval perspective was unusable because "black winners
are positive and black losers are positive". **That was wrong.** It is
white-relative, and consistently so:

| group | games | median final eval | share > 0 |
|---|---|---|---|
| white won | 166 | **+9,975** | 98% |
| white lost | 271 | −348 | 28% |
| black won | 152 | **−460** | 36% |
| black lost | 186 | +842 | 89% |

The correct narrower statement: the perspective is white-relative and must be
flipped for black — which revision 1 did not always do — but the **final** stored
eval does not predict the result, because his games end by resignation, timeout
and abandonment far more often than by the board. All curve work below flips
the sign explicitly.

---

## 3. Superseded and withdrawn

Carried forward from revision 1:

| Earlier claim | Status |
|---|---|
| "he has a capture-consequence habit" | **withdrawn.** Opportunity-adjusted preference 0.78× |
| "`time_flag` is miscalibrated" | **withdrawn.** 0.56% firing is by design |
| "knowledge is there, execution is not" | **withdrawn as premature** |
| "his queen had six safe squares" | **withdrawn.** Depth 20: `bxc5` was best of all 38 legal moves |
| "he left a rook hanging and ignored it" | **withdrawn.** His own knight was the shield |
| "never castles in 41 of 100 games" | **withdrawn.** Disjoint recount: 2 |
| "87% right kind of move" | **withdrawn.** `decision_register` index join |
| "most games have no opening identified" | **corrected.** chess.com 98% named, lichess 0% |

New in revision 2 — **all five of these were revision-1 headlines**:

| Revision 1 claim | Status |
|---|---|
| **"accuracy collapses through the game: 19.4 → 68.3 → 114.6 → 201.2 → 289.5 → 324.0cp"** | **withdrawn (D2).** Ordinary loss is 21.6 → 59.3 → 68.2 → 72.3 → 70.4 → 77.5. There is **one step, at move 6, and then a plateau** — not an escalating collapse |
| **"his games are decided at moves 6–11"** | **withdrawn.** After his first 100cp+ error he is still clearly winning in 15% of games and level in 31%; only 9% are clearly losing. Of the games where it did leave him at −100 or worse, **79% recover to level or better** |
| **"endgames: queens-on 482.8cp vs rook endings 135.5cp, a 3.5× spread"** | **withdrawn (D2).** Ordinary loss is 58–68cp across *every* ending. What differs is mate involvement |
| **"he plays more accurately in lichess blitz (108.2cp) than chess.com rapid (192.0cp)"** | **withdrawn (D2).** Ordinary loss: chess.com rapid 59.4, lichess blitz 59.8, chess.com blitz 60.9. Indistinguishable |
| **"lichess mean loss fell 171.5 → 66.7, −61%, while his win rate stayed flat"** | **withdrawn (D2). There is no improvement trend.** Ordinary loss 50.1 → 68.9 → 59.7 on lichess, 57.7 → 60.7 → 59.3 on chess.com. He is flat, not improving. The "getting quieter, not safer" story in revision 1 rested entirely on the sentinel |
| "clock coverage is 10%, no claim is supportable" | **withdrawn.** The clock is in the source PGNs — 587 of 590 chess.com games. 16,350 ordinary moves recovered, 54× revision 1 |
| "nothing in the product stores a *what did you see* answer" | **withdrawn.** `reflection_sessions` holds **9 of his answers** to exactly that question |
| "castling: 74% in wins vs 59% in losses" | **withdrawn (D3).** Rated: 74% vs 71% — no difference |
| "the ±1500 eval clamp destroys peak-to-trough" | **withdrawn.** There is no ±1500 clamp; evals run to ±10,000 |
| "the eval sign is not usable for direction" | **corrected** — see §2 |

**One finding killed before it reached print.** A 43-game Giuoco Piano family
showed 9 wins and 31 losses — a 21% win rate that would have been the
profile's most actionable claim. **20 of those 43 games were coach games.** On
rated results the line is 9–10, a 47% win rate, exactly his baseline.

---

## 4. The player, by area

### 4.1 Opening repertoire, and what happens when familiar moves end

**His repertoire, read from the moves** (lichess stores no opening name on any
of his 104 games, and `opening_key` is set on 8 of 20,293 games product-wide —
so this is reconstructed from move sequences, not from stored names):

| First four half-moves | Games |
|---|---|
| **W** `e4 e5 Nf3 Nc6` | **133** |
| **B** `e4 e5 Nf3 Nc6` | **96** |
| B `e4 d5 exd5 Qxd5` (Scandinavian) | 37 |
| W `e4 e5 Nf3 d6` | 33 |
| W `e4 d5 exd5 Qxd5` | 24 |
| B `e4 e5 Bc4 Nf6` | 19 |
| B `d4 d5 Bf4 Nc6` | 13 |
| W `e4 e6 d4 d5` | 13 |

**Observed:** an open-games specialist on both sides — `1.e4` and `1…e5`,
heading for the Italian — with the Scandinavian as his main alternative as
Black. Narrow and consistent.

**What he does well.** Moves 1–5 are nearly free: **21.6cp mean loss, median 1,
a 1% blunder rate and zero mate errors** over 3,954 moves.

**Where it breaks down — one step, not a slide.** This is the corrected table:

| His move numbers | Moves | Mean cp | Median | Blunder rate | Mate errors / 1000 |
|---|---|---|---|---|---|
| 1–5 | 3,954 | 21.6 | 1 | **1%** | 0.0 |
| **6–10** | 3,602 | **59.3** | **19** | **8%** | 1.4 |
| 11–15 | 3,230 | 68.2 | 16 | 10% | 6.5 |
| 16–20 | 2,831 | 72.3 | 16 | 11% | 16.6 |
| 21–30 | 4,263 | 70.4 | 15 | 10% | 30.0 |
| 31+ | 3,966 | 77.5 | 1 | 11% | 35.8 |

**Supported:** there is a single sharp discontinuity at move 6 — blunder rate
multiplies by eight, median loss by nineteen — and after move 10 he plays at a
**constant** level for the rest of the game. The thing that keeps rising is mate
errors, which is a property of games reaching a decided state, not of his
accuracy.

**And it does not decide his games.** His first move costing 100cp+ lands at
median move **8** (p25/p75 6/11; 73% by move 10; 693 of 807 games have one, 114
have none). What the position is worth immediately afterwards:

| User-relative eval after his first 100cp+ error | Games |
|---|---|
| still clearly winning (≥ +100) | 102 (15%) |
| still level (−50 … +100) | 218 (31%) |
| worse but playable (−300 … −50) | 303 (44%) |
| clearly losing (< −300) | 63 (9%) |
| a mate error | 7 (1%) |

And of the 300 games where it did leave him at −100 or worse:

| What happened next | Games |
|---|---|
| **recovered to level or better** | **236 (79%)** |
| never recovered | 55 (18%) |
| clawed back part of it | 8 (3%) |

**So the move-8 error is real and the "games are decided there" reading is
wrong.** It is usually survivable and usually survived.

**Representative sequences.** Recovered: `5c3d7a49` m7 `Nxd7` → −125, later
reached mate, won. `73140de9` m7 `Bh5` → −184, won by checkmate.
Never recovered: `7d2c3b44` m11 `b4` → −363, best later −345, lost;
`0f00953e` m3 `Qg5` → −156, best later −170, lost — this one is genuinely
decided at move 3, 47 moves before it ended.

**Counterexample.** 114 of 807 games contain no 100cp+ error at all.

**No opening family stands out.** Folding transpositions by keying on the
*position* after three full moves rather than the move order, eight families
have ten or more decided rated games:

| Side | Rated | Won | Lost | Win% | Mean cp m6–15 | Median 1st error | Line |
|---|---|---|---|---|---|---|---|
| B | 26 | 15 | 11 | 58% | 71.1 | 7 | `e4 e5 Nf3 Nc6 Bc4 Nf6 Ng5 d5` |
| W | 25 | 10 | 15 | 40% | 55.8 | 11 | `e4 e5 Nf3 Nc6 Bc4 h6 d3 Nf6` |
| B | 22 | 12 | 10 | 55% | 62.3 | 10 | `e4 d5 exd5 Qxd5 Nc3 Qa5 Nf3 c6` |
| W | 19 | 8 | 11 | 42% | 58.2 | 8 | `e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Bc5` |
| W | 19 | 9 | 10 | 47% | 69.8 | 7 | `e4 e5 Nf3 Nc6 Bc4 Bc5 d3 d6` |
| B | 19 | 6 | 13 | 32% | 74.8 | 7 | `e4 e5 Nf3 Nc6 Bc4 Bc5 d3 Nf6` |
| B | 16 | 8 | 8 | 50% | 64.2 | 8 | `e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Bc5` |
| B | 13 | 5 | 8 | 38% | 59.1 | 7 | `e4 e5 Nf3 Nc6 Nc3 Bc5 Bc4 Nf6` |

Win rates span 32–58% around a 47% baseline on 13–26 game samples, and the
median first error is move 7–11 in every one. **Observed: no line is
distinctively bad for him.** The move-6 problem is general, not repertoire-specific.

**Unknown.** Whether any *named* opening fails, and whether his errors cluster
on a recurring structural motif rather than a move order — the position-keyed
families are too fine-grained to say, and a motif-level grouping was not built.

### 4.2 Tactical recognition

Opportunity-paired over the full corpus, rated games, turn-filtered (**these
numbers replace revision 1's, which used a 100-game window and the broken
filter**):

| | Available | Taken | Rate |
|---|---|---|---|
| mate in one | 163 | **120** | **74%** |
| a free undefended piece worth 3+ | 1,657 positions | **1,314** | **79%** |

246 of the free-material chances arose while he was in check — he was not
always free to take.

**The striking pattern is what he played instead of mate.** Across the 47
missed mates in one:

| Instead of the mate he played | Count |
|---|---|
| **a different check** | **27 (57%)** |
| something quiet | 13 (28%) |
| a capture | 7 (15%) |

Examples, all board-verified: `ad652319` m40 `Re4+` when `Rd4#` mated;
`45f946c3` m21 `Bd7+` when `Qd7#` mated; `0f24e0b6` m61 `Be6+` when `h7#`
mated; `100897b9` m24 `Qe7+` when `Qh8#` mated. In more than half of these he
found *a* forcing move and played it instead of the one that ended the game.

**Prompted and untimed, he is stronger than his play.** 32 of 37 diagnostic
items exactly right, the grader accepting no alternatives: fork 4/4, skewer 4/4,
mate patterns 4/4, discovered attack 2/2, calculation 3/3. The five misses
cluster at the top of the tested range (four of five at puzzle ratings
1193–1300) and share a shape — three times a capture when the answer was a
different move, twice a king move when the answer was a pawn push.

**Counterexamples and limits.** He took 11 of 14 items rated 1200+. Low tier
21/22 against mid tier 11/15 is 95% vs 73% — a real gradient on 37 trials.
`puzzle_attempts` is a different pool: 53 of 118 overall, `skewer` 8/9 and
`fork` 10/14 but **`piece_safety` 9 of 24** and `pin` 0 of 3.

**Unknown.** Anything above a 1300 puzzle rating — nothing harder has been put
to him, while he plays in a 1490 lichess pool.

### 4.3 Calculation and anticipating the reply

**Does well.** He is the only user who has used the calculation instrument. On
his best attempt he submitted a real three-move line — `Kg8, Nd7, Qd3+` —
**sound through 3 ply** against a required depth of 2, and judged the resulting
position correctly in **both** attempts where he was asked.

**Where it breaks down.** Four attempts across **two distinct positions**:

| Submitted | Found the idea | Sound through | Required | Note |
|---|---|---|---|---|
| `Kg8, Nd7, Qd3+` | yes | 3 | 2 | correct end judgement |
| `Qxe5` | no | 0 | 2 | 3 seconds after the above |
| `Qd3+` | yes | 1 | 2 | **`stopped_early: true`** |
| `h4` | no | 0 | **8** | correct end judgement |

**Three of four submissions were a single move** where the task asked for a
line.

**Hypothesis, not supported — but it now has three independent legs.** That he
commits once he has *a* forcing move. It fits the single-move submissions and
`stopped_early`; it fits **57% of missed mates being a different check**; and it
fits the `Rh6+` sequence in §4.7. It remains a hypothesis because a single-move
submission may be an interface misunderstanding, he did submit a real line once,
and nothing measures his search directly.

**Unknown, and a hole in the product rather than in him.**
`prediction_correct` is **null on all 232** lesson attempts — he has never once
been asked in a lesson to predict the opponent's reply. Candidate-move
generation is recorded nowhere.

### 4.4 Threat recognition and defence

**Observed, over 4,342 positions** where one of his own pieces worth 3+ was
attacked and underdefended: he answered the threat in **3,342 (77%)** of them in
rated games, and 162 of 252 (64%) in coach games. *Revision 1's 60% came from
the 100-game window and the broken filter.*

**Where it breaks down.** `missed_pattern: king_safety` fires **112 times
across 60 of the 100 RECENT games** — his largest single stored signal — with
`subtype: ignored_king_attack` 38 times in 29 games. Independently, in the
prompted condition `threat_response` is his **weakest concept**: 5 of 7, and 2
of his 5 total diagnostic misses, including one at puzzle rating 838 where he
played `Kh6` and the answer was `c5`.

**Supported:** two instruments that share nothing — a board-derived in-game
detector and an untimed puzzle set — both put threat handling at the bottom.
That agreement is what raises this above the other patterns. A 77% answer rate
is nonetheless not a collapse.

**Unknown, and it decides the teaching.** Whether he *fails to see* the threat,
*sees it and misjudges* the answer, or *sees it and declines* for a reason.
`missed_pattern` counts unmade moves and cannot separate the three. §4.10 now
gives nine direct answers to this question — far too few to settle it, but no
longer zero.

### 4.5 Planning and whether successive moves serve one objective

**Still unknown as to intent, and now bounded by a measured null.** The brief is
right that empty detector fields prove nothing, so twelve positional quantities
were computed off the board instead (§4.6). **None of them separates his wins
from his losses.** That bounds the question without answering it: whatever makes
his losses losses is not visible in development, castling, pawn direction, open
files, piece coordination or exchange selection.

What remains genuinely unavailable: his intended plan. It cannot be recovered
from moves, no instrument asks for one, and `user_misconceptions`,
`home_today_answers` and `concept_tests` hold 0 rows. `concept_used` is written
**only on good moves**, so it can congratulate and can never show the converse.
Engine disagreement is not evidence of having no plan.

### 4.6 Positional play, measured from complete games

Twelve quantities computed by replaying all 694 rated games and reading the
board, split by outcome. Rates are per-move where game length would otherwise
confound.

| Measure | In games he won | In games he lost |
|---|---|---|
| minor + rook pieces off home by move 10 | 2.35 | 2.32 |
| move number he castled on | 9.54 | 10.01 |
| castling rate | 74% | 71% |
| queen moves in his first 10 | 0.83 | 0.75 |
| **flank pawn moves (a,b,g,h) by m15** | **0.99** | **1.21** |
| centre pawn moves (d,e) by m15 | 2.80 | 2.64 |
| heavy pieces on an own-pawn-free file at m20 | 0.93 | 0.91 |
| undefended own pieces per position | 1.66 | 1.59 |
| captures per move | 0.273 | 0.233 |
| **captures losing material on the recapture, per move** | **0.043** | **0.034** |
| checks per move | 0.115 | 0.054 |
| mean ordinary cp lost | 51.1 | 88.2 |
| his moves in the game | 28.8 | 29.5 |

**Supported, and it is a null result worth stating plainly:** no positional
measure available from the board distinguishes his wins from his losses. Development
is identical. Castling is identical. Undefended pieces are *slightly higher in
the games he wins*. **Losing captures are more frequent in his wins, not his
losses** — a third independent refutation of the capture-habit claim. The two
quantities that do differ, checks and captures per move, are consequences of
being better, not causes of it; mean cp lost differs by definition.

The one genuine positional candidate is **flank pawn moves: 1.21 in losses
against 0.99 in wins**, a 22% difference on a 0.22-move base. Small, and offered
as hypothesis.

**Style, opportunity-adjusted (RECENT, observed).** He captures **4.14×** and
checks **2.84×** more often than the positions offer. These are the two traits
that survived denominator testing; forward movement did not (1.10×).

**Unknown.** Pawn structure quality (as opposed to pawn-move direction), and
piece coordination beyond the undefended-piece count.

### 4.7 Converting advantages, resisting, recovering

**This section now holds the profile's strongest finding, and it is new.**

Blunder rate by what the position was worth *before* his move, user-relative,
mates removed, 20,554 moves:

| Position before his move | Moves | Mean cp | Blunder rate |
|---|---|---|---|
| losing badly (< −500) | 1,771 | 47.9 | **4.9%** |
| worse (−500 … −100) | 3,632 | 59.6 | 8.3% |
| **level (−100 … +100)** | **9,096** | 43.5 | **5.5%** |
| better (+100 … +300) | 2,128 | 93.9 | 12.4% |
| **clearly better (+300 … +500)** | **1,870** | 97.1 | **16.5%** |
| winning (+500 … +1000) | 1,975 | 72.5 | 10.3% |

**Supported:** his error rate is lowest when the game is level or lost and
**peaks at three times that when he is clearly better.** It replicates
independently on both platforms — chess.com 17% at +300…+500 (n=1,574), lichess
15% (n=296) — and the denominator is moves in that state, so it is not an
artifact of how often each state occurs.

This is the mechanism his self-report is reaching for. He is not being outplayed
from level positions; level is his **safest** state. He is losing the games he
has already won.

Consistent with it: he reached +300 or better in **442 of 807** games and won
**282 (64%)**, losing 144 (33%). And **240 moves threw away 400cp or more from a
+300…+1500 position, across 187 games** — for example `8519d4b8` m37 `Qxe5` at
+1130 costing 1,494cp when `Kg8` held it; `3a41fb4c` m28 `R8e7` at +924 costing
1,338cp when `Qxc7` won; `e5f72b71` m16 `Bf5` at +304 costing 1,249cp.

**Loss shapes**, over his 457 losses, peak-to-trough with the sign flipped:

| Shape | Losses |
|---|---|
| one move ≥60% of the fall (**cliff**) | 116 (25%) |
| **no decisive fall at all** (<200cp peak→trough) | 114 (25%) |
| mixed | 90 (20%) |
| worst move ≤40% (**slide**) | 87 (19%) |
| too few non-sentinel evals to classify | 50 (11%) |

Median **4** moves costing 100cp+ per lost game. A quarter of his losses have no
collapse to explain — he was never meaningfully better in them.

**Does well — demonstrated resilience, which a results-first reading hides.**
He **delivered mate 120 times and created a forced mate 35 times**, against 343
mate errors. `73140de9`: at move 19 the eval was **−9,970** — facing forced
mate — and he played the engine's best move anyway (`Qg3`, 0cp); the opponent
did not deliver it; by move 23 he was +396 and he **won by checkmate**, punishing
both errors offered. `66ac48e5`: move 9 took him from +491 to −197, then **eight
consecutive engine-approved moves** (m11–m20) rebuilt it from −208 to **+509**.
Both games also contain many blunders; both halves are true.

**Representative sequence for the forcing-move hypothesis.** `2af810fd`
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

He supplied both halves of a discovered attack against himself and then removed
his own screen. Worst single move = 29% of a 1,205cp fall. Intention unknown.

### 4.8 Endgames, separated by the ending actually reached

Classified from the pieces on the board, ordinary loss only:

| Ending reached | Games | Ordinary moves | Mean cp | Median | Mate rows | Mate share of moves |
|---|---|---|---|---|---|---|
| rook plus a minor piece | 112 | 1,368 | 58.5 | 0 | 122 | 8% |
| rook endgame | 35 | 620 | 61.2 | 0 | 84 | 12% |
| **queens still on** | 92 | 565 | 67.0 | 0 | **301** | **35%** |
| minor pieces only | 26 | 456 | 68.1 | 4 | 62 | 12% |
| king and pawns only | 3 | 89 | 63.3 | 0 | 11 | 11% |

**Revision 1's 3.5× spread was entirely the mate sentinel.** Corrected, his
ordinary accuracy is **58–68cp in every ending** — indistinguishable, and the
median is 0 in four of five, meaning most endgame moves cost him nothing.

**What does differ is mate involvement:** with queens still on the board,
**35% of his moves are mate-related against 8% in rook-and-minor endings** — a
four-fold difference. **Supported:** queens-on endings are where his games reach
mating positions, in both directions; they are not where he plays inaccurately.
Whether he is the one being mated more often there is **unknown** — the
transition split was not computed per ending.

**Unknown.** King-and-pawn endings: 3 games, 89 moves. His taught endgame
material is almost entirely king-and-pawn and Lucena, which he reaches in **3
of 807 games**.

### 4.9 Opponent strength, platform, time control, and the clock

**Platform and time control, ordinary loss only.** These are different rating
pools and are not comparable as skill measures:

| Platform | Control | Games | Moves | Mean cp | Median | Blunder% | Win% |
|---|---|---|---|---|---|---|---|
| chess.com | rapid | 508 | 14,091 | 59.4 | 8 | 8% | 46% |
| lichess | blitz | 104 | 3,021 | 59.8 | 9 | 8% | 53% |
| chess.com | blitz | 51 | 1,408 | 60.9 | 11 | 9% | **27%** |
| coach | untimed | 113 | 1,176 | **73.7** | 14 | 6% | 0% |

**Corrected and now a null:** his accuracy is the same on every platform and at
every time control — 59–61cp — and revision 1's lichess-blitz advantage was the
sentinel. Note the direction also reversed for coach games: at 73.7cp they are
his *least* accurate, because revision 1 was counting the engine's near-perfect
moves as his.

His own rating: lichess median **1310** (1202–1391), chess.com median **1161**
(824–1367). Separate pools.

**Opponent strength — lichess only** (101 games with both ratings):

| Band | Games | Won | Win% | Mean cp |
|---|---|---|---|---|
| opponent 100+ weaker | 3 | 3 | 100% | 79.4 |
| 25–99 weaker | 24 | 12 | 50% | 113.4 |
| within 25 points | 44 | 24 | 55% | 121.8 |
| 25–99 stronger | 24 | 12 | 50% | 79.5 |
| 100+ stronger | 6 | 3 | 50% | 145.0 |

**Flat.** Against opponents 25–99 points stronger he scores the same 50% as
against equals, with a *lower* mean loss. On this evidence — 101 games, 6 in the
top band — **his belief that stronger opponents understand things he does not is
not visible in his results.**

**The chess.com bands remain excluded, not reported.** They read 100% against
weaker (65 of 65) and 11% against stronger (13 of 116) — an odds ratio near 21
between winning and the opponent appearing weaker, far too deterministic for a
25–99 point gap. Stored `user_rating` equals the PGN Elo header in **400 of 400**
sampled games and **no PGN carries a `RatingDiff` tag**, so pre- versus
post-game cannot be established from our data. It needs chess.com's own rating
history.

**How his games end** — and this reframes the clock question:

| Platform | Terminations |
|---|---|
| lichess (104) | **timeout 41**, checkmate 40, resignation 23 |
| chess.com (590) | checkmate 170, resignation 145, **timeout 141**, **abandonment 115** |

**39% of his lichess games end on the clock.** But of the games he *lost* on
time, he was **already losing in 83% (lichess, n=30) and 68% (chess.com,
n=127)**, and winning in only 10% and 17%. **So timeouts are mostly the
consequence of a bad position, not an independent clock failure** — a
refutation of the obvious reading. The residue is real but small: 22 chess.com
games and 3 lichess games where he was at +100 or better and lost on time.

**The clock itself, recovered from the source PGNs.** The analysis pipeline
discards it — **0 of 23,735 analysis rows carry any clock field** — but the
annotation is in the imported PGN:

| Stage | Coverage |
|---|---|
| source annotation, chess.com | **587 of 590 games (99%)** |
| source annotation, lichess | 44 of 104 (42%) stored, **+2 recovered** by public retrieval |
| source annotation, coach | 0 of 113 |
| parsed and halfmove-aligned to a move | **17,379 moves** |
| of those, ordinary (non-mate) | **16,350** |

*Retrieval attempt, as the brief asked:* all 60 lichess games whose stored PGN
lacked clocks were requested from `lichess.org/game/export/{id}?clocks=true`.
**2 returned PGN with clocks; 58 were redirected to lichess's registration
page** — re-tested individually with 15-second gaps, so it is gating rather
than rate-limiting. Those 58 need an authenticated lichess token. 13 games were
also found where a *duplicate* stored record held the richer PGN.

His pace: median **5.0s** per move, p25 2.3s, p75 11.8s, p95 40.8s.

**Move quality by time remaining**, mates removed:

| Clock left | Moves | Mean cp | Blunder% | Median spent |
|---|---|---|---|---|
| under 10s | 213 | 118.3 | **22%** | 1.5s |
| 10–30s | 422 | 95.8 | 16% | 2.2s |
| 30–60s | 577 | 80.7 | 13% | 3.0s |
| 1–3 min | 2,089 | 73.2 | 11% | 5.3s |
| 3–10 min | 12,629 | 58.1 | **8%** | 5.3s |
| over 10 min | 420 | 51.5 | 5% | 7.5s |

**Observed and monotonic: his blunder rate roughly triples as his clock
drains.** Stated with its limit — the mate-row share also rises at low clock
(25% under 10s against 4% at 3–10 min), and causation runs both ways, since hard
and lost positions consume clock *and* produce blunders. n=213 in the lowest band.

**Does he slow down where it matters?** No, and the pattern matches §4.7:

| Position | Moves | Median time | Blunder% |
|---|---|---|---|
| quiet (|eval| < 100) | 6,193 | 3.9s | 6% |
| **he is better (+100…+500)** | 3,589 | **6.2s** | **15%** |
| he is worse (−500…−100) | 3,226 | 6.5s | 8% |
| critical (|eval| ≥ 500) | 3,342 | **4.9s** | 8% |

He spends *less* time in the sharpest positions than in the ones where he is
mildly worse. And his worst band by blunder rate — when he is better — is not
one where he is short of time.

Time by move number: 2.2s (moves 1–5), 4.9s (6–10), 6.9s (11–15), 8.1s (16–20),
6.7s (21–30), 3.6s (31+). **Observed:** he more than doubles his thinking time
at exactly the point his accuracy drops — the move-6 problem is not a case of
him moving too fast there.

### 4.10 Learning: independent vs assisted, retries, unfamiliarity, delay

**232 lesson attempt records**, recovered from `learning_sessions.events[].attempt`.

| | Correct | Incorrect |
|---|---|---|
| unassisted | 22 | 62 (26%) |
| assisted | 18 | 22 (45%) |

First answers unassisted: 17 of 58 (29%). **Untimed is not assisted** — 184 of
232 attempts record no assistance and `assistance_measured` is true on 209.
Assistance used: `hint` 24, `guided_line` 10, `answer_revealed` 8,
`hint`+`answer_revealed` 6. `retry_index` reaches **7**; one item drew 15
`show_on_board` requests. `distinct_position` is true on only 35 of 232.

**What he says about his own choices** — 82 trials:

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

**Nine direct answers to "What were you thinking before this move?"** — the
evidence revision 1 wrongly said did not exist. `reflection_sessions` holds 9 of
his records across 7 games, all `answered_before_reveal: true`:

| Date | Concept | He chose | Took |
|---|---|---|---|
| 09-01 | `calculation.verified_stored_line` | `not_sure` | 44.9s |
| 09-05 | `calculation.legal_material_loss` | **`thought_piece_safe`** — "I did not notice the knight on a3 attacking my knight on c2" | 10.1s |
| 09-05 | `piece_safety.simple_hang` | **`thought_piece_safe`** — "I did not notice the bishop on d2 attacking my bishop on b4" | 8.6s |
| (two further) | | `not_sure`, `missed_capture` — "I did not consider the full capture sequence" | 17.5s |
| 09-09 | `calculation.legal_material_loss` | **`chose_attack_over_safety`** — "I was trying to continue the attack" | 28.4s |
| 09-11 | `calculation.verified_stored_line` | **`chose_attack_over_safety`** — "I was focused on continuing my attack" | 136.6s |
| 09-16 | `piece_safety.simple_hang` | `none_of_these` | 112.9s |
| 10-02 | `calculation.verified_stored_line` | **`missed_check`** — "I didn't see the check" | 26.5s |

Tally: `not_sure` 2, `thought_piece_safe` 2, `chose_attack_over_safety` 2,
`missed_capture` 1, `none_of_these` 1, `missed_check` 1.

**Observed, on these nine trials only:** twice he reported not seeing an
attacker, and twice he reported choosing to continue his attack instead. Those
two answers are different diagnoses — one is perception, the other is
prioritisation — and on this evidence they are equally common. The brief's rule
applies: this is what he selected on those trials, not a trait.

The product's own `intent`, `intent_confidence` and `free_text` fields are
**not populated anywhere in the nesting** (verified by recursive walk over all
9 records' prompt and response trees). The capture is `selected_option_id`, from
five offered options. So the route named in `routes/reflect.py` exists and is
unused; what exists instead is this.

**Delayed application — the one real before/after chain, `piece_safety`:**

| Date | Stage | Unfamiliar | Unassisted | First answer | Result |
|---|---|---|---|---|---|
| 09-02 | transfer | yes | yes | — | ✗ |
| 09-07 | retain | yes | 7 tries, then hint + 12 helps | yes, then no | ✗ ×7, then ✓ assisted |
| **09-10** | **transfer** | **yes** | **yes** | **yes** | **✓** |
| 09-17, 09-24, 09-28 | recall | no | mostly | mixed | mostly ✗ |
| **09-25** | **transfer** | **yes** | **yes** | **yes** | **✓** |

**Supported:** his first transfer attempt, on the day teaching began, failed;
two later ones — **8 days and 23 days after** — were unassisted first answers on
unfamiliar positions and both succeeded. **Not supported:** that he has learned
piece safety — familiar recall drills kept failing unassisted *after* both
transfer successes, and three transfer attempts is a small base.

**The in-game half of that chain is empty.** All 95 game observations fed to the
learning ledger carry `correct: null` — exposure, not outcome.

**Also unscored:** his diagnostic sessions are all marked `abandoned` or
`in_progress` yet hold **37 scored attempts** (32 understood), one session
reaching all 20 puzzles. No diagnosis was ever produced from them.

---

## 5. Plain-English description

He is a classical, narrow-repertoire player — `1.e4` as White, `1…e5` against
it, heading for the Italian, with the Scandinavian in reserve. He plays his
first five moves almost perfectly: a one-in-a-hundred blunder rate, and most
moves costing nothing at all. At move six, when the remembered moves run out,
his blunder rate jumps eightfold in a single step — and then stays there,
unchanged, for the rest of the game. The common story that a player "falls apart
in the middlegame" does not fit him. He has one discontinuity, and after it he
is simply a constant, moderate-strength player.

That move-eight error, which arrives in nearly three games in four, is also not
where his games are lost. Four times in five he recovers from it. What actually
costs him games is the opposite of what he and I both assumed: **he is at his
safest when the game is level, and at his most dangerous to himself when he is
winning.** From a level position he blunders on about one move in eighteen. From
a clearly better position — a piece up, an attack landing — he blunders on about
one move in six, three times as often, and the same pattern shows up
independently on both sites he plays on. He has thrown away 400 centipawns or
more from a winning position 240 times in 187 games. He reaches a clearly
winning position in more than half his games and converts two in three.

He is sharp and forcing by temperament — he plays captures four times and checks
nearly three times more often than the positions offer them — and that
temperament is both his strength and the shape of his errors. He takes free
material four times in five and delivers three mates in four. But of the 47
times a mate in one was on the board and he missed it, **in 27 he played a
different check.** He found a forcing move and played it instead of the one that
ended the game. He has told us, on the trials where he was asked, that his
commonest reason for a move is that it *looks active*, and his least common is
that he *checked the square he was moving to*.

Given a position and no clock he is better than his results: 32 of 37 diagnostic
items exactly right, including every fork, skewer and mate pattern put to him.
Defence is his weakest area and the only one two unrelated instruments agree on
— he answers about three threats in four, and threat response is also his worst
prompted concept.

His clock matters, but not in the way the raw numbers suggest. Two in five of
his lichess games end on time — yet in more than four-fifths of those he was
already losing when the flag fell, so the clock is mostly recording a lost
position, not creating one. What is real is that his blunder rate triples as his
clock drains, and that he does *not* slow down in the sharpest positions: he
thinks longer when he is mildly worse than when the position is critical.

And one correction to my own earlier account: he is not quietly improving. Over
his recent games his error rate is flat on both platforms. The improvement I
reported last time was an artifact of counting forced mates as ordinary
mistakes.

---

## 6. Best-supported barriers to improvement

Ordered by strength of evidence, each with its uncertainty.

1. **His error rate triples once he is ahead.** 5.5% blunders at level against
   16.5% at +300…+500, over 20,554 moves, replicated on both platforms, with
   moves-in-state as the denominator. *This is the strongest finding in the
   profile and it is new in revision 2.* It is where his rating is going. What is
   unknown is **why** — complacency, unfamiliarity with converting, or
   calculating less carefully when the position feels won are all consistent.
2. **One discontinuity at move 6.** Blunder rate 1% → 8% in a single step, then
   flat; median first 100cp+ error at move 8. *Stable across 807 games and both
   platforms.* But it does **not** decide his games — 79% recovery — so it is a
   barrier to playing well, not the reason he loses. And no opening line stands
   out, so the target is the transition itself, not a repertoire hole.
3. **Threat handling.** 77% answered over 4,342 positions; `king_safety` the
   largest stored signal; weakest prompted concept. *Two independent instruments
   agree.* The cause is unknown, and the nine reflection answers split evenly
   between "did not see it" and "chose the attack instead" — which need
   different teaching.
4. **A possible single mechanism behind 1 and 3, hypothesis only:** that he
   commits to the first forcing move he sees. **27 of 47 missed mates were a
   different check**; three of four calculation submissions were one move;
   `stopped_early` fired; the `Rh6+` sequence fits. Unmeasured, and a
   single-move submission may be an interface artifact.
5. **He is not improving.** Ordinary error rate flat across the whole window on
   both platforms. *Observed.* This is the honest content of "stuck" and it
   replaces revision 1's claim of unrewarded improvement.
6. **Low clock multiplies his errors** — 8% at 3–10 minutes to 22% under 10
   seconds — though causation runs both ways and the lowest band is 213 moves.
   Timeouts themselves are mostly a symptom: he was already losing in 83% of the
   lichess games he lost on time.
7. **Queens-on endings are where his games reach mate** — 35% of his moves
   there are mate-related against 8% in rook-and-minor endings — while the
   endgame material he has been taught is king-and-pawn, which he reaches in 3
   games of 807. *Not* an accuracy gap: ordinary loss is 58–68cp in every ending.

**Not a barrier, on current evidence:** stronger opponents (lichess results are
flat across bands, 50% against opponents 100+ above him); any positional
quantity measurable from the board (twelve tested, none separates wins from
losses); his opening repertoire (no family deviates from his baseline);
material-losing captures (now refuted a third time — they are *more* frequent in
his wins).

---

## 7. The few questions that would change the coaching decision

Each checked against existing records first.

1. **Why does being ahead triple his error rate?** *Records checked:* nothing
   distinguishes the candidate explanations. The 240 moves that threw away 400cp
   from a winning position are identified and available; classifying what kind
   of move each was — a premature attack, a missed defensive resource, a
   simplification error — is read-only work on data already in hand, and would
   turn barrier 1 into teaching. **This is now the highest-value question, ahead
   of the calculation one.**
2. **Does he commit to the first forcing move?** *Records checked:* the
   calculation instrument is wired and holds **4 attempts over 2 positions**.
   The 27 alternative-check positions are the better instrument — asking him in
   those specific positions distinguishes "did not look further" from "did not
   see the mate". I will not claim a fixed number of puzzles settles it; these
   are the positions that bear on it.
3. **When a threat appears, does he not see it or does he choose the attack?**
   *Records checked:* **nine** reflection answers exist and split 2–2 between
   exactly those two options. The instrument works and has run nine times. More
   of the same prompt on his own threat positions is the cheapest high-value
   evidence in the product.
4. **Are the chess.com Elo values pre- or post-game?** *Records checked:* stored
   rating equals the PGN header on 400 of 400 games and no `RatingDiff` tag
   exists. Not resolvable from our data; needs chess.com's rating history. Until
   then no claim about his performance by opponent strength on that platform is
   usable.
5. **The 58 lichess games whose clocks are gated.** *Attempted and failed:*
   anonymous export redirects to a sign-up page. An authenticated lichess token
   would recover them; without it, lichess clock coverage stays at 46 of 104.

---

## 8. What ChessGuru can responsibly personalise now, and what it cannot

**Can, on current evidence:**

- **Positions where he is winning.** The best-evidenced thing about him, and
  240 concrete moves from his own games are already identified. This should
  replace the move 6–11 window as the primary target.
- **The move 6–11 transition**, as a general skill rather than opening theory —
  no line of his deviates from his baseline, so drilling a repertoire would be
  aimed at the wrong thing.
- **His actual repertoire by move sequence** (`1.e4`/`1…e5` into the Italian,
  Scandinavian as Black), without naming openings the product cannot identify.
- **Threat positions from his own games, as questions** — the evidence supports
  the weakness, not yet a cause, and the reflection prompt that asks the right
  question already exists and already works.
- **Piece-safety landing squares**, sourced from his own stated reasons
  (`looks_active` 34, `checked_landing_square` 4, `piece_left_unsafe` 51),
  stated as what he selected on those trials.
- **Queens-still-on positions** rather than the king-and-pawn material he is
  taught and reaches in 3 games of 807 — framed as mating-attack awareness, not
  as an accuracy problem.
- **Low-clock play**, with the honest framing: his blunder rate triples as the
  clock drains, and his timeouts are mostly already-lost positions.

**Cannot claim:**

- That he has **mastered** anything — every surviving mastery stamp sits on a
  concept he was never shown.
- That he is **improving**. He is flat. Revision 1 said otherwise and was wrong.
- **Retention**, beyond two unassisted transfer successes 8 and 23 days apart on
  one idea.
- Any **planning** ability or deficit, or any **positional** strength or
  weakness — twelve board measures were tested and none separates his wins from
  his losses, which bounds the question without answering it.
- That stronger opponents beat him more — his lichess results say otherwise and
  the chess.com data is unusable.
- That any **opening line** is a weakness of his.
- A **single rating** for him. Four exist (920 resolved by the app, 1199, 1241,
  1490) and they are not from one pool.

**Two things it should stop doing.** First, coaching him at the rating the app
resolves: `resolve_coaching_rating` returns **920**, from the median of three
chess.com games, while 87 of his last 100 games are lichess blitz where his
rating is 1490, and the puzzles he was served sat at a median rating of 898.
Second, discarding the clock: the annotation is present on 99% of his chess.com
PGNs and **0 of 23,735 analysis rows retain it**, so every clock-aware coaching
surface is starved by the import path rather than by missing data.
