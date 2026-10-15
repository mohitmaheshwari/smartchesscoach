# Coaching profile — user_8b599930d7ef

Read-only assessment, 2026-10-15, against live production. Nothing written, no
code changed. Window: his **100 most recent analysed games**, 2026-09-08 to
2026-10-14 — 2,986 of his moves, 90,048 legal moves across those positions,
2,958 observation rows. Record in the window: **48 won, 52 lost**.

## How to read this

Four evidence classes, kept apart on purpose:

| Class | Means | Example |
|---|---|---|
| **OBSERVED** | board-verifiable from the position, engine-free | "a free knight was available in 211 positions; he took 179" |
| **ENGINE** | Stockfish's verdict | `cp_loss`, `eval_after` |
| **DERIVED** | a stored detector's output, named by its own field | `missed_pattern: king_safety` |
| **INFERRED** | my reading of the above — always labelled, never counted | "he stops at the first forcing move" |

Also kept apart: **assisted** (hint, reveal, help event, no clock) from
**independent** (his own game, his own clock); and **recorded mastery** (a
stored state) from **verified retention** (which needs opportunity,
unfamiliarity, delay and no assistance — and which nothing here establishes).

Concept ids are reported under their own field names. Six vocabularies appear
below and **none are forced together**.

---

## 0. Corrections to the previous investigation

Three, all accepted:

1. **Five alternative checks, not six.** Of the nine missed mates he played a
   *different check* in five: Re4+, Bd7+, Be6+, Rxd7+, Be5+. I had counted
   Rxh4 as a sixth — it is a queen capture, not a check. The other three were
   Bd5, axb5, Bxe4.
2. **"Stops searching" is a hypothesis**, not a finding. It is INFERRED from
   five positions, and it has one piece of independent support (§3) at n=4.
   It is not measured anywhere.
3. **The capture weakness is unproven, not refuted.** A preference ratio of
   0.78× shows he does not *prefer* losing captures; it does not prove the
   absence of a weakness. 42 of the 95 cost 50cp or more and remain
   unexplained. The correct status is **not supported by this evidence**.

---

## 1. Goals and intent

**Reliably: he has told us three things.** `player_motivation: "learn"`,
`skill_level: "intermediate"` (self-declared), `plan: "pro"`. Account created
2026-02-10. He also has an **active focus he chose or was given**:
`{cluster: "calculation", name: "Calculation Discipline"}`.

Ratings disagree and the disagreement matters: `assessed_rating` 1241 and
`detected_rating` 1241 (source: chess.com) against `lichess_rating` **1490** —
while 87 of his last 100 games are **lichess blitz**. So we are coaching him at
a band ~250 points below the pool he actually plays in.

**Tentative / missing.** No practice time, no preferred game type, no stated
improvement target. `coaching_profile.preferred_learning_style` reads
`"practice"` — an **unmeasured default** present on all 128 users with no
reader anywhere; it is not evidence of anything.

**What would resolve it.** Two one-off questions: how much time per week, and
what he wants in three months. And one decision for us: which rating band to
coach him at, given 87% of his games are at 1490.

---

## 2. Tactics

**Reliably, and this is a strength area.** OBSERVED, opportunity-paired:

| Opportunity | Took | Offered | Rate |
|---|---|---|---|
| a free undefended piece (3+ points) | **179** | 211 | **85%** |
| mate in one | 20 | 29 | 69% |
| promotion | 7 | 11 | 64% |

DERIVED, paired measures:

| | Took | Offered | Rate |
|---|---|---|---|
| punishing an opponent error | 111 | 174 | **64%** |
| answering a threat | 155 | 272 | 57% |

And ASSISTED (no clock, prompted) from his diagnostic attempts: **fork 4 of 4,
skewer 4 of 4, mate_patterns 4 of 4, discovered_attack 2 of 2** understood, on
puzzles rated 777–1300.

So: he sees free material four times out of five, converts two mates in three,
and with a prompt he recognises every standard motif put to him.

