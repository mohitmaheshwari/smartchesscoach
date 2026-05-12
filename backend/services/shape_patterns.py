"""
Shape-pattern catalog (TIER 3).

Pure data. No chess imports. No detector logic.
This file is the player-facing language for the 23 visual-danger patterns
the coach can name on the board. Each entry pairs:

  - name           : 2-3 word label shown to the player
  - description    : 1-2 short sentences, present tense, plain English
  - phase_in_scope : opening | middlegame | endgame | any
  - priority       : higher fires first when multiple match
  - geometry_hint  : structured note for the detector engineer (NOT shown to user)
  - verifier_policy: how Stockfish must agree before this pattern fires
                     'engine_confirms_target' : engine top-1 must execute / defend it
                     'engine_in_top_3'        : engine PV top-3 must include the idea
                     'heuristic_only'         : positional, no direct engine confirm

Locked rule: 22 board-verified + 1 heuristic. Tactical patterns MUST verify.

Language rules (signed off 2026-05-12):
  - Class 6-8 English vocabulary only. Audience is Indian players, English may be second language.
  - Keep chess terms Indian coaches already teach (Fork, Pin, Skewer).
  - No idioms, no Western cultural references, no military/animal/food metaphors.
  - Square names in label where it helps memory (h7 Attack, Pawn Hole at g6).
  - No piece-value math, no notation, no PV-speak in player-facing strings.
"""

