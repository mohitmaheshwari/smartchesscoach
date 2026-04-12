"""
Fundamentals Evaluator — Stateless, Pure, Derived
===================================================

Evaluates player's chess fundamentals from move history + current position.
No stored state. No increments. Always recomputed fresh.

Same input → same output. Always.

Usage:
    result = evaluate_fundamentals(board, move_history, user_color)
    # {"phase": "OPENING", "fundamentals": [...]}
"""

import chess
from typing import Dict, List, Tuple, Optional


# ─── STATUS CONSTANTS ─────────────────────────────────────────────

NOT_STARTED = "NOT_STARTED"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
FAILED = "FAILED"


# ─── MAIN ENTRY ───────────────────────────────────────────────────

def evaluate_fundamentals(
    board: chess.Board,
    move_history: List[Dict],
    user_color: str,
    eval_data: Dict = None,
) -> Dict:
    """
    Evaluate all fundamentals from current position + history.
    Stateless. Pure function. No side effects.

    Args:
        board: current chess.Board
        move_history: list of {move, by, eval_before, eval_after, ...}
        user_color: "white" or "black"
        eval_data: optional {cp_loss, move_quality, best_move} for current move

    Returns:
        {"phase": "OPENING", "fundamentals": [...]}
    """
    color = chess.WHITE if user_color == "white" else chess.BLACK
    opponent = not color
    move_number = board.fullmove_number
    user_moves = [m for m in move_history if m.get("by") == "player"]
    eval_data = eval_data or {}

    # Phase detection
    phase = _detect_phase(board, color, move_number)

    fundamentals = []

    # ─── OPENING FUNDAMENTALS (always shown, evaluated from history) ───
    fundamentals.append(_eval_piece_development(board, color))
    fundamentals.append(_eval_king_safety_from_history(board, color, move_number, user_moves))
    fundamentals.append(_eval_center_control(board, color, opponent))
    if phase == "OPENING":
        fundamentals.append(_eval_piece_coordination(board, color))
        fundamentals.append(_eval_early_queen(board, color, user_moves, move_number))
        fundamentals.append(_eval_development_efficiency(user_moves, board, color))
    fundamentals.append(_eval_pawn_discipline(board, color))

    # ─── TACTICAL FUNDAMENTALS (always active) ────────────────
    fundamentals.append(_eval_threat_awareness(user_moves, board, color, opponent))
    fundamentals.append(_eval_piece_safety(board, color, opponent))
    fundamentals.append(_eval_calculation_depth(user_moves, eval_data))
    fundamentals.append(_eval_tactical_awareness(board, color, opponent))

    # ─── POSITIONAL FUNDAMENTALS (middlegame+) ────────────────
    if phase in ("MIDDLEGAME", "ENDGAME"):
        fundamentals.append(_eval_playing_with_plan(user_moves, eval_data))
        fundamentals.append(_eval_piece_activity(board, color))
        fundamentals.append(_eval_rook_usage(board, color))
        fundamentals.append(_eval_pawn_structure_awareness(board, color))

    # ─── ENDGAME FUNDAMENTALS ─────────────────────────────────
    if phase == "ENDGAME":
        fundamentals.append(_eval_king_activation(board, color))
        fundamentals.append(_eval_pawn_promotion_awareness(board, color, opponent))

    return {"phase": phase, "fundamentals": fundamentals}


# ─── PHASE DETECTION ──────────────────────────────────────────────

def _detect_phase(board: chess.Board, color: chess.Color, move_number: int) -> str:
    # Count material
    total_pieces = 0
    has_queens = False
    undeveloped_minors = 0
    back_rank = 0 if color == chess.WHITE else 7

    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type not in (chess.PAWN, chess.KING):
            total_pieces += 1
            if p.piece_type == chess.QUEEN:
                has_queens = True
        if p and p.color == color and p.piece_type in (chess.KNIGHT, chess.BISHOP):
            if chess.square_rank(sq) == back_rank:
                undeveloped_minors += 1

    if total_pieces <= 6:
        return "ENDGAME"
    if move_number <= 12 or undeveloped_minors >= 2:
        return "OPENING"
    return "MIDDLEGAME"


# ─── OPENING EVALUATORS ──────────────────────────────────────────

