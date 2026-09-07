"""narrator_claim_verifier.py — verify a NARRATOR (LLM) caption's chess claims
against the board + stored engine line before it ships (2026-06-11).

Counterpart to caption_claim_verifier.py: that one checks the DETECTOR's
*structured* primary-reason claim; this one checks the narrator's free *text*
(the LLM can name a piece on the wrong square, say "no recapture" when there is
one, call a defended pawn "free", or claim a mate that isn't). Claude hallucinates
~10-15% even when fed engine truth — proven on this game (m14 "queen on b6 / no
recapture"; m9 v1 "knight on e6"). A narrator caption ships ONLY if it passes;
otherwise it is sent back for self-correction, and on a second failure it is HELD.

API:
    verify_caption(caption, facts) -> list[dict]   # deployed V1 behavior
    verify_caption(caption, facts, strict_v2=True) -> list[dict]
      facts needs: fen_before, played_san (=move_san), is_user_move,
                   best_move_san, pv_after_played
    Each violation: {"check": str, "detail": str}   # detail IS the board truth,
      suitable to feed straight back to the LLM as the correction.

V1 covers the deterministic, high-frequency classes we actually saw. Tactic-NAME
mislabels (e.g. "discovered attack" for a plain check) need per-tactic geometry
and are deferred (logged by the caller as residual). Adding a check = adding one
function — same growth model as caption_claim_verifier.
"""
import re
from typing import Any, Dict, List

import chess

_PIECE = {"knight": chess.KNIGHT, "bishop": chess.BISHOP, "rook": chess.ROOK,
          "queen": chess.QUEEN, "king": chess.KING, "pawn": chess.PAWN}
_PNAME = {v: k for k, v in _PIECE.items()}

_FREE_RX = re.compile(r"\b(free pawn|hanging|undefended|for free|wins? the pawn|"
                      r"win a free|free piece|grab the free)\b", re.I)
_NORECAP_RX = re.compile(r"\b(no recapture|can'?t (?:take|recapture)|"
                         r"loses? (?:the|that) pawn cleanly|without (?:a )?recapture|"
                         r"no way to recapture)\b", re.I)
_MATE_RX = re.compile(
    r"\b(checkmate|mate|mating|forced win|wins by force|winning by force)\b|#",
    re.I,
)
_MATE_DELIVERED_RX = re.compile(r"\bcheckmate\b|#", re.I)
_MATE_ALLOWED_RX = re.compile(
    r"\ballows? (?:mate|a forced win)\b|"
    r"\ballows?\s+\S+#|"
    r"\blets\b.*\bforced win\b|"
    r"\bleaves? (?:mate|a forced win|you a forced win)\b",
    re.I,
)
_MATE_MISSED_RX = re.compile(
    r"\bmiss(?:es|ed) (?:mate|a forced win|the finish)\b",
    re.I,
)
_MATE_ALREADY_RX = re.compile(
    r"\bcannot stop\b.*\b(?:mate|forced win)\b|"
    r"\balready forced\b|\balready on the board\b",
    re.I,
)
_MATE_PRESERVED_RX = re.compile(
    r"\bforces mate\b|\bwins by force\b|"
    r"\bopp(?:onent)? (?:threatens mate|is winning by force)\b",
    re.I,
)
_EXPLICIT_MATE_SAN_RX = re.compile(
    r"(?<!\w)(O-O(?:-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)#"
)

