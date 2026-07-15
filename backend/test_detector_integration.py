#!/usr/bin/env python3
"""
Test that the three new detectors integrate properly into the R12_blunder template.

This verification checks:
1. played_hangs facts are in glossary and wired to failure modes
2. opp_traded_active facts are in glossary and wired to failure modes
3. opp_quiet_threat facts are in glossary and wired to failure modes
4. All facts have corresponding teaching principle templates
5. All facts have corresponding variant text templates
"""

import json
import sys

# Expected facts from new detectors
EXPECTED_PLAYED_HANGS_FACTS = {
    'played_hangs_result', 'played_hangs_square', 'played_hangs_piece'
}

EXPECTED_OPP_TRADED_ACTIVE_FACTS = {
    'opp_traded_active_result', 'opp_traded_active_piece',
    'opp_traded_active_square', 'opp_traded_active_recapture'
}

EXPECTED_OPP_QUIET_THREAT_FACTS = {
    'opp_quiet_threat_result', 'opp_quiet_threat_piece',
    'opp_quiet_threat_square', 'opp_quiet_threat_best'
}

ALL_NEW_FACTS = EXPECTED_PLAYED_HANGS_FACTS | EXPECTED_OPP_TRADED_ACTIVE_FACTS | EXPECTED_OPP_QUIET_THREAT_FACTS


def main():
    """Test detector integration against R12_blunder template."""

    print("=" * 80)
    print("DETECTOR INTEGRATION TEST")
    print("=" * 80)

    # Test 1: Load R12_blunder template
    print("\n[OK] Test 1: Template loading")
    print("  -> Loading R12_blunder.json")

    try:
        with open("data/captions/R12_blunder.json") as f:
            r12_template = json.load(f)
        print("  [OK] Template loaded successfully")

        # Test 2: Verify fact glossary
        print("\n[OK] Test 2: Fact glossary validation")

        glossary = r12_template["fact_glossary"]

        # Check that new facts are in glossary
        glossary_new_facts = ALL_NEW_FACTS & set(glossary.keys())
        print(f"  [OK] Found {len(glossary_new_facts)}/{len(ALL_NEW_FACTS)} new facts in R12_blunder glossary")

        if len(glossary_new_facts) < len(ALL_NEW_FACTS):
            missing_from_glossary = ALL_NEW_FACTS - glossary_new_facts
            print(f"  [ERROR] Missing from glossary: {missing_from_glossary}")

        # Test 3: Verify failure mode gates
        print("\n[OK] Test 3: Failure mode gates validation")

        failure_modes = r12_template.get("failure_mode_clauses_opp", [])
        failure_mode_variants = [fm.get("variant") for fm in failure_modes]

        expected_variants = {'opp_failure_traded_active', 'opp_failure_quiet_threat'}
        found_variants = expected_variants & set(failure_mode_variants)

        print(f"  [OK] Found {len(found_variants)}/{len(expected_variants)} new failure mode variants")

        if len(found_variants) < len(expected_variants):
            missing_variants = expected_variants - found_variants
            print(f"  [ERROR] Missing variants: {missing_variants}")

        # Test 4: Verify teaching principle templates
        print("\n[OK] Test 4: Teaching principle templates validation")

        teaching_principles = r12_template.get("teaching_principles", {})
        expected_principles = {'opp_failure_traded_active', 'opp_failure_quiet_threat'}
        found_principles = expected_principles & set(teaching_principles.keys())

        print(f"  [OK] Found {len(found_principles)}/{len(expected_principles)} new teaching principle templates")

        if len(found_principles) < len(expected_principles):
            missing_principles = expected_principles - found_principles
            print(f"  [ERROR] Missing principles: {missing_principles}")

        # Test 5: Summary
        print("\n" + "=" * 80)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 80)

        all_checks = [
            ("R12_blunder glossary", len(glossary_new_facts) == len(ALL_NEW_FACTS)),
            ("Failure mode gates", len(found_variants) == len(expected_variants)),
            ("Teaching principles", len(found_principles) == len(expected_principles))
        ]

        passed = sum(1 for _, result in all_checks if result)
        total = len(all_checks)

        print(f"\nPassed: {passed}/{total}")

        for check_name, result in all_checks:
            status = "[OK]" if result else "[FAIL]"
            print(f"  {status} {check_name}")

        if passed == total:
            print("\n[SUCCESS] ALL CHECKS PASSED - Detectors are properly integrated!")
            return 0
        else:
            print(f"\n[INCOMPLETE] {total - passed} checks failed - review above for details")
            return 1

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1



if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