SHAPE_PATTERNS = [
    {
        "id": "knight_fork",
        "name": "Knight Fork",
        "description": "Your knight attacks two big pieces at once. They can save only one.",
        "phase_in_scope": "any",
        "priority": 95,
        "geometry_hint": "own knight; >=2 enemy pieces of value >= knight on its 8 L-jump squares; both targets must be undefended OR worth more than knight",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "bishop_fork",
        "name": "Bishop Fork",
        "description": "Two enemy pieces on the same diagonal. Your bishop hits both.",
        "phase_in_scope": "any",
        "priority": 90,
        "geometry_hint": "own bishop; >=2 enemy pieces of value >= knight on its diagonal rays; ray unobstructed up to each target",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "rook_fork",
        "name": "Rook Fork",
        "description": "Two enemy pieces on the same line. Your rook hits both.",
        "phase_in_scope": "any",
        "priority": 90,
        "geometry_hint": "own rook; >=2 enemy pieces of value >= bishop on its file or rank rays; ray unobstructed up to each target",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "hidden_attack",
        "name": "Hidden Attack",
        "description": "Your front piece moves, the piece behind it was hidden — now it attacks.",
        "phase_in_scope": "any",
        "priority": 92,
        "geometry_hint": "own slider (B/R/Q) on a ray; own piece between slider and enemy target blocking the ray; moving the front piece reveals the attack on a target of value >= knight",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "pin",
        "name": "Pin",
        "description": "Their piece cannot move. If it moves, a bigger piece behind is lost.",
        "phase_in_scope": "any",
        "priority": 88,
        "geometry_hint": "own slider on a ray; enemy piece on the ray; behind that enemy piece on the same ray is a higher-value enemy piece (or the king for absolute pin)",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "skewer",
        "name": "Skewer",
        "description": "Hit the big piece in front. When it moves, the small piece behind is yours.",
        "phase_in_scope": "any",
        "priority": 88,
        "geometry_hint": "own slider on a ray; higher-value enemy piece on the ray; behind it on the same ray is a lower-value enemy piece; front piece must legally move",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "double_attack_line",
        "name": "Double Attack Line",
        "description": "Two of your pieces on the same line, one behind the other. Double power.",
        "phase_in_scope": "middlegame",
        "priority": 70,
        "geometry_hint": "two own sliders of compatible movement (R+R, R+Q, B+B, B+Q) stacked on same file/rank/diagonal aimed at enemy territory",
        "verifier_policy": "engine_in_top_3",
    },
    {
        "id": "back_rank_trap",
        "name": "Back-Rank Trap",
        "description": "Their king is stuck on the last row. No pawn escape. One check ends the game.",
        "phase_in_scope": "any",
        "priority": 96,
        "geometry_hint": "enemy king on its back rank; all three squares in front blocked by own pawns or pieces (no escape); own rook/queen has access to back rank or can reach it",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "h7_attack",
        "name": "h7 Attack",
        "description": "Your queen and bishop both pointing at h7. Sacrifice the bishop, queen comes, knight jumps in.",
        "phase_in_scope": "middlegame",
        "priority": 85,
        "geometry_hint": "own bishop bears on h7 (or h2 for Black); own queen has access to h-file or h5/h4 diagonal; enemy king on g8 (or g1); enemy knight on f6 NOT a defender, OR h7 pawn undefended by minor piece",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "queen_knight_mate",
        "name": "Queen-Knight Mate",
        "description": "Queen and knight near their king. Together they mate on squares neither can alone.",
        "phase_in_scope": "any",
        "priority": 94,
        "geometry_hint": "own queen and own knight both within 3 squares of enemy king; engine finds forced mate <=5 plies that uses both pieces",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "strong_knight_square",
        "name": "Strong Knight Square",
        "description": "Your knight on a square no enemy pawn can kick. It stays there forever.",
        "phase_in_scope": "middlegame",
        "priority": 60,
        "geometry_hint": "own knight on rank 4/5/6 (white) or 3/4/5 (black); square is defended by own pawn; no enemy pawn on adjacent files can ever attack it (already past or captured)",
        "verifier_policy": "engine_in_top_3",
    },
    {
        "id": "weak_squares",
        "name": "Weak Squares",
        "description": "Their bishop is the wrong colour to defend the squares around their king.",
        "phase_in_scope": "middlegame",
        "priority": 55,
        "geometry_hint": "enemy king zone (3x3 around king) — >=3 squares are one colour and enemy has no bishop of that colour; own pieces can access those squares",
        "verifier_policy": "heuristic_only",
    },
    {
        "id": "free_pawn",
        "name": "Free Pawn",
        "description": "A pawn with no enemy pawn in front or on the side. Push it to promote.",
        "phase_in_scope": "endgame",
        "priority": 80,
        "geometry_hint": "own pawn; no enemy pawn on same file or adjacent files between this pawn and promotion rank",
        "verifier_policy": "engine_in_top_3",
    },
    {
        "id": "open_long_line",
        "name": "Open Long Line",
        "description": "Their corner bishop is gone. The long line to their king is wide open.",
        "phase_in_scope": "middlegame",
        "priority": 65,
        "geometry_hint": "enemy fianchetto pawn moved (g6/g3/b6/b3) AND enemy bishop of that colour no longer on board OR not on the long diagonal; own piece can access the diagonal",
        "verifier_policy": "engine_in_top_3",
    },
    {
        "id": "no_safe_square",
        "name": "No Safe Square",
        "description": "Their piece has nowhere to go. Attack it once more — it falls.",
        "phase_in_scope": "any",
        "priority": 82,
        "geometry_hint": "enemy piece; all legal destination squares are attacked by own pieces with SEE >= 0, OR no legal destinations at all; piece can be attacked by one more own move",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "tired_defender",
        "name": "Tired Defender",
        "description": "One of their pieces is defending two things. Force it to choose.",
        "phase_in_scope": "any",
        "priority": 78,
        "geometry_hint": "enemy piece is the sole defender of >=2 own targets (pieces or critical squares); removing/distracting it loses one target",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "free_piece",
        "name": "Free Piece",
        "description": "Their piece has no defender. Just take it.",
        "phase_in_scope": "any",
        "priority": 99,
        "geometry_hint": "enemy piece attacked by own piece; defenders count = 0; SEE of capture >= piece value",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "long_diagonal_bishop",
        "name": "Long Diagonal Bishop",
        "description": "A bishop controlling the full long diagonal. Strong piece, do not trade lightly.",
        "phase_in_scope": "middlegame",
        "priority": 50,
        "geometry_hint": "own bishop on a1-h8 or a8-h1 diagonal; >=5 squares of that diagonal are not blocked by own pawns/pieces",
        "verifier_policy": "engine_in_top_3",
    },
    {
        "id": "remove_the_guard",
        "name": "Remove the Guard",
        "description": "The piece defending something important — trade or capture it. Then take the target.",
        "phase_in_scope": "any",
        "priority": 80,
        "geometry_hint": "enemy piece X defends enemy target Y of higher value; own move captures or trades X; after X is gone, Y falls to next own move",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "force_the_king",
        "name": "Force the King",
        "description": "Force their king or piece onto a square where you can hit it.",
        "phase_in_scope": "any",
        "priority": 75,
        "geometry_hint": "own move (often check or capture-sac) compels enemy king/piece to a forced square; that square is attacked by own piece(s) on the next move with winning SEE",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "in_between_move",
        "name": "In-Between Move",
        "description": "Before recapturing, you have a check or bigger threat first. Play that first.",
        "phase_in_scope": "any",
        "priority": 85,
        "geometry_hint": "previous move was an enemy capture inviting auto-recapture; instead of recapturing, an intermediate own move (check or threat of mate/major material) wins more than the recapture line",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "knight_mate",
        "name": "Knight Mate",
        "description": "Their king is blocked by its own pieces. A knight check on the right square mates.",
        "phase_in_scope": "any",
        "priority": 98,
        "geometry_hint": "enemy king with all escape squares occupied by own enemy pieces; own knight can deliver check on a square that is not defended; engine reports mate-in-1 or mate-in-2",
        "verifier_policy": "engine_confirms_target",
    },
    {
        "id": "pawn_hole_fianchetto",
        "name": "Pawn Hole at g6",
        "description": "They played g6 but the bishop is gone. That square is a permanent weakness.",
        "phase_in_scope": "middlegame",
        "priority": 58,
        "geometry_hint": "enemy played g6/g3/b6/b3 fianchetto pawn move; enemy bishop of that fianchetto colour no longer on board; squares f6/h6 (for g6) or symmetric for others are accessible to own minor piece",
        "verifier_policy": "engine_in_top_3",
    },
]


# Quick-access by id
PATTERNS_BY_ID = {p["id"]: p for p in SHAPE_PATTERNS}


# Invariant checks (run on import; fail loud if catalog drifts)
assert len(SHAPE_PATTERNS) == 23, f"shape catalog must be 23 entries, got {len(SHAPE_PATTERNS)}"
assert len({p["id"] for p in SHAPE_PATTERNS}) == 23, "duplicate pattern ids"
_heuristic_count = sum(1 for p in SHAPE_PATTERNS if p["verifier_policy"] == "heuristic_only")
assert _heuristic_count == 1, f"locked rule: 22 verified + 1 heuristic; got {_heuristic_count} heuristic"
