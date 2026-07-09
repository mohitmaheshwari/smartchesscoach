"""geometry_plans.py — the "living plan overlay" detector (Phase 1).

Given a position, return the top few PLANS for BOTH sides as verified arrows
+ zones, so the coach can draw "here's your plan, here's mine" on the board.
docs/coach_geometry_arrows_scope.md.

Design rules (non-negotiable, from the scope):
  - TRUTH: every claim is re-derived from the board here. A "pin" is a real
    python-chess pin; a "fork" really attacks 2+ targets; a loose target is
    really undefended. Latent lines (rook->king through pieces) are marked
    dashed and never called a pin.
  - DISTILL: rank by significance, cap the default view (~2 per side). "Show
    more" layering is Phase 2 — this returns the ranked list; the caller slices.
  - BOTH SIDES: you = green, coach = amber.

Output: list of plan dicts, each:
  { "kind", "side": "you"|"coach", "color": "green"|"amber",
    "style": "solid"|"dashed", "arrows": [(from_sq_name, to_sq_name), ...],
    "squares": [sq_name, ...], "text": "<one plain line>", "rank": int }
Squares are SAN names (e.g. "e4") so react-chessboard can render directly.
"""
from __future__ import annotations
from typing import Dict, List, Optional
import chess

VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
PN = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
_SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def _name(sq: int) -> str:
    return chess.square_name(sq)


def _defended_by(board: chess.Board, color: chess.Color, sq: int) -> bool:
    return board.is_attacked_by(color, sq)


def _find_pins(board: chess.Board, by: chess.Color) -> List[Dict]:
    """Enemy pieces absolutely pinned (to their king) by `by`'s sliders."""
    enemy = not by
    ksq = board.king(enemy)
    out: List[Dict] = []
    if ksq is None:
        return out
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not (p and p.color == enemy and p.piece_type != chess.KING):
            continue
        if not board.is_pinned(enemy, sq):
            continue
        # the pinner is the `by` slider on the pin ray beyond the pinned piece
        ray = board.pin(enemy, sq)  # SquareSet along the pin line
        pinner = next((s for s in ray if (q := board.piece_at(s)) and q.color == by and q.piece_type in _SLIDERS), None)
        if pinner is None:
            continue
        out.append({
            "kind": "pin", "pinner": pinner, "pinned": sq, "target": ksq,
            "sig": 90 + VAL[p.piece_type],
        })
    return out


def _find_forks(board: chess.Board, by: chess.Color) -> List[Dict]:
    """`by` pieces that attack 2+ enemy pieces worth pressuring (>= knight, or the king)."""
    enemy = not by
    out: List[Dict] = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not (p and p.color == by):
            continue
        targets = []
        for t in board.attacks(sq):
            q = board.piece_at(t)
            if q and q.color == enemy and (q.piece_type == chess.KING or VAL[q.piece_type] >= 3):
                # only count it if capturing/attacking isn't self-losing: the forking
                # piece isn't simply defended-away — keep Phase 1 simple: real attack.
                targets.append(t)
        if len(targets) >= 2:
            out.append({
                "kind": "fork", "forker": sq, "targets": targets,
                "sig": 80 + sum(VAL[board.piece_at(t).piece_type] for t in targets),
            })
    return out


def _find_loose_targets(board: chess.Board, by: chess.Color) -> List[Dict]:
    """Enemy pieces `by` attacks that are UNDEFENDED (a real, winnable target)."""
    enemy = not by
    out: List[Dict] = []
    for sq in chess.SQUARES:
        q = board.piece_at(sq)
        if not (q and q.color == enemy and q.piece_type != chess.KING):
            continue
        if board.is_attacked_by(by, sq) and not board.is_attacked_by(enemy, sq):
            attacker = next((s for s in chess.SQUARES
                             if (a := board.piece_at(s)) and a.color == by and sq in board.attacks(s)), None)
            out.append({
                "kind": "loose_target", "attacker": attacker, "target": sq,
                "sig": 60 + VAL[q.piece_type],
            })
    return out


