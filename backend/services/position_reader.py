"""
Position Reader — Teaches players HOW TO READ A BOARD
======================================================

Looks at a FEN and returns the 2-3 most important things to notice,
adapted to the player's rating.

800-1000: Basic safety — hanging pieces, king safety, development
1000-1200: + Open files, piece activity, center control
1200-1400: + Pawn structure, pins, weak squares
1400-1600: + Prophylaxis, piece coordination, long-term plans

Not what to PLAY — what to SEE.
"""

import chess
import logging
from typing import Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PositionFeature:
    priority: int       # Lower = more important
    category: str       # "king_safety", "tactics", "piece_activity", "pawn_structure", "development"
    title: str          # Short label
    description: str    # What to notice
    min_rating: int     # Don't show below this rating
    actionable: str     # What to do about it


def read_position(fen: str, user_color: str = "white", user_rating: int = 1200) -> Dict:
    """
    Read a position and return the most important features for this player's level.
    """
    try:
        board = chess.Board(fen)
    except Exception:
        return {"features": [], "eval_text": "Invalid position"}

    user_is_white = user_color == "white"
    user_color_bool = chess.WHITE if user_is_white else chess.BLACK
    opp_color_bool = not user_color_bool

    features = []

    # ─── KING SAFETY (all levels) ───
    features.extend(_analyze_king_safety(board, user_color_bool, opp_color_bool))

    # ─── HANGING PIECES (all levels) ───
    features.extend(_analyze_hanging_pieces(board, user_color_bool, opp_color_bool))

    # ─── DEVELOPMENT (800+) ───
    features.extend(_analyze_development(board, user_color_bool))

    # ─── OPEN FILES (1000+) ───
    features.extend(_analyze_open_files(board, user_color_bool))

    # ─── PIECE ACTIVITY (1000+) ───
    features.extend(_analyze_piece_activity(board, user_color_bool, opp_color_bool))

    # ─── CENTER CONTROL (1000+) ───
    features.extend(_analyze_center(board, user_color_bool))

    # ─── PAWN STRUCTURE (1200+) ───
    features.extend(_analyze_pawn_structure(board, user_color_bool))

    # ─── PINS (1200+) ───
    features.extend(_analyze_pins(board, user_color_bool, opp_color_bool))

    # ─── CHECKS AVAILABLE (all levels) ───
    features.extend(_analyze_checks(board, user_color_bool))

    # ─── CASTLING STATUS (always relevant) ───
    features.extend(_analyze_castling(board, user_color_bool, opp_color_bool))

    # ─── SPACE + PIECE COUNT (always something to say) ───
    features.extend(_analyze_general(board, user_color_bool, opp_color_bool))

    # ─── FORKS (all levels) ───
    features.extend(_analyze_forks(board, user_color_bool, opp_color_bool))

    # ─── OUR PINNED PIECES (all levels) ───
    features.extend(_analyze_our_pins(board, user_color_bool, opp_color_bool))

    # Filter by rating
    filtered = [f for f in features if f.min_rating <= user_rating]

    # Sort by priority, take top 6 (more observations for commentary panel)
    filtered.sort(key=lambda f: f.priority)
    top = filtered[:6]

    # Who's better (simple material count)
    eval_text = _get_eval_text(board, user_color_bool)

    # Game phase
    phase = _get_phase(board)

    return {
        "features": [
            {
                "category": f.category,
                "title": f.title,
                "description": f.description,
                "actionable": f.actionable,
            }
            for f in top
        ],
        "eval_text": eval_text,
        "phase": phase,
    }


# ─── ANALYZERS ───────────────────────────────────────────────