def _eval_piece_development(board: chess.Board, color: chess.Color) -> Dict:
    back_rank = 0 if color == chess.WHITE else 7
    total = 0
    developed = 0
    well_placed = 0
    badly_placed = []

    # Good squares: central or controlling center. Bad: rim, blocking own pawns.
    # Knights: center (c3,f3,d2,e2,c6,f6,d7,e7) = good. Rim (a/h file) = bad.
    # Bishops: long diagonals, not blocking own pawns = good.
    pawn_start_rank = 1 if color == chess.WHITE else 6

    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != color or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
            continue
        total += 1
        if chess.square_rank(sq) == back_rank:
            continue  # Still on back rank — not developed
        developed += 1

        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        sq_name = chess.square_name(sq)

        is_bad = False
        reason = ""

        if p.piece_type == chess.KNIGHT:
            # Knight on a/h file (rim) is almost always bad in the opening
            if file_idx in (0, 7):
                is_bad = True
                reason = f"Knight on {sq_name} — knights belong in the center, not the edge"

        if p.piece_type == chess.BISHOP:
            # Bishop blocking own unmoved central pawn
            direction = 1 if color == chess.WHITE else -1
            expected_rank = pawn_start_rank + direction
            if rank_idx == expected_rank and file_idx in (3, 4):  # d and e files only
                pawn_sq = chess.square(file_idx, pawn_start_rank)
                pawn = board.piece_at(pawn_sq)
                if pawn and pawn.piece_type == chess.PAWN and pawn.color == color:
                    is_bad = True
                    reason = f"Bishop on {sq_name} blocks your {chess.square_name(pawn_sq)} pawn"

        if is_bad:
            badly_placed.append(reason)
        else:
            well_placed += 1

    if total == 0:
        return _fund("Piece Development", "Opening", COMPLETED, 100, "All minor pieces traded or active.")

    if developed == 0:
        return _fund("Piece Development", "Opening", NOT_STARTED, 0, "No minor pieces developed yet. Get your knights and bishops into the game.")

    # Find undeveloped pieces to name them specifically
    undeveloped_pieces = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type in (chess.KNIGHT, chess.BISHOP):
            if chess.square_rank(sq) == back_rank:
                piece_name = "knight" if p.piece_type == chess.KNIGHT else "bishop"
                undeveloped_pieces.append(f"{piece_name} on {chess.square_name(sq)}")

    # Score: base from development ratio, penalty for bad placement
    base_progress = round(developed / total * 100)
    bad_penalty = len(badly_placed) * 20
    progress = max(10, base_progress - bad_penalty)

    if badly_placed:
        worst = badly_placed[0]
        if developed < total:
            return _fund("Piece Development", "Opening", IN_PROGRESS, progress,
                          f"{developed}/{total} developed, but {worst}.")
        else:
            return _fund("Piece Development", "Opening", IN_PROGRESS, progress,
                          f"All pieces out, but {worst}.")
    elif developed < total:
        if undeveloped_pieces:
            still_home = undeveloped_pieces[0]
            return _fund("Piece Development", "Opening", IN_PROGRESS, progress,
                          f"{developed}/{total} developed. Your {still_home} is still at home.")
        return _fund("Piece Development", "Opening", IN_PROGRESS, progress,
                      f"{developed}/{total} minor pieces developed. Keep going.")
    else:
        return _fund("Piece Development", "Opening", COMPLETED, 100, "Excellent — all pieces are developed to active squares. That's textbook.")


def _eval_king_safety_from_history(board: chess.Board, color: chess.Color,
                                    move_number: int, user_moves: List[Dict]) -> Dict:
    """Check king safety using move history (not just current king position)."""
    # Check if player castled at any point in the game
    has_castled = False
    for m in user_moves:
        san = m.get("move", "")
        if san in ("O-O", "O-O-O", "0-0", "0-0-0"):
            has_castled = True
            break
    # Also detect castling from king position (catches pending move not yet in history)
    if not has_castled:
        king_sq = board.king(color)
        if king_sq is not None:
            castled_squares = [chess.G1, chess.C1] if color == chess.WHITE else [chess.G8, chess.C8]
            if king_sq in castled_squares and not board.has_kingside_castling_rights(color) and not board.has_queenside_castling_rights(color):
                has_castled = True

    if has_castled:
        # Castled — check current pawn shield
        king_sq = board.king(color)
        if king_sq is not None:
            king_file = chess.square_file(king_sq)
            shield_rank = 1 if color == chess.WHITE else 6
            intact = 0
            for f in [max(0, king_file - 1), king_file, min(7, king_file + 1)]:
                p = board.piece_at(chess.square(f, shield_rank))
                if p and p.piece_type == chess.PAWN and p.color == color:
                    intact += 1
            if intact >= 2:
                return _fund("King Safety", "Opening", COMPLETED, 100, "Nice — king is safe behind a solid pawn shield. Well done castling early.")
            else:
                return _fund("King Safety", "Opening", COMPLETED, 80, "King castled. Pawn shield slightly weakened.")
        return _fund("King Safety", "Opening", COMPLETED, 90, "King castled earlier in the game.")

    # Not castled — check if possible
    can_castle_ks = board.has_kingside_castling_rights(color)
    can_castle_qs = board.has_queenside_castling_rights(color)

    if not can_castle_ks and not can_castle_qs:
        if move_number > 20:
            # Late game, castling lost — might be OK in endgame
            return _fund("King Safety", "Opening", IN_PROGRESS, 40,
                          "Never castled. King safety was a concern earlier.")
        return _fund("King Safety", "Opening", FAILED, 10,
                      "Castling rights lost. King safety was not addressed.")

    if move_number >= 10:
        return _fund("King Safety", "Opening", IN_PROGRESS, 30,
                      f"Move {move_number} and still uncastled. Castle soon.")

    return _fund("King Safety", "Opening", IN_PROGRESS, 40, "Castling available. Prioritize it.")


