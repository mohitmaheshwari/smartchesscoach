"""Game review: the child answers by tapping the board, and the coach's reply
depends on why the mistake happened.

docs/review_tap_reflection_scope.md (signed 2026-11-10). This extends the
review's "Before I explain" step. It does not replace the verified caption.

A stored review moment becomes a tap moment only when the board can grade it.
The board decides every answer; nothing here reads caption prose, and the page
never sends its own verdict.

  landing        one of the child's pieces can be taken after the move:
                 "which of his pieces could take it?"
  missed_tactic  there was a mate or a material win: "find the move"

Everything except the optional "is this other move also good?" check is
python-chess only, so it is cheap enough to build while the review page loads.
The tap flow's "try another square" step is out of scope (it needs every
legal move graded by the engine).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

import chess

from services import coach_plan_service as cp

logger = logging.getLogger(__name__)

KIND = "game_review_tap"
SCHEMA = "game_review_tap.v1"
PICK_KINDS = {"attack", "defend", "develop", "escape", "other"}
SEEN = {"no", "ok", "unsure"}
HANG_FLOOR_CP = 100      # a piece counts as takeable when it loses at least a pawn
ACCEPT_LOSS_CP = cp.ACCEPT_LOSS   # another move within this of the best also counts
TRY_DEPTH = 12

# Review concept / cause -> tap test. Anything not listed keeps the buttons.
_LANDING_CONCEPTS = {"piece_safety.simple_hang"}


def _stable_id(*parts: str) -> str:
    return "grt_" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]


def tap_kind(event: Mapping[str, Any]) -> Optional[tuple]:
    """(kind, pattern) for a stored review event, or None for "keep the buttons"."""
    cause = event.get("cause") if isinstance(event.get("cause"), Mapping) else {}
    concept = (event.get("concept") or {}).get("id")
    if cause.get("kind") == "legal_material_loss":
        return ("landing", None)
    lesson = cause.get("lesson_kind")
    if lesson == "exchange_sequence":
        return ("landing", None)
    if lesson == "missed_forced_mate":
        return ("missed_tactic", "mate")
    if lesson == "missed_material_opportunity":
        return ("missed_tactic", None)
    if not cause and concept in _LANDING_CONCEPTS:
        return ("landing", None)
    return None


def _target(event: Mapping[str, Any], before: chess.Board, move: chess.Move,
            after: chess.Board, reply: Optional[chess.Move] = None) -> Optional[Dict[str, str]]:
    """The child's piece the test is about: the one that can be taken."""
    me = before.turn
    cause = event.get("cause") if isinstance(event.get("cause"), Mapping) else {}
    if cause.get("kind") == "legal_material_loss":
        aff = cause.get("affected") or {}
        sq = aff.get("square")
        if isinstance(sq, str):
            s = chess.parse_square(sq)
            if after.color_at(s) == me:
                return {"sq": sq, "piece": cp._name(after, s)}
        return None
    if cause.get("lesson_kind") == "exchange_sequence":
        # Only when his actual reply took the piece that moved. Dry run on prod
        # 2026-11-10: without this, "g5" was asked about while he played Qe3,
        # a board fact that is not the lesson.
        s = move.to_square
        if reply is None or reply.to_square != s or not after.is_capture(reply):
            return None
        return {"sq": chess.square_name(s), "piece": cp._name(after, s)}
    from services.caption_facts import legally_hanging_pieces
    hanging = legally_hanging_pieces(after, me, HANG_FLOOR_CP)
    if not hanging:
        return None
    return {"sq": hanging[0]["square"], "piece": hanging[0]["piece_type"]}


def _takers(after: chess.Board, sq: int) -> List[Dict[str, Any]]:
    """His pieces that can legally capture on sq (a pinned piece cannot)."""
    out, seen = [], set()
    for mv in after.legal_moves:
        if mv.to_square != sq or not after.is_capture(mv) or mv.from_square in seen:
            continue
        seen.add(mv.from_square)
        kind, path = cp._kind(after, mv.from_square, sq)
        out.append({"sq": chess.square_name(mv.from_square), "piece": cp._name(after, mv.from_square),
                    "kind": kind, "path": path})
    return out


