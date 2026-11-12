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
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import chess
import chess.engine

logger = logging.getLogger(__name__)

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
    """SAN tokens in a line written as 'Qg6 7. Bb5+ Nc6', move numbers dropped.

    Also the glued forms the engine lines carry: '6...d6' -> 'd6',
    '7.cxd4' -> 'cxd4'. Until 2026-11-11 a glued first token stopped the
    packet's material ledger at move one, so every study was told material
    did not change along either line (6.c3 of 2d86e1f9 wins a pawn back).
    """
    out = []
    for t in str(text or "").split():
        t = re.sub(r"^\d+\.(\.\.)?", "", t)
        if t:
            out.append(t)
    return out


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


def material_balance(board: chess.Board, side: str) -> int:
    """That side's material minus the other side's, in centipawns."""
    m = material(board)
    other = "black" if side == "white" else "white"
    return m[side] - m[other]


def material_now(board: chess.Board, mover: chess.Color) -> Dict[str, Any]:
    """Who is ahead in material before the move, in words the model can repeat."""
    side = "white" if mover == chess.WHITE else "black"
    bal = material_balance(board, side)
    pawns = abs(bal) // 100
    if bal == 0:
        plain = "material is level"
    else:
        amount = f"{pawns} pawn" + ("s" if pawns != 1 else "") if bal % 100 == 0 else f"{abs(bal)} cp"
        plain = f"the mover is {amount} {'up' if bal > 0 else 'down'}"
    return {"mover_minus_opponent_cp": bal, "plain": plain}


def material_along(base: chess.Board, line: Sequence[str], mine: str, theirs: str) -> Dict[str, Any]:
    """Material change for `mine` along an engine line, replayed move by move.

    Records how many moves actually replayed, so a line that stops early can
    never again pass as "no change" (the 2026-11-11 bug: zero moves replayed,
    zero change reported, on every study).
    """
    sans = _san_only(" ".join(str(x) for x in (line or [])))
    b = base.copy()
    start = material(b)
    replayed = 0
    for san in sans:
        try:
            b.push_san(san)
        except Exception:                               # noqa: BLE001
            break
        replayed += 1
    end = material(b)
    return {"mover_material_change_cp": (end[mine] - start[mine]) - (end[theirs] - start[theirs]),
            "replayed_moves": replayed, "line_moves": len(sans), "line": list(line or [])}


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
                 live_engine_said: Optional[Dict[str, Any]] = None,
                 card_lines: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Everything the model may reason from. Engine lines, board facts, probes.

    `card_lines` are the two lines the review card plays out beside the caption
    (stored analysis, `pv_after_played` / `pv_after_best`). They can differ from
    this packet's own lines: on 6.e5 (2d86e1f9) the card plays c3 dxc3 Bxf7+
    Kxf7 Qd5+ while the packet's best reply was d6, so the study explained
    cxd4 under a line that never plays it (2026-11-12).
    """
    root = chess.Board(fen_before)
    mover = root.turn
    played = root.copy()
    played.push_san(played_san)

    with open_engine(engine_path) as eng:
        root_lines = lines(eng, root, mover, depth, 5, 8)
        # A stored best that IS the move played (the live engine's
        # "engine_choice", studied since 2026-11-05) would make the better
        # line the played line; take the engine's next candidate instead.
        if better_san and better_san.strip().rstrip("+#!?") == played_san.strip().rstrip("+#!?"):
            better_san = None
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
        mine = "white" if mover == chess.WHITE else "black"
        theirs = "black" if mine == "white" else "white"
        for label, base, ls in (("after_played", played, after_played), ("after_better", better, after_better)):
            if not ls:
                continue
            ledger[label] = material_along(base, ls[0]["line"], mine, theirs)
            # Counted from the position BEFORE the move, so a capture made by
            # the move itself is in the number too.
            ledger[label]["mover_material_change_from_before_the_move_cp"] = (
                material_balance(base, mine) - material_balance(root, mine)
                + ledger[label]["mover_material_change_cp"])

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
        "material_now": material_now(root, mover),
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
        "lines_shown_on_the_card": shown_lines(card_lines, played_san),
    }


def shown_lines(card_lines: Optional[Dict[str, Any]], played_san: str) -> Optional[Dict[str, Any]]:
    """The card's two lines as full SAN lists from the position before the move, or None."""
    if not card_lines:
        return None
    def clean(seq):
        return [m for m in _san_only(" ".join(str(x) for x in (seq or [])))]
    played_tail = clean(card_lines.get("pv_after_played"))
    better = str(card_lines.get("best_move_san") or "").strip()
    better_tail = clean(card_lines.get("pv_after_best"))
    if not played_tail and not (better and better_tail):
        return None
    return {
        "note": ("The review card plays these two lines out, move by move, beside your words. "
                 "They come from the game's stored analysis and can differ from the engine lines above."),
        "played_line": [played_san] + played_tail if played_tail else None,
        "better_move_on_card": better or None,
        "better_line": [better] + better_tail if better and better_tail else None,
    }


