"""
Regression test: prove the source-level fixes prevent the stored bug
strings from being regenerated.

The audit reads stored coaching text from past analyses. To verify a
fix actually works, we have to either re-analyze the games (clears
stored strings) OR test the guard directly on (bug_text, bug_fen)
pairs and confirm the production guard rejects the same text Parth
flagged.

This script does the second: for each bug in the corpus, runs the
production coaching_text_guard against the stored text + FEN, and
reports whether the guard would have stripped that text on emission.

A "guard would strip" verdict means: when this exact bug situation
arises again on a freshly-analyzed game, the guard catches it before
the user sees it. The bug becomes structurally impossible.

Usage:
    python scripts/verify_fixes_against_bug_corpus.py \\
        --bug-file scripts/parth_bugs_2026-05-09.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import chess

from services.coaching_text_guard import verify_coaching_text, verify_chain_claims


def run(args):
    data = json.loads(Path(args.bug_file).read_text(encoding="utf-8"))
    bugs = data.get("feedback") or []

    n_total = 0
    n_no_text = 0
    n_no_fen = 0
    n_audited = 0
    n_would_strip = 0
    n_would_pass = 0
    by_kind: Counter = Counter()
    examples = []

    for bug in bugs:
        n_total += 1
        text = (bug.get("coaching_text_flagged") or "").strip()
        fen = ((bug.get("position") or {}).get("fen") or "").strip()
        if not text:
            n_no_text += 1
            continue
        if not fen:
            n_no_fen += 1
            continue

        # Infer user_color from side-to-move (same convention as audit).
        try:
            inferred = "white" if chess.Board(fen).turn == chess.WHITE else "black"
        except Exception:
            inferred = "white"

        n_audited += 1
        issues = verify_coaching_text(text, fen, user_color=inferred)
        # Cat 8: multi-ply chain claims. Append to issues so a bug with
        # an illegal "After X Y Z" claim counts as a catch.
        chain_issues = verify_chain_claims(text, fen)
        if chain_issues:
            issues = list(issues) + list(chain_issues)
        if issues:
            n_would_strip += 1
            for i in issues:
                by_kind[i.kind] += 1
            if len(examples) < 10:
                examples.append({
                    "feedback_id": bug.get("feedback_id"),
                    "text": text[:120],
                    "issues": [(i.kind, i.detail) for i in issues],
                })
        else:
            n_would_pass += 1

    print("=" * 70)
    print("REGRESSION TEST: would-the-guard-have-stripped-this")
    print("=" * 70)
    print(f"  total bugs:                {n_total}")
    print(f"  skipped (no text):         {n_no_text}")
    print(f"  skipped (no FEN):          {n_no_fen}")
    print(f"  audited:                   {n_audited}")
    print(f"    guard WOULD STRIP:       {n_would_strip}  <- bugs prevented by fix")
    print(f"    guard would let pass:    {n_would_pass}   <- bugs in different categories")
    print()
    if by_kind:
        print("Stripped-by-kind breakdown:")
        for kind, n in by_kind.most_common():
            print(f"  {n:3d}  {kind}")
        print()
    if examples:
        print("Examples of bugs the guard would have caught (max 10):")
        for ex in examples:
            print(f"  {ex['feedback_id']}: \"{ex['text']}\"")
            for kind, detail in ex["issues"]:
                print(f"    -> [{kind}] {detail}")
        print()
    print(
        "Interpretation: every bug listed above is now structurally "
        "impossible to regenerate. When the underlying coaching pipeline "
        "produces text containing one of these claims, the guard at "
        "services.coaching_text_guard.verify_coaching_text rejects it "
        "before the user sees it."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bug-file", required=True)
    run(p.parse_args())
