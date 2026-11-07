"""First steps: rules classes for a child who has never played.

docs/first_steps_scope.md. Pure logic, no database. Every answer is decided
here by the rules of chess (python-chess), never by an engine's opinion and
never in the browser: the page sends a tap, this module says what it means.

A class is a list of items. Item kinds:

  tap_piece   tap every piece of one type ("Tap the rook")
  tap_reach   tap every square the piece on `from` can move to
  tap_take    tap the piece the piece on `from` can take
  choose      answer a yes/no question decided by the rules (is it check?)
  move_goal   make a move that does something (check, checkmate, promote...)
  stars       capture every black pawn with one piece, in as few moves as
              possible (the pawns stand still; "stars" is the historic name)
  game        a small game against the computer (pawn race, capture race,
              queen mate); the computer's moves come from simple fixed rules

Wrong answers carry a mistake kind ("jumped", "like_bishop", "into_check"...)
so the next class can start from what the child found hard.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import chess

CONTENT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "first_steps_classes.json")
SESSIONS = "academy_class_sessions"

LETTER = {chess.PAWN: "P", chess.KNIGHT: "N", chess.BISHOP: "B", chess.ROOK: "R",
          chess.QUEEN: "Q", chess.KING: "K"}
TYPE_OF = {v: k for k, v in LETTER.items()}
NAME = {"P": "pawn", "N": "knight", "B": "bishop", "R": "rook", "Q": "queen", "K": "king"}
LOOK = {
    "R": "Look for the one shaped like a castle tower.",
    "B": "Look for the one with a pointed hat.",
    "Q": "Look for the one with a crown of points.",
    "N": "Look for the horse.",
    "K": "Look for the one with a cross on top.",
    "P": "Look for the smallest piece.",
}
HOW = {
    "R": "The rook only goes in straight lines: up, down, left or right.",
    "B": "The bishop only goes diagonally, corner to corner.",
    "Q": "The queen goes in straight lines and diagonals.",
    "N": "The knight jumps in an L: two squares one way, then one to the side.",
    "K": "The king goes one square in any direction.",
    "P": "The pawn goes straight forward. It takes diagonally.",
}

# What a wrong tap means, said to the child. {p} is the piece's name.
MISTAKE_WORDS = {
    "wrong_piece": "That's the {tapped}. {look}",
    "own_piece": "That's your own piece. The {p} can't land on it.",
    "jumped": "Something is in the way there. The {p} can't jump over pieces.",
    "like_bishop": "That's a diagonal. The {p} can't go that way. That is how the bishop moves.",
    "like_rook": "That's a straight line. The {p} can't go that way. That's how the rook moves!",
    "like_knight": "That is a knight's jump. The {p} can't do that.",
    "too_far": "The king only goes one square at a time.",
    "into_check": "That square is attacked. The king can never move into check.",
    "pawn_backward": "Pawns never go backwards.",
    "pawn_sideways": "Pawns never go sideways.",
    "pawn_blocked": "Something is in front of the pawn. A pawn can't take straight ahead.",
    "pawn_two": "Only on its very first move can a pawn go two squares.",
    "pawn_diag_empty": "A pawn goes diagonally only when it takes a piece.",
    "off_line": "{how}",
    "not_on_line": "That piece is not on the {p}'s path.",
    "own_piece_take": "That's your own piece. You can only take the other side's pieces.",
    "protected": "That piece is protected. If the king took it, the king would be attacked.",
    "not_checker": "That piece isn't attacking the king. Find the one that is.",
    "wrong_choice": "Not quite. Look again.",
    "no_check": "That move doesn't attack the king. Find a move that gives check.",
    "check_not_mate": "That's check, but the king can still escape. Find checkmate.",
    "stalemate": "The king can't move, but it isn't in check. That is stalemate, a draw.",
    "not_goal": "That move is allowed, but it doesn't do what we need. Try another.",
    "leaves_check": "Your king is still in check after that. You must get out of check.",
    "illegal": "That move isn't allowed.",
    "extra_moves": "Done. It can be done in fewer moves.",
}


# ---------------------------------------------------------------------------
# content
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load_content() -> Dict[str, Any]:
    with open(CONTENT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def classes() -> List[Dict[str, Any]]:
    return sorted(load_content()["classes"], key=lambda c: c["order"])


def class_by_id(class_id: str) -> Optional[Dict[str, Any]]:
    return next((c for c in classes() if c["id"] == class_id), None)


def item_by_id(cls: Mapping[str, Any], item_id: str) -> Optional[Dict[str, Any]]:
    return next((it for it in cls["items"] if it["id"] == item_id), None)


# ---------------------------------------------------------------------------
# board helpers
# ---------------------------------------------------------------------------
def board_of(fen: str) -> chess.Board:
    return chess.Board(fen)


def _sq(name: str) -> int:
    return chess.parse_square(name)


def _names(squares) -> Set[str]:
    return {chess.square_name(s) for s in squares}


def _empty_reach(piece_type: int, square: int, color: bool = chess.WHITE) -> Set[int]:
    """Squares a piece reaches from `square` on an otherwise empty board."""
    b = chess.Board(None)
    b.set_piece_at(square, chess.Piece(piece_type, color))
    if piece_type == chess.PAWN:
        out = set()
        step = 8 if color == chess.WHITE else -8
        if 0 <= square + step < 64:
            out.add(square + step)
        start_rank = 1 if color == chess.WHITE else 6
        if chess.square_rank(square) == start_rank:
            out.add(square + 2 * step)
        return out
    return set(b.attacks(square))


def reach(board: chess.Board, square: int, ignore_checks: bool = False) -> Set[int]:
    """Where the piece on `square` may move, by the rules, ignoring whose turn it is.

    A king never steps onto an attacked square. Other pieces ignore checks: the
    rules classes for those pieces use boards without kings. ignore_checks is
    for the capture exercises, where the pawns are targets and attack nothing.
    """
    piece = board.piece_at(square)
    if piece is None:
        return set()
    color = piece.color
    own = board.occupied_co[color]
    if piece.piece_type == chess.PAWN:
        out = set()
        step = 8 if color == chess.WHITE else -8
        one = square + step
        if 0 <= one < 64 and board.piece_at(one) is None:
            out.add(one)
            start_rank = 1 if color == chess.WHITE else 6
            two = square + 2 * step
            if chess.square_rank(square) == start_rank and board.piece_at(two) is None:
                out.add(two)
        for t in chess.SquareSet(chess.BB_PAWN_ATTACKS[color][square]):
            target = board.piece_at(t)
            if target is not None and target.color != color:
                out.add(t)
        return out
    targets = {t for t in board.attacks(square) if not (chess.BB_SQUARES[t] & own)}
    if piece.piece_type == chess.KING and not ignore_checks:
        without = board.copy(stack=False)
        without.remove_piece_at(square)
        targets = {t for t in targets if not without.is_attacked_by(not color, t)}
    return targets


def classify_reach_tap(board: chess.Board, square: int, tapped: int) -> str:
    """The mistake kind of tapping `tapped` when asked where the piece on `square` can go."""
    piece = board.piece_at(square)
    letter = LETTER[piece.piece_type]
    target = board.piece_at(tapped)
    if target is not None and target.color == piece.color:
        return "own_piece"
    if piece.piece_type == chess.PAWN:
        df = chess.square_file(tapped) - chess.square_file(square)
        dr = chess.square_rank(tapped) - chess.square_rank(square)
        forward = 1 if piece.color == chess.WHITE else -1
        if dr * forward < 0:
            return "pawn_backward"
        if dr == 0:
            return "pawn_sideways"
        if df == 0 and dr == forward:
            return "pawn_blocked"
        if df == 0 and dr == 2 * forward:
            return "pawn_blocked" if board.piece_at(square + 8 * forward) or target else "pawn_two"
        if abs(df) == 1 and dr == forward:
            return "pawn_diag_empty"
        return "off_line"
    if piece.piece_type == chess.KING:
        if chess.square_distance(square, tapped) == 1:
            return "into_check"
        if tapped in _empty_reach(chess.QUEEN, square):
            return "too_far"
    elif tapped in _empty_reach(piece.piece_type, square):
        return "jumped"
    if letter != "B" and tapped in _empty_reach(chess.BISHOP, square):
        return "like_bishop"
    if letter != "R" and tapped in _empty_reach(chess.ROOK, square):
        return "like_rook"
    if letter != "N" and tapped in _empty_reach(chess.KNIGHT, square):
        return "like_knight"
    return "off_line"


def words(kind: str, letter: str, **extra: str) -> str:
    template = MISTAKE_WORDS.get(kind, MISTAKE_WORDS["off_line"])
    return template.format(p=NAME.get(letter, "piece"), how=HOW.get(letter, ""), **extra)


# ---------------------------------------------------------------------------
# answers for each item kind
# ---------------------------------------------------------------------------
def answers(item: Mapping[str, Any]) -> Set[str]:
    """The full answer set, decided by the rules. Squares, or moves as uci."""
    kind = item["kind"]
    if kind == "stars":
        return set(item["stars"])
    board = board_of(item["fen"])
    if kind == "tap_piece":
        color = chess.WHITE if item.get("color", "w") == "w" else chess.BLACK
        return _names(board.pieces(TYPE_OF[item["piece"]], color))
    if kind == "tap_reach":
        return _names(reach(board, _sq(item["from"])))
    if kind == "tap_take":
        return {s for s in _names(reach(board, _sq(item["from"]))) if board.piece_at(_sq(s))}
    if kind == "tap_checker":
        return _names(board.checkers())
    if kind == "choose":
        return {_choose_truth(item, board)}
    if kind == "move_goal":
        return {m.uci() for m in board.legal_moves if _meets_goal(board, m, item["goal"])}
    return set()


def _choose_truth(item: Mapping[str, Any], board: chess.Board) -> str:
    q = item["question"]
    if q == "is_check":
        return "yes" if board.is_check() else "no"
    if q == "is_checkmate":
        return "yes" if board.is_checkmate() else "no"
    if q == "is_stalemate":
        return "yes" if board.is_stalemate() else "no"
    if q == "same_colour":
        a, b = (_sq(s) for s in item["squares"])
        same = (chess.square_file(a) + chess.square_rank(a)) % 2 == (chess.square_file(b) + chess.square_rank(b)) % 2
        return "yes" if same else "no"
    raise ValueError(f"unknown question {q}")


def _meets_goal(board: chess.Board, move: chess.Move, goal: str) -> bool:
    after = board.copy(stack=False)
    after.push(move)
    if goal == "check":
        return after.is_check()
    if goal == "checkmate":
        return after.is_checkmate()
    if goal == "escape":
        return True  # every legal move gets out of check
    if goal == "promote":
        return move.promotion is not None
    if goal == "capture":
        return board.is_capture(move)
    raise ValueError(f"unknown goal {goal}")


# ---------------------------------------------------------------------------
# stars
# ---------------------------------------------------------------------------
def _stars_board(item: Mapping[str, Any], at: str, left: Optional[Sequence[str]] = None) -> chess.Board:
    """The exercise's position: walls are your own pawns, targets black pawns."""
    b = chess.Board(None)
    for w in item.get("walls", []):
        b.set_piece_at(_sq(w), chess.Piece(chess.PAWN, chess.WHITE))
    for t in (item["stars"] if left is None else left):
        b.set_piece_at(_sq(t), chess.Piece(chess.PAWN, chess.BLACK))
    b.set_piece_at(_sq(at), chess.Piece(TYPE_OF[item["piece"]], chess.WHITE))
    return b


