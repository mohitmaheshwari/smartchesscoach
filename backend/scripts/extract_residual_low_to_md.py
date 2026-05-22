"""Extract the residual LOW captions from the 500-game audit and
write a per-position MD file for each.

The verifier found 0 mechanical hallucinations — these captions
aren't bugs, they're the engine-speak FLOOR (correctly classified
LOW). Mohit asked for per-position MDs for review.

Run inside container:
    python /app/backend/scripts/extract_residual_low_to_md.py \
        --out-dir /app/docs/caption_backlog_500/residual_low
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chess
import chess.engine
from motor.motor_asyncio import AsyncIOMotorClient


_STOCKFISH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")


def _engine_analysis(fen: str):
    try:
        b = chess.Board(fen)
    except Exception:
        return {}
    try:
        with chess.engine.SimpleEngine.popen_uci(_STOCKFISH) as e:
            info = e.analyse(b, chess.engine.Limit(depth=15), multipv=3)
    except Exception as exc:
        return {"error": str(exc)}
    out = []
    for line in info:
        score = line.get("score")
        if score is None:
            continue
        cp = score.white().score(mate_score=10000)
        pv = line.get("pv") or []
        tmp = b.copy()
        sans = []
        for mv in pv[:6]:
            try:
                sans.append(tmp.san(mv)); tmp.push(mv)
            except Exception:
                break
        out.append({"cp": cp, "pv": sans})
    return {"multipv": out}


def _md(idx: int, m: dict, ga_meta: dict, engine: dict) -> str:
    multipv_md = ""
    if engine.get("multipv"):
        lines = []
        for j, line in enumerate(engine["multipv"], 1):
            lines.append(f"  #{j} eval(W) `{line['cp']:+d}cp`  PV: `{' '.join(line['pv'])}`")
        multipv_md = "\n".join(lines)
    elif engine.get("error"):
        multipv_md = f"  (engine: {engine['error']})"

    fen = m.get("fen_before", "")
    cap = m.get("caption", "")
    move_san = m.get("move_san", "")
    best_san = m.get("best_move_san", "")
    cpl = m.get("cp_loss")
    move_num = m.get("move_number")
    gid = ga_meta.get("game_id", "")[:12]
    user_color = ga_meta.get("user_color", "")

    # Identify which engine-speak variant
    if "wins material in the resulting line" in cap:
        variant = "why_user_missed_material"
        diagnosis = (
            "Engine PV shows a material gain in the resulting line, but the "
            "eval guard rejected the specific piece_capture claim (eval not "
            "+400cp after best move from user POV). Detector downgraded to "
            "the generic 'wins material' fallback."
        )
    elif "Opponent's strongest reply:" in cap:
        variant = "why_user_reply"
        diagnosis = (
            "No tactical / positional detector matched this position. The "
            "engine has an opp_reply in its PV, so the engine-speak "
            "fallback fires. cp_loss is 100-249 (mistake tier) AND user is "
            "in a balanced position (per v51 gating)."
        )
    else:
        variant = "(unknown)"
        diagnosis = "Caption doesn't match the expected engine-speak phrasings."

    return f"""# {gid} m{move_num} {move_san} — residual LOW #{idx}

**Variant:** `{variant}`
**Position (FEN):** `{fen}`
**Move played:** `{move_san}` (cp_loss `{cpl}`)
**Engine's best (stored):** `{best_san}`
**User color:** {user_color}

## Caption as shipped

> {cap}

## Live engine view (depth 15, multipv 3)

{multipv_md}

## Diagnosis

{diagnosis}

This is **not a bug** — the v51 asymmetric threshold + v55 winning/losing
flags correctly suppress the variants in winning/losing positions. They
fire only in balanced positions where:
- cp_loss 100-249 (mistake tier)
- No tactical detector (mate / piece_capture / clearance / king_pawn / hanging / capture / check)
- No positional detector (curriculum_deviation / blocked_pawn / board_state)
- User is neither decisively winning nor losing

Most-likely paths to address (in order of effort):

1. **Accept as floor.** 79 LOW captions / 11,441 user moves = 0.7%.
   That's the noise floor with the current detector set.
