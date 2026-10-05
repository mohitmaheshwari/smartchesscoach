"""Which authored caption variants never fire?

A variant can be written, given a correct predicate and correct template
slots, be wired into a live rule -- and still never reach a single reader.
Nothing told us the difference until Mohit read a card and asked why the
mate was not mentioned.

`why_user_missed_mate` is the case that prompted this. It is authored in
R12_blunder.json, selected on {"missed_tactic_kind": "mate"}, renders
"it would have led to mate in N moves", and had fired ZERO times across
188,456 stored cards -- while its two sibling mate clauses fired 894 and
313 times. Roughly 4,900 cards were moves where the player had a forced
mate and played something else, 3,547 of them already blunder-tier. The
opportunity was there every time; the clause never spoke.

A variant with zero fires against thousands of chances is a bug by
definition, and it is cheap to find mechanically.

This counts the variant the selector ACTUALLY picked, via the observer in
caption_templates -- not keywords in the rendered text. Keyword scans of
captions undercount coverage and invent phantom gaps; measuring this bug
that way is what produced a false "0 occurrences" reading earlier.

Usage:
  docker exec -i chess-coach-backend python -m scripts.audit_variant_fire_counts
  ... --limit 400          how many analyses to replay (default 300)
  ... --rule R12_blunder   restrict to one rule
Exit 0 always: this reports, it does not gate. Wire it into deploy.sh only
once the known-silent variants are either fixed or explicitly retired.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_ROOT)

from services.caption_templates import (  # noqa: E402
    all_rule_names,
    authored_variants,
    set_variant_observer,
)

# The decision lists a rule can hold. Each is a separate namespace of
# variants, so a variant silent in one is not excused by another.
LIST_KEYS = ("select_variant", "why_clauses_user", "why_clauses_opp",
             "failure_mode_clauses_user", "failure_mode_clauses_opp",
             "teaching_principles")


def _catalogue(only_rule=None):
    """Everything that COULD fire. Without this denominator a zero is
    indistinguishable from 'this rule has no variants'."""
    out = {}
    for rule in all_rule_names():
        if only_rule and rule != only_rule:
            continue
        for key in LIST_KEYS:
            for variant in authored_variants(rule, key):
                out.setdefault((rule, key), set()).add(variant)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--rule", default=None)
    args = ap.parse_args()

    catalogue = _catalogue(args.rule)
    authored_total = sum(len(v) for v in catalogue.values())
    print(f"authored variants: {authored_total} "
          f"across {len({r for r, _ in catalogue})} rules")

    fired = collections.Counter()
    set_variant_observer(lambda rule, key, variant:
                         fired.update([(rule, key, variant)]) if variant else None)

    replayed = _replay(args.limit)
    set_variant_observer(None)
    print(f"replayed {replayed} moves\n")

    silent = []
    for (rule, key), variants in sorted(catalogue.items()):
        for variant in sorted(variants):
            n = fired[(rule, key, variant)]
            if n == 0:
                silent.append((rule, key, variant))

    print(f"{'VARIANT':<52} {'RULE':<16} FIRES")
    for (rule, key, variant), n in fired.most_common(25):
        print(f"  {variant:<50} {rule:<16} {n}")

    print(f"\nNEVER FIRED: {len(silent)} of {authored_total}")
    for rule, key, variant in silent:
        print(f"  {variant:<50} {rule}.{key}")
    if silent:
        print("\nA variant that never fires is either broken or should be "
              "retired. Both are worth knowing; neither is visible today.")
    return 0


def _replay(limit: int) -> int:
    """Render real stored moves through the real caption path."""
    import asyncio
    return asyncio.run(_replay_async(limit))


async def _replay_async(limit: int) -> int:
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.caption_pipeline import (
        build_move_teaching_decision, MoveInputs, CrossMoveState)
    import chess

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    cur = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True}},
        {"user_color": 1, "stockfish_analysis.move_evaluations": 1}).limit(limit)
    moves = 0
    async for a in cur:
        user_color = (a.get("user_color") or "white")
        for m in (a.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            fen = m.get("fen_before")
            san = m.get("move")
            if not fen or not san:
                continue
            try:
                board = chess.Board(fen)
                is_white = board.turn == chess.WHITE
                inputs = MoveInputs(
                    fen_before=fen,
                    played_san=san,
                    mover_is_user=not m.get("is_opponent_move"),
                    mover_is_white=is_white,
                    user_color=user_color,
                    full_move_number=board.fullmove_number,
                    move_history_san=[],
                    best_move_san=m.get("best_move"),
                    eval_before_cp=_int(m.get("eval_before")),
                    eval_after_cp=_int(m.get("eval_after")),
                    cp_loss=_int(m.get("cp_loss")) or 0,
                    pv_after_played=list(m.get("pv_after_played") or []),
                    pv_after_best=list(m.get("pv_after_best") or []),
                )
                build_move_teaching_decision(inputs, CrossMoveState())
                moves += 1
            except Exception:
                continue
    return moves


def _int(v):
    try:
        return int(v)
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
