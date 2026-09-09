"""Audit the canonical trap library without changing it.

Examples:
    python scripts/audit_trap_library_truth.py
    python scripts/audit_trap_library_truth.py --json --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.trap_library_audit import audit_trap_library_file, has_gold_blockers


DEFAULT_TRAPS_PATH = BACKEND_DIR / "data" / "traps.json"


def _print_human(report: dict) -> None:
    summary = report["summary"]
    print("Canonical trap-library audit")
    print(f"  source sha256: {report['source']['sha256']}")
    print(f"  families: {summary['family_count']}")
    print(f"  traps: {summary['trap_count']}")
    print(f"  fully legal: {summary['fully_legal_count']}")
    print(f"  illegal: {summary['illegal_entry_count']}")
    print(f"  duplicate full-line groups: {summary['duplicate_full_line_group_count']}")
    print(f"  ambiguous exact-setup groups: {summary['ambiguous_setup_sequence_group_count']}")
    print(f"  setter/parity disagreements: {summary['role_parity_mismatch_count']}")
    print(f"  first trap-line mover roles: {summary['first_line_role_counts']}")
    print(f"  authored line steps: {summary['authored_line_step_count']}")
    print(f"  legally reached decision steps: {summary['legally_reached_decision_step_count']}")
    print(f"  unique decision positions: {summary['unique_decision_position_count']}")
    print(f"  gold-eligible before engine/human review: {summary['gold_eligible_entry_count']}")
    print(f"  canonical stable IDs present: {summary['has_canonical_stable_ids']}")
    print(f"  entries with missing step explanations: {summary['missing_explanation_entry_count']}")

    for key in report["illegal_entries"]:
        issue = report["entries"][key]["illegal"]
        print(
            f"ILLEGAL {key}: {issue['phase']} step={issue['line_step_index']} "
            f"move={issue['move']} fen={issue['fen_before']}"
        )
    for group in report["duplicate_full_lines"]:
        print(f"DUPLICATE_LINE {', '.join(group['entries'])}")
    for group in report["ambiguous_setup_sequences"]:
        print(f"AMBIGUOUS_SETUP {', '.join(group['entries'])}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traps", type=Path, default=DEFAULT_TRAPS_PATH)
    parser.add_argument("--json", action="store_true", help="Print the complete JSON report.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when canonical gold blockers are present.",
    )
    args = parser.parse_args()

    report = audit_trap_library_file(args.traps)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 1 if args.strict and has_gold_blockers(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
