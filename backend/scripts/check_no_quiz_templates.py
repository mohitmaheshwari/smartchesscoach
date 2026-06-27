"""check_no_quiz_templates.py — STRUCTURAL guard for Coach Conductor LAW 1
(the coach STATES, never ASKS). Sweeps every caption template for a '?' in any
user-facing field. Exits non-zero if a question slipped in.

Run in CI / pre-commit. This exists because the 2026-06-26 purge missed
R17 coach_threat_general ("what changed on the board for you?") — a lowercase
question the strip-regex didn't catch and the rendered-sample harness never hit.
A standing sweep catches what vigilance misses. docs/pwc_coach_conductor_scope.md
"""
import json, glob, sys, os

SKIP_PATH_PARTS = ("description", "fact_glossary", ".when", ".requires", ".select_variant")
CAPTIONS = os.path.join(os.path.dirname(__file__), "..", "data", "captions", "*.json")


def main():
    bad = []
    for p in sorted(glob.glob(CAPTIONS)):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue

        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{path}[{i}]")
            elif isinstance(o, str) and "?" in o:
                if not any(s in path for s in SKIP_PATH_PARTS):
                    bad.append((os.path.basename(p), path, o))

        walk(d)

    if bad:
        print("LAW 1 VIOLATION — coach asks instead of states (question in a caption template):")
        for f, path, v in bad:
            print(f"  {f}{path}: {v!r}")
        print(f"\n{len(bad)} question(s) found. Reframe to a STATEMENT.")
        return 1
    print("OK — no questions in any caption template (the coach states, never asks).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
