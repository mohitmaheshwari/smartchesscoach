#!/usr/bin/env python3
"""
Step 1: Extract top 5 CLASS_B patterns and design detectors
Step 2: Build a batch workflow for detector testing + shipping
Step 3: Apply to CLASS_A_SILENT assessment conflicts

This is the DETECTOR IMPROVEMENT LOOP:
  feedback → pattern extraction → detector design → test on position → verify caption → ship
"""

import os
import json
import asyncio
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

# From batch 3 triage, these are the top patterns we identified
TOP_5_CLASSB_PATTERNS = [
    {
        "pattern_name": "WANTS_WHY_EXPLANATION",
        "count": 8,
        "description": "User asks 'why?' for move assessment — wants tactical/strategic explanation of WHY it's bad",
        "detector_type": "failure_mode_predicate",
        "example_feedback": "User: 'a3 is a mistake. Check for any threats. Black may play Ne5.'",
        "action": "Add concrete failure-mode clause (what went wrong, what opponent threatens)"
    },
    {
        "pattern_name": "ASSESSMENT_CONFLICTS",
        "count": 6,
        "description": "Caption severity mismatches severity flag (says 'inaccuracy' but move is 'good', or vice versa)",
        "detector_type": "gate_predicate",
        "example_feedback": "User: 'UI shows Good but coaching says mistake'",
        "action": "Add cp_loss gate: only caption if cp_loss exceeds rating-band threshold"
    },
    {
        "pattern_name": "NARRATIVE_WRONG",
        "count": 5,
        "description": "Coaching explanation is factually wrong or irrelevant to position",
        "detector_type": "narrative_rewrite",
        "example_feedback": "User: 'narrative is factually wrong for this position'",
        "action": "Rewrite narrative to match actual board state (not generic principle)"
    },
    {
        "pattern_name": "WANTS_OPENING_THEORY",
        "count": 4,
        "description": "User provides opening context/variation that caption missed",
        "detector_type": "opening_enrichment",
        "example_feedback": "User: 'This is Giucco Piano, Black develops bishop before king knight'",
        "action": "Add opening_curriculum detection to provide theory context"
    },
    {
        "pattern_name": "WANTS_ALTERNATIVE_SUGGESTION",
        "count": 4,
        "description": "User says 'better move is X' — wants coaching to acknowledge the alternative",
        "detector_type": "move_comparison",
        "example_feedback": "User: 'Qd8 is playable but Qc7 is even better because...'",
        "action": "Add 'compare_to_best' clause (not just 'X is bad', but 'X is okay but Y is better')"
    }
]

CLASS_A_SILENT_PATTERNS = [
    {
        "pattern_name": "SILENT_WHEN_SHOULD_SPEAK",
        "count": 19,
        "description": "Coach is silent on a move when it should provide feedback (too conservative gates)",
        "detector_type": "gate_lowering",
        "action": "Lower confidence thresholds or remove overly restrictive gates"
    }
]

async def step1_extract_patterns():
    """Step 1: Identify top 5 CLASS_B patterns + design detectors"""

    print("\n" + "="*120)
    print("STEP 1: EXTRACT TOP 5 CLASS_B PATTERNS & DESIGN DETECTORS")
    print("="*120 + "\n")

    for i, pattern in enumerate(TOP_5_CLASSB_PATTERNS, 1):
        print(f"{i}. {pattern['pattern_name']}")
        print(f"   Count: {pattern['count']} items")
        print(f"   Description: {pattern['description']}")
        print(f"   Detector type: {pattern['detector_type']}")
        print(f"   Example: {pattern['example_feedback']}")
        print(f"   Action: {pattern['action']}\n")

    print("="*120)
    print("DETECTOR DESIGN SUMMARY")
    print("="*120 + "\n")

    designs = [
        {
            "pattern": "WANTS_WHY_EXPLANATION",
            "detector_code": "Add failure_mode predicates with concrete WHY clauses",
            "example": """
# Current (bad):
  "Does the move lose material?" → "Nf4 is a mistake"

# New (good):
  "Does the move lose material?" → "Nf4 is a mistake because your knight is undefended and will be captured"
            """,
            "file_to_change": "services/caption_pipeline.py → build_move_teaching_decision()",
            "effort": "MEDIUM (add 2-3 failure-mode templates per pattern)"
        },
        {
            "pattern": "ASSESSMENT_CONFLICTS",
            "detector_code": "Gate all captions on cp_loss vs rating-band threshold",
            "example": """
# Current (bad):
  if evaluated_as_mistake: show_caption()

# New (good):
  user_rating_band = get_user_rating_band(user_id)
  min_cp_for_this_band = RATING_BANDS[band]['mistake_cp']
  if cp_loss >= min_cp_for_this_band: show_caption()
            """,
            "file_to_change": "services/realtime_coaching_feedback.py → _classify_move_quality()",
            "effort": "LOW (already have RATING_BANDS; add one gate)"
        },
        {
            "pattern": "NARRATIVE_WRONG",
            "detector_code": "Engine-verify narrative before serving (check FEN for mentioned pieces/squares)",
            "example": """
# Current (bad):
  narrative = "Your dark-squared bishop stays blocked"  # ← assumes it's YOUR bishop

# New (good):
  board_state = parse_fen(fen)
  color = get_user_color(game_id)
  dark_bishops = find_pieces(board_state, color, piece_type='B', on_dark_squares=True)
  if dark_bishops: narrative = "...your dark-squared bishop..."
  else: suppress_narrative()  # ← don't mention it if not on board
            """,
            "file_to_change": "services/caption_pipeline.py → build_move_teaching_decision()",
            "effort": "MEDIUM (add board verification gates)"
        },
        {
            "pattern": "WANTS_OPENING_THEORY",
            "detector_code": "Detect opening positions and inject curriculum context",
            "example": """
# Current (bad):
  narrative = "Bc5 develops the bishop"

# New (good):
  if in_opening_phase():
      theory = opening_curriculum.lookup(opening_key, move_number)
      if theory: narrative = f"Bc5 develops the bishop. {theory['context']}"
            """,
            "file_to_change": "services/opening_curriculum_engine.py → enrich_opening_narrative()",
            "effort": "LOW (already have curriculum; just wire it in)"
        },
        {
            "pattern": "WANTS_ALTERNATIVE_SUGGESTION",
            "detector_code": "Compare played move to best move with reason for preference",
            "example": """
# Current (bad):
  narrative = "Qd8 is an inaccuracy. Qc7 was better."

# New (good):
  best_move = engine.best_move
  reason_why_better = evaluate_move_comparison(played, best_move)
  narrative = f"Qd8 is okay, but Qc7 was better because {reason_why_better}"
            """,
            "file_to_change": "services/caption_pipeline.py → compare_alternatives()",
            "effort": "MEDIUM (need comparison logic)"
        }
    ]

    for design in designs:
        print(f"\n[{design['pattern']}]")
        print(f"   Code change: {design['detector_code']}")
        print(f"   File: {design['file_to_change']}")
        print(f"   Effort: {design['effort']}")
        print(f"   Example:\n{design['example']}")

    return TOP_5_CLASSB_PATTERNS

