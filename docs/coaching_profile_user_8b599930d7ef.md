# Coaching profile — user_8b599930d7ef

Read-only assessment, 2026-10-15, against live production. Nothing written, no
code changed. Window: his **100 most recent analysed games**, 2026-09-08 to
2026-10-14 — 2,986 of his moves, 90,048 legal moves across those positions,
2,958 observation rows. Record in the window: **48 won, 52 lost**.

**Revision 2, 2026-10-15.** Four corrections from your review, all measured
and all upheld, plus two errors of my own that your FEN replay exposed. Three
of the corrections change a headline. See section 12; it is the first thing to
read, because several numbers below are superseded by it.

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

Ratings disagree, and verifying *what the application actually uses* changed
the finding — see section 12.3. Four numbers are in play, and the one the app
resolves is **920**, not the 1241 I reported.

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

**One position worth teaching — but not for the reason I first gave.**

```
r1bqk2r/pppp1Bpp/2n5/2b1P3/6n1/2p2N2/PP3PPP/RNBQ1RK1 b kq - 0 8
he played Kf8, at 80cp
```

You replayed it and you are right: **Black is in check.** The only legal moves
are Kf8, Kxf7 and Ke7. So "he declined free material" is the wrong description
— he was in a forced position with three options and chose a king retreat over
the capture. The teaching question is **why retreat rather than capture**, which
is a question about his evaluation of the resulting position, not about whether
he saw the bishop.

And it is **not recurring**. The two "different games" are the same game
imported twice (section 12.5): same platform, same minute, same result, same
colour, two `game_id`s, PGN lengths 564 and 1234. One occurrence, not two.

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
cross-source convergence, not a forced join. Second, **`weakness_type: "unknown"` is 0 of 16**, and section 12.4 shows why
that is not a skill fact — though not for the reason I guessed. No move was
ever submitted on any of them, and the puzzles themselves are not broken.

**Lessons (assisted):** 21 sessions, 7 completed, **6 with a
`help_requested` event**. States: `learning` 9, `can_do_with_help` 4,
`can_do_alone` **2**, `remembered` 1, no state 5.

**Recorded mastery — not verified retention:** 118 rows, `mastered_at` set on
**33**, `mastery_stripped_at` set on **42**, `last_clean_game_at` on 77,
`streak_clean ≥ 1` on 63. States: `monitoring` 75, `shown` 37.

| concept_type | Rows | Mastered | Stripped (ALL artifact — see 12.4) |
|---|---|---|---|
| endgame | 73 | 5 | 30 |
| tactical | 17 | 8 | 5 |
| opening | 13 | 12 | 1 |
| middlegame | 5 | 5 | 0 |
| positional | 5 | 0 | 5 |
| defense | 3 | 3 | 0 |
| general | 2 | 0 | 1 |

**"More masteries stripped (42) than held (33)" is withdrawn — it was an
artifact, not forgetting.** All 42 stripped rows carry
`mastery_stripped_reason: "artifact_backfill_cleanup"`, and **0 of the 42 ever
had `mastered_at` set**: they were never held, so nothing was lost. See
section 12.4 for the corrected table.

The surviving caution still holds: "mastered" is a stored state reached with no
unfamiliarity, delay or no-assistance condition, so **none of it is verified
retention** and none of it should be shown to him as "you have mastered X".

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
| `puzzle_attempts.weakness_type: "unknown"` (16, 0 correct) | **abandoned, not failed** — `moves_tried: []` on all 16; other users solve the same puzzles (section 12.4) |
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

**What I can and cannot conclude.** I previously wrote "the knowledge is
there and the execution is not". **That overreaches and is withdrawn.** The
prompted set he answered tops out at a puzzle rating of 1300 with a median of
898, while he plays at 1490 — so it shows *foundational recognition*, not
knowledge at the complexity his games present. Nothing above distinguishes a
knowledge gap from an execution gap at his playing strength, and the two can
coexist. What is supportable: **at around 900 his recognition of standard
motifs is sound, and his blitz middlegame is where his games are lost.** Those
are two facts, not one causal story.

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

---

## 12. Revision 2 — the four corrections, measured

### 12.1 "Knowledge is there, execution is not" — premature, withdrawn

The prompted evidence is not at the complexity of his games:

