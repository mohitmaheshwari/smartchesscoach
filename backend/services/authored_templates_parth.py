"""
Parth's authored caption templates — Round 1 (10 games, started 2026-05-13).

Source of truth for player-facing caption text that Claude is not
allowed to author. Templates are authored by Parth (full-time chess
coach) against 10 stratified games picked by scripts/pick_authoring_games.py.

This file is intentionally empty at scaffold time. Parth fills it in
position-by-position as he reviews each game with ?show_facts=1 on the
URL. Once Round 1 is complete (~10 games × ~30 moves = ~300 instance
captions), we'll review patterns and refactor into reusable templates.

────────────────────────────────────────────────────────────────────
SCHEMA
────────────────────────────────────────────────────────────────────

Each entry is a dict with the following keys:

  id:                  Stable identifier, snake_case. Author picks it.
                       e.g. "OPP_KNIGHT_BLOCKS_OWN_BISHOP_AND_QUEEN"

  fires_when:          Predicate dict over the facts the extractor
                       produces. Mechanical, machine-checkable. Example:
                         {
                           "mover_is_user": False,
                           "cp_loss_range": [50, 200],
                           "moving_piece_type": "knight",
                           "fact:piece_blocks_own_pieces": True,
                         }

  template:            The caption STRING with {placeholders}. Author
                       writes this. Placeholders are filled from facts
                       at render time.
                       e.g. "oops! Opponent's {played_san}. The {moving_piece_type}
                             blocks their {blocked_pieces}."

  required_facts:      List of fact keys the template references.
                       Used at validation time — if a fact is missing,
                       the template doesn't fire (silence > wrong claim).

  priority:            Integer. Higher fires first when multiple match.
                       Reserve 1-20 for tactical; 21-40 for opening;
                       41-60 for strategy; 61-80 for endgame; 81-99 fallback.

  author:              "Parth Gilda" (or "Mohit Maheshwari")
  authored_on:         Date the template landed (YYYY-MM-DD)
  source_game_id:      First game/position Parth saw this pattern in.
  source_move_number:  Move number for traceability.

  notes:               Optional. Free-text author notes — e.g. "this
                       case is borderline; might want to gate harder."

────────────────────────────────────────────────────────────────────
HOW THE AUTHORING WORKFLOW PRODUCES ENTRIES
────────────────────────────────────────────────────────────────────

1. Parth opens game in /game/{id}?show_facts=1
2. For each move he wants to caption, he checks the fact-dump panel
3. He fills a row in the authoring sheet (columns below):

   game_id | move_number | move_san | current_caption | issue_with_current |
   suggested_caption | generalizable_template | facts_needed | author_notes

4. After 10 games, sheet rows get converted into entries below.
   Conversion is mechanical — Claude reads the sheet and emits
   Python dicts. Author retains text authority.

5. New `fact:*` predicates that the templates reference but which
   the extractor doesn't yet produce go on the "extractor TODO" list
   in [[audit-coverage-tracks-surface]].

────────────────────────────────────────────────────────────────────
ROUND 1 ENTRIES — Parth's authoring
────────────────────────────────────────────────────────────────────
"""

AUTHORED_TEMPLATES: list = [
    # Round 1 — empty at scaffold time. Parth fills as he reviews games.
    # First entries land after he completes game 1 of the picked 10.
]


# Index by id for quick lookup.
TEMPLATES_BY_ID = {t["id"]: t for t in AUTHORED_TEMPLATES if "id" in t}


# Mechanical sanity-check: every required_fact in every template
# should either match a known extractor fact OR be on the extractor
# TODO list. Loud failure if a template references a fact that doesn't
# exist anywhere — that's a wiring bug.
def _self_check_required_facts():
    KNOWN_FACTS = {
        # Subset of the facts caption_facts.py emits. Extend as the
        # extractor adds new facts. Not exhaustive — only the keys
        # templates have referenced so far.
        "played_san", "best_move_san", "cp_loss", "moving_piece_type",
        "target_square", "is_check", "is_capture", "is_castling",
        "phase", "mover_is_user", "is_exchange_losing", "opp_reply_san",
        "captured_piece_type",
    }
    EXTRACTOR_TODO = set()  # Add fact names here when a template needs them
                             # but the extractor doesn't produce them yet.
    for t in AUTHORED_TEMPLATES:
        for f in t.get("required_facts", []):
            if f.startswith("fact:"):
                EXTRACTOR_TODO.add(f[5:])
            elif f not in KNOWN_FACTS:
                EXTRACTOR_TODO.add(f)
    return EXTRACTOR_TODO


EXTRACTOR_TODO = _self_check_required_facts()
