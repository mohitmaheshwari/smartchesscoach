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
PICK_KINDS = {"attack", "defend", "develop", "escape", "other", "worried"}
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


# ---------------------------------------------------------------------------
# the player's own problem, and the story after the move
# (amendment 2, 2026-11-10: "first think how a human coach would take us
# through that position ... how player thinks really")
# ---------------------------------------------------------------------------
WORD_COUNT = {1: "one", 2: "two", 3: "three"}
_VAL = {chess.piece_name(t): v for t, v in cp.VALUE.items()}


def _his(piece: str, sq: str) -> str:
    return f"his {piece} on {sq}"


def _guards_of(board: chess.Board, me: bool, sq: int, skip: Optional[int] = None) -> List[Dict[str, Any]]:
    out = []
    for g in board.attackers(me, sq):
        if g == skip:
            continue
        out.append({"sq": chess.square_name(g), "piece": cp._name(board, g),
                    "pinned": board.is_pinned(me, g), "pinned_by": cp._pinner(board, me, g)})
    return out


def own_problem(before: chess.Board, move: chess.Move) -> Optional[Dict[str, Any]]:
    """The piece of the player's that was in danger before the move, and why
    its guard did not work. None when nothing was (or the side was in check).

    Board only: the side to move "passes" and we ask which of its pieces the
    opponent could then win by legal exchange.
    """
    if before.is_check():
        return None
    me = before.turn
    from services.caption_facts import legally_hanging_pieces
    passed = before.copy(stack=False)
    passed.push(chess.Move.null())
    try:
        hanging = legally_hanging_pieces(passed, me, HANG_FLOOR_CP)
    except ValueError:
        return None
    if not hanging:
        return None
    top = hanging[0]
    sq = chess.parse_square(top["square"])
    attackers = [{"sq": chess.square_name(a), "piece": cp._name(before, a)}
                 for a in before.attackers(not me, sq)]
    guards = _guards_of(before, me, sq)
    live = [g for g in guards if not g["pinned"]]
    if guards and not live:
        issue = "pinned"
    elif not guards:
        issue = "no_guard"
    elif min((cp.VALUE[before.piece_type_at(a)] for a in before.attackers(not me, sq)), default=100)             < cp.VALUE[before.piece_type_at(sq)]:
        issue = "cheaper_attacker"
    else:
        issue = "outnumbered"
    after = before.copy(stack=False)
    after.push(move)
    if move.from_square == sq:
        how = "moved"
        still = chess.square_name(move.to_square) in {h["square"] for h in legally_hanging_pieces(after, me, HANG_FLOOR_CP)}
    else:
        still = top["square"] in {h["square"] for h in legally_hanging_pieces(after, me, HANG_FLOOR_CP)}
        how = "guards" if sq in after.attacks(move.to_square) else ("breaks_pin" if issue == "pinned" and not any(
            after.is_pinned(me, chess.parse_square(g["sq"])) for g in guards if after.piece_at(chess.parse_square(g["sq"]))) else None)
    return {"sq": top["square"], "piece": top["piece_type"], "attackers": attackers,
            "guards": guards, "issue": issue, "solved": not still, "how": how}


