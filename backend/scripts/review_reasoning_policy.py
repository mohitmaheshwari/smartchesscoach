"""Freeze and rerun a disclosed review set, with a separate depth-20 audit.

This is an offline review tool. Gold labels are retained in the original file
but never passed to the reasoning engine. A reviewed set is not a new holdout.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

import chess
import chess.engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.benchmark_reasoning import run
from services.reasoning import ReasoningConfig
from services.reasoning.contracts import fingerprint
from services.reasoning.objectives import common_prefix
from services.reasoning.search import fingerprint_bytes


def requests_from_review(raw):
    cases = raw if isinstance(raw, list) else raw["cases"]
    return {"split": "development", "exposure": "disclosed review set; frozen rerun, not untouched evaluation",
            "cases": [{"id": row["id"], **{k: row[k] for k in ("fen", "played_move", "player_level", "history") if k in row}}
                      for row in cases]}


def source_hashes():
    backend = Path(__file__).resolve().parents[1]
    files = [*sorted((backend / "services" / "reasoning").glob("*.py")), backend / "services" / "stored_line_verifier.py",
             Path(__file__), backend / "scripts" / "benchmark_reasoning.py"]
    return {str(p.relative_to(backend)): fingerprint_bytes(p) for p in files}


def freeze_record(source, settings):
    return {"source_manifest_sha256": fingerprint_bytes(source), "config": asdict(settings),
            "config_digest": fingerprint(asdict(settings)), "source_hashes": source_hashes(),
            "engine_sha256": fingerprint_bytes(Path(settings.engine_path)),
            "policy": "root gap before conditional witnesses; unrestricted depth20 agreement for later events",
            "exposure": "The 12-case failures and ho05 have been disclosed; no untouched-set claim."}


def depth20_audit(cases, report, destination, settings):
    """Independent unrestricted root checks; audit time is outside pipeline cost."""
    rows = []
    for case, row in zip(cases, report["cases"]):
        if "result_file" not in row:
            rows.append({"id": case["id"], "status": "no_pipeline_result"})
            continue
        result = json.loads((destination / row["result_file"]).read_text(encoding="utf-8"))
        board = chess.Board(case["fen"])
        started = time.perf_counter()
        with chess.engine.SimpleEngine.popen_uci(settings.engine_path) as engine:
            engine.configure({"Threads": 1, "Hash": settings.hash_mb})
            info = engine.analyse(board, chess.engine.Limit(depth=20))
        pv, walker, sans = info["pv"], board.copy(), []
        for move in pv:
            sans.append(walker.san(move))
            walker.push(move)
        typed = info["score"].pov(board.turn)
        score = {"kind": "mate" if typed.is_mate() else "cp", "value": typed.mate() if typed.is_mate() else typed.score(),
                 "pov": "white" if board.turn else "black"}
        selected = result["selected_teaching_point"]
        best = pv[0].uci()
        reference = next((s for s in result["searches"] if s["purpose"] == "coaching_best_reply_depth20"), None)
        item = {"id": case["id"], "pipeline_status": result["status"],
                "depth20_root_best_uci": best, "depth20_root_pv": sans, "depth20_root_score": score,
                "depth20_root_depth": info["depth"], "depth20_root_nodes": info.get("nodes"),
                "selected_root_uci": selected["root_uci"] if selected else None,
                "selected_root_matches_depth20_best": selected["root_uci"] == best if selected else None,
                "pipeline_best_root_matches_depth20_best": result["context"]["best_searched_uci"] == best,
                "later_sentence_reference_depth": reference["lines"][0]["depth"] if reference and reference["lines"] else None,
                "text": result["coaching"]["text"], "sentence_checks": [],
                "pipeline_wall_ms": result["runtime"]["wall_ms"],
                "independent_audit_wall_ms": round(1000 * (time.perf_counter() - started), 3)}
        if selected:
            facts = {p["id"]: p for p in result["propositions"]}
            timelines = {t["id"]: t for t in result["timelines"]}
            for sentence in result["coaching"].get("sentences", []):
                if selected["objective"]["kind"] in ("comparative_sequence", "comparative_threat"):
                    verdict = "explicit_conditional_certificate; not_a_best_reply_line_claim"
                else:
                    decisive = [facts[key] for key in sentence["proposition_ids"] if facts[key]["ply"] > 1]
                    if not decisive:
                        verdict = "exact_root_action"
                    elif selected["root_uci"] != best:
                        verdict = "different_root_from_depth20_best; no_best_move_quality_claim"
                    else:
                        verdict = "retained_in_depth20_root_pv" if all(p["ply"] <= common_prefix(timelines[p["timeline_id"]]["moves_uci"], [m.uci() for m in pv]) for p in decisive) else "absent_from_depth20_root_pv"
                item["sentence_checks"].append({"text": sentence["text"], "verdict": verdict})
        rows.append(item)
        (destination / "depth20_progress.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps({"audit": case["id"], "root_agrees": item["pipeline_best_root_matches_depth20_best"]}), flush=True)
    return {"reference_depth": 20, "threads": 1, "hash_mb": settings.hash_mb,
            "audit_is_separate_from_pipeline_budget_and_latency": True, "cases": rows,
            "root_disagreements": sum(not r.get("pipeline_best_root_matches_depth20_best", True) for r in rows),
            "sentence_verdicts": dict(Counter(s["verdict"] for r in rows for s in r.get("sentence_checks", []))),
            "human_coaching_usefulness": "not_independently_graded"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    settings = json.loads(args.config.read_text(encoding="utf-8"))
    settings["engine_path"] = args.engine
    settings = ReasoningConfig(**settings)
    current = freeze_record(args.manifest, settings)
    freeze = args.output_dir / "freeze.json"
    manifest = requests_from_review(json.loads(args.manifest.read_text(encoding="utf-8")))
    if args.freeze:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if freeze.exists():
            raise ValueError("refusing to replace an existing freeze")
        freeze.write_text(json.dumps(current, indent=2), encoding="utf-8")
        (args.output_dir / "heldout_manifest.original.json").write_bytes(args.manifest.read_bytes())
        (args.output_dir / "requests.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"freeze": str(freeze), "code_digest": fingerprint(current["source_hashes"]), "cases": len(manifest["cases"])}))
        return
    if current != json.loads(freeze.read_text(encoding="utf-8")):
        raise ValueError("code, config, engine or source inputs changed after freezing")
    destination = args.output_dir / "pipeline"
    if (destination / "report.json").exists():
        raise ValueError("refusing to overwrite a completed frozen run")
    report = run(manifest, settings, destination)
    audit = depth20_audit(manifest["cases"], report, destination, settings)
    unchanged = freeze_record(args.manifest, settings) == current
    final = {"freeze_unchanged": unchanged, "pipeline_report": "pipeline/report.json", "audit": audit,
             "exposure": current["exposure"], "pipeline_code_digest": fingerprint(current["source_hashes"])}
    (args.output_dir / "review_report.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    if not unchanged:
        raise ValueError("code changed during evaluation; this run is invalid")


if __name__ == "__main__":
    main()
