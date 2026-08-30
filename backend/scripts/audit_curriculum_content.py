"""Print the offline curriculum truth report; no DB or credentials required."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.curriculum_content_validator import (  # noqa: E402
    get_defense_ready_trap_ids,
    validate_all_content,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument(
        "--fail-on-quarantined",
        action="store_true",
        help="exit non-zero while any canonical record remains quarantined",
    )
    args = parser.parse_args()

    report = validate_all_content()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for subject, data in report["subjects"].items():
            print(
                f"{subject}: {data['publishable']}/{data['total']} "
                f"publishable; {data['quarantined']} quarantined"
            )
        print(
            "trap lessons: "
            f"{len(get_defense_ready_trap_ids())} defense-ready"
        )
        print(f"reported issues: {report['issue_count']}")

    quarantined = sum(
        data["quarantined"] for data in report["subjects"].values()
    )
    return 1 if args.fail_on_quarantined and quarantined else 0


if __name__ == "__main__":
    raise SystemExit(main())
