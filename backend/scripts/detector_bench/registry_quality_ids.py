"""Read quality_id, not concept_id. My earlier probe read the wrong field.

Bundles carry BOTH: concept_id is dotted and semantic (tactic.clearance),
quality_id is colon and is what the registry is keyed on
(tactic:clearance_with_stored_payoff). I reported "17 of 17 provers cannot
caption" off concept_id, which the registry was never keyed on.

Positive control: gap:piece_safety:simple_hang must be caption.
"""
import os, sys, importlib
sys.path.insert(0, "/app/backend")
os.environ["DETECTOR_QUALITY_GATE_ENFORCED"] = "true"
from services.detector_quality import (
    grade_for, is_authorized, QualitySurface, explicit_authorizations)

MODS = ["fork", "trapped_piece", "discovered_attack", "back_rank_mate",
        "deflection", "attraction", "clearance", "interference", "xray_attack",
        "removal_defender", "advanced_pawn", "defensive_move", "forced_mate",
        "free_piece", "piece_safety", "destination_safety", "aligned_tactic"]

reg = explicit_authorizations()
print("control gap:piece_safety:simple_hang -> %s\n" % grade_for("gap:piece_safety:simple_hang"))
print("%-22s %-46s %-9s %s" % ("module", "QUALITY_ID constant", "grade", "captions?"))
print("-" * 96)
for m in MODS:
    try:
        mod = importlib.import_module("services.%s_puzzle_proof" % m)
    except Exception as e:
        print("%-22s import failed %s" % (m, str(e)[:40]))
        continue
    qids = [getattr(mod, n) for n in dir(mod)
            if n.endswith("QUALITY_ID") and isinstance(getattr(mod, n), str)]
    if not qids:
        print("%-22s %-46s %-9s %s" % (m, "(no *_QUALITY_ID constant)", "-", "-"))
        continue
    for q in sorted(set(qids)):
        g = grade_for(q)
        g = g.value if hasattr(g, "value") else str(g)
        print("%-22s %-46s %-9s %s%s"
              % (m, q, g, is_authorized(q, QualitySurface.CAPTION),
                 "" if q in reg else "   (no row)"))
