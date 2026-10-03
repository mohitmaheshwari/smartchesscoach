"""Serving and grading the pin and skewer drill.

docs/pin_skewer_drill_scope.md.

THREE SOURCES, IN THIS ORDER, and the order is the point. His own games come
first because he was there -- the opponent's name and the date do more than any
extra position would. Then other players' real games. Then Lichess, which is
effectively unlimited and therefore last.

NO NEW COLLECTION. The positions already existed in all three pools; what was
missing was the label. `scripts/tag_motif_positions.py` wrote `drill_motif` onto
them and this reads it.

THE GRADER MATCHES THE PRINTED QUESTION, which is the whole reason it is not a
string comparison. The card says "find the move that attacks the line", so a
different move that also creates the line IS a right answer to the question
asked, and marking it wrong would be the printed-question-against-the-grader
fault that `lesson_question_spec` exists to prevent.

Two ways to be right:

  the stored answer           always accepted; the engine chose it
  any move that creates the   accepted only if it does not hand over material,
  same alignment              because "attacks the line" does not mean "at any
                              price" and the engine has not vetted this one

The material floor is one pawn, by the static exchange on the square the piece
lands on. That is a chess constant rather than a tuned number -- there is no
distribution to look at first, because the question is not "how much material do
players usually give" but "is giving a piece away an answer to this card".
"""
from __future__ import annotations

import collections
from typing import Any, Dict, List, Optional

import chess

from services.lesson_question_spec import spec_or_fallback
from services.motif_alignment import alignment_after
from services.pattern_confidence.see import static_exchange_eval

MOTIFS = ("pin", "skewer")

# Collections the tagger wrote to, in serving order, with how each names the
# player a position came from. `own` is resolved per collection because the two
# community pools use different field names for the same idea.
SOURCES = (
    ("community_training_positions", "source_user_id", "own_game"),
    ("community_puzzles", "shared_by", "own_game"),
    ("community_training_positions", "source_user_id", "community"),
    ("community_puzzles", "shared_by", "community"),
    ("lichess_puzzles", None, "lichess"),
)

# Giving away more than a pawn is not an answer to "attack the line".
MATERIAL_FLOOR_CP = 100


def _position_id(collection: str, doc) -> str:
    """Stable id that says which collection to look in when it comes back.

    The id has to survive a round trip through the browser and identify the row
    again, and `puzzle_attempts` rows are useless without one -- 55 legacy rows
    carry a null id and can never be filtered. Nothing here writes one of those.
    """
    return "%s:%s" % (collection, doc.get("puzzle_id") or doc.get("position_id")
                      or doc["_id"])


def _card(motif: str) -> Dict[str, Any]:
    """The words on the card, from the one file that owns them."""
    spec = spec_or_fallback(motif)
    return {
        "question": spec.question_for(spec.accepts),
        "task_line": spec.task_line_for(spec.accepts),
        "reason_prompt": spec.reason_prompt,
        # Order is shuffled per position by the caller so the expected answer
        # never sits first on screen.
        "reason_options": [{"id": o.id, "label": o.label}
                           for o in spec.reason_options],
    }


async def _solved_ids(db, user_id: str) -> set:
    out = set()
    async for row in db.puzzle_attempts.find(
            {"user_id": user_id, "correct": True}, {"_id": 0, "puzzle_id": 1}):
        pid = row.get("puzzle_id")
        if pid:
            out.add(str(pid))
    return out


async def get_drill_positions(db, user_id: str, motif: str,
                              limit: int = 10) -> Dict[str, Any]:
    """Positions for one motif, own games first. The answer is never included.

    `exhausted` is told apart from `not_tagged`: one means he has solved what we
    have, the other means the tagger has not run. Collapsing them would make a
    missing migration look like a finished drill.
    """
    motif = str(motif or "").lower()
    if motif not in MOTIFS:
        return {"ok": False, "reason": "unknown_motif", "positions": []}

    solved = await _solved_ids(db, user_id)
    out: List[Dict[str, Any]] = []
    tagged_anywhere = 0
    seen_fens = set()

    for collection, owner_field, source in SOURCES:
        if len(out) >= limit:
            break
        query: Dict[str, Any] = {"drill_motif": motif}
        if owner_field and source == "own_game":
            query[owner_field] = user_id
        elif owner_field:
            query[owner_field] = {"$ne": user_id}
        cursor = db[collection].find(query, {
            "fen": 1, "drill_fen": 1, "puzzle_id": 1, "position_id": 1,
            "move_number": 1, "user_color": 1, "opening_name": 1,
            "source_game_id": 1, "rating": 1,
        }).limit(limit * 4)
        async for doc in cursor:
            tagged_anywhere += 1
            pid = _position_id(collection, doc)
            if pid in solved:
                continue
            fen = doc.get("drill_fen") or doc.get("fen")
            if not fen or fen in seen_fens:
                continue            # the same position reaches us from two pools
            seen_fens.add(fen)
            board = chess.Board(fen)
            out.append({
                "position_id": pid,
                "fen": fen,
                "to_move": "white" if board.turn == chess.WHITE else "black",
                "source": source,
                "source_game_id": doc.get("source_game_id"),
                "move_number": doc.get("move_number"),
                "opening_name": doc.get("opening_name"),
                **_card(motif),
            })
            if len(out) >= limit:
                break

    return {
        "ok": True,
        "motif": motif,
        "positions": out,
        # Why the list is short, when it is short.
        "state": ("ready" if out
                  else "exhausted" if tagged_anywhere
                  else "not_tagged"),
    }


