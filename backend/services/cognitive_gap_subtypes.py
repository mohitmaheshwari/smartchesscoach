"""
Cognitive-gap subtype classifiers — board-verified for all 8 remaining
cognitive_gap tags (piece_safety lives in move_observation_deriver.py
for historical reasons; may consolidate later).

Every classifier:
  - Takes the same signature: (mv, opponent_previous, opp_next, board_context)
  - Returns (subtype_str, severity_str) or (None, None) if the event
    doesn't cleanly match any subtype (falls back to a generic label)
  - Uses python-chess to VERIFY, not upstream analyzer flags
  - Never trusts cct_is_capture / cct_forcing (SAN 'x' / '+' / '#' instead)

See docs/all_cognitive_gap_subtypes_scope.md for taxonomy + severity rules.
"""
from typing import Any, Dict, Optional, Tuple

import chess


_PIECE_VALUES = {"p": 100, "n": 300, "b": 300, "r": 500, "q": 900, "k": 0}
_SEVERITY_LEVELS = ["minor", "moderate", "critical"]


def _san_forcing(san: str) -> bool:
    """SAN indicates the move is forcing (capture, check, mate)."""
    if not isinstance(san, str):
        return False
    return "x" in san or san.endswith("+") or san.endswith("#")


def _promote_severity(base: str, mv: Dict[str, Any]) -> str:
    """Same promotion rules as piece_safety: blunder | material-loss | high-cp-not-hopeless."""
    idx = _SEVERITY_LEVELS.index(base) if base in _SEVERITY_LEVELS else 0
    cp = mv.get("cp_loss") or 0
    eb = mv.get("eval_before") or 0
    promote = False
    if mv.get("evaluation") == "blunder":
        promote = True
    elif cp >= 400 and eb >= -300:
        promote = True
    if promote:
        idx = min(idx + 1, len(_SEVERITY_LEVELS) - 1)
    return _SEVERITY_LEVELS[idx]


def _piece_moved(fen: str, uci: str) -> Optional[chess.Piece]:
    if not fen or not uci or len(uci) < 4:
        return None
    try:
        return chess.Board(fen).piece_at(chess.Move.from_uci(uci).from_square)
    except Exception:
        return None


def _board_after(fen: str, uci: str) -> Optional[chess.Board]:
    if not fen or not uci or len(uci) < 4:
        return None
    try:
        b = chess.Board(fen)
        b.push(chess.Move.from_uci(uci))
        return b
    except Exception:
        return None


# ─── KING_SAFETY ──────────────────────────────────────────────────────
# 2026-07-02 v2: tightened after Mohit found the classifier over-fires on
# already-lost positions and endgame king walks. Now:
#   - Skip events where eval_before < -300 (already hopeless — noise, not signal)
#   - Endgame king moves are NOT king_safety events (see should_reroute_king_safety_to_endgame)


def _is_endgame_board(board: chess.Board) -> bool:
    """Heuristic: no queens on board AND ≤4 non-king/pawn pieces per side."""
    piece_map = board.piece_map()
    if any(p.piece_type == chess.QUEEN for p in piece_map.values()):
        return False
    n_w = sum(1 for p in piece_map.values() if p.color == chess.WHITE and p.piece_type not in (chess.PAWN, chess.KING))
    n_b = sum(1 for p in piece_map.values() if p.color == chess.BLACK and p.piece_type not in (chess.PAWN, chess.KING))
    return n_w <= 3 and n_b <= 3


def should_reroute_king_safety_to_endgame(mv) -> bool:
    """Return True if this event was tagged king_safety but is actually an
    endgame king move (should be classified under endgame_technique instead).

    Called by the deriver before classify_king_safety(), to reclassify
    the missed_pattern itself."""
    fen = mv.get("fen_before")
    uci = mv.get("move_uci")
    if not fen or not uci:
        return False
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        piece_moved = board.piece_at(move.from_square)
        if piece_moved is None or piece_moved.piece_type != chess.KING:
            return False
        return _is_endgame_board(board)
    except Exception:
        return False


