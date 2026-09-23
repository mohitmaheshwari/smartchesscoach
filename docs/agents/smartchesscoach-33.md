# smartchesscoach-33

**Working on:** player profile on the home page, the focus picker, and
positional measurement.

**Worktree / branch:** `_teaching_loop_scope` (detached, lands on working-code)

**Status:** scoping · **Deployed:** `9520afbc` is on origin

## Files owned

| file | note |
|---|---|
| `services/positional_snapshot.py` | NEW, landed 9520afbc, wired into the deriver at schema 19 |
| `services/blunder_anatomy.py` | NEW — currently **0 importers, dead** |
| `services/behavioural_stats.py` | NEW, read by `player_identity.py` |
| `services/primary_weakness_picker.py` | sources work — **confirmed mine by -8f** |
| `docs/picker_sources_scope.md` | Section 0 only, awaiting Mohit |
| `docs/agents/BOARD.md` | the index |

## Findings other sessions should know

- Only **one** quality id is PLAN-graded
  (`gap:piece_safety:destination_safety_exact`). Independently confirmed by
  -8f: 59 ids = 1 PLAN / 7 CAPTION / 46 SHADOW / 5 DISABLED. Any widening of
  the picker's sources is discarded by `topic_can_be_planned` on the next
  line. 53 of ~86 users share `piece_safety`; 0 have an opening focus.
- `positional` is stored on only 1,771 of 532,399 move_observations — the
  rest sit at schema 18. `scripts/backfill_move_observations.py` treats them
  as `stale_version` and re-derives from stored analysis, no engine needed.
- Nothing reads the stored `positional` block.
  `chess_understanding.calculate_positional_sense()` does substring matching
  on category labels instead.

## Positional queue context (handed over by -8f)

`positional_reason_queue` is 240 rows, all status `pending`, **0 dispositions
ever**. `positional_reason_submissions` has 1 row (Mohit's, 2026-09-09,
incomplete — `concept_label` null).

The gate in `docs/verified_positional_captions_data_lock.md` requires
`disposition == eligible_positional` **plus** a complete contrastive proof,
so with 0 dispositions nothing positional can reach a caption.

**The friction is data entry, not design:** five prose fields per position
(`better_move_fact`, `played_move_fact`, `contrast`, `transferable_lesson`,
`concept_label`), and `voice_warnings()` HARD REJECTS a whole submission on
one word of jargon rather than flagging it.

**Why -8f's drafts only covered 13%:** the queue is sampled by position type
(60 bare endgame / 60 endgame / 60 middlegame / 60 middlegame-with-queens,
36 rows with ≤8 men) and their rules are tactical. The queue's own
`already_explained_by` field names **blockade, knight_outpost,
rook_behind_passer, king_pawn_cover** — those are the concepts it is made of.
`positional_snapshot.py` currently speaks doubled/isolated/backward pawns,
islands, undefended pieces, bad-bishop pawns, centre control, space and
mobility, which barely intersects that list. Closing that gap is the real
positional work.

**Blocked on Mohit:** board decision 6 — picker path 1 / 2 / 3.
