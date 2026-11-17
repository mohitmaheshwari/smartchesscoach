"""Similar moments: how a stronger player handled the same kind of moment.

docs/similar_moments_scope.md (Mohit, 2026-11-17: "pull up those games too to
show how a better player did here ... each game knows its similar game").

THE TAG. After a game is analysed (analysis worker only, never the backend),
every move the player made is looked at as a moment: which of their pieces
could have landed on a square where it can be won, by what kind of taker (the
three looks), whether that move was a capture or a check, and how tempting it
was (Maia at the player's rating). When the player played a sound move while
such a tempting dangerous move was there, the moment is stored in
`similar_moments`, keyed by its kind.

THE POOL. Only public games (Lichess, Chess.com); never games against our own
coach, never an academy child (academy_students.child_user_id). Mohit decided
no consent rule: the games are public.

THE MATCH. A player's own landing-square mistake gets its kind from the same
signature; the closest stored moment is the same kind, from a player rated at
least STRONGER_BY above, at least as tempting as SHOW_FLOOR, most tempting first.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

import chess

from services.landing_check import LOOK_WORDS, check_landing

VERSION = "similar_moments.v1"
COLLECTION = "similar_moments"
PUBLIC_PLATFORMS = ("lichess", "chess.com")
PIECES = {chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen"}
_VALUE = {"pawn": 1, "knight": 3, "bishop": 3, "rook": 5, "queen": 9, "king": 100}
# A stored moment needs a sound played move: below a pawn's worth of loss.
SOUND_CP = 60
# Store wide, show narrow. Anchor measured 2026-11-17 (research/similar_probe2):
# Maia at his own rating gives Mohit's six real landing mistakes 0.1%, 0.8%,
# 0.8%, 1.1%, 1.2% and 4.2%, so real mistakes are often unlikely moves; a 5%
# floor (the first guess) would have excluded moments like his. STORE_FLOOR
# drops only the near-impossible (a bishop to h6 on move two) and is costly to
# change (the backfill re-tags). SHOW_FLOOR sits at his own mistakes' level and
# is cheap to change; tune it from the stronger players' distribution.
STORE_FLOOR = 0.005
SHOW_FLOOR = 0.01
STRONGER_BY = 150


def moment_key(piece: str, kind: Optional[str], capture: bool, check: bool, phase: Optional[str]) -> str:
    return f"landing:{piece}:{kind or 'any'}:{'cap' if capture else 'quiet'}:{'check' if check else 'nocheck'}:{phase or 'any'}"


def landing_signature(fen: str, uci: str) -> Optional[Dict[str, Any]]:
    """The kind of landing mistake a move would be, or None if it lands safely."""
    r = check_landing(fen, uci, answer="safe")
    if not r.get("eligible") or r.get("safe"):
        return None
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    winners = sorted((t for t in r["takers"] if t["wins"]), key=lambda t: _VALUE.get(t["piece"], 50))
    taker = winners[0] if winners else None
    return {
        "piece": r["piece"], "square": r["square"], "kind": taker["kind"] if taker else None,
        "taker": {"piece": taker["piece"], "sq": taker["sq"]} if taker else None,
        "capture": board.is_capture(move), "check": board.gives_check(move),
        "san": board.san(move), "uci": uci,
    }


def landing_candidates(fen: str, exclude_uci: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every move of a knight, bishop, rook or queen that would land where it can be won."""
    board = chess.Board(fen)
    out = []
    for move in board.legal_moves:
        if move.uci() == exclude_uci or board.piece_type_at(move.from_square) not in PIECES:
            continue
        after = board.copy(stack=False)
        after.push(move)
        if not after.is_attacked_by(after.turn, move.to_square):
            continue  # nothing can even reach the square: cheap skip before the exchange tree
        sig = landing_signature(fen, move.uci())
        if sig:
            out.append(sig)
    return out


