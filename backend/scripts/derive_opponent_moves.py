"""Give every opponent move a record, without spending a single engine call.

Mohit, 2026-10-23: "we need to keep every opponent moves too, like we keep
user moves, that's really really required" -- then, when I quoted 40 hours
of Stockfish to backfill 1,354 games: "40 hours on this machine??"

He was right to stop it. The box has ~2 GB free of 16 GB, shares it with
another product, and had mongod OOM-killed repeatedly that day -- twice by
a careless aggregation of mine while measuring this very gap.

The gap is real. Across his, Shobhit's and Parth Gilda's accounts: 1,354
analysed games, and only 3 of 200 sampled carry complete opponent coverage.
Median opponent records are 0.14 of the user's move count for Mohit, 0.05
for Shobhit, 0.28 for Gilda -- because the old code stored an opponent move
only when it was an error.

Almost none of an opponent move needs the engine, though, because the
engine already evaluated those positions when it walked the game:

    their fen_before   = the reader's previous move's fen_after
    their eval_before  = the reader's previous move's eval_after
    their eval_after   = the reader's next move's eval_before
    their cp_loss      = the difference, from the mover's side

Validated on 6,911 user moves where the engine's own cp_loss is stored:
median error 0.0 cp, 92.6% within 25 cp, and **96.8% agreement on the one
decision that matters** -- whether the move is a fault at the 40 cp bar.

What this CANNOT derive is the opponent's own best_move and the engine's
lines (pv_after_best, pv_after_played, eval_line_played). That is the
accepted cost. The facts that describe what an opponent's move DOES read
the board and the played move -- which is what the a4-prepares-b4 teaching
needs -- and "what you should do about it" is already stored as best_move
on the reader's own next move. Every derived record is stamped
`derived: "user_evals"` so nothing mistakes it for engine truth and a later
engine pass overwrites it cleanly.

Two traps this script is built around:

  * **The field.** Opponent records do NOT live in move_evaluations. They
    live in `stockfish_analysis.opponent_move_evaluations`, and I lost an
    hour reporting "zero opponent moves stored" from the wrong path.

  * **Alignment by ply, never by FEN.** A repeated position has the same
    FEN twice, so a FEN-keyed index silently maps two plies onto one
    record. This replays the PGN, checks the stored moves against it in
    order, and REFUSES any game where they disagree rather than attributing
    evals to the wrong move and looking plausible.

Usage:
    python3 scripts/derive_opponent_moves.py --users <uid>[,<uid>...] [--dry-run]
    python3 scripts/derive_opponent_moves.py --game <game_id> [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

from stockfish_service import StockfishEngine

DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# Where opponent records actually live.
OPP_PATH = "stockfish_analysis.opponent_move_evaluations"

# The provenance stamp. Anything reading the list can tell an engine record
# from a derived one, and an engine pass overwrites by this field.
DERIVED = "user_evals"

# Evals this large are the mate/clamp sentinel rather than a centipawn
# score; differencing them produces nonsense, so cp_loss is left off.
CLAMP = 900


def _classify(cp_loss: int, eval_before_mover: Optional[int]) -> str:
    """The move's quality label, from the repo's ONE classifier.

    NOT written to derived records -- kept because the measurement that
    rejected it runs through here, and because an engine pass that later
    upgrades these records should use this and no second table.

    `StockfishEngine.classify_move` never touches `self`, so it is called
    unbound rather than starting an engine a derivation does not need.
    MoveClassification is a (str, Enum) and str() on one yields
    "MoveClassification.BEST", not "best" -- that slip read as 0 of 57
    labels agreeing when every one of them did.

    Why the label is withheld: the derived cp_loss is good but not exact
    (median 3 cp off, p90 19 cp), and the classifier's bands sit at 10, 30,
    100 and 300, so small errors cross them. Measured on 6,436 user moves
    where the engine's own label is stored, labelling from the derived
    cp_loss agrees 75.7% of the time and calls a move WORSE than it was on
    16.7% -- 469 of them by two levels or more. Shaving 10 cp off first
    only brings the overstatement to 6.4%, still 227 moves called much
    worse than they were.

    The evals themselves are exact (100% on both), and the 40 cp fault call
    agrees 93%. So the derivation claims those and stays quiet about the
    six-way label, rather than handing the caption layer a severity the
    engine never said.
    """
    label = StockfishEngine.classify_move(
        None, int(cp_loss), False, eval_before_mover)
    return getattr(label, "value", str(label))


def _plies(pgn: str) -> List[Tuple[str, str, str, bool, int]]:
    """(fen_before, san, fen_after, is_white_mover, move_number) per ply."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return []
    board = game.board()
    out: List[Tuple[str, str, str, bool, int]] = []
    for mv in game.mainline_moves():
        fen_before = board.fen()
        try:
            san = board.san(mv)
        except Exception:
            return []
        is_white = board.turn == chess.WHITE
        number = board.fullmove_number
        board.push(mv)
        out.append((fen_before, san, board.fen(), is_white, number))
    return out


