# Review Brief — ChessGuru coaching work, 2026-08-25 → 27

Hand this to the reviewing agent. It assumes no knowledge of the session that
produced the work.

---

## 1. Your job

Review three things, in this order of importance:

1. **Two new detector modules** (`board_concepts.py`, `concept_attribution.py`)
   — are they correct *chess*, and are the measurements honest?
2. **The measurements** quoted in commit messages and planning docs — reproduce
   them, don't take them.
3. **The plans** (`chessguru_master_plan.md`, `coach_gap_closure_plan.md`,
   `coach_test_strategy.md`) — are the priorities right, is anything important
   missing, is anything overclaimed?

**Verify, don't trust.** Every number below was produced by the previous agent
and every one is reproducible. Where you cannot reproduce a number, say so — that
is a finding, not an inconvenience.

---

## 2. Product context (minimum you need)

ChessGuru is a personalised chess coach for 600–1500 players. It imports games
from Chess.com/Lichess, analyses them with Stockfish, finds the mistake a player
*repeats*, gives one instruction, drills it, and then checks later games to see
whether it stopped.

**Stage:** pre-launch. 118 users, ~40 monthly active, **zero paying customers**,
never properly released. Behavioural/engagement data is therefore treated as
contaminated and is NOT used as a baseline. **Corpus data — 14,021 games, 13,425
analyses, 421,464 move observations — IS valid**, because those games were played
on Chess.com/Lichess before ChessGuru touched anything.

**The pitch being built toward:** the coach watches your games, names the pattern
you repeat, plans the fix, and proves it stopped — in simple language, on a board.

**Non-negotiable product rule:** the product must never claim improvement it
cannot prove. There is an explicit "honesty register" of things that cannot yet
be claimed. Treat any weakening of that as a serious finding.

---

## 3. How to verify

Production MongoDB is reachable from the repo host:

```bash
ssh root@72.60.204.176 'docker exec -i chess-coach-backend python -' < your_script.py
```

The container's app root is `/app/backend`; `MONGO_URL` and `DB_NAME` are in its
environment. Relevant collections: `move_observations` (421,464),
`game_analyses` (13,425), `games` (14,021), `user_active_focus`,
`community_training_positions` (37,266).

Two gotchas that already bit once:
- `games` has **no** `created_at`; the field is `imported_at`, stored as a
  **string**. Querying the wrong field silently returns zero.
- MongoDB `$sample` is **not seeded** — two runs give different samples. Do not
  treat a small-sample difference as a contradiction.

Local: `cd backend && python tests/test_board_concepts.py` and
`python tests/test_concept_attribution.py` (plain scripts, not pytest).
`pytest-asyncio` must be installed or async suites silently "fail".

---

## 4. What was built (the commits to review)

| Commit | What |
|---|---|
| `d6dc4b40` | `services/board_concepts.py` — 5 detectors + 30 tests |
| `c513af68` | `services/concept_attribution.py` — 4 attributions + 22 tests |
| `2497e47e` | Landed a pre-existing, uncommitted PIC implementation (not authored in-session) |
| `5542d4fa` | `services/rep_generator.py` + 32 tests |
| `3d9a771e` | `components/coach/RepRunner.jsx`, `lib/repView.js` + 16 tests |
| `324a0c41` | Contract/scope docs |

Plus a design canvas (four product screens, web + mobile) and four planning
documents under `docs/`.

---

## 5. Claims to reproduce

State PASS/FAIL against each, with your own number.

**Detector-naming claims**
- 421k observations split **25.8% named / 74.2% generic**
- `rule_of_square`, `opposition`, `back_rank`, `trapped_piece`, `pawn_race`,
  `zugzwang`, `bad_bishop`, `outpost` each have **zero** observations, despite
  being referenced across the code (`rule_of_square` in 19 places, `opposition`
  29, `back_rank` 48)
- The five new detectors fire on **24.5%** of sampled generic positions
- Attribution fires on **5.4%** (65/1200)

**Corpus/detector-quality claims**
- `simple_hang`: 96.9% precision (n=260, independent SEE), 61.61% taxonomy recall
- `piece_safety.d_live.v1`: 22,583 decisions / 149,886 v16 moves (15.07%),
  9.47% miss rate
- 1,145 of 2,003 `simple_hang` events (57%) sit on pre-SEE schema <16
- 663 of 858 v16 hangs (77%) have rating band `unknown`
- `cognitive_gap == "time_pressure"`: **0 moves, 0 users**; only 20.8% of moves
  carry `time_spent_seconds`