def _analyze_king_safety(board, user_color, opp_color) -> List[PositionFeature]:
    features = []

    # Opponent's king analysis
    opp_king_sq = board.king(opp_color)
    if opp_king_sq is not None:
        opp_castled = _is_castled(board, opp_color, opp_king_sq)
        opp_pawn_shield = _has_pawn_shield(board, opp_color, opp_king_sq)
        
        if not opp_castled:
            # King in the center — only flag if game is far enough along
            if board.fullmove_number >= 8:
                king_name = chess.square_name(opp_king_sq)
                escape_squares = _count_escape_squares(board, opp_color, opp_king_sq, user_color)
            
                if len(escape_squares) <= 1:
                    features.append(PositionFeature(
                        priority=1,
                        category="king_safety",
                        title="Opponent's king hasn't castled",
                        description=f"Their king is stuck on {king_name} with {'only 1 escape: ' + escape_squares[0] if escape_squares else 'almost no escape squares'}. It's vulnerable in the center.",
                        min_rating=800,
                        actionable="Open the center! An uncastled king hates open lines. Look for checks.",
                    ))
                else:
                    features.append(PositionFeature(
                        priority=3,
                        category="king_safety",
                        title="Opponent still hasn't castled",
                        description=f"Their king is still on {king_name} after {board.fullmove_number} moves. This is a target.",
                        min_rating=800,
                        actionable="Open the center and look for checks. Their king is uncomfortable.",
                    ))
        elif opp_castled and not opp_pawn_shield:
            # Castled but pawn shield is broken
            king_name = chess.square_name(opp_king_sq)
            features.append(PositionFeature(
                priority=2,
                category="king_safety",
                title="Opponent's pawn shield is broken",
                description=f"Their king castled but the pawns in front are damaged. This creates attack opportunities.",
                min_rating=1000,
                actionable="Look for ways to open lines toward their king. A broken pawn shield = attacking chances.",
            ))

    # User's own king — only warn if genuinely exposed
    user_king_sq = board.king(user_color)
    if user_king_sq is not None:
        user_castled = _is_castled(board, user_color, user_king_sq)
        
        if not user_castled and board.fullmove_number >= 8:
            features.append(PositionFeature(
                priority=2,
                category="king_safety",
                title="Your king hasn't castled yet",
                description=f"It's move {board.fullmove_number} and your king is still in the center. Castle soon.",
                min_rating=800,
                actionable="Castle as soon as possible. Your king is not safe in the center.",
            ))

    return features


def _is_castled(board, color, king_sq) -> bool:
    """Check if king is in a castled position."""
    file_idx = chess.square_file(king_sq)
    rank_idx = chess.square_rank(king_sq)
    
    expected_rank = 0 if color == chess.WHITE else 7
    if rank_idx != expected_rank:
        return False  # King moved off back rank — could be castled or not
    
    # Kingside castle: king on g1/g8
    if file_idx == 6:
        return True
    # Queenside castle: king on c1/c8
    if file_idx == 2:
        return True
    # King still on e-file: hasn't castled
    if file_idx == 4:
        return False
    # King on h-file (rare but possible after castling + moves)
    if file_idx in [5, 6, 7]:
        return True
    
    return False


def _has_pawn_shield(board, color, king_sq) -> bool:
    """Check if castled king has intact pawn shield."""
    file_idx = chess.square_file(king_sq)
    rank_idx = chess.square_rank(king_sq)
    
    pawn_rank = rank_idx + (1 if color == chess.WHITE else -1)
    if pawn_rank < 0 or pawn_rank > 7:
        return False
    
    # Check pawns on the 3 files around the king
    shield_files = [max(0, file_idx - 1), file_idx, min(7, file_idx + 1)]
    pawns_present = 0
    
    for f in shield_files:
        sq = chess.square(f, pawn_rank)
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.PAWN and piece.color == color:
            pawns_present += 1
    
    return pawns_present >= 2  # At least 2 of 3 shield pawns intact


def _count_escape_squares(board, king_color, king_sq, attacker_color) -> List[str]:
    """Count safe escape squares for a king."""
    escapes = []
    for sq in chess.SQUARES:
        if chess.square_distance(king_sq, sq) == 1:
            piece = board.piece_at(sq)
            if piece is None or piece.color != king_color:
                if not board.is_attacked_by(attacker_color, sq):
                    escapes.append(chess.square_name(sq))
    return escapes


