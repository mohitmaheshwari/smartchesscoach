"""Does the coaching we computed actually reach the words a player reads?

`what_a_real_user_sees.py` asks whether a PAGE is alive. This asks the next
question down: a detector fired on this move -- did anything about it survive
into the caption the player actually gets?

Four separate times on 2026-09-19/20, working machinery reached nobody, and
every one was invisible until someone went looking:

  - concept detectors gated on "the move played WAS the engine's move", so
    across 12,365 moves they returned 1,639 "applied" and 5 "missed". A
    detector that can only congratulate cannot teach.
  - opening_play and trap_detection were handed move_history_san built from
    move_evaluations, which holds ONLY the user's moves. Half the game. They
    fired 0 times while working perfectly on a constructed position.
  - the back-rank / in-check / opponent-plan mate lessons were written into
    /admin/detector-review's own caption producer, so a game review of the
    same position still said "Bxd5 allows mate in 3."
  - narrator_claim_verifier assumed any mate mention on a user move meant OUR
    best move mates, so it rejected "Bxd5 allows mate in 2." and the pipeline
    replaced every allowed-mate caption with the safe floor.

That is not four coincidences. It is one disease -- we build the mechanism and
never check the last wire -- and it is cheap to test for: fire the detectors,
render the real caption, and count the moves where the first happened and the
second did not.

    python scripts/last_wire_audit.py                 # 40 games
    python scripts/last_wire_audit.py --games 200
    python scripts/last_wire_audit.py --json          # for a cron

Exit code is 1 when a detector fires and NOTHING specific reaches the player,
which is the shape worth waking someone for.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
from motor.motor_asyncio import AsyncIOMotorClient

# A caption that says only "X was the stronger move" has reached the player
# with nothing a detector contributed. Matching on the floor's own shapes
# rather than a word list, because a word list is how caption audits go wrong.
GENERIC_MARKERS = (
    "was the stronger move",
    "is the best move",
    "was the move",
    "look for attacks on your king",
    "before moving, calculate every enemy check",
)
GENERIC_RULES = ("R_FALLBACK", "R16_board_state_fallback", "R_TIER3")


def _is_generic(caption: str, rule_name: str) -> bool:
    low = (caption or "").lower()
    if not low.strip():
        return True
    if any(r.lower() in (rule_name or "").lower() for r in GENERIC_RULES):
        return True
    # Short AND floor-shaped: a long caption that happens to contain one of
    # these still carries teaching around it.
    if len(low.split()) <= 18 and any(m in low for m in GENERIC_MARKERS):
        return True
    return False


PROBE_ERRORS: collections.Counter = collections.Counter()


def _detectors_that_fire(board: chess.Board, move_eval: Dict[str, Any],
                         colour: str) -> List[str]:
    """Which detectors have something to say about this move.

    Every probe failure is COUNTED, never swallowed. An audit whose own
    probes break silently reports zeros as findings, which is the mistake
    this script exists to catch -- four false zeros came from exactly that
    on 2026-09-19/20.
    """
    fired: List[str] = []
    san = move_eval.get("move")
    best = move_eval.get("best_move")
    cp_loss = int(move_eval.get("cp_loss") or 0)
    try:
        played = board.parse_san(str(san))
    except Exception:  # noqa: BLE001
        return fired

    from analysis_interpreter import mate_gate_label
    if mate_gate_label(move_eval.get("mate_info"), colour):
        fired.append("allowed_mate")

    try:
        from services.played_hangs_detector import detect_played_hangs
        if detect_played_hangs(board.copy(stack=False), played, cp_loss,
                               mate_in_play=bool(move_eval.get("mate_info"))):
            fired.append("simple_hang")
    except Exception as exc:  # noqa: BLE001
        PROBE_ERRORS[f"simple_hang: {type(exc).__name__}: {exc}"[:90]] += 1

    if best:
        pv = move_eval.get("pv_after_best") or []
        for name, builder in (
                ("discovered_attack",
                 "services.discovered_attack_puzzle_proof:build_discovered_attack_proof"),
                ("fork", "services.fork_puzzle_proof:build_fork_proof")):
            try:
                mod_name, fn_name = builder.split(":")
                mod = __import__(mod_name, fromlist=[fn_name])
                bundle = getattr(mod, fn_name)(
                    board.copy(stack=False), san, best, pv, cp_loss)
                if bundle and getattr(bundle.verifier, "verified", False):
                    fired.append(name)
            except Exception as exc:  # noqa: BLE001
                PROBE_ERRORS[f"{name}: {type(exc).__name__}: {exc}"[:90]] += 1

    # The concept detectors, through the production runner.
    try:
        from services.concept_detectors._runner import run_detectors_for_move
        col = chess.WHITE if str(colour).lower().startswith("w") else chess.BLACK
        for skill_id, outcome in run_detectors_for_move(
                board.copy(stack=False), played, col,
                move_number=move_eval.get("move_number"),
                best_move_san=best,
                best_move_uci=move_eval.get("best_move_uci"),
                cp_loss=cp_loss, mate_info=move_eval.get("mate_info"),
                include_shadow=True):
            if outcome == "wrong":
                fired.append(f"missed:{skill_id}")
    except Exception as exc:  # noqa: BLE001
        PROBE_ERRORS[f"concept runner: {type(exc).__name__}: {exc}"[:90]] += 1
    return fired


async def _audit_game(db, game: Dict[str, Any], analysis: Dict[str, Any],
                      stats: Dict[str, collections.Counter]) -> None:
    from services.game_decryption_v5_service import generate_game_decryption_v5

    evs = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
    if not evs:
        return
    try:
        cards = await generate_game_decryption_v5(
            pgn=game.get("pgn") or "",
            user_color=game.get("user_color"),
            move_evaluations=evs,
            user_id=game.get("user_id") or "audit",
            db=db,
            game_id=game.get("game_id"),
            persist_learning_side_effects=False,
            allow_llm_polish=False,
        )
    except Exception as exc:  # noqa: BLE001
        PROBE_ERRORS[f"render: {type(exc).__name__}: {exc}"[:90]] += 1
        return

    by_move = {}
    for card in cards:
        key = card.get("move_number")
        if key is not None and card.get("is_user_move"):
            by_move[int(key)] = card

    for m in evs:
        if m.get("is_opponent_move") or int(m.get("cp_loss") or 0) < 100:
            continue
        fen = m.get("fen_before")
        if not fen:
            continue
        try:
            board = chess.Board(str(fen))
        except Exception:  # noqa: BLE001
            continue
        fired = _detectors_that_fire(board, m, game.get("user_color") or "white")
        if not fired:
            continue
        card = by_move.get(int(m.get("move_number") or -1)) or {}
        caption = (card.get("caption") or "").strip()
        rule = str(card.get("rule_name") or "")
        generic = _is_generic(caption, rule)
        for name in fired:
            stats[name]["fired"] += 1
            if not caption:
                stats[name]["player sees NOTHING"] += 1
            elif generic:
                stats[name]["player sees a generic floor"] += 1
            else:
                stats[name]["reaches the player"] += 1
            if "SOFTENED" in rule:
                stats[name]["deleted by the verifier"] += 1


async def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    stats: Dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    scanned = 0
    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"game_id": 1, "stockfish_analysis": 1}).limit(args.games)
    async for analysis in cursor:
        game = await db.games.find_one({"game_id": analysis.get("game_id")})
        if not game or not game.get("pgn"):
            continue
        scanned += 1
        await _audit_game(db, game, analysis, stats)

    broken = []
    for name, c in stats.items():
        if c["fired"] and not c["reaches the player"]:
            broken.append(name)

    if args.json:
        print(json.dumps({
            "games": scanned,
            "detectors": {k: dict(v) for k, v in stats.items()},
            "last_wire_broken": broken,
            "probe_errors": dict(PROBE_ERRORS),
        }, indent=2))
    else:
        print(f"games rendered: {scanned}")
        print()
        head = f"{'detector':34s} {'fired':>6s} {'reaches':>8s} {'generic':>8s} {'nothing':>8s}"
        print(head)
        print("-" * len(head))
        for name, c in sorted(stats.items(), key=lambda kv: -kv[1]["fired"]):
            print(f"{name:34s} {c['fired']:6d} "
                  f"{c['reaches the player']:8d} "
                  f"{c['player sees a generic floor']:8d} "
                  f"{c['player sees NOTHING']:8d}")
        print()
        if PROBE_ERRORS:
            print("PROBE FAILURES -- these are MY bug, not a finding. A zero")
            print("below a broken probe means nothing:")
            for detail, n in PROBE_ERRORS.most_common(8):
                print(f"   {n:5d}x  {detail}")
            print()
        if broken:
            print("LAST WIRE BROKEN -- fires, and nothing specific ever reaches a player:")
            for name in broken:
                print(f"   {name}  ({stats[name]['fired']} fires)")
        else:
            print("No detector fires into silence.")

    # A silent probe failure is not a clean run.
    return 1 if (broken or PROBE_ERRORS) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
