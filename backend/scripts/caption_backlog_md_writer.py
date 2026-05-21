"""Per-position MD writer for caption backlog.

Reads the caption_verifier.py JSON report and emits per-position MD
files in docs/caption_backlog_500/ following the format Mohit asked
for. Each file documents: FEN, played move, current caption, engine
analysis, why the caption is suspect, suggested fix, confidence tier.

Mohit overnight task (2026-05-21).

Usage:
    docker exec chess-coach-backend python /app/backend/scripts/caption_backlog_md_writer.py \
        --report /tmp/caption_verifier_report.json \
        --out-dir /app/docs/caption_backlog_500
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chess
import chess.engine


_STOCKFISH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")


def _engine_analysis(fen: str, depth: int = 16) -> dict:
    """Quick depth-16 multipv=3 analysis to enrich MD files."""
    try:
        board = chess.Board(fen)
    except Exception:
        return {}
    try:
        with chess.engine.SimpleEngine.popen_uci(_STOCKFISH) as e:
            info = e.analyse(board, chess.engine.Limit(depth=depth), multipv=3)
    except Exception as exc:
        return {"error": str(exc)}
    out = {"multipv": []}
    for line in info:
        score = line.get("score")
        if score is None:
            continue
        cp = score.white().score(mate_score=10000)
        pv = line.get("pv") or []
        san_pv = []
        tmp = board.copy()
        for mv in pv[:6]:
            try:
                san_pv.append(tmp.san(mv))
                tmp.push(mv)
            except Exception:
                break
        out["multipv"].append({"eval_white_cp": cp, "pv_san": san_pv})
    return out


def _md_for_suspect(suspect: dict, idx: int) -> str:
    verifier = suspect.get("verifier", "unknown")
    gid = suspect.get("game_id", "")
    mn = suspect.get("move_number", "")
    msan = suspect.get("move_san", "")
    fen = suspect.get("fen_before", "")
    best = suspect.get("best_move_san", "")
    cap = suspect.get("caption", "")
    cpl = suspect.get("cp_loss", "")
    reason = suspect.get("reason", "")
    claim = suspect.get("claim") or {}
    user_color = suspect.get("user_color", "")

    analysis = _engine_analysis(fen) if fen else {}
    multipv_md = ""
    if analysis.get("multipv"):
        lines = []
        for j, line in enumerate(analysis["multipv"], 1):
            cp = line["eval_white_cp"]
            pv = " ".join(line["pv_san"])
            lines.append(f"  - #{j} eval(W) `{cp:+d}cp`  PV: `{pv}`")
        multipv_md = "\n".join(lines)
    elif analysis.get("error"):
        multipv_md = f"  (engine unavailable: {analysis['error']})"
    else:
        multipv_md = "  (no engine output)"

    return f"""# {gid} m{mn} {msan} — `{verifier}` suspect #{idx}

**Verifier:** `{verifier}`
**Reason flagged:** {reason}

**Position (FEN):** `{fen}`
**Move played:** `{msan}` (cp_loss `{cpl}`)
**Engine's best (stored):** `{best}`
**User color:** {user_color}

## Caption as shipped

> {cap}

## Specific claim

```
{json.dumps(claim, indent=2)}
```

## Live engine view (depth 16, multipv 3)

{multipv_md}

## Diagnosis

The caption made a claim the verifier could mechanically falsify.
See `reason` above. Confirm by reconstructing the position and
walking the line — does the claimed piece actually fall on the
claimed square, the named reply actually appear in the engine's
PV, etc.?

## Suggested action

- If the verifier reason is a stale-data issue (e.g., stored
  `best_move_san` differs from current engine's pick), regenerate
  the game and re-verify.
- If the claim is structurally wrong (detector logic bug),
  identify the responsible detector and tighten — same approach
  as v53's clearance-detector simulation drop.
- If it's a one-off / hard-to-reproduce noise, leave for human
  review.

## Confidence tag

`needs-human-review` — verifier flagged automatically; mark `fix`
after a code patch lands, `accept-noise` if false-positive.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max", type=int, default=50,
                        help="Cap MD output to N suspects (default 50).")
    args = parser.parse_args()

    with open(args.report, encoding="utf-8") as f:
        rep = json.load(f)
    suspects = rep.get("suspects", [])

    os.makedirs(args.out_dir, exist_ok=True)

    # Index file
    index_md = ["# Caption Backlog — 500-game audit suspects\n"]
    index_md.append(f"Generated from `{args.report}`.\n")
    index_md.append(f"- Sample size: **{rep.get('sample_size', '?')} games**")
    index_md.append(f"- Captioned moves checked: **{rep.get('total_captioned_moves', '?')}**")
    index_md.append(f"- Suspect captions: **{rep.get('suspect_count', '?')}**")
    index_md.append(f"- Breakdown by verifier: `{rep.get('counters', {})}`\n")
    index_md.append("## Suspects (per-position files)\n")

    count = min(len(suspects), args.max)
    for i, s in enumerate(suspects[:count], 1):
        verifier = s.get("verifier", "x")
        gid = s.get("game_id", "x")
        mn = s.get("move_number", "x")
        msan = s.get("move_san", "x").replace("+", "p").replace("#", "m")
        fname = f"{i:03d}_{verifier}_{gid[:8]}_m{mn}_{msan}.md"
        path = os.path.join(args.out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_md_for_suspect(s, i))
        reason_short = (s.get("reason") or "")[:80]
        index_md.append(f"- [{fname}]({fname}) — `{verifier}`: {reason_short}")
        print(f"Wrote {fname}")

    with open(os.path.join(args.out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index_md) + "\n")

    print(f"\nWrote {count} MD files + README.md to {args.out_dir}")


if __name__ == "__main__":
    main()