| Puzzle difficulty | Understood |
|---|---|
| under 850 | 4 of 5 |
| 850–999 | 17 of 17 |
| 1000–1199 | 0 of 1 |
| 1200+ | 11 of 14 |

Ratings span 777–1300, median **898**. He plays lichess blitz at **1490**, and
**no position above 1300 was ever put to him.** For scale, his own flagged
mistakes have a median `cp_loss` of 231 and a p90 of 764.

Worth noting in his favour: he took 11 of 14 at 1200+, so his recognition does
not collapse at the top of the tested range. But the range stops ~190 points
below his playing strength, so the evidence supports **foundational recognition
at around 900**, not knowledge at blitz-game complexity. **Knowledge and
execution gaps can coexist and this data cannot separate them.**

### 12.2 "Stops at the first forcing move" — one explanation of several

Weakened to a candidate, and the alternatives named rather than dismissed. Any
of these fits the five positions equally well:

- he did not see the mate at all (a pattern gap, not a search gap)
- he saw it, calculated it, and miscalculated the reply
- he saw a forcing move, judged it good enough, and did not look for better
- blitz: he had a move that looked winning and moved on
- the mates were of a shape he does not hold (back-rank, smothered, etc.)

And you are right that **twenty selected problems would not settle it either**:
choosing positions where a second forcing move beats the first presupposes the
mechanism, which is selection bias. A fair design would mix positions where the
first forcing move *is* best with positions where it is not, and compare.

### 12.3 The rating — the app uses **920**, and I had it wrong

Verified by calling the canonical resolver rather than reading fields:

| Source | Value |
|---|---|
| `users.rating_source` | `chess.com` |
| `users.assessed_rating` | 1241 |
| `users.detected_rating` | 1241 |
| `users.lichess_rating` | **1490** |
| `player_profiles.current_rating` | 1199 |
| `get_current_rating()` (sync) | 1241 |
| **`resolve_coaching_rating()` (canonical, async)** | **920** |

The canonical resolver returns **920**, with `source: recent_game_median`,
`platform: chess.com`, `sample_games: 3`, `as_of: 2026-09-24`. It takes the
median of his three most recent **chess.com** game ratings, because
`rating_source` names chess.com.

His play has moved and the anchor has not:

| Platform | Games | Time control |
|---|---|---|
| chess.com | 628 | **rapid 542**, blitz 54, other 32 |
| lichess | 115 | **blitz 115** |
| coach | 137 | untimed |

So the app anchors him on three old chess.com *rapid* games while his recent
play is lichess *blitz*. Corroboration that this reaches difficulty selection:
`routes/training.py` and `routes/diagnostic.py` both import the resolver, and
the puzzles he was actually served sit at a median rating of **898** —
consistent with a 920 anchor, not with 1241 or 1490.

**So the direction of my claim survives but the number and mechanism were
wrong.** It is not "1241 versus 1490". It is that four ratings exist, the app
resolves the lowest, and it derives it from a platform and time control he has
largely stopped playing.

### 12.4 Mastery stripping and the "unknown" puzzles — both artifacts

**Mastery stripping: not forgetting.** All 42 stripped rows carry
`mastery_stripped_reason: "artifact_backfill_cleanup"`, and 0 of the 42 ever had
`mastered_at` set. The artifact rows are visibly corrupt: `concept_id` and
`concept_text` do not match each other (`concept_id: "blocked_bishop"` carries
a queen-mate endgame instruction; `"knight_on_rim"` carries "castle early"),
and `shown_count` runs to 10,593, 6,118 and 1,366. Every one of the 17 rows
with `shown_count > 50` is an artifact; no clean row exceeds 50.

Excluding them, the real picture is 76 rows, 33 mastered, **0 genuinely
stripped**:

| concept_type | Clean rows | Mastered |
|---|---|---|
| endgame | 43 | **5** |
| opening | 12 | **12** |
| tactical | 12 | 8 |
| middlegame | 5 | 5 |
| defense | 3 | 3 |
| general | 1 | 0 |

So the endgame signal (5 of 43) is real and is his weakest area; the opening
strength (12 of 12) is real; and **"positional: 0 of 5" was entirely artifact**
and should be struck from section 5. 36 of the 76 clean rows have
`shown_count: 0` — never shown to him at all.

