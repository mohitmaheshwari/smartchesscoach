"""Tempo: the move brings no piece out while the better move does.

Mohit, 2026-11-02, on 4...b6 in a Scandinavian (1.e4 d5 2.exd5 Qxd5 3.Nc3
Qe6+ 4.Be2 b6, about 70 cp against Nf6 or Qd6): "that defeats the purpose of
why. Why should have told what you told." What a coach says there:

    Your queen on e6 is standing on the square your e-pawn needs, so your f8
    bishop cannot move and you cannot castle. b6 does not change that. Qd6
    gets the queen out of the way; Nf6 brings a piece out.

Every clause is a board fact (docs/why_positional_families_scope.md has the
table). This module computes them and fires only when the difference between
the two moves IS that fact: the better move develops a piece, castles, frees a
stuck piece or steps out of a pawn's way, and the played move does none of
those. When both moves are quiet (best c6, played b6) the property is shared
and the family is silent, the rule the material families use for an exchange
both lines allow.

It runs last, only when every material family is silent, and only on an
inaccuracy or a mistake. The consequence (the queen is chased again) is read
off the two engine lines and said only when the played line has it and the
better move's line does not; the line here changes between depths (d4, Nb5
and d5 all appear), so the cause carries the sentence and the consequence is
optional.

Two things this is NOT: a "piece in front of a pawn" detector (Nf6 stands in
front of f7, Nc3 in front of c2; the predicate is the mover's queen or king on
the square a pawn needs to free a STUCK bishop), and a "chases" sentence on
its own (graded thin four times on the regression set).

The two cutoffs below are provisional until the fire-rate pass on Mohit's
recent games (scope, "Measurement before any threshold is locked").
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import chess

from services.stored_line_verifier import parse_legal_move
from .differential import PIECE_NAME, _VALUE

# The family needs a position still in development: at least this many of the
# mover's minor pieces on their home squares. Provisional.
MIN_UNDEVELOPED = 2
# Plies of each engine line read for forced retreats and the development count.
LINE_HORIZON = 8

_HOME = {
    chess.WHITE: {"knights": (chess.B1, chess.G1), "bishops": (chess.C1, chess.F1), "queen": chess.D1,
                  "castled": (chess.G1, chess.C1)},
    chess.BLACK: {"knights": (chess.B8, chess.G8), "bishops": (chess.C8, chess.F8), "queen": chess.D8,
                  "castled": (chess.G8, chess.C8)},
}


def _forward(square: int, color: chess.Color) -> int:
    return square + (8 if color == chess.WHITE else -8)


def _home_minors(board: chess.Board, color: chess.Color) -> List[int]:
    """Knights and bishops still on the square they started the game on."""
    home = _HOME[color]
    out = []
    for square, kind in [(s, chess.KNIGHT) for s in home["knights"]] + [(s, chess.BISHOP) for s in home["bishops"]]:
        piece = board.piece_at(square)
        if piece is not None and piece.color == color and piece.piece_type == kind:
            out.append(square)
    return out


def _can_move(board: chess.Board, square: int, color: chess.Color) -> bool:
    """Pseudo-legal on purpose: a pin or a check is a tactic, not development."""
    probe = board.copy(stack=False)
    probe.turn = color
    return any(True for _ in probe.generate_pseudo_legal_moves(chess.BB_SQUARES[square]))


def _freeing_paths(board: chess.Board, bishop_square: int, color: chess.Color) -> List[Dict[str, Any]]:
    """For a bishop at home: the pawns whose advance would free it, and what
    of the mover's own stands on the square each pawn needs."""
    out: List[Dict[str, Any]] = []
    file, rank = chess.square_file(bishop_square), chess.square_rank(bishop_square)
    pawn_rank = rank + (1 if color == chess.WHITE else -1)
    for df in (-1, 1):
        f = file + df
        if not 0 <= f <= 7:
            continue
        pawn_square = chess.square(f, pawn_rank)
        pawn = board.piece_at(pawn_square)
        if pawn is None or pawn.color != color or pawn.piece_type != chess.PAWN:
            continue
        front = _forward(pawn_square, color)
        standing = board.piece_at(front)
        blocker = None
        if standing is not None and standing.color == color and standing.piece_type != chess.PAWN:
            blocker = {"piece": PIECE_NAME[standing.piece_type], "square": chess.square_name(front)}
        out.append({"pawn": chess.square_name(pawn_square), "file": chess.FILE_NAMES[f],
                    "front": chess.square_name(front), "blocker": blocker})
    return out