def _wins(cause: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    for c in cause.get("best_captures") or []:
        if isinstance(c, Mapping) and c.get("actor") == "initiator":
            return {"piece": c.get("captured_piece"), "sq": c.get("captured_square"),
                    "first": int(c.get("ply") or 1) == 1}
    return None


def build_tap_moment(event: Mapping[str, Any], row: Mapping[str, Any],
                     next_row: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The tap moment for one stored review move, or None when the board
    cannot grade it (then the review keeps its button question)."""
    kt = tap_kind(event)
    if not kt:
        return None
    kind, pattern = kt
    try:
        before = chess.Board(row["fen_before"])
        move = before.parse_san(row["move_san"])
    except Exception:
        return None
    me = before.turn
    color = "white" if me == chess.WHITE else "black"
    after = before.copy()
    san = before.san(move)
    after.push(move)
    to = move.to_square
    m: Dict[str, Any] = {
        "key": event.get("event_id"), "kind": kind, "pattern": pattern, "color": color,
        "date": None, "san": san, "uci": move.uci(), "from": chess.square_name(move.from_square),
        "to": chess.square_name(to), "moved": cp._name(after, to),
        "fen_before": before.fen(), "fen_after": after.fen(),
        "fen_reply": None, "reply_san": None, "reply_from": None, "think_s": None,
        **cp.intents(before, move),
    }
    reply = None
    if next_row and next_row.get("move_san") and next_row.get("fen_before"):
        try:
            nb = chess.Board(next_row["fen_before"])
            if nb.board_fen() == after.board_fen() and nb.turn == after.turn:
                reply = after.parse_san(next_row["move_san"])
        except Exception:
            reply = None

    if kind == "landing":
        target = _target(event, before, move, after, reply)
        if not target:
            return None
        tsq = chess.parse_square(target["sq"])
        answer = _takers(after, tsq)
        if not answer:
            return None  # the board says nothing can take it: do not ask
        m["target"] = target
        m["test"] = {"kind": "tap_pieces", "answer": answer}
        if reply is not None:
            m["reply_san"] = after.san(reply)
            m["reply_from"] = chess.square_name(reply.from_square)
            r = after.copy()
            r.push(reply)
            m["fen_reply"] = r.fen()
            if reply.to_square == tsq and after.is_capture(reply):
                lost = after.piece_type_at(tsq)
                won = after.piece_type_at(reply.from_square)
                can_recapture = bool(r.attackers(me, tsq))
                # "your knight for his knight" reads as a loss; say the cost
                # only when taking back still leaves the child behind.
                if not can_recapture or cp.VALUE.get(lost, 0) > cp.VALUE.get(won, 100):
                    m["cost"] = {"lost": chess.piece_name(lost), "won": chess.piece_name(won),
                                 "can_recapture": can_recapture}
    else:
        best_uci = row.get("best_move_uci")
        try:
            best = chess.Move.from_uci(str(best_uci))
        except Exception:
            return None
        if best not in before.legal_moves:
            return None
        cause = event.get("cause") or {}
        explain: Dict[str, Any] = {"targets": [], "mate": pattern == "mate"}
        if pattern is None:
            wins = _wins(cause)
            if not wins:
                return None
            explain["wins"] = wins
        m["test"] = {"kind": "find_move", "accept": [best.uci()],
                     "best": {"uci": best.uci(), "san": before.san(best)}, "explain": explain}
        # Destination dots and move names only; nothing here is graded.
        m["practice"] = {"from": None,
                         "moves": {mv.uci(): {"san": before.san(mv)} for mv in before.legal_moves}}
    m["best"] = {}
    return m


def attach_tap_moments(response: Dict[str, Any], stored_moves: Sequence[Mapping[str, Any]]) -> None:
    """Add `tap_moments` for the authorized, reflection-eligible events the
    response already carries. Reads only this game's stored rows."""
    wanted = {e.get("event_id") for e in response.get("teachable_events") or []
              if (e.get("display") or {}).get("reflection_eligible")}
    out = []
    rows = list(stored_moves or [])
    for i, row in enumerate(rows):
        ev = row.get("teachable_event") if isinstance(row, Mapping) else None
        if not isinstance(ev, Mapping) or ev.get("event_id") not in wanted:
            continue
        try:
            m = build_tap_moment(ev, row, rows[i + 1] if i + 1 < len(rows) else None)
        except Exception as exc:  # one bad row must not cost the page
            logger.warning("[review-tap] moment failed for %s: %s", ev.get("event_id"), exc)
            m = None
        if m:
            out.append(m)
    response["tap_moments"] = out


def find_stored_moment(stored_moves: Sequence[Mapping[str, Any]], event_id: str):
    rows = list(stored_moves or [])
    for i, row in enumerate(rows):
        ev = row.get("teachable_event") if isinstance(row, Mapping) else None
        if isinstance(ev, Mapping) and ev.get("event_id") == event_id:
            disp = ev.get("display") or {}
            if not (disp.get("authorized") and disp.get("reflection_eligible")):
                return None, None
            return ev, build_tap_moment(ev, row, rows[i + 1] if i + 1 < len(rows) else None)
    return None, None


# ---------------------------------------------------------------------------
# grading and the cause
# ---------------------------------------------------------------------------
def clean_answers(m: Mapping[str, Any], raw: Mapping[str, Any]) -> Dict[str, Any]:
    picks = []
    for p in (raw.get("picks") or [])[:8]:
        if isinstance(p, Mapping) and p.get("kind") in PICK_KINDS:
            sq = p.get("sq")
            picks.append({"kind": p["kind"], "sq": sq if isinstance(sq, str) and len(sq) == 2 else None})
    tapped = [t for t in (raw.get("tapped") or [])[:16] if isinstance(t, str) and len(t) <= 5]
    seen = raw.get("seen_in_game") if raw.get("seen_in_game") in SEEN else "unsure"
    return {"picks": picks, "tapped": tapped, "seen_in_game": seen}


def found_when_asked(m: Mapping[str, Any], tapped: Sequence[str], also_good: Sequence[str] = ()) -> bool:
    """Graded from the board. For find_move, `also_good` holds tapped moves the
    engine judged as good as the best (checked by the caller)."""
    test = m.get("test") or {}
    if test.get("kind") == "find_move":
        ok = set(test.get("accept") or []) | set(also_good)
        return any(t in ok for t in list(tapped)[:2])
    answer = {a["sq"] for a in test.get("answer") or []}
    return bool(answer) and answer <= set(tapped)


def _taker_kind(m: Mapping[str, Any]) -> Optional[str]:
    ans = (m.get("test") or {}).get("answer") or []
    return ans[0].get("kind") if ans else None


KEEP = {
    ("landing", "not_looking"):
        "Before any piece lands, look from that square: pieces close by, knight jumps, and long lines.",
    ("landing", "misjudged"):
        "When a piece can be taken, count what you lose and what you get back before you play it.",
    ("missed_tactic", "not_looking"): "Before every move: checks, captures, then attacks.",
    ("missed_tactic", "misjudged"):
        "When you spot a move that wins something, look at it properly before you play anything else.",
}
KEEP_UNKNOWN_LANDING = {
    "knight": "Before a piece lands, check every square a knight could jump to it from.",
    "near": "Before a piece lands, check the pieces right next to its square.",
    "far_diagonal": "Before a piece lands, look down every diagonal to that square, all the way to the edge.",
    "far_line": "Before a piece lands, look down the file and the rank to that square, all the way to the edge.",
}
KEEP_UNKNOWN_TACTIC = {
    "mate": "Before every move, look at every check you can give.",
    None: "Before every move, look for a capture that wins something.",
}


def keep_line(m: Mapping[str, Any], cause: Optional[str]) -> Optional[str]:
    """The "Keep this with you" line for this cause. None keeps the event's
    own principle (an unclear answer gets no special line)."""
    kind = m.get("kind")
    if cause == "unknown_pattern":
        if kind == "landing":
            return KEEP_UNKNOWN_LANDING.get(_taker_kind(m) or "")
        return KEEP_UNKNOWN_TACTIC.get(m.get("pattern"))
    return KEEP.get((kind, cause))


def summary(m: Mapping[str, Any], answers: Mapping[str, Any]) -> List[str]:
    """What the review shows on re-entry instead of the whole conversation."""
    found = answers.get("found_when_asked")
    if m.get("kind") == "landing":
        a = ((m.get("test") or {}).get("answer") or [{}])[0]
        what = f"his {a.get('piece')} on {a.get('sq')}"
    else:
        what = ((m.get("test") or {}).get("best") or {}).get("san") or "the move"
    seen = {"no": "In the game you didn't see it.",
            "ok": "In the game you saw it, and thought it was fine.",
            "unsure": "You weren't sure if you saw it in the game."}[answers.get("seen_in_game") or "unsure"]
    first = f"You found {what} when you looked." if found else f"When you looked, you didn't find {what}."
    return [first, seen]


def build_document(*, user_id: str, game_id: str, event: Mapping[str, Any], m: Mapping[str, Any],
                   answers: Mapping[str, Any]) -> Dict[str, Any]:
    cause = cp.cause_of(answers)
    now = datetime.now(timezone.utc).isoformat()
    return {
        "reflection_id": _stable_id(user_id, game_id, str(event.get("event_id"))),
        "reflection_kind": KIND, "schema_version": SCHEMA,
        "user_id": user_id, "game_id": game_id, "updated_at": now,
        "event": {"event_id": event.get("event_id"),
                  "concept_id": (event.get("concept") or {}).get("id"),
                  "quality_id": (event.get("evidence") or {}).get("quality_id"),
                  "kind": m.get("kind"), "pattern": m.get("pattern"), "source": "game_review"},
        "response": {**answers, "cause": cause, "keep_line": keep_line(m, cause),
                     "summary": summary(m, answers)},
    }


def public_tap_history(documents: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for d in documents or []:
        ev, r = d.get("event") or {}, d.get("response") or {}
        if not ev.get("event_id"):
            continue
        out.append({"event_id": ev["event_id"], "cause": r.get("cause"),
                    "keep_line": r.get("keep_line"), "summary": r.get("summary") or []})
    return out


def also_good_moves(m: Mapping[str, Any], tapped: Sequence[str]) -> List[str]:
    """Runs in a worker thread. Which tapped moves (other than the stored best)
    the engine rates within ACCEPT_LOSS_CP of the best. One short search."""
    test = m.get("test") or {}
    if test.get("kind") != "find_move":
        return []
    board = chess.Board(m["fen_before"])
    best = chess.Move.from_uci(test["best"]["uci"])
    tries = []
    for t in list(tapped)[:2]:
        try:
            mv = chess.Move.from_uci(t)
        except Exception:
            continue
        if mv != best and mv in board.legal_moves:
            tries.append(mv)
    if not tries:
        return []
    import chess.engine
    from config import STOCKFISH_PATH
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    try:
        me = board.turn
        infos = engine.analyse(board, chess.engine.Limit(depth=TRY_DEPTH),
                               multipv=len(tries) + 1, root_moves=[best, *tries])
        score = {i["pv"][0]: i["score"].pov(me).score(mate_score=100000) for i in infos if i.get("pv")}
    finally:
        engine.quit()
    top = max(score.values()) if score else None
    if top is None:
        return []
    return [mv.uci() for mv in tries if mv in score and top - score[mv] <= ACCEPT_LOSS_CP]