def excluded_users(db) -> set:
    return {s.get("child_user_id") for s in db.academy_students.find({}, {"child_user_id": 1}) if s.get("child_user_id")}


_MAIA = None


def _maia_probs(fen: str, rating: int) -> Optional[Mapping[str, float]]:
    global _MAIA
    import os
    from services.human_behavior_engine import Maia2Provider, MoveContext
    if _MAIA is None:
        path = os.environ.get("MAIA2_MODEL_PATH")
        if not path:
            return None
        _MAIA = Maia2Provider(model_path=path)
    dist = _MAIA.predict(MoveContext(fen=fen, player_elo=int(rating), opponent_elo=int(rating)))
    return dist.probabilities if dist else None


def tag_game_moments_sync(db, game: Mapping[str, Any], observations: Iterable[Mapping[str, Any]],
                          maia=_maia_probs) -> int:
    """Store the tempting dangerous moments a player handled soundly in one game. Worker only."""
    user_id, game_id = game.get("user_id"), game.get("game_id")
    rating = game.get("user_rating")
    if game.get("platform") not in PUBLIC_PLATFORMS or not rating or not user_id:
        return 0
    if user_id in excluded_users(db):
        return 0
    stored = 0
    for obs in observations:
        fen, played = obs.get("fen_before"), obs.get("move_uci")
        if not fen or not played or (obs.get("cp_loss") or 0) >= SOUND_CP:
            continue
        if ((obs.get("destination_safety_exact") or {}).get("outcome")) == "miss":
            continue
        cands = landing_candidates(fen, exclude_uci=played)
        if not cands:
            continue
        probs = maia(fen, rating) or {}
        best: Dict[str, Dict[str, Any]] = {}
        for c in cands:
            p = float(probs.get(c["uci"]) or 0.0)
            if p < STORE_FLOOR:
                continue
            key = moment_key(c["piece"], c["kind"], c["capture"], c["check"], obs.get("phase"))
            if key not in best or p > best[key]["temptation"]:
                best[key] = {**c, "temptation": p}
        board = chess.Board(fen)
        for key, c in best.items():
            db[COLLECTION].update_one(
                {"_id": f"{game_id}:{obs.get('move_number')}:{key}"},
                {"$set": {
                    "key": key, "version": VERSION, "user_id": user_id, "game_id": game_id,
                    "platform": game.get("platform"), "rating": int(rating), "phase": obs.get("phase"),
                    "fen": fen, "temptation": round(c["temptation"], 4),
                    "dangerous": {k: c[k] for k in ("uci", "san", "piece", "square", "kind", "taker", "capture", "check")},
                    "played": {"uci": played, "san": board.san(chess.Move.from_uci(played))},
                    "tagged_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            stored += 1
    db.games.update_one({"game_id": game_id, "user_id": user_id}, {"$set": {"similar_moments_version": VERSION}})
    return stored


def _side(fen: str) -> str:
    return "White" if fen.split()[1] == "w" else "Black"


def moment_words(row: Mapping[str, Any]) -> str:
    d, p = row["dangerous"], row["played"]
    taker = d.get("taker") or {}
    look = LOOK_WORDS.get(d.get("kind") or "", "")
    return (f"Their {d['piece']} could go to {d['square']}, where the {taker.get('piece', 'opponent')} on "
            f"{taker.get('sq', '')} could win it {look}. They played {p['san']} instead.").replace("  ", " ")


def thinking_words(fen: str, uci: str) -> Optional[Dict[str, Any]]:
    """The coach's three looks from the player's own landing square."""
    h = check_landing(fen, uci, hint=True)
    if not h.get("eligible"):
        return None
    lines = [{"label": look["label"], "found": ", ".join(f"the {f['piece']} on {f['sq']}" for f in look["found"]) or "nothing"}
             for look in h["looks"]]
    return {"lead": f"Before your {h['piece']} lands on {h['square']}, look from {h['square']}:", "looks": lines,
            "end": "One of them can take it. Stop and find another move." if not h["safe"] else "Nothing wins it. Then it is safe to play."}


def _match_query(user_id: str, fen: str, played_uci: str, rating: int, phase: Optional[str]):
    sig = landing_signature(fen, played_uci)
    if not sig:
        return None, None
    key = moment_key(sig["piece"], sig["kind"], sig["capture"], sig["check"], phase)
    return sig, {"key": key, "user_id": {"$ne": user_id}, "rating": {"$gte": int(rating) + STRONGER_BY},
                 "temptation": {"$gte": SHOW_FLOOR}}


def find_similar_sync(db, *, user_id: str, fen: str, played_uci: str, rating: int,
                      phase: Optional[str]) -> Optional[Dict[str, Any]]:
    """The closest stronger-player moment for one of the player's landing mistakes."""
    _, query = _match_query(user_id, fen, played_uci, rating, phase)
    row = db[COLLECTION].find_one(query, sort=[("temptation", -1)]) if query else None
    return _present(row)


async def find_similar(db, *, user_id: str, fen: str, played_uci: str, rating: int,
                       phase: Optional[str]) -> Optional[Dict[str, Any]]:
    """Async twin for the backend (motor). Reads the index only; never runs Maia."""
    _, query = _match_query(user_id, fen, played_uci, rating, phase)
    row = await db[COLLECTION].find_one(query, sort=[("temptation", -1)]) if query else None
    return _present(row)


async def other_side_puzzle(db, *, piece: str, kind: Optional[str], rating: int,
                            sample: int = 800) -> Optional[Dict[str, Any]]:
    """A Lichess puzzle where the winning move takes the same piece with the same kind of taker.

    lichess_puzzles (4.4M rows) is indexed on themes and rating (checked
    2026-11-17), so the theme and rating band are queried directly; a random
    skip varies the pick. A row's fen is BEFORE the opponent's move; moves[0]
    is that move, moves[1] the solution.
    """
    import random
    from services import coach_plan_service as cp
    pt = {v: k for k, v in PIECES.items()}.get(piece)
    cursor = db.lichess_puzzles.find(
        {"themes": "hangingPiece", "rating": {"$gte": int(rating) - 250, "$lte": int(rating) + 250}},
        {"_id": 0, "puzzle_id": 1, "fen": 1, "moves": 1, "rating": 1},
    ).skip(random.randint(0, 2000)).limit(sample)
    async for row in cursor:
        moves = row.get("moves") or []
        try:
            board = chess.Board(row.get("fen"))
            board.push(chess.Move.from_uci(moves[0]))
            sol = chess.Move.from_uci(moves[1])
        except (ValueError, IndexError, TypeError):
            continue
        if sol not in board.legal_moves or board.piece_type_at(sol.to_square) != pt:
            continue
        if kind and cp._kind(board, sol.from_square, sol.to_square)[0] != kind:
            continue
        return {
            "fen": board.fen(), "solution_uci": sol.uci(), "solution_san": board.san(sol),
            "side": "White" if board.turn == chess.WHITE else "Black",
            "words": f"Someone left a {piece} where it could be taken. You are {'White' if board.turn else 'Black'}. Find the move that wins it.",
            "source": "lichess", "puzzle_id": row.get("puzzle_id"),
        }
    return None


def _present(row: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "fen": row["fen"], "side": _side(row["fen"]),
        "dangerous_uci": row["dangerous"]["uci"], "played_uci": row["played"]["uci"],
        "taker_uci": (row["dangerous"].get("taker") or {}).get("sq", "") + row["dangerous"]["square"]
        if row["dangerous"].get("taker") else None,
        "words": moment_words(row), "key": row["key"],
    }


__all__ = ["COLLECTION", "VERSION", "find_similar_sync", "landing_candidates", "landing_signature",
           "moment_key", "tag_game_moments_sync", "thinking_words"]
