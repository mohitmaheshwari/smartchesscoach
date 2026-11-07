"""The academy pilot: what a coach and a parent read about one child's week.

docs/academy_pilot_scope.md. Everything here is pure -- it takes the rows the
routes read and returns plain data -- so the tests can pin it without Mongo or
an engine.

Three ideas carry the whole report, and each is checked on the board with
python-chess before a word about it is written, because a stored label can be
wrong (an 18% disagreement was measured on lesson outcomes on 2026-11-05, and
one of Mohit's own cards that week called an even queen trade a lost queen):

  * a habit       -- a move graded mistake or blunder that either put a piece
                     where it can be taken, or left an attacked piece where it
                     was;
  * a good moment -- a piece was under attack and the child's move, graded
                     good or better, saved it without leaving another behind;
  * homework      -- the biggest single slip from winning to not winning, in a
                     game the child then lost or drew ("Win it back").

The engine decides what is a mistake (`execution_quality`); the board decides
what the mistake *was*. Nothing here asks a language model.

Stored evaluations in `move_observations` are white-relative (checked on prod
2026-11-05: a black win carried -642). `mover_eval` turns them round.

No digit ever reaches a parent or a child. Numbers choose the sentence; they
never appear in it (Mohit's standing rule, 2026-09-25).
"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from urllib.parse import quote

import chess

ROW_VERSION = "academy_week.v1"
IST = timezone(timedelta(hours=5, minutes=30))

ACADEMIES = "academies"
STAFF = "academy_staff"
BATCHES = "academy_batches"
STUDENTS = "academy_students"
WEEKS = "academy_student_weeks"
REPORTS = "academy_parent_reports"
ATTEMPTS = "academy_homework_attempts"

# v2 2026-11-05: deletion covers everything held about the child, not only games.
CONSENT_TEXT_VERSION = "consent.v3"

MISTAKE = {"mistake", "blunder"}
GOOD = {"good", "excellent", "best", "brilliant", "great"}
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
WORTH_SAVING = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)

# A habit is named only when it shows up in at least this many separate games
# in the week. One slip is a slip; a parent report that names a habit from one
# move would be the "a count is not a pattern" mistake this codebase already
# made once.
MIN_HABIT_GAMES = 2

# Homework: the position must have been clearly winning for the child and the
# one move must have taken it below a clear edge. Same bar as the Win it back
# prototype (scratchpad wib/, 2026-11-02): from at least +3 to under +1.
SLIP_FROM_CP = 300
SLIP_TO_CP = 100

# Less / same / more. Locked from data 2026-11-05 (scope section 6): 151
# consecutive-week pairs of real players, 12 weeks, both weeks with five or
# more analysed games. The week-to-week ratio of this habit's rate is mostly
# noise -- p10 0.31, p25 0.64, median 1.00, p75 1.37, p90 1.94. Cutting at
# 0.5 / 1.5 would call one week in five a change. At 0.4 / 2.5 "less" is
# named on 13% of pairs and "more" on 3%, so a label the coach acts on is a
# real move, not a noisy week. Below the game floor the coach sees "Not
# enough games".
TREND_MIN_GAMES = 5
TREND_LESS = 0.4
TREND_MORE = 2.5

HOMEWORK_MAX_CHILD_MOVES = 25
HOMEWORK_KEPT_PAWNS = 2.0


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def new_token() -> str:
    return secrets.token_urlsafe(18)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def week_start(now: Optional[datetime] = None) -> date:
    """Monday of the current week, in India time, as a date."""
    now = (now or datetime.now(timezone.utc)).astimezone(IST)
    return (now - timedelta(days=now.weekday())).date()


def week_bounds_utc(start: date) -> tuple:
    """The naive-UTC [start, end) of an IST week, matching `played_at_utc`."""
    begin = datetime(start.year, start.month, start.day, tzinfo=IST)
    end = begin + timedelta(days=7)
    return (begin.astimezone(timezone.utc).replace(tzinfo=None),
            end.astimezone(timezone.utc).replace(tzinfo=None))


def normalise_phone(raw: Any) -> Optional[str]:
    """Digits only, with India's country code added to a bare ten-digit number.

    Returns None for anything that cannot be a phone number, so a bad entry is
    refused at the form rather than producing a WhatsApp link that opens the
    wrong chat.
    """
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        digits = "91" + digits
    if not 11 <= len(digits) <= 15:
        return None
    return digits


def whatsapp_link(phone: Optional[str], text: str) -> str:
    """A click-to-chat link. Opens WhatsApp with the message filled in; the
    coach presses send. Automatic sending needs a ChessGuru WhatsApp Business
    number, which does not exist yet (scope section 4)."""
    base = f"https://wa.me/{phone}" if phone else "https://wa.me/"
    return f"{base}?text={quote(text)}"


def mover_eval(cp: Any, color: str) -> Optional[int]:
    if cp is None:
        return None
    try:
        value = int(cp)
    except (TypeError, ValueError):
        return None
    return value if color == "white" else -value


def _piece_word(piece_type: int) -> str:
    return chess.piece_name(piece_type)


# ---------------------------------------------------------------------------
# the board checks
# ---------------------------------------------------------------------------
def _losing_capture(board: chess.Board, square: int) -> Optional[chess.Move]:
    """A legal capture on `square` that wins something for the side to move.

    It wins when the capturing piece is worth less than the piece taken, or
    when the piece taken has no guard at all. Pinned guards still count as
    guards: the check errs towards silence, never towards a false claim.
    """
    target = board.piece_at(square)
    if target is None or target.color == board.turn:
        return None
    guarded = bool(board.attackers(target.color, square))
    best = None
    for move in board.legal_moves:
        if move.to_square != square:
            continue
        attacker = board.piece_at(move.from_square)
        if attacker is None:
            continue
        cheaper = VALUE.get(attacker.piece_type, 0) < VALUE.get(target.piece_type, 0)
        if cheaper or not guarded:
            if best is None or VALUE.get(attacker.piece_type, 0) < VALUE.get(
                    board.piece_at(best.from_square).piece_type, 0):
                best = move
    return best


def _hanging_after(board: chess.Board, color: bool) -> Dict[int, chess.Move]:
    """Every piece of `color` worth saving that the side to move can win now.

    `board.turn` must be the opponent of `color`.
    """
    out = {}
    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type not in WORTH_SAVING:
            continue
        capture = _losing_capture(board, square)
        if capture is not None:
            out[square] = capture
    return out


def _threats_before(board: chess.Board) -> Dict[int, chess.Move]:
    """Pieces of the side to move that the opponent could win if it were their
    turn. Empty when the side to move is in check, where flipping the turn
    would make an illegal position."""
    if board.is_check():
        return {}
    flipped = board.copy(stack=False)
    flipped.turn = not board.turn
    if not flipped.is_valid():
        return {}
    return _hanging_after(flipped, board.turn)


def _parse(fen: Any, uci: Any):
    try:
        board = chess.Board(str(fen))
        move = chess.Move.from_uci(str(uci))
    except (ValueError, TypeError):
        return None, None
    if move not in board.legal_moves:
        return None, None
    return board, move


def read_move(obs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """What one of the child's moves shows, checked on the board.

    Returns one event or None. Kinds: "left_takeable", "left_attacked",
    "saved_piece".
    """
    board, move = _parse(obs.get("fen_before"), obs.get("move_uci"))
    if board is None:
        return None
    quality = str(obs.get("execution_quality") or "").lower()
    mover = board.turn
    moved = board.piece_at(move.from_square)
    threats = _threats_before(board)
    san = board.san(move)
    after = board.copy(stack=False)
    after.push(move)
    hanging = _hanging_after(after, mover) if not after.is_game_over() else {}

    base = {
        "game_id": obs.get("game_id"),
        "ply": obs.get("ply"),
        "fen": board.fen(),
        "move_uci": move.uci(),
        "move_san": san,
        "quality": quality,
    }

    if quality in MISTAKE:
        # 1. The piece that moved can now be taken.
        if moved.piece_type in WORTH_SAVING and move.to_square in hanging:
            captured = board.piece_at(move.to_square)
            gave = VALUE.get(moved.piece_type, 0)
            got = VALUE.get(captured.piece_type, 0) if captured else 0
            if got < gave:
                capture = hanging[move.to_square]
                return {**base, "kind": "left_takeable",
                        "piece": _piece_word(moved.piece_type),
                        "square": chess.square_name(move.to_square),
                        "attacker": _piece_word(after.piece_at(capture.from_square).piece_type),
                        "attacker_uci": capture.uci(),
                        "free": not after.attackers(mover, move.to_square)}
        # 2. A piece was already under attack, and it is still there to take.
        for square, capture in threats.items():
            if square == move.from_square or square not in hanging:
                continue
            if after.piece_at(square) is None:
                continue
            reply = hanging[square]
            return {**base, "kind": "left_attacked",
                    "piece": _piece_word(board.piece_at(square).piece_type),
                    "square": chess.square_name(square),
                    "attacker": _piece_word(after.piece_at(reply.from_square).piece_type),
                    "attacker_uci": reply.uci(),
                    "free": not after.attackers(mover, square)}
        return None

    if quality in GOOD and threats and not hanging:
        square, capture = max(threats.items(),
                              key=lambda kv: VALUE.get(board.piece_at(kv[0]).piece_type, 0))
        return {**base, "kind": "saved_piece",
                "piece": _piece_word(board.piece_at(square).piece_type),
                "square": chess.square_name(square),
                "attacker": _piece_word(board.piece_at(capture.from_square).piece_type),
                "attacker_uci": capture.uci()}
    return None


def safe_better_move(fen: str, uci: Optional[str]) -> Optional[str]:
    """The engine's better move, kept only if it does not itself leave a piece
    to be taken. A best move can be a sacrifice; showing it next to "do not
    leave pieces where they can be taken" would teach the opposite."""
    if not uci:
        return None
    board, move = _parse(fen, uci)
    if board is None:
        return None
    mover = board.turn
    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        return move.uci()
    return None if _hanging_after(after, mover) else move.uci()


