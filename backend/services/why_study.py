"""Studying one silent position: the fact packet, the model's contract, the gate.

Used by scripts/why_queue_worker.py on Mohit's machine. Kept here, importable
without the worker's ssh and subprocess plumbing, so the gate can be tested on
known positions.

The rule this serves (docs/why_queue_claude_scope.md): the model proposes, the
board decides. Everything the model says must arrive as a CLAIM the gate can
replay with python-chess or the engine. A reason whose claims do not all
replay is held, never shown.

Claim kinds the gate knows:

  attacks          {after, subject, target}        the piece on `subject` attacks the piece on `target`
  controls         {after, subject, target}        the piece on `subject` covers the square `target` (empty or not)
  undefended       {after, target}                 the piece on `target` has no defender
  no_legal_moves   {after, subject}                the piece on `subject` cannot move
  gives_check      {after}                         the last move of `after` gives check
  castling_illegal {after, side}                   that side cannot castle now
  blocks_own_pawn  {after, subject, target}        own piece on `subject` stands in front of own pawn on `target`
  capture_loses    {after, capture_san, swing_cp_min}        playing that capture costs the capturer at least so much
  line_better      {worse_line, better_line, side, by_cp_min} the position after `better_line` is better for `side`
                                                             than the one after `worse_line`, by at least so much

`after` is a list of SAN moves from the position before the move played (may
be empty). Squares are "g2"-style. Everything else is refused.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import chess
import chess.engine

VALUES = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900}
PIECE_WORD = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
CLAIM_KINDS = ("attacks", "controls", "undefended", "no_legal_moves", "gives_check", "castling_illegal",
               "blocks_own_pawn", "capture_loses", "line_better")
PIECE_OF = {v: k for k, v in {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
                              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}.items()}
DEFAULT_ENGINE = os.environ.get("STOCKFISH_PATH") or "/usr/games/stockfish"
MATE = 10000


# --- engine ------------------------------------------------------------------

def open_engine(path: Optional[str] = None, *, hash_mb: int = 256) -> chess.engine.SimpleEngine:
    eng = chess.engine.SimpleEngine.popen_uci(path or DEFAULT_ENGINE)
    try:
        eng.configure({"Threads": 1, "Hash": hash_mb})
    except Exception:                                   # noqa: BLE001
        pass
    return eng


def _cp(info: Dict[str, Any], pov: chess.Color) -> int:
    return int(info["score"].pov(pov).score(mate_score=MATE))


def eval_cp(eng, board: chess.Board, pov: chess.Color, depth: int) -> int:
    return _cp(eng.analyse(board, chess.engine.Limit(depth=depth)), pov)


def lines(eng, board: chess.Board, pov: chess.Color, depth: int, multipv: int, plies: int) -> List[Dict[str, Any]]:
    infos = eng.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    out = []
    for info in infos:
        pv = list(info.get("pv") or [])[:plies]
        if not pv:
            continue
        out.append({"san": board.san(pv[0]), "cp": _cp(info, pov),
                    "line": board.variation_san(pv).split()})
    return out


# --- board facts ---------------------------------------------------------------

def replay(fen: str, sans: Sequence[str]) -> chess.Board:
    """The board after `sans` from `fen`. Raises ValueError naming the bad move."""
    board = chess.Board(fen)
    for san in sans or []:
        try:
            board.push_san(str(san))
        except Exception as exc:                        # noqa: BLE001
            raise ValueError(f"{san} is not legal here") from exc
    return board


def _san_only(text: str) -> List[str]:
    """SAN tokens in a line written as 'Qg6 7. Bb5+ Nc6', move numbers dropped."""
    return [t for t in str(text or "").split() if not re.fullmatch(r"\d+\.(\.\.)?", t)]


def piece_name(board: chess.Board, square: str) -> Optional[str]:
    try:
        piece = board.piece_at(chess.parse_square(square))
    except ValueError:
        return None
    return PIECE_WORD[piece.piece_type] if piece else None


def _with_turn(board: chess.Board, color: chess.Color) -> chess.Board:
    b = board.copy(stack=False)
    b.turn = color
    return b


def pieces_with_no_legal_move(board: chess.Board, color: chess.Color) -> List[str]:
    b = _with_turn(board, color)
    if b.is_check():
        return []
    out = []
    for sq, piece in b.piece_map().items():
        if piece.color != color or piece.piece_type in (chess.KING, chess.PAWN):
            continue
        if not any(m.from_square == sq for m in b.legal_moves):
            out.append(f"{PIECE_WORD[piece.piece_type]} {chess.square_name(sq)}")
    return sorted(out)


def can_castle_now(board: chess.Board, color: chess.Color) -> bool:
    b = _with_turn(board, color)
    return any(b.is_castling(m) for m in b.legal_moves)


def attacks_on_undefended(board: chess.Board, by: chess.Color) -> List[Dict[str, Any]]:
    """Enemy men the side `by` attacks that have no defender."""
    out = []
    for sq, piece in board.piece_map().items():
        if piece.color == by or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(by, sq)
        if not attackers:
            continue
        defenders = board.attackers(not by, sq)
        if defenders:
            continue
        for a in attackers:
            ap = board.piece_at(a)
            out.append({"attacker": f"{PIECE_WORD[ap.piece_type]} {chess.square_name(a)}",
                        "target": f"{PIECE_WORD[piece.piece_type]} {chess.square_name(sq)}",
                        "defenders": 0})
    return out


def material(board: chess.Board) -> Dict[str, int]:
    w = sum(VALUES.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.WHITE)
    b = sum(VALUES.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.BLACK)
    return {"white": w, "black": b}


def board_facts(board: chess.Board, mover: chess.Color) -> Dict[str, Any]:
    opp = not mover
    return {
        "side_to_move": "white" if board.turn == chess.WHITE else "black",
        "in_check": board.is_check(),
        "mover_pieces_with_no_legal_move": pieces_with_no_legal_move(board, mover),
        "opponent_pieces_with_no_legal_move": pieces_with_no_legal_move(board, opp),
        "mover_can_castle_now": can_castle_now(board, mover),
        "opponent_can_castle_now": can_castle_now(board, opp),
        "mover_attacks_on_undefended": attacks_on_undefended(board, mover),
        "opponent_attacks_on_undefended": attacks_on_undefended(board, opp),
        "material": material(board),
    }


# --- the packet ----------------------------------------------------------------

def build_packet(fen_before: str, played_san: str, *, better_san: Optional[str] = None,
                 mover_is_user: bool = True, depth: int = 20, engine_path: Optional[str] = None,
                 stored_class: Optional[str] = None, rating: Optional[int] = None,
                 live_engine_said: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Everything the model may reason from. Engine lines, board facts, probes.

    The model never runs an engine itself; this is the whole of its evidence.
    """
    root = chess.Board(fen_before)
    mover = root.turn
    played = root.copy()
    played.push_san(played_san)

    with open_engine(engine_path) as eng:
        root_lines = lines(eng, root, mover, depth, 5, 8)
        if not better_san:
            for cand in root_lines:
                if cand["san"] != played_san:
                    better_san = cand["san"]
                    break
        better = root.copy()
        better.push_san(better_san)
        after_played = lines(eng, played, mover, depth, 3, 10)
        after_better = lines(eng, better, mover, depth, 2, 10)

        # The best replies after the move played, then the same reply after the
        # better move when it is legal there: the shared-threat comparison.
        # Three replies, not one: at depth 20 the b3 position's Qg6 (the
        # threat) sits second behind Nc6 by three centipawns.
        probes: List[Dict[str, Any]] = []
        seen_targets: set = set()
        reply = after_played[0]["san"] if after_played else None
        for reply_row in after_played[:3]:
            reply_san = reply_row["san"]
            played_reply = played.copy()
            played_reply.push_san(reply_san)
            for hit in attacks_on_undefended(played_reply, not mover):
                if len(probes) >= 6:
                    break
                target_sq = hit["target"].split()[-1]
                attacker_sq = hit["attacker"].split()[-1]
                if (reply_san, target_sq) in seen_targets:
                    continue
                seen_targets.add((reply_san, target_sq))
                reply = reply_san
                probe: Dict[str, Any] = {"threat": f"{hit['attacker']} attacks undefended {hit['target']} after {played_san} {reply}"}
                # If the capture is simply taken next: what does it cost the capturer?
                for label, base in (("after_played", played), ("after_better", better)):
                    b = base.copy()
                    try:
                        b.push_san(reply)
                    except Exception:                   # noqa: BLE001
                        probe[label] = "the reply is not legal here"
                        continue
                    before = eval_cp(eng, b, not mover, 14)
                    # the mover's best answer to the threat
                    answer = lines(eng, b, mover, 14, 1, 6)
                    answer_san = answer[0]["san"] if answer else None
                    if answer_san:
                        b.push_san(answer_san)
                    cap = None
                    try:
                        move = b.find_move(chess.parse_square(attacker_sq), chess.parse_square(target_sq))
                        cap = b.san(move)
                    except Exception:                   # noqa: BLE001
                        cap = None
                    entry: Dict[str, Any] = {"mover_answers_with": answer_san,
                                             "eval_for_the_attacker_before_cp": before}
                    if cap:
                        b.push(move)
                        after = eval_cp(eng, b, not mover, 14)
                        entry["then_capture"] = cap
                        entry["eval_for_the_attacker_after_capture_cp"] = after
                        entry["capture_costs_the_attacker_cp"] = before - after
                        entry["line"] = [reply, answer_san, cap] if answer_san else [reply, cap]
                    else:
                        entry["then_capture"] = None
                    probe[label] = entry
                probes.append(probe)
        reply = after_played[0]["san"] if after_played else None

        ledger = {}
        for label, base, ls in (("after_played", played, after_played), ("after_better", better, after_better)):
            if not ls:
                continue
            b = base.copy()
            start = material(b)
            for san in ls[0]["line"]:
                try:
                    b.push_san(san)
                except Exception:                       # noqa: BLE001
                    break
            end = material(b)
            mine = "white" if mover == chess.WHITE else "black"
            theirs = "black" if mine == "white" else "white"
            ledger[label] = {"mover_material_change_cp": (end[mine] - start[mine]) - (end[theirs] - start[theirs]),
                             "line": ls[0]["line"]}

    reply_board = played.copy()
    if reply:
        reply_board.push_san(reply)
    mover_name = "white" if mover == chess.WHITE else "black"
    other_name = "black" if mover_name == "white" else "white"
    you, them = (mover_name, other_name) if mover_is_user else (other_name, mover_name)
    return {
        "whose_move": "the reader's own move" if mover_is_user else "the opponent's move",
        "side_to_move": mover_name,
        "pronouns": {you: "you / your", them: "the opponent / their"},
        "fen_before": fen_before,
        "played_san": played_san,
        "better_san": better_san,
        "stored_class": stored_class,
        "reader_rating": rating,
        "root_candidates_cp_for_mover": root_lines,
        "after_played": {"fen": played.fen(), "best_replies_cp_for_mover": after_played},
        "after_better": {"fen": better.fen(), "best_replies_cp_for_mover": after_better},
        "board_facts": {
            "before_the_move": board_facts(root, mover),
            "after_played": board_facts(played, mover),
            "after_played_and_best_reply": board_facts(reply_board, mover) if reply else None,
            "after_better": board_facts(better, mover),
        },
        "shared_threat_probes": probes,
        "material_along_best_lines": ledger,
        "live_engine_said": live_engine_said,
        "pv_after_played": after_played[0]["line"] if after_played else [],
        "pv_after_best": after_better[0]["line"] if after_better else [],
    }


