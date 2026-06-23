"""check_caption_sources.py — the teachable-caption framework guard (Step 3).

Goal (docs/teachable_caption_framework_scope.md): every user-facing caption must
be produced through the ONE central layer (build_move_teaching_decision and the
caption_* modules it owns), so it is auto-verified and teachable. The recurring
disease is a new surface growing its OWN caption engine that bypasses the central
layer + verifier (PWC, then puzzle-miss, …).

This guard flags files OUTSIDE the central layer that hand-assemble chess-teaching
prose — the signal of a bespoke caption engine. It is **warn-only** during the
migration grace period (prints findings, exits 0). Flip DEFAULT_STRICT / pass
--strict to make it block once the surfaces are migrated.

Usage:
  python backend/scripts/check_caption_sources.py            # audit whole backend
  python backend/scripts/check_caption_sources.py f1.py f2.py  # only these (hook)
  python backend/scripts/check_caption_sources.py --strict   # exit 1 on findings

Opt-out: append `# allow-noncentral-caption` to a legitimately-exempt line.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# The central caption layer — the ONLY place caption prose is allowed to be built.
ALLOWLIST = {
    "backend/services/caption_pipeline.py",
    "backend/services/caption_renderer.py",
    "backend/services/caption_rules.py",
    "backend/services/caption_templates.py",
    "backend/services/caption_fallback_tiers.py",
    "backend/services/caption_facts.py",
    "backend/services/caption_principles.py",
    "backend/services/caption_classifier.py",
    "backend/services/caption_config.py",
    "backend/services/narrator_fallback.py",      # batch-time LLM enrichment, gated
    "backend/services/narrator_claim_verifier.py",  # the verifier itself
    "backend/services/shape_layer.py",             # shapes feed the central layer
    "backend/services/severity_mismatch_guard.py",
    # Migrated surface — now delegates its chess-prose to the central why
    # (_recommended_move_why); kept on the allowlist, monitor for new bespoke prose.
    "backend/services/puzzle_miss_coaching.py",
}

# Path fragments never scanned (tests/scripts/audits/the verifier-by-example).
SKIP_FRAGMENTS = ("backend/tests/", "backend/scripts/", "/__pycache__/", "memory/")

# Chess-teaching prose signals — UNAMBIGUOUS caption narration. Kept tight to limit
# false positives: a SAN/piece + teaching verb, or the mistake/better-move framing.
PROSE_PATTERNS = [
    re.compile(r"\bwas (?:the )?(?:better|stronger)\b"),
    re.compile(r"\bis an? (?:mistake|blunder|inaccuracy|serious mistake|major blunder)\b"),
    re.compile(r"(?:wins|forks|pins|skewers|hangs|drops|threatens|attacks|develops|"
               r"captures|takes) the (?:pawn|knight|bishop|rook|queen|king)\b"),
    re.compile(r"\b(?:you (?:missed|played)|the stronger move|the best move was)\b", re.I),
]

DEFAULT_STRICT = False


def _is_allowlisted(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    if rel in ALLOWLIST:
        return True
    return any(frag in rel for frag in SKIP_FRAGMENTS)


def scan_file(path: Path, repo_root: Path):
    rel = str(path.relative_to(repo_root)).replace("\\", "/")
    if _is_allowlisted(rel):
        return []
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    # Only files that reason about the board produce chess prose — gate on it
    # to cut noise (a route returning a stored string isn't building a caption).
    if "import chess" not in text:
        return []
    for i, line in enumerate(text.splitlines(), 1):
        if "allow-noncentral-caption" in line:
            continue
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        # Only user-facing PROSE counts — the phrase must live inside a string
        # literal. Skips docstrings, type annotations, comments, and var names
        # (e.g. `is_mistake:`, `# why best was better`) that aren't captions.
        if '"' not in line and "'" not in line:
            continue
        for pat in PROSE_PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            # require a quote BEFORE the match (match is inside a string, not a
            # trailing comment / annotation after the code).
            if '"' in line[:m.start()] or "'" in line[:m.start()]:
                findings.append((rel, i, s[:110]))
            break
    return findings


def main(argv):
    strict = DEFAULT_STRICT
    args = [a for a in argv if a != "--strict"]
    if "--strict" in argv:
        strict = True

    repo_root = Path(__file__).resolve().parents[2]  # .../smartchesscoach
    if args:
        targets = [Path(a) if Path(a).is_absolute() else repo_root / a for a in args]
        targets = [t for t in targets if t.suffix == ".py" and t.exists()]
    else:
        targets = sorted((repo_root / "backend").rglob("*.py"))

    all_findings = []
    for t in targets:
        all_findings.extend(scan_file(t, repo_root))

    if not all_findings:
        print("[caption-guard] OK — no bespoke caption prose outside the central layer.")
        return 0

    tag = "BLOCK" if strict else "WARN"
    print(f"\n[caption-guard] {tag}: chess-teaching prose found OUTSIDE the central "
          f"caption layer ({len(all_findings)} line(s)).")
    print("Captions must be produced via build_move_teaching_decision / the caption_* "
          "modules so they are auto-verified + teachable.")
    print("See docs/teachable_caption_framework_scope.md. Opt out a legit line with "
          "`# allow-noncentral-caption`.\n")
    by_file = {}
    for rel, ln, txt in all_findings:
        by_file.setdefault(rel, []).append((ln, txt))
    for rel in sorted(by_file):
        print(f"  {rel}")
        for ln, txt in by_file[rel][:8]:
            print(f"      {ln}: {txt}")
        if len(by_file[rel]) > 8:
            print(f"      … +{len(by_file[rel]) - 8} more")
    print()
    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