def _find_open_file_rooks(board: chess.Board, by: chess.Color) -> List[Dict]:
    """`by` rooks/queens sitting on a fully-open file (no pawns) — control to seize."""
    out: List[Dict] = []
    enemy = not by
    eksq = board.king(enemy)
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not (p and p.color == by and p.piece_type in (chess.ROOK, chess.QUEEN)):
            continue
        f = chess.square_file(sq)
        pawns = any((pp := board.piece_at(chess.square(f, r))) and pp.piece_type == chess.PAWN
                    for r in range(8))
        if pawns:
            continue
        # arrow up the file toward the enemy back rank / king side
        far_rank = 7 if by == chess.WHITE else 0
        head = chess.square(f, far_rank)
        # Real control: the path from the rook to the head must be CLEAR of pieces
        # (an enemy piece AT the head is fine — that's the target). No blockers.
        between = chess.SquareSet.between(sq, head)
        if any(board.piece_at(s) for s in between):
            continue
        piece_word = "rook" if p.piece_type == chess.ROOK else "queen"
        sig = 55
        if eksq is not None and chess.square_file(eksq) == f:
            sig = 70  # open file pointing at the enemy king — big deal
        out.append({"kind": "open_file", "rook": sq, "head": head, "piece": piece_word, "sig": sig})
    return out


def _find_latent_xray(board: chess.Board, by: chess.Color) -> List[Dict]:
    """`by` slider shares a line with the enemy KING/QUEEN but pieces sit between —
    a latent line to watch (dashed). Never called a pin."""
    enemy = not by
    out: List[Dict] = []
    highs = [board.king(enemy)] + [s for s in chess.SQUARES
                                   if (q := board.piece_at(s)) and q.color == enemy and q.piece_type == chess.QUEEN]
    highs = [h for h in highs if h is not None]
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not (p and p.color == by and p.piece_type in _SLIDERS):
            continue
        for h in highs:
            between = chess.SquareSet.between(sq, h)
            if len(between) == 0:
                continue  # same line & adjacent => not latent (handled by pin/attack)
            # must actually be on a shared line the slider could travel (rook: file/rank; bishop: diag)
            if not _shares_slider_line(p.piece_type, sq, h):
                continue
            occ = [s for s in between if board.piece_at(s)]
            # Exactly ONE blocker = a genuinely loaded line (Mohit's rook->king
            # case). Two+ blockers is too latent to be worth an arrow.
            # Dedup vs pins: if the lone blocker is an enemy piece already pinned
            # (to its king), this line is a PIN, reported there — don't double it.
            if len(occ) == 1 and board.piece_at(occ[0]).color == enemy and board.is_pinned(enemy, occ[0]):
                continue
            if len(occ) == 1 and h not in board.attacks(sq):
                tq = board.piece_at(h)
                out.append({
                    "kind": "latent_xray", "slider": sq, "target": h,
                    "target_is_king": (tq and tq.piece_type == chess.KING),
                    "sig": 45,
                })
    return out


def _shares_slider_line(pt: int, a: int, b: int) -> bool:
    fa, ra = chess.square_file(a), chess.square_rank(a)
    fb, rb = chess.square_file(b), chess.square_rank(b)
    same_orthogonal = (fa == fb) or (ra == rb)
    same_diagonal = abs(fa - fb) == abs(ra - rb)
    if pt == chess.ROOK:
        return same_orthogonal
    if pt == chess.BISHOP:
        return same_diagonal
    if pt == chess.QUEEN:
        return same_orthogonal or same_diagonal
    return False