# --- the model's contract -----------------------------------------------------

SYSTEM_PROMPT = """You are a chess coach's analyst. You are given one position where a player made a move the engine dislikes, the better move, engine lines, and board facts. Your job is to find the MECHANISM: the concrete thing on the board that makes the move played worse than the better move. Then write it for a player rated 600 to 1500.

Rules.
- Reason only from the packet. It holds the engine's lines and the board facts; nothing else exists.
- Every chess statement in your reason must be backed by a CLAIM in `claims`, using only the claim kinds listed in the schema. A claim is a thing the board or the engine can replay. If you cannot express a statement as a claim, do not say it.
- The reason: two to five short sentences, at most sixty words in all. No numbers, no centipawns, no evaluations. Name the better move once. Say what the move played fails to do or allows, and what the better move does instead. Pronouns: the packet's `pronouns` field says which colour is "you/your" and which is "the opponent/their". Never call the opponent's piece "your".

How to write it. The reader is ten years old, or reading English as a second language, on a phone, between games. Anybody must be able to read it once, understand it, and explain it to a friend.
- Never more than fourteen words in one sentence. Split it instead. Count.
- One idea in each sentence. Everyday words. Prefer five short sentences to two clever ones.
- No metaphor, no idiom, no figure of speech. Not "the queen is stuck in traffic", not "heads for", not "spends a move". Say what happens on the board.
- Never use these words at all; say the plain thing instead. "undefended" / "loose" / "hanging" / "en prise" -> "nothing is guarding it". "material" -> name the piece or pawn. "inaccuracy" -> "a small mistake". "exchange" -> "trade". "recapture" -> "take back". "develop" / "development" -> "bring a piece out". "tempo" -> "a wasted move". "centralise" -> "bring it to the middle". Never: initiative, counterplay, prophylaxis, structure, outpost, passive, coordination, compensation, zugzwang, fianchetto, ply.
- Piece names, square names, "check", "takes", "guards", "attacks", "castle" are fine. A pattern word is fine only if the same sentence explains it with the pieces on the board: "a skewer: hit the knight, then win the pawn behind it".
- When the facts list several squares or pieces, name ONE as the example and drop the rest. A list is not teaching.
- The reader must finish knowing what to do differently next game. If the honest lesson cannot be said plainly, say the simplest true part and stop.
- Every piece you mention must be the `subject` or `target` of one of your claims, with its square, on the board where you mean it (set `after` to the moves that reach that board). A move name counts for its own piece and destination square. A piece you cannot tie to a claim is a piece you may not mention.
- The `shared_threat_probes` section is where the mechanism usually hides: a threat that both moves allow but that only the better move answers well. Prefer a claim about that over a bare "the better line is better".
- If the packet shows no mechanism, only that the position is a little worse with nothing concrete, set `no_lesson` true and say why in one line. That is a real and useful answer. Do not invent a lesson.
- Do not read a threat off a line without checking it in the facts or probes: a move in a line is not a threat until the board says what it attacks.
- `attacks` needs a piece on the target square. For an empty square use `controls`. For "the better line is better" use `line_better` with `worse_line` = the moves of the move played's line and `better_line` = the moves of the better move's line, both starting from the position before the move played.

Example. Black played 4...b6 in a Scandinavian; the better move was Nf6; it is the reader's own move, so Black is "you".
{"no_lesson": false,
 "mechanism": "a pawn move while pieces are still at home",
 "reason": "b6 moves a pawn while your pieces are still at home. Your queen on e6 stands where your e-pawn needs to go. So your bishop on f8 cannot move, and you cannot castle. Nf6 brings a piece out instead.",
 "claims": [
  {"kind": "blocks_own_pawn", "label": "your queen on e6 stands in front of your e7 pawn", "after": ["b6"], "subject": "e6", "target": "e7"},
  {"kind": "no_legal_moves", "label": "your bishop on f8 cannot move after b6", "after": ["b6"], "subject": "f8"},
  {"kind": "castling_illegal", "label": "you cannot castle after b6", "after": ["b6"], "side": "black"}
 ]}
Every piece in that reason (queen e6, pawn e7, bishop f8) is the subject or target of a claim, every move named (b6, Nf6) is the move played or the better move, no sentence is over fourteen words, and there is not one number.
"""