2. **Delete the engine-speak variants.** Replaces them with bare
   `X is a mistake. Y was better.` (MID tier). Less informative but no
   engine-speak.
3. **Build a new detector** that catches positional / move-quality
   reasons in balanced positions where current detectors miss. Hard.

## Pattern bucket

For grouping in your review: `engine_speak_balanced_position`
(this caption is correctly LOW per the pipeline; the question is
whether to leave it or eliminate the variants entirely).
"""


async def main_async(out_dir: str, max_per_variant: int):
    mongo_url = os.environ.get(
        "MONGO_URL",
        "mongodb://admin_user_mii_s_c:Mii123$44$@host.docker.internal:27018/?authSource=admin",
    )
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    os.makedirs(out_dir, exist_ok=True)

    n_reply = 0
    n_material = 0
    idx = 0
    index_lines = ["# Residual LOW captions — engine-speak floor\n"]
    index_lines.append("These captions are not bugs. They fire when:")
    index_lines.append("- cp_loss 100-249 (mistake tier)")
    index_lines.append("- No tactical / positional detector matches")
    index_lines.append("- User is in a balanced position\n")
    index_lines.append("Two variants make up the entire 79-caption set:\n")

    samples_reply = []
    samples_material = []
    async for ga in db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True}, "decryption_v5_version": {"$gte": 53}}
    ).sort("created_at", -1).limit(500):
        gid = ga.get("game_id", "")
        gd = await db.games.find_one({"game_id": gid}, {"_id": 0, "user_color": 1})
        user_color = (gd or {}).get("user_color", "white")
        ga_meta = {"game_id": gid, "user_color": user_color}
        for m in (ga.get("decryption_v5_data") or []):
            if not m.get("is_user_move"):
                continue
            cap = m.get("caption") or ""
            if "Opponent's strongest reply:" in cap:
                samples_reply.append((m, ga_meta))
            elif "wins material in the resulting line" in cap:
                samples_material.append((m, ga_meta))

    print(f"Found {len(samples_reply)} why_user_reply + {len(samples_material)} why_user_missed_material")

    index_lines.append(f"- **why_user_reply** — \"Opponent's strongest reply: X.\" — {len(samples_reply)} positions")
    index_lines.append(f"- **why_user_missed_material** — \"X wins material in the resulting line.\" — {len(samples_material)} positions\n")
    index_lines.append("## Per-position files (capped at {} per variant for review tractability)\n".format(max_per_variant))

    for m, ga_meta in samples_reply[:max_per_variant]:
        idx += 1
        eng = _engine_analysis(m.get("fen_before", ""))
        gid = ga_meta.get("game_id", "")[:8]
        msan = (m.get("move_san") or "").replace("+", "p").replace("#", "m")
        fname = f"{idx:03d}_reply_{gid}_m{m.get('move_number')}_{msan}.md"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(_md(idx, m, ga_meta, eng))
        index_lines.append(f"- [{fname}]({fname}) — `why_user_reply` `{gid} m{m.get('move_number')} {m.get('move_san')}` cp={m.get('cp_loss')}")
        n_reply += 1

    for m, ga_meta in samples_material[:max_per_variant]:
        idx += 1
        eng = _engine_analysis(m.get("fen_before", ""))
        gid = ga_meta.get("game_id", "")[:8]
        msan = (m.get("move_san") or "").replace("+", "p").replace("#", "m")
        fname = f"{idx:03d}_material_{gid}_m{m.get('move_number')}_{msan}.md"
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(_md(idx, m, ga_meta, eng))
        index_lines.append(f"- [{fname}]({fname}) — `why_user_missed_material` `{gid} m{m.get('move_number')} {m.get('move_san')}` cp={m.get('cp_loss')}")
        n_material += 1

    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines) + "\n")

    print(f"Wrote {n_reply} reply + {n_material} material MDs + README.md to {out_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-per-variant", type=int, default=20,
                        help="Cap per variant for review tractability (default 20)")
    args = parser.parse_args()
    asyncio.run(main_async(args.out_dir, args.max_per_variant))


if __name__ == "__main__":
    main()