def _render(plan: Dict, board: chess.Board, side: str) -> Dict:
    color = "green" if side == "you" else "amber"
    who = "your" if side == "you" else "their"
    k = plan["kind"]
    if k == "pin":
        pc = PN[board.piece_at(plan["pinner"]).piece_type]
        pd = PN[board.piece_at(plan["pinned"]).piece_type]
        return {"kind": k, "side": side, "color": color, "style": "solid",
                "arrows": [(_name(plan["pinner"]), _name(plan["target"]))],
                "squares": [_name(plan["pinned"])],
                "text": (f"{who.capitalize()} {pc} pins the {pd} on {_name(plan['pinned'])} to the king."
                         if side == "you" else
                         f"Their {pc} pins your {pd} on {_name(plan['pinned'])} to your king — it can't move."),
                "rank": plan["sig"]}
    if k == "fork":
        fp = PN[board.piece_at(plan["forker"]).piece_type]
        tnames = ", ".join(_name(t) for t in plan["targets"])
        return {"kind": k, "side": side, "color": color, "style": "solid",
                "arrows": [(_name(plan["forker"]), _name(t)) for t in plan["targets"]],
                "squares": [_name(t) for t in plan["targets"]],
                "text": (f"{who.capitalize()} {fp} forks two things on {tnames}."
                         if side == "you" else
                         f"Their {fp} hits two of your pieces at once ({tnames}) — a fork."),
                "rank": plan["sig"]}
    if k == "loose_target":
        tq = PN[board.piece_at(plan["target"]).piece_type]
        arr = [(_name(plan["attacker"]), _name(plan["target"]))] if plan.get("attacker") is not None else []
        return {"kind": k, "side": side, "color": color, "style": "solid",
                "arrows": arr, "squares": [_name(plan["target"])],
                "text": (f"Their {tq} on {_name(plan['target'])} is loose — nothing defends it."
                         if side == "you" else
                         f"Your {tq} on {_name(plan['target'])} is hanging — defend it or move it."),
                "rank": plan["sig"]}
    if k == "open_file":
        f = chess.FILE_NAMES[chess.square_file(plan["rook"])]
        pw = plan.get("piece", "rook")
        return {"kind": k, "side": side, "color": color, "style": "solid",
                "arrows": [(_name(plan["rook"]), _name(plan["head"]))], "squares": [],
                "text": (f"The {f}-file is open — {who} {pw} owns it."
                         if side == "you" else
                         f"Their {pw} owns the open {f}-file — watch that line."),
                "rank": plan["sig"]}
    if k == "latent_xray":
        return {"kind": k, "side": side, "color": color, "style": "dashed",
                "arrows": [(_name(plan["slider"]), _name(plan["target"]))], "squares": [],
                "text": (f"Your piece and their {'king' if plan['target_is_king'] else 'queen'} share a line — "
                         f"a line to watch if the piece between it moves."
                         if side == "you" else
                         f"Their piece lines up on your {'king' if plan['target_is_king'] else 'queen'} through a blocker — a line to watch."),
                "rank": plan["sig"]}
    return {}


def find_plans(fen: str, user_color: str, per_side: int = 2) -> List[Dict]:
    """Top plans for BOTH sides, ranked, capped at `per_side` each (default view)."""
    try:
        board = chess.Board(fen)
    except Exception:
        return []
    me = chess.WHITE if str(user_color).lower().startswith("w") else chess.BLACK
    out: List[Dict] = []
    for color, side in ((me, "you"), (not me, "coach")):
        raw: List[Dict] = []
        raw += _find_pins(board, color)
        raw += _find_forks(board, color)
        raw += _find_loose_targets(board, color)
        raw += _find_open_file_rooks(board, color)
        raw += _find_latent_xray(board, color)
        raw.sort(key=lambda p: -p["sig"])
        rendered = [_render(p, board, side) for p in raw[:per_side]]
        out += [r for r in rendered if r]
    return out


if __name__ == "__main__":
    tests = [
        ("pin: white Bb5 pins Nc6 to Ke8", "r1bqkbnr/pppp1ppp/2n5/1B6/4P3/8/PPPP1PPP/RNBQK1NR b KQkq - 3 3", "black"),
        ("fork: white Nd5 hits c7 & e7 area", "r1bqk2r/ppp1nppp/2n5/3N4/1b2P3/8/PPP2PPP/R1BQKB1R w KQkq - 0 1", "white"),
        ("open file: white Re1 on open e-file", "r2qkb1r/ppp2ppp/2n5/3np3/8/2N5/PPPP1PPP/R1BQR1K1 w kq - 0 1", "white"),
        ("hanging: black Bb4 loose", "rnbqk1nr/pppp1ppp/8/4p3/1b2P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1", "white"),
    ]
    for label, fen, uc in tests:
        print(f"\n### {label}  (user={uc})")
        for p in find_plans(fen, uc, per_side=3):
            print(f"  [{p['side']:5}|{p['color']:5}|{p['style']:6}] {p['kind']:12} arrows={p['arrows']} -> {p['text']}")