def _eval_center_control(board: chess.Board, color: chess.Color, opponent: chess.Color) -> Dict:
    """
    Evaluate center control: pawns on central squares + piece pressure.
    Inner center (e4/d4/e5/d5) counts double. Extended center (c3-f3 to c6-f6) counts once.
    """
    inner_center = [chess.E4, chess.D4, chess.E5, chess.D5]
    extended_center = [chess.C3, chess.D3, chess.E3, chess.F3,
                       chess.C4, chess.F4, chess.C5, chess.F5,
                       chess.C6, chess.D6, chess.E6, chess.F6]

    our_score = 0
    opp_score = 0
    our_pawns = 0
    our_pieces_on_center = 0

    # Inner center: pawns = 3 pts, pieces on square = 2 pts, attacks = 1 pt each
    for sq in inner_center:
        p = board.piece_at(sq)
        if p and p.color == color:
            if p.piece_type == chess.PAWN:
                our_score += 3
                our_pawns += 1
            else:
                our_score += 2
                our_pieces_on_center += 1
        elif p and p.color == opponent:
            if p.piece_type == chess.PAWN:
                opp_score += 3
            else:
                opp_score += 2
        our_score += len(board.attackers(color, sq))
        opp_score += len(board.attackers(opponent, sq))

    # Extended center: lighter weight
    for sq in extended_center:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type in (chess.KNIGHT, chess.BISHOP):
            our_score += 1
            our_pieces_on_center += 1
        elif p and p.color == opponent and p.piece_type in (chess.KNIGHT, chess.BISHOP):
            opp_score += 1

    total = our_score + opp_score
    if total == 0:
        return _fund("Center Control", "Opening", NOT_STARTED, 0,
                      "No influence on center squares yet.")

    ratio = our_score / total if total > 0 else 0
    progress = round(ratio * 100)

    if our_pawns >= 2:
        return _fund("Center Control", "Opening", COMPLETED, 100,
                      "Strong pawn center. You're controlling the key squares.")
    elif ratio >= 0.6:
        if our_pieces_on_center >= 2:
            return _fund("Center Control", "Opening", COMPLETED, progress,
                          f"Good center control — {our_pawns} pawn(s) and {our_pieces_on_center} pieces influence the center.")
        return _fund("Center Control", "Opening", IN_PROGRESS, progress,
                      "Decent center presence. Add more piece pressure to central squares.")
    elif ratio >= 0.4:
        return _fund("Center Control", "Opening", IN_PROGRESS, progress,
                      "Center is contested. Look for a pawn push or piece move to claim more space.")
    else:
        return _fund("Center Control", "Opening", FAILED, progress,
                      "Opponent dominates the center. Challenge it with a pawn break or piece development.")


def _eval_piece_coordination(board: chess.Board, color: chess.Color) -> Dict:
    pieces = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type not in (chess.PAWN, chess.KING):
            pieces.append(sq)

    if len(pieces) < 2:
        return _fund("Piece Coordination", "Opening", NOT_STARTED, 0, "Not enough pieces to coordinate.")

    # How many of our pieces defend each other?
    defended = 0
    for sq in pieces:
        defenders = board.attackers(color, sq)
        if len(defenders) >= 1:
            defended += 1

    ratio = defended / len(pieces) if pieces else 0
    progress = round(ratio * 100)

    if ratio >= 0.7:
        return _fund("Piece Coordination", "Opening", COMPLETED, progress,
                      "Pieces are well connected and supporting each other.")
    elif ratio >= 0.4:
        return _fund("Piece Coordination", "Opening", IN_PROGRESS, progress,
                      f"{defended}/{len(pieces)} pieces are defended by other pieces.")
    else:
        return _fund("Piece Coordination", "Opening", NOT_STARTED, progress,
                      "Most pieces are unconnected. Coordinate before attacking.")


def _eval_early_queen(board: chess.Board, color: chess.Color,
                       user_moves: List[Dict], move_number: int) -> Dict:
    if move_number > 10:
        return _fund("Avoid Early Queen", "Opening", COMPLETED, 100, "Opening played without premature queen usage.")

    queen_moves = 0
    for m in user_moves[:10]:
        san = m.get("move", "")
        if san.startswith("Q"):
            queen_moves += 1

    if queen_moves >= 2:
        return _fund("Avoid Early Queen", "Opening", FAILED, 10,
                      f"Queen moved {queen_moves} times in first 10 moves. Develop minor pieces first.")
    elif queen_moves == 1:
        return _fund("Avoid Early Queen", "Opening", IN_PROGRESS, 60,
                      "Queen moved once early. Be careful not to overuse it.")
    return _fund("Avoid Early Queen", "Opening", COMPLETED, 100, "Good discipline — queen stayed back while other pieces developed.")