CLAIM_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["no_lesson", "reason", "claims"],
    "properties": {
        "no_lesson": {"type": "boolean"},
        "no_lesson_why": {"type": "string"},
        "reason": {"type": "string"},
        "mechanism": {"type": "string", "description": "one short label for the pattern, e.g. threat left unanswered"},
        "claims": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "label"],
                "properties": {
                    "kind": {"type": "string", "enum": list(CLAIM_KINDS)},
                    "label": {"type": "string", "description": "the claim in plain words"},
                    "after": {"type": "array", "items": {"type": "string"},
                              "description": "SAN moves from the position before the move played"},
                    "worse_line": {"type": "array", "items": {"type": "string"},
                                   "description": "line_better only: the move played and the moves that follow it"},
                    "better_line": {"type": "array", "items": {"type": "string"},
                                    "description": "line_better only: the better move and the moves that follow it"},
                    "subject": {"type": "string", "pattern": "^[a-h][1-8]$"},
                    "target": {"type": "string", "pattern": "^[a-h][1-8]$"},
                    "side": {"type": "string", "enum": ["white", "black"]},
                    "capture_san": {"type": "string"},
                    "swing_cp_min": {"type": "integer"},
                    "by_cp_min": {"type": "integer"},
                },
            },
        },
    },
}