def stars_par(item: Mapping[str, Any]) -> Optional[int]:
    """Fewest moves that capture every pawn, by breadth-first search."""
    stars = list(item["stars"])
    index = {s: i for i, s in enumerate(stars)}
    full = (1 << len(stars)) - 1
    start = (item["start"], 0)
    seen = {start}
    frontier = [start]
    depth = 0
    while frontier:
        nxt = []
        for at, mask in frontier:
            if mask == full:
                return depth
            left = [s for i, s in enumerate(stars) if not mask & (1 << i)]
            for t in _names(reach(_stars_board(item, at, left), _sq(at), ignore_checks=True)):
                m2 = mask | (1 << index[t]) if t in index else mask
                if (t, m2) not in seen:
                    seen.add((t, m2))
                    nxt.append((t, m2))
        frontier = nxt
        depth += 1
    return None


# ---------------------------------------------------------------------------
# games against the computer
# ---------------------------------------------------------------------------
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def _pawn_game_over(board: chess.Board) -> Optional[str]:
    """Pawn race and capture race: a pawn on the last rank wins for its side;
    a side with nothing left to move loses."""
    for sq in board.pieces(chess.PAWN, chess.WHITE):
        if chess.square_rank(sq) == 7:
            return "white"
    for sq in board.pieces(chess.PAWN, chess.BLACK):
        if chess.square_rank(sq) == 0:
            return "black"
    if not board.pieces(chess.PAWN, chess.BLACK) and board.piece_map() and all(
            p.color == chess.WHITE for p in board.piece_map().values()):
        return "white"
    if not any(True for _ in _plain_moves(board)):
        return "black" if board.turn == chess.WHITE else "white"
    return None