def _eval_development_efficiency(user_moves: List[Dict], board: chess.Board, color: chess.Color) -> Dict:
    if len(user_moves) < 4:
        return _fund("Development Efficiency", "Opening", NOT_STARTED, 0, "Too early to evaluate.")

    # Check if same piece moved multiple times in first 10 moves
    piece_moves = {}
    temp = chess.Board()
    for m in user_moves[:10]:
        san = m.get("move", "")
        try:
            move = temp.parse_san(san)
            from_sq = move.from_square
            p = temp.piece_at(from_sq)
            if p and p.piece_type not in (chess.PAWN, chess.KING):
                key = f"{chess.piece_name(p.piece_type)}"
                piece_moves[key] = piece_moves.get(key, 0) + 1
            temp.push(move)
        except Exception:
            break

    repeated = [k for k, v in piece_moves.items() if v >= 3]
    if repeated:
        return _fund("Development Efficiency", "Opening", FAILED, 20,
                      f"Your {repeated[0]} moved {piece_moves[repeated[0]]} times. Develop new pieces instead.")

    double = [k for k, v in piece_moves.items() if v == 2]
    if len(double) >= 2:
        return _fund("Development Efficiency", "Opening", IN_PROGRESS, 50,
                      "Multiple pieces moved twice. Try bringing out new pieces each move.")

    return _fund("Development Efficiency", "Opening", COMPLETED, 100,
                  "Good efficiency — each move brought out a new piece.")


def _eval_pawn_discipline(board: chess.Board, color: chess.Color) -> Dict:
    # Check for doubled, isolated pawns
    files_with_pawns = [0] * 8
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type == chess.PAWN and p.color == color:
            files_with_pawns[chess.square_file(sq)] += 1

    doubled = sum(1 for c in files_with_pawns if c >= 2)
    isolated = 0
    for f in range(8):
        if files_with_pawns[f] == 0:
            continue
        has_neighbor = False
        if f > 0 and files_with_pawns[f - 1] > 0:
            has_neighbor = True
        if f < 7 and files_with_pawns[f + 1] > 0:
            has_neighbor = True
        if not has_neighbor:
            isolated += 1

    if doubled >= 2 or isolated >= 2:
        return _fund("Pawn Structure", "Opening", FAILED, 20,
                      f"Pawn structure damaged: {doubled} doubled, {isolated} isolated.")
    elif doubled == 1 or isolated == 1:
        return _fund("Pawn Structure", "Opening", IN_PROGRESS, 60,
                      "Minor pawn weakness. Be careful with future pawn trades.")
    return _fund("Pawn Structure", "Opening", COMPLETED, 100, "Pawn structure is clean. No weaknesses to worry about.")


# ─── TACTICAL EVALUATORS ─────────────────────────────────────────

def _eval_threat_awareness(user_moves: List[Dict], board: chess.Board,
                            color: chess.Color, opponent: chess.Color) -> Dict:
    """
    Did the user address the opponent's threats?

    For each user move, we check:
    1. What did the opponent's previous move threaten? (new attacks on user pieces)
    2. Did the user respond to it? (defend, block, move the piece, or counterattack)
    3. If user ignored it — was the user's move still good? (cp_loss check)
       Good counterattack = fine. Ignoring for nothing = missed threat.
    """
    if not user_moves:
        return _fund("Threat Awareness", "Tactical", NOT_STARTED, 0, "No moves to evaluate.")

    missed_threats = 0
    addressed_threats = 0
    total_threats = 0
    last_missed_detail = ""

    for m in user_moves:
        fen_before = m.get("fen_before")
        if not fen_before:
            continue

        try:
            board_before = chess.Board(fen_before)
        except Exception:
            continue

        # Find what the opponent's last move newly threatens
        # Compare: which of our pieces are attacked NOW that weren't before?
        threats = _find_opponent_threats(board_before, color, opponent)

        if not threats:
            continue  # No threats to address

        total_threats += 1

        # Did the user's move address ANY of the threats?
        user_san = m.get("move", "")
        if not user_san:
            continue

        try:
            user_move = board_before.parse_san(user_san)
        except Exception:
            continue

        addressed = _did_address_threat(board_before, user_move, threats, color, opponent)

        if addressed:
            addressed_threats += 1
        else:
            # User didn't address the threat — but was the move still good?
            eb = m.get("eval_before")
            ea = m.get("eval_after")
            if eb is not None and ea is not None:
                cp_loss = (eb - ea) if color == chess.WHITE else (ea - eb)
                if cp_loss < 0.5:
                    # Move was fine — user chose a strong counterattack
                    addressed_threats += 1
                    continue

            missed_threats += 1
            # Build detail for the last missed threat
            threatened_piece = threats[0]
            sq_name = chess.square_name(threatened_piece["square"])
            piece_name = chess.piece_name(threatened_piece["piece_type"])
            last_missed_detail = f"Your {piece_name} on {sq_name} was under attack"

    if total_threats == 0:
        return _fund("Threat Awareness", "Tactical", COMPLETED, 100,
                      "No opponent threats to worry about so far.")

    if missed_threats == 0:
        return _fund("Threat Awareness", "Tactical", COMPLETED, 100,
                      "Good habit — you addressed every opponent threat. Keep doing this.")
    elif missed_threats == 1:
        reason = f"1 threat missed. {last_missed_detail}." if last_missed_detail else "1 missed threat."
        reason += " Before moving, ask: what is my opponent attacking?"
        return _fund("Threat Awareness", "Tactical", IN_PROGRESS, 70, reason)
    else:
        return _fund("Threat Awareness", "Tactical", FAILED, max(0, 100 - missed_threats * 20),
                      f"{missed_threats} threats missed. Habit: name your opponent's threat before touching a piece.")