# --- the gate ----------------------------------------------------------------

def _color(name: Optional[str]) -> Optional[chess.Color]:
    return {"white": chess.WHITE, "black": chess.BLACK}.get(str(name or "").lower())


def check_claim(claim: Dict[str, Any], fen_before: str, *, eng=None, depth: int = 16) -> Tuple[bool, Optional[str]]:
    """Replay one claim. (True, None) when it holds, (False, why) when it does not."""
    kind = str(claim.get("kind") or "")
    if kind not in CLAIM_KINDS:
        return False, f"unknown claim kind {kind!r}"
    try:
        board = replay(fen_before, claim.get("after") or [])
    except ValueError as exc:
        return False, str(exc)

    def sq(name: str) -> Optional[int]:
        try:
            return chess.parse_square(str(claim.get(name) or ""))
        except ValueError:
            return None

    if kind == "attacks":
        s, t = sq("subject"), sq("target")
        if s is None or t is None:
            return False, "attacks needs subject and target squares"
        piece = board.piece_at(s)
        if piece is None:
            return False, f"no piece on {claim['subject']}"
        if board.piece_at(t) is None:
            return False, f"nothing on {claim['target']} to attack"
        if s not in board.attackers(piece.color, t):
            return False, f"the {PIECE_WORD[piece.piece_type]} on {claim['subject']} does not attack {claim['target']}"
        return True, None
    if kind == "controls":
        s, t = sq("subject"), sq("target")
        if s is None or t is None:
            return False, "controls needs subject and target squares"
        piece = board.piece_at(s)
        if piece is None:
            return False, f"no piece on {claim['subject']}"
        if t not in board.attacks(s):
            return False, f"the {PIECE_WORD[piece.piece_type]} on {claim['subject']} does not cover {claim['target']}"
        return True, None
    if kind == "undefended":
        # One square either way: the model has put it in `subject` as often as
        # in `target`, and the meaning is the same.
        t = sq("target") if sq("target") is not None else sq("subject")
        if t is None:
            return False, "undefended needs a target square"
        piece = board.piece_at(t)
        if piece is None:
            return False, f"no piece on {claim['target']}"
        if board.attackers(piece.color, t):
            return False, f"{claim['target']} is defended"
        return True, None
    if kind == "no_legal_moves":
        s = sq("subject") if sq("subject") is not None else sq("target")
        if s is None:
            return False, "no_legal_moves needs a subject square"
        piece = board.piece_at(s)
        if piece is None:
            return False, f"no piece on {claim['subject']}"
        b = _with_turn(board, piece.color)
        if any(m.from_square == s for m in b.legal_moves):
            return False, f"the {PIECE_WORD[piece.piece_type]} on {claim['subject']} can move"
        return True, None
    if kind == "gives_check":
        if not (claim.get("after") or []):
            return False, "gives_check needs the move in `after`"
        return (True, None) if board.is_check() else (False, f"{claim['after'][-1]} is not check")
    if kind == "castling_illegal":
        color = _color(claim.get("side"))
        if color is None:
            return False, "castling_illegal needs side"
        return (False, "that side can castle now") if can_castle_now(board, color) else (True, None)
    if kind == "blocks_own_pawn":
        s, t = sq("subject"), sq("target")
        if s is None or t is None:
            return False, "blocks_own_pawn needs subject (blocker) and target (pawn)"
        pawn = board.piece_at(t)
        blocker = board.piece_at(s)
        if pawn is None or pawn.piece_type != chess.PAWN:
            return False, f"no pawn on {claim['target']}"
        if blocker is None or blocker.color != pawn.color:
            return False, f"no own piece on {claim['subject']}"
        step = 8 if pawn.color == chess.WHITE else -8
        if s != t + step:
            return False, f"{claim['subject']} is not in front of the pawn on {claim['target']}"
        return True, None
    if kind == "capture_loses":
        if eng is None:
            return False, "no engine for capture_loses"
        cap = str(claim.get("capture_san") or "")
        try:
            move = board.parse_san(cap)
        except Exception:                               # noqa: BLE001
            return False, f"{cap} is not legal here"
        if not board.is_capture(move):
            return False, f"{cap} is not a capture"
        capturer = board.turn
        before = eval_cp(eng, board, capturer, depth)
        b = board.copy()
        b.push(move)
        after = eval_cp(eng, b, capturer, depth)
        need = int(claim.get("swing_cp_min") or 200)
        if before - after < need:
            return False, f"{cap} costs the capturer {before - after} cp, claim needs {need}"
        return True, None
    if kind == "line_better":
        if eng is None:
            return False, "no engine for line_better"
        color = _color(claim.get("side"))
        if color is None:
            color = chess.Board(fen_before).turn
        worse, better = claim.get("worse_line") or [], claim.get("better_line") or []
        if not worse or not better:
            return False, "line_better needs worse_line and better_line"
        try:
            a = replay(fen_before, worse)
            b = replay(fen_before, better)
        except ValueError as exc:
            return False, str(exc)
        gain = eval_cp(eng, b, color, depth) - eval_cp(eng, a, color, depth)
        need = int(claim.get("by_cp_min") or 100)
        if gain < need:
            return False, f"the better line is ahead by {gain} cp, claim needs {need}"
        return True, None
    return False, "unreachable"