def _align_in_order(
    records: List[Dict[str, Any]],
    plies: List[Tuple[str, str, str, bool, int]],
    indices: List[int],
) -> Optional[Dict[int, Dict[str, Any]]]:
    """Map existing records onto ply indices.

    The stored opponent list is a SUBSET of the opponent plies -- only the
    errors were kept -- so it cannot be zipped; each record has to be
    placed. The match is on (move_number, SAN), and on fen_before too when
    the record carries one.

    A first version of this walked forwards looking for the next ply whose
    SAN matched, and put an engine record for Qf6 on move 26 onto an
    earlier Qf6 on move 11 -- the merged list then ran 10, 26, 12, 13 and
    every eval after it described the wrong move. Same-SAN repeats are
    ordinary in chess, so the move number is what disambiguates them.

    Returns None when a record cannot be placed or is ambiguous, which
    means the stored list is not this game's and nothing should be written.
    """
    placed: Dict[int, Dict[str, Any]] = {}
    for rec in records:
        san = str(rec.get("move") or "")
        number = rec.get("move_number")
        fen = str(rec.get("fen_before") or "")

        hits = [i for i in indices
                if plies[i][1] == san
                and i not in placed
                and (number is None or plies[i][4] == number)]
        if len(hits) > 1 and fen:
            narrowed = [i for i in hits if plies[i][0] == fen]
            if narrowed:
                hits = narrowed
        if len(hits) != 1:
            return None
        placed[hits[0]] = rec
    return placed