**The 16 "unknown" puzzle failures: abandoned, not failed, and the puzzles are
not broken.** All 16 have `moves_tried: []` and `time_taken_ms: null` — **no
move was ever submitted.** They cover only 6 distinct `puzzle_id`s, so he met
the same few repeatedly. The control settles the "broken set" guess: across all
users those same 6 puzzles have 5 correct attempts from 5 different users. They
are solvable. These 16 rows are an engagement record, not a skill record, and
my "broken puzzle set" reading was wrong.

### 12.5 My own error: 13% of the window is duplicate records

Your FEN replay led me to check the two "different games", and they are one
game imported twice. Quantified over the window:

| | |
|---|---|
| analysed game records in the window | 100 |
| distinct (platform, minute, result, colour) keys | **87** |
| keys with more than one record | 12 |
| extra records | **13** |

So the window holds about **87 distinct games, not 100**. One chess.com key
holds **three** records with byte-identical PGN lengths. Across all 880 of his
game records, 32 extras (3.6%) — the recent window is worse than his history.

What this does and does not change:

- **Counts are inflated by ~13%.** His 2,986 moves are nearer 2,600; the
  48–52 record is nearer 42–45; every absolute count in sections 2–9 should be
  read as an upper bound.
- **Rates mostly survive**, because a duplicated game duplicates numerator and
  denominator together: 85% free-material conversion, 69% mate conversion,
  113cp middlegame, 57% threat response.
- **Any "this recurred" claim is invalid without de-duplicating first.** That
  is exactly the claim I made about the Kf8 position.

### 12.6 And the free-material split

Checking whether my free-material detector counted forced positions: 33 of the
211 opportunities were in check. The rates are almost identical either way —
**not in check 151 of 180 (84%), in check 28 of 33 (85%)** — so the 85%
headline stands. But every example I quoted came from the in-check subset, so
the illustrations were wrong even though the aggregate was right.

---

## 13. The next assessment: recognition, then evaluation

Per your direction, and designed to investigate the strongest reported concern
without presuming its cause. No code; this is the design.

**The concern.** Threat handling: `missed_pattern: king_safety` 112 flags
across 60 of the window's games, threats answered 155 of 272 (57%), and
`threat_response` is also his weakest prompted concept (2 of his 5 diagnostic
misses). Two instruments, same direction.

**The design.** Positions drawn from **his own games**, at the moment after the
opponent has created a threat, asked in three steps with no clock. Each step is
recorded before the next is shown, because the order is what separates the
causes:

1. **Recognition** — "What is your opponent threatening?" Free or
   multiple-choice over squares/pieces. Recorded before any move is requested.
2. **Response** — "What do you play?" One move.
3. **Evaluation** — "What do you expect after that?" The continuation, two or
   three moves deep.

**What each outcome pattern would mean**, written before seeing any data so the
reading is not fitted afterwards:

| Step 1 | Step 2 | Step 3 | Reading |
|---|---|---|---|
| wrong | — | — | he does not see the threat: a **recognition** gap |
| right | wrong | — | sees it, cannot answer it: an **evaluation/calculation** gap |
| right | right | wrong | answers it without knowing why: fragile, likely to fail when the position shifts |
| right | right | right | he can do this untimed — which points at the clock, and we cannot see his clock |

**Sample and conditions.** Eight to twelve positions, from his own games, mixed
difficulty, no clock, assistance recorded if offered. Mixed in deliberately:
two or three positions where **no** real threat exists, as a control against
him answering "yes there is a threat" to every prompt.

**What it will not settle.** It is untimed, so it cannot distinguish "cannot do
this" from "cannot do this in six seconds" — and he plays blitz at a median 5s
per move. Until clock extraction works for his lichess games, that distinction
stays out of reach, and the assessment should be read with that written on it.

**Instruments to reuse, not rebuild.** `calculation_test` already grades a line
on `found_the_idea` / `sound_through` / `judged_the_end` with `stopped_early` —
steps 2 and 3 are its existing fields. Step 1 is the one genuinely new thing
asked for, and nothing currently stores an answer to "what do you see"
(`user_misconceptions` and `home_today_answers` both hold 0 rows).

## 14. Standing position

Per your recommendation: **the nine-area profile stays as our working
understanding, with its uncertainties intact.** No process-only training is
prescribed. The three strongest things we hold are that his opening phase is
genuinely clean, his blitz middlegame is where games are lost, and threat
handling is his most-corroborated weakness — with the cause unknown.