def _analyze_hanging_pieces(board, user_color, opp_color) -> List[PositionFeature]:
    features = []
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

    # Opponent's undefended pieces we can capture
    best_target = None
    best_target_value = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != opp_color or piece.piece_type == chess.KING:
            continue
        attacked_by_us = board.is_attacked_by(user_color, sq)
        defended = board.is_attacked_by(opp_color, sq)
        if attacked_by_us and not defended:
            # Verify capture is SAFE — check our cheapest attacker vs their piece value
            our_attackers = list(board.attackers(user_color, sq))
            if not our_attackers:
                continue
            cheapest_attacker = min(our_attackers, key=lambda a: piece_values.get(board.piece_at(a).piece_type, 0) if board.piece_at(a) else 99)
            attacker_piece = board.piece_at(cheapest_attacker)
            if not attacker_piece:
                continue
            attacker_value = piece_values.get(attacker_piece.piece_type, 0)
            target_value = piece_values.get(piece.piece_type, 0)
            # Only flag if we don't lose material (e.g. don't take pawn with queen if they can recapture)
            if target_value >= attacker_value or not defended:
                if target_value > best_target_value:
                    best_target = (sq, piece, attacker_piece)
                    best_target_value = target_value

    if best_target:
        sq, piece, attacker = best_target
        piece_name = chess.piece_name(piece.piece_type)
        sq_name = chess.square_name(sq)
        attacker_name = chess.piece_name(attacker.piece_type)
        features.append(PositionFeature(
            priority=1,
            category="tactics",
            title=f"Opponent's {piece_name} is undefended",
            description=f"Their {piece_name} on {sq_name} has no defender. Your {attacker_name} can take it.",
            min_rating=800,
            actionable=f"Take their {piece_name} on {sq_name} with your {attacker_name}.",
        ))

    # Your hanging pieces — only flag if it's actually under attack AND undefended
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != user_color or piece.piece_type == chess.KING:
            continue
        attackers = list(board.attackers(opp_color, sq))
        defenders = list(board.attackers(user_color, sq))
        if not attackers:
            continue
        # Only flag if there's a real attacker (not just x-ray through pieces)
        # and we're actually losing material
        target_value = piece_values.get(piece.piece_type, 0)
        cheapest_attacker_value = min(
            (piece_values.get(board.piece_at(a).piece_type, 0) for a in attackers if board.piece_at(a)),
            default=99
        )
        # Hanging: attacked and undefended, OR attacked by cheaper piece
        if (not defenders and target_value >= 3) or (cheapest_attacker_value < target_value and len(attackers) > len(defenders)):
            piece_name = chess.piece_name(piece.piece_type)
            sq_name = chess.square_name(sq)
            features.append(PositionFeature(
                priority=2,
                category="tactics",
                title=f"Your {piece_name} is hanging",
                description=f"Your {piece_name} on {sq_name} is under attack with {'no defenders' if not defenders else 'not enough defenders'}.",
                min_rating=800,
                actionable=f"Save your {piece_name} on {sq_name} — move it or defend it.",
            ))
            break

    return features


def _analyze_development(board, user_color) -> List[PositionFeature]:
    features = []
    back_rank = 0 if user_color == chess.WHITE else 7

    undeveloped = []
    for sq in chess.SQUARES:
        if chess.square_rank(sq) != back_rank:
            continue
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            undeveloped.append(chess.piece_name(piece.piece_type) + " on " + chess.square_name(sq))

    if len(undeveloped) >= 2 and board.fullmove_number >= 5 and board.fullmove_number <= 15:
        features.append(PositionFeature(
            priority=4,
            category="development",
            title=f"{len(undeveloped)} pieces still on back rank",
            description=f"Your {' and '.join(undeveloped[:2])} haven't moved yet. Get them into the game.",
            min_rating=800,
            actionable="Develop a piece. Every piece sitting at home is a piece not helping.",
        ))

    return features


