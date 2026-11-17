"""Calibrate the trap judge against the graders' labels before it decides anything live.

    python scripts/trap_judge_calibrate.py --engine <stockfish.exe> --out <results.jsonl>
           [--set docs/qa/trap_judge_calibration_2026_11_17.json] [--workers 3] [--limit N] [--model M]

Runs on Mohit's machine with Claude Code headless and the why queue's engine tools
(scripts/why_queue_worker.run_claude). Resumable: ids already in --out are skipped.
The bar (docs/trap_lesson_from_games_scope.md): of the judge's TRAP verdicts, at least
90% are TRAP in the labels.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import why_queue_worker as worker  # noqa: E402
from services import trap_judge  # noqa: E402


def judge(case, *, model, scratch):
    out = worker.run_claude(trap_judge.SYSTEM_PROMPT, trap_judge.packet(case), trap_judge.SCHEMA,
                            cwd=scratch, model=model, tools_note=trap_judge.TOOLS_NOTE)
    return {**trap_judge.parse(out["answer"]), "cost_usd": out.get("cost_usd"),
            "duration_ms": out.get("duration_ms"), "turns": out.get("turns"), "model": out.get("model")}


def report(path: Path) -> None:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [r for r in rows if "verdict" in r]
    said_trap = [r for r in ok if r["verdict"] == "TRAP"]
    true_trap = [r for r in ok if r["label"] == "TRAP"]
    hit = [r for r in said_trap if r["label"] == "TRAP"]
    print(f"judged {len(ok)} of {len(rows)}; judge TRAP {len(said_trap)}, of which label TRAP {len(hit)}"
          f" (precision {len(hit) / max(1, len(said_trap)):.0%}); label TRAP found {len(hit)} of {len(true_trap)}"
          f" (recall {len(hit) / max(1, len(true_trap)):.0%})")
    print("confusion (label -> judge):", dict(collections.Counter((r["label"], r["verdict"]) for r in ok)))
    cost = sum(r.get("cost_usd") or 0 for r in ok)
    print(f"cost ${cost:.2f}, ${cost / max(1, len(ok)):.2f} a case")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", default=str(HERE.parent.parent / "docs" / "qa" / "trap_judge_calibration_2026_11_17.json"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=worker.DEFAULT_MODEL)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if args.report_only:
        report(out)
        return 0
    worker.ENGINE_FOR_TOOLS = args.engine
    cases = json.loads(Path(args.set).read_text(encoding="utf-8"))["cases"]
    done = set()
    if out.exists():
        done = {json.loads(l)["id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [c for c in cases if c["id"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    lock = threading.Lock()
    scratch_root = Path(tempfile.mkdtemp(prefix="trap_judge_"))

    def one(case):
        scratch = scratch_root / case["id"]
        scratch.mkdir(parents=True, exist_ok=True)
        try:
            res = judge(case, model=args.model, scratch=scratch)
        except Exception as exc:                    # noqa: BLE001 - record and go on
            res = {"error": str(exc)[:500]}
        row = {"id": case["id"], "label": case["label"], **res}
        with lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(case["id"], case["label"], "->", res.get("verdict") or "ERROR", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(one, todo))
    report(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