def classify_king_safety(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    fen = mv.get("fen_before")
    uci = mv.get("move_uci")
    san = mv.get("move") or ""
    if not fen or not uci:
        return (None, None)
    try:
        board = chess.Board(fen)
    except Exception:
        return (None, None)

    # ── Gate: skip already-hopeless positions (eval_before < -300).
    # A "king safety mistake" when you were already down a queen is not
    # a coaching moment. This is noise, not signal.
    eval_before = mv.get("eval_before")
    if eval_before is not None and eval_before < -300:
        return (None, None)

    move = chess.Move.from_uci(uci)
    piece_moved = board.piece_at(move.from_square)
    move_number = mv.get("move_number") or 0
    is_white = board.turn == chess.WHITE
    in_endgame = _is_endgame_board(board)

    # ── king_walked_into_attack — user king moved to a square with attackers > defenders.
    # ONLY in middlegame — in endgame this is endgame technique (should have been
    # rerouted before this call, but belt-and-suspenders here).
    if piece_moved and piece_moved.piece_type == chess.KING and not in_endgame:
        board.push(move)
        opp_col = board.turn
        n_att = len(list(board.attackers(opp_col, move.to_square)))
        n_def = len(list(board.attackers(not opp_col, move.to_square)))
        if n_att > n_def:
            return ("king_walked_into_attack", _promote_severity("critical", mv))
        # Reset board for further classifiers below
        board.pop()

    # ── ignored_king_attack — opp has SIGNIFICANT presence near user king
    # (3+ squares in the king ring are attacked by opp), user didn't
    # defend, and it's the middlegame. Middlegames naturally have some
    # opp pieces attacking near-king squares — requiring 3+ concentration
    # of attackers distinguishes REAL king-safety pressure from ambient
    # middlegame activity.
    king_sq = board.king(board.turn)
    if not in_endgame and king_sq is not None:
        opp_col = not board.turn
        n_attacked_squares_near_king = 0
        for sq in chess.SQUARES:
            if chess.square_distance(sq, king_sq) <= 2:
                if board.attackers(opp_col, sq):
                    n_attacked_squares_near_king += 1
        if (n_attacked_squares_near_king >= 3
                and not _san_forcing(san)
                and (mv.get("cp_loss") or 0) >= 150):
            return ("ignored_king_attack", _promote_severity("critical", mv))

    # ── king_in_center — king still on starting square past move 12
    if move_number > 12 and king_sq is not None and not in_endgame:
        home_king = chess.E1 if is_white else chess.E8
        if king_sq == home_king:
            central_pieces = sum(1 for sq in [chess.D4, chess.E4, chess.D5, chess.E5]
                                 if board.piece_at(sq))
            if central_pieces >= 2:
                return ("king_in_center", _promote_severity("moderate", mv))

    # ── weakened_shelter — flank pawn moved near king, and opp has
    # attackers close to the king (not just anywhere on the flank).
    # 2026-07-04: tightened to require attackers WITHIN 2 squares of king
    # (was "anywhere on the flank") — matches ignored_king_attack rule.
    if piece_moved and piece_moved.piece_type == chess.PAWN and king_sq is not None and not in_endgame:
        from_file = chess.square_file(move.from_square)
        king_file = chess.square_file(king_sq)
        if abs(from_file - king_file) <= 2 and from_file in (5, 6, 7, 0, 1, 2):
            opp_col = not board.turn
            n_attacked_near_king = 0
            for sq in chess.SQUARES:
                if chess.square_distance(sq, king_sq) <= 2:
                    if board.attackers(opp_col, sq):
                        n_attacked_near_king += 1
            if n_attacked_near_king >= 2 and (mv.get("cp_loss") or 0) >= 100:
                return ("weakened_shelter", _promote_severity("moderate", mv))

    return (None, None)


# ─── MISSED_TACTIC ────────────────────────────────────────────────────

def _best_move_uci(mv: Dict[str, Any]) -> Optional[str]:
    """Try to find the engine's best move UCI from various stored fields."""
    for key in ("best_move_uci", "best_move", "pv_best_uci"):
        v = mv.get(key)
        if isinstance(v, str) and len(v) >= 4 and v[0].isalpha() and v[1].isdigit():
            return v
    pv = mv.get("pv") or mv.get("best_line") or []
    if isinstance(pv, list) and pv:
        first = pv[0]
        if isinstance(first, str) and len(first) >= 4:
            return first
    return None


def _detect_tactic_on_move(board: chess.Board, move_uci: str) -> Optional[str]:
    """After this move is played on `board`, what tactic (if any) does it create?
    Returns 'fork', 'pin', 'skewer', 'discovered_attack', or None."""
    try:
        board = board.copy()
        move = chess.Move.from_uci(move_uci)
        piece = board.piece_at(move.from_square)
        board.push(move)
        if piece is None:
            return None

        opp_col = not (not board.turn)  # piece's color = mover's original turn
        # After push, board.turn = opponent. The moved piece belongs to (not board.turn).
        moved_color = not board.turn

        # ── FORK — moved piece attacks ≥2 opp pieces of value ≥300
        attacked_valuable = []
        for sq in board.attacks(move.to_square):
            p = board.piece_at(sq)
            if p and p.color != moved_color and _PIECE_VALUES.get(p.symbol().lower(), 0) >= 300:
                attacked_valuable.append(sq)
        if len(attacked_valuable) >= 2:
            return "fork"

        # ── PIN — moved piece pins an opp piece to a more valuable one behind it
        # Check ray attacks from moved piece
        piece_type = piece.piece_type
        if piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            # For each opp piece attacked, check if there's a more valuable piece behind
            for direction in _sliding_directions(piece_type):
                pin_result = _check_line_pin_or_skewer(
                    board, move.to_square, direction, moved_color
                )
                if pin_result == "pin":
                    return "pin"
                if pin_result == "skewer":
                    return "skewer"

        # ── DISCOVERED_ATTACK — a piece other than the one that moved now attacks
        # a valuable opp piece. Check: any friendly slider whose line to opp piece
        # was previously blocked by the moved piece.
        for from_sq in [s for s in chess.SQUARES if board.piece_at(s) and
                        board.piece_at(s).color == moved_color and s != move.to_square]:
            attacker = board.piece_at(from_sq)
            if attacker.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
                for tgt in board.attacks(from_sq):
                    tgt_p = board.piece_at(tgt)
                    if (tgt_p and tgt_p.color != moved_color
                        and _PIECE_VALUES.get(tgt_p.symbol().lower(), 0) >= 300):
                        # Was this line previously blocked by the moved piece?
                        if _squares_between_contains(from_sq, tgt, move.from_square):
                            return "discovered_attack"
        return None
    except Exception:
        return None


def _sliding_directions(piece_type):
    if piece_type == chess.BISHOP:
        return [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    if piece_type == chess.ROOK:
        return [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if piece_type == chess.QUEEN:
        return [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    return []


def _check_line_pin_or_skewer(board, from_sq, direction, mover_color):
    """Along `direction` from `from_sq`, find first opp piece; if a MORE valuable
    opp piece is next in line → pin. If LESS valuable → skewer."""
    df, dr = direction
    f = chess.square_file(from_sq) + df
    r = chess.square_rank(from_sq) + dr
    first_piece = None
    first_val = 0
    while 0 <= f < 8 and 0 <= r < 8:
        sq = chess.square(f, r)
        p = board.piece_at(sq)
        if p:
            v = _PIECE_VALUES.get(p.symbol().lower(), 0)
            if p.color == mover_color:
                return None  # blocked
            if first_piece is None:
                first_piece = p
                first_val = v
            else:
                # Second opp piece found
                second_val = v
                if second_val > first_val:
                    return "pin"
                if second_val < first_val:
                    return "skewer"
                return None
        f += df
        r += dr
    return None


def _squares_between_contains(a, b, c):
    """Is square c on the line between a and b (exclusive)?"""
    try:
        between = list(chess.SquareSet(chess.between(a, b)))
        return c in between
    except Exception:
        return False


def classify_missed_tactic(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    fen = mv.get("fen_before")
    best = _best_move_uci(mv)
    if not fen or not best:
        return (None, None)
    try:
        board = chess.Board(fen)
        tactic = _detect_tactic_on_move(board, best)
    except Exception:
        return (None, None)
    if tactic == "fork":
        return ("missed_fork", _promote_severity("critical", mv))
    if tactic == "pin":
        return ("missed_pin", _promote_severity("moderate", mv))
    if tactic == "skewer":
        return ("missed_skewer", _promote_severity("critical", mv))
    if tactic == "discovered_attack":
        return ("missed_discovered_attack", _promote_severity("critical", mv))
    # Generic tactic — engine best gives ≥200cp advantage but doesn't fit
    if (mv.get("cp_loss") or 0) >= 200:
        return ("missed_generic_tactic", _promote_severity("moderate", mv))
    return (None, None)


# ─── TACTICAL_OVERSIGHT ───────────────────────────────────────────────

def classify_tactical_oversight(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    san = mv.get("move") or ""
    cp = mv.get("cp_loss") or 0

    # ── ignored_forcing_threat — opp's previous was a capture or check, user didn't address
    if opponent_previous:
        prev_san = opponent_previous.get("move_san") or ""
        if _san_forcing(prev_san) and cp >= 150 and not _san_forcing(san):
            return ("ignored_forcing_threat", _promote_severity("critical", mv))

    # ── overlooked_immediate_reply — opp's next move captures/checks for cp gain
    if opp_next:
        next_san = opp_next.get("move") or ""
        if _san_forcing(next_san):
            # Opp's cp_loss for their move being NEGATIVE means they gained material
            opp_cp_loss = opp_next.get("cp_loss") or 0
            eval_after_user = mv.get("eval_after")
            eval_after_opp = opp_next.get("eval_after")
            if (eval_after_user is not None and eval_after_opp is not None
                and (eval_after_user - eval_after_opp) >= 300):
                return ("overlooked_immediate_reply", _promote_severity("critical", mv))
            if cp >= 200 and "x" in next_san:
                return ("overlooked_immediate_reply", _promote_severity("moderate", mv))

    if cp >= 200:
        return ("generic_oversight", _promote_severity("moderate", mv))
    return (None, None)


# ─── CALCULATION_DEPTH ────────────────────────────────────────────────

def classify_calculation_depth(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    cp = mv.get("cp_loss") or 0
    san = mv.get("move") or ""

    # ── 2ply_forcing_win — opp's next move is forcing AND wins material
    if opp_next:
        next_san = opp_next.get("move") or ""
        if _san_forcing(next_san) and cp >= 300:
            return ("shallow_horizon_2ply", _promote_severity("critical", mv))

    # ── broken_forcing_sequence — user's move was in a forcing sequence they started
    if _san_forcing(san) and cp >= 200:
        # And the previous move by user (their previous forcing move) started a sequence
        # Simplified: if this user move IS forcing and cp_loss high, they broke it
        return ("broken_forcing_sequence", _promote_severity("moderate", mv))

    if cp >= 150:
        return ("generic_calc_gap", _promote_severity("moderate", mv))
    return (None, None)


# ─── PIECE_ACTIVITY ───────────────────────────────────────────────────

def classify_piece_activity(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    fen = mv.get("fen_before")
    uci = mv.get("move_uci")
    move_number = mv.get("move_number") or 0

    if not fen or not uci:
        return (None, None)
    try:
        board = chess.Board(fen)
    except Exception:
        return (None, None)
    move = chess.Move.from_uci(uci)
    piece = board.piece_at(move.from_square)
    if piece is None:
        return (None, None)
    is_white = piece.color == chess.WHITE

    # ── queen_out_early — queen moved before move 8 while other pieces are home
    if piece.piece_type == chess.QUEEN and move_number <= 8:
        home_rank = 0 if is_white else 7
        starting_pieces_home = 0
        for f in [1, 2, 5, 6]:  # b, c, f, g (knights + bishops home squares)
            sq = chess.square(f, home_rank)
            p = board.piece_at(sq)
            if p and p.color == piece.color and p.piece_type in (chess.KNIGHT, chess.BISHOP):
                starting_pieces_home += 1
        if starting_pieces_home >= 3 and (mv.get("cp_loss") or 0) >= 100:
            return ("queen_out_early", _promote_severity("moderate", mv))

    # ── piece_parked_on_start — a knight/bishop/rook has been on its starting square
    # for ≥move 12, and user didn't develop it now (moved something else)
    if move_number >= 12 and piece.piece_type not in (chess.KNIGHT, chess.BISHOP):
        home_rank = 0 if is_white else 7
        parked = []
        for f in [1, 6]:  # knight starting files
            sq = chess.square(f, home_rank)
            p = board.piece_at(sq)
            if p and p.color == piece.color and p.piece_type == chess.KNIGHT:
                parked.append(("knight", sq))
        for f in [2, 5]:  # bishop starting files
            sq = chess.square(f, home_rank)
            p = board.piece_at(sq)
            if p and p.color == piece.color and p.piece_type == chess.BISHOP:
                parked.append(("bishop", sq))
        if parked and (mv.get("cp_loss") or 0) >= 100:
            return ("piece_parked_on_start", _promote_severity("moderate", mv))

    # Ship as unverified_hint for the residue
    if (mv.get("cp_loss") or 0) >= 150:
        return ("unverified_hint", _promote_severity("minor", mv))
    return (None, None)


# ─── OPENING_KNOWLEDGE ────────────────────────────────────────────────

def classify_opening_knowledge(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    fen = mv.get("fen_before")
    uci = mv.get("move_uci")
    move_number = mv.get("move_number") or 0
    san = mv.get("move") or ""

    if move_number > 12:
        return (None, None)  # not really opening any more
    if not fen or not uci:
        return (None, None)
    try:
        board = chess.Board(fen)
    except Exception:
        return (None, None)
    move = chess.Move.from_uci(uci)
    piece = board.piece_at(move.from_square)
    if piece is None:
        return (None, None)

    from_file = chess.square_file(move.from_square)
    to_file = chess.square_file(move.to_square)
    from_rank = chess.square_rank(move.from_square)
    to_rank = chess.square_rank(move.to_square)

    # ── early_flank_pawn_move — moving f/g/h/a/b/c pawn 2 squares in first 8 moves
    if (piece.piece_type == chess.PAWN and move_number <= 8
        and from_file in (0, 1, 2, 5, 6, 7)
        and abs(from_rank - to_rank) == 2
        and (mv.get("cp_loss") or 0) >= 100):
        return ("early_flank_pawn_move", _promote_severity("moderate", mv))

    # ── tempo_wasted_by_repeat — same piece moved twice in opening without capture
    # Approximation: user's move is a non-capture piece move and this piece has
    # already been moved (dest not on starting square = piece has moved before)
    # We can't easily know from FEN alone if this specific piece moved before, but:
    # If it's a piece move (not a pawn) and destination is close to start (near retreat),
    # and no capture → tempo waste heuristic.
    if (piece.piece_type in (chess.KNIGHT, chess.BISHOP) and move_number <= 10
        and "x" not in san):
        home_rank = 0 if piece.color == chess.WHITE else 7
        # If retreating toward home rank
        if piece.color == chess.WHITE and to_rank < from_rank:
            if (mv.get("cp_loss") or 0) >= 100:
                return ("tempo_wasted_by_repeat", _promote_severity("moderate", mv))
        if piece.color == chess.BLACK and to_rank > from_rank:
            if (mv.get("cp_loss") or 0) >= 100:
                return ("tempo_wasted_by_repeat", _promote_severity("moderate", mv))

    # ── theory_deviation_early — punt, would need opening_book service
    # For v1 ship as unverified_hint
    if (mv.get("cp_loss") or 0) >= 150 and move_number <= 10:
        return ("unverified_hint", _promote_severity("minor", mv))
    return (None, None)


# ─── ENDGAME_TECHNIQUE ────────────────────────────────────────────────

def _is_endgame(board: chess.Board) -> bool:
    """Heuristic: no queens, ≤6 pieces per side (incl. king)."""
    piece_map = board.piece_map()
    has_queen = any(p.piece_type == chess.QUEEN for p in piece_map.values())
    n_white = sum(1 for p in piece_map.values() if p.color == chess.WHITE and p.piece_type != chess.PAWN)
    n_black = sum(1 for p in piece_map.values() if p.color == chess.BLACK and p.piece_type != chess.PAWN)
    return (not has_queen) and n_white <= 4 and n_black <= 4


def _distance_to_center(square: int) -> int:
    """King distance to nearest central square (d4/e4/d5/e5)."""
    return min(chess.square_distance(square, c) for c in [chess.D4, chess.E4, chess.D5, chess.E5])


def classify_endgame_technique(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    fen = mv.get("fen_before")
    if not fen:
        return (None, None)
    try:
        board = chess.Board(fen)
    except Exception:
        return (None, None)
    if not _is_endgame(board):
        return (None, None)

    user_king = board.king(board.turn)
    opp_king = board.king(not board.turn)
    if user_king is None or opp_king is None:
        return (None, None)

    # ── passive_king_in_endgame — user king further from center by ≥3 vs opp king
    u_dist = _distance_to_center(user_king)
    o_dist = _distance_to_center(opp_king)
    if u_dist - o_dist >= 3 and (mv.get("cp_loss") or 0) >= 100:
        return ("passive_king_in_endgame", _promote_severity("moderate", mv))

    # ── passed_pawn_ignored — opp has a passed pawn advancing and user's move didn't address
    opp_col = not board.turn
    for sq, p in board.piece_map().items():
        if p.color != opp_col or p.piece_type != chess.PAWN:
            continue
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        # Advanced past its 4th rank
        advanced = (r >= 4) if opp_col == chess.WHITE else (r <= 3)
        if not advanced:
            continue
        # Check if it's passed (no user pawns blocking)
        is_passed = True
        for check_f in (f - 1, f, f + 1):
            if check_f < 0 or check_f > 7:
                continue
            for check_r in range(8):
                cp2 = board.piece_at(chess.square(check_f, check_r))
                if cp2 and cp2.color == board.turn and cp2.piece_type == chess.PAWN:
                    if (opp_col == chess.WHITE and check_r > r) or \
                       (opp_col == chess.BLACK and check_r < r):
                        is_passed = False
                        break
        if is_passed and (mv.get("cp_loss") or 0) >= 150:
            return ("passed_pawn_ignored", _promote_severity("critical", mv))

    if (mv.get("cp_loss") or 0) >= 100:
        return ("generic_endgame_slip", _promote_severity("moderate", mv))
    return (None, None)


# ─── PAWN_STRUCTURE ───────────────────────────────────────────────────

def _pawn_files_by_color(board: chess.Board, color: chess.Color) -> Dict[int, int]:
    """Return {file: count} of user pawns per file."""
    out = {}
    for sq, p in board.piece_map().items():
        if p.color == color and p.piece_type == chess.PAWN:
            f = chess.square_file(sq)
            out[f] = out.get(f, 0) + 1
    return out


def _find_backward_pawns(board: chess.Board, color) -> set:
    """Set of squares carrying a backward pawn for `color` on this board.

    Definition (strict, per 2026-07-03 tightening):
      A pawn is backward iff ALL of:
        1. No friendly pawn on adjacent files at any rank ahead of it.
        2. The square directly in front of it is controlled by an enemy pawn
           on an adjacent file (i.e., its advance is punished).

    This excludes newly-pushed pawns that just happen to lead on their file.
    """
    backward = set()
    ahead_dir = 1 if color == chess.WHITE else -1
    for sq, p in board.piece_map().items():
        if p.color != color or p.piece_type != chess.PAWN:
            continue
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        # (1) no friendly pawn on adjacent files ahead
        friend_ahead = False
        for adj_f in (f - 1, f + 1):
            if 0 <= adj_f <= 7:
                for check_r in range(8):
                    if (check_r - r) * ahead_dir > 0:
                        cp = board.piece_at(chess.square(adj_f, check_r))
                        if cp and cp.color == color and cp.piece_type == chess.PAWN:
                            friend_ahead = True
                            break
                if friend_ahead:
                    break
        if friend_ahead:
            continue
        # (2) advance square is controlled by enemy pawn on an adjacent file
        block_r = r + ahead_dir
        if not (0 <= block_r <= 7):
            continue
        controlled = False
        for adj_f in (f - 1, f + 1):
            if 0 <= adj_f <= 7:
                controller = board.piece_at(chess.square(adj_f, block_r))
                if (controller and controller.color != color
                        and controller.piece_type == chess.PAWN):
                    controlled = True
                    break
        if controlled:
            backward.add(sq)
    return backward


def classify_pawn_structure(mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    fen = mv.get("fen_before")
    uci = mv.get("move_uci")
    if not fen or not uci:
        return (None, None)
    try:
        board_before = chess.Board(fen)
    except Exception:
        return (None, None)
    move = chess.Move.from_uci(uci)
    piece = board_before.piece_at(move.from_square)
    # Only relevant on pawn moves OR captures (which change structure)
    is_pawn_move = piece is not None and piece.piece_type == chess.PAWN
    is_capture = "x" in (mv.get("move") or "")
    if not (is_pawn_move or is_capture):
        return (None, None)

    board_after = board_before.copy()
    board_after.push(move)
    user_color = piece.color if piece else board_before.turn
    from_file = chess.square_file(move.from_square)
    to_file = chess.square_file(move.to_square)

    files_before = _pawn_files_by_color(board_before, user_color)
    files_after = _pawn_files_by_color(board_after, user_color)

    # ── isolated_pawn_created — after move, some user pawn has no friendly pawn on adjacent files
    for sq, p in board_after.piece_map().items():
        if p.color != user_color or p.piece_type != chess.PAWN:
            continue
        f = chess.square_file(sq)
        left = files_after.get(f - 1, 0) if f > 0 else 0
        right = files_after.get(f + 1, 0) if f < 7 else 0
        if left == 0 and right == 0:
            # Check if this pawn was previously not-isolated (structure change)
            was_left = files_before.get(f - 1, 0) if f > 0 else 0
            was_right = files_before.get(f + 1, 0) if f < 7 else 0
            was_isolated = (was_left == 0 and was_right == 0)
            if not was_isolated and (mv.get("cp_loss") or 0) >= 80:
                return ("isolated_pawn_created", _promote_severity("moderate", mv))

    # ── doubled_pawn_created — a file that was singly-populated becomes doubled after move
    for f in range(8):
        if files_after.get(f, 0) >= 2 and files_before.get(f, 0) < 2:
            if (mv.get("cp_loss") or 0) >= 60:
                return ("doubled_pawn_created", _promote_severity("moderate", mv))

    # ── backward_pawn_created — a NEW backward pawn appears that wasn't
    # backward before this move. Structural degradation of *other* pawns.
    #
    # Excludes the pushed-pawn itself: pushing a pawn INTO a backward
    # position is a strategic choice (space gain vs advance-controlled
    # cost), not a "you accidentally created a backward pawn" moment.
    before_bp = _find_backward_pawns(board_before, user_color)
    after_bp = _find_backward_pawns(board_after, user_color)
    new_bp = after_bp - before_bp
    # Exclude the just-moved pawn's destination from "new"
    if piece and piece.piece_type == chess.PAWN:
        new_bp.discard(move.to_square)
    if new_bp and (mv.get("cp_loss") or 0) >= 60:
        return ("backward_pawn_created", _promote_severity("moderate", mv))

    if (mv.get("cp_loss") or 0) >= 100:
        return ("generic_structure_slip", _promote_severity("minor", mv))
    return (None, None)


# ─── Registry / dispatcher ────────────────────────────────────────────

CLASSIFIER_REGISTRY = {
    "king_safety":        classify_king_safety,
    "missed_tactic":      classify_missed_tactic,
    "tactical_oversight": classify_tactical_oversight,
    "calculation_depth":  classify_calculation_depth,
    "piece_activity":     classify_piece_activity,
    "opening_knowledge":  classify_opening_knowledge,
    "endgame_technique":  classify_endgame_technique,
    "pawn_structure":     classify_pawn_structure,
}


def classify(missed_pattern: str, mv, opponent_previous, opp_next) -> Tuple[Optional[str], Optional[str]]:
    """Main entry point — dispatches to the right classifier."""
    fn = CLASSIFIER_REGISTRY.get(missed_pattern)
    if fn is None:
        return (None, None)
    return fn(mv, opponent_previous, opp_next)