def facts_from_claims(claims: List[Dict[str, Any]], fen_before: str, *, mover_is_user: bool,
                      better_san: Optional[str], played_san: str) -> Dict[str, Any]:
    """The vocabulary the reason may use: every move, square and piece its claims name,
    each piece with its owner in the reader's words."""
    root = chess.Board(fen_before)
    mover = root.turn
    moves: List[str] = [played_san]
    if better_san:
        moves.append(better_san)
    squares: List[str] = []
    owned: List[str] = []
    for c in claims or []:
        for key in ("after", "worse_line", "better_line"):
            moves.extend(str(m) for m in (c.get(key) or []))
        if c.get("capture_san"):
            moves.append(str(c["capture_san"]))
        try:
            board = replay(fen_before, c.get("after") or [])
        except ValueError:
            board = root
        for key in ("subject", "target"):
            s = c.get(key)
            if not s:
                continue
            squares.append(str(s))
            try:
                piece = board.piece_at(chess.parse_square(str(s)))
            except ValueError:
                piece = None
            if piece:
                is_mover = piece.color == mover
                yours = is_mover if mover_is_user else not is_mover
                owned.append(f"{'your' if yours else 'the opponent' + chr(39) + 's'} {PIECE_WORD[piece.piece_type]}")
    return {"moves": sorted(set(moves)), "squares": sorted(set(squares)), "owned": sorted(set(owned))}