def settled_before_the_model(packet: Dict[str, Any], rating: Optional[int] = None) -> Optional[str]:
    """Why there is no lesson, when the packet's own engine lines already say so; else None.

    A question the engine already answers is not asked of a model: when the
    better move is no real improvement at the packet's depth, there is no
    mechanism to find, and a model asked for one may invent it (2026-11-11,
    13...e6: Opus 5.5 wrote a false "Kd8 was better"). The gap is graded by the
    live Why button's own table (differential.classify_gap), so the two never
    disagree on what counts as no real difference.

    Not a rule here: "lost after either move". Tried 2026-11-11 at ten pawns,
    it also silenced 14...Ke7 (-1307 vs -1607), a true and published lesson:
    a lost side can still lose a whole extra bishop.
    """
    after_played = (packet.get("after_played") or {}).get("best_replies_cp_for_mover") or []
    after_better = (packet.get("after_better") or {}).get("best_replies_cp_for_mover") or []
    if not after_played or not after_better:
        return None
    played_cp, better_cp = int(after_played[0]["cp"]), int(after_better[0]["cp"])
    played, better = packet.get("played_san"), packet.get("better_san")
    from services.reasoning.differential import classify_gap
    if classify_gap(better_cp - played_cp, rating) == "good":
        return (f"{better} is no real improvement on {played}: {better_cp} against {played_cp} "
                f"for the side to move at the packet's depth.")
    return None


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
- Read material FIRST. `material_now` says who is ahead before the move. `material_along_best_lines` says how material changes along each engine line, counted from before the move (`mover_material_change_from_before_the_move_cp`). If the better move wins material back or the move played loses some, that IS the lesson: say which pawn or piece, and how the better move gets it.
- A threat in `shared_threat_probes` is a lesson only when it survives: look at `mover_answers_with`. If that answer takes the attacking piece or moves the target away for free, the threat does not land and must not be your mechanism. When one does survive, it is where a mechanism often hides: a threat both moves allow that only the better move answers well.
- Any threat you claim must still work after the other side's best reply. The gate replays the engine's best reply and holds a reason whose threat never lands.
- If the packet shows no mechanism, only that the position is a little worse with nothing concrete, set `no_lesson` true and say why in one line. That is a real and useful answer. Do not invent a lesson.
- `live_engine_said` is what the quick engine on the site answered when the player asked. Its `reason` `no_gap` means it measured no real difference between the two moves; `engine_choice` means the move played was its own first choice. The card still called the move a fault. If the lines here agree with the quick engine, set `no_lesson` true and say so in one line; if they show a real difference the quick engine missed, that difference is the lesson.
- Do not read a threat off a line without checking it in the facts or probes: a move in a line is not a threat until the board says what it attacks.
- `lines_shown_on_the_card` (when present) are the two lines the player watches beside your words. Your reason must agree with them. If the better line shown holds a tactic (a check, a fork, a piece given up to win more), that is what the player will see: explain it. When the card's better line is not the other side's best reply, say both in plain words, the best reply first and then the card's line as "if they take": "c3 attacks your pawn on d4. If you take with dxc3, Bxf7+ and Qd5+ check your king and win your bishop on c5." Never describe a move that is in neither shown line as the main point.
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


THREAT_PLIES = 4