def _find_opponent_threats(board: chess.Board, user_color: chess.Color,
                            opp_color: chess.Color) -> List[Dict]:
    """Find user pieces that are attacked by the opponent and not adequately defended."""
    threats = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != user_color or piece.piece_type == chess.KING:
            continue

        attackers = board.attackers(opp_color, sq)
        real_attackers = [a for a in attackers if not board.is_pinned(opp_color, a)]
        if not real_attackers:
            continue

        defenders = board.attackers(user_color, sq)

        # Threat exists if:
        # 1. Piece is undefended (any attacker can take for free), OR
        # 2. Attacker value <= piece value (equal or profitable trade — still a threat)
        # We include equal trades (bishop takes knight) because the user needs to decide
        piece_val = _PIECE_VALUES.get(piece.piece_type, 0)
        if piece_val < 3:
            continue  # Skip pawns — pawn threats are too noisy
        if not defenders:
            threats.append({"square": sq, "piece_type": piece.piece_type, "value": piece_val, "undefended": True})
        else:
            min_attacker_val = min(_PIECE_VALUES.get(board.piece_at(a).piece_type, 0) for a in real_attackers)
            if min_attacker_val <= piece_val:
                threats.append({"square": sq, "piece_type": piece.piece_type, "value": piece_val, "undefended": False})

    # Sort by value — most valuable piece threatened first
    threats.sort(key=lambda t: -t["value"])
    return threats


def _did_address_threat(board: chess.Board, user_move: chess.Move,
                         threats: List[Dict], user_color: chess.Color,
                         opp_color: chess.Color) -> bool:
    """Check if the user's move addresses at least one of the threats."""
    # Make the move and check if threats are resolved
    board_after = board.copy()
    board_after.push(user_move)

    for threat in threats:
        sq = threat["square"]
        piece = board_after.piece_at(sq)

        # Case 1: Threatened piece moved away
        if not piece or piece.color != user_color or piece.piece_type != threat["piece_type"]:
            return True

        # Case 2: Threat is now defended (new defender added)
        defenders_after = board_after.attackers(user_color, sq)
        attackers_after = board_after.attackers(opp_color, sq)
        real_attackers_after = [a for a in attackers_after if not board_after.is_pinned(opp_color, a)]

        if not real_attackers_after:
            return True  # Attacker was blocked or captured

        if len(defenders_after) > len(board.attackers(user_color, sq)):
            return True  # Added a defender

    # Case 3: User captured the attacker
    if board.piece_at(user_move.to_square) and board.piece_at(user_move.to_square).color == opp_color:
        return True

    return False


_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def _eval_piece_safety(board: chess.Board, color: chess.Color, opponent: chess.Color) -> Dict:
    hanging = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type not in (chess.KING, chess.PAWN):
            atts = board.attackers(opponent, sq)
            defs = board.attackers(color, sq)
            real_atts = [a for a in atts if not board.is_pinned(opponent, a)]
            if real_atts and not defs:
                hanging += 1

    if hanging == 0:
        return _fund("Piece Safety", "Tactical", COMPLETED, 100, "All pieces are defended. Good board awareness.")
    elif hanging == 1:
        return _fund("Piece Safety", "Tactical", FAILED, 40,
                      "1 piece is hanging. Check defenders before moving.")
    else:
        return _fund("Piece Safety", "Tactical", FAILED, 10,
                      f"{hanging} pieces are undefended. Urgent — secure them.")