**Tentative / missing.** His DERIVED misses are `missed_tactic` 70 in 50 games
and `subtype: missed_generic_tactic` 42 — but "generic" means the detector
could not say which motif, so that is a count without a diagnosis. The
specific ones are thin: `missed_fork` 7, `missed_pin` 4, `missed_skewer` 2,
`missed_discovered_attack` 2, `missed_mate` 2 across 100 games.

**Unreliable — stated so it is not used.** My fork-availability detector fired
in **582 of 2,986 positions (19.5%)** and he "took" 37. A real fork is not
available in a fifth of all positions; the detector counts any move attacking
two pieces regardless of whether the fork wins anything. **The 6% is an
artefact and must not be read as a weakness.**

**What would resolve it.** The nine mate positions in
[player_investigations_2026_10_15.md](player_investigations_2026_10_15.md) put
to him as a board activity: same positions, no clock. If he finds the mates
with time, the gap is search under pressure, not pattern knowledge.

---

## 3. Calculation

**Reliably: he has actually done the instrument, and he is the only user who
has.** Four `calculation_test_attempts`, both on 2026-10-02:

| # | Found the idea | Sound through | Depth required | Stopped early | Judged the end |
|---|---|---|---|---|---|
| 1 | **found** | 3 | 2 | no | right |
| 2 | missed | 0 | 2 | no | — |
| 3 | **found** | 1 | 2 | **yes** | — |
| 4 | missed | 0 | 8 | no | right |

So 2 of 4 found the first move. Of those two, one calculated past the required
depth and **one stopped early with the idea in hand**. Both times he was asked
to judge the final position he was right.

ENGINE, by phase (material-based, not move-number):

| Phase | Moves | Mean cp lost | Blunder rate |
|---|---|---|---|
| opening | 994 | 41.9 | 5% |
| **middlegame** | **1,417** | **113.0** | **13%** |
| endgame | 575 | 51.6 | 7% |

The middlegame costs him **2.7× the opening** per move. That is where his games
are decided.

**Conversion.** He reached +3 in 77 of these games and **won 45, failed to win
32** — 58% conversion.

**INFERRED, and flagged as such.** Two independent things point the same way:
in five of nine mate positions he played a different check, and on the one
calculation attempt where he found the idea but fell short he **stopped early**.
A reading consistent with both is that he commits once he has *a* forcing
move rather than checking whether a better one exists. **This is a hypothesis
on five positions and one test attempt. It is not measured, and n=4 on the
instrument.**

**What would resolve it.** Twenty more calculation-test positions, chosen where
a second forcing move beats the first. `stopped_early` and `sound_through`
already measure exactly this. That is the single highest-value question we
could ask him.

---

## 4. Openings

**Reliably, OBSERVED from the moves** — necessary because `opening_name` is
absent on all 87 of his lichess games (the lichess importer writes no opening):

| Line | Games |
|---|---|
| as White: e4 e5 | 23 |
| as Black: e4 e5 | 20 |
| as Black: d4 d5 | 7 |
| as White: e4 d5 (Scandinavian) | 6 |
| as White: e4 c5 (Sicilian) | 6 |
| as Black: e4 d5 | 5 |

A narrow, classical, open-game repertoire: 1.e4 as White, 1...e5 against e4.

**This is his best area on the engine numbers** — 41.9cp mean loss, 5% blunder
rate over 994 moves — and on recorded mastery: of 13 `concept_type: opening`
rows, **12 mastered, 1 stripped**, his best ratio of any type.

**One concrete, repeated failure.** The same position appears twice in two
different games, and he played the same losing move both times:

```
r1bqk2r/pppp1Bpp/2n5/2b1P3/6n1/2p2N2/PP3PPP/RNBQ1RK1 b kq - 0 8
games 5bb3e449 and 81663a72, move 8, he played Kf8 both times
```

A free 3-point piece was available and declined, at 80cp, twice. **A recurring
position he gets wrong is the most teachable thing in this entire profile.**

**Tentative / missing.** `missed_pattern: opening_knowledge` fires 52 times in
43 games, which is high, but it cannot say *which* opening. Without
`opening_key` on his games (set on 8 of 20,293 across the product), none of
this can be joined to the 79-key curriculum.

