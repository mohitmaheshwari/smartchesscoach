"""Real games that teach an idea he does not know yet
(docs/daily_coach_plan_scope.md, section 9).

Every Lichess puzzle keeps the game it came from (`game_url`), its opening
(`opening_tags`) and its ideas (`themes`). So "a game in the Italian, near your
level, decided by a fork, with you on the side that finds it" is one query.
Only that game is fetched from Lichess's public export (nothing about the
player is sent), kept in `teaching_games`, and walked through on /study/:id.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import chess
import chess.pgn

COLLECTION = "teaching_games"
OPENINGS_READ = 200
OPENINGS_TRIED = 3
IDEAS_TRIED = 4
CANDIDATES_READ = 300
GAME_AFTER_PLIES = 8
EXPORT_URL = "https://lichess.org/game/export/{gid}?evals=false&clocks=false&literate=false"
_GAME_ID = re.compile(r"lichess\.org/([A-Za-z0-9]{8})")
_TAGS: Dict[str, str] = {}


def norm(name: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


NAMING_PLIES = 20
_VARIANT_WORDS = ("from position", "chess960", "racing kings", "crazyhouse", "atomic", "horde", "antichess",
                  "king of the hill", "three-check")


def opening_name(pgn: Any) -> Optional[str]:
    """The deepest Lichess opening name his game reaches in its first moves
    (services/lichess_openings_local.py, looked up by position). Stored PGNs
    carry no opening tag, and `games.opening` is empty for most games
    (2026-11-18: 17 of Mohit's newest 200, all of them variants)."""
    from services.lichess_openings_local import name_for_fen

    try:
        game = chess.pgn.read_game(io.StringIO(str(pgn or "")))
    except Exception:
        return None
    if game is None or game.headers.get("FEN"):
        return None
    board = game.board()
    name = None
    for i, mv in enumerate(game.mainline_moves()):
        if i >= NAMING_PLIES or mv not in board.legal_moves:
            break
        board.push(mv)
        hit = name_for_fen(board.fen())
        if hit:
            name = hit[0]
    return name


def his_openings(games: Iterable[Mapping[str, Any]]) -> List[Tuple[str, str]]:
    """(opening name, his colour), most played first. Named from the moves;
    the stored `opening` is used only when the moves give nothing."""
    c: Counter = Counter()
    for g in games:
        colour = g.get("user_color")
        stored = g.get("opening") if isinstance(g.get("opening"), str) else ""
        if colour not in ("white", "black") or any(w in stored.lower() for w in _VARIANT_WORDS):
            continue
        name = opening_name(g.get("pgn")) or stored.strip()
        if name:
            c[(name, colour)] += 1
    return [k for k, _ in c.most_common()]


def tags_for(opening: str, tags_by_norm: Mapping[str, str]) -> List[str]:
    """Lichess opening tags whose name starts his opening's name, most specific
    first ("Caro Kann Defense Exchange Variation" -> Caro-Kann_Defense_Exchange_Variation,
    then Caro-Kann_Defense)."""
    mine = norm(opening)
    hits = [(len(n), tag) for n, tag in tags_by_norm.items() if n and mine.startswith(n)]
    return [tag for _, tag in sorted(hits, reverse=True)]


def solver_colour(fen: str) -> str:
    """A Lichess puzzle's FEN is before the opponent's move, so the solver is
    the side NOT to move in it."""
    return "white" if fen.split()[1] == "b" else "black"


def game_id_of(url: str) -> Optional[str]:
    m = _GAME_ID.search(str(url or ""))
    return m.group(1) if m else None


async def opening_tags(db) -> Dict[str, str]:
    if not _TAGS:
        for tag in await db.lichess_puzzles.distinct("opening_tags"):
            if isinstance(tag, str):
                _TAGS[norm(tag)] = tag
    return _TAGS


async def find_puzzle(db, theme: str, tag: str, colour: str, low: int, high: int,
                      exclude: set) -> Optional[Dict[str, Any]]:
    async for p in db.lichess_puzzles.find(
            {"opening_tags": tag, "themes": theme, "rating": {"$gte": low, "$lte": high}},
            {"_id": 0, "puzzle_id": 1, "fen": 1, "moves": 1, "game_url": 1, "rating": 1}).limit(CANDIDATES_READ):
        if p.get("puzzle_id") in exclude or not game_id_of(p.get("game_url")):
            continue
        if solver_colour(p["fen"]) == colour:
            return p
    return None


async def fetch_pgn(game_id: str) -> Optional[str]:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(EXPORT_URL.format(gid=game_id),
                                 headers={"Accept": "application/x-chess-pgn", "User-Agent": "ChessGuru/1.0"})
        return r.text if r.status_code == 200 and "[Event" in r.text else None
    except Exception:
        return None


async def stored_or_fetch(db, puzzle: Mapping[str, Any], idea: Mapping[str, Any], tag: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLLECTION].find_one({"puzzle_id": puzzle["puzzle_id"]}, {"_id": 0})
    if doc:
        return doc
    gid = game_id_of(puzzle.get("game_url"))
    pgn = await fetch_pgn(gid) if gid else None
    if not pgn or study(pgn, puzzle) is None:
        return None
    doc = {"puzzle_id": puzzle["puzzle_id"], "lichess_game_id": gid, "pgn": pgn, "fen": puzzle["fen"],
           "moves": puzzle["moves"], "idea": idea["key"], "theme": idea["theme"], "opening_tag": tag,
           "rating": puzzle.get("rating"), "fetched_at": datetime.now(timezone.utc)}
    await db[COLLECTION].update_one({"puzzle_id": doc["puzzle_id"]}, {"$setOnInsert": doc}, upsert=True)
    return doc


async def next_game(db, ideas: Sequence[Mapping[str, Any]], openings: Sequence[Tuple[str, str]],
                    rating: Optional[int], exclude: set) -> Optional[Dict[str, Any]]:
    """The first teaching game for the first idea that has one in his openings."""
    from services.topic_practice_themes import rating_window

    low, high = rating_window(rating)
    tags = await opening_tags(db)
    for idea in list(ideas)[:IDEAS_TRIED]:
        for opening, colour in list(openings)[:OPENINGS_TRIED]:
            for tag in tags_for(opening, tags)[:2]:
                p = await find_puzzle(db, idea["theme"], tag, colour, low, high, exclude)
                if not p:
                    continue
                doc = await stored_or_fetch(db, p, idea, tag)
                if doc:
                    return {"puzzle_id": doc["puzzle_id"], "idea": idea, "opening": tag.replace("_", " ")}
    return None


# --------------------------------------------------------------------------
# The study page
# --------------------------------------------------------------------------
def _moves(raw: Any) -> List[str]:
    return raw.split() if isinstance(raw, str) else list(raw or ())


def study(pgn: str, puzzle: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The walk-through: the game's moves up to the moment (ending with the
    opponent's move that allowed it), the pause position, the idea's line,
    and what was really played. None when the game does not reach the puzzle."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or game.headers.get("FEN") or game.headers.get("Variant", "Standard") != "Standard":
        return None
    target = chess.Board(puzzle["fen"])
    key = (target.board_fen(), target.turn)
    board = game.board()
    before: List[str] = []
    mainline = list(game.mainline_moves())
    at = None
    for i, mv in enumerate(mainline):
        if (board.board_fen(), board.turn) == key:
            at = i
            break
        before.append(board.san(mv))
        board.push(mv)
    if at is None:
        return None
    line = _moves(puzzle.get("moves"))
    if len(line) < 2:
        return None
    setup = chess.Move.from_uci(line[0])
    if setup not in board.legal_moves:
        return None
    before.append(board.san(setup))
    board.push(setup)
    pause_fen = board.fen()
    solution: List[str] = []
    b = board.copy()
    for u in line[1:]:
        mv = chess.Move.from_uci(u)
        if mv not in b.legal_moves:
            break
        solution.append(b.san(mv))
        b.push(mv)
    actual: List[str] = []
    b = board.copy()
    for mv in mainline[at + 1: at + 1 + GAME_AFTER_PLIES]:
        if mv not in b.legal_moves:
            break
        actual.append(b.san(mv))
        b.push(mv)
    h = game.headers
    return {
        "moves_before": before, "pause_fen": pause_fen, "solver": solver_colour(puzzle["fen"]),
        "solution": solution, "game_after": actual, "found_in_game": bool(actual) and actual[0] == (solution or [None])[0],
        "result": h.get("Result"), "opening": h.get("Opening"),
        "white_rating": h.get("WhiteElo"), "black_rating": h.get("BlackElo"),
    }


async def study_payload(db, puzzle_id: str) -> Optional[Dict[str, Any]]:
    from services.topic_practice_themes import daily_themes

    doc = await db[COLLECTION].find_one({"puzzle_id": puzzle_id}, {"_id": 0})
    if not doc:
        return None
    s = study(doc["pgn"], doc)
    if s is None:
        return None
    idea = daily_themes().get(doc.get("idea")) or {}
    return {**s, "puzzle_id": puzzle_id, "position_id": f"lichess_puzzles:{puzzle_id}", "topic": f"study-{puzzle_id}",
            "idea_title": idea.get("title"), "idea_text": idea.get("idea")}