def _eval_calculation_depth(user_moves: List[Dict], eval_data: Dict) -> Dict:
    """
    Did the user calculate before moving?
    Checks two things:
    1. Blunders (big eval drops — missed something deep)
    2. Walked into 1-move tactics (opponent can capture for free after user's move)
    """
    blunders = 0
    walked_into_tactic = 0
    last_tactic_detail = ""

    for m in user_moves:
        eb = m.get("eval_before")
        ea = m.get("eval_after")

        # Big eval drop = calculation error
        if m.get("evaluation") in ("BLUNDER",):
            blunders += 1
        elif eb is not None and ea is not None and abs(eb - ea) >= 3.0:
            blunders += 1

        # Check if user's move left a piece hanging (1-move tactic)
        fen_after = m.get("fen_after")
        if fen_after:
            try:
                board_after = chess.Board(fen_after)
                user_color = board_after.turn  # it's opponent's turn after user moved
                # opponent = whose turn it is now (they can capture)
                for sq in chess.SQUARES:
                    p = board_after.piece_at(sq)
                    if not p or p.color == user_color or p.piece_type in (chess.KING, chess.PAWN):
                        continue
                    # Is this user's piece attacked and undefended?
                    attackers = board_after.attackers(user_color, sq)
                    real_atts = [a for a in attackers if not board_after.is_pinned(user_color, a)]
                    defenders = board_after.attackers(not user_color, sq)
                    if real_atts and not defenders:
                        piece_name = chess.piece_name(p.piece_type)
                        walked_into_tactic += 1
                        last_tactic_detail = f"Your {piece_name} on {chess.square_name(sq)} was left undefended"
                        break
            except Exception:
                pass

    total_errors = blunders + walked_into_tactic
    total = len(user_moves)
    if total == 0:
        return _fund("Calculation", "Tactical", NOT_STARTED, 0, "No moves to evaluate.")

    if total_errors == 0:
        return _fund("Calculation", "Tactical", COMPLETED, 100,
                      "No calculation errors so far. Clean, accurate play.")
    elif total_errors == 1:
        detail = last_tactic_detail or "Check 2 moves ahead before committing"
        return _fund("Calculation", "Tactical", IN_PROGRESS, 70,
                      f"1 calculation slip. {detail}.")
    else:
        detail = ""
        if walked_into_tactic > 0:
            detail = f" {walked_into_tactic} time(s) you left a piece undefended."
        return _fund("Calculation", "Tactical", FAILED, max(0, 100 - total_errors * 25),
                      f"{total_errors} calculation errors.{detail} Slow down on critical moves.")


def _eval_tactical_awareness(board: chess.Board, color: chess.Color, opponent: chess.Color) -> Dict:
    # Check for existing pins, forks
    tactics_found = []

    # Pins on opponent
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == opponent and p.piece_type != chess.KING:
            if board.is_pinned(opponent, sq):
                tactics_found.append(f"pin on {chess.square_name(sq)}")
                break

    # Our pieces pinned
    our_pinned = False
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type != chess.KING:
            if board.is_pinned(color, sq):
                our_pinned = True
                break

    # Forks by our pieces
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type in (chess.KNIGHT, chess.QUEEN):
            targets = []
            for t_sq in board.attacks(sq):
                t = board.piece_at(t_sq)
                if t and t.color == opponent and t.piece_type not in (chess.PAWN,):
                    targets.append(t_sq)
            if len(targets) >= 2:
                tactics_found.append("fork opportunity")
                break

    if our_pinned:
        return _fund("Tactical Awareness", "Tactical", IN_PROGRESS, 50,
                      "You have a pinned piece. Consider how to break it.")
    elif tactics_found:
        return _fund("Tactical Awareness", "Tactical", COMPLETED, 90,
                      f"Tactics present: {', '.join(tactics_found[:2])}. Exploit them.")
    else:
        return _fund("Tactical Awareness", "Tactical", IN_PROGRESS, 60,
                      "No immediate tactics. Keep scanning for forks and pins.")


# ─── POSITIONAL EVALUATORS ───────────────────────────────────────