def threat_lands(claim: Dict[str, Any], fen_before: str, *, eng, depth: int = 16) -> Tuple[bool, Optional[str]]:
    """A threat must survive the threatened side's best reply.

    `check_claim` proves the attack is on the board. It cannot see that the
    other side simply answers it. 2026-11-11, two of the first four studies
    passed this way and were wrong: 6.e5 "you answer d5, attacking their
    bishop" (7.exd6 en passant removes the pawn) and 6.b3 "Qg6 hits g2 and
    their queen cannot help" (7.Bb5+ Nc6 8.Qe2 guards it).

    Applies to `attacks` / `undefended` claims made after a line, when the
    threatened side is to move and an enemy piece really hits the target.
    The threat lands when, in the engine's best line from there, within
    THREAT_PLIES half-moves, the attacking side takes on the target square,
    or the target steps away while the attacker still stands (a real tempo).
    Anything else is a threat the reply answers: (False, why).
    """
    if claim.get("kind") not in ("attacks", "undefended") or not (claim.get("after") or []):
        return True, None
    try:
        board = replay(fen_before, claim.get("after") or [])
        t = chess.parse_square(str(claim.get("target") or claim.get("subject") or ""))
    except ValueError:
        return True, None                               # check_claim already judged the shape
    target = board.piece_at(t)
    if target is None or board.turn != target.color:
        return True, None                               # not a threat the other side must answer
    attacker_color = not target.color
    if not board.attackers(attacker_color, t):
        return True, None
    attacker_sq = None
    if claim.get("kind") == "attacks":
        try:
            attacker_sq = chess.parse_square(str(claim.get("subject") or ""))
        except ValueError:
            attacker_sq = None
    info = eng.analyse(board, chess.engine.Limit(depth=depth))
    pv = list(info.get("pv") or [])[:THREAT_PLIES]
    if not pv:
        return True, None
    b = board.copy()
    reply_san = b.san(pv[0])
    for i, mv in enumerate(pv):
        mover = b.turn
        if mover == attacker_color and mv.to_square == t and b.is_capture(mv):
            return True, None
        if (i == 0 and mover == target.color and mv.from_square == t
                and target.piece_type != chess.PAWN):
            # A PIECE had to move: a tempo, if the attacker is still there. A
            # pawn stepping out of an attack answers it for nothing -- after
            # 6.b3 Qg6 the gate's own engine plays 7.g3 and g2 is simply gone
            # from the queen's line.
            after = b.copy()
            after.push(mv)
            if attacker_sq is None or after.piece_at(attacker_sq) is not None:
                return True, None
        b.push(mv)
    line = board.variation_san(pv)
    return False, f"the threat on {chess.square_name(t)} never lands: best reply {reply_san} ({line})"


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
    needs_engine = any(
        c.get("kind") in ("capture_loses", "line_better")
        or (c.get("kind") in ("attacks", "undefended") and (c.get("after") or []))
        for c in claims)
    eng = None
    if needs_engine:
        try:
            eng = open_engine(engine_path)
        except Exception:                               # noqa: BLE001
            # Fail closed: every engine-backed claim is held below.
            logger.warning("why gate: no engine at %r", engine_path)
            eng = None
    try:
        for c in claims:
            ok, why = check_claim(c, fen_before, eng=eng, depth=depth)
            if ok and c.get("kind") in ("attacks", "undefended") and (c.get("after") or []):
                # True on the board is not enough: the threat must survive the
                # threatened side's best reply (threat_lands).
                if eng is None:
                    ok, why = False, "no engine to check the threat survives the reply"
                else:
                    ok, why = threat_lands(c, fen_before, eng=eng, depth=depth)
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


# --- engine tools: how the agents check a line instead of trusting it -----------
# Appended to the system prompts when the worker runs the agents with the engine
# (scripts/why_engine_mcp.py). Written from how the Bc5 case was settled by hand
# on 2026-11-12: a depth-20 packet line misled the checker; depth 26 and a
# comparison of the two lines showed the real difference.

WRITER_TOOLS_NOTE = """

You have a chess engine. Use it. The packet is a starting point at modest depth and its lines can be wrong.
Tools: `analyse` (engine lines from the position before the move played, after any SAN moves you give, at a depth you choose) and `board` (the board as text, material, and pieces attacked with nothing guarding them).
How to work, in this order:
1. Run `analyse` at depth 24 or more after the move played (moves: [played]) and after the better move (moves: [better]). Note both scores and both lines.
2. Find the concrete difference: play each line forward with `board` and see what changes. Which piece or pawn is won or lost, which square or piece is attacked, what one move does that the other does not.
3. Test your mechanism before you write it. If you say the move played allows something, check that the better move does NOT allow the same thing: play the better move's line and look. If the same thing happens after both moves, it is not the reason; find another one. If you say there is a threat, play it and check the other side's best reply.
4. If after testing the difference is small and nothing concrete explains it, answer no_lesson. That is a good answer.
Use about ten to fifteen tool calls, then answer in the JSON shape. Every claim is still replayed by a machine afterwards, so write claims exactly as the schema says, with `after` lines starting from the position before the move played."""

