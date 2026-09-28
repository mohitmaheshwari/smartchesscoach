# Cold-start content: what exists, and what is actually broken

**Status:** measurements only. No design, no scope, no code. Onboarding and
`/home` belong to `-8f` (onboarding diagnostic) and `-33` (profile /
composition) per `docs/agents/BOARD.md`; both sessions have since ended, so
this is written down rather than handed over.

**Question asked (Mohit, 2026-09-28):** a player who has not played many games
with us and has not imported anything — what do we show them? He proposed a
mix of Lichess theme puzzles and our own, used to find ability where they
solve and weakness where they do not.

---

## 1. The content already exists

Measured against prod data through the local container.

| collection | count | notes |
|---|---:|---|
| `lichess_puzzles` | **4,110,434** | theme **and** rating labelled |
| `community_training_positions` | 45,828 approved | easy 8,675 / medium 24,208 / hard 12,945 |
| `community_puzzles` | 34,652 approved | only 5 motifs |
| `onboarding_puzzles` | 11,812 | |
| `diagnostic_pool` | 388 | |

Lichess theme coverage for the cases Mohit named:

| theme | puzzles |
|---|---:|
| fork | 586,676 |
| pin | 253,487 |
| discoveredAttack | 228,879 |
| deflection | 192,307 |
| hangingPiece | 143,413 |
| skewer | 101,531 |
| backRankMate | 95,340 |

## 2. No user-facing route reads the 4.1M corpus

`lichess_puzzles` is read only by `routes/admin_detector_review.py`,
`scripts/build_diagnostic_pool.py` and the detector benches. It exists to test
our detectors and has never been shown to a player.

Both serving paths read `community_puzzles` instead:

- `services/diagnostic_service.py::_fetch_approved_pool`
- `routes/training.py:1362`

That is why `diagnostic_pool` holds 388 positions while 4.1M sit beside it.

## 3. The diagnostic is already built, including the hard part

`services/diagnostic_service.py`:

| function | does |
|---|---|
| `select_diagnostic_puzzles` | picks the mixed set |
| `_grading_thresholds(puzzle_rating)` | grades against the **puzzle's own rating** |
| `_rating_estimate` | ability band from solves |
| `_category_label` | strengths / growth areas |
| `apply_diagnosis_to_training` | feeds the plan |
| `diagnostic_supersedes_after(n_games)` | hands over to real games later |

`_grading_thresholds` is the line that matters. Grading against the puzzle's
rating is what separates *"you are not strong enough yet"* from *"you
specifically miss discovered attacks"*. Without it, a weakness read from a
failed puzzle is noise — the likeliest explanation for a miss is that the
puzzle was rated 1800 and the player is 900. It is already implemented.

## 4. The funnel is the problem, not the pool

`diagnostic_sessions`, all 45 of them:

| status | sessions |
|---|---:|
| in_progress (started, never finished) | 35 |
| abandoned | 4 |
| skipped | 4 |
| **complete** | **2** |

- **31 distinct real users** started (40 sessions `role=user`, 5 `super_admin`)
- **19 of 45 sessions recorded zero attempts** — started, answered nothing
- completion **2/45 = 4.4%**

**Positive control, so this is not "nobody wants puzzles":** `puzzle_attempts`
holds 462 attempts from 20 distinct users. People do solve here. The
diagnostic specifically loses them, and 42% of starts produce no answer at all.

A larger or better pool changes nothing for the 19 who answer nothing.
Whatever is wrong is on the first screen.

## 5. Order this should be done in

1. **Find why 19 of 45 answer nothing.** Cheapest win available and it gates
   everything else. Watch one real session before improving content.
2. **Point both surfaces at the combined corpus.** Keep community puzzles in
   the diagnostic — they are real mistakes real players at this level actually
   made — and add Lichess for the themes community puzzles cannot cover (5
   motifs only) and for crowd-derived difficulty ratings.
3. **The "explore" surface** Mohit asked for: unbounded, theme-selectable,
   rating-sequenced, attempts feeding `puzzle_attempts`, which already feeds
   `pattern_decay_service`. A player who never imports a game still builds a
   real profile from solving alone.

## 6. The pattern this belongs to

Sixth built-but-unreachable feature found in two days, after `EvalBar`, the
`session_focus` bundle, `CoachTimelinePanel`, `playMoveSound`, and the 80k
community puzzle pool. Work here reliably stops at "wired" and does not reach
"a user can get to it". That is worth treating as a process finding rather
than six unrelated accidents.
