"""Calibrate the Why queue checker on studies whose right answer is known.

    python backend/scripts/why_checker_calibrate.py CASES.json --engine PATH [--runs 1]

CASES.json is a list of positions, each with `studies`: [{label, expect, reason,
claims, mechanism_label}], where expect is "agree" or "disagree". The packet is
built once per position with the local engine, then the checker judges each study.
Nothing is written to prod. docs/why_queue_checker_scope.md: the publish flag stays
off unless every known-bad study is rejected.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import why_queue_worker as worker  # noqa: E402
from services import why_study      # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--depth", type=int, default=20)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    scratch = worker.LOG_DIR / "claude_cwd"
    scratch.mkdir(parents=True, exist_ok=True)
    results, total_cost = [], 0.0
    for case in cases:
        t0 = time.time()
        packet = why_study.build_packet(
            case["fen_before"], case["played_san"], better_san=case.get("better_san") or case.get("stored_best"),
            mover_is_user=case.get("side") != "opponent", depth=args.depth, engine_path=args.engine,
            stored_class=case.get("stored_class"), rating=case.get("rating"),
            live_engine_said=case.get("differential"))
        print(f"\n{case['played_san']} ({case.get('side')}) packet {time.time() - t0:.0f}s, better {packet['better_san']}",
              flush=True)
        for study in case["studies"]:
            for run in range(args.runs):
                check = worker.run_checker(packet, study, cwd=scratch)
                total_cost += float(check.get("cost_usd") or 0)
                ok = check["verdict"] == study["expect"]
                results.append({"position": case["played_san"], "label": study["label"], "expect": study["expect"],
                                "run": run + 1, **check, "correct": ok})
                print(f"  {'OK  ' if ok else 'MISS'} {study['label']}: expect {study['expect']}, "
                      f"got {check['verdict']} ({check.get('seconds')}s, ${check.get('cost_usd')})", flush=True)
                if check.get("problem"):
                    print(f"       problem: {check['problem']}")
                print(f"       own reading: {check.get('own_reading')}")
    good = [r for r in results if r["expect"] == "agree"]
    bad = [r for r in results if r["expect"] == "disagree"]
    print(f"\nagreed studies agreed: {sum(r['correct'] for r in good)}/{len(good)}")
    print(f"known-bad rejected:    {sum(r['correct'] for r in bad)}/{len(bad)}")
    print(f"checker model {worker.CHECKER_MODEL}, total ${total_cost:.2f}")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    return 0 if all(r["correct"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
