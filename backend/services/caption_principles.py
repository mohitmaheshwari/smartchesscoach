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

  aligned_moves       Specification of what moves WOULD satisfy this
                      principle. Detector turns this into a list of
                      SAN strings at runtime.

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
                      Engine-endorsement phrase rotates across 5 variants
                      so the catalog doesn't read as a template:
                        - "Best move."
                        - "Engine's top choice."
                        - "Strongest move here."
                        - "The engine wants this immediately."
                        - "Engine agrees." (kept, used sparingly)
                      Audit rule S17: no variant used in >6 entries.

  cue_top_n           ≤20-word coach-voice line for when an aligned
                      move is in engine's top-3 PV but not #1.

  cue_absent          ≤20-word coach-voice line for when engine prefers
                      a non-aligned move. Used only by `preferred` /
                      `forbidden` policies. TONE: habit-correction, NOT
                      lecture. Always acknowledge the engine's priority
                      this position, then plant the long-term habit.

  visual_signature    Spec for the mini-board diagram. Frontend renders
                      it from this spec.

  drill_outline       What practice would reinforce this. ≤30 words.

──────────────────────────────────────────────────────────────────────
DRAFT v2 — 28 entries.
──────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

from typing import Any, Dict, List


PRINCIPLES: List[Dict[str, Any]] = [

    # ══════════════════════════════════════════════════════════════════
    # OPENING (9) — moves 1–12. Heaviest teaching ground for 600–1200.
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "OP_FINISH_DEVELOPMENT",
        "name": "Develop all your pieces first",
        "phase_in_scope": ["opening", "middlegame"],
        "priority": 26,
        "match_kind": "played_move",
        "aligned_moves": "any move that develops a piece still on its starting square",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Develop your remaining pieces before attacking.",
        "cue_top_n":  "Attacks with two pieces still on their starting squares fail. Finish development first.",
        # Was "Engine likes the attack here. Most positions, develop fully
        # first — early attacks fail." — Parth fb_c64e76a26a74 2026-05-17
        # flagged engine-meta as vague. Rewriting concrete per
        # [[teaching-not-reading]].
        "cue_absent": "This position rewards attacking, but most positions don't. As a default: develop every piece before attacking.",
        "visual_signature": {
            "highlight": ["undeveloped_piece_squares"],
            "arrows": [("attacker_square", "attacked_square", "amber")],
        },
        "drill_outline": "5 positions tempting an attack with 2+ undeveloped pieces; correct answer develops the last piece.",
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
        "cue_best":   "Pushing pawns near your king before castling opens lines toward it. Develop and castle first.",
        "cue_top_n":  "Pawn moves near your unsafe king create weak squares. Castle first, push later.",
        "cue_absent": "Pushing pawns near your king before castling weakens the squares around it. Castle, then think about pawn breaks.",
        "visual_signature": {
            "highlight": ["king_square", "weakened_pawn_square"],
            "arrows": [],
        },
        "drill_outline": "5 pre-castling positions where the temptation is h3 / g3 / f3; correct answer is development or castling.",
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
        "cue_best":   "Develop knights and bishops first — strongest move here. Your queen will only get chased on that square.",
        "cue_top_n":  "Queens out early get chased. Develop knights and bishops, then castle, then the queen.",
        "cue_absent": "Bringing the queen out early — develop a minor piece (knight or bishop) first. Queens out early get chased and lose tempo.",
        "visual_signature": {
            "highlight": ["queen_square"],
            "arrows": [],
        },
        "drill_outline": "5 opening positions where queen has an apparent good move; correct answer is a minor piece instead.",
    },

    {
        "id": "OP_SAME_PIECE_TWICE",
        "name": "Don't move the same piece twice",
        "phase_in_scope": ["opening"],
        "priority": 31,
        "match_kind": "played_move",
        "aligned_moves": "any move that develops a new piece",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Develop a new piece. Engine agrees — a fresh piece is the better move here.",
        "cue_top_n":  "Develop a new piece each turn. Multiple pieces are still on their starting squares.",
        # Was "Engine sees something tactical. Even so..." — Parth
        # fb_0f57acc84791 2026-05-17 flagged as unclear. Rewriting per
        # [[teaching-not-reading]].
        # v91 (2026-05-25): Parth fb_441026e27b10 — "The 'specific
        # threat' part is not correct. are two principle merged here?"
        # The previous "This move solves a specific threat" was an
        # UNVERIFIED claim — the detector knows the user re-moved a
        # piece, not that the re-move solved a threat. Rewriting to
        # describe what actually happened (a re-move costs tempo)
        # without inventing a chess-reason the detector can't see.
        "cue_absent": "Re-moving the same piece costs tempo. As a default: a fresh piece each turn keeps the opening flowing.",
        "visual_signature": {
            "highlight": ["piece_first_move_square", "this_move_to_square"],
            "arrows": [("piece_first_move_square", "this_move_to_square", "amber")],
        },
        "drill_outline": "5 opening positions where the temptation is to re-move a developed piece; correct answer always develops a new one.",
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
        "cue_best":   "Develop a piece. Best move. Pieces win games, not extra pawn moves.",
        "cue_top_n":  "You've used too much opening time on pawns. Bring out a knight or bishop instead.",
        "cue_absent": "Pawn-heavy openings work in this position. Usually the habit is: develop a piece every move.",
        "visual_signature": {
            "highlight": [],
            "arrows": [],
        },
        "drill_outline": "5 positions after 4–6 moves where the temptation is another pawn move; correct answer develops a minor.",
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
        "cue_best":   "Take the centre with a pawn — central pawns open lines for every piece.",
        "cue_top_n":  "e4 and d4 open lines for your pieces immediately.",
        # Was "Engine sees a tactic this move..." — engine-meta language
        # banned per [[teaching-not-reading]]. 2026-05-17 sweep alongside
        # Parth's flagged cue_absent variants.
        "cue_absent": "Tactics work here. As a default: e4 or d4 first — central pawns open lines for every piece.",
        "visual_signature": {
            "highlight": ["d4", "e4", "d5", "e5"],
            "arrows": [],
        },
        "drill_outline": "5 first-2-moves positions where central pawn is the choice; correct answer is e4 or d4 (or e5 / d5 for black).",
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
        # Reverted to silence 2026-05-13. Previous string was authored
        # by me without sign-off when fixing a forbidden-phrase hit on
        # "controls" — per audit-coverage-tracks-surface rule, removal
        # is allowed, rewriting is authoring. Awaiting user-authored
        # replacement.
        "cue_best":   "",
        "cue_top_n":  "Knights fight best near the centre.",
        "cue_absent": "This rim move works here. But knights fight best near the centre — make that your default.",
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
        "cue_best":   "Don't lock your own bishop in. A different pawn square keeps the diagonal open.",
        "cue_top_n":  "This pawn move blocks your bishop's diagonal. Try a square that keeps it open.",
        "cue_absent": "This pawn move works here. Usually — look at your bishop's diagonal first.",
        "visual_signature": {
            "highlight": ["bishop_square", "blocking_pawn_square"],
            "arrows": [("bishop_square", "blocked_diagonal_far_square", "red")],
        },
        "drill_outline": "5 positions with a choice between two pawn moves; correct one preserves the bishop's diagonal.",
    },

    {
        "id": "OP_NOT_CASTLED",
        "name": "Castle by move 12",
        "phase_in_scope": ["opening", "middlegame"],
        "priority": 36,
        "match_kind": "state_entry",
        "aligned_moves": "O-O or O-O-O when legal",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_state_entry",
        "cue_best":   "Castle now. Best move — O-O is the top engine pick.",
        "cue_top_n":  "Castle when you can. King safety is the priority before any attack.",
        # 2026-05-17 sweep: replacing engine-meta cue_absent variants
        # per [[teaching-not-reading]].
        "cue_absent": "Tactics this move. Either way — castle as soon as you can. King safety saves games.",
        "visual_signature": {
            "highlight": ["king_starting_square", "castled_target_square"],
            "arrows": [("king_starting_square", "castled_target_square", "green")],
        },
        "drill_outline": "5 positions where the king is uncastled past move 12; correct answer is O-O or O-O-O.",
    },

    # ══════════════════════════════════════════════════════════════════
    # TACTICS / PATTERN RECOGNITION (10) — the visual library.
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "TAC_CHECKS_CAPTURES_THREATS",
        "name": "Checks, captures, threats first",
        "phase_in_scope": ["opening", "middlegame", "endgame"],
        "priority": 9,
        "match_kind": "missed_chance",
        "aligned_moves": "any check, capture, or threat-creating move when engine's #1 is forcing",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_move",
        "cue_best":   "Forcing move available — check, capture, or threat.",
        "cue_top_n":  "Scan checks, captures, threats every move. A forcing move is faster than a quiet one.",
        "cue_absent": "Scan forcing moves first: checks, captures, threats — yours and theirs.",
        "visual_signature": {
            "highlight": ["forcing_move_target_square"],
            "arrows": [("forcing_move_from_square", "forcing_move_to_square", "red")],
        },
        "drill_outline": "5 positions where the engine's #1 is a check, capture, or threat the player missed.",
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
        "cue_best":   "Back-rank mate — their king has no escape squares. Play this immediately.",
        "cue_top_n":  "Watch the back rank: pawns blocking + rook or queen on the file = mate.",
        "cue_absent": "Back-rank mate works when the king is blocked by its own pawns with no escape squares.",
        "visual_signature": {
            "highlight": ["enemy_king_square", "back_rank_attacker_square"],
            "arrows": [("back_rank_attacker_square", "back_rank_target", "red")],
        },
        "drill_outline": "5 positions where a back-rank tactic finishes the game; correct answer delivers or threatens it.",
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
        # 2026-05-17 Parth fb_b31dacc286bf: the old cue_best said
        # "Best move: take it" — but TAC_HANGING_PIECE fires on the
        # MOVER hanging their own piece (could be the user OR the
        # opponent). When the user hangs their own piece, "take it"
        # is nonsense. Rewriting neutral; resolver detail surfaces
        # whose-piece-it-is via mover_is_user.
        # Parth 2026-05-18 fb_a30cab50da3d: previous cue ended with
        # "there's a stronger move available" — empty calorie since the
        # cue itself can't name the move (no evidence binding at this
        # layer). Rewritten 2026-05-19 to be observational + actionable
        # without overpromising the missing concrete recommendation.
        "cue_best":   "Watch the loose piece — yours or theirs. Count attackers and defenders before deciding.",
        "cue_top_n":  "Loose piece in the position — confirm it's defended before you commit elsewhere.",
        "cue_absent": "Loose piece in the position — yours or theirs. Address it before launching plans.",
        "visual_signature": {
            "highlight": ["hanging_piece_square"],
            "arrows": [("attacker_square", "hanging_piece_square", "red")],
        },
        "drill_outline": "5 positions with a hanging piece somewhere on the board; correct answer wins it.",
    },

    {
        "id": "TAC_DEFENDER_COUNT",
        "name": "Count attackers and defenders",
        "phase_in_scope": ["opening", "middlegame", "endgame"],
        "priority": 12,
        "match_kind": "played_move",
        "aligned_moves": "any move that does NOT leave a piece with more attackers than defenders",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_move",
        "cue_best":   "Count attackers and defenders before you move. Engine agrees — this drops material.",
        "cue_top_n":  "Two attackers, one defender — the piece falls. Always count before you move.",
        "cue_absent": "Before every move, count attackers and defenders on the target square.",
        "visual_signature": {
            "highlight": ["target_square"],
            "arrows": [("attacker_square", "target_square", "red"),
                       ("defender_square", "target_square", "green")],
        },
        "drill_outline": "5 positions where one move leaves a piece 1-vs-2 attacked; correct answer adds a defender or moves the piece.",
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
        "cue_best":   "One piece, two targets — the fork wins material.",
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
        # 2026-05-17: cues had to neutralize "pin" wording because the
        # detector fires on both pin (front non-king) AND skewer (front
        # is the king under check) — Parth fb_05356cf43f98: "Not pin.
        # King cannot be pinned. Skewer is the correct term."
        "cue_best":   "Two enemy pieces on a line — pin or skewer the front one with a slider.",
        "cue_top_n":  "Two enemy pieces on a line — pin or skewer the front one with a slider.",
        "cue_absent": "When two enemy pieces sit on a line, a bishop / rook / queen can pin or skewer them.",
        "visual_signature": {
            "highlight": ["pinner_square", "front_square", "rear_square"],
            "arrows": [("pinner_square", "rear_square", "red")],
        },
        "drill_outline": "5 positions with a pin available; correct answer installs the pin.",
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
        "cue_best":   "Check the king — the piece behind it falls when the king moves.",
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
        "cue_best":   "Move the front piece — your slider behind it attacks. Play this immediately.",
        "cue_top_n":  "Discovered attack: move a piece out of the line, the piece behind hits.",
        "cue_absent": "Discovered attacks open a slider's line by moving the blocker — two threats in one move.",
        "visual_signature": {
            "highlight": ["mover_square", "slider_square", "discovered_target_square"],
            "arrows": [("slider_square", "discovered_target_square", "red")],
        },
        "drill_outline": "5 positions where a piece can move and uncover an attack; correct answer makes the discovery.",
    },

    {
        "id": "DEF_MOST_ATTACKED",
        "name": "Defend the most-attacked piece",
        "phase_in_scope": ["middlegame", "endgame"],
        "priority": 17,
        "match_kind": "played_move",
        "aligned_moves": "any move that defends or moves away the most-attacked piece",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_move",
        "cue_best":   "Defend the most-attacked piece first — it's the worst threat. Play this immediately.",
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
        "id": "TAC_CHANGED_AFTER_MOVE",
        "name": "What changed after the move?",
        "phase_in_scope": ["opening", "middlegame", "endgame"],
        "priority": 18,
        "match_kind": "played_move",
        "aligned_moves": "any move that does NOT open a line / expose a piece / create a new threat against the mover",
        "gate_policy": "endorsement_required + cp_loss_strict",
        "suppress": "once_per_move",
        # cue_best + cue_absent reverted to silence 2026-05-13. The text
        # I shipped in commit ed1dc69e was authored without user sign-off
        # — user flagged it (fb_399b9c6dc18c, fb_a4748723dd18). cue_top_n
        # remains as it was pre-existing user-approved text.
        "cue_best":   "",
        "cue_top_n":  "Scan after every move — yours or theirs — for new threats and exposed pieces.",
        "cue_absent": "",
        "visual_signature": {
            "highlight": ["newly_exposed_square", "new_attacker_square"],
            "arrows": [("new_attacker_square", "newly_exposed_square", "red")],
        },
        "drill_outline": "5 positions where one move LOOKS reasonable but opens a new tactical problem; correct answer avoids it.",
    },

    # ══════════════════════════════════════════════════════════════════
    # MIDDLEGAME / STRATEGY (7)  — includes defence priorities 44, 47.
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "MID_KING_SAFETY",
        "name": "Loose king pawns — slow down",
        "phase_in_scope": ["middlegame"],
        "priority": 38,
        "match_kind": "state_entry",
        "aligned_moves": "any defensive move that addresses king pawn weakness",
        "gate_policy": "endorsement_preferred",
        "suppress": "once_per_state_entry",
        "cue_best":   "Defend the king first. Best move — the pawn weakness needs attention.",
        "cue_top_n":  "Your king pawns are loose. Defend before you attack.",
        # 2026-05-17 sweep: engine-meta cue_absent rewrite.
        "cue_absent": "Other priorities this move. Either way — loose pawns near your king mean defend before attack.",
        "visual_signature": {
            "highlight": ["king_square", "weak_pawn_squares"],
            "arrows": [],
        },
        "drill_outline": "5 positions with king-side weaknesses; correct answer is a defensive consolidation.",
    },

    {
        "id": "MID_KEEP_ATTACKERS",
        "name": "Trade defenders, keep attackers",
        "phase_in_scope": ["middlegame"],
        "priority": 42,
        "match_kind": "played_move",
        "aligned_moves": "any trade where the captured piece was defending the target, not attacking it",
        "gate_policy": "endorsement_preferred + cp_loss_strict",
        "suppress": "once_per_game",
        "cue_best":   "Trade the defender, not the attacker — keeps your attackers alive.",
        "cue_top_n":  "When you're attacking, trade off their defenders. Your attackers want to stay.",
        "cue_absent": "This trade works here. Usually — when attacking, trade their defenders, not your attackers.",
        "visual_signature": {
            "highlight": ["attacker_square", "defender_square"],
            "arrows": [],
        },
        "drill_outline": "5 mid-attack positions where two trades are possible; correct answer takes the defender.",
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
        "cue_best":   "Put your rook on the open file. Nothing blocks it there.",
        "cue_top_n":  "Open files are for rooks. Move yours there before the opponent does.",
        # 2026-05-17 sweep: engine-meta cue_absent rewrite.
        "cue_absent": "Tactics shift things this move. Most positions — your rook belongs on the open file.",
        "visual_signature": {
            "highlight": ["rook_square", "open_file_target_square"],
            "arrows": [("rook_square", "open_file_target_square", "green")],
        },
        "drill_outline": "5 positions with an open file unclaimed; correct answer puts a rook there.",
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
        # 2026-05-17 sweep: engine-meta cue_absent rewrite.
        "cue_absent": "A different defence works this move. Usually — under attack, trade off their attackers first.",
        "visual_signature": {
            "highlight": ["own_defender_square", "opp_attacker_square"],
            "arrows": [],
        },
        "drill_outline": "5 positions under attack where a trade is available; correct answer takes the attacker.",
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
        "cue_best":   "Reroute the bishop. Best move — your bad bishop is in the way.",
        "cue_top_n":  "Bishop locked behind your own pawns is a bad bishop. Reroute or trade it.",
        # Was "Engine sees something else..." — engine-meta language
        # banned per [[teaching-not-reading]]. 2026-05-17 sweep.
        "cue_absent": "Other priorities this move. Long-term: your bad bishop is locked behind pawns and needs a reroute or trade.",
        "visual_signature": {
            "highlight": ["bad_bishop_square", "own_pawn_squares"],
            "arrows": [],
        },
        "drill_outline": "5 middlegame positions with a bad bishop; correct answer reroutes or trades.",
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
        "cue_best":   "The pawn break opens the line — closed positions need this.",
        "cue_top_n":  "Closed lines stop your attack. The pawn break opens them.",
        "cue_absent": "No break needed this move. When attacks stall, look for the pawn push that opens a line.",
        "visual_signature": {
            "highlight": ["pawn_break_square", "enemy_king_square"],
            "arrows": [("pawn_break_square", "enemy_king_square", "amber")],
        },
        "drill_outline": "5 attacking positions where one pawn break wins; correct answer pushes it.",
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
        # Parth 2026-05-18 fb_7950be24f981: "short steps toward shelter"
        # is hollow — no concrete target square named here. The
        # resolver-detail branch (caption_priority_resolver.py:568) DOES
        # name the engine's king target square; this cue is only used in
        # surfaces that don't run the resolver. Made the cue more
        # observational so it doesn't promise a recommendation it can't
        # deliver at this layer.
        "cue_best":   "Castling rights are gone — walk the king toward pawn cover, one square at a time.",
        "cue_top_n":  "Castling unavailable? Walk the king toward pawn cover. Short steps, no risks.",
        "cue_absent": "Different defence works here. Usually — castling gone, walk the king to safety, one square at a time.",
        "visual_signature": {
            "highlight": ["king_square", "safer_king_square"],
            "arrows": [("king_square", "safer_king_square", "green")],
        },
        "drill_outline": "5 mid-attack positions where castling is unavailable; correct answer is a king walk toward shelter.",
    },

    # ══════════════════════════════════════════════════════════════════
    # ENDGAME (5) — 2 original + 3 added 2026-05-16 (Mohit signoff,
    # see project_endgame_principles_backlog.md). The new three:
    #   END_RULE_OF_SQUARE       — geometric king-catches-pawn check
    #   END_OPPOSITION           — kings facing one square apart in K+P
    #   END_ROOK_BEHIND_PASSER   — Tarrasch rule (single-passer only v1)
    # All three use vocabulary aligned with endgames.json lesson library
    # so coaching → lesson → caption all share the same names.
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "END_PASSED_PAWN",
        "name": "Passed pawns must be pushed",
        "phase_in_scope": ["endgame", "middlegame"],
        "priority": 50,
        "match_kind": "missed_chance",
        "aligned_moves": "the passed pawn pushes one square",
        "gate_policy": "endorsement_required + cp_loss_strict",
        # Phase 0.5 (2026-05-18): state-keyed. Re-arms when the set of
        # passed pawns changes (new pawn becomes passed, or a passed
        # pawn promotes). Avoids the "push your passer" cue repeating
        # uselessly when the same passer sits for many moves.
        "suppress": "once_per_state_key",
        "cue_best":   "Push the passed pawn. Engine agrees — every step is progress.",
        "cue_top_n":  "Passed pawns must be pushed. Every step forces the opponent to stop it.",
        "cue_absent": "A passed pawn has no enemy pawn in front of it. Push it — every square is progress.",
        "visual_signature": {
            "highlight": ["passed_pawn_square", "promotion_square"],
            "arrows": [("passed_pawn_square", "promotion_square", "green")],
        },
        "drill_outline": "5 endgames with a passed pawn; correct answer pushes the pawn (with king support if needed).",
    },

    {
        "id": "END_KING_ACTIVE",
        "name": "King is a fighter in the endgame",
        "phase_in_scope": ["endgame"],
        "priority": 65,
        "match_kind": "state_entry",
        "aligned_moves": "any king move toward the centre",
        "gate_policy": "endorsement_preferred",
        # Phase 0.5 (2026-05-18): one-time-per-game lesson. The "activate
        # the king" cue is a structural reminder; once shown, the player
        # carries it through the rest of the endgame.
        "suppress": "once_per_game",
        "cue_best":   "Activate the king — the centre is where it fights in the endgame.",
        "cue_top_n":  "Endgames need an active king. Walk it toward the centre, one square at a time.",
        # 2026-05-17 sweep: engine-meta cue_absent rewrite.
        "cue_absent": "Other plans this move. Generally — endgames need an active king, walk it to the centre.",
        "visual_signature": {
            "highlight": ["king_square", "centre_square"],
            "arrows": [("king_square", "centre_square", "green")],
        },
        "drill_outline": "5 simple endgames where the king should march to the centre; correct answer takes the first step.",
    },

    # ── ADDED 2026-05-16 (Mohit signoff) ────────────────────────────
    # Three foundational endgame principles for 1200-1500 players.
    # Vocabulary matches data/endgames.json lesson library so the same
    # name appears across coaching surfaces.

    {
        "id": "END_RULE_OF_SQUARE",
        "name": "Rule of the Square",
        "phase_in_scope": ["endgame"],
        "priority": 12,   # high — geometric certainty, often game-deciding
        "match_kind": "missed_chance",
        "aligned_moves": "the king move that lands inside the box from opponent's passed pawn to its promotion square",
        "gate_policy": "endorsement_required + cp_loss_strict",
        # Phase 0.5 (2026-05-18): state-keyed suppression. Re-arms when
        # the (pawn_square, king_should_move_to) pair changes — different
        # pawn or different king target = different lesson.
        "suppress": "once_per_state_key",
        "cue_best":   "Step into the square. Engine agrees — your king catches the pawn from there.",
        "cue_top_n":  "Rule of the Square — count squares from the pawn to promotion; your king must reach that many squares to catch it.",
        "cue_absent": "Their passed pawn promotes if your king's too far. Step inside the box — count squares.",
        "visual_signature": {
            "highlight": ["passed_pawn_square", "promotion_square", "king_square_played", "king_should_move_to"],
            "arrows": [("king_square_played", "king_should_move_to", "green"),
                       ("passed_pawn_square", "promotion_square", "red")],
        },
        "drill_outline": "5 K+P races where the defending king must enter the square; correct answer is the king step into the box.",
    },

    {
        "id": "END_OPPOSITION",
        "name": "The Opposition",
        "phase_in_scope": ["endgame"],
        "priority": 28,   # high in K+P endings; only fires when material is reduced AND the best move is a king move
        "match_kind": "missed_chance",
        "aligned_moves": "the king move that takes direct or distant opposition (engine-confirmed king move only)",
        "gate_policy": "endorsement_required + cp_loss_strict + king_move_required",
        # Phase 0.5 (2026-05-18): state-keyed suppression. Re-arms when
        # the (your_king_should_move_to, their_king_square, opposition_kind)
        # tuple changes — repeated fires with same king pair + same kind
        # (the audit's 10c19d0c case with 4 Kf2/g4/direct fires) dedupe
        # to one visible caption.
        "suppress": "once_per_state_key",
        "cue_best":   "Take the opposition. Engine wants this king move — they must step aside.",
        "cue_top_n":  "The Opposition — kings facing one square apart, opponent to move means you have it. They must give ground.",
        "cue_absent": "Kings face on the same line. The side NOT to move has the opposition — force them aside.",
        "visual_signature": {
            "highlight": ["your_king_square", "their_king_square", "your_king_should_move_to"],
            "arrows": [("your_king_square", "your_king_should_move_to", "green")],
        },
        "drill_outline": "5 K+P positions where seizing the opposition wins; correct answer is the king move that creates direct opposition.",
    },

    {
        "id": "END_ROOK_BEHIND_PASSER",
        "name": "Rook behind the passed pawn",
        "phase_in_scope": ["endgame", "middlegame"],
        "priority": 35,
        "match_kind": "missed_chance",
        "aligned_moves": "the rook move that places your rook directly behind the single passed pawn (yours: supporting from behind; theirs: restraining from behind)",
        "gate_policy": "endorsement_required + cp_loss_strict + single_passer_only",
        # Phase 0.5 / 4 (2026-05-18): state-keyed suppression. Re-arms
        # when the (passer_square, rook_target_square) pair changes —
        # different passer or different rook destination = different
        # Tarrasch moment.
        "suppress": "once_per_state_key",
        "cue_best":   "Rook behind the passed pawn — Tarrasch's rule.",
        "cue_top_n":  "Tarrasch rule: the rook belongs behind the passed pawn. It supports yours, restrains theirs.",
        "cue_absent": "Rook + passed pawn? Behind is the right square — either to push it (yours) or hold it back (theirs).",
        "visual_signature": {
            "highlight": ["passed_pawn_square", "rook_square_played", "rook_target_square"],
            "arrows": [("rook_square_played", "rook_target_square", "green")],
        },
        "drill_outline": "5 R+P endgames where rook-behind-pawn is the only winning idea; correct answer is the rook lift to the square behind the passed pawn.",
    },

    # ══════════════════════════════════════════════════════════════════
    # CROSS-OPENING THEMES (3) — added 2026-05-18 (Mohit signoff).
    # Geometric patterns that appear across many openings (English /
    # Nimzo-Indian / Vienna / Italian / Fried Liver / etc.) and live
    # in no single opening file. They fire on the SHAPE, not on the
    # opening identity. See project_endgame_principles_backlog.md for
    # the pattern this followed.
    #
    # The three:
    #   OP_BISHOP_TRADE_DOUBLES_PAWN — Bxc3 / bxc3 doubled-pawn trade
    #   OP_F2_F7_STRIKE              — early capture on the weak king square
    #   OP_TRAPPED_KNIGHT            — knight with no safe destination
    # ══════════════════════════════════════════════════════════════════

    {
        "id": "OP_BISHOP_TRADE_DOUBLES_PAWN",
        "name": "Bishop trade doubles their pawns",
        "phase_in_scope": ["opening", "middlegame"],
        "priority": 37,
        "match_kind": "played_move",
        "aligned_moves": "the bishop capture of an enemy minor piece whose forced recapture is a pawn that doubles an enemy pawn file",
        "gate_policy": "endorsement_preferred",
        # State-keyed: re-arms if a DIFFERENT bishop trade doubles a
        # different file (rare — usually once per game per file).
        "suppress": "once_per_state_key",
        "cue_best":   "Trade bishop for knight — they recapture with a pawn, doubling that file.",
        "cue_top_n":  "Bishop takes their knight — they recapture with a pawn, doubling that file. A factor in your favour, not always decisive.",
        "cue_absent": "BxN forced a pawn recapture that doubled their pawns — depending on the position, that's a small structural concession.",
        "visual_signature": {
            "highlight": ["capture_square", "doubled_pawn_file_squares"],
            "arrows": [("bishop_from_square", "capture_square", "green")],
        },
        "drill_outline": "5 positions (English / Nimzo / Vienna setups) where Bxc3 / Bxf6 forces a doubled-pawn recapture; correct answer is the trade.",
    },

    {
        "id": "OP_F2_F7_STRIKE",
        "name": "Strike on f7 / f2",
        "phase_in_scope": ["opening", "middlegame"],
        "priority": 8,   # high — material claim on the king's weak square
        "match_kind": "played_move",
        "aligned_moves": "the capture on f7 (white attacker) or f2 (black attacker) defended only by the king",
        "gate_policy": "endorsement_required",
        # State-keyed: re-arms if the strike square changes (shouldn't
        # happen — once per game), but state_key gives consistency.
        "suppress": "once_per_state_key",
        "cue_best":   "Capture on f7 — defended only by the king.",
        "cue_top_n":  "f7 (or f2) is defended only by the king in the opening. Take it when you can win material.",
        "cue_absent": "f7 (and f2) is the weakest square at the start — only the king defends it. Watch for tactical strikes there.",
        "visual_signature": {
            "highlight": ["strike_square", "enemy_king_square"],
            "arrows": [("attacker_from_square", "strike_square", "red")],
        },
        "drill_outline": "5 opening positions where Bxf7+ / Nxf7 / Qxf7 wins material; correct answer captures on the weak square.",
    },

    {
        "id": "OP_TRAPPED_KNIGHT",
        "name": "Knight has no safe square",
        "phase_in_scope": ["opening", "middlegame"],
        "priority": 11,  # piece-loss claim — high priority near hanging-piece tier
        "match_kind": "state_entry",
        "aligned_moves": "any move that gives the knight a safe escape, or trades / defends it",
        "gate_policy": "endorsement_preferred",
        # State-keyed on the trapped knight's square — re-arms if a
        # DIFFERENT knight gets trapped later in the game (rare but
        # possible: two knights in the same game).
        "suppress": "once_per_state_key",
        "cue_best":   "Your knight on the trap square has no safe move. Engine wants the rescue immediately.",
        "cue_top_n":  "A knight with zero safe squares loses next move. Get it out now or trade it.",
        "cue_absent": "When every square a knight can reach is attacked with no defender, it's trapped — rescue it before they win it.",
        "visual_signature": {
            "highlight": ["trapped_knight_square"],
            "arrows": [],
        },
        "drill_outline": "5 positions where a knight has been forced to the rim and lost mobility; correct answer is the only safe retreat or a trade.",
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