def _analyze_open_files(board, user_color) -> List[PositionFeature]:
    features = []

    # Only relevant in middlegame/endgame — rooks don't belong on open files in move 6
    if board.fullmove_number < 12:
        return features

    # Check if we even have a rook that's not on the back rank (i.e., is it developed?)
    back_rank = 0 if user_color == chess.WHITE else 7
    has_developed_rook = False
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.ROOK:
            if chess.square_rank(sq) != back_rank:
                has_developed_rook = True

    for file_idx in range(8):
        has_white_pawn = False
        has_black_pawn = False
        for rank_idx in range(8):
            sq = chess.square(file_idx, rank_idx)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                if piece.color == chess.WHITE:
                    has_white_pawn = True
                else:
                    has_black_pawn = True

        if not has_white_pawn and not has_black_pawn:
            file_letter = chr(97 + file_idx)
            our_rook_on_file = False
            for rank_idx in range(8):
                sq = chess.square(file_idx, rank_idx)
                piece = board.piece_at(sq)
                if piece and piece.color == user_color and piece.piece_type == chess.ROOK:
                    our_rook_on_file = True

            if not our_rook_on_file:
                target_sq = f"{file_letter}1" if user_color == chess.WHITE else f"{file_letter}8"
                features.append(PositionFeature(
                    priority=6,
                    category="piece_activity",
                    title=f"Open {file_letter}-file — no rook there",
                    description=f"The {file_letter}-file has no pawns. A rook on {target_sq} would control it.",
                    min_rating=1000,
                    actionable=f"When you get a chance, move a rook to the {file_letter}-file.",
                ))
                break

    return features


def _analyze_piece_activity(board, user_color, opp_color) -> List[PositionFeature]:
    features = []

    # Only relevant after development phase
    if board.fullmove_number < 8:
        return features

    # Piece blocking own central pawn (e.g. Bd3 blocks d2-d4, Ne3 blocks e2-e4)
    # Check any minor piece sitting on a central file with its own unmoved pawn behind it
    home_rank = 0 if user_color == chess.WHITE else 7
    pawn_start_rank = 1 if user_color == chess.WHITE else 6
    direction = 1 if user_color == chess.WHITE else -1
    central_files = (2, 3, 4, 5)  # c, d, e, f

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != user_color or piece.piece_type not in (chess.BISHOP, chess.KNIGHT):
            continue
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        if file_idx not in central_files:
            continue
        # Is this piece on rank 3 (white) or rank 6 (black) — one square ahead of pawn start?
        expected_piece_rank = pawn_start_rank + direction
        if rank_idx != expected_piece_rank:
            continue
        # Is there an unmoved pawn behind it?
        pawn_sq = chess.square(file_idx, pawn_start_rank)
        pawn = board.piece_at(pawn_sq)
        if pawn and pawn.piece_type == chess.PAWN and pawn.color == user_color:
            piece_name = "Bishop" if piece.piece_type == chess.BISHOP else "Knight"
            sq_name = chess.square_name(sq)
            pawn_name = chess.square_name(pawn_sq)
            features.append(PositionFeature(
                priority=6,
                category="development",
                title=f"{piece_name} on {sq_name} blocks your {pawn_name} pawn",
                description=f"Your {piece_name.lower()} on {sq_name} prevents the {pawn_name} pawn from advancing. Develop where you don't block your own pawns.",
                min_rating=800,
                actionable=f"Look for a square where this {piece_name.lower()} is active without blocking your pawns.",
            ))

    # Knights on the rim — skip starting squares only
    starting_squares = {chess.B1, chess.G1, chess.B8, chess.G8}

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.KNIGHT:
            if sq in starting_squares:
                continue
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            if file_idx in [0, 7] or rank_idx in [0, 7]:
                # Check if knight has good squares to jump to (not really stuck)
                mobility = len([m for m in board.legal_moves if m.from_square == sq])
                # If it can reach a central square in 1 move, it's fine
                central_files = {2, 3, 4, 5}
                central_ranks = {2, 3, 4, 5}
                has_central_jump = any(
                    chess.square_file(m.to_square) in central_files and chess.square_rank(m.to_square) in central_ranks
                    for m in board.legal_moves if m.from_square == sq
                )
                if has_central_jump:
                    continue  # Knight can get to the center next move — not stuck

                sq_name = chess.square_name(sq)
                features.append(PositionFeature(
                    priority=7,
                    category="piece_activity",
                    title=f"Knight stuck on {sq_name}",
                    description=f"Your knight on {sq_name} is on the edge with {mobility} moves, none of them toward the center.",
                    min_rating=800,
                    actionable=f"This knight needs a better square. Look for a way to reroute it toward the center.",
                ))
                break

    # Opponent's passive knights
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == opp_color and piece.piece_type == chess.KNIGHT:
            if sq in starting_squares:
                continue
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            if file_idx in [0, 7] or rank_idx in [0, 7]:
                mobility = len([m for m in board.legal_moves if m.from_square == sq])
                # Only flag if it's truly stuck (few moves, none central)
                if mobility <= 3:
                    sq_name = chess.square_name(sq)
                    features.append(PositionFeature(
                        priority=8,
                        category="piece_activity",
                        title=f"Opponent's knight is stuck on {sq_name}",
                        description=f"Their knight on {sq_name} only has {mobility} squares. It's not helping them.",
                        min_rating=1000,
                        actionable="Their knight is passive. Don't give them time to reposition it — keep the pressure on.",
                    ))
                    break

    return features