**What would resolve it.** Show him that exact FEN and ask for his move. Then
`opening_key` on lichess imports, so the 52 flags become nameable.

---

## 5. Planning and positional play

**Reliably: almost nothing, and I will not pretend otherwise.**

The only DERIVED evidence is `concept_type: positional` in recorded mastery:
**5 rows, 0 mastered, 5 stripped** — his worst ratio of any type. And
`concept_used` carries `rook_on_open_file` 88 in 36 games, `center_control` 125
in 83, `central_knight` 64 in 48 — but `concept_used` is written **only on good
moves**, so these are congratulations and cannot show the converse.

There is no `missed_pattern` for planning. `pawn_structure` and
`piece_activity` do not appear in his 2,958 rows at all.

**Unreliable.** Any claim about "plans" from move quality. A player can reach a
good square by accident and the record cannot tell.

**What would resolve it.** A board activity that asks for a *plan* rather than
a move — "what are you trying to achieve here, in one sentence" on three
positions from his own games. Nothing in the product asks this today and no
collection stores an answer (`user_misconceptions` and `home_today_answers`
both hold 0 rows).

---

## 6. Defence

**Reliably.** DERIVED: `missed_pattern: king_safety` is his **largest single
weakness signal — 112 occurrences in 60 of 100 games**, with
`subtype: ignored_king_attack` 38 in 29 games and `weakened_shelter` 5. And the
paired measure: he answers a threat **155 of 272 times (57%)** — so he misses
roughly two in five threats against him.

ASSISTED, from the diagnostic: `threat_response` **5 of 7** understood — and
notably **2 of his 5 total diagnostic misses** were threat_response, his
weakest concept there. Recorded mastery shows `concept_type: defense` 3 rows,
3 mastered, 0 stripped — but on three rows that means little.

The convergence is worth naming: threat handling is his weakest area in the
prompted condition *and* his largest flagged pattern in games. Two independent
instruments, same direction.

**Tentative / unreliable.** I measured "his move left an own 3+ piece attacked
and undefended" at 285 of 2,986 (9.5%), but **two of the five sampled examples
had cp_loss 0** — the engine does not mind, because the piece is defended
tactically or the capture loses. **Without a baseline for other players, and
with the engine disagreeing, this number is not usable.**

**What would resolve it.** Positions from his own games where the opponent has
just created a threat, with the question "what is he threatening?" — asked
before he moves. That separates *did not see it* from *saw it and misjudged*,
which no game record can.

---

## 7. Endgames

**Reliably, and the two sources disagree, which is itself the finding.**

ENGINE says his endgames are *fine*: 575 moves, 51.6cp mean loss, 7% blunder
rate — better than his middlegame on both counts. Pawn-only endgames: 81
moves, 5 blunders (6.2%).

RECORDED MASTERY says the opposite, loudly: `concept_type: endgame` is **73 of
his 118 rows — 62% of everything ever taught him — with only 5 mastered and 30
stripped.** Of his 21 learning sessions, the endgame ones sit at `learning`
(4) and `can_do_with_help` (1), with one `can_do_alone`.

Both can be true: he plays the endgames he reaches competently, while the
*taught* endgame material has not stuck. DERIVED
`missed_pattern: endgame_technique` fires 38 times in 22 games, so there is
real content behind the second reading.

**Tentative.** `endgame_opposition` in puzzles: **0 correct of 3**.
`generic_endgame_slip` 17 in 9 games — again "generic", so no diagnosis.

**What would resolve it.** The specific endgame concepts recorded as stripped,
re-asked after a delay on unfamiliar positions. That is the retention test
proper, and nothing has run it.

---

## 8. Clock management

**Reliably: nothing, and the reason is a data gap, not a finding.** A clock
reading survives on **309 of his 2,986 moves (10%)**, against ~82%
population-wide. He plays lichess blitz almost exclusively and the clock is not
reaching his observation rows.