def piece_story(before: chess.Board, move: chess.Move, target_sq: int,
                later_rows: Sequence[Mapping[str, Any]], max_own_moves: int = 3) -> Optional[Dict[str, Any]]:
    """What happened to the piece after the move, from the stored game rows:
    how many more of the player's moves left it there, and who took it."""
    me = before.turn
    board = before.copy(stack=False)
    board.push(move)
    piece_type = board.piece_type_at(target_sq)
    if piece_type is None:
        return None
    steps: List[Dict[str, Any]] = []
    left_there = 0
    end: Dict[str, Any] = {"kind": "open"}
    for row in later_rows:
        fen, san = row.get("fen_before"), row.get("move_san")
        if not fen or not san:
            break
        try:
            rb = chess.Board(fen)
        except Exception:
            break
        if rb.board_fen() != board.board_fen() or rb.turn != board.turn:
            break  # stored rows and the board disagree: stop the story here
        try:
            mv = board.parse_san(san)
        except Exception:
            break
        if board.turn != me:
            if mv.to_square == target_sq and board.is_capture(mv):
                won = board.piece_type_at(mv.from_square)
                after = board.copy(stack=False)
                after.push(mv)
                end = {"kind": "taken", "san": board.san(mv), "lost": chess.piece_name(piece_type),
                       "won": chess.piece_name(won), "can_recapture": bool(after.attackers(me, target_sq))}
                break
            steps.append({"by": "him", "san": board.san(mv)})
            board.push(mv)
            continue
        if left_there >= max_own_moves:
            break
        my_san = board.san(mv)
        board.push(mv)
        from services.caption_facts import legally_hanging_pieces
        if board.piece_type_at(target_sq) != piece_type or board.color_at(target_sq) != me:
            end = {"kind": "moved", "san": my_san}
            break
        if chess.square_name(target_sq) not in {h["square"] for h in legally_hanging_pieces(board, me, HANG_FLOOR_CP)}:
            end = {"kind": "safe", "san": my_san}
            break
        steps.append({"by": "you", "san": my_san})
        left_there += 1
    return {"steps": steps, "left_there": left_there, "end": end}


def story_lines(m: Mapping[str, Any]) -> List[str]:
    """The story in plain words. Only when he did not take it at once."""
    st = m.get("story") or {}
    steps, end = st.get("steps") or [], st.get("end") or {}
    if not steps and end.get("kind") not in ("moved", "safe"):
        return []
    t = m.get("target") or {}
    piece, sq = t.get("piece"), t.get("sq")
    lines: List[str] = []
    first = steps[0] if steps else {"by": "you"}
    if first["by"] == "him":
        lines.append(f"He didn't take it. He played {first['san']}.")
        rest = steps[1:]
    else:
        rest = steps
    # Only up to the last move of yours that left it there.
    last_you = max((i for i, s_ in enumerate(rest) if s_["by"] == "you"), default=-1)
    rest = rest[:last_you + 1]
    yours = [s_ for s_ in rest if s_["by"] == "you"]
    if len(yours) > 2:
        lines.append(f"Then you played {WORD_COUNT.get(len(yours), 'several')} more moves, "
                     f"and your {piece} was still on {sq}.")
    elif yours:
        # In move order: "you played Ne2, he played d5, and you played exd5".
        parts = [f"{'you' if s_['by'] == 'you' else 'he'} played {s_['san']}" for s_ in rest]
        said = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + ", and " + parts[-1]
        lines.append(f"Then {said}. Your {piece} was still on {sq}.")
    if end.get("kind") == "taken":
        if end.get("can_recapture") and _VAL.get(end["lost"], 0) > _VAL.get(end["won"], 100):
            lines.append(f"Then he took it with {end['san']}. You can take back, but that's your {end['lost']} for his {end['won']}.")
        elif not end.get("can_recapture"):
            lines.append(f"Then he took it with {end['san']}, and nothing of yours could take back.")
        else:
            lines.append(f"Then he took it with {end['san']}.")
    elif end.get("kind") == "moved":
        lines.append(f"Then you played {end.get('san')}, and it got away.")
    elif end.get("kind") == "safe":
        lines.append(f"Then you played {end.get('san')}, and it was safe again.")
    return lines


def seen_from_game(m: Mapping[str, Any]) -> Optional[str]:
    """When the player left the piece en prise on a later move, the game has
    already answered "did you see it?" (no). Otherwise None: ask."""
    return "no" if int((m.get("story") or {}).get("left_there") or 0) >= 1 else None


