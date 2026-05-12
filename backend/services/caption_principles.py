"""
Caption Principles — the named-rule catalog for the teaching layer.

This is the COACH'S MOUTH. Every player-facing principle ChessGuru ever
teaches lives in this file. The catalog is hand-authored, reviewed
word-for-word, and treated as the contract between Mohit (product) and
the renderer. Detector code lives in `caption_facts.py` and reads this
catalog at runtime; render code in `caption_rules.py` reads the cue
strings; the audit script reads the IDs.

Locked architectural decisions (see memory):
  - feedback_sub1500_memory_anchors.md
        Player memory <1500 is principle-anchored, geometry-anchored,
        process-anchored — NEVER game-anchored. Cue text never references
        opponents, dates, or "you did this N times in M games."
  - feedback_renderer_never_computes_chess_meaning.md
        Detectors live in caption_facts.py. This file is pure data.
  - feedback_design_clean_code_leaky.md
        TEXT catalog ships before any detector code; each detector
        ships individually with a corpus audit.
  - feedback_1200_test.md
        Every cue ≤20 words; concrete pieces/squares/consequences;
        no jargon (outpost, fianchetto, minority attack, luft).

──────────────────────────────────────────────────────────────────────
Schema (per entry):
──────────────────────────────────────────────────────────────────────

  id                  Stable identifier. ALL_CAPS_SNAKE. Never changes
                      once shipped (referenced by memory + audit).

  name                Sticky ≤6-word memory hook. The label the player
                      walks away with.

  phase_in_scope      List of phases this principle is relevant in:
                      "opening" | "middlegame" | "endgame"
                      Outside scope → principle never fires.

  priority            Integer; lower wins when multiple match the same
                      move. Tactics (immediate material) beat strategy
                      (long-term habit). Reserve 1–20 for tactics,
                      21–40 for opening discipline, 41–60 strategy,
                      61–80 endgame, 81–99 fallback.

  match_kind          One of:
                      "played_move"      — fires on the move that did it
                      "state_entry"      — fires the first move state holds
                      "missed_chance"    — fires when opportunity wasn't taken
                      "counterfactual"   — fires when engine's best was the
                                           principle-aligned move
                      Detector author reads this and writes the right
                      kind of match_fn in caption_facts.py.

  aligned_moves       Specification of what moves WOULD satisfy this
                      principle. Detector turns this into a list of
                      SAN strings at runtime. Examples:
                        "O-O or O-O-O"
                        "any minor piece development"
                        "any central pawn push to {d4, e4} (white) or
                         {d5, e5} (black)"
                        "any move that defends the most-attacked piece"

  gate_policy         "endorsement_required"  — fire only if engine's
                                                best/top-3 includes an
                                                aligned move
                      "endorsement_preferred" — always fire if state
                                                matches; cue varies
                                                by endorsement strength
                      "endorsement_forbidden" — fire only when engine
                                                disagrees (rare)
                      "cp_loss_strict"        — also require cp_loss
                                                ≥30 (suboptimal move)
                      Stack multiple with " + ".

  suppress            "once_per_move"          — default; can't fire twice
                                                 on the same move record
                      "once_per_state_entry"   — fires the first move the
                                                 state holds, then never
                                                 again unless state resets
                      "once_per_game"          — at most one firing per
                                                 game across all moves

  cue_best            ≤20-word coach-voice line for when the engine's
                      #1 move IS an aligned move. Strongest claim.

  cue_top_n           ≤20-word coach-voice line for when an aligned
                      move is in engine's top-3 PV but not #1.

  cue_absent          ≤20-word coach-voice line for when engine prefers
                      a non-aligned move. Used only by `preferred` /
                      `forbidden` policies. Reads as "long-term principle,
                      this position has other priorities."

  visual_signature    Spec for the mini-board diagram. Frontend renders
                      it from this spec. Examples:
                        {"highlight": ["king_square"],
                         "arrows": [("king_square", "castled_square",
                                     "green")]}
                        {"highlight": ["hanging_piece_square"],
                         "arrows": [("attacker_square",
                                     "hanging_piece_square", "red")]}
                      Same shape every time → geometric memory forms.

  drill_outline       What practice would reinforce this. ≤30 words.
                      Used by the drill-generation system to find /
                      surface puzzles tagged with this principle_id.

──────────────────────────────────────────────────────────────────────
DRAFT v1 — 25 entries. Read top to bottom; edit any field freely.
──────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from typing import Any, Dict, List


PRINCIPLES: List[Dict[str, Any]] = [

    # ══════════════════════════════════════════════════════════════════
    # OPENING (8) — moves 1–12. Heaviest teaching ground for 600–1200.
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "OP_SAME_PIECE_TWICE",
        "name": "Don't move the same piece twice",
        "phase_in_scope": ["opening"],
        "priority": 31,
        "match_kind": "played_move",
        "aligned_moves": "any move that develops a new piece",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Develop a new piece. Engine agrees — a fresh piece is the better move.",
        "cue_top_n":  "Develop a new piece each turn. Multiple pieces are still on their starting squares.",
        "cue_absent": "Don't move the same piece twice in the opening — develop a new piece each turn.",
        "visual_signature": {
            "highlight": ["piece_first_move_square", "this_move_to_square"],
            "arrows": [("piece_first_move_square", "this_move_to_square", "amber")],
        },
        "drill_outline": "5 opening positions where the temptation is to re-move a developed piece; correct answer always develops a new one.",
    },

    {
        "id": "OP_QUEEN_OUT_EARLY",
        "name": "Queen out early gets chased",
        "phase_in_scope": ["opening"],
        "priority": 30,
        "match_kind": "played_move",
        "aligned_moves": "any non-queen developing move (knight or bishop)",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Develop knights and bishops first. Engine agrees — your queen will be chased here.",
        "cue_top_n":  "Queens out early get chased. Develop knights and bishops, then castle, then bring the queen.",
        "cue_absent": "Queens out early get chased. Even when the engine likes it, build the habit: minors first.",
        "visual_signature": {
            "highlight": ["queen_square"],
            "arrows": [],
        },
        "drill_outline": "5 opening positions where queen has an apparent good move; correct answer is a minor piece instead.",
    },

    {
        "id": "OP_PAWN_HEAVY",
        "name": "Stop pushing pawns, develop a piece",
        "phase_in_scope": ["opening"],
        "priority": 32,
        "match_kind": "played_move",
        "aligned_moves": "any minor-piece development from its starting square",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Develop a piece. Engine agrees — pieces win games, not extra pawn moves.",
        "cue_top_n":  "You've used too much opening time on pawns. Bring out a knight or bishop instead.",
        "cue_absent": "Limit pawn moves in the opening. Each move should develop a piece toward the center.",
        "visual_signature": {
            "highlight": [],  # filled at runtime with all undeveloped minor-piece squares
            "arrows": [],
        },
        "drill_outline": "5 positions after 4–6 moves where the temptation is another pawn move; correct answer develops a minor.",
    },

    {
        "id": "OP_NOT_CASTLED",
        "name": "Castle by move 12",
        "phase_in_scope": ["opening", "middlegame"],
        "priority": 28,
        "match_kind": "state_entry",
        "aligned_moves": "O-O or O-O-O when legal",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_state_entry",
        "cue_best":   "Castle now — engine agrees, O-O is the top move.",
        "cue_top_n":  "Castle when you can. King safety is the priority before any attack.",
        "cue_absent": "By move 12, your king should be safe. Castle as soon as it becomes available.",
        "visual_signature": {
            "highlight": ["king_starting_square", "castled_target_square"],
            "arrows": [("king_starting_square", "castled_target_square", "green")],
        },
        "drill_outline": "5 positions where the king is uncastled past move 12; correct answer is O-O or O-O-O.",
    },

    {
        "id": "OP_KNIGHT_ON_RIM",
        "name": "Knight on the rim is dim",
        "phase_in_scope": ["opening"],
        "priority": 34,
        "match_kind": "played_move",
        "aligned_moves": "any knight move to a non-rim square (b/g/c/f files for development)",
        "gate_policy": "cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Centralise the knight. Engine agrees — a central knight controls more squares.",
        "cue_top_n":  "Knights on the edge cover fewer squares. Try a central square instead.",
        "cue_absent": "Knights on the a or h file see fewer squares. Develop them toward the centre.",
        "visual_signature": {
            "highlight": ["knight_target_square"],
            "arrows": [],
        },
        "drill_outline": "5 opening positions where a knight has a rim move and a central move; correct answer is always central.",
    },

    {
        "id": "OP_BISHOP_BLOCKED",
        "name": "Your pawn locks your bishop",
        "phase_in_scope": ["opening", "middlegame"],
        "priority": 35,
        "match_kind": "played_move",
        "aligned_moves": "any pawn move that does NOT block an own bishop's diagonal",
        "gate_policy": "cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Don't lock your own bishop in. Engine agrees — there's a better square.",
        "cue_top_n":  "This pawn move blocks your bishop's diagonal. Try a square that keeps it open.",
        "cue_absent": "Pawns can lock your own bishop in. Look at your bishop's diagonal before pushing pawns near it.",
        "visual_signature": {
            "highlight": ["bishop_square", "blocking_pawn_square"],
            "arrows": [("bishop_square", "blocked_diagonal_far_square", "red")],
        },
        "drill_outline": "5 positions with a choice between two pawn moves; correct one preserves the bishop's diagonal.",
    },

    {
        "id": "OP_CLAIM_CENTER",
        "name": "Claim the centre first",
        "phase_in_scope": ["opening"],
        "priority": 33,
        "match_kind": "counterfactual",
        "aligned_moves": "e4, e5, d4, d5 (whichever is legal and uncontested)",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_game",
        "cue_best":   "Take the centre. Engine agrees — a central pawn is the best move here.",
        "cue_top_n":  "Central pawns control the diagonals for both bishops. Take the centre when you can.",
        "cue_absent": "Claim the centre with a pawn early. Even when the engine differs, e4 / d4 builds the habit.",
        "visual_signature": {
            "highlight": ["d4", "e4", "d5", "e5"],
            "arrows": [],
        },
        "drill_outline": "5 first-2-moves positions where central pawn is the choice; correct answer is e4 or d4 (or e5 / d5 for black).",
    },

    {
        "id": "OP_LOOSE_KING_PAWNS",
        "name": "Don't loosen pawns near your king",
        "phase_in_scope": ["opening"],
        "priority": 27,
        "match_kind": "played_move",
        "aligned_moves": "any move that does NOT push h-pawn, g-pawn, or f-pawn before castling",
        "gate_policy": "cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Don't push pawns in front of your king before castling. Engine agrees — develop instead.",
        "cue_top_n":  "Pawn moves near your unsafe king create weak squares. Castle first, push later.",
        "cue_absent": "Pawns near your king-to-be square create permanent weaknesses. Develop and castle first.",
        "visual_signature": {
            "highlight": ["king_square", "weakened_pawn_square"],
            "arrows": [],
        },
        "drill_outline": "5 pre-castling positions where the temptation is h3 / g3 / f3; correct answer is development or castling.",
    },

    # ══════════════════════════════════════════════════════════════════
    # TACTICS / PATTERN RECOGNITION (7) — the visual library.
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "TAC_DEFENDER_COUNT",
        "name": "Count attackers and defenders",
        "phase_in_scope": ["opening", "middlegame", "endgame"],
        "priority": 12,
        "match_kind": "played_move",
        "aligned_moves": "any move that does NOT leave a piece with more attackers than defenders",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_move",
        "cue_best":   "Count attackers and defenders on every square before you move. Engine agrees — this drops material.",
        "cue_top_n":  "Two attackers, one defender — the piece falls. Always count before you move.",
        "cue_absent": "Before every move, count attackers and defenders on the target square. 1-vs-2 means the piece falls.",
        "visual_signature": {
            "highlight": ["target_square"],
            "arrows": [("attacker_square", "target_square", "red"),
                       ("defender_square", "target_square", "green")],
        },
        "drill_outline": "5 positions where one move leaves a piece 1-vs-2 attacked; correct answer adds a defender or moves the piece.",
    },

    {
        "id": "TAC_HANGING_PIECE",
        "name": "Loose piece on the board",
        "phase_in_scope": ["opening", "middlegame", "endgame"],
        "priority": 11,
        "match_kind": "played_move",
        "aligned_moves": "any move that defends or captures the hanging piece",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_move",
        "cue_best":   "A piece is hanging with no defender. Engine agrees — the free capture is on.",
        "cue_top_n":  "Loose piece with no defender — yours or theirs. Scan every move.",
        "cue_absent": "Scan for pieces with no defender — yours and theirs — before every move.",
        "visual_signature": {
            "highlight": ["hanging_piece_square"],
            "arrows": [("attacker_square", "hanging_piece_square", "red")],
        },
        "drill_outline": "5 positions with a hanging piece somewhere on the board; correct answer wins it.",
    },

    {
        "id": "TAC_FORK_PATTERN",
        "name": "One piece, two targets",
        "phase_in_scope": ["opening", "middlegame", "endgame"],
        "priority": 13,
        "match_kind": "missed_chance",
        "aligned_moves": "any move that attacks two enemy pieces simultaneously",
        "gate_policy": "endorsement_required",
        "suppress": "once_per_move",
        "cue_best":   "One piece, two targets — the fork wins material. Engine sees it as #1.",
        "cue_top_n":  "Look for forks every move. One piece attacking two — opponent saves only one.",
        "cue_absent": "Forks are a one-move pattern: one piece, two targets, opponent saves one.",
        "visual_signature": {
            "highlight": ["forker_square", "target_1_square", "target_2_square"],
            "arrows": [("forker_square", "target_1_square", "red"),
                       ("forker_square", "target_2_square", "red")],
        },
        "drill_outline": "5 positions with a knight or bishop fork available; correct answer plants the forker.",
    },

    {
        "id": "TAC_PIN_PATTERN",
        "name": "Two pieces on one line",
        "phase_in_scope": ["opening", "middlegame", "endgame"],
        "priority": 14,
        "match_kind": "missed_chance",
        "aligned_moves": "any move that pins an enemy piece against a more valuable one",
        "gate_policy": "endorsement_required",
        "suppress": "once_per_move",
        "cue_best":   "Pin the front piece — it can't move without losing the rear piece. Engine's #1.",
        "cue_top_n":  "Two enemy pieces on a line — pin the front one with a slider.",
        "cue_absent": "When two enemy pieces sit on a line, a bishop / rook / queen can pin them.",
        "visual_signature": {
            "highlight": ["pinner_square", "front_square", "rear_square"],
            "arrows": [("pinner_square", "rear_square", "red")],
        },
        "drill_outline": "5 positions with a pin available; correct answer installs the pin.",
    },

    {
        "id": "TAC_BACK_RANK",
        "name": "King with no escape",
        "phase_in_scope": ["middlegame", "endgame"],
        "priority": 10,
        "match_kind": "missed_chance",
        "aligned_moves": "any move that delivers or threatens back-rank mate",
        "gate_policy": "endorsement_required",
        "suppress": "once_per_move",
        "cue_best":   "Back-rank mate — their king has no escape squares. Engine's #1.",
        "cue_top_n":  "Watch the back rank: pawns blocking + rook or queen on the file = mate.",
        "cue_absent": "Back-rank mate works when the king is blocked by its own pawns with no escape squares.",
        "visual_signature": {
            "highlight": ["enemy_king_square", "back_rank_attacker_square"],
            "arrows": [("back_rank_attacker_square", "back_rank_target", "red")],
        },
        "drill_outline": "5 positions where a back-rank tactic finishes the game; correct answer delivers or threatens it.",
    },

    {
        "id": "TAC_SKEWER_PATTERN",
        "name": "King forced to move, piece behind",
        "phase_in_scope": ["middlegame", "endgame"],
        "priority": 15,
        "match_kind": "missed_chance",
        "aligned_moves": "any move that gives check with a valuable piece behind the king on the same line",
        "gate_policy": "endorsement_required",
        "suppress": "once_per_move",
        "cue_best":   "Check the king — the piece behind it falls when the king moves. Engine's #1.",
        "cue_top_n":  "Look for skewers: check with a slider, valuable piece directly behind the king.",
        "cue_absent": "A skewer wins material: check the king, and the piece behind it on the same line is undefended.",
        "visual_signature": {
            "highlight": ["king_square", "behind_piece_square"],
            "arrows": [("attacker_square", "behind_piece_square", "red")],
        },
        "drill_outline": "5 positions where a check-and-grab skewer works; correct answer delivers the check.",
    },

    {
        "id": "TAC_DISCOVERED_PATTERN",
        "name": "Move one piece, attack with another",
        "phase_in_scope": ["middlegame", "endgame"],
        "priority": 16,
        "match_kind": "missed_chance",
        "aligned_moves": "any move that opens a slider's line onto an enemy piece",
        "gate_policy": "endorsement_required",
        "suppress": "once_per_move",
        "cue_best":   "Move the front piece — your slider behind it attacks. Engine's #1.",
        "cue_top_n":  "Discovered attack: move a piece out of the line, the piece behind hits.",
        "cue_absent": "Discovered attacks open a slider's line by moving the blocker — two threats in one move.",
        "visual_signature": {
            "highlight": ["mover_square", "slider_square", "discovered_target_square"],
            "arrows": [("slider_square", "discovered_target_square", "red")],
        },
        "drill_outline": "5 positions where a piece can move and uncover an attack; correct answer makes the discovery.",
    },

    # ══════════════════════════════════════════════════════════════════
    # MIDDLEGAME / STRATEGY (5)
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "MID_KEEP_ATTACKERS",
        "name": "Trade defenders, keep attackers",
        "phase_in_scope": ["middlegame"],
        "priority": 42,
        "match_kind": "played_move",
        "aligned_moves": "any trade where the captured piece was defending the target, not attacking it",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Trade the defender, not the attacker. Engine agrees — keep your attackers on the board.",
        "cue_top_n":  "When you're attacking, trade off their defenders. Your attackers want to stay.",
        "cue_absent": "Attacking? Trade off the pieces defending the target — keep your attacking pieces alive.",
        "visual_signature": {
            "highlight": ["attacker_square", "defender_square"],
            "arrows": [],
        },
        "drill_outline": "5 mid-attack positions where two trades are possible; correct answer takes the defender.",
    },

    {
        "id": "MID_BAD_BISHOP",
        "name": "Bad bishop, reroute or trade",
        "phase_in_scope": ["middlegame"],
        "priority": 45,
        "match_kind": "state_entry",
        "aligned_moves": "any move that reroutes the bad bishop OR trades it",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_game",
        "cue_best":   "Reroute the bishop. Engine agrees — your bad bishop is in your way.",
        "cue_top_n":  "Bishop locked behind your own pawns is a bad bishop. Reroute or trade it.",
        "cue_absent": "A bishop trapped behind its own pawns is a bad bishop. Plan a reroute or trade it off.",
        "visual_signature": {
            "highlight": ["bad_bishop_square", "own_pawn_squares"],
            "arrows": [],
        },
        "drill_outline": "5 middlegame positions with a bad bishop; correct answer reroutes or trades.",
    },

    {
        "id": "MID_ROOK_OPEN_FILE",
        "name": "Rook on the open file",
        "phase_in_scope": ["middlegame", "endgame"],
        "priority": 43,
        "match_kind": "missed_chance",
        "aligned_moves": "any rook move to an open or half-open file",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Put your rook on the open file. Engine agrees — it dominates.",
        "cue_top_n":  "Open files are for rooks. Move yours there before the opponent does.",
        "cue_absent": "Rooks belong on open and half-open files. Look for the file first.",
        "visual_signature": {
            "highlight": ["rook_square", "open_file_target_square"],
            "arrows": [("rook_square", "open_file_target_square", "green")],
        },
        "drill_outline": "5 positions with an open file unclaimed; correct answer puts a rook there.",
    },

    {
        "id": "MID_PAWN_BREAK",
        "name": "Pawn break opens the attack",
        "phase_in_scope": ["middlegame"],
        "priority": 46,
        "match_kind": "counterfactual",
        "aligned_moves": "any pawn break that opens a line toward the enemy king",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_game",
        "cue_best":   "The pawn break opens the line. Engine agrees — push to attack.",
        "cue_top_n":  "Attacks need open lines. The right pawn push opens the file toward their king.",
        "cue_absent": "Attacks stall without pawn breaks. Find the pawn push that opens a line toward the enemy king.",
        "visual_signature": {
            "highlight": ["pawn_break_square", "enemy_king_square"],
            "arrows": [("pawn_break_square", "enemy_king_square", "amber")],
        },
        "drill_outline": "5 attacking positions where one pawn break wins; correct answer pushes it.",
    },

    {
        "id": "MID_KING_SAFETY",
        "name": "Loose king pawns — slow down",
        "phase_in_scope": ["middlegame"],
        "priority": 41,
        "match_kind": "state_entry",
        "aligned_moves": "any defensive move that addresses king pawn weakness",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_state_entry",
        "cue_best":   "Defend the king first. Engine agrees — the pawn weakness needs attention.",
        "cue_top_n":  "Your king pawns are loose. Defend before you attack.",
        "cue_absent": "Loose pawns near your king need defending. Pause the attack, secure the king first.",
        "visual_signature": {
            "highlight": ["king_square", "weak_pawn_squares"],
            "arrows": [],
        },
        "drill_outline": "5 positions with king-side weaknesses; correct answer is a defensive consolidation.",
    },

    # ══════════════════════════════════════════════════════════════════
    # DEFENCE (3)
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "DEF_MOST_ATTACKED",
        "name": "Defend the most-attacked piece",
        "phase_in_scope": ["middlegame", "endgame"],
        "priority": 17,
        "match_kind": "played_move",
        "aligned_moves": "any move that defends or moves away the most-attacked piece",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_move",
        "cue_best":   "Defend the most-attacked piece first. Engine agrees — that's the immediate threat.",
        "cue_top_n":  "Multiple pieces attacked — handle the highest-value or worst-defended one first.",
        "cue_absent": "When several pieces are under attack, defend the most-attacked one first.",
        "visual_signature": {
            "highlight": ["most_attacked_piece_square"],
            "arrows": [("attacker_1", "most_attacked_piece_square", "red"),
                       ("attacker_2", "most_attacked_piece_square", "red")],
        },
        "drill_outline": "5 positions with two threatened pieces; correct answer addresses the more attacked one.",
    },

    {
        "id": "DEF_TRADE_ATTACKERS",
        "name": "Defending? Trade their attackers",
        "phase_in_scope": ["middlegame"],
        "priority": 44,
        "match_kind": "played_move",
        "aligned_moves": "any trade that removes an enemy attacking piece",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Trade their attacker. Engine agrees — fewer attackers means less danger.",
        "cue_top_n":  "Under attack? Each trade of an attacker reduces the pressure.",
        "cue_absent": "When defending, trade off the opponent's attacking pieces. Each trade calms the storm.",
        "visual_signature": {
            "highlight": ["own_defender_square", "opp_attacker_square"],
            "arrows": [],
        },
        "drill_outline": "5 positions under attack where a trade is available; correct answer takes the attacker.",
    },

    {
        "id": "DEF_WALK_KING",
        "name": "Walk the king to safety",
        "phase_in_scope": ["middlegame", "endgame"],
        "priority": 47,
        "match_kind": "missed_chance",
        "aligned_moves": "any king move that increases distance from attackers and moves toward safer pawn cover",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Walk the king to safety. Engine agrees — short steps toward shelter.",
        "cue_top_n":  "Castling unavailable? Walk the king toward pawn cover. Short steps, no risks.",
        "cue_absent": "When castling is gone, you can still walk the king to safety — one square at a time.",
        "visual_signature": {
            "highlight": ["king_square", "safer_king_square"],
            "arrows": [("king_square", "safer_king_square", "green")],
        },
        "drill_outline": "5 mid-attack positions where castling is unavailable; correct answer is a king walk toward shelter.",
    },

    # ══════════════════════════════════════════════════════════════════
    # ENDGAME (2) — fewer because 600–1400 games rarely reach pure endgames.
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "END_KING_ACTIVE",
        "name": "King is a fighter in the endgame",
        "phase_in_scope": ["endgame"],
        "priority": 65,
        "match_kind": "state_entry",
        "aligned_moves": "any king move toward the centre",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_state_entry",
        "cue_best":   "Activate the king. Engine agrees — centre is where it fights.",
        "cue_top_n":  "Endgames need an active king. Walk it toward the centre, one square at a time.",
        "cue_absent": "In endgames, the king is a strong piece. Centralise it — it fights alongside the rest.",
        "visual_signature": {
            "highlight": ["king_square", "centre_square"],
            "arrows": [("king_square", "centre_square", "green")],
        },
        "drill_outline": "5 simple endgames where the king should march to the centre; correct answer takes the first step.",
    },

    {
        "id": "END_PASSED_PAWN",
        "name": "Passed pawns must be pushed",
        "phase_in_scope": ["endgame", "middlegame"],
        "priority": 50,
        "match_kind": "missed_chance",
        "aligned_moves": "the passed pawn pushes one square",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Push the passed pawn. Engine agrees — every square closer to promotion counts.",
        "cue_top_n":  "Passed pawns must be pushed. Each step toward promotion narrows the opponent's options.",
        "cue_absent": "A passed pawn has no enemy pawn in front of it. Push it — every square is progress.",
        "visual_signature": {
            "highlight": ["passed_pawn_square", "promotion_square"],
            "arrows": [("passed_pawn_square", "promotion_square", "green")],
        },
        "drill_outline": "5 endgames with a passed pawn; correct answer pushes the pawn (with king support if needed).",
    },

]


# Looked up by id; the audit and the renderer reach for it through this.
PRINCIPLES_BY_ID: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PRINCIPLES}


def get_principle(principle_id: str) -> Dict[str, Any]:
    """Return the principle entry for an id, or KeyError if unknown."""
    return PRINCIPLES_BY_ID[principle_id]


def all_principle_ids() -> List[str]:
    """All defined principle ids in catalog order."""
    return [p["id"] for p in PRINCIPLES]
