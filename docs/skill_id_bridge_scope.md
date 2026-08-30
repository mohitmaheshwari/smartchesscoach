# Skill-id bridge — reconnect curriculum lessons to stored player history

Date: 2026-08-30 · Branch: `fable/skill-id-bridge` · Status: built, measured, awaiting review

## Problem (measured, not assumed)

`derive_personal_teaching_profile` looks up player history in
`coach_memory.learning.skills` by strict `skill_id ==`. The curriculum passes
content_ids (`king_and_pawn/square_rule`); production history uses an older
vocabulary (`endgame_rule_of_square`, display-name opening ids). Measured on
`chess_coach` 2026-08-30: **1 of 65** players with history was visible to the
profile. The "coach remembers you" layer was structurally dead.

## Design

Two deterministic joins — no fuzzy matching, no LLM:

1. **`LEGACY_ALIASES`** — the entire non-opening production vocabulary is 19
   distinct ids. Each mapped id was hand-verified as the *same teachable
   concept* as its lesson. Ids broader than one lesson (`king_pawn_endgame`,
   `trap_set_italian`, `opening_principles`) are deliberately unmapped and
   listed in `UNMAPPED_TOO_BROAD` — the profile's "you have used this idea
   before" is a factual claim, and a broad id can't license it.
2. **Opening slug rule** — curriculum opening ids were generated as
   `slugify(display_name)[:30]` from the very names production stores
   ("Four Knights Game Italian Variation" → `four_knights_game_italian_vari`).
   `matches_opening_id` inverts that exact rule. A short id requires full
   equality, so "Italian Game" history cannot claim
   `italian_game_knight_attack`.

One consumer change: `_exact_skill` in `personal_teaching_profile.py`
delegates to `find_skill_record` (exact match still wins over aliases).

## Result

| | before | after |
|---|---|---|
| users whose history the profile can see | 1 / 65 | **64 / 65** |

Top reconnected lessons: `king_and_pawn/square_rule` (48 users),
scholar's-mate pair (34), `king_and_pawn/opposition` (31),
`basic_mates/rook_mate` (28), `basic_mates/queen_mate` (27).

Tests: 12 new (`test_skill_id_bridge.py`), including locks that every alias
key exists in the curriculum and every alias value was observed in
production; existing personalization suites still pass (30 total).

## Explicitly out of scope

- Rewriting stored skill_ids (data migration) — the bridge reads, never writes.
- Mapping the 4 too-broad ids — needs a product decision, not a lookup.
- Concept-lesson ids (`pre_move_check` etc.) — these match exactly if/when
  concept lessons use the same id; nothing to bridge until shown otherwise.
