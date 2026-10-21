"""Who was the better player in the game he just finished.

Everything the product knows about a game today comes from one side of the
board: `move_evaluations` holds his moves and nobody has ever run the engine
over his opponent's. Measured on one account, that is 21,827 opponent
half-moves stored in full in the PGNs and zero of them evaluated.

That absence is why the home page could only ever say what he did wrong. It
could not say whether he was the better player, whether the opponent handed
him the game, or whether the board or the clock decided it -- and on his
lichess record the biggest swing in a game is more often the opponent's
mistake than his.

So this evaluates both sides of ONE game: the last one he played. Every
position once, from the mover's point of view, which gives the cost of every
move on both sides from a single pass:

    cp_loss(move i) = eval_before(mover) - eval_after(mover)

Cached per game, because the answer for a finished game never changes.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

import chess
import chess.pgn

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "both_sides_review.v2"
CACHE_COLLECTION = "game_both_sides"

# Depth 12 is enough to say which of two club players held together better.
# It is NOT the depth to judge one move by; the turning point it reports is a
# pointer to a moment, not a verdict on a move.
DEPTH = 12
# Beyond this the game is decided and differences are noise, so a lost queen
# in a lost position does not swamp the average.
CLAMP = 1500
# A bound on the work one page load can cause.
MAX_PLIES = 160
BLUNDER_CP = 200
# His reply counts as going straight at a mistake if it costs no more than
# this. The card used to ASSERT that he punished it and never checked.
PUNISHED_CP = 30
# From his point of view, the eval at which he is not merely worse but lost.
LOSING_CP = -200
# Share of HIS OWN turns spent lost before "you were the steadier player"
# stops being the story. Measured over his 30 most recent games: the share is
# 0% in the median game, and the values run 0,0,...,2,11,20,23,27 and then
# 55,55 -- so the two games he was genuinely rescued in sit on the far side of
# a gap, and anything from 0.30 to 0.50 separates them identically.
RESCUED_SHARE = 0.40

_TIME_CONTROL_TAG = re.compile(r'\[TimeControl "([^"]+)"\]')


def _clamp(value: int) -> int:
    return max(-CLAMP, min(CLAMP, value))


def mate_reply_cost(
    end: "chess.Board", colour: bool, n_moves: int, turning_index: int
) -> Optional[int]:
    """0 when he answered their mistake by mating them, otherwise None.

    The eval loop stops at game over, so the mating move never gets a cost --
    and the card therefore said nothing about the best answer a player can
    possibly give. This reads it off the final position instead:

      * their mistake is the second-to-last ply  (n_moves == turning_index + 2)
      * the game ended in mate
      * the side to move in that final position is NOT him, so the mate is his

    Pure, so it can be tested without an engine.
    """
    if n_moves != turning_index + 2:
        return None
    if not end.is_checkmate() or end.turn == colour:
        return None
    return 0


def review_both_sides(pgn: str, user_color: str) -> Optional[Dict[str, Any]]:
    """Evaluate every position once and return both players' costs.

    Synchronous and engine-bound: call it through a thread, never on the event
    loop.
    """
    from stockfish_service import StockfishEngine

    try:
        game = chess.pgn.read_game(io.StringIO(str(pgn or "")))
    except Exception:
        return None
    if game is None:
        return None
    moves = list(game.mainline_moves())
    if len(moves) < 10:
        return None
    moves = moves[:MAX_PLIES]
    colour = chess.WHITE if str(user_color) == "white" else chess.BLACK

    evals = []
    with StockfishEngine() as engine:
        board = game.board()
        for move in [None] + moves:
            if move is not None:
                board.push(move)
            if board.is_game_over():
                evals.append(None)
                break
            score, mate = engine.evaluate_position(board, depth=DEPTH)
            if mate is not None:
                evals.append(CLAMP if mate > 0 else -CLAMP)
            else:
                evals.append(_clamp(int(score)))

    his: list = []
    theirs: list = []
    turning: Optional[Dict[str, Any]] = None
    turning_index: Optional[int] = None
    # How much of the game he spent lost, counted over HIS OWN turns. A player
    # told he was the sharper player in a game he was losing for half of has
    # been told something he will not recognise.
    his_turns = 0
    his_turns_lost = 0
    losses: Dict[int, int] = {}
    board = game.board()
    for index, move in enumerate(moves):
        if index + 1 >= len(evals) or evals[index] is None or evals[index + 1] is None:
            break
        mover = board.turn
        sign = 1 if mover == chess.WHITE else -1
        loss = max(0, sign * evals[index] - sign * evals[index + 1])
        try:
            san = board.san(move)
        except Exception:
            break
        mine = mover == colour
        (his if mine else theirs).append(loss)
        losses[index] = loss
        if mine:
            his_turns += 1
            pov = evals[index] if colour == chess.WHITE else -evals[index]
            if pov < LOSING_CP:
                his_turns_lost += 1
        if turning is None or loss > turning["cost"]:
            turning_index = index
            turning = {
                "move_number": board.fullmove_number,
                "san": san,
                "whose": "his" if mine else "theirs",
                "fen_before": board.fen(),
                "cost": loss,
                "board_orientation": "white" if colour == chess.WHITE else "black",
            }
        board.push(move)

    if len(his) < 5 or len(theirs) < 5:
        return None

    # Did he actually go straight at their mistake? The move right after it is
    # his, and we already know what it cost.
    reply_cost: Optional[int] = None
    if turning_index is not None and turning["whose"] == "theirs":
        reply_cost = losses.get(turning_index + 1)
        # Mating them is the clearest punishment there is, but the eval loop
        # stops at game over, so the mating move never gets a cost and the
        # card stayed quiet about his best possible answer.
        if reply_cost is None:
            end = game.board()
            for played in moves:
                end.push(played)
            reply_cost = mate_reply_cost(end, colour, len(moves), turning_index)

    return {
        "schema_version": SCHEMA_VERSION,
        "depth": DEPTH,
        "his_moves": len(his),
        "their_moves": len(theirs),
        "his_mean_cp": round(sum(his) / len(his), 1),
        "their_mean_cp": round(sum(theirs) / len(theirs), 1),
        "his_blunders": sum(1 for x in his if x >= BLUNDER_CP),
        "their_blunders": sum(1 for x in theirs if x >= BLUNDER_CP),
        "turning_point": turning,
        "reply_cost": reply_cost,
        "his_turns": his_turns,
        "his_turns_lost": his_turns_lost,
    }


def card_from_review(
    review: Mapping[str, Any],
    *,
    won: bool,
    lost: bool,
    termination: str,
) -> Dict[str, Any]:
    """Turn the two numbers into the one sentence he reads.

    No figure reaches him. The engine numbers justify the sentence; they are
    not the sentence, and a player told "your average loss was 63 centipawns"
    has been given arithmetic rather than coaching.
    """
    sharper = review["his_mean_cp"] < review["their_mean_cp"]
    # A timeout is a timeout whoever's flag fell, so `decided_by` records the
    # game. Only the rare card -- he was steadier AND his own flag fell --
    # turns it into the story he reads.
    on_time = str(termination) == "timeout"
    flagged = lost and on_time
    turning = review.get("turning_point") or {}
    theirs = turning.get("whose") == "theirs"

    # "You went straight at it" used to be asserted from `theirs` alone and
    # never checked. Measured over 30 games it fired on 16 and was true on 12,
    # so one time in four it credited him with a punishment he had not played.
    # `reply_cost` is what his answering move actually cost, from the pass the
    # review already makes. Against a fresh depth-14 check it agrees 13/16 and
    # every disagreement is this one erring low, so it never says he took a
    # chance he missed -- it only stays quiet on about one he did take in five.
    reply_cost = review.get("reply_cost")
    punished = theirs and reply_cost is not None and reply_cost <= PUNISHED_CP

    # Steadier, in a game he was lost in for much of, is not a thing he will
    # recognise as a description of what happened to him.
    his_turns = review.get("his_turns") or 0
    rescued = bool(his_turns) and (review.get("his_turns_lost") or 0) / his_turns >= RESCUED_SHARE

    if sharper and flagged:
        # The rare and expensive one: he earned it and the clock took it.
        state = "clock"
        headline = "You were the steadier player. The clock ended it."
        detail = "The game was still yours when your flag fell."
    elif sharper and won and rescued:
        # The story of the game is theirs, so it is told as theirs.
        state = "rescued"
        headline = "They were winning this one and let it go."
        detail = (
            "You stayed in it, and when the chance came you took it."
            if punished
            else "You stayed in it until it came back to you."
        )
    elif sharper and won:
        state = "sharper"
        headline = "You were the steadier player in that one."
        detail = (
            "They went wrong and you went straight at it."
            if punished
            else "They went wrong, and the game came your way."
            if theirs
            else "You kept it together better than they did."
        )
    elif sharper:
        state = "sharper_no_win"
        headline = "You were the steadier player, and it got away."
        detail = "Worth a look at where it turned."
    elif review["his_mean_cp"] == review["their_mean_cp"]:
        state = "even"
        headline = "Hard to separate you two."
        detail = "Neither of you gave much away."
    else:
        state = "outplayed"
        headline = "They held together better than you did."
        detail = (
            "They gave you a chance and you took it, but the rest got away."
            if punished
            else "They gave you a chance and it went by."
            if theirs
            else "They gave you less to work with than you gave them."
        )
    return {
        "state": state,
        "headline": headline,
        "detail": detail,
        "decided_by": "clock" if on_time else "board",
        "turning_point_is_theirs": bool(theirs),
        "punished": bool(punished),
    }


def turning_point_squares(turning: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """The turning move's squares, read off the stored FEN and SAN.

    Mohit 2026-10-17, on a card whose board was 4...Bd6 -- the position
    BEFORE the move, so every black piece still sat on its home square:
    "look, bd6 here, look at board, it doesn't make sense."

    The move was right. Checked against Stockfish, 4...Bd6 swings the game
    +160 to +612 because it allows Qh5+, the largest swing in that game.
    What was missing is that the card NAMED a move the picture never drew,
    on a board that looks untouched, so there was nothing on screen to
    connect the sentence to.

    Derived here rather than stored by the review, because the reviews are
    cached: computing it at card-build time fixes every card that already
    exists without re-analysing a single game. Returns {} when the SAN does
    not parse, so a bad row costs the arrow and not the card.
    """
    if not turning:
        return {}
    fen, san = turning.get("fen_before"), turning.get("san")
    if not fen or not san:
        return {}
    try:
        board = chess.Board(str(fen))
        move = board.parse_san(str(san))
    except (ValueError, AssertionError, TypeError):
        return {}
    return {
        "from": chess.square_name(move.from_square),
        "to": chess.square_name(move.to_square),
    }


# The games the home card may be about: finished, with a PGN to read both
# sides from, and not a Play with Coach game.
_HOME_GAME_FILTER = {
    "played_at_utc": {"$ne": None},
    "platform": {"$ne": "coach"},
    "pgn": {"$nin": [None, ""]},
}
_HOME_GAME_PROJECTION = {
    "_id": 0,
    "game_id": 1,
    "user_id": 1,
    "pgn": 1,
    "user_color": 1,
    "result": 1,
    "termination": 1,
    "platform": 1,
    "played_at_utc": 1,
    "opponent_name": 1,
    "url": 1,
}

# Said under the lead line when the opponent's biggest error came after the
# player's deciding one. Checked by hand on game 8f40005b: Black threw a won
# game away with Rxf3+, White handed it back with Ne6+, and the card said
# only "the game was still yours" while the story said only "Rxf3+". Both
# true, so the card tells both, in order.
_THEY_WENT_WRONG_TOO = "They went wrong here too."


async def _home_game(db, user_id: str):
    """The game the home card is about, and why it was chosen.

    The coach's review pick when the player has one -- the same pick the Lab
    shows, read through the same service, so the two pages cannot disagree
    about which game is worth reviewing. Otherwise the last game.

    Returns (game, chosen_by, review_url). A failing pick never costs the
    card: it falls back to the last game.
    """
    try:
        from services.coach_selected_review_service import get_recommendation

        recommendation = await get_recommendation(db, user_id)
        prescription = (recommendation or {}).get("prescription") or {}
        picked_id = (prescription.get("game") or {}).get("game_id")
        if picked_id:
            picked = await db.games.find_one(
                {"user_id": user_id, "game_id": picked_id, **_HOME_GAME_FILTER},
                _HOME_GAME_PROJECTION,
            )
            if picked:
                return picked, "coach_pick", prescription.get("review_url")
    except Exception:
        logger.warning("home card could not read the review pick", exc_info=True)

    game = await db.games.find_one(
        {"user_id": user_id, **_HOME_GAME_FILTER},
        _HOME_GAME_PROJECTION,
        sort=[("played_at_utc", -1)],
    )
    return game, "last_game", None


def _ply_order(move_number: Any, white_moved: bool) -> tuple:
    try:
        number = int(move_number)
    except (TypeError, ValueError):
        number = 0
    return (number, 0 if white_moved else 1)


def story_card_fields(
    story: Optional[Mapping[str, Any]],
    review: Mapping[str, Any],
    *,
    user_colour: str,
) -> Dict[str, Any]:
    """What the home card shows from the game story, and what its board shows.

    The board follows the story's lead move, so the picture and the first
    line can never point at different moves. Only when the story has no move
    to show does the board fall back to the both-sides turning point, which
    is the biggest single swing by either player.
    """
    user_is_white = str(user_colour) == "white"
    plan = (story or {}).get("plan") or {}
    if plan.get("home_lines"):
        return _plan_card_fields(plan, review, user_is_white)
    lines = []
    lead_move = None
    for item in (story or {}).get("home_lines") or []:
        text = str(item.get("display_name") or "").strip()
        if not text:
            continue
        # Each line on the card is read as a sentence. The names come from
        # three owners and only some end in a full stop, so the card read
        # "This is where the game got away." beside "Found the best move
        # when it mattered" -- seen on production cards 2026-10-21.
        if text[-1] not in ".!?":
            text += "."
        is_move = item.get("kind") == "moment" and bool(item.get("move_san"))
        line = {
            "kind": "moment" if is_move else "stretch",
            "polarity": item.get("polarity"),
            "san": item.get("move_san") if is_move else None,
            "text": text,
        }
        lines.append(line)
        if (
            lead_move is None
            and is_move
            and item.get("fen_before")
            and len(str(item.get("move_uci") or "")) >= 4
        ):
            lead_move = item

    turning = review.get("turning_point") or {}
    orientation = "white" if user_is_white else "black"
    if lead_move is not None:
        uci = str(lead_move["move_uci"])
        board = {
            "source": "story",
            "fen_before": lead_move["fen_before"],
            "san": lead_move["move_san"],
            "from": uci[:2],
            "to": uci[2:4],
            "board_orientation": orientation,
        }
    else:
        board = {
            "source": "turning_point",
            **turning,
            **turning_point_squares(turning),
        }

    # Both halves, in order: his deciding mistake, then their bigger one.
    if (
        lead_move is not None
        and lines
        and lines[0]["san"] == lead_move.get("move_san")
        and lead_move.get("polarity") == "negative"
        and lead_move.get("decisive")
        and turning.get("whose") == "theirs"
        and turning.get("san")
        and _ply_order(turning.get("move_number"), not user_is_white)
        > _ply_order(lead_move.get("move_number"), user_is_white)
    ):
        lines.insert(1, {
            "kind": "theirs",
            "polarity": "neutral",
            "san": turning.get("san"),
            "text": _THEY_WENT_WRONG_TOO,
        })

    return {"story_lines": lines[:3], "board": board}


def _plan_card_fields(plan, review, user_is_white: bool) -> Dict[str, Any]:
    """The home cut of the ledger story: its title, the opening line, and the
    two moments that matter most. Each line is a full sentence that already
    names its move, so no move is shown beside it a second time. The board
    shows the most important move the player made."""
    lines = []
    for item in plan.get("home_lines") or []:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        lines.append({
            "kind": "moment" if item.get("san") else "stretch",
            "polarity": item.get("polarity"),
            "san": None,
            "text": text,
        })
    move = plan.get("board_move") or {}
    uci = str(move.get("uci") or "")
    if move.get("fen_before") and len(uci) >= 4:
        board = {
            "source": "story",
            "fen_before": move["fen_before"],
            "san": move.get("san"),
            "from": uci[:2],
            "to": uci[2:4],
            "board_orientation": "white" if user_is_white else "black",
        }
    else:
        turning = review.get("turning_point") or {}
        board = {"source": "turning_point", **turning, **turning_point_squares(turning)}
    return {
        "story_lines": lines[:3],
        "story_title": (plan.get("type") or {}).get("title"),
        "board": board,
    }


async def last_game_card(db, user_id: str) -> Optional[Dict[str, Any]]:
    """The home card: the coach's review pick, or his last finished game."""
    game, chosen_by, review_url = await _home_game(db, user_id)
    if not game:
        return None

    cache = getattr(db, CACHE_COLLECTION, None)
    review = None
    if cache is not None:
        cached = await cache.find_one(
            {"game_id": game["game_id"], "schema_version": SCHEMA_VERSION},
            {"_id": 0, "review": 1},
        )
        if cached:
            review = cached.get("review")
    if review is None:
        try:
            review = await asyncio.to_thread(
                review_both_sides, game.get("pgn"), str(game.get("user_color"))
            )
        except Exception:
            logger.exception("both-sides review failed for %s", game.get("game_id"))
            return None
        if review is None:
            return None
        if cache is not None:
            try:
                await cache.update_one(
                    {"game_id": game["game_id"]},
                    {
                        "$set": {
                            "game_id": game["game_id"],
                            "user_id": user_id,
                            "schema_version": SCHEMA_VERSION,
                            "review": review,
                            "computed_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
            except Exception:
                # A cache that cannot be written must not cost him the card.
                logger.warning("could not cache both-sides review", exc_info=True)

    colour = str(game.get("user_color"))
    result = str(game.get("result") or "")
    won = (result == "1-0" and colour == "white") or (result == "0-1" and colour == "black")
    lost = (result == "1-0" and colour == "black") or (result == "0-1" and colour == "white")
    card = card_from_review(
        review, won=won, lost=lost, termination=str(game.get("termination") or "")
    )
    card.update(
        {
            "schema_version": SCHEMA_VERSION,
            "game_id": game.get("game_id"),
            "game_url": game.get("url"),
            "platform": game.get("platform"),
            "played_at": game.get("played_at_utc"),
            "result": "won" if won else "lost" if lost else "drew",
            "turning_point": {
                **(review.get("turning_point") or {}),
                **turning_point_squares(review.get("turning_point")),
            },
            # For a reviewer and for tests. The UI does not render these.
            "measured": {
                "his_mean_cp": review["his_mean_cp"],
                "their_mean_cp": review["their_mean_cp"],
                "his_blunders": review["his_blunders"],
                "their_blunders": review["their_blunders"],
                "depth": review["depth"],
                "reply_cost": review.get("reply_cost"),
                "his_turns_lost": review.get("his_turns_lost"),
                "his_turns": review.get("his_turns"),
                "counted_by": "both sides of the PGN, evaluated here",
            },
            "chosen_by": chosen_by,
            "review_url": review_url or f"/game/{game.get('game_id')}",
        }
    )

    # The story is extra. If it cannot be built, the card still says who was
    # the better player, exactly as it did before the story existed.
    story = None
    try:
        from services.game_story import story_for_game

        story = await story_for_game(db, game)
    except Exception:
        logger.warning("home card could not load the game story", exc_info=True)
    card.update(story_card_fields(story, review, user_colour=colour))
    return card