def _plain_moves(board: chess.Board):
    """Moves by the movement rules only. Race boards have no kings, so check
    does not exist there; promotion is not played out — reaching the end wins."""
    for sq, piece in board.piece_map().items():
        if piece.color != board.turn:
            continue
        for t in reach(board, sq):
            yield chess.Move(sq, t)


def computer_move(board: chess.Board, game: str) -> Optional[chess.Move]:
    """The computer's reply, by fixed rules a child can learn to beat."""
    moves = list(_plain_moves(board)) if game in ("pawn_race", "capture_race") else list(board.legal_moves)
    if not moves:
        return None
    if game in ("pawn_race", "capture_race"):
        me = board.turn

        def safe(m: chess.Move) -> bool:
            after = board.copy(stack=False)
            after.remove_piece_at(m.from_square)
            after.set_piece_at(m.to_square, board.piece_at(m.from_square))
            return not any(m.to_square in reach(after, s)
                           for s, p in after.piece_map().items() if p.color != me)

        def progress(m: chess.Move) -> int:
            r = chess.square_rank(m.to_square)
            return r if me == chess.WHITE else 7 - r

        wins = [m for m in moves if progress(m) == 7]
        if wins:
            return wins[0]
        captures = [m for m in moves if board.piece_at(m.to_square)]
        if captures:
            return max(captures, key=lambda m: (safe(m), progress(m)))
        return max(moves, key=lambda m: (safe(m), progress(m), -chess.square_file(m.to_square)))
    if game == "queen_mate":
        # The lone king keeps as many squares as it can, and goes for the centre.
        def room(m: chess.Move) -> Tuple[int, int]:
            after = board.copy(stack=False)
            after.push(m)
            after.turn = board.turn
            centre = -max(abs(3.5 - chess.square_file(m.to_square)), abs(3.5 - chess.square_rank(m.to_square)))
            return (sum(1 for _ in after.legal_moves), centre)
        captures = [m for m in moves if board.is_capture(m)]
        if captures:
            return captures[0]
        return max(moves, key=room)
    return moves[0]