def _eval_playing_with_plan(user_moves: List[Dict], eval_data: Dict) -> Dict:
    """
    Detect if user is playing with a plan or making random moves.

    Plan indicators (positive):
    - Consistent piece improvements (same piece moves toward a better square)
    - Pawn breaks (advancing a pawn to open/challenge the center)
    - Piece coordination (moves that support each other)
    - Eval stays stable or improves

    Random indicators (negative):
    - Same piece moves back and forth
    - Moves that don't change the eval in either direction (shuffling)
    - Moving pieces away from the action
    """
    if len(user_moves) < 5:
        return _fund("Playing With a Plan", "Positional", NOT_STARTED, 0, "Too early to evaluate.")

    recent = user_moves[-6:]
    plan_score = 0
    issues = []

    # Check 1: Piece shuffling — same piece moving back and forth
    piece_moves = {}  # track squares visited by each piece type
    for m in recent:
        san = m.get("move", "")
        fen_before = m.get("fen_before", "")
        if not san or not fen_before:
            continue
        try:
            b = chess.Board(fen_before)
            mv = b.parse_san(san)
            piece = b.piece_at(mv.from_square)
            if piece and piece.piece_type not in (chess.PAWN, chess.KING):
                key = piece.piece_type
                if key not in piece_moves:
                    piece_moves[key] = []
                piece_moves[key].append((mv.from_square, mv.to_square))
        except Exception:
            continue

    for piece_type, moves in piece_moves.items():
        if len(moves) >= 2:
            # Check if piece went A->B then B->A (or similar)
            squares = [mv[0] for mv in moves] + [moves[-1][1]]
            if len(set(squares)) < len(squares):
                issues.append(f"Your {chess.piece_name(piece_type)} moved back and forth")
                plan_score -= 2

    # Check 2: Eval stability — are moves maintaining/improving position?
    good_moves = 0
    bad_moves = 0
    for m in recent:
        eb = m.get("eval_before")
        ea = m.get("eval_after")
        if eb is not None and ea is not None:
            drop = (eb - ea) if user_moves[0].get("by") == "player" else (ea - eb)
            if drop < 0.3:
                good_moves += 1
            elif drop > 1.0:
                bad_moves += 1

    if good_moves >= 4:
        plan_score += 3
    elif bad_moves >= 2:
        plan_score -= 2
        issues.append("Several moves lost ground")

    # Check 3: Pawn advances (sign of a plan)
    pawn_advances = sum(1 for m in recent if m.get("move", "")[0].islower() and "x" not in m.get("move", ""))
    if pawn_advances >= 2:
        plan_score += 1  # Pawn pushes suggest a plan

    # Score to progress
    progress = max(0, min(100, 50 + plan_score * 12))

    if plan_score >= 2:
        return _fund("Playing With a Plan", "Positional", COMPLETED, progress,
                      "Your recent moves are consistent and purposeful.")
    elif plan_score >= 0:
        issue_text = issues[0] if issues else "Think about your next 2-3 moves before playing"
        return _fund("Playing With a Plan", "Positional", IN_PROGRESS, progress,
                      f"Some moves feel aimless. {issue_text}.")
    else:
        issue_text = issues[0] if issues else "Stop and ask: what am I trying to achieve?"
        return _fund("Playing With a Plan", "Positional", FAILED, progress,
                      f"Moves are disconnected. {issue_text}.")


def _eval_piece_activity(board: chess.Board, color: chess.Color) -> Dict:
    total = 0
    active = 0

    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type not in (chess.PAWN, chess.KING):
            total += 1
            mobility = len(list(board.attacks(sq)))
            if mobility >= 4:
                active += 1

    if total == 0:
        return _fund("Piece Activity", "Positional", COMPLETED, 100, "All pieces traded.")

    ratio = active / total
    progress = round(ratio * 100)

    if ratio >= 0.7:
        return _fund("Piece Activity", "Positional", COMPLETED, progress,
                      "Most pieces are active with good mobility.")
    elif ratio >= 0.4:
        return _fund("Piece Activity", "Positional", IN_PROGRESS, progress,
                      f"{active}/{total} pieces are active. Improve the passive ones.")
    else:
        return _fund("Piece Activity", "Positional", FAILED, progress,
                      "Most pieces are passive. Find better squares for them.")


def _eval_rook_usage(board: chess.Board, color: chess.Color) -> Dict:
    """Check if rooks are connected and on useful files (open/semi-open)."""
    rook_squares = [sq for sq in chess.SQUARES
                    if board.piece_at(sq) and board.piece_at(sq).piece_type == chess.ROOK
                    and board.piece_at(sq).color == color]

    if len(rook_squares) == 0:
        return _fund("Rook Usage", "Positional", IN_PROGRESS, 50, "No rooks on the board.")
    if len(rook_squares) == 1:
        # Check if on open/semi-open file
        sq = rook_squares[0]
        file_idx = chess.square_file(sq)
        own_pawn_on_file = any(
            board.piece_at(chess.square(file_idx, r))
            and board.piece_at(chess.square(file_idx, r)).piece_type == chess.PAWN
            and board.piece_at(chess.square(file_idx, r)).color == color
            for r in range(8)
        )
        if not own_pawn_on_file:
            return _fund("Rook Usage", "Positional", COMPLETED, 80,
                          f"Rook on {chess.square_name(sq)} is on an open file. Good placement.")
        return _fund("Rook Usage", "Positional", IN_PROGRESS, 50,
                      f"Rook on a closed file. Look for an open file to move it to.")

    # Two rooks — check if connected (can see each other on same rank/file with nothing between)
    r1, r2 = rook_squares[0], rook_squares[1]
    connected = False
    if chess.square_rank(r1) == chess.square_rank(r2):
        # Same rank — check if path is clear
        rank = chess.square_rank(r1)
        f1, f2 = sorted([chess.square_file(r1), chess.square_file(r2)])
        clear = all(not board.piece_at(chess.square(f, rank)) for f in range(f1 + 1, f2))
        connected = clear
    elif chess.square_file(r1) == chess.square_file(r2):
        # Same file — check if path is clear
        file_idx = chess.square_file(r1)
        rk1, rk2 = sorted([chess.square_rank(r1), chess.square_rank(r2)])
        clear = all(not board.piece_at(chess.square(file_idx, r)) for r in range(rk1 + 1, rk2))
        connected = clear

    # Check open file usage
    on_open_file = 0
    for sq in rook_squares:
        file_idx = chess.square_file(sq)
        own_pawn_on_file = any(
            board.piece_at(chess.square(file_idx, r))
            and board.piece_at(chess.square(file_idx, r)).piece_type == chess.PAWN
            and board.piece_at(chess.square(file_idx, r)).color == color
            for r in range(8)
        )
        if not own_pawn_on_file:
            on_open_file += 1

    if connected and on_open_file >= 1:
        return _fund("Rook Usage", "Positional", COMPLETED, 100,
                      "Rooks connected and active on open files. Strong setup.")
    elif connected:
        return _fund("Rook Usage", "Positional", IN_PROGRESS, 70,
                      "Rooks are connected. Now get them on open files.")
    elif on_open_file >= 1:
        return _fund("Rook Usage", "Positional", IN_PROGRESS, 60,
                      "A rook is on an open file, but rooks aren't connected yet. Clear the back rank.")
    else:
        return _fund("Rook Usage", "Positional", FAILED, 30,
                      "Rooks are disconnected and on closed files. Connect them and find open files.")


