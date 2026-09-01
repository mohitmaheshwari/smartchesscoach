#!/usr/bin/env python3
"""Read-only deployment verification for Fathom, Otter and Maia-2."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.exact_endgame_service import (  # noqa: E402
    compute_syzygy_manifest_sha256,
    probe_configured_fathom,
)
from services.human_behavior_engine import MoveContext  # noqa: E402
from services.human_policy_runtime import derive_human_policy_evidence  # noqa: E402


EXACT_FIXTURE = "8/8/8/8/8/8/2P5/K1k5 b - - 0 1"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4_E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"


def verify_exact() -> dict:
    evidence, reason = probe_configured_fathom(EXACT_FIXTURE)
    return {
        "ok": evidence is not None,
        "reason": reason,
        "complete_legal_partition": bool(
            evidence and evidence.contract_dict()["complete_legal_partition"]
        ),
        "provider": evidence.provider if evidence else None,
    }


def verify_human() -> dict:
    maia, maia_reason = derive_human_policy_evidence(
        MoveContext(
            fen=START_FEN,
            player_elo=1200,
            opponent_elo=1200,
            time_control="600+0",
            history_uci=(),
        )
    )
    otter, otter_reason = derive_human_policy_evidence(
        MoveContext(
            fen=AFTER_E4_E5,
            player_elo=1200,
            opponent_elo=1250,
            time_control="600+0",
            history_uci=("e2e4", "e7e5"),
        )
    )
    return {
        "ok": bool(
            maia and maia.provider == "maia2"
            and otter and otter.provider == "otter"
        ),
        "maia": {
            "reason": maia_reason,
            "provider": maia.provider if maia else None,
            "legal_moves": len(maia.probabilities) if maia else 0,
        },
        "otter": {
            "reason": otter_reason,
            "provider": otter.provider if otter else None,
            "legal_moves": len(otter.probabilities) if otter else 0,
            "history_mode": otter.history_mode if otter else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-exact", action="store_true")
    parser.add_argument("--require-human", action="store_true")
    parser.add_argument("--compute-syzygy-manifest")
    args = parser.parse_args()
    if args.compute_syzygy_manifest:
        print(json.dumps({
            "syzygy_tablebase_manifest_sha256": compute_syzygy_manifest_sha256(
                args.compute_syzygy_manifest
            )
        }, sort_keys=True))
        return 0
    result = {
        "exact": verify_exact() if args.require_exact else {"ok": None, "reason": "not_required"},
        "human": verify_human() if args.require_human else {"ok": None, "reason": "not_required"},
    }
    result["ok"] = all(
        section["ok"] is not False for section in (result["exact"], result["human"])
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