# ---------------------------------------------------------------------------
# a week
# ---------------------------------------------------------------------------
HABIT_OF_KIND = {"left_takeable": "piece_left_takeable", "left_attacked": "piece_left_attacked"}


def find_slip(observations: Iterable[Mapping[str, Any]],
              games_by_id: Mapping[str, Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The biggest one-move fall from winning, in a game the child lost or drew."""
    best = None
    for obs in observations:
        game = games_by_id.get(obs.get("game_id"))
        if not game or game.get("outcome") not in ("loss", "draw"):
            continue
        color = obs.get("color") or game.get("user_color")
        before = mover_eval(obs.get("eval_before"), color)
        after = mover_eval(obs.get("eval_after"), color)
        if before is None or after is None:
            continue
        if before < SLIP_FROM_CP or after >= SLIP_TO_CP:
            continue
        board, move = _parse(obs.get("fen_before"), obs.get("move_uci"))
        if board is None:
            continue
        drop = before - after
        key = (drop, str(game.get("played_at") or ""))
        if best is None or key > best[0]:
            best = (key, {
                "game_id": obs.get("game_id"), "ply": obs.get("ply"),
                "fen": board.fen(), "played_uci": move.uci(), "played_san": board.san(move),
                "color": color,
                "opponent_rating": game.get("opponent_rating"),
                "outcome": game.get("outcome"),
            })
    return best[1] if best else None


def summarise_week(games: Sequence[Mapping[str, Any]],
                   observations: Sequence[Mapping[str, Any]],
                   previous: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """One child's week, as data. `games` carry `outcome` already resolved."""
    games_by_id = {g["game_id"]: g for g in games if g.get("game_id")}
    played_days = {str(g.get("played_day")) for g in games if g.get("played_day")}
    outcomes = [g.get("outcome") for g in games]
    analysed = {o.get("game_id") for o in observations if o.get("game_id") in games_by_id}

    events = []
    for obs in observations:
        if obs.get("game_id") not in games_by_id:
            continue
        event = read_move(obs)
        if event:
            event["played_at"] = str(games_by_id[obs["game_id"]].get("played_at") or "")
            events.append(event)
    events.sort(key=lambda e: (e["played_at"], e.get("ply") or 0), reverse=True)

    habits: Dict[str, Dict[str, Any]] = {}
    for event in events:
        habit = HABIT_OF_KIND.get(event["kind"])
        if not habit:
            continue
        h = habits.setdefault(habit, {"id": habit, "events": [], "games": set()})
        h["events"].append(event)
        h["games"].add(event["game_id"])

    top = None
    for h in habits.values():
        if len(h["games"]) < MIN_HABIT_GAMES:
            continue
        if top is None or (len(h["games"]), len(h["events"])) > (len(top["games"]), len(top["events"])):
            top = h

    habit_out = None
    if top:
        evidence, seen = [], set()
        for event in top["events"]:
            if event["game_id"] in seen:
                continue
            seen.add(event["game_id"])
            evidence.append(event)
            if len(evidence) == 2:
                break
        habit_out = {
            "id": top["id"],
            "events": len(top["events"]),
            "games": len(top["games"]),
            "rate": round(len(top["events"]) / max(1, len(analysed)), 4),
            "evidence": evidence,
        }

    counts = {hid: {"events": len(h["events"]), "games": len(h["games"])} for hid, h in habits.items()}
    good = next((e for e in events if e["kind"] == "saved_piece"), None)
    slip = find_slip(observations, games_by_id)

    return {
        "row_version": ROW_VERSION,
        "games": {
            "count": len(games),
            "analysed": len(analysed),
            "days": len(played_days),
            "wins": outcomes.count("win"),
            "losses": outcomes.count("loss"),
            "draws": outcomes.count("draw"),
        },
        "habit": habit_out,
        "habit_counts": counts,
        "good_moment": good,
        "homework": slip,
        "trend": trend(habit_out, len(analysed), previous),
    }


def trend(habit: Optional[Mapping[str, Any]], analysed: int,
          previous: Optional[Mapping[str, Any]]) -> str:
    """"less" / "same" / "more" / "new" / "not_enough" for the coach's table."""
    if not habit:
        return "none"
    if analysed < TREND_MIN_GAMES or not previous:
        return "not_enough"
    prev_games = int((previous.get("games") or {}).get("analysed") or 0)
    if prev_games < TREND_MIN_GAMES:
        return "not_enough"
    prev_counts = (previous.get("habit_counts") or {}).get(habit["id"]) or {}
    prev_rate = float(prev_counts.get("events") or 0) / prev_games
    rate = float(habit.get("rate") or 0)
    if prev_rate == 0:
        return "new"
    if rate <= prev_rate * TREND_LESS:
        return "less"
    if rate >= prev_rate * TREND_MORE:
        return "more"
    return "same"


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------
HABIT_WORDS = {
    "piece_left_takeable": {
        "short": "Moves a piece where it can be taken",
        "headline": "{name} moves a piece to a square where it can be taken.",
        "body": "The idea is often good. The new square is not checked first.",
        "home_question": "Before you move, can that piece be taken?",
        "class_topic": "Check the new square before you move.",
    },
    "piece_left_attacked": {
        "short": "Leaves a piece under attack",
        "headline": "{name} leaves a piece under attack.",
        "body": "A piece was in danger, and the move played did not save it.",
        "home_question": "What is their last move attacking?",
        "class_topic": "Look at what their last move attacks.",
    },
}

TREND_WORDS = {
    "less": "Less often",
    "same": "About the same",
    "more": "More often",
    "new": "New this week",
    "not_enough": "Not enough games",
    "none": "—",
}

NUMBER_WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
                "Nine", "Ten"]


def number_word(n: int) -> str:
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else "Many"


def _caption(event: Mapping[str, Any]) -> str:
    piece, attacker = event["piece"], event["attacker"]
    if event["kind"] == "left_takeable":
        tail = "for free." if event.get("free") else "and win something."
        return f"The {piece} moved here. Their {attacker} could take it {tail}"
    if event["kind"] == "left_attacked":
        return f"Their {attacker} was attacking this {piece}. It stayed in danger."
    return f"Their {attacker} was attacking this {piece}. The move kept it safe."


def _board(event: Mapping[str, Any], good_uci: Optional[str] = None) -> Dict[str, Any]:
    arrows = []
    if event["kind"] == "saved_piece":
        arrows.append([event["attacker_uci"][:2], event["attacker_uci"][2:4], "red"])
        arrows.append([event["move_uci"][:2], event["move_uci"][2:4], "green"])
    else:
        arrows.append([event["move_uci"][:2], event["move_uci"][2:4], "red"])
        if good_uci:
            arrows.append([good_uci[:2], good_uci[2:4], "green"])
    flip = event["fen"].split(" ")[1] == "b"
    return {"fen": event["fen"], "arrows": arrows, "ring": event.get("square"),
            "orientation": "black" if flip else "white", "caption": _caption(event)}


def _say_list(items: Sequence[str]) -> str:
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _class_section(name: str, classes: Mapping[str, Any]) -> Dict[str, Any]:
    learnt, practised = list(classes.get("learnt") or []), list(classes.get("practised") or [])
    lines: List[str] = []
    if learnt:
        headline = f"{name} learnt {_say_list(learnt)}."
        if practised:
            lines.append(f"{name} also practised {_say_list(practised)}.")
    else:
        headline = f"{name} practised {_say_list(practised)}."
        lines.append("One more lesson on it comes first, then the next one.")
    if classes.get("all_done"):
        lines.append(f"{name} has finished the first lessons. Real games come next.")
    return {"kind": "classes", "eyebrow": "In class this week", "headline": headline, "lines": lines,
            "boards": []}


def report_blocked(week: Mapping[str, Any]) -> Optional[str]:
    """Why this week cannot go to a parent yet, in words, or None.

    Every game is still unread and there is no class to report, so the report
    would say only that it is not ready.
    """
    games = week.get("games") or {}
    classes = week.get("classes") or {}
    if int(games.get("count") or 0) and not int(games.get("analysed") or 0) and \
            not (classes.get("learnt") or classes.get("practised")):
        return "The games are still being read. Approve the report once they are."
    return None


def render_report(week: Mapping[str, Any], *, child_name: str, batch_name: str = "",
                  coach_name: str = "", coach_note: str = "",
                  better_moves: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """The parent's page, as words and boards. No digit anywhere."""
    name = (child_name or "Your child").strip()
    games = week.get("games") or {}
    better_moves = better_moves or {}
    out: Dict[str, Any] = {"child_name": name, "batch_name": batch_name,
                           "coach_name": coach_name, "sections": []}

    count, days = int(games.get("count") or 0), int(games.get("days") or 0)
    classes = week.get("classes") or {}
    in_class = bool(classes.get("learnt") or classes.get("practised"))
    if count == 0:
        lines = [f"{name} had lessons this week." if in_class else f"{name} did not play this week."]
    else:
        if days >= 5:
            lines = [f"{name} played most days this week."]
        elif days >= 2:
            lines = [f"{name} played on a few days this week."]
        else:
            lines = [f"{name} played on one day this week."]
        wins, losses = int(games.get("wins") or 0), int(games.get("losses") or 0)
        if count == 1:
            # "About even" was the fallback here, so a child who lost their
            # only game was told the week was even.
            lines.append("The game was a win." if wins
                         else "The game was a loss. That is normal while learning." if losses
                         else "The game was a draw.")
        elif wins > losses * 1.5 and wins >= 2:
            lines.append("There were more wins than losses.")
        elif losses > wins * 1.5 and losses >= 2:
            lines.append("There were more losses than wins. That is normal while learning.")
        else:
            lines.append("Wins and losses were about even.")
    out["sections"].append({"kind": "week", "lines": lines})

    if in_class:
        out["sections"].append(_class_section(name, classes))

    habit = week.get("habit")
    if count == 0 and in_class:
        # Nothing was played, so there is nothing to say about habits yet.
        question = "Can you show me what you learnt in class?"
    elif habit and habit.get("id") in HABIT_WORDS:
        words = HABIT_WORDS[habit["id"]]
        often = ("It happened in several games this week." if int(habit.get("games") or 0) >= 4
                 else "It happened in more than one game this week.")
        boards = [_board(e, better_moves.get(f"{e['game_id']}:{e['ply']}")) for e in habit["evidence"]]
        out["sections"].append({
            "kind": "habit", "eyebrow": "The habit we saw this week",
            "headline": words["headline"].format(name=name),
            "lines": [words["body"], often], "boards": boards,
            "key": [["red", f"{name}'s move"], ["green", "A safe move"]],
        })
        question = words["home_question"]
    elif count and not int(games.get("analysed") or 0):
        # Imported but not read yet: saying "nothing stood out" would be a
        # claim about games nobody has looked at.
        out["sections"].append({
            "kind": "habit", "eyebrow": "The habit we saw this week",
            "headline": "The games are still being read.",
            "lines": ["They will be in the next report."],
            "boards": [],
        })
        question = "Before you move, can that piece be taken?"
    else:
        out["sections"].append({
            "kind": "habit", "eyebrow": "The habit we saw this week",
            "headline": "No habit stood out this week.",
            "lines": ["We only name a habit when it shows up in more than one game."],
            "boards": [],
        })
        question = "Before you move, can that piece be taken?"

    good = week.get("good_moment")
    if good:
        lines = [f"The {good['piece']} was under attack. {name} kept it safe."]
        # The coach's own judgement, in the coach's name. It is not a claim
        # that the habit is gone; the report never makes that claim alone.
        confirmed_by = (good.get("confirmed_by_name") or "").strip()
        if confirmed_by:
            lines.append(f"{confirmed_by} checked this move. It shows {name} understands the idea.")
        out["sections"].append({
            "kind": "good", "eyebrow": "A good moment",
            "headline": f"Here {name} spotted the danger.",
            "lines": lines,
            "boards": [_board(good)],
            "key": [["green", f"{name}'s move"], ["red", "The danger"]],
            "confirmed": bool(confirmed_by),
        })

    homework = week.get("homework")
    if homework:
        flip = homework["fen"].split(" ")[1] == "b"
        out["sections"].append({
            "kind": "homework", "eyebrow": "This week's homework", "headline": "Win it back",
            "lines": [f"{name} was winning here. Then one move let the win slip away.",
                      "This week, play it again from this spot."],
            "boards": [{"fen": homework["fen"], "arrows": [],
                        "orientation": "black" if flip else "white"}],
        })

    out["sections"].append({"kind": "question", "eyebrow": "One question to ask at home",
                            "headline": question,
                            "lines": ["Ask it when you watch a game. One question is enough."]})
    note = (coach_note or "").strip()
    if note:
        out["sections"].append({"kind": "note",
                                "eyebrow": f"From {coach_name}" if coach_name else "From the coach",
                                "lines": [note]})
    out["footer"] = "This report shows habits we can see in the games. It is not a score or a test."
    return out


def needs_coach(student: Mapping[str, Any], week: Optional[Mapping[str, Any]],
                homework_status: str) -> Optional[str]:
    """Why this child needs the coach this week, in words, or None."""
    consent = (student.get("consent") or {}).get("status")
    if consent != "given":
        return "Waiting for the parent to agree"
    classes = (week or {}).get("classes") or {}
    if not week or not (week.get("games") or {}).get("count"):
        if classes.get("all_done"):
            return "Finished the lessons. Set up a class game"
        if classes.get("learnt") or classes.get("practised"):
            return None  # in class this week; that is what a child with no games should be doing
        if not student.get("lichess_username") and not student.get("chesscom_username"):
            return "No lessons this week"
        return "No games to read"
    if not (week.get("games") or {}).get("analysed"):
        return None  # imported, still being read; nothing to act on yet
    if week.get("trend") == "more":
        return "Getting worse"
    if week.get("homework") and homework_status == "not_started":
        return "Homework not started"
    return None


HOMEWORK_WORDS = {
    "none": "No homework this week",
    "not_started": "Not started",
    "playing": "Started",
    "kept": "Won it back",
    "held": "Held on",
    "lost": "Tried, not yet",
    "drawn": "Drawn",
}


def class_topic(weeks: Iterable[Optional[Mapping[str, Any]]]) -> Optional[Dict[str, Any]]:
    """The habit most children in the batch showed this week, if any two did."""
    tally: Dict[str, int] = {}
    for week in weeks:
        habit = (week or {}).get("habit")
        if habit and habit.get("id") in HABIT_WORDS:
            tally[habit["id"]] = tally.get(habit["id"], 0) + 1
    if not tally:
        return None
    habit_id, n = max(tally.items(), key=lambda kv: kv[1])
    if n < 2:
        return None
    return {"habit": habit_id, "children": n,
            "headline": HABIT_WORDS[habit_id]["class_topic"],
            "line": f"{number_word(n)} children showed this habit this week. "
                    "Their own positions are ready to use in class."}


# ---------------------------------------------------------------------------
# homework judging
# ---------------------------------------------------------------------------
def homework_verdict(board: chess.Board, child_color: str,
                     eval_pawns_white: Optional[float]) -> str:
    """"kept" / "lost" / "drawn" / "held" once a homework game stops."""
    child = chess.WHITE if child_color == "white" else chess.BLACK
    if board.is_checkmate():
        return "lost" if board.turn == child else "kept"
    if board.is_game_over():
        return "drawn"
    if eval_pawns_white is None:
        return "held"
    value = eval_pawns_white if child == chess.WHITE else -eval_pawns_white
    if value >= HOMEWORK_KEPT_PAWNS:
        return "kept"
    if value <= -HOMEWORK_KEPT_PAWNS:
        return "lost"
    return "held"


HOMEWORK_RESULT_WORDS = {
    "kept": "You won it back. Well played.",
    "held": "You held on. Try again to win it.",
    "lost": "Not this time. Try it again.",
    "drawn": "It ended in a draw. Try again to win it.",
}


# ---------------------------------------------------------------------------
# class games: two children of one batch, on the site
# ---------------------------------------------------------------------------
CLASS_GAMES = "academy_class_games"

CLASS_STATUS_WORDS = {
    "playing": "Playing",
    "white_won": "White won",
    "black_won": "Black won",
    "draw": "Draw",
}


def class_game_outcome(board: chess.Board, resigned: Optional[str] = None) -> Optional[Dict[str, str]]:
    """How a class game ended, or None while it goes on.

    `resigned` is the colour that resigned. A draw by repetition or the
    fifty-move rule is applied automatically: children do not claim draws.
    """
    if resigned in ("white", "black"):
        winner = "black" if resigned == "white" else "white"
        return {"status": f"{winner}_won", "result": "1-0" if winner == "white" else "0-1",
                "reason": "resigned"}
    if board.is_checkmate():
        winner = "black" if board.turn == chess.WHITE else "white"
        return {"status": f"{winner}_won", "result": "1-0" if winner == "white" else "0-1",
                "reason": "checkmate"}
    if (board.is_stalemate() or board.is_insufficient_material()
            or board.can_claim_threefold_repetition() or board.can_claim_fifty_moves()):
        return {"status": "draw", "result": "1/2-1/2", "reason": "draw"}
    return None


def class_game_pgn(white: str, black: str, sans: Sequence[str], result: str,
                   played: datetime, event: str) -> str:
    def tag(name, value):
        return '[%s "%s"]' % (name, str(value).replace('"', ""))
    headers = [tag("Event", event), tag("Site", "ChessGuru"), tag("Date", played.strftime("%Y.%m.%d")),
               tag("White", white), tag("Black", black), tag("Result", result)]
    body = []
    for i, san in enumerate(sans):
        if i % 2 == 0:
            body.append(f"{i // 2 + 1}.")
        body.append(san)
    body.append(result)
    return "\n".join(headers) + "\n\n" + " ".join(body) + "\n"


CLASS_RESULT_WORDS = {
    ("checkmate", True): "Checkmate. You won.",
    ("checkmate", False): "Checkmate. You lost this one.",
    ("resigned", True): "They resigned. You won.",
    ("resigned", False): "You resigned.",
}


def class_result_words(outcome: Optional[Mapping[str, str]], my_color: str) -> Optional[str]:
    if not outcome:
        return None
    if outcome.get("status") == "draw":
        return "The game is a draw."
    won = outcome.get("status") == f"{my_color}_won"
    return CLASS_RESULT_WORDS.get((outcome.get("reason"), won))