def game_status(board: chess.Board, game: str, child: bool) -> Optional[str]:
    """None while playing; otherwise "won", "lost" or "draw" for the child."""
    if game in ("pawn_race", "capture_race"):
        winner = _pawn_game_over(board)
        if winner is None:
            return None
        child_side = "white" if child == chess.WHITE else "black"
        return "won" if winner == child_side else "lost"
    if board.is_checkmate():
        return "won" if board.turn != child else "lost"
    if board.is_stalemate() or board.is_insufficient_material():
        return "draw"
    return None


# ---------------------------------------------------------------------------
# grading one attempt
# ---------------------------------------------------------------------------
def _letter_on(board: chess.Board, name: str) -> Optional[str]:
    p = board.piece_at(_sq(name))
    return LETTER[p.piece_type] if p else None


def grade(item: Mapping[str, Any], answer: Mapping[str, Any], state: Optional[Mapping[str, Any]] = None
          ) -> Dict[str, Any]:
    """Judge one tap or move. Returns outcome ("right", "wrong", "ignored",
    "progress", "done"), the mistake kind, the words, and the new state.

    `state` carries what an item remembers between taps: squares found,
    where the star piece stands, the game's position.
    """
    state = dict(state or {})
    kind = item["kind"]
    if kind in ("tap_piece", "tap_reach", "tap_take", "tap_checker"):
        return _grade_tap(item, answer.get("square"), state)
    if kind == "choose":
        right = _choose_truth(item, board_of(item["fen"])) == answer.get("choice")
        return {"outcome": "right" if right else "wrong", "kind": None if right else "wrong_choice",
                "say": item.get("right") if right else item.get("why_wrong") or MISTAKE_WORDS["wrong_choice"],
                "state": state}
    if kind == "move_goal":
        return _grade_move_goal(item, answer.get("move"))
    if kind == "stars":
        return _grade_stars(item, answer.get("square"), state)
    if kind == "game":
        return _grade_game(item, answer.get("move"), state)
    raise ValueError(f"unknown item kind {kind}")


