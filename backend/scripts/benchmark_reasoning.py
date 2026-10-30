"""Offline experiment runner. A manifest is explicit development or sealed evaluation data.

Reports mechanical validation and outcome coverage; never calls them human
correctness, explanatory quality, coaching usefulness, or generalisation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.reasoning import ReasoningConfig, explain_fen
from services.reasoning.contracts import fingerprint
from services.reasoning.search import fingerprint_bytes


def run(manifest: dict, config: ReasoningConfig, destination: Path, development_manifest=None, *, combined=None) -> dict:
    if manifest.get("split") not in ("development", "sealed_evaluation") or not isinstance(manifest.get("cases"), list):
        raise ValueError("manifest requires split=development|sealed_evaluation and cases")
    configuration = {'reasoning': asdict(config), 'combined': combined} if combined else asdict(config)
    if manifest["split"] == "sealed_evaluation" and not manifest.get("frozen_config_digest") == fingerprint(configuration):
        raise ValueError("sealed evaluation requires a matching frozen_config_digest")
    if manifest["split"] == "sealed_evaluation":
        package = Path(__file__).resolve().parents[1] / "services" / "reasoning"
        sources = [*sorted(package.glob("*.py")), package.parent / "stored_line_verifier.py"]
        if combined:
            vendor = package.parents[1] / 'vendor' / 'chessgpt'
            sources.extend([vendor / 'features.py', vendor / 'PROVENANCE.json'])
        code_digest = fingerprint({p.name: fingerprint_bytes(p) for p in sources})
        if manifest.get("frozen_code_digest") != code_digest or manifest.get("frozen_engine_sha256") != fingerprint_bytes(Path(config.engine_path)):
            raise ValueError("sealed evaluation requires matching frozen code and engine hashes")
        if not development_manifest or fingerprint(development_manifest) != manifest.get("development_manifest_digest"):
            raise ValueError("sealed evaluation requires its frozen development manifest")
        def games(data):
            if any(not c.get("source_game_id") for c in data["cases"]):
                raise ValueError("game provenance is required to check evaluation separation")
            return {c["source_game_id"] for c in data["cases"]}
        if games(manifest) & games(development_manifest):
            raise ValueError("evaluation and development games overlap")
        def positions(data):
            return {" ".join(c["fen"].split()[:4]) for c in data["cases"]}
        if positions(manifest) & positions(development_manifest):
            raise ValueError("evaluation and development positions overlap")
    ids = [str(c["id"]) for c in manifest["cases"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("manifest needs unique nonempty case IDs")
    # Never turn a case ID into a filesystem path.
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, case in enumerate(manifest["cases"]):
        try:
            request = {k: case[k] for k in ("fen", "played_move", "player_level", "history") if k in case}
            result = explain_fen(**request, config=config, **(combined or {}))
            path = destination / f"case_{index:04d}.json"
            path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            row = {"id": ids[index], "stratum": case.get("stratum", "unlabelled"), "status": result["status"],
                   "result_file": path.name, "verified_propositions": len(result["propositions"]),
                   "rejected_propositions": len(result["invalid_propositions"]),
                   "accepted_hypotheses": len(result["hypotheses"]["accepted"]),
                   "rejected_hypotheses": len(result["hypotheses"]["rejected"]),
                   "incomplete_hypotheses": len(result["hypotheses"]["incomplete"]),
                   "comparison": result["context"].get("comparison"), "text": result["coaching"]["text"],
                   "runtime": result["runtime"]}
        except (ValueError, OSError, TypeError, KeyError) as exc:
            row = {"id": ids[index], "stratum": case.get("stratum", "unlabelled"), "status": "input_or_runtime_error",
                   "error": f"{type(exc).__name__}:{exc}"}
        rows.append(row)
        print(json.dumps({"case": row["id"], "status": row["status"]}), flush=True)
        # Save progress so interruption cannot masquerade as a completed run.
        (destination / "progress.json").write_text(json.dumps({"completed": len(rows), "total": len(ids), "cases": rows}, indent=2), encoding="utf-8")
    latencies = sorted(r["runtime"]["wall_ms"] for r in rows if "runtime" in r)
    report = {"schema_version": "reasoning.experiment.v1", "split": manifest["split"],
              "manifest_digest": fingerprint(manifest), "config_digest": fingerprint(configuration),
              "all_inputs": len(ids), "outcomes": dict(Counter(r["status"] for r in rows)),
              "by_stratum": {s: dict(Counter(r["status"] for r in rows if r["stratum"] == s)) for s in sorted({r["stratum"] for r in rows})},
              "mechanical_validation": {"accepted_propositions": sum(r.get("verified_propositions", 0) for r in rows),
                                        "rejected_propositions": sum(r.get("rejected_propositions", 0) for r in rows)},
              "human_factual_correctness": "not_reviewed", "explanatory_support": "not_reviewed", "coaching_usefulness": "not_reviewed",
              "latency_ms": {"p50": statistics.median(latencies) if latencies else None,
                             "p95_nearest_rank": latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)] if latencies else None,
                             "max": max(latencies, default=None)},
              "sampled_peak_child_rss_bytes": max((r.get("runtime", {}).get("sampled_peak_engine_rss_bytes", 0) for r in rows), default=0),
              "sampled_peak_parent_rss_bytes": max((r.get("runtime", {}).get("sampled_peak_parent_rss_bytes", 0) for r in rows), default=0),
              "sampled_peak_combined_rss_bytes": max((r.get("runtime", {}).get("sampled_peak_combined_rss_bytes", 0) for r in rows), default=0),
              "cases": rows, "evaluation_claim": "No quality or generalisation claim follows from mechanical validation alone."}
    if combined:
        report['combined_settings'] = combined
    (destination / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--development-manifest", type=Path, help="Required provenance/split check for sealed evaluation")
    parser.add_argument('--positional-features', action='store_true', help='Opt into the combined offline engine')
    parser.add_argument('--feature-plies', type=int, help='Explicit positional proposal horizon')
    parser.add_argument('--verification-nodes', type=int, help='Explicit per-reference allocation; the overall config cap still applies')
    args = parser.parse_args()
    settings = json.loads(args.config.read_text(encoding="utf-8"))
    settings["engine_path"] = args.engine
    development = json.loads(args.development_manifest.read_text(encoding="utf-8")) if args.development_manifest else None
    combined = None
    if args.positional_features:
        if not args.feature_plies or not args.verification_nodes:
            parser.error('--positional-features requires --feature-plies and --verification-nodes')
        combined = {'positional_features': True, 'feature_plies': args.feature_plies,
                    'verification_nodes': args.verification_nodes}
    elif args.feature_plies is not None or args.verification_nodes is not None:
        parser.error('positional allocations require --positional-features')
    run(json.loads(args.manifest.read_text(encoding="utf-8")), ReasoningConfig(**settings), args.output_dir, development,
        combined=combined)


if __name__ == "__main__":
    main()