# Words a ten-year-old does not own, each with the plain thing that says more.
# The same list the live caption prompt bans (services/llm_caption.py); measured
# there: "undefended" sat in 51% of stored captions, "material" in 16%.
HARD_WORDS: Dict[str, str] = {
    "undefended": "nothing is guarding it", "loose": "nothing is guarding it",
    "hanging": "nothing is guarding it", "en prise": "nothing is guarding it",
    "material": "name the piece or pawn", "inaccuracy": "a small mistake",
    "exchange": "trade", "recapture": "take back", "recaptures": "take back",
    "develop": "bring a piece out", "develops": "brings a piece out", "developing": "bringing a piece out",
    "development": "bringing pieces out", "developed": "brought out",
    "tempo": "a wasted move", "tempi": "wasted moves", "centralise": "bring it to the middle",
    "centralize": "bring it to the middle", "initiative": "say what the attack does",
    "counterplay": "say what the other side can do", "prophylaxis": "stops that plan",
    "prophylactic": "stops that plan", "structure": "say which pawns", "outpost": "a safe square",
    "passive": "has very little room", "coordination": "work together", "compensation": "gets something back",
    "zugzwang": "no good moves left", "fianchetto": "the bishop on the long line", "ply": "one move",
    "plies": "moves",
}
SENTENCE_WORD_LIMIT = 14
_HARD_WORD_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(w) for w in HARD_WORDS), key=len, reverse=True)) + r")\b", re.I)