def build_tap_moment(event: Mapping[str, Any], row: Mapping[str, Any],
                     next_row: Optional[Mapping[str, Any]],
                     later_rows: Sequence[Mapping[str, Any]] = ()) -> Optional[Dict[str, Any]]:
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
        # What the player was dealing with before the move (their own problem),
        # and what happened to the piece over the next moves.
        problem = own_problem(before, move)
        if problem and problem["sq"] != target["sq"]:
            m["problem"] = problem
            m["practice"] = {"from": None,
                             "moves": {mv.uci(): {"san": before.san(mv)} for mv in before.legal_moves}}
        story = piece_story(before, move, tsq, later_rows)
        if story and story["steps"]:
            m["story"] = story
            m["story"]["lines"] = story_lines(m)
            m["seen_from_game"] = seen_from_game(m)
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
            m = build_tap_moment(ev, row, rows[i + 1] if i + 1 < len(rows) else None, rows[i + 1:])
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
            return ev, build_tap_moment(ev, row, rows[i + 1] if i + 1 < len(rows) else None, rows[i + 1:])
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
    better = [t for t in (raw.get("better") or [])[:3] if isinstance(t, str) and len(t) <= 5]
    # The game has the last word on "did you see it": a piece left there on a
    # later move was not seen, whatever the page sends.
    seen = m.get("seen_from_game") or (raw.get("seen_in_game") if raw.get("seen_in_game") in SEEN else "unsure")
    return {"picks": picks, "tapped": tapped, "seen_in_game": seen, "better": better,
            "seen_from_game": bool(m.get("seen_from_game"))}


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
# When the move answered a threat of his (the player's own problem), the habit
# is to check the new square as part of the answer.
KEEP_ANSWERING_THREAT = {
    "knight": "When you answer a threat, check the new square too: knight jumps first.",
    "near": "When you answer a threat, check the new square too: pieces close by first.",
    "far_diagonal": "When you answer a threat, check the new square too: long diagonals first.",
    "far_line": "When you answer a threat, check the new square too: long files and ranks first.",
}
KEEP_UNKNOWN_TACTIC = {
    "mate": "Before every move, look at every check you can give.",
    None: "Before every move, look for a capture that wins something.",
}


def keep_line(m: Mapping[str, Any], cause: Optional[str]) -> Optional[str]:
    """The "Keep this with you" line for this cause. None keeps the event's
    own principle (an unclear answer gets no special line)."""
    kind = m.get("kind")
    if kind == "landing" and m.get("problem") and cause in ("not_looking", "unknown_pattern"):
        return KEEP_ANSWERING_THREAT.get(_taker_kind(m) or "")
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
    left = int((m.get("story") or {}).get("left_there") or 0)
    if left and answers.get("seen_from_game"):
        t = m.get("target") or {}
        more = "one more move" if left == 1 else f"{WORD_COUNT.get(left, 'several')} more moves"
        seen = f"In the game your {t.get('piece')} stayed on {t.get('sq')} for {more}, so you didn't see it."
    lines = [first, seen]
    prob = m.get("problem")
    if prob and prob.get("solved"):
        lines.insert(0, f"{m.get('san')} looked after your {prob['piece']} on {prob['sq']}.")
    return lines


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


# ---------------------------------------------------------------------------
# "How else could you look after it?" (engine on one position, on request)
# ---------------------------------------------------------------------------
BETTER_DEPTH = 12
BETTER_MULTIPV = 4
BETTER_ACCEPT_CP = 80   # within this of the engine's best counts as a good answer


def move_facts(board: chess.Board, mv: chess.Move, problem: Mapping[str, Any]) -> Dict[str, Any]:
    """What a candidate move does about the player's problem, from the board."""
    me = board.turn
    from services.caption_facts import legally_hanging_pieces
    after = board.copy(stack=False)
    after.push(mv)
    psq = chess.parse_square(problem["sq"])
    hanging = {h["square"] for h in legally_hanging_pieces(after, me, HANG_FLOOR_CP)}
    moved_piece = cp._name(after, mv.to_square)
    takers = _takers(after, mv.to_square) if chess.square_name(mv.to_square) in hanging else []
    freed = None
    for g in problem.get("guards") or []:
        gs = chess.parse_square(g["sq"])
        if g.get("pinned") and after.piece_at(gs) and not after.is_pinned(me, gs) and psq in after.attacks(gs):
            freed = g
    return {
        "san": board.san(mv), "uci": mv.uci(), "moved": moved_piece,
        "moves_problem_piece": mv.from_square == psq,
        "guards_problem": psq in after.attacks(mv.to_square) and mv.from_square != psq,
        "breaks_pin": freed,
        "problem_still_hangs": (chess.square_name(mv.to_square) if mv.from_square == psq else problem["sq"]) in hanging,
        "lands_hanging": bool(takers), "takers": takers,
        "develops": cp.develops("white" if me == chess.WHITE else "black",
                                board.piece_type_at(mv.from_square), mv.from_square),
    }