def _eval_pawn_structure_awareness(board: chess.Board, color: chess.Color) -> Dict:
    files = [0] * 8
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type == chess.PAWN and p.color == color:
            files[chess.square_file(sq)] += 1

    doubled = sum(1 for c in files if c >= 2)
    isolated = 0
    for f in range(8):
        if files[f] == 0:
            continue
        neighbor = (f > 0 and files[f - 1] > 0) or (f < 7 and files[f + 1] > 0)
        if not neighbor:
            isolated += 1

    weaknesses = doubled + isolated
    if weaknesses == 0:
        return _fund("Pawn Structure", "Positional", COMPLETED, 100, "Clean pawn structure. No weaknesses.")
    elif weaknesses <= 1:
        return _fund("Pawn Structure", "Positional", IN_PROGRESS, 70,
                      "Minor pawn weakness. Avoid creating more.")
    else:
        return _fund("Pawn Structure", "Positional", FAILED, max(0, 100 - weaknesses * 25),
                      f"{weaknesses} pawn weaknesses. These give your opponent targets.")


# ─── ENDGAME EVALUATORS ──────────────────────────────────────────

def _eval_king_activation(board: chess.Board, color: chess.Color) -> Dict:
    king_sq = board.king(color)
    if king_sq is None:
        return _fund("King Activation", "Endgame", NOT_STARTED, 0, "No king.")

    rank = chess.square_rank(king_sq)
    file = chess.square_file(king_sq)
    centrality = min(file, 7 - file) + min(rank, 7 - rank)

    if centrality >= 4:
        return _fund("King Activation", "Endgame", COMPLETED, 100,
                      "King is centralized. Active king is crucial in endgames.")
    elif centrality >= 2:
        return _fund("King Activation", "Endgame", IN_PROGRESS, 50,
                      "King is moving toward the center. Keep going.")
    else:
        return _fund("King Activation", "Endgame", NOT_STARTED, 10,
                      "King is still on the edge. In endgames, centralize your king.")


def _eval_pawn_promotion_awareness(board: chess.Board, color: chess.Color, opponent: chess.Color) -> Dict:
    passed = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.piece_type != chess.PAWN or p.color != color:
            continue

        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        is_passed = True

        if color == chess.WHITE:
            check_ranks = range(rank + 1, 8)
        else:
            check_ranks = range(0, rank)

        for r in check_ranks:
            for f in [file - 1, file, file + 1]:
                if 0 <= f <= 7:
                    bp = board.piece_at(chess.square(f, r))
                    if bp and bp.piece_type == chess.PAWN and bp.color == opponent:
                        is_passed = False
                        break
            if not is_passed:
                break

        if is_passed:
            passed += 1

    if passed >= 2:
        return _fund("Pawn Promotion", "Endgame", COMPLETED, 90,
                      f"{passed} passed pawns. Push them — they're your winning weapon.")
    elif passed == 1:
        return _fund("Pawn Promotion", "Endgame", IN_PROGRESS, 60,
                      "1 passed pawn. Support it and push it forward.")
    else:
        return _fund("Pawn Promotion", "Endgame", NOT_STARTED, 20,
                      "No passed pawns. Create one by exchanging pawns.")


# ─── HELPER ───────────────────────────────────────────────────────

def _fund(name: str, category: str, status: str, progress: int, reason: str) -> Dict:
    return {
        "name": name,
        "category": category,
        "status": status,
        "progress": min(100, max(0, progress)),
        "reason": reason,
    }
