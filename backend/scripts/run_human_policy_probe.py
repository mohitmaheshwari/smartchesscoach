"""Run one pinned Maia-2 or Otter request through the research contract.

Use each provider's isolated Python environment.  Model weights must already
exist locally and match the required SHA-256; this command never downloads a
model and never touches MongoDB.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from research.human_chess_intelligence.policy_contract import HumanPolicyRequest  # noqa: E402
from research.human_chess_intelligence.providers import predict_maia2, predict_otter  # noqa: E402


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _request_from_path(path: Path) -> tuple[str, HumanPolicyRequest]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    request_payload = payload.get("request", payload)
    request = HumanPolicyRequest(
        fen=request_payload["fen"],
        player_elo=request_payload["player_elo"],
        opponent_elo=request_payload["opponent_elo"],
        history_moves=tuple(request_payload.get("history_moves") or ()),
        time_control=request_payload.get("time_control"),
        clock_fraction=request_payload.get("clock_fraction"),
    )
    return str(payload.get("fixture_id") or request.input_fingerprint[:16]), request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("maia2", "otter"))
    parser.add_argument("--request-json", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--expected-package-version", required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    parser.add_argument("--weight-family", choices=("rapid", "blitz"), default="rapid")
    parser.add_argument("--otter-mode", choices=("observed", "neutral_ablation"), default="observed")
    args = parser.parse_args()

    model_path = args.model_path.resolve(strict=True)
    actual_hash = _sha256_file(model_path)
    if actual_hash != args.expected_model_sha256.lower():
        raise SystemExit(f"model SHA-256 mismatch: {actual_hash}")
    distribution = "maia2" if args.provider == "maia2" else "otter-chess"
    actual_version = importlib.metadata.version(distribution)
    if actual_version != args.expected_package_version:
        raise SystemExit(
            f"package version mismatch: expected {args.expected_package_version}, got {actual_version}"
        )

    fixture_id, request = _request_from_path(args.request_json)
    with contextlib.redirect_stdout(sys.stderr):
        if args.provider == "maia2":
            from maia2.inference import prepare
            from maia2.model import from_pretrained

            model = from_pretrained(
                args.weight_family,
                device="cpu",
                save_root=str(model_path.parent),
            )
            evidence = predict_maia2(
                request,
                model=model,
                prepared=prepare(),
                model_version=actual_version,
                model_sha256=actual_hash,
                weight_family=args.weight_family,
            )
        else:
            from otter_chess import OtterModel

            model = OtterModel(checkpoint_path=str(model_path), device="cpu")
            evidence = predict_otter(
                request,
                model=model,
                model_version=actual_version,
                model_sha256=actual_hash,
                mode=args.otter_mode,
            )

    print(json.dumps({
        "fixture_id": fixture_id,
        "request_input_fingerprint": request.input_fingerprint,
        "evidence": evidence.to_dict(),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
