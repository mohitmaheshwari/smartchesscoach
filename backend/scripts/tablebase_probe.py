"""Ask a tablebase what a small ending really is, instead of guessing.

A tablebase is the finished answer for positions with few pieces: someone
solved every one of them, so there is a result rather than an estimate. It is
one of only three things the detector quality lock permits to certify a claim
-- human, board check, or tablebase -- and the only one that needs nobody's
time.

WHY THIS EXISTS
---------------
On 2026-10-19 I claimed players reach drawn endings and lose them, and
supported it by counting MATERIAL SHAPES: "rook and pawn against rook is a
textbook draw". Checked against the engine, two of the three examples were
not drawn at all. Whether a specific rook-and-pawn ending is held depends on
where the kings are and whether the defending rook is behind the pawn, which
a material count cannot see.

So: no more shape-guessing. Probe the position.

USAGE
    python scripts/tablebase_probe.py --self-test
    python scripts/tablebase_probe.py --fen "8/6r1/2p5/8/2k2K2/8/R7/8 b - - 0 58"

The files live outside the repo (E:\\syzygy by default, ~939MB, 3-4-5 pieces
from tablebase.sesse.net). Set SYZYGY_PATH to point elsewhere.
"""
from __future__ import annotations

import argparse
import os
import sys

import chess
import chess.syzygy

DEFAULT_PATH = os.environ.get("SYZYGY_PATH", "E:/syzygy")
MAX_PIECES = 5

# Positions whose answer is not in question, used to prove the files work
# before any of their answers are believed.
# Every one of these must be a LEGAL position. The first version put the
# white queen on e2 and the black king on e5 -- the queen attacks e5 up the
# file, so black was in check on white's move, which cannot occur in a game.
# python-chess then "captured" the king and looked for a table with no black
# pieces, and I read the resulting error as a broken tablebase. The files
# were fine. `check_legal` below stops that happening again.
SELF_TEST = [
    ("k7/8/8/8/8/8/4Q3/4K3 w - - 0 1", "win", "king and queen against king"),
    ("k7/8/8/8/8/8/4B3/4K3 w - - 0 1", "draw", "king and bishop against king"),
    ("k7/8/8/8/8/8/4R3/4K3 w - - 0 1", "win", "king and rook against king"),
    ("k7/8/8/8/8/8/4N3/4K3 w - - 0 1", "draw", "king and knight against king"),
    ("8/8/8/8/8/5k2/5p2/5K2 w - - 0 1", "draw", "king and pawn, defender holds"),
    ("8/8/8/8/8/4k3/4p3/4K3 w - - 0 1", "draw", "king and pawn, kings opposed"),
]


def verdict(board: chess.Board, tables) -> str:
    """win / draw / loss from the side-to-move's point of view, or unknown."""
    if len(board.piece_map()) > MAX_PIECES:
        return "unknown (too many pieces)"
    try:
        wdl = tables.probe_wdl(board)
    except (KeyError, ValueError, chess.syzygy.MissingTableError):
        return "unknown (no table for this material)"
    if wdl > 1:
        return "win"
    if wdl == 1:
        return "win (cursed by the fifty-move rule)"
    if wdl == 0:
        return "draw"
    if wdl == -1:
        return "loss (blessed by the fifty-move rule)"
    return "loss"


def open_tables(path: str):
    if not os.path.isdir(path):
        print("no tablebase directory at %s" % path)
        print("set SYZYGY_PATH, or download the 3-4-5 set from tablebase.sesse.net")
        return None
    return chess.syzygy.open_tablebase(path)


def self_test(path: str) -> int:
    tables = open_tables(path)
    if tables is None:
        return 2
    print("tablebase at %s\n" % path)
    bad = 0
    for fen, expected, label in SELF_TEST:
        board = chess.Board(fen)
        if not board.is_valid():
            print("  %-44s ILLEGAL POSITION -- fix the fixture, not the tablebase"
                  % label)
            bad += 1
            continue
        got = verdict(board, tables)
        ok = got.startswith(expected)
        if not ok:
            bad += 1
        print("  %-44s expected %-5s got %-22s %s" % (
            label, expected, got, "ok" if ok else "WRONG"))
    tables.close()
    print()
    if bad:
        print("%d of %d known answers came back wrong -- do not trust anything"
              " this tablebase says until that is fixed." % (bad, len(SELF_TEST)))
        return 1
    print("all %d known answers correct." % len(SELF_TEST))
    return 0


def probe(path: str, fen: str) -> int:
    tables = open_tables(path)
    if tables is None:
        return 2
    board = chess.Board(fen)
    print("%s" % fen)
    print("  pieces      : %d" % len(board.piece_map()))
    print("  to move     : %s" % ("white" if board.turn else "black"))
    print("  the answer  : %s  (for the side to move)" % verdict(board, tables))
    try:
        dtz = tables.probe_dtz(board)
        print("  distance    : %d (to the next capture or pawn move)" % dtz)
    except Exception:
        pass
    tables.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--fen")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test or not args.fen:
        return self_test(args.path)
    return probe(args.path, args.fen)


if __name__ == "__main__":
    sys.exit(main())