def _grade_tap(item: Mapping[str, Any], square: Optional[str], state: Dict[str, Any]) -> Dict[str, Any]:
    board = board_of(item["fen"])
    try:
        tapped = _sq(str(square))
    except ValueError:
        return {"outcome": "ignored", "state": state}
    want = answers(item)
    found = set(state.get("found", []))
    name = chess.square_name(tapped)
    kind = item["kind"]
    if name in want:
        if name in found:
            return {"outcome": "ignored", "state": state}
        found.add(name)
        state["found"] = sorted(found)
        all_found = kind != "tap_reach" or found >= want
        return {"outcome": "right" if all_found else "progress", "kind": None,
                "say": item.get("right") if all_found else "Yes!",
                "found": sorted(found), "total": len(want), "state": state}
    on = board.piece_at(tapped)
    if kind == "tap_checker":
        if on is None:
            return {"outcome": "ignored", "state": state}
        return {"outcome": "wrong", "kind": "not_checker",
                "say": item.get("hints", {}).get("not_checker") or MISTAKE_WORDS["not_checker"], "state": state}
    if kind == "tap_piece":
        if on is None:
            return {"outcome": "ignored", "state": state}
        return {"outcome": "wrong", "kind": "wrong_piece",
                "say": words("wrong_piece", item["piece"], tapped=NAME[LETTER[on.piece_type]],
                             look=LOOK[item["piece"]]), "state": state}
    src = _sq(item["from"])
    letter = _letter_on(board, item["from"])
    mover = board.piece_at(src)
    if kind == "tap_take":
        if on is None:
            return {"outcome": "ignored", "state": state}
        if on.color == mover.color:
            k = "own_piece_take"
        elif mover.piece_type == chess.KING and chess.square_distance(src, tapped) == 1:
            k = "protected"
        elif tapped in _empty_reach(mover.piece_type, src) and mover.piece_type not in (chess.PAWN, chess.KNIGHT, chess.KING):
            k = "jumped"
        else:
            k = "not_on_line"
        return {"outcome": "wrong", "kind": k, "say": item.get("hints", {}).get(k) or words(k, letter),
                "state": state}
    if tapped == src:
        return {"outcome": "ignored", "state": state}
    k = classify_reach_tap(board, src, tapped)
    return {"outcome": "wrong", "kind": k, "say": item.get("hints", {}).get(k) or words(k, letter),
            "found": sorted(found), "total": len(want), "state": state}


def _parse_move(board: chess.Board, uci: Any) -> Optional[chess.Move]:
    try:
        move = chess.Move.from_uci(str(uci))
    except ValueError:
        return None
    piece = board.piece_at(move.from_square)
    if (piece and piece.piece_type == chess.PAWN and move.promotion is None
            and chess.square_rank(move.to_square) in (0, 7)):
        move = chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)
    return move


def _grade_move_goal(item: Mapping[str, Any], uci: Any) -> Dict[str, Any]:
    board = board_of(item["fen"])
    move = _parse_move(board, uci)
    letter = _letter_on(board, str(uci)[:2]) if move else None
    if move is None or letter is None or board.piece_at(move.from_square).color != board.turn:
        return {"outcome": "ignored", "state": {}}
    if move not in board.legal_moves:
        if move in board.pseudo_legal_moves:
            k = "leaves_check" if board.is_check() else "into_check"
        else:
            k = classify_reach_tap(board, move.from_square, move.to_square)
        return {"outcome": "wrong", "kind": k, "say": item.get("hints", {}).get(k) or words(k, letter),
                "state": {}}
    san = board.san(move)
    after = board.copy(stack=False)
    after.push(move)
    if _meets_goal(board, move, item["goal"]):
        return {"outcome": "right", "kind": None, "say": item.get("right"), "move": move.uci(),
                "san": san, "fen_after": after.fen(), "state": {}}
    goal = item["goal"]
    if goal == "checkmate":
        k = "stalemate" if after.is_stalemate() else ("check_not_mate" if after.is_check() else "no_check")
    elif goal == "check":
        k = "no_check"
    else:
        k = "not_goal"
    return {"outcome": "wrong", "kind": k, "say": item.get("hints", {}).get(k) or words(k, letter),
            "state": {}}


