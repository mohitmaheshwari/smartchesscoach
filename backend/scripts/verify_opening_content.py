#!/usr/bin/env python3
"""Engine-check the opening curriculum before it can ship.

The structural rules (is this a legal line, does the tree replay, is the
colour right) already live in ``services.curriculum_content_validator`` and
run at serve time. This script covers the part an offline tool has to do,
because it needs Stockfish and several seconds per position: whether the
chess *claim* a trap makes is actually true.

That claim depends on what kind of trap it is, and conflating the kinds is
how the curriculum ended up shipping an Elephant Trap that told the user to
capture on a square with no piece on it:

  punish      the opponent errs and we punish it. Their trigger_move must
              really lose material, and our_reply must really be the answer.
  avoid       the same shape, but it is *we* who can fall in. The lesson is
              "do not play this", so the move must genuinely be bad.
  bait        we offer something. It only wins if they take, so the move may
              well be objectively worse, and the entry has to say what
              happens when they decline instead.
  common_line an entry filed under traps that is not a trap at all: a normal
              line worth knowing. It must not claim anyone blundered, so the
              only check is that whatever we recommend is sound.
  only_move   the trigger is playable, but after our_reply the opponent has
              essentially one move that survives. That is what makes it
              dangerous at club level, and it is checkable: count them.

It also checks the teaching lines themselves. A tree node's `next` is the
move we put in front of a student as the right answer, so it has to be a
move the engine can live with -- not merely a legal one.

Usage:
    python backend/scripts/verify_opening_content.py [opening_key ...]
    LINE_REPORT=1 python backend/scripts/verify_opening_content.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import chess
import chess.engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = Path(
    os.environ.get("OPENING_CURRICULUM", BACKEND_ROOT / "data" / "opening_curriculum.json")
)
STOCKFISH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
DEPTH = int(os.environ.get("VERIFY_DEPTH", "20"))

# A move we call a mistake has to lose enough that a student would feel it.
MISTAKE_MIN_CP = 60
# A move we tell the student to play has to be close to the engine's choice.
REPLY_MAX_CP_LOSS = 40
# An "only move" trap states exactly how many replies lose on the spot. That
# is a falsifiable number, so it is checked against the board rather than
# against a centipawn window somebody picked to make a sentence come true.

VALID_TYPES = {"punish", "avoid", "bait", "only_move", "common_line"}

# Measured over all 183 taught moves in the curriculum: p50 3, p90 19, p99 47,
# max 76. Repeat analyses of the same position disagree by 20-30cp, so a small
# figure here is search noise, not a bad recommendation. The genuinely large
# ones are the defining move of a gambit, which is a choice rather than an
# error, so the gate only fires when we recommend a move the engine dislikes
# AND it is not the move that defines the opening.
TAUGHT_MOVE_MAX_CP_LOSS = 60


def _score(info, pov) -> int:
    return info["score"].pov(pov).score(mate_score=10000)


def _replay(moves, errors, label):
    board = chess.Board()
    for san in moves or []:
        try:
            board.push_san(san)
        except ValueError:
            errors.append(f"{label}: illegal move {san!r} in trigger_after")
            return None
    return board


def _analyse(engine, board):
    return engine.analyse(board, chess.engine.Limit(depth=DEPTH))


def verify_trap(trap, engine, errors, opening):
    name = trap.get("name") or "unnamed"
    label = f"{opening}/{name}"

    trap_type = str(trap.get("trap_type") or "").strip()
    if trap_type not in VALID_TYPES:
        errors.append(
            f"{label}: trap_type {trap_type!r} is not one of {sorted(VALID_TYPES)}. "
            "Without it nobody can tell whether this move is meant to be good or bad."
        )
        return

    board = _replay(trap.get("trigger_after"), errors, label)
    if board is None:
        return

    trigger = str(trap.get("trigger_move") or "")
    if not trigger:
        errors.append(f"{label}: no trigger_move")
        return
    try:
        trigger_move = board.parse_san(trigger)
    except ValueError:
        errors.append(
            f"{label}: trigger_move {trigger!r} is not legal there. "
            f"It is {'White' if board.turn else 'Black'} to move after trigger_after."
        )
        return

    mover = board.turn
    before = _analyse(engine, board)
    best_cp = _score(before, mover)
    best_san = board.san(before["pv"][0])

    after_trigger = board.copy()
    after_trigger.push(trigger_move)
    trigger_cp = _score(_analyse(engine, after_trigger), mover)
    trigger_loss = best_cp - trigger_cp

    if trap_type in {"punish", "avoid"}:
        if trigger_loss < MISTAKE_MIN_CP:
            errors.append(
                f"{label}: calls {trigger} a mistake, but it only loses {trigger_loss}cp "
                f"(engine best {best_san}). Either it is not a trap or the type is wrong."
            )
        _check_reply(trap, after_trigger, engine, errors, label)

    elif trap_type == "common_line":
        if not str(trap.get("description") or "").strip():
            errors.append(f"{label}: a common_line entry still needs a description")
        if trap.get("our_reply"):
            _check_reply(trap, after_trigger, engine, errors, label)

    elif trap_type == "bait":
        for field in ("if_declined", "trap_idea"):
            if not str(trap.get(field) or "").strip():
                errors.append(
                    f"{label}: a bait trap must fill {field!r} so the student is told "
                    "what happens when the opponent does not take."
                )

    elif trap_type == "only_move":
        _check_reply(trap, after_trigger, engine, errors, label)
        reply = str(trap.get("our_reply") or "")
        try:
            reply_move = after_trigger.parse_san(reply)
        except ValueError:
            return
        after_reply = after_trigger.copy()
        after_reply.push(reply_move)
        total, mated = _count_replies(after_reply)
        for field, actual in (("total_reply_count", total), ("mate_reply_count", mated)):
            claimed = trap.get(field)
            if claimed is None:
                errors.append(
                    f"{label}: an only_move trap must state {field}, because that is "
                    "the claim the lesson makes to the student."
                )
            elif int(claimed) != actual:
                errors.append(
                    f"{label}: says {field}={claimed} after {reply}, board says {actual}."
                )
        safest = str(trap.get("safest_reply") or "")
        if safest:
            try:
                after_reply.parse_san(safest)
            except ValueError:
                errors.append(f"{label}: safest_reply {safest!r} is not legal there")


def _check_reply(trap, board, engine, errors, label):
    """The move we tell the student to play has to be the real answer."""
    reply = str(trap.get("our_reply") or "")
    if not reply:
        errors.append(f"{label}: no our_reply, so the trap never states the punishment")
        return
    try:
        reply_move = board.parse_san(reply)
    except ValueError:
        errors.append(f"{label}: our_reply {reply!r} is not legal in the trap position")
        return
    mover = board.turn
    info = _analyse(engine, board)
    best_cp = _score(info, mover)
    best_san = board.san(info["pv"][0])
    after = board.copy()
    after.push(reply_move)
    loss = best_cp - _score(_analyse(engine, after), mover)
    if loss > REPLY_MAX_CP_LOSS:
        errors.append(
            f"{label}: teaches {reply} as the punishment, but it gives up {loss}cp "
            f"against {best_san}."
        )


def _count_replies(board):
    """How many replies exist, and how many let us mate immediately.

    No engine needed: mate is a fact about the board. Note the mate belongs
    to *our* next move, not to their reply, which is the easy thing to get
    backwards here.
    """
    total = 0
    mated = 0
    for reply in board.legal_moves:
        total += 1
        after_reply = board.copy()
        after_reply.push(reply)
        for punish in after_reply.legal_moves:
            probe = after_reply.copy()
            probe.push(punish)
            if probe.is_checkmate():
                mated += 1
                break
    return total, mated


def walk_lines(responses, board, path, engine, rows, opening, preview_next=False):
    """Score every move the tree teaches, so no lesson recommends a bad move."""
    for san, child in (responses or {}).items():
        if not isinstance(child, dict):
            continue
        after = board.copy()
        try:
            after.push_san(san)
        except ValueError:
            rows.append((999, opening, " ".join(path + [san]), san, "ILLEGAL"))
            continue
        here = path + [san]
        nxt = str(child.get("next") or "")
        nxt_board = after
        if nxt and not preview_next:
            mover = after.turn
            info = engine.analyse(after, chess.engine.Limit(depth=DEPTH))
            best_cp = _score(info, mover)
            best_san = after.san(info["pv"][0])
            probe = after.copy()
            try:
                probe.push_san(nxt)
            except ValueError:
                rows.append((999, opening, " ".join(here), nxt, "ILLEGAL", ""))
                continue
            cp = _score(engine.analyse(probe, chess.engine.Limit(depth=DEPTH)), mover)
            rows.append((best_cp - cp, opening, " ".join(here), nxt, best_san,
                         str(child.get("deliberate_choice") or "")))
            nxt_board = probe
            here = here + [nxt]
        walk_lines(child.get("responses"), nxt_board, here, engine, rows, opening)


def line_report(data, engine):
    rows = []
    for key, entry in data.items():
        if not isinstance(entry, dict) or not entry.get("tree"):
            continue
        plays_white = str(entry.get("color") or "white").lower() != "black"
        walk_lines(entry["tree"], chess.Board(), [], engine, rows, key,
                   preview_next=plays_white)
    rows.sort(key=lambda r: -r[0])
    losses = [r[0] for r in rows if r[0] < 999]
    print(f"  taught moves scored: {len(rows)}")
    if losses:
        losses_sorted = sorted(losses)
        def pct(p):
            return losses_sorted[min(len(losses_sorted) - 1, int(len(losses_sorted) * p))]
        print(f"  cp given up vs engine best -- p50 {pct(.5)}  p75 {pct(.75)}  "
              f"p90 {pct(.9)}  p99 {pct(.99)}  max {max(losses)}")
    print("  worst 20:")
    for loss, opening, path, mv, best, _why in rows[:20]:
        print(f"    {loss:5} {opening:26} after {path[:52]:52} teaches {mv:7} best {best}")
    return rows


def main() -> int:
    data = json.loads(CURRICULUM.read_text(encoding="utf-8"))
    if os.environ.get("LINE_REPORT"):
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH) as engine:
            line_report(data, engine)
        return 0
    wanted = set(sys.argv[1:])
    errors: list[str] = []
    checked = 0
    lines = 0
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH) as engine:
        for key, entry in data.items():
            if not isinstance(entry, dict):
                continue
            if wanted and key not in wanted:
                continue
            for trap in entry.get("traps") or []:
                checked += 1
                verify_trap(trap, engine, errors, key)
            if entry.get("tree"):
                rows = []
                plays_white = str(entry.get("color") or "white").lower() != "black"
                walk_lines(entry["tree"], chess.Board(), [], engine, rows, key,
                           preview_next=plays_white)
                lines += len(rows)
                for loss, opening, path, mv, best, why in rows:
                    if best == "ILLEGAL":
                        errors.append(f"{opening}: taught move {mv!r} is illegal after {path}")
                    elif loss > TAUGHT_MOVE_MAX_CP_LOSS and mv != best and len(path.split()) > 2:
                        # A move the engine dislikes may still be the right thing
                        # to teach, but only if the reason is written down where
                        # the next person can read it.
                        if not why:
                            errors.append(
                                f"{opening}: after {path} we teach {mv}, which gives up "
                                f"{loss}cp against {best}. If that is deliberate, say why "
                                f"in the node's deliberate_choice field."
                            )
    print(f"  traps checked : {checked}")
    print(f"  taught moves  : {lines}")
    print(f"  problems      : {len(errors)}")
    for err in errors:
        print(f"    - {err}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