def readability(text: str) -> Dict[str, Any]:
    """How the reason reads, as numbers for the reviewer and notes for the model.

    Measured, never a hold: refusing a true reason for a long word would silence
    it, and the position already has nothing (feedback_caption_very_easy_english:
    "measure and report the number; do not refuse on it").
    """
    from services.llm_caption import _SAN
    text = (text or "").strip()
    sentences = [s for s in re.split(r"(?<=[.!?:;])\s+", text) if s.strip()]
    counts = [len(_SAN.sub(" x ", s).split()) for s in sentences]
    hard = sorted({m.group(1).lower() for m in _HARD_WORD_RE.finditer(text)})
    plain_words = [w.strip(".,;:!?'\"()") for w in _SAN.sub(" ", text).split()]
    long_words = sorted({w for w in plain_words if len(w) > 12 and "-" not in w})
    notes: List[str] = []
    for i, n in enumerate(counts, 1):
        if n > SENTENCE_WORD_LIMIT:
            notes.append(f"sentence {i} has {n} words; the limit is fourteen. Split it.")
    for w in hard:
        notes.append(f"hard word '{w}': say '{HARD_WORDS.get(w, 'the plain thing')}' instead")
    for w in long_words:
        notes.append(f"long word '{w}': find a shorter everyday word")
    total = sum(counts)
    if total > 60:
        notes.append(f"{total} words in all; the limit is sixty")
    return {"sentences": len(sentences), "words": total,
            "longest_sentence_words": max(counts) if counts else 0,
            "hard_words": hard, "long_words": long_words, "notes": notes}


def gate_text(text: str, claims: List[Dict[str, Any]], *, fen_before: str, played_san: str,
              better_san: Optional[str], mover_is_user: bool) -> List[str]:
    """Why the reason may not ship, as a list; empty when it may.

    Truth and containment hold a reason; reading level does not (see
    readability()). The one length failure left is a safety net for an answer
    that is plainly not a card.
    """
    from services.llm_caption import _SAN, _flatten, _implied_pieces, _tokens
    from services.why_words import swapped_ownership

    failures: List[str] = []
    text = (text or "").strip()
    if not text:
        return ["empty reason"]
    words = text.split()
    if len(words) > 120:
        failures.append(f"far too long ({len(words)} words)")
    stripped = _SAN.sub(" ", text)
    if re.search(r"\d", stripped):
        failures.append("uses a number")
    if better_san and not re.search(rf"(?<![A-Za-z]){re.escape(better_san.rstrip('+#'))}", text):
        failures.append(f"does not name the better move {better_san}")
    facts = facts_from_claims(claims, fen_before, mover_is_user=mover_is_user,
                              better_san=better_san, played_san=played_san)
    flat = _flatten(facts)
    invented = sorted(_tokens(text) - (_tokens(flat) | _implied_pieces(flat)))
    if invented:
        failures.append(f"names chess not in its claims: {invented}")
    swapped = swapped_ownership(facts, text)
    if swapped:
        failures.append(swapped)
    failures.extend(owner_on_square(text, claims, fen_before, mover_is_user=mover_is_user))
    return failures


_OWNED_ON = re.compile(
    r"\b(your|their|(?:the\s+)?opponent'?s)\s+(pawn|knight|bishop|rook|queen|king)\s+on\s+([a-h][1-8])\b", re.I)