def _hands_over_material(fen: str, uci: str) -> bool:
    """Can the opponent profitably take the piece that just landed?"""
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(str(uci))
    except Exception:
        return True
    if move not in board.legal_moves:
        return True
    board.push(move)
    # `board.turn` is now the opponent, which is exactly the attacker we ask about.
    return static_exchange_eval(board, move.to_square, board.turn) > MATERIAL_FLOOR_CP


async def grade(db, user_id: str, position_id: str, move_uci: str,
                reason_id: Optional[str] = None) -> Dict[str, Any]:
    """Mark one attempt. The answer only ever leaves here, after a submission."""
    try:
        collection, key = str(position_id).split(":", 1)
    except ValueError:
        return {"ok": False, "reason": "bad_position_id"}
    if collection not in {c for c, _, _ in SOURCES}:
        return {"ok": False, "reason": "bad_position_id"}

    doc = None
    for field in ("puzzle_id", "position_id"):
        doc = await db[collection].find_one({field: key, "drill_motif": {"$ne": None}})
        if doc:
            break
    if doc is None:
        from bson import ObjectId
        try:
            doc = await db[collection].find_one({"_id": ObjectId(key)})
        except Exception:
            doc = None
    if doc is None or not doc.get("drill_motif"):
        return {"ok": False, "reason": "unknown_position"}

    motif = str(doc["drill_motif"])
    fen = doc.get("drill_fen") or doc.get("fen")
    answer = str(doc.get("drill_answer_uci") or "")
    submitted = str(move_uci or "")

    exact = bool(submitted) and submitted == answer
    # The question asked for a move that attacks the line, so any move that
    # makes the line is an answer to it -- provided it does not cost material.
    also_works = (not exact
                  and alignment_after(fen, submitted) == motif
                  and not _hands_over_material(fen, submitted))
    correct = exact or also_works

    spec = spec_or_fallback(motif)
    option = spec.reason(reason_id) if reason_id else None
    teaching = (
        "When two of their pieces sit on one line, the back one cannot be "
        "defended by moving the front one. Look for the line before you look "
        "for the move."
    )

    await db.puzzle_attempts.insert_one({
        "user_id": user_id,
        # Never null. See _position_id.
        "puzzle_id": position_id,
        "drill_motif": motif,
        "move_uci": submitted,
        "correct": bool(correct),
        "accepted_as": "best" if exact else "also_works" if also_works else None,
        "reason_id": reason_id or None,
    })

    board = chess.Board(fen)
    try:
        answer_san = board.san(chess.Move.from_uci(answer)) if answer else ""
    except Exception:
        answer_san = ""

    return {
        "ok": True,
        "correct": bool(correct),
        "accepted_as": "best" if exact else "also_works" if also_works else None,
        "answer_san": answer_san,
        "teaching": teaching,
        # What they believed, when they got it wrong and told us why.
        "belief_lead": (option.belief_lead if option and not correct else ""),
        "correction": (option.correction if option and option.correction else ""),
    }


async def drill_supply(db) -> Dict[str, Any]:
    """How many tagged positions exist per motif per collection.

    For the operator, not the player -- the player is never shown a count.
    """
    out: Dict[str, Any] = collections.OrderedDict()
    for collection in {c for c, _, _ in SOURCES}:
        for motif in MOTIFS:
            out["%s.%s" % (collection, motif)] = await db[
                collection].count_documents({"drill_motif": motif})
    return out