def _analyze_center(board, user_color) -> List[PositionFeature]:
    features = []
    opp_color = not user_color

    # Only relevant after a few moves
    if board.fullmove_number < 5:
        return features

    center_squares = [chess.E4, chess.D4, chess.E5, chess.D5]

    # Count attacks on center squares (more meaningful than pieces ON center)
    user_attacks = 0
    opp_attacks = 0
    user_occupies = 0
    opp_occupies = 0

    for sq in center_squares:
        user_attacks += len(list(board.attackers(user_color, sq)))
        opp_attacks += len(list(board.attackers(opp_color, sq)))
        piece = board.piece_at(sq)
        if piece:
            if piece.color == user_color:
                user_occupies += 1
            else:
                opp_occupies += 1

    user_total = user_attacks + user_occupies * 2
    opp_total = opp_attacks + opp_occupies * 2

    if user_total >= opp_total + 4:
        features.append(PositionFeature(
            priority=9,
            category="center",
            title="You control the center",
            description="You have more pieces and pawns aimed at the center. This gives your pieces better squares.",
            min_rating=1000,
            actionable="Use your center control — your pieces can reach both sides of the board faster.",
        ))
    elif opp_total >= user_total + 4:
        features.append(PositionFeature(
            priority=5,
            category="center",
            title="Opponent controls the center",
            description="They have more control over d4, d5, e4, e5. Your pieces have fewer good squares.",
            min_rating=1000,
            actionable="Challenge the center — push a pawn (c5, d5, e5, or f5) or develop a piece toward the center.",
        ))

    return features


def _analyze_pawn_structure(board, user_color) -> List[PositionFeature]:
    features = []

    # Passed pawns
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type == chess.PAWN:
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            is_passed = True
            direction = 1 if user_color == chess.WHITE else -1

            for check_rank in range(rank_idx + direction, 8 if direction == 1 else -1, direction):
                for check_file in [file_idx - 1, file_idx, file_idx + 1]:
                    if 0 <= check_file <= 7:
                        check_sq = chess.square(check_file, check_rank)
                        check_piece = board.piece_at(check_sq)
                        if check_piece and check_piece.piece_type == chess.PAWN and check_piece.color != user_color:
                            is_passed = False
                            break
                if not is_passed:
                    break

            if is_passed and ((user_color == chess.WHITE and rank_idx >= 4) or (user_color == chess.BLACK and rank_idx <= 3)):
                features.append(PositionFeature(
                    priority=5,
                    category="pawn_structure",
                    title=f"Passed pawn on {chess.square_name(sq)}",
                    description=f"Your pawn on {chess.square_name(sq)} has no enemy pawns blocking it. It can march to promotion.",
                    min_rating=1200,
                    actionable="Push this pawn! Passed pawns must be pushed. Support it with your pieces.",
                ))
                break

    return features


def _analyze_pins(board, user_color, opp_color) -> List[PositionFeature]:
    features = []

    # Check if any opponent piece is pinned to their king
    opp_king = board.king(opp_color)
    if opp_king is None:
        return features

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == opp_color and piece.piece_type != chess.KING:
            if board.is_pinned(opp_color, sq):
                piece_name = chess.piece_name(piece.piece_type)
                sq_name = chess.square_name(sq)
                features.append(PositionFeature(
                    priority=3,
                    category="tactics",
                    title=f"Opponent's {piece_name} is pinned",
                    description=f"Their {piece_name} on {sq_name} is pinned to their king. It can't move without exposing the king.",
                    min_rating=1200,
                    actionable=f"A pinned piece is a weak piece. Can you pile up on {sq_name} with another attacker?",
                ))
                break

    return features