| Clock left | Moves | Mean cp lost | Blunder rate |
|---|---|---|---|
| over 3 min | 210 | 53.4 | 6% |
| 1–3 min | 66 | 82.7 | 14% |
| 30–60 s | **10** | 132.2 | 30% |
| under 30 s | **23** | 34.5 | 4% |

Only the top two rows are readable. The one supportable statement: with 1–3
minutes left he loses about half again as much per move as with over 3 minutes
— 66 moves against 210, suggestive only. His own pace, from 297 readings:
median **5s** per move, p90 21s.

**Withdrawn.** "30–60s is his danger band" rested on ten moves. And the
under-30s row is not a strength: by then a game is decided or being flagged.

**Also withdrawn: the `time_flag` criticism.** It fires on 0.56% product-wide
by design — mistakes only, speed relative to that player's own pace in that
game, already-losing positions skipped — and was recalibrated 2026-09-26 after
the previous test was measured vacuous on 11,984 of 11,984 fires. Its docstring
already records that mistakes are *less* rushed than ordinary moves and that
nothing should aggregate it into an impulsiveness claim.

**What would resolve it.** Fix clock extraction for lichess imports. Until
then, no clock claim about this player is possible, and we should say so rather
than reach.

---

## 9. Learning history

**Independent-game evidence** is in §§2–7. This section is the assisted and
taught record, kept separate.

**Puzzles (assisted conditions, own pace):** 118 attempts, **53 correct (45%)**.

| Type | Correct / attempts |
|---|---|
| skewer | 8 / 9 |
| fork | 10 / 14 |
| tactical_oversight | 12 / 18 |
| calculation_depth | 4 / 5 |
| **piece_safety** | **9 / 24** |
| opening_knowledge | 2 / 3 |
| pin | 0 / 3 |
| endgame_opposition | 0 / 3 |
| king_safety | 0 / 1 |
| `unknown` | **0 / 16** |

Two things stand out. **`piece_safety` 9 of 24 (38%)** is his worst type with
real volume — and `piece_safety` is also his second-largest game pattern (98 in
62 games). Those two sources share the same id, so this is a genuine
cross-source convergence, not a forced join. Second, **`weakness_type:
"unknown"` is 0 of 16** — sixteen attempts, none correct, no type recorded.
That looks like a broken puzzle set rather than a skill fact and should not be
counted against him.

**Lessons (assisted):** 21 sessions, 7 completed, **6 with a
`help_requested` event**. States: `learning` 9, `can_do_with_help` 4,
`can_do_alone` **2**, `remembered` 1, no state 5.

**Recorded mastery — not verified retention:** 118 rows, `mastered_at` set on
**33**, `mastery_stripped_at` set on **42**, `last_clean_game_at` on 77,
`streak_clean ≥ 1` on 63. States: `monitoring` 75, `shown` 37.

| concept_type | Rows | Mastered | Stripped |
|---|---|---|---|
| endgame | 73 | 5 | 30 |
| tactical | 17 | 8 | 5 |
| opening | 13 | 12 | 1 |
| middlegame | 5 | 5 | 0 |
| positional | 5 | 0 | 5 |
| defense | 3 | 3 | 0 |
| general | 2 | 0 | 1 |

**More masteries stripped (42) than held (33).** But "mastered" here is a
stored state reached without any unfamiliarity, delay or no-assistance
condition, so **none of it is verified retention** and it should not be
reported to him as "you have mastered X".

**The breadth probe he nearly finished.** Three `diagnostic_sessions` carry
attempts — 37 in total, one session reaching all 20 — and every session is
marked `abandoned` or `in_progress`, so **no diagnosis was ever produced from
them.** The data is sitting there:

| Concept | Understood / attempted |
|---|---|
| threat_response | 5 / 7 |
| piece_safety | 4 / 5 |
| pin | 4 / 5 |
| mate_patterns | 4 / 4 |
| fork | 4 / 4 |
| skewer | 4 / 4 |
| calculation | 3 / 3 |
| opening | 2 / 3 |
| discovered_attack | 2 / 2 |
| **total** | **32 / 37 (86%)** |

