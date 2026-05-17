---
name: Production Database Schema
description: chess_coach DB — 38 collections, field names and types for games, coach_sessions, game_analyses, users, and all other collections
type: reference
---

**Database:** chess_coach (NOT test_database)
**Mongo URL:** mongodb://admin_user_mii_s_c:...@mongodb:27017

## Key Collections

### games (69 docs)
- `game_id`, `user_id`, `platform` (chess.com)
- `pgn` (full PGN string)
- `white_player`, `black_player`, `result` (1-0, 0-1, 1/2-1/2)
- `time_control`, `date_played`
- **`opening`** (str, e.g. "Scandinavian Defense") — this is the field that EXISTS
- **NO `opening_name` field** — games only have `opening`, not `opening_name`
- **NO `eco` field** on most games
- `user_color`, `termination`, `imported_at`
- `is_analyzed` (bool), `analysis_status`, `analyzed_at`

### game_analyses (66 docs)
- `game_id`, `user_id`, `analysis_depth`, `analysis_duration_seconds`
- `stockfish_analysis` {accuracy, blunders, mistakes, inaccuracies, best_moves}
- `interpretation` {total_moves, critical_moves, reason_breakdown, gap_breakdown}
- `turning_point` {move_number, move, best_move, eval_before, eval_after}
- `decryption_data` (list of per-move coaching data)
- `termination`, `termination_weakness`

### coach_sessions (3 docs)
- `session_id`, `user_id`, `status`, `user_color`
- `fen_history`, `move_history`, `current_fen`
- `time_control`, `user_time_remaining`, `coach_time_remaining`
- `result`, `termination_reason`, `created_at`, `ended_at`
- `user_rating` (1200), `coach_skill_level`
- `detected_opening`, `opening_to_teach`, `opening_teaching_active`
- `evaluations` (list), `habits_checked`, `habit_violations`
- `pedagogical_mode_active`, `curriculum_active`

### users (2 docs)
- `user_id`, `email`, `name`, `picture`
- `chess_com_username`, `lichess_username`
- `assessed_rating` (1241), `rating_source`, `skill_level`
- `role` (super_admin)

### thinking_scores (66 docs)
- `game_id`, `user_id`, `overall_score`
- `habit_scores` {threat_awareness, tactical_vision, move_verification, king_safety, patience}

### community_training_positions (192 docs)
- `position_id`, `fen`, `best_move_san`, `user_move_san`
- `cp_loss`, `pattern_type`, `difficulty`, `opening_name`

### player_profiles (2 docs)
- `average_accuracy`, `biggest_weakness`, `errors_per_game`
- `top_weaknesses`, `phase_accuracy` {opening, middlegame, endgame}

### problem_lifecycle (3 docs)
- `category` (threw_winning), `anger` (recurring), `state` (active)

## Critical Notes
- Games have `opening` field, NOT `opening_name` — the opening-suggestions endpoint queries `opening_name` which doesn't exist on most games
- DB name is `chess_coach`, not `test_database`
- All 38 collections listed, most important ones documented above

**How to apply:** When querying games for openings, use the `opening` field, not `opening_name`. When backfilling, set BOTH `opening` and `opening_name`.