CHECKER_TOOLS_NOTE = """

You have a chess engine. Use it. The packet is at modest depth and its lines can be wrong; do not base your verdict on a packet line you have not checked.
Tools: `analyse` (engine lines from the position before the move played, after any SAN moves you give, at a depth you choose) and `board` (the board as text, material, and pieces attacked with nothing guarding them).
How to work:
1. Before reading the study, run `analyse` at depth 24 or more after the move played and after the better move, and write your own reading from those lines.
2. Test the study's central claim twice: it must happen after the move played, and it must NOT happen (or happen worse) after the better move. If both moves lead to the same thing, the study names a side fact, not the reason.
3. Test your own reading the same way before you use it to reject the study. Reject only for a reason you checked with the engine.
Use about ten tool calls, then answer in the JSON shape."""


# --- the checker: a second agent reads the study before it goes live ------------

CHECK_SYSTEM_PROMPT = """You are a senior chess coach checking a colleague's explanation before a player reads it. The player is rated 600 to 1500 and will trust it.

You get the same packet the colleague had (the position, the move played, the better move, engine lines, board facts, material along each line) and the colleague's study: a short reason and the claims behind it. A machine has already replayed every claim on the board, so each claim on its own is true. Your job is the part the machine cannot do: is this the REAL reason the better move is better?

Work in this order.
1. Before reading the study, read the packet yourself. Compare the line after the move played with the line after the better move, and the material change along each. Write in `own_reading` one sentence: the main concrete difference between the two moves. If the lines show no real difference, say that.
2. Now read the study. Agree only if ALL of these hold:
   - It names the same main difference you found, or a true and equally central one. A true side fact that is not why the move is worse is a disagree.
   - Every sentence is true on the board and in the lines. A sentence that suggests something false is a disagree, even if each word could be defended.
   - It does not say the better move wins or saves something that the better move's line shows it does not.
   - "You/your" and "the opponent/their" match the packet's `pronouns` field.
   - When the packet has `lines_shown_on_the_card`, the study agrees with them, and if the better line shown holds a tactic (a check, a fork, a piece given up to win more), the study explains it. A study that talks about a different branch and leaves the shown tactic unexplained is a disagree: the player watches that line beside the words.
   - A player could act on it next game.
3. If you are unsure, the verdict is disagree. A wrong explanation shown to a player does more harm than a good one held back for a person to read.

`problem`: empty when you agree; otherwise one or two plain sentences naming exactly what is wrong."""

CHECK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["own_reading", "verdict", "problem"],
    "properties": {
        "own_reading": {"type": "string", "description": "the main difference between the two moves, from the packet alone"},
        "verdict": {"type": "string", "enum": ["agree", "disagree"]},
        "problem": {"type": "string"},
    },
}


def check_prompt(packet: Dict[str, Any], study: Dict[str, Any]) -> str:
    """The checker's message: the packet first, then the study to judge."""
    shown = {"reason": study.get("reason"), "mechanism": study.get("mechanism_label") or study.get("mechanism"),
             "claims": [{k: c.get(k) for k in ("kind", "label", "after", "subject", "target", "side",
                                                "worse_line", "better_line", "capture_san")
                         if c.get(k) not in (None, [], "")}
                        for c in (study.get("claims") or [])]}
    return ("The packet:\n" + json.dumps(packet, indent=1, default=str)
            + "\n\nThe colleague's study, to judge after you have written your own reading:\n"
            + json.dumps(shown, indent=1, default=str))


def check_verdict(answer: Dict[str, Any]) -> Dict[str, Any]:
    """The checker's answer, normalised. Anything but a clean "agree" is a disagree."""
    verdict = str((answer or {}).get("verdict") or "").strip().lower()
    return {"verdict": "agree" if verdict == "agree" else "disagree",
            "problem": str((answer or {}).get("problem") or "").strip(),
            "own_reading": str((answer or {}).get("own_reading") or "").strip()}


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


__all__ = ["CHECK_SCHEMA", "CHECK_SYSTEM_PROMPT", "check_prompt", "check_verdict",
           "CLAIM_KINDS", "CLAIM_SCHEMA", "HARD_WORDS", "SENTENCE_WORD_LIMIT", "SYSTEM_PROMPT", "board_facts",
           "build_packet", "check_claim", "facts_from_claims", "gate_text", "open_engine", "owner_on_square",
           "readability", "replay", "run_gate", "user_prompt"]
