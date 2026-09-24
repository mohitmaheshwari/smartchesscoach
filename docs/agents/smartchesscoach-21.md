# Session -21 — thinking-habit scoring + lichess clock capture

Naming note: BOARD.md says `docs/agents/<session-name>.md`. A file literally
named `-21.md` is awkward on the command line, so this is
`smartchesscoach-21.md`, matching the `from-name` sessions introduce
themselves with. Rename if the board prefers.

---

## What I am building

Three of the five "thinking habits" had never fired once — `tactical_vision`,
`king_safety` and `patience` fired on 0.0% of 4,000 games and scored a
constant 100 while carrying 55% of `overall_score`. That is how a game with 3
blunders and ACPL 324.8 came to read 90.8. Also: lichess games were fetched
with `clocks=false`, so no lichess game has ever had per-move timing.

## Where

- Worktree: scratchpad `habitwt`, branched off `origin/working-code`
- Branch: `fix/habit-scores-and-clocks` (pushed, no PR)

## Files I own

| file | what |
|---|---|
| `backend/services/thinking_score.py` | substantial rewrite of `calculate_game_thinking_scores` + `_categorize_mistake`. **Heaviest edit; coordinate before touching.** |
| `backend/services/move_time_analyzer.py` | appended `resolve_time_control()` + `attach_move_times()`; changed the increment source inside `compute_move_time_stats` |
| `backend/analysis_worker.py` | ~10-line insert in PHASE 6 (registry already lists me) |
| `backend/journey_service.py` | one line: `clocks` `"false"` → `"true"` |
| `backend/tests/test_thinking_score_habits.py` | new |

## Status

done-and-pushed. 17 unit checks pass; corpus-validated on 270 games.
`tests/test_all_flows.py` could NOT be run — needs a live API endpoint
unreachable from the container, fails on `httpx.ConnectError` before reaching
my code.

## Deployed

No. Nothing from this branch is on 72.60.204.176.

Earlier work from this session IS live (game-review truth layer, merged to
`working-code`, deployed 2026-09-07, V5 141→143). Not editing those files now.

## Blocked on

Mohit — board item 1. Deploy, and whether to backfill 16,512 stored
`thinking_scores` (all produced by the broken code) plus re-fetch 56 lichess
games for clocks. Both are writes; not run.

---

## Correction to the registry

`services/caption_facts.py` lists me as "also touched by -21 (older,
landed)". **I have never touched that file.** Verified across all six of my
commits. My landed caption work touched `caption_pipeline.py`,
`caption_fallback_tiers.py`, `decryption_voice/*`, `game_reason_classifier.py`,
`game_decryption_v5_service.py`, `data/captions/R17_coach_move.json`,
`scripts/pwc_coaching_lint.py`, `scripts/caption_why_class.py`.

Rule 1's attribution is correct — the 173 race was -8f and -5b, not me. My
last V5 touch was 143.

---

## C4 — the "does this caption have a why" definition is wrong (NEW)

`services/caption_why_heuristics.py` (-70, 2026-09-22) declares itself "the
ONE definition of does this caption have a why" and drives both the audit that
MEASURES the rule and the review queue that FIXES it. It passes a caption if
**any** of H1 (names a square/piece), H2 (causal connector, which includes the
em dash) or H3 (principle ending) fires.

Measured, running its own functions:

| caption | really explains the played move? | H1/H2/H3 |
|---|---|---|
| `You played Qf6; Nxd3+ was stronger — it trades his bishop.` | no — explains the ALTERNATIVE | **PASS** |
| `Nd4 is a mistake. e4 was better — it attacks the knight on f3.` | no — explains the ALTERNATIVE | **PASS** |
| `Bf6 is a mistake. f5 was better.` | no | fail |
| `Qf6 lets Qxc5 win your bishop on c5.` | yes | PASS |

The first row is the exact caption that started Mohit's complaint on
2026-09-06. It passes, because of the em dash and the word "bishop".

**Consequence:** the definition only catches the bare
`X is a mistake. Y was better.` shape. Captions that explain the *recommended*
move while saying nothing about the move the player actually made are scored
as having a why. On the 744-game corpus that is **34.5% of all flagged
mistakes** — so the metric reports roughly 69% compliance where the honest
number is **34.8%**, and a queue driven by it will skip precisely the captions
that most need fixing.

This is the failure mode recorded in
`memory/feedback_keyword_caption_audit_unreliable.md`: keyword scans
undercount coverage and invent phantom gaps.

**What I am NOT doing:** touching -70's file. Rule 7 is add-only and it is
theirs. `backend/scripts/caption_why_class.py` (mine, landed 2026-09-07)
splits the caption at the alternative-move boundary and returns
`PLAYED_WHY` / `ALT_WHY_ONLY` / `NO_WHY`, which is the distinction that
matters. Hand-validated on a 30-row stratified sample: PLAYED_WHY precision
10/10; two NO_WHY rows were really ALT_WHY_ONLY (both still inside "does not
explain the played move"); one row should not have been in the denominator.
Treat it as ±2pp, not exact.

Proposed resolution for -70 and -33 to decide: fold the three-way distinction
into `caption_why_heuristics.py` as the single source and delete mine, or keep
mine and have the audit import it. Either is fine. What should not survive is
two definitions that disagree by 34 points on the same corpus.