async def step2_build_workflow():
    """Step 2: Build batch workflow for detector design + test + ship"""

    print("\n\n" + "="*120)
    print("STEP 2: BATCH WORKFLOW FOR DETECTOR IMPROVEMENT")
    print("="*120 + "\n")

    workflow = """
FOR EACH CLASS_B PATTERN (top 5):
  [Design Phase]
    - Identify root cause (WHY caption fails)
    - Design detector predicate (what check catches it?)
    - Write test fixture (sample positions where it should fire)
    - Code it

  [Test Phase]
    - Run detector against feedback positions
    - Verify it catches the problem (TP rate)
    - Verify it doesn't over-fire (FP rate)
    - Check generated captions are good

  [Ship Phase]
    - Deploy to PWC (Play with Coach)
    - Run against 10 games from feedback batch
    - Verify captions improve (vs before)
    - Mark feedback items as RESOLVED

Automation:
  - Extract CLASS_B item + reason
  - Find game_id + move_number
  - Get FEN, coaching_text, user_note
  - Run detector on FEN
  - Compare old caption vs new caption
  - Save result to detector_improvements collection
  - Report improvement rate (e.g., "9/10 captions better")
    """

    print(workflow)

    return True

async def step3_class_a_silent():
    """Step 3: Apply same loop to CLASS_A_SILENT (assessment conflicts)"""

    print("\n\n" + "="*120)
    print("STEP 3: CLASS_A_SILENT — ASSESSMENT CONFLICTS")
    print("="*120 + "\n")

    print("Problem: Coach is SILENT when it should speak, OR over-speaking when it shouldn't")
    print("Root cause: Gates are either TOO HIGH (miss real mistakes) or TOO LOW (over-classify)\n")

    print("Examples from batch 3:\n")
    print("  fb_c7b7be53b387: Move marked 'inaccuracy' but severity='good' → gate conflict")
    print("  fb_1305644d72e9: Coach says 'lost the game' but user disputes it → severity mismatch")
    print("  fb_05710bfc7125: UI shows 'Good' but coach says 'mistake' → classification conflict\n")

    print("Solution:")
    print("  For each CLASS_A_SILENT item:")
    print("    - Get the FEN + move")
    print("    - Get cp_loss from engine")
    print("    - Get user rating + rating band")
    print("    - Check: is cp_loss >= band threshold?")
    print("      - YES: caption should fire -> FIX: lower gates or enable caption")
    print("      - NO: user right, move is okay for band -> FIX: add gate to silence")
    print("    - Implement the gate change")
    print("  Batch test: run all 19 CLASS_A_SILENT through new gates")
    print("    - Measure: % that now agree with severity flags\n")

    print("Expected result: 19 gates refined → fewer assessment conflicts → better coaching\n")

    return True

async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Step 1
    patterns = await step1_extract_patterns()

    # Step 2
    await step2_build_workflow()

    # Step 3
    await step3_class_a_silent()

    print("\n" + "="*120)
    print("NEXT: START WITH PATTERN #1 (WANTS_WHY_EXPLANATION)")
    print("="*120 + "\n")
    print("Action: Design 2-3 new failure-mode predicates in caption_pipeline.py")
    print("Then test against the 8 feedback items that want explanations")
    print("Then measure: did captions improve? (run /probe-game on each)\n")

    client.close()

if __name__ == "__main__":
    asyncio.run(main())
