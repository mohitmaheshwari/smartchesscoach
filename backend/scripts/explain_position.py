"""Offline deterministic explanation CLI. Never reads or writes MongoDB.

See docs/general_deterministic_reasoning_offline.md for the experimental config.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.reasoning import ReasoningConfig, explain_fen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fen")
    source.add_argument("--input", type=Path, help="JSON: fen, played_move?, player_level?, history?")
    parser.add_argument("--played")
    parser.add_argument("--engine", required=True, help="Explicit local Stockfish executable")
    parser.add_argument("--config", type=Path, required=True, help="Explicit experimental settings JSON")
    parser.add_argument("--output", type=Path, help="Write result here; otherwise stdout")
    args = parser.parse_args()
    try:
        request = json.loads(args.input.read_text(encoding="utf-8")) if args.input else {"fen": args.fen}
        if args.played is not None:
            request["played_move"] = args.played
        settings = json.loads(args.config.read_text(encoding="utf-8"))
        settings["engine_path"] = args.engine
        result = explain_fen(**request, config=ReasoningConfig(**settings))
        text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
            print(json.dumps({"output": str(args.output.resolve()), "status": result["status"],
                              "text": result["coaching"]["text"], "runtime": result["runtime"]}, ensure_ascii=False))
        else:
            print(text)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