def owner_on_square(text: str, claims: List[Dict[str, Any]], fen_before: str, *, mover_is_user: bool) -> List[str]:
    """"Your queen on d1" when the queen on d1 is the opponent's.

    The token guard cannot see this when both sides own a piece of that kind:
    "your queen" and "the opponent's queen" are then both in the facts. The
    square settles it. The piece must stand there, with that owner, on the
    board before the move or on a board one of the claims reaches.
    """
    root = chess.Board(fen_before)
    reader = root.turn if mover_is_user else not root.turn
    boards = [root]
    for c in claims or []:
        for key in ("after", "worse_line", "better_line"):
            if c.get(key):
                try:
                    boards.append(replay(fen_before, c[key]))
                except ValueError:
                    pass
    out: List[str] = []
    for owner, piece, square in _OWNED_ON.findall(text or ""):
        want_color = reader if owner.lower() == "your" else not reader
        want_type = PIECE_OF[piece.lower()]
        sq = chess.parse_square(square.lower())
        if not any((p := b.piece_at(sq)) is not None and p.piece_type == want_type and p.color == want_color
                   for b in boards):
            out.append(f"ownership: {owner} {piece} on {square} is not on any board the claims reach")
    return out


def run_gate(answer: Dict[str, Any], *, fen_before: str, played_san: str, better_san: Optional[str],
             mover_is_user: bool, engine_path: Optional[str] = None, depth: int = 16) -> Dict[str, Any]:
    """Replay every claim, then check the words. Returns the gate record and the
    claims annotated with `verified` / `failure`."""
    claims = [dict(c) for c in (answer.get("claims") or [])]
    failures: List[str] = []
    if answer.get("no_lesson"):
        return {"passed": True, "failures": [], "claims": claims, "no_lesson": True,
                "readability": readability(str(answer.get("no_lesson_why") or "")), "notes": []}
    if not claims:
        failures.append("a reason with no claims")
    needs_engine = any(c.get("kind") in ("capture_loses", "line_better") for c in claims)
    eng = open_engine(engine_path) if needs_engine else None
    try:
        for c in claims:
            ok, why = check_claim(c, fen_before, eng=eng, depth=depth)
            c["verified"] = bool(ok)
            c["failure"] = why
            if not ok:
                failures.append(f"{c.get('label') or c.get('kind')}: {why}")
    finally:
        if eng is not None:
            eng.quit()
    reason_text = str(answer.get("reason") or "")
    failures.extend(gate_text(reason_text, claims, fen_before=fen_before,
                              played_san=played_san, better_san=better_san, mover_is_user=mover_is_user))
    read = readability(reason_text)
    return {"passed": not failures, "failures": failures, "claims": claims, "no_lesson": False,
            "readability": read, "notes": list(read["notes"])}


def user_prompt(packet: Dict[str, Any], *, previous: Optional[Dict[str, Any]] = None,
                fixes: Optional[Sequence[str]] = None) -> str:
    """The packet as the model's message; with `previous` and `fixes`, the rewrite request."""
    text = ("Study this position and answer in the JSON shape you were given.\n\n"
            + json.dumps(packet, indent=1, default=str))
    if previous is not None:
        text += ("\n\nYou already answered once. Here is that answer:\n"
                 + json.dumps({k: previous.get(k) for k in ("no_lesson", "mechanism", "reason", "claims")},
                              indent=1, default=str)
                 + "\n\nIt was checked against the board and the writing rules. Fix every point below and "
                 "answer again in full. Keep every claim that replayed; drop or correct the ones that did "
                 "not; rewrite the reason so each sentence has at most fourteen words and uses only the "
                 "words a ten-year-old owns.\n- " + "\n- ".join(fixes or []))
    return text


__all__ = ["CLAIM_KINDS", "CLAIM_SCHEMA", "HARD_WORDS", "SENTENCE_WORD_LIMIT", "SYSTEM_PROMPT", "board_facts",
           "build_packet", "check_claim", "facts_from_claims", "gate_text", "open_engine", "owner_on_square",
           "readability", "replay", "run_gate", "user_prompt"]