def development_facts(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    """What is still at home, what cannot move, and what stands in its way."""
    home = _home_minors(board, color)
    stuck = [s for s in home if not _can_move(board, s, color)]
    bishops = _HOME[color]["bishops"]
    freeing = {chess.square_name(s): _freeing_paths(board, s, color) for s in stuck if s in bishops}
    probe = board.copy(stack=False)
    probe.turn = color
    castling_now = (not probe.is_check()) and any(probe.is_castling(m) for m in probe.legal_moves)
    queens = list(board.pieces(chess.QUEEN, color))
    king = board.king(color)
    return {
        "undeveloped": [chess.square_name(s) for s in home],
        "stuck": [chess.square_name(s) for s in stuck],
        "freeing": freeing,
        "can_castle": board.has_castling_rights(color),
        "castling_legal_now": castling_now,
        "castled": king in _HOME[color]["castled"] and not board.has_castling_rights(color),
        "queen_square": chess.square_name(queens[0]) if queens else None,
        "queen_out": bool(queens) and queens[0] != _HOME[color]["queen"],
    }


def move_effect(board: chess.Board, move: chess.Move) -> Dict[str, Any]:
    """What one move does for the mover's development: develops a minor
    piece, castles, frees a stuck piece, steps out of a pawn's way, or none."""
    color = board.turn
    before = development_facts(board, color)
    piece = board.piece_at(move.from_square)
    after_board = board.copy(stack=False)
    after_board.push(move)
    after = development_facts(after_board, color)
    from_name, to_name = chess.square_name(move.from_square), chess.square_name(move.to_square)
    kinds: List[str] = []
    out: Dict[str, Any] = {"kinds": kinds, "moved_piece": PIECE_NAME[piece.piece_type] if piece else None,
                           "from_home": False, "develops": None, "castles": False, "frees": None, "unblocks": None}
    if piece is not None and piece.piece_type == chess.QUEEN:
        out["from_home"] = move.from_square == _HOME[color]["queen"]
    if board.is_castling(move):
        kinds.append("castles")
        out["castles"] = True
    if (piece is not None and piece.piece_type in (chess.KNIGHT, chess.BISHOP)
            and from_name in before["undeveloped"] and to_name not in after["undeveloped"]):
        kinds.append("develops")
        out["develops"] = PIECE_NAME[piece.piece_type]
    freed = [s for s in before["stuck"] if s not in after["stuck"] and s != from_name]
    if freed:
        freed_piece = after_board.piece_at(chess.parse_square(freed[0]))
        kinds.append("frees")
        out["frees"] = {"piece": PIECE_NAME[freed_piece.piece_type], "square": freed[0]}
    for bishop_square, paths in before["freeing"].items():
        for path in paths:
            blocker = path["blocker"]
            if (blocker and blocker["square"] == from_name
                    and after_board.piece_at(chess.parse_square(path["front"])) is None):
                kinds.append("unblocks")
                out["unblocks"] = {"pawn": path["pawn"], "file": path["file"], "bishop_square": bishop_square}
                break
        if out["unblocks"]:
            break
    if not kinds:
        kinds.append("none")
    return out


def forced_retreats(root: chess.Board, line_san: Sequence[str], mover: chess.Color,
                    horizon: int = LINE_HORIZON) -> List[Dict[str, Any]]:
    """The mover's pieces that move away while attacked, along an engine line.

    `line_san` starts with the move being judged (ply 0), which is never a
    retreat. A move counts when the piece is attacked by something cheaper, or
    attacked and undefended, and the move is not a capture, a castling or a
    king move out of check. Pawns are not pieces here.
    """
    board = root.copy(stack=False)
    out: List[Dict[str, Any]] = []
    previous: Optional[str] = None
    for ply, san in enumerate(list(line_san)[:horizon]):
        move = parse_legal_move(board, san)
        if move is None:
            break
        if board.turn == mover and ply > 0 and not board.is_check():
            piece = board.piece_at(move.from_square)
            if (piece is not None and piece.piece_type not in (chess.PAWN, chess.KING)
                    and not board.is_capture(move) and not board.is_castling(move)):
                attackers = board.attackers(not mover, move.from_square)
                if attackers:
                    cheapest = min(_VALUE[board.piece_at(a).piece_type] for a in attackers)
                    defended = bool(board.attackers(mover, move.from_square))
                    if cheapest < _VALUE[piece.piece_type] or not defended:
                        out.append({"ply": ply, "san": board.san(move), "piece": PIECE_NAME[piece.piece_type],
                                    "from": chess.square_name(move.from_square), "chased_by": previous})
        previous = board.san(move)
        board.push(move)
    return out


def developed_at(root: chess.Board, line_san: Sequence[str], mover: chess.Color,
                 horizon: int = LINE_HORIZON) -> Dict[str, Any]:
    """Development count at the end of a line, recorded for the fire-rate pass."""
    board = root.copy(stack=False)
    plies = 0
    for san in list(line_san)[:horizon]:
        move = parse_legal_move(board, san)
        if move is None:
            break
        board.push(move)
        plies += 1
    facts = development_facts(board, mover)
    return {"plies": plies, "undeveloped": len(facts["undeveloped"]), "castled": facts["castled"]}


def _lead(played_san: str, effect: Dict[str, Any]) -> Dict[str, str]:
    """The first sentence, and the same fact as a fragment for the words model."""
    piece = effect["moved_piece"]
    if piece == "queen":
        fragment = "brings the queen out before the pieces" if effect["from_home"] else "moves the queen again"
    elif piece in ("knight", "bishop"):
        fragment = "moves a piece that is already out"
    else:
        fragment = "brings no piece out"
    sentence = f"{played_san} does not bring a piece out." if fragment == "brings no piece out" else f"{played_san} {fragment}."
    return {"sentence": sentence, "fragment": fragment}


def _better(alt_san: str, effect: Dict[str, Any], your: str,
            same_threat: Optional[Dict[str, str]] = None, their: str = "their") -> Dict[str, str]:
    if effect["frees"]:
        fragment = f"frees the {effect['frees']['piece']} on {effect['frees']['square']}"
    elif effect["unblocks"]:
        fragment = f"steps out of the {effect['unblocks']['file']}-pawn's way"
    elif effect["develops"]:
        fragment = f"brings the {effect['develops']} out"
    else:
        fragment = f"gets {your} king to safety"
    if same_threat:
        # Move-order: both moves hit the same piece, so the only difference is
        # which of the mover's pieces does the job (mohit_qc2: Qc2 and Bd3
        # both attack the knight on e4; Bd3 also develops).
        fragment = f"makes the same threat to {their} {same_threat['piece']} on {same_threat['square']} and {fragment}"
    return {"sentence": f"{alt_san} {fragment}.", "fragment": fragment}


def same_threat(root: chess.Board, played: chess.Move, alternative: chess.Move) -> Optional[Dict[str, str]]:
    """An enemy piece both moves attack directly, most valuable first, or None."""
    from .differential import reply_footprint
    a = reply_footprint(root, played, None)
    b = reply_footprint(root, alternative, None)
    shared = [k for k in a if k in b and k[0] == "attacks"]
    if not shared:
        return None
    by_name = {v: k for k, v in PIECE_NAME.items()}
    key = max(shared, key=lambda k: _VALUE[by_name[k[1]]])
    return {"piece": key[1], "square": key[2]}


def tempo_claim(root: chess.Board, played: chess.Move, alternative: chess.Move, *,
                played_line: Sequence[str], alt_line: Sequence[str], move_class: str,
                mover_is_user: bool) -> Dict[str, Any]:
    """The measurement for this family on one position, and the sentence when it fires.

    Always returns the measurement (`eligible`, `fires`, `why_not`, the facts
    and the line counts) so a run over many positions gives the fire-rate
    distribution the thresholds are read from.
    """
    mover = root.turn
    played_san, alt_san = root.san(played), root.san(alternative)
    facts_root = development_facts(root, mover)
    played_effect = move_effect(root, played)
    alt_effect = move_effect(root, alternative)
    out: Dict[str, Any] = {
        "eligible": False, "fires": False, "why_not": None,
        "root": facts_root, "played_effect": played_effect, "better_effect": alt_effect,
        "retreats_played": forced_retreats(root, played_line, mover),
        "retreats_better": forced_retreats(root, alt_line, mover),
        "developed_played": developed_at(root, played_line, mover),
        "developed_better": developed_at(root, alt_line, mover),
        "text": None, "facts": None, "consequence": None,
    }
    if move_class not in ("inaccuracy", "mistake"):
        out["why_not"] = "class"
        return out
    if len(facts_root["undeveloped"]) < MIN_UNDEVELOPED:
        out["why_not"] = "developed"
        return out
    out["eligible"] = True
    if played_effect["kinds"] != ["none"]:
        out["why_not"] = "played_develops"
        return out
    if alt_effect["kinds"] == ["none"]:
        out["why_not"] = "shared_quiet"
        return out
    out["fires"] = True

    from services.why_words import _RELATION, _owned
    your = "your" if mover_is_user else "their"
    you = "you" if mover_is_user else "they"
    owner = "your" if mover_is_user else "their"

    lead = _lead(played_san, played_effect)
    their = "their" if mover_is_user else "your"
    threat = same_threat(root, played, alternative)
    better = _better(alt_san, alt_effect, your, threat, their)
    out["same_threat"] = threat
    facts: Dict[str, Any] = {
        "relation": _RELATION["TEMPO"],
        "what_the_move_played_does": lead["fragment"],
        "what_the_better_move_does": better["fragment"],
    }
    if threat:
        facts["the_piece_both_moves_attack"] = f"{_owned('their' if mover_is_user else 'your', threat['piece'])} on {threat['square']}"

    cause: Optional[str] = None
    cannot_castle = facts_root["can_castle"] and not facts_root["castling_legal_now"]
    castle_tail = f" and {you} cannot castle" if cannot_castle else ""
    stuck_bishops = [s for s in facts_root["stuck"] if s in facts_root["freeing"]]
    if stuck_bishops:
        square = stuck_bishops[0]
        blocked = [p for p in facts_root["freeing"][square] if p["blocker"]]
        facts["the_piece_that_cannot_move"] = f"{_owned(owner, 'bishop')} on {square}"
        if blocked:
            path = blocked[0]
            blocker = path["blocker"]
            cause = (f"{your.capitalize()} {blocker['piece']} on {blocker['square']} is standing where {your} "
                     f"{path['file']}-pawn needs to go, so the bishop on {square} cannot move{castle_tail}.")
            facts["what_is_in_its_way"] = (f"{_owned(owner, blocker['piece'])} on {blocker['square']}, "
                                           f"the square the {path['file']}-pawn needs")
        else:
            cause = f"{your.capitalize()} bishop on {square} cannot move yet{castle_tail}."
    elif facts_root["stuck"]:
        square = facts_root["stuck"][0]
        piece = PIECE_NAME[root.piece_at(chess.parse_square(square)).piece_type]
        cause = f"{your.capitalize()} {piece} on {square} cannot move yet{castle_tail}."
        facts["the_piece_that_cannot_move"] = f"{_owned(owner, piece)} on {square}"
    if cannot_castle:
        facts["castling"] = f"{_owned(owner, 'king')} cannot castle yet"

    consequence_text: Optional[str] = None
    unshared = [r for r in out["retreats_played"]
                if not any(a["piece"] == r["piece"] for a in out["retreats_better"]) and r["chased_by"]]
    if unshared:
        r = unshared[0]
        again = " again" if (r["piece"] != "queen" or facts_root["queen_out"]) else ""
        consequence_text = f"After {played_san}, {r['chased_by']} makes {your} {r['piece']} move{again}."
        out["consequence"] = {"mechanism": "TEMPO", "direction": "missed", "agent_move": alt_san,
                              "chaser": r["chased_by"], "chased_piece": r["piece"], "chased_from": r["from"],
                              "ply": r["ply"], "victim_piece": None, "victim_square": None, "payoff_cp": None,
                              "text": consequence_text}
        facts["their_move_that_then_chases_a_piece"] = r["chased_by"]
        facts["the_piece_it_chases"] = _owned(owner, r["piece"])

    out["text"] = " ".join(s for s in (lead["sentence"], cause, better["sentence"], consequence_text) if s)
    out["facts"] = facts
    return out
