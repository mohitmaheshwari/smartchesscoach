"""Generalised own-side alignment shape. No files, no colours, no pieces hard-coded."""
import chess
VAL = {chess.PAWN:100, chess.KNIGHT:300, chess.BISHOP:320, chess.ROOK:500,
       chess.QUEEN:900, chess.KING:10000}
ORTH = [(1,0),(-1,0),(0,1),(0,-1)]
DIAG = [(1,1),(1,-1),(-1,1),(-1,-1)]

def _ray(frm, d):
    f, r = chess.square_file(frm), chess.square_rank(frm)
    out = []
    while True:
        f += d[0]; r += d[1]
        if not (0 <= f < 8 and 0 <= r < 8): break
        out.append(chess.square(f, r))
    return out

def _dirs_for(pt):
    if pt == chess.ROOK: return ORTH
    if pt == chess.BISHOP: return DIAG
    if pt == chess.QUEEN: return ORTH + DIAG
    return []

def is_passed(board, sq, color):
    """pawn with no enemy pawn on its file or the two adjacent files, ahead of it"""
    if board.piece_type_at(sq) != chess.PAWN: return False
    f, r = chess.square_file(sq), chess.square_rank(sq)
    for ef in range(max(0, f-1), min(8, f+2)):
        for er in range(8):
            ahead = er > r if color == chess.WHITE else er < r
            if not ahead: continue
            p = board.piece_at(chess.square(ef, er))
            if p and p.piece_type == chess.PAWN and p.color != color:
                return False
    return True

def find_alignments(board, color):
    """Own (front, rear) pairs on one line that an ENEMY slider can enter in one move.
    color = the side we are coaching."""
    enemy = not color
    hits = []
    probe = board.copy(stack=False); probe.turn = enemy
    for mv in probe.pseudo_legal_moves:
        piece = probe.piece_at(mv.from_square)
        if piece is None or piece.color != enemy: continue
        dirs = _dirs_for(piece.piece_type)
        if not dirs: continue
        entry = mv.to_square
        # the slider must survive landing there
        after = probe.copy(stack=False); after.push(mv)
        if after.is_attacked_by(color, entry):
            defenders = after.attackers(color, entry)
            # landing into a cheaper capture is not a threat
            if any(VAL.get(after.piece_type_at(s), 0) <= VAL[piece.piece_type] for s in defenders):
                continue
        for d in dirs:
            seen = []
            for sq in _ray(entry, d):
                p = after.piece_at(sq)
                if p is None: continue
                seen.append((sq, p))
                if len(seen) == 2: break
            if len(seen) != 2: continue
            (fs, fp), (rs, rp) = seen
            if fp.color != color or rp.color != color: continue
            if VAL.get(rp.piece_type, 0) < 100: continue
            front_undefended = not after.attackers(color, fs)
            front_worth_more = VAL.get(fp.piece_type,0) > VAL.get(rp.piece_type,0)
            if not (front_undefended or front_worth_more): continue
            hits.append({
                "slider": piece.symbol(), "slider_from": chess.square_name(mv.from_square),
                "entry": chess.square_name(entry),
                "front": fp.symbol(), "front_sq": chess.square_name(fs),
                "rear": rp.symbol(), "rear_sq": chess.square_name(rs),
                "front_undefended": front_undefended,
                "front_worth_more": front_worth_more,
                "rear_is_passed_pawn": is_passed(board, rs, color),
                "rear_value": VAL.get(rp.piece_type, 0),
            })
    # de-dup on the (entry, front, rear) triple
    seen_k, out = set(), []
    for h in hits:
        k = (h["entry"], h["front_sq"], h["rear_sq"])
        if k in seen_k: continue
        seen_k.add(k); out.append(h)
    return out

def best_move_addresses(board, color, hit, best_san):
    """Counterfactual: does the engine's best move actually deal with this shape?"""
    try:
        mv = board.parse_san(best_san)
    except Exception:
        return None
    b = board.copy(stack=False); b.push(mv)
    entry = chess.parse_square(hit["entry"])
    front = chess.parse_square(hit["front_sq"])
    rear = chess.parse_square(hit["rear_sq"])
    reasons = []
    if b.attackers(color, entry): reasons.append("guards entry square")
    if b.piece_at(front) and b.attackers(color, front): reasons.append("defends front piece")
    if mv.from_square == front: reasons.append("moves front piece away")
    if mv.from_square == rear: reasons.append("moves rear unit away")
    # did the shape survive at all?
    still = any(h["entry"] == hit["entry"] and h["front_sq"] == hit["front_sq"]
                and h["rear_sq"] == hit["rear_sq"] for h in find_alignments(b, color))
    if not still and not reasons: reasons.append("shape gone")
    return {"addressed": bool(reasons) or not still, "how": reasons, "shape_survives": still}