_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def _capture_square(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return move.to_square + (-8 if board.turn == chess.WHITE else 8)
    return move.to_square


def _replay_branch(
    facts: Dict[str, Any],
    *,
    first_key: str,
    continuation_key: str,
) -> tuple[chess.Board, list[Dict[str, Any]], bool]:
    """Legally replay one stored branch and record its capture ledger."""
    board = chess.Board(facts["fen_before"])
    entries: list[Dict[str, Any]] = []
    sans = [facts.get(first_key)] + list(facts.get(continuation_key) or [])
    for san in sans:
        if not san:
            continue
        try:
            move = board.parse_san(str(san))
        except Exception:
            return board, entries, False
        moving = board.piece_at(move.from_square)
        captured = (
            board.piece_at(_capture_square(board, move))
            if board.is_capture(move)
            else None
        )
        entries.append(
            {
                "san": str(san),
                "move": move,
                "mover": board.turn,
                "moving_piece": moving,
                "captured_piece": captured,
                "capture_square": _capture_square(board, move),
            }
        )
        board.push(move)
    return board, entries, True


def _capture_totals(
    entries: list[Dict[str, Any]], mover: chess.Color
) -> tuple[int, int]:
    """Return (mover material lost, opponent material lost)."""
    mover_lost = 0
    opponent_lost = 0
    for entry in entries:
        captured = entry.get("captured_piece")
        if captured is None:
            continue
        value = _VALUE.get(captured.piece_type, 0)
        if captured.color == mover:
            mover_lost += value
        else:
            opponent_lost += value
    return mover_lost, opponent_lost


_FORCING_RX = re.compile(r"\bforcing move\b|\bchecks? and forcing", re.I)


def _check_forcing_move(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _FORCING_RX.search(caption):
        return []
    try:
        board = chess.Board(facts["fen_before"])
        san = facts.get("best_move_san") or facts.get("move_san")
        move = board.parse_san(str(san))
        is_capture = board.is_capture(move)
        board.push(move)
        if not is_capture and not board.is_check():
            return [{
                "check": "forcing_move",
                "detail": f"calls {san} forcing, but it is neither a check nor a capture",
            }]
    except Exception:
        return [{"check": "forcing_move", "detail": "forcing claim could not be verified"}]
    return []


_OPENING_PRAISE_RX = re.compile(
    r"\bclassic development\b|\bprincipled move\b|\bmain[- ]line move\b|"
    r"\bgood development\b",
    re.I,
)


def _check_unsound_opening_praise(
    caption: str, facts: Dict[str, Any]
) -> List[Dict[str, str]]:
    if not _OPENING_PRAISE_RX.search(caption):
        return []
    try:
        board = chess.Board(facts["fen_before"])
        played = board.parse_san(str(facts.get("move_san") or ""))
        moved_piece = board.piece_at(played.from_square)
        moved_to = played.to_square
        board.push(played)
        reply_san = next(iter(facts.get("pv_after_played") or []), None)
        if not reply_san:
            return []
        reply = board.parse_san(str(reply_san))
        immediately_loses_moved_piece = (
            board.is_capture(reply)
            and _capture_square(board, reply) == moved_to
            and moved_piece is not None
            and moved_piece.piece_type != chess.PAWN
        )
        if (
            immediately_loses_moved_piece
            and int(facts.get("cp_loss") or 0) >= 100
            and facts.get("best_move_san") != facts.get("move_san")
        ):
            return [{
                "check": "unsound_opening_praise",
                "detail": f"praises {facts.get('move_san')} although {reply_san} immediately captures the moved piece",
            }]
    except Exception:
        return []
    return []


_SACRIFICE_RX = re.compile(
    r"\bsacrific(?:e|es|ing)\s+(?:your\s+)?(pawn|knight|bishop|rook|queen)\b",
    re.I,
)


def _check_false_sacrifice(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    match = _SACRIFICE_RX.search(caption)
    if not match:
        return []
    try:
        board = chess.Board(facts["fen_before"])
        move = board.parse_san(str(facts.get("best_move_san") or ""))
        piece = board.piece_at(move.from_square)
        if piece is None or _PNAME.get(piece.piece_type) != match.group(1).lower():
            return [{"check": "false_sacrifice", "detail": "the named sacrificed piece is not the best-move piece"}]
        tracked_square = move.to_square
        tracked_color = piece.color
        tracked_type = piece.piece_type
        board.push(move)

        # A legal immediate recapture is already sufficient, position-owned
        # proof that the moved piece is being sacrificed.  Older evidence
        # packets do not always carry ``pv_after_best``; treating an absent PV
        # as a *complete* line used to produce the opposite conclusion (that
        # the piece survived).  Only legal moves count here, so a pinned or
        # otherwise immobile attacker cannot manufacture sacrifice evidence.
        immediate_recapture = any(
            board.is_capture(reply)
            and _capture_square(board, reply) == tracked_square
            for reply in board.legal_moves
        )
        if immediate_recapture:
            return []

        continuation = list(facts.get("pv_after_best") or [])
        if not continuation:
            return [{
                "check": "false_sacrifice",
                "detail": "sacrifice claim has neither a legal immediate recapture nor a stored best line",
            }]
        alive = True
        for san in continuation:
            next_move = board.parse_san(str(san))
            capture_square = _capture_square(board, next_move)
            if board.is_capture(next_move) and capture_square == tracked_square:
                alive = False
            if next_move.from_square == tracked_square:
                moving = board.piece_at(next_move.from_square)
                if moving and moving.color == tracked_color and moving.piece_type == tracked_type:
                    tracked_square = next_move.to_square
            board.push(next_move)
        if alive and board.piece_at(tracked_square) == chess.Piece(tracked_type, tracked_color):
            return [{
                "check": "false_sacrifice",
                "detail": f"calls the {match.group(1).lower()} sacrificed, but it survives the complete stored best line",
            }]
    except Exception:
        return [{"check": "false_sacrifice", "detail": "sacrifice claim could not be verified"}]
    return []


_YOUR_PIECE_RX = re.compile(
    r"your\s+(pawn|knight|bishop|rook|queen)\s+on\s+([a-h][1-8])",
    re.I,
)
_LOSS_LANGUAGE_RX = re.compile(r"\bfor nothing\b|\blosing your\b|\bsimply lose\b", re.I)


def _check_exchange_sequence(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    named = _YOUR_PIECE_RX.search(caption)
    if not named or not _LOSS_LANGUAGE_RX.search(caption):
        return []
    try:
        start = chess.Board(facts["fen_before"])
        mover = start.turn
        _, entries, complete = _replay_branch(
            facts, first_key="move_san", continuation_key="pv_after_played"
        )
        if not complete:
            return [{"check": "exchange_sequence", "detail": "stored played line is not fully legal"}]
        mover_lost, opponent_lost = _capture_totals(entries, mover)
        named_value = _VALUE[_PIECE[named.group(1).lower()]]
        says_for_nothing = bool(re.search(r"\bfor nothing\b", caption, re.I))
        compensated_named_piece = opponent_lost >= named_value
        if (says_for_nothing and opponent_lost > 0) or compensated_named_piece:
            return [{
                "check": "exchange_sequence",
                "detail": (
                    f"caption calls the {named.group(1).lower()} a free loss, but the stored line "
                    f"also removes {opponent_lost}cp of opponent material "
                    f"(mover material removed: {mover_lost}cp)"
                ),
            }]
    except Exception:
        return [{"check": "exchange_sequence", "detail": "exchange claim could not be verified"}]
    return []


_MATERIAL_LOSS_RX = re.compile(
    r"\bcosts? you material\b|\bhands material away\b|\bloses? material\b",
    re.I,
)


def _check_unsupported_material_loss(
    caption: str, facts: Dict[str, Any]
) -> List[Dict[str, str]]:
    if not _MATERIAL_LOSS_RX.search(caption):
        return []
    try:
        start = chess.Board(facts["fen_before"])
        mover = start.turn
        _, entries, complete = _replay_branch(
            facts, first_key="move_san", continuation_key="pv_after_played"
        )
        if complete:
            mover_lost, opponent_lost = _capture_totals(entries, mover)
            if mover_lost <= opponent_lost:
                return [{
                    "check": "unsupported_material_loss",
                    "detail": (
                        "claims material loss, but the complete stored line shows "
                        f"{mover_lost}cp removed from the mover and {opponent_lost}cp from the opponent"
                    ),
                }]
    except Exception:
        return [{"check": "unsupported_material_loss", "detail": "material claim could not be verified"}]
    return []


_ATTACK_COUNT_RX = re.compile(
    r"\b(\d+)\s+opponent pieces are aimed at your king on\s+([a-h][1-8])\b",
    re.I,
)


def _check_attack_count(caption: str, post: chess.Board) -> List[Dict[str, str]]:
    match = _ATTACK_COUNT_RX.search(caption)
    if not match:
        return []
    expected = int(match.group(1))
    square = chess.parse_square(match.group(2).lower())
    mover = not post.turn
    king_square = post.king(mover)
    actual = len(post.attackers(not mover, square))
    if king_square != square or actual != expected:
        return [{
            "check": "attack_count",
            "detail": (
                f"claims {expected} attackers on the king at {match.group(2).lower()}, "
                f"but the post-move board has {actual}"
            ),
        }]
    return []


def _board_post(facts: Dict[str, Any]) -> chess.Board:
    """Board the user is looking at: after the move that was played."""
    b = chess.Board(facts["fen_before"])
    b.push_san(facts["move_san"])
    return b


def _stored_capture_claims(
    facts: Dict[str, Any],
) -> set[tuple[str, str]]:
    """Piece/square pairs proved at the exact capture ply of a stored line."""
    claims: set[tuple[str, str]] = set()
    for first_key, continuation_key in (
        ("move_san", "pv_after_played"),
        ("best_move_san", "pv_after_best"),
    ):
        _, entries, complete = _replay_branch(
            facts,
            first_key=first_key,
            continuation_key=continuation_key,
        )
        if not complete:
            continue
        for entry in entries:
            captured = entry.get("captured_piece")
            if captured is None:
                continue
            claims.add(
                (
                    _PNAME[captured.piece_type],
                    chess.square_name(entry["capture_square"]),
                )
            )
    return claims


def _is_stored_capture_phrase(caption: str, start: int) -> bool:
    prefix = caption[max(0, start - 24):start]
    return bool(
        re.search(
            r"\b(?:takes?|captures?|wins?|won|removes?)\s+(?:the\s+)?$",
            prefix,
            re.I,
        )
    )


def _check_piece_on_square(
    caption: str,
    post: chess.Board,
    facts: Dict[str, Any],
    *,
    strict_v2: bool = False,
) -> List[Dict[str, str]]:
    """'<piece> on <sq>' must match the board the user sees. Current-location
    claims only — skip 'to/jumps to/plays' (those are future moves)."""
    out = []
    stored_captures = _stored_capture_claims(facts) if strict_v2 else set()
    for m in re.finditer(r"\b(knight|bishop|rook|queen|king|pawn)\s+on\s+([a-h][1-8])\b",
                         caption, re.I):
        pc, sq = m.group(1).lower(), m.group(2).lower()
        if (
            strict_v2
            and _is_stored_capture_phrase(caption, m.start())
            and (pc, sq) in stored_captures
        ):
            continue
        pa = post.piece_at(chess.parse_square(sq))
        if pa is None or pa.piece_type != _PIECE[pc]:
            actual = _PNAME.get(pa.piece_type, "nothing") if pa else "nothing"
            out.append({"check": "piece_on_square",
                        "detail": f"says '{pc} on {sq}' but {sq} holds {actual}"})
    return out


def _recommended_capture(facts: Dict[str, Any]):
    """The capture the caption is justifying: best move (user) or the student's
    punishing reply (opponent move). Returns (base_board, move) or (None, None)."""
    b = chess.Board(facts["fen_before"])
    try:
        if facts.get("is_user_move"):
            san = facts.get("best_move_san")
            base = b
        else:
            b.push_san(facts["move_san"])
            pv = facts.get("pv_after_played") or []
            san = pv[0] if pv else None
            base = b
        if not san:
            return (None, None)
        mv = base.parse_san(san)
        return (base, mv) if base.is_capture(mv) else (None, None)
    except Exception:
        return (None, None)


def _check_free(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _FREE_RX.search(caption):
        return []
    base, mv = _recommended_capture(facts)
    if mv is None:
        return []
    defs = base.attackers(not base.turn, mv.to_square)
    if defs:
        sq = chess.square_name(mv.to_square)
        return [{"check": "free_when_defended",
                 "detail": f"calls it free/won but {sq} is defended by "
                           f"{[chess.square_name(s) for s in defs]} — the win is a tactic, not a free grab"}]
    return []


def _check_no_recapture(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _NORECAP_RX.search(caption):
        return []
    if facts.get("is_user_move"):
        return []  # 'no recapture' framing applies to an opponent capture
    try:
        b = chess.Board(facts["fen_before"])
        mv = b.parse_san(facts["move_san"])
        if not b.is_capture(mv):
            return []
        tgt = mv.to_square
        b.push(mv)
        recaps = [m for m in b.legal_moves if m.to_square == tgt and b.is_capture(m)]
        if recaps:
            return [{"check": "no_recapture",
                     "detail": f"says 'no recapture' but you can recapture on "
                               f"{chess.square_name(tgt)} ({[b.san(m) for m in recaps]})"}]
    except Exception:
        pass
    return []


def _check_mate(
    caption: str,
    facts: Dict[str, Any],
    *,
    strict_v2: bool = False,
) -> List[Dict[str, str]]:
    if not _MATE_RX.search(caption):
        return []

    evidence = facts.get("mate_threat_evidence")
    transition = evidence.get("transition") if isinstance(evidence, dict) else None
    violations: List[Dict[str, str]] = []
    claimed_transition = None
    if _MATE_ALREADY_RX.search(caption):
        claimed_transition = "already_lost"
    elif _MATE_ALLOWED_RX.search(caption):
        claimed_transition = "allowed"
    elif _MATE_MISSED_RX.search(caption):
        claimed_transition = "missed"
    elif _MATE_PRESERVED_RX.search(caption):
        claimed_transition = "preserved"
    elif _MATE_DELIVERED_RX.search(caption):
        claimed_transition = "delivered"

    if strict_v2 and transition not in {
        "delivered", "preserved", "missed", "allowed", "already_lost"
    }:
        return [{
            "check": "mate_direction",
            "detail": "mate language has no branch-owned transition evidence",
        }]
    if claimed_transition and transition and claimed_transition != transition:
        violations.append({
            "check": "mate_direction",
            "detail": (
                f"caption says {claimed_transition}, but stored branch evidence "
                f"proves {transition}"
            ),
        })

    # Independently reconstruct the transition from the raw stored branches.
    # The rendered verifier does not trust the extractor's transition merely
    # because it is present in the same packet.
    if strict_v2 and transition:
        try:
            from services.stored_line_verifier import replay_stored_line

            start = chess.Board(facts["fen_before"])
            mover = start.turn
            opponent = not mover
            played = replay_stored_line(
                start,
                facts.get("move_san"),
                facts.get("pv_after_played") or (),
            )
            best = replay_stored_line(
                start,
                facts.get("best_move_san"),
                facts.get("pv_after_best") or (),
            )

            def eval_side(value: Any):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return None
                if abs(value) < 9000:
                    return None
                return chess.WHITE if value > 0 else chess.BLACK

            def proves(replay, value: Any, side: chess.Color) -> bool:
                exact = (
                    replay.complete
                    and replay.checkmate
                    and replay.checkmating_color == side
                )
                return bool(exact or eval_side(value) == side)

            played_mover = proves(played, facts.get("eval_after_cp"), mover)
            played_opponent = proves(
                played, facts.get("eval_after_cp"), opponent
            )
            best_mover = proves(best, facts.get("eval_before_cp"), mover)
            best_opponent = proves(best, facts.get("eval_before_cp"), opponent)

            after = start.copy(stack=False)
            move = after.parse_san(str(facts.get("move_san") or ""))
            after.push(move)
            if after.is_checkmate():
                reconstructed = "delivered"
            elif played_opponent:
                reconstructed = "already_lost" if best_opponent else "allowed"
            elif played_mover:
                reconstructed = "preserved"
            elif best_mover:
                reconstructed = "missed"
            elif best_opponent:
                reconstructed = "already_lost"
            else:
                reconstructed = None
            if reconstructed != transition:
                violations.append({
                    "check": "mate_direction",
                    "detail": (
                        f"branch evidence says {transition}, but independent "
                        f"replay reconstructs {reconstructed or 'no proven mate'}"
                    ),
                })
        except Exception as exc:
            violations.append({
                "check": "mate_direction",
                "detail": (
                    "mate branches could not be independently replayed: "
                    f"{type(exc).__name__}"
                ),
            })

    explicit_mates = {
        match.group(1)
        for match in _EXPLICIT_MATE_SAN_RX.finditer(caption)
    }
    if strict_v2 and explicit_mates:
        try:
            from services.stored_line_verifier import replay_stored_line

            start = chess.Board(facts["fen_before"])
            terminal_mates = set()
            for first_key, continuation_key in (
                ("move_san", "pv_after_played"),
                ("best_move_san", "pv_after_best"),
            ):
                first = facts.get(first_key)
                if not first:
                    continue
                replay = replay_stored_line(
                    start,
                    first,
                    facts.get(continuation_key) or (),
                )
                if (
                    replay.complete
                    and replay.checkmate
                    and replay.replayed_san
                ):
                    terminal_mates.add(
                        replay.replayed_san[-1].rstrip("+#")
                    )
            unsupported = sorted(explicit_mates - terminal_mates)
            if unsupported:
                violations.append({
                    "check": "mate",
                    "detail": (
                        "claims "
                        + ", ".join(f"{san}#" for san in unsupported)
                        + " is checkmate, but no complete stored branch ends "
                        "in that mate"
                    ),
                })
            return violations
        except Exception:
            violations.append({
                "check": "mate",
                "detail": "explicit mating line could not be verified",
            })
            return violations
    if strict_v2 and transition:
        # Direction and the supporting branch were checked above. Captions such
        # as "misses mate in 2" do not claim that the first move itself mates.
        return violations
    try:
        b = chess.Board(facts["fen_before"])
        if facts.get("is_user_move"):
            rec = facts.get("best_move_san") or facts.get("move_san")
        else:
            pv = facts.get("pv_after_played") or []
            rec = pv[0] if pv else None
        if not rec:
            return []
        b.push_san(rec)
        if not b.is_checkmate():
            return [{"check": "mate",
                     "detail": f"claims checkmate but {rec} is not mate"}]
    except Exception:
        pass
    return []


_OUTPOST_RX = re.compile(r"\boutpost\b|no pawn can chase", re.I)


_CENTRAL_OUTPOST_SQ = {chess.square(f, r) for f in range(2, 6) for r in range(2, 6)}  # c3..f6


def _move_is_outpost(board: "chess.Board", mv: "chess.Move") -> bool:
    """Independent re-derivation of the outpost claim, matching the CANONICAL definition
    (a rim knight is NOT an outpost — that was the bug): knight to a CENTRAL square
    (files c-f), DEFENDED by an own piece, and NOT currently attacked by an enemy pawn."""
    pc = board.piece_at(mv.from_square)
    if pc is None or pc.piece_type != chess.KNIGHT:
        return False
    if mv.to_square not in _CENTRAL_OUTPOST_SQ:
        return False
    us = pc.color
    them = not us
    b = board.copy()
    try:
        b.push(mv)
    except Exception:
        return False
    # must be defended by an own piece (other than the knight itself)
    if not any(d != mv.to_square for d in b.attackers(us, mv.to_square)):
        return False
    # must not be currently attacked by an enemy pawn
    kf, kr = chess.square_file(mv.to_square), chess.square_rank(mv.to_square)
    par = kr + (1 if them == chess.BLACK else -1)
    if 0 <= par <= 7:
        for df in (-1, 1):
            af = kf + df
            if 0 <= af <= 7:
                p = b.piece_at(chess.square(af, par))
                if p and p.color == them and p.piece_type == chess.PAWN:
                    return False
    return True


def _check_outpost(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    if not _OUTPOST_RX.search(caption):
        return []
    cands = []
    try:
        b = chess.Board(facts["fen_before"])
        for san in (facts.get("move_san"), facts.get("best_move_san")):
            if san:
                try:
                    cands.append((b, b.parse_san(san)))
                except Exception:
                    pass
    except Exception:
        pass
    fa = facts.get("fen_after")
    if fa and facts.get("user_best_reply_san"):
        try:
            ba = chess.Board(fa)
            cands.append((ba, ba.parse_san(facts["user_best_reply_san"])))
        except Exception:
            pass
    if cands and not any(_move_is_outpost(bd, mv) for bd, mv in cands):
        return [{"check": "outpost",
                 "detail": "claims an outpost but no candidate move posts a knight no pawn can chase"}]
    return []


_QUEEN_CHASE_RX = re.compile(r"queen gets chased|queen.*(chase|hits it and it must move)", re.I)


def _check_queen_chased(caption: str, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    """Independent re-derivation: the played move is a QUEEN move, and the opponent's
    reply is a NON-capturing pawn/knight/bishop that attacks the queen's square (so it
    must move). Catches a 'queen chased' claim on a non-queen move or a non-attacking reply."""
    if not _QUEEN_CHASE_RX.search(caption):
        return []
    try:
        b = chess.Board(facts["fen_before"])
        mv = b.parse_san(facts["move_san"])
        pc = b.piece_at(mv.from_square)
        if pc is None or pc.piece_type != chess.QUEEN:
            return [{"check": "queen_chased", "detail": "says queen chased but the move isn't a queen move"}]
        pv = facts.get("pv_after_played") or []
        if not pv:
            return []  # no reply to check against → don't flag
        ba = chess.Board(facts["fen_after"])
        rmv = ba.parse_san(pv[0])
        rpc = ba.piece_at(rmv.from_square)
        is_cap = ba.is_capture(rmv)
        ba.push(rmv)
        if not (rpc and rpc.piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP)
                and not is_cap and mv.to_square in ba.attacks(rmv.to_square)):
            return [{"check": "queen_chased",
                     "detail": "says queen chased but the reply doesn't attack the queen with a lower piece"}]
    except Exception:
        return []
    return []


# "allows/lets <SAN>" — the named opponent reply must be LEGAL on the board the
# user now faces (after the played move). Guards the lost-position-floor variant
# that names the punishment move, and any existing "lets Bxe5 win" caption.
_ALLOWS_RX = re.compile(
    r"\b(?:allows|lets)\s+"
    r"(O-O(?:-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b"
)


def _check_allows(caption: str, post: chess.Board) -> List[Dict[str, str]]:
    out = []
    for m in _ALLOWS_RX.finditer(caption):
        san = m.group(1)
        try:
            post.parse_san(san)  # raises if illegal / ambiguous in this position
        except Exception:
            out.append({"check": "allows_illegal",
                        "detail": f"says 'allows {san}' but {san} is not a legal reply here"})
    return out


_KING_CENTER_RX = re.compile(r"king in the cent(?:er|re)", re.I)


def _check_king_center(caption: str, post: chess.Board) -> List[Dict[str, str]]:
    """'leaves your king in the center' — the MOVER's king must actually be
    central (files c-f) on its home rank in the position the user now faces."""
    if not _KING_CENTER_RX.search(caption):
        return []
    mover = not post.turn  # post is after the played move → opponent to move
    ksq = post.king(mover)
    if ksq is None:
        return []
    home_rank = 0 if mover == chess.WHITE else 7
    central = (2 <= chess.square_file(ksq) <= 5) and (chess.square_rank(ksq) == home_rank)
    if not central:
        return [{"check": "king_not_central",
                 "detail": f"says 'king in the center' but the king is on {chess.square_name(ksq)}"}]
    return []


def verify_caption(
    caption: str,
    facts: Dict[str, Any],
    *,
    strict_v2: bool = False,
) -> List[Dict[str, str]]:
    """Return board-verified violations while preserving deployed V1 by default.

    ``strict_v2`` is opt-in for Quality V2 evidence and gold construction. The
    player-facing V1 narrator calls this function without that option, so a
    default-off Quality V2 deployment remains byte-compatible.
    """
    if not caption or not (caption or "").strip():
        return []
    try:
        post = _board_post(facts)
    except Exception as exc:
        # A malformed or incomplete evidence packet is not proof. Returning clean
        # here used to let claims escape merely because the verifier could not
        # reconstruct the position.
        if strict_v2:
            return [{
                "check": "unverified_board",
                "detail": f"caption evidence could not be reconstructed: {type(exc).__name__}",
            }]
        return []
    base = (_check_piece_on_square(
                caption, post, facts, strict_v2=strict_v2
            )
            + _check_free(caption, facts)
            + _check_no_recapture(caption, facts)
            + _check_mate(caption, facts, strict_v2=strict_v2)
            + _check_outpost(caption, facts)
            + _check_queen_chased(caption, facts)
            + _check_allows(caption, post)
            + _check_king_center(caption, post))
    if not strict_v2:
        return base
    return (base
            + _check_forcing_move(caption, facts)
            + _check_unsound_opening_praise(caption, facts)
            + _check_false_sacrifice(caption, facts)
            + _check_exchange_sequence(caption, facts)
            + _check_unsupported_material_loss(caption, facts)
            + _check_attack_count(caption, post))