def better_words(f: Mapping[str, Any], problem: Mapping[str, Any]) -> str:
    """One or two plain sentences about a good way to handle the problem."""
    p = f"your {problem['piece']} on {problem['sq']}"
    if f.get("breaks_pin"):
        g = f["breaks_pin"]
        t = f"{f['san']} breaks the pin, so your {g['piece']} on {g['sq']} guards {problem['sq']} again."
    elif f.get("guards_problem"):
        t = (f"{f['san']} guards {p}." if f.get("lands_hanging")
             else f"{f['san']} guards {p}, from a square he can't hit.")
    elif f.get("moves_problem_piece"):
        t = f"{f['san']} moves {p} to a safe square."
    elif not f.get("problem_still_hangs"):
        t = f"After {f['san']}, {p} can't be won any more."
    else:
        t = f"{f['san']} is a strong move here, even though {p} can still be taken."
    if f.get("develops") and f.get("moved") not in ("queen", "king"):
        t += " It also brings a piece into play."
    return t


def better_way(m: Mapping[str, Any], uci: Optional[str] = None) -> Dict[str, Any]:
    """Runs in a worker thread. The engine's best way to handle the player's
    problem, and (when `uci` is given) whether that tapped move is good too."""
    problem = m.get("problem")
    if not problem:
        return {"ok": False}
    board = chess.Board(m["fen_before"])
    me = board.turn
    tried = None
    if uci:
        try:
            tried = chess.Move.from_uci(uci)
        except Exception:
            tried = None
        if tried not in board.legal_moves:
            tried = None
    import chess.engine
    from config import STOCKFISH_PATH
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    try:
        infos = engine.analyse(board, chess.engine.Limit(depth=BETTER_DEPTH), multipv=BETTER_MULTIPV)
        score = {i["pv"][0]: i["score"].pov(me).score(mate_score=100000) for i in infos if i.get("pv")}
        if tried is not None and tried not in score:
            info = engine.analyse(board, chess.engine.Limit(depth=BETTER_DEPTH), root_moves=[tried])
            score[tried] = info["score"].pov(me).score(mate_score=100000)
    finally:
        engine.quit()
    top = max(score.values())
    played = chess.Move.from_uci(m["uci"])
    good = [mv for mv, sc in score.items() if top - sc <= BETTER_ACCEPT_CP and mv != played]
    facts = {mv: move_facts(board, mv, problem) for mv in good}
    # Prefer a good move that solves the problem on the board itself.
    ranked = sorted(good, key=lambda mv: (facts[mv]["problem_still_hangs"], facts[mv]["lands_hanging"], -score[mv]))
    out: Dict[str, Any] = {}
    if ranked:
        b = ranked[0]
        out["best"] = {"uci": b.uci(), "san": facts[b]["san"], "words": better_words(facts[b], problem)}
    if tried is not None:
        f = facts.get(tried) or move_facts(board, tried, problem)
        ok = tried in good and not f["lands_hanging"]
        if ok:
            words = "Yes. " + better_words(f, problem)
        elif f["lands_hanging"]:
            tk = f["takers"][0]
            words = f"Do the check: {_his(tk['piece'], tk['sq'])} can take it on {chess.square_name(tried.to_square)}."
        elif f["problem_still_hangs"]:
            words = f"After {f['san']}, your {problem['piece']} on {problem['sq']} can still be won."
        else:
            words = "That's playable, but there's a stronger way."
        out.update({"ok": ok, "san": f["san"], "words": words})
    return out