**Wiring claims**
- Neither `caption_pipeline` nor `game_decryption` reads `user_active_focus`
  (game review is focus-blind)
- Nothing under `backend/coach_play/` reads `motif_profiles` (live coaching is
  history-blind)
- `backend/coach_play/teaching_coach.py` is imported by nothing

**Testing claims**
- ~3,098 tests collected by pytest; CI runs **4 files**; 4 suites fail to collect

---

## 6. Where the previous agent thinks it is weakest

Start here. These are self-identified; find the ones that were missed.

### 6.1 The detectors' precision was never measured ★ biggest gap
Firing *rate* was measured (24.5% / 5.4%). **Correctness was not.** Nobody has
checked whether those 65 attributions are actually right. The tests use ~50
hand-made positions; there is no independent verification on real corpus fires.

This is the exact failure the project criticises elsewhere ("precision and
meaning are separate audits"), and it was committed anyway. **Sample 30–50 real
attributions and judge each on the board.** A false "you let the pawn through" is
worse than `generic_endgame_slip`, and the whole justification for this work is
that a wrong name costs more than no name.

### 6.2 The author's chess was wrong five times
Across the two suites, five test fixtures failed initially and **every one was
the author's chess error**, not a code bug: a knight placed behind a pawn instead
of in front; a king blocking the promotion square it was meant to be racing to; a
white pawn expected to attack downward; a rook "guard" that could always drop
back so no mate ever existed; kings placed so the opposition move was illegal.

The code was right each time — but treat all chess reasoning in these modules
and docs as suspect and check it independently.

### 6.3 Two parallel implementations exist
`rep_generator.py` (safe/unsafe scan reps) was built **without first checking the
working tree**, which already contained a PIC lesson serving `best_move_san`
puzzles. Both are now committed. This duplicates the "one source of truth"
violation the project explicitly forbids. There is also a duplicated locked
constant: `D_LIVE_SEE_FLOOR_CP` in `move_observation_deriver.py` vs
`SEE_FLOOR_CP` in `rep_generator.py`.

### 6.4 Unverified implementation details
- `MAX_ALTERNATIVES = 60` truncates the "was it avoidable?" search. If the saving
  move is the 61st legal move, the code blames the player wrongly. Not measured.
- `trapped_pieces()` mutates `board.turn` on a copy to probe the post-move
  position. Check this is sound (castling rights, en passant, repetition).
- Attribution is O(legal moves × detector cost) per move. **Runtime cost was
  never measured** — it may be too slow for the analysis pipeline.
- `pawn_race` counts tempi only; it ignores what happens after both promote
  (queen check, skewer on the new queen). It may name races that are not races.

### 6.5 Not integrated
Neither module is wired into the observation pipeline. Nothing writes these names
to `move_observations`. The corpus is unchanged. The 5.4% is a *potential*, not a
delivered improvement.

---

## 7. Questions worth an opinion

1. **Is 5.4% worth it?** Or should the effort have gone to
   `missed_generic_tactic` (3,103 events) using the existing canonical fork
   evidence — a bigger bucket with a detector already built?
2. **Is the two-clause attribution rule right?** ("move made it worse" AND "an
   alternative existed".) Too strict? Too loose? It rejects ~4 in 5 presence hits.
3. **Is the build order in `coach_gap_closure_plan.md` correct** — focus→review
   and focus→PWC wiring before more detectors?
4. **Does the test strategy** (`coach_test_strategy.md`) actually catch the
   failure modes of a chess coaching product, particularly the synthetic-player
   cohorts (L4) and honesty tests (L5)?
5. **Is anything in the plans overclaimed** relative to what the corpus supports?

---

## 8. What to return

- One verdict per claim in §5: reproduced / not reproduced / contradicted, with
  your number.
- A precision estimate for the new attributions from §6.1, with the positions you
  judged and your reasoning on each.
- Findings ranked by severity, each with file:line and a concrete failure
  scenario (inputs → wrong output).
- A direct answer to each question in §7.
- Anything the previous agent missed entirely.

**Be adversarial.** The author of this work was asked to be a peer reviewer, not
a cheerleader, and expects the same of you. If the detectors are wrong, if the
5.4% is inflated, if the priorities are backwards — say so plainly with evidence.
Do not soften findings, and do not accept a claim because a commit message states
it confidently.
