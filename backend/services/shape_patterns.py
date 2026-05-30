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

  - dynamic_policy : how the pattern's DYNAMIC condition is verified beyond
                     geometric alignment. Added 2026-05-15 after Parth flagged
                     3 detectors firing on positions with valid geometry but
                     no real tactical mechanic. Policies are dispatched in
                     services.shape_layer.verify_dynamics():
                     'geometry_only'              : default; geometry suffices
                     'mate_in_1_simulated'        : a candidate piece must
                                                    have a move that delivers
                                                    checkmate (simulated)
                     'pin_capture_suppress'       : suppress when the played
                                                    move CAPTURES the pinned
                                                    front piece (just a trade,
                                                    not a tactical setup)
                     'skewer_front_defended'      : require the front piece to
                                                    be defended (else it's
                                                    just a hanging-piece
                                                    capture, not a skewer);
                                                    king-front is exempt
                                                    (forced-move by check).
                     'open_line_move_uses_diagonal': for open_long_line —
                                                    suppress unless the
                                                    played move's to_square
                                                    lands ON the long
                                                    diagonal (i.e., the
                                                    player actually moved a
                                                    piece onto the line, not
                                                    merely departed from it).
                                                    Prevents from_square
                                                    coincidence fires (queen
                                                    on b2 captures a2 —
                                                    b2 is on the a1-h8 diag
                                                    but the queen LEFT it).
                     New policies are added when new bug classes surface;
                     keep this list synchronized with the dispatcher.

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
        "id": "pawn_fork",
        "name": "Pawn Fork",
        "description": "Two enemy pieces on the same rank, 2 squares apart. A single pawn push attacks both.",
        "phase_in_scope": "any",
        "priority": 93,
        "geometry_hint": "two enemy pieces of value >= knight on same rank, 2 files apart; own pawn one rank behind the file between them; push square clear; push is legal",
        "verifier_policy": "engine_confirms_target",
        # 2026-05-16 (Mohit fb_eb1d11ba227f): "you walked into this"
        # patterns must be detected on the POST-move board, then
        # attached to the move that CREATED the vulnerability — not
        # the next move that could execute the fork. Default for all
        # other patterns is "pre_move" (your opportunity).
        "detect_phase": "post_move",
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
        "dynamic_policy": "pin_capture_suppress",
    },
    {
        "id": "skewer",
        "name": "Skewer",
        "description": "Hit the big piece in front. When it moves, the small piece behind is yours.",
        "phase_in_scope": "any",
        "priority": 88,
        "geometry_hint": "own slider on a ray; higher-value enemy piece on the ray; behind it on the same ray is a lower-value enemy piece; front piece must legally move",
        "verifier_policy": "engine_confirms_target",
        "dynamic_policy": "skewer_front_defended",
    },
    {
        "id": "double_attack_line",
        "name": "Aligned Pieces",
        # Mohit Day 3 Issue B (2026-05-30): the previous description
        # ("Two of your pieces on the same line — coordinate them for
        # shared pressure on an open file or diagonal.") fired on 131
        # of 5,264 audited moves (2.5%) as the ENTIRE caption — generic
        # without naming the file or the specific pieces. Authored
        # silence per [[no-hollow-coverage]]. R_PROMOTED_shape requires
        # shape_pattern_desc; empty means the rule renders nothing and
        # falls through. Replace when a richer file+pieces template is
        # authored that names what to coordinate.
        "description": "",
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
        "dynamic_policy": "mate_in_1_simulated",
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
        # Mohit Day 3 Issue B (2026-05-30): fired 35 times in 200-game
        # audit, frequently on positions unrelated to king-zone weakness
        # (winning checks, captures). The heuristic_only verifier_policy
        # means there's no engine verification. Authored silence until
        # the detector is tightened to require named weak squares
        # involved in the played move.
        "description": "",
        "phase_in_scope": "middlegame",
        "priority": 55,
        "geometry_hint": "enemy king zone (3x3 around king) — >=3 squares are one colour and enemy has no bishop of that colour; own pieces can access those squares",
        "verifier_policy": "heuristic_only",
    },
    {
        "id": "free_pawn",
        "name": "Passed Pawn",
        "description": "A pawn with no enemy pawn in front or on adjacent files. Push it toward promotion.",
        "phase_in_scope": "endgame",
        "priority": 80,
        "geometry_hint": "own pawn; no enemy pawn on same file or adjacent files between this pawn and promotion rank",
        "verifier_policy": "engine_in_top_3",
    },
    {
        "id": "open_long_line",
        "name": "Open Long Line",
        # v91 (2026-05-25): Parth fb_55e490a74436 — "wrong narrative. not
        # relevant to this position." The previous description overclaimed:
        # said "their corner bishop is gone" (implying a fianchetto setup
        # that may never have existed) and "the long line to their king is
        # wide open" (implying direct king attack when the king may just be
        # adjacent to the diagonal, not on it, with defenders blocking the
        # line). Reworded honestly: the detector knows the enemy lacks a
        # same-colour bishop AND ≥4 squares on the long diagonal are empty
        # — but not that the king is in the line of fire or that the enemy
        # ever fianchettoed. State just what's true.
        "description": "Enemy has no bishop of this colour. The long diagonal has open squares for your queen or bishop to use.",
        "phase_in_scope": "middlegame",
        "priority": 65,
        "geometry_hint": "enemy fianchetto pawn moved (g6/g3/b6/b3) AND enemy bishop of that colour no longer on board OR not on the long diagonal; own piece can access the diagonal",
        "verifier_policy": "engine_in_top_3",
        # 2026-05-19 (Mohit Lab review, move 21 Qxa2): open_long_line fired as
        # secondary narrative on a material-capture move where the queen's
        # FROM square (b2) was on the a1-h8 diagonal — but the queen moved
        # OFF the diagonal onto a2.  The _is_relevant_to_move gate treats
        # from_square overlap as "relevant", but for a purely positional
        # pattern the teaching only makes sense when the played move brings a
        # piece ONTO the diagonal, not when it leaves it.  Policy suppresses
        # any fire where to_square is not on the long diagonal.
        "dynamic_policy": "open_line_move_uses_diagonal",
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
        # Mohit Day 3 Issue B (2026-05-30): fired 25 times in 200-game
        # audit; generic "force it to choose" without naming WHICH piece
        # or WHICH targets. Authored silence until detector enriches
        # the template with the defender's piece+square and the two
        # targets it's stretched between.
        "description": "",
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
    {
        # Mohit 2026-05-20: classic 1200-level teaching pattern. When
        # opponent's king-pawn shelter is broken (e.g. f7 moved after
        # ...exd4 or ...fxe5), the lifted square is defended only by
        # the king. If we have a piece attacking it, that's a target
        # to pile onto. Generalizes to f-pawn (Scholar's-mate territory),
        # g-pawn (fianchetto squares), and queenside-castle a/b/c-pawns.
        "id": "king_pawn_lifted",
        "name": "King-Pawn Lifted",
        "description": "Their king-pawn has moved. Only the king defends that square. Keep your piece pointed at it.",
        "phase_in_scope": "any",
        "priority": 70,
        "geometry_hint": "opp king's shelter pawn (f/g/h for kingside castled, a/b/c for queenside castled, files adjacent to king for uncastled) is absent from its starting rank; we have at least one attacker on that square; non-king defenders fewer than attackers",
        "verifier_policy": "heuristic_only",
    },
    {
        # Mohit 2026-05-20: the Légal's Mate / Fried Liver family.
        # A piece moves and clears a line for an own slider; from a
        # newly-reachable square the slider can reach a king-zone
        # square that ANOTHER own piece also attacks. Captures the
        # "knight sacrifices to bring the queen out for the mate
        # threat" idea that engine PVs and material-counting detectors
        # both miss. The pattern fires on the CLEARANCE move (the
        # sacrifice or quiet piece-move that opens the line) — not
        # on the eventual attack move.
        "id": "clearance_for_attack",
        "name": "Clearance for Attack",
        "description": "Your moved piece opens the line. Your slider now has a path to the king zone — bring it out to coordinate the threat.",
        "phase_in_scope": "any",
        "priority": 82,
        "geometry_hint": "moved piece (any) cleared a line that own slider (Q/R/B) was on; the slider can now reach a square from which it attacks a king-zone square; AT LEAST one other own piece also attacks that king-zone square (coordination); pattern fires on the clearance move, not the attack move",
        "verifier_policy": "heuristic_only",
    },
]


# Quick-access by id
PATTERNS_BY_ID = {p["id"]: p for p in SHAPE_PATTERNS}


# Invariant checks (run on import; fail loud if catalog drifts)
# 2026-05-16: 23 → 24 with `pawn_fork`.
# 2026-05-20: 24 → 25 with `king_pawn_lifted` (Mohit f7 weakness teaching).
# 2026-05-20: 25 → 26 with `clearance_for_attack` (Mohit Légal's / Fried Liver family).
assert len(SHAPE_PATTERNS) == 26, f"shape catalog must be 26 entries, got {len(SHAPE_PATTERNS)}"
assert len({p["id"] for p in SHAPE_PATTERNS}) == 26, "duplicate pattern ids"
_heuristic_count = sum(1 for p in SHAPE_PATTERNS if p["verifier_policy"] == "heuristic_only")
assert _heuristic_count == 3, f"23 verified + 3 heuristic expected; got {_heuristic_count} heuristic"