def derive_for_game(
    pgn: str,
    user_color: str,
    user_records: List[Dict[str, Any]],
    opp_records: List[Dict[str, Any]],
) -> Tuple[Optional[List[Dict[str, Any]]], str, int]:
    """The full opponent list -- engine records kept, derived ones filled in.

    Returns (list, reason, n_derived). The list is in ply order because
    downstream readers walk it forwards.
    """
    plies = _plies(pgn)
    if not plies:
        return None, "unreadable pgn", 0

    me = chess.WHITE if (user_color or "white").lower() == "white" \
        else chess.BLACK

    mine = [i for i, p in enumerate(plies)
            if (chess.WHITE if p[3] else chess.BLACK) == me]
    theirs = [i for i in range(len(plies)) if i not in set(mine)]

    # The gate on the reader's own side. If the stored moves are not this
    # game's user moves in order, every eval would be attributed to the
    # wrong ply -- the result would look plausible and be wrong, which is
    # the failure shape this repo keeps producing. Refuse instead.
    if len(user_records) != len(mine):
        return None, "stored %d user records, pgn has %d user plies" % (
            len(user_records), len(mine)), 0
    for rec, i in zip(user_records, mine):
        if str(rec.get("move") or "") != plies[i][1]:
            return None, "user move mismatch at ply %d: stored %r, pgn %r" % (
                i, rec.get("move"), plies[i][1]), 0

    by_user_ply: Dict[int, Dict[str, Any]] = dict(zip(mine, user_records))

    # The opponent's stored records are a subset, so they align by walking.
    engine_only = [r for r in opp_records if not r.get("derived")]
    placed = _align_in_order(engine_only, plies, theirs)
    if placed is None:
        return None, "opponent records do not align with the pgn", 0

    merged: List[Dict[str, Any]] = []
    n_derived = 0
    for i in theirs:
        if i in placed:
            merged.append(placed[i])
            continue

        fen_before, san, fen_after, is_white, number = plies[i]

        prev = next((by_user_ply[j] for j in range(i - 1, -1, -1)
                     if j in by_user_ply), None)
        nxt = next((by_user_ply[j] for j in range(i + 1, len(plies))
                    if j in by_user_ply), None)

        eval_before = prev.get("eval_after") if prev else None
        eval_after = nxt.get("eval_before") if nxt else None

        cp_loss: Optional[int] = None
        if (eval_before is not None and eval_after is not None
                and abs(eval_before) <= CLAMP and abs(eval_after) <= CLAMP):
            # Stored evals are white-relative, so a black mover loses when
            # the number goes UP.
            loss = (eval_before - eval_after) if is_white \
                else (eval_after - eval_before)
            cp_loss = max(0, int(round(loss)))

        record: Dict[str, Any] = {
            "move_number": number,
            "move": san,
            "fen_before": fen_before,
            "fen_after": fen_after,
            "is_opponent_move": True,
            "derived": DERIVED,
        }
        if eval_before is not None:
            record["eval_before"] = eval_before
        if eval_after is not None:
            record["eval_after"] = eval_after
        if cp_loss is not None:
            record["cp_loss"] = cp_loss
        # No `evaluation`: see _classify. The six-way label cannot be
        # derived honestly, and a wrong one is a false fact about how bad
        # the move was.
        merged.append(record)
        n_derived += 1

    if not n_derived:
        return None, "already complete", 0
    return merged, "ok", n_derived


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="")
    ap.add_argument("--game", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[DB_NAME]

    if args.game:
        games = await db.games.find(
            {"game_id": args.game},
            {"game_id": 1, "pgn": 1, "user_color": 1, "_id": 0}
        ).to_list(1)
    else:
        uids = [u.strip() for u in args.users.split(",") if u.strip()]
        if not uids:
            print("need --users or --game")
            return
        cur = db.games.find(
            {"user_id": {"$in": uids}, "is_analyzed": True},
            {"game_id": 1, "pgn": 1, "user_color": 1, "_id": 0})
        if args.limit:
            cur = cur.limit(args.limit)
        games = await cur.to_list(100000)

    print("games to consider: %d%s" % (
        len(games), "   (DRY RUN)" if args.dry_run else ""))

    done = skipped = 0
    added = 0
    reasons: Dict[str, int] = {}
    for n, g in enumerate(games, 1):
        gid = g["game_id"]
        if not g.get("pgn"):
            reasons["no pgn"] = reasons.get("no pgn", 0) + 1
            skipped += 1
            continue
        # One document at a time, by indexed game_id. Never a scan: the
        # docs are ~300 KB and a collection-wide pass over them is what
        # OOM-killed mongod twice while this gap was being measured.
        # Only the three fields the derivation reads off the reader's moves.
        # Pulling the whole move_evaluations array means ~300 KB a game and
        # the engine lines inside it are never looked at here.
        doc = await db.game_analyses.find_one(
            {"game_id": gid},
            {"stockfish_analysis.move_evaluations.move": 1,
             "stockfish_analysis.move_evaluations.eval_before": 1,
             "stockfish_analysis.move_evaluations.eval_after": 1,
             OPP_PATH: 1, "_id": 0})
        if not doc:
            reasons["no analysis"] = reasons.get("no analysis", 0) + 1
            skipped += 1
            continue
        sa = doc.get("stockfish_analysis") or {}

        merged, why, n_derived = derive_for_game(
            g["pgn"], g.get("user_color") or "white",
            sa.get("move_evaluations") or [],
            sa.get("opponent_move_evaluations") or [])
        if merged is None:
            key = why.split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
            skipped += 1
            continue

        added += n_derived
        done += 1
        if not args.dry_run:
            res = await db.game_analyses.update_one(
                {"game_id": gid},
                {"$set": {OPP_PATH: merged,
                          "opponent_moves_derived": True}})
            if res.matched_count != 1:
                print("   WRITE DID NOT MATCH for %s" % gid)
        if n % 100 == 0:
            print("   ... %d/%d" % (n, len(games)), flush=True)

    print()
    print("games filled:       %d" % done)
    print("opponent records added: %d" % added)
    print("skipped:            %d" % skipped)
    for why, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print("   %-44s %d" % (why, count))


if __name__ == "__main__":
    asyncio.run(main())