By difficulty: low tier **21 of 22**, mid tier **11 of 15**. Puzzle ratings
777–1300, median 898.

**This is the most important contrast in the profile.** Prompted, untimed, at
puzzle ratings around 900, he understands 32 of 37 — including every fork,
skewer, mate pattern and discovered attack put to him. In his own blitz games
he loses 113cp per middlegame move with a 13% blunder rate and converts 58% of
winning positions. **The gap is not knowledge of the motifs.**

Caveat, stated: the puzzle pool (45%) and the diagnostic pool (86%) are
different sets at different difficulties under different conditions, and are
not directly comparable to each other.

---

## 10. Instruments I do not trust, stated so they are not used

| Instrument | Why |
|---|---|
| my fork-availability detector | fired in 19.5% of positions; a real fork is not available in a fifth of all positions |
| my "left a piece hanging" detector | 2 of 5 sampled examples had cp_loss 0; engine disagrees, and there is no cross-player baseline |
| my two-ply "losing capture" heuristic | disagreed with Stockfish on 53 of 95 moves and was wrong all 53 times |
| `subtype: missed_generic_tactic` (42), `generic_endgame_slip` (17), `generic_oversight` (10) | a count without a diagnosis; "generic" means the detector could not name the motif |
| `puzzle_attempts.weakness_type: "unknown"` (16, 0 correct) | looks like a broken puzzle set, not a skill fact |
| `coaching_profile.preferred_learning_style` | unmeasured default on all 128 users, no reader |
| `concept_used` as evidence of ability | written only on good moves; can congratulate, can never show the converse |

---

## 11. Coach's assessment

**What I understand about him.** He is a 1490-blitz lichess player we have been
coaching as a 1241, playing a narrow classical repertoire — 1.e4, and 1...e5
against e4 — with a clean opening phase (41.9cp, 5% blunders over 994 moves)
and competent endgame play when he reaches one. He is sharply aggressive in a
way the denominators support: 4.24× more captures and 2.84× more checks than
the positions offer. He takes free material four times in five and punishes
roughly two in three opponent errors. Prompted and untimed, he understood 32 of
37 diagnostic positions, every fork, skewer and mate pattern among them.

His games are lost in the middlegame — 113cp per move, 13% blunders, 2.7× his
opening — and in two specific places. He misses roughly two in five threats
against him (`king_safety` 112 flags across 60 of 100 games, `threat_response`
also his weakest prompted concept). And he reached +3 in 77 games and won 45.

**The most useful single thing I can say about him today:** the knowledge is
there and the execution is not. That is a far better problem to have than the
reverse, and it points at process rather than curriculum.

**What I still need to learn, and why.**

1. **Does he stop calculating once he has a forcing move?** This is my
   strongest hypothesis and my weakest evidence — five mate positions and one
   `stopped_early: true` out of four test attempts. It is also the only
   hypothesis that would explain the mate misses, the threat misses and the
   conversion failures with one mechanism. Twenty calculation-test positions
   where a second forcing move beats the first would settle it, using fields
   that already exist.
2. **What does he see when the opponent threatens something?** His largest
   weakness signal is a count of unmade moves. `missed_pattern: king_safety`
   cannot distinguish *did not see it* from *saw it and misjudged*, and those
   need different teaching. Only asking before he moves separates them.
3. **Has anything we taught him actually stuck?** 42 masteries stripped against
   33 held, 73 of 118 rows in endgames with 5 mastered — but not one of those
   states was tested against unfamiliarity or delay, so I cannot tell
   forgetting from a recording artefact.
4. **His clock.** 10% coverage against 82% product-wide. He plays blitz almost
   exclusively, so the condition under which he actually makes decisions is the
   one we cannot see at all.

**Where I would start tomorrow, read-only turned into teaching:** the position
he got wrong twice in two games
(`r1bqk2r/pppp1Bpp/2n5/2b1P3/6n1/2p2N2/PP3PPP/RNBQ1RK1 b kq - 0 8`, Kf8 both
times). It is his own game, it recurs, it is in his main repertoire, and it is
concrete. Everything else above is a measurement; that is a lesson.