def _analyze_checks(board, user_color) -> List[PositionFeature]:
    features = []

    if board.turn != user_color:
        return features

    # Count available checks
    checks = []
    for move in board.legal_moves:
        board.push(move)
        if board.is_check():
            checks.append(move)
        board.pop()

    if len(checks) >= 2:
        check_sans = [board.san(m) for m in checks[:3]]
        features.append(PositionFeature(
            priority=4,
            category="tactics",
            title=f"{len(checks)} checks available",
            description=f"You can give check with: {', '.join(check_sans)}. Always consider checks — they force the opponent to respond.",
            min_rating=800,
            actionable="Check each check: does it lead to something good? A check that wins material or improves position is powerful.",
        ))

    return features


# ─── HELPERS ────────────────────────────────────────────────

def _get_eval_text(board, user_color) -> str:
    """Simple material-based evaluation."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    white_material = sum(values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.WHITE)
    black_material = sum(values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.BLACK)

    user_material = white_material if user_color == chess.WHITE else black_material
    opp_material = black_material if user_color == chess.WHITE else white_material
    diff = user_material - opp_material

    if diff >= 5:
        return "You're winning — up significant material."
    elif diff >= 3:
        return "You're up a piece. Convert carefully."
    elif diff >= 1:
        return "You're up a pawn. Small edge."
    elif diff <= -5:
        return "You're down big. Look for tricks."
    elif diff <= -3:
        return "You're down a piece. Need to fight back."
    elif diff <= -1:
        return "You're down a pawn. Stay solid."
    return "Material is equal."


def _get_phase(board) -> str:
    pieces = len(board.piece_map())
    if pieces >= 28:
        return "opening"
    elif pieces >= 14:
        return "middlegame"
    return "endgame"



def _analyze_castling(board, user_color, opp_color) -> List[PositionFeature]:
    """Castling opportunities and status."""
    features = []

    user_can_castle = board.has_castling_rights(user_color)
    opp_can_castle = board.has_castling_rights(opp_color)
    user_castled = _is_castled(board, user_color, board.king(user_color))
    opp_castled = _is_castled(board, opp_color, board.king(opp_color))

    if user_can_castle and not user_castled and board.fullmove_number >= 4:
        features.append(PositionFeature(
            priority=6,
            category="king_safety",
            title="You can still castle",
            description="Your king is still in the center. Castling gets it safe and connects your rooks.",
            min_rating=800,
            actionable="Look for a chance to castle soon.",
        ))

    if not opp_castled and not opp_can_castle and board.fullmove_number >= 6:
        features.append(PositionFeature(
            priority=5,
            category="king_safety",
            title="Opponent lost castling rights",
            description="They can't castle anymore. Their king is stuck in the center permanently.",
            min_rating=1000,
            actionable="Open the center! Their king is a target.",
        ))

    return features


def _analyze_general(board, user_color, opp_color) -> List[PositionFeature]:
    """General position assessment — always has something to say."""
    features = []

    # Count developed pieces (not on back rank)
    user_back = 0 if user_color == chess.WHITE else 7
    opp_back = 0 if opp_color == chess.WHITE else 7

    user_developed = 0
    opp_developed = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.piece_type in [chess.PAWN, chess.KING]:
            continue
        rank = chess.square_rank(sq)
        if piece.color == user_color and rank != user_back:
            user_developed += 1
        elif piece.color == opp_color and rank != opp_back:
            opp_developed += 1

    if user_developed > opp_developed + 1:
        features.append(PositionFeature(
            priority=8,
            category="development",
            title="You have better development",
            description=f"You have {user_developed} pieces developed vs their {opp_developed}. Use this lead before they catch up.",
            min_rating=800,
            actionable="Open the position while you're ahead in development.",
        ))
    elif opp_developed > user_developed + 1:
        features.append(PositionFeature(
            priority=5,
            category="development",
            title="Opponent has better development",
            description=f"They have {opp_developed} pieces out vs your {user_developed}. Catch up before they attack.",
            min_rating=800,
            actionable="Develop your remaining pieces. Don't start an attack yet.",
        ))

    # Space — count squares controlled in opponent's half
    user_space = 0
    opp_space = 0
    for sq in chess.SQUARES:
        rank = chess.square_rank(sq)
        if rank >= 4 and board.is_attacked_by(user_color, sq):
            user_space += 1
        if rank <= 3 and board.is_attacked_by(opp_color, sq):
            opp_space += 1

    if user_space > opp_space + 5:
        features.append(PositionFeature(
            priority=9,
            category="center",
            title="You have more space",
            description="Your pieces control more of the board. This means better mobility.",
            min_rating=1000,
            actionable="Use your space — maneuver pieces to their best squares.",
        ))
    elif opp_space > user_space + 5:
        features.append(PositionFeature(
            priority=7,
            category="center",
            title="Opponent has more space",
            description="They control more squares. Your pieces feel cramped.",
            min_rating=1000,
            actionable="Look for a pawn break (c5, d5, e5, f5) to challenge their space.",
        ))

    # If nothing else — piece count summary
    if not features:
        total_pieces = len(board.piece_map())
        if total_pieces <= 12:
            features.append(PositionFeature(
                priority=10,
                category="piece_activity",
                title="Endgame approaching",
                description="Few pieces left. King activity and pawn promotion are key now.",
                min_rating=800,
                actionable="Activate your king! In endgames, the king is a fighting piece.",
            ))
        else:
            features.append(PositionFeature(
                priority=10,
                category="piece_activity",
                title="Position is balanced",
                description="No immediate threats or imbalances. Look for ways to improve your worst piece.",
                min_rating=800,
                actionable="Find your least active piece and give it a better job.",
            ))

    return features


def _analyze_forks(board, user_color, opp_color) -> List[PositionFeature]:
    """Detect existing forks — pieces attacking 2+ valuable targets."""
    features = []

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece:
            continue
        if piece.piece_type not in (chess.KNIGHT, chess.QUEEN, chess.PAWN):
            continue

        attacks = board.attacks(sq)
        targets = []
        target_color = opp_color if piece.color == user_color else user_color

        for target_sq in attacks:
            target = board.piece_at(target_sq)
            if target and target.color == target_color and target.piece_type not in (chess.PAWN,):
                targets.append((target, target_sq))

        if len(targets) >= 2:
            piece_name = chess.piece_name(piece.piece_type)
            target_names = " and ".join(
                f"{chess.piece_name(t.piece_type)} on {chess.square_name(s)}"
                for t, s in targets[:2]
            )
            is_ours = piece.color == user_color

            if is_ours:
                features.append(PositionFeature(
                    priority=2,
                    category="tactics",
                    title=f"Your {piece_name} forks two pieces",
                    description=f"Your {piece_name} on {chess.square_name(sq)} attacks their {target_names}.",
                    min_rating=600,
                    actionable="You're attacking two pieces at once — one of them is likely lost.",
                ))
            else:
                features.append(PositionFeature(
                    priority=1,
                    category="tactics",
                    title=f"Opponent's {piece_name} forks your pieces",
                    description=f"Their {piece_name} on {chess.square_name(sq)} attacks your {target_names}.",
                    min_rating=600,
                    actionable="You need to address this fork — save the more valuable piece.",
                ))
            break  # One fork is enough

    return features


def _analyze_our_pins(board, user_color, opp_color) -> List[PositionFeature]:
    """Detect if our pieces are pinned."""
    features = []

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type != chess.KING:
            if board.is_pinned(user_color, sq):
                piece_name = chess.piece_name(piece.piece_type)
                sq_name = chess.square_name(sq)

                # Find what's pinning
                pinner_name = "a piece"
                for att_sq in board.attackers(opp_color, sq):
                    att = board.piece_at(att_sq)
                    if att and att.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
                        pinner_name = f"their {chess.piece_name(att.piece_type)} on {chess.square_name(att_sq)}"
                        break

                features.append(PositionFeature(
                    priority=3,
                    category="tactics",
                    title=f"Your {piece_name} is pinned",
                    description=f"Your {piece_name} on {sq_name} is pinned by {pinner_name}. It can't move without exposing your king or queen.",
                    min_rating=600,
                    actionable=f"Consider breaking the pin — move your king, block the pin line, or challenge the pinner.",
                ))
                break  # One is enough

    return features