def _grade_stars(item: Mapping[str, Any], square: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    at = state.get("at") or item["start"]
    left = set(state.get("left", item["stars"]))
    moves = int(state.get("moves", 0))
    try:
        to = _sq(str(square))
    except ValueError:
        return {"outcome": "ignored", "state": state}
    board = _stars_board(item, at, sorted(left))
    if to == _sq(at) or chess.square_name(to) in item.get("walls", []):
        return {"outcome": "ignored", "state": state}
    if to not in reach(board, _sq(at), ignore_checks=True):
        k = classify_reach_tap(board, _sq(at), to)
        return {"outcome": "wrong", "kind": k, "say": words(k, item["piece"]), "state": state}
    name = chess.square_name(to)
    moves += 1
    left.discard(name)
    state = {"at": name, "left": sorted(left), "moves": moves}
    par = stars_par(item)
    if left:
        return {"outcome": "progress", "kind": None, "say": "Captured." if name in item["stars"] else None,
                "state": state, "par": par}
    if moves <= par:
        return {"outcome": "right", "kind": None, "say": f"All the pawns in {moves} moves. That is the shortest route.",
                "state": state, "par": par}
    return {"outcome": "done", "kind": "extra_moves",
            "say": f"All the pawns in {moves} moves. It can be done in {par}.",
            "state": state, "par": par}


def _grade_game(item: Mapping[str, Any], uci: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    game = item["game"]
    board = board_of(state.get("fen") or item["fen"])
    child = chess.WHITE if item.get("child", "w") == "w" else chess.BLACK
    if board.turn != child or game_status(board, game, child):
        return {"outcome": "ignored", "state": state}
    move = _parse_move(board, uci)
    if move is None or board.piece_at(move.from_square) is None or board.piece_at(move.from_square).color != child:
        return {"outcome": "ignored", "state": state}
    letter = LETTER[board.piece_at(move.from_square).piece_type]
    if game in ("pawn_race", "capture_race"):
        legal = move.to_square in reach(board, move.from_square)
    else:
        legal = move in board.legal_moves
    if not legal:
        if game == "queen_mate" and move in board.pseudo_legal_moves:
            k = "into_check"
        else:
            k = classify_reach_tap(board, move.from_square, move.to_square)
        return {"outcome": "wrong", "kind": k, "say": words(k, letter), "state": state}
    played = [move.uci()]
    _push(board, move, game)
    moves = int(state.get("moves", 0)) + 1
    status = game_status(board, game, child)
    reply = None
    if status is None:
        reply = computer_move(board, game)
        if reply is not None:
            _push(board, reply, game)
            played.append(reply.uci())
        status = game_status(board, game, child)
    if status is None and game == "queen_mate" and moves >= int(item.get("max_moves", 30)):
        status = "draw"
    state = {"fen": board.fen(), "moves": moves}
    if status is None:
        return {"outcome": "progress", "kind": None, "say": None, "played": played, "state": state}
    say = item.get("on_" + status) or {"won": "You won.", "lost": "They won this time.",
                                       "draw": "It is a draw."}[status]
    if status == "draw" and board.is_stalemate():
        say = item.get("on_stalemate") or MISTAKE_WORDS["stalemate"]
    return {"outcome": "right" if status == "won" else "done", "kind": None if status == "won" else "game_" + status,
            "say": say, "played": played, "state": state, "result": status}


def _push(board: chess.Board, move: chess.Move, game: str) -> None:
    if game in ("pawn_race", "capture_race"):
        piece = board.piece_at(move.from_square)
        board.remove_piece_at(move.from_square)
        board.set_piece_at(move.to_square, piece)
        board.turn = not board.turn
        board.ep_square = None
        return
    board.push(move)


# ---------------------------------------------------------------------------
# what the page shows (never the answers)
# ---------------------------------------------------------------------------
def public_item(item: Mapping[str, Any], state: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    state = state or {}
    # "from" names the piece a task is about, so the page can light up its lines; it is not an answer.
    out = {k: item[k] for k in ("id", "part", "kind", "say", "sub", "test", "options", "flip", "marks", "from") if k in item}
    if item["kind"] == "stars":
        out.update({"fen": _stars_board(item, state.get("at") or item["start"], state.get("left")).fen(),
                    "stars_left": state.get("left", item["stars"]), "moves": state.get("moves", 0),
                    "par": stars_par(item)})
    elif item["kind"] == "game":
        out["fen"] = state.get("fen") or item["fen"]
        out["child"] = item.get("child", "w")
    else:
        out["fen"] = item["fen"]
    if item["kind"] == "tap_reach":
        out["total"] = len(answers(item))
        out["found"] = state.get("found", [])
    if item["kind"] == "choose":
        out.setdefault("options", [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}])
    return out


def reveal(item: Mapping[str, Any]) -> Dict[str, Any]:
    """After two wrong tries the page may show the answer."""
    a = sorted(answers(item))
    if item["kind"] == "move_goal":
        board = board_of(item["fen"])
        return {"moves": a, "squares": sorted({m[2:4] for m in a}),
                "sans": [board.san(chess.Move.from_uci(m)) for m in a]}
    if item["kind"] == "choose":
        return {"choice": a[0]}
    return {"squares": a}


# ---------------------------------------------------------------------------
# placement and the next class
# ---------------------------------------------------------------------------
LEVEL_START = {0: "rook", 1: "check", 2: "checkmate"}


def placement_level(results: Mapping[str, bool]) -> int:
    """Three tasks: knows the knight, knows check, finds a mate in one."""
    if not results.get("knight"):
        return 0
    if not (results.get("check") and results.get("mate")):
        return 1
    return 2


def next_class(level: int, passed: Sequence[str]) -> Optional[Dict[str, Any]]:
    """The first class from the child's starting point not yet passed."""
    order = classes()
    start = LEVEL_START.get(level, "rook")
    ids = [c["id"] for c in order]
    begin = ids.index(start) if start in ids else 0
    for c in order[begin:]:
        if c["id"] not in passed:
            return c
    return None


def warm_up_for(cls: Mapping[str, Any], previous: Optional[Mapping[str, Any]],
                previous_mistakes: Mapping[str, int]) -> List[Dict[str, Any]]:
    """Items to put in front of a class: the previous class's recall item,
    then one aimed at the previous class's most frequent mistake."""
    out: List[Dict[str, Any]] = []
    if previous is None:
        return out
    recall = item_by_id(previous, previous.get("recall", ""))
    if recall:
        out.append({**recall, "part": "Warm-up", "test": False})
    by_kind = previous.get("warm_up_by_kind") or {}
    for kind, _n in sorted(previous_mistakes.items(), key=lambda kv: -kv[1]):
        target = item_by_id(previous, by_kind.get(kind, ""))
        if target and (not recall or target["id"] != recall["id"]):
            out.append({**target, "part": "Warm-up", "test": False, "why": kind})
            break
    return out


NOTICE_WORDS = {
    "wrong_piece": "mixes up which piece is which",
    "jumped": "tries to move through pieces",
    "like_bishop": "moves pieces diagonally when they can't",
    "like_rook": "moves pieces in straight lines when they can't",
    "like_knight": "moves other pieces like a knight",
    "too_far": "moves the king more than one square",
    "into_check": "moves the king onto attacked squares",
    "pawn_backward": "moves pawns backwards",
    "pawn_blocked": "tries to take straight ahead with a pawn",
    "pawn_diag_empty": "moves pawns diagonally without taking",
    "pawn_two": "moves a pawn two squares after its first move",
    "check_not_mate": "gives check but not checkmate",
    "stalemate": "has given stalemate",
    "no_check": "misses moves that give check",
    "leaves_check": "forgets to get out of check",
    "extra_moves": "takes the long way round",
}


def coach_notes(mistakes: Mapping[str, int]) -> List[str]:
    """Plain sentences for the coach about what the taps showed.

    Twice at least: one tap is a slip, and these read as a statement about the
    child ("misses moves that give check").
    """
    return [NOTICE_WORDS[k] for k, n in sorted(mistakes.items(), key=lambda kv: -kv[1])
            if n >= 2 and k in NOTICE_WORDS][:3]
