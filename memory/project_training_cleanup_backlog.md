---
name: Training + page-duplication cleanup — DONE 2026-04-21
description: Executed cleanup of orphans from training consolidation + page duplication audit
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

Executed 2026-04-21 in a dedicated cleanup pass. All deletions were grep-verified first (per "verify before deleting" rule — 40% historical miss rate).

**Frontend pages DELETED** (all verified zero external references):
- `pages/CoachHome.jsx`
- `pages/JourneyCognitive.jsx`
- `pages/Progress.jsx`
- `pages/Training.jsx` (legacy original — distinct from `TrainingNew.jsx` which is still alive)
- `pages/PatternTraining.jsx`
- `pages/ThinkingTraining.jsx`
- `pages/ProgressV2.jsx`
- `pages/JourneyV2.jsx`

**Routes DELETED**:
- `/training/legacy`
- `/progress-old`
- `/progress-v2`
- `/dashboard-full`

**Backend DELETED**:
- `_get_lichess_puzzles` / `_format_lichess_puzzle` / `_get_sample_puzzles_by_theme` methods (167 lines)
- `SAMPLE_PUZZLES` curated dict
- `self.lichess_api_base` instance var
- `aiohttp` optional-import guard (no longer needed)

**App.js imports removed**: CoachHome, ThinkingTraining, PatternTraining, JourneyV2, ProgressV2.

**Renamed for clarity**: `import Training from "@/pages/TrainingNew"` → `import TrainingNew from "@/pages/TrainingNew"` with call sites updated. Was a landmine — the alias name diverged from the file name and caused a "did you delete my training page?" moment mid-cleanup. Moral: don't let aliases differ from file names, even if it saves a keystroke.

## Still-ambiguous items (next cleanup task, if desired)
- `/game-old/:gameId` → `pages/Lab.jsx` — likely legacy duplicate of `/lab/game/:gameId` → `pages/LabV2.jsx`. Needs grep audit before removal.
- `/dashboard` alias of `/home` — both render HomePage. Alias kept intentionally for bookmark compat; delete only if strictness preferred.

## Backend test files that reference deprecated endpoints (not touched)
- `backend/tests/test_decay_model_puzzles.py` — calls `/api/training/pattern-puzzles/{pattern}`
- `backend/tests/test_community_training.py` — calls `/api/training/community-feed`
- `backend/tests/test_pattern_prescription_features.py` — same

These keep the two DEPRECATED endpoints alive (`/pattern-puzzles`, `/community-feed`, `/pattern-stats`, `/community-count` in `training_advanced.py`). Deleting the endpoints requires migrating the tests to the canonical `/api/training/prescribed/{weakness}`. Not urgent — marked DEPRECATED in docstrings so a reader knows.

## Not-yet-examined possible orphans
- `backend/services/coaching_puzzle_service.py` still has `WEAKNESS_TO_PUZZLE_THEMES` + `THEME_COACHING_CONTEXT` + `DEFAULT_COACHING` maps. Still used by the coaching-intro copy generator; only delete if refactoring makes them fully unreferenced. Deferred.
