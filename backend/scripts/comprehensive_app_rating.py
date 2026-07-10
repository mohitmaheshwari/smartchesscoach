#!/usr/bin/env python3
"""
Comprehensive app rating for bhutramohit's games.

Analyze verified captions by phase (opening/middlegame/endgame).
Rate app quality 0-10 for each phase.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from services.caption_facts_verified import extract_facts_verified
from collections import defaultdict


def main():
    client = MongoClient("mongodb://admin_user_mii_s_c:Mii123$44$@localhost:27018")
    db = client["chess_coach"]

    print("=" * 100)
    print("COMPREHENSIVE APP RATING - BHUTRAMOHIT'S GAMES")
    print("=" * 100)
    print()

    # Get all analyzed games
    analyzed_games = list(db.game_analyses.find({}).limit(100))
    print(f"Analyzing {len(analyzed_games)} games")
    print()

    # Collect stats by phase
    phase_stats = defaultdict(lambda: {
        "total_moves": 0,
        "verified": 0,
        "unverified_gate1": 0,
        "unverified_no_fact": 0,
        "fact_types": defaultdict(int),
        "cp_loss_distribution": [],
        "coverage": 0,
    })

    for analysis in analyzed_games:
        moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])

        for move_data in moves:
            move_san = move_data.get("move")
            fen_before = move_data.get("fen_before")
            eval_before = move_data.get("eval_before", 0)
            eval_after = move_data.get("eval_after", 0)
            cp_loss = move_data.get("cp_loss", 0)
            move_num = move_data.get("move_number")

            if not fen_before or cp_loss < 50:
                continue

            # Determine phase
            if move_num <= 12:
                phase = "opening"
            elif move_num <= 40:
                phase = "middlegame"
            else:
                phase = "endgame"

            try:
                facts = extract_facts_verified(
                    fen_before=fen_before,
                    played_san=move_san,
                    best_move_san=None,
                    eval_before_cp=eval_before,
                    eval_after_cp=eval_after,
                )

                phase_stats[phase]["total_moves"] += 1
                phase_stats[phase]["cp_loss_distribution"].append(cp_loss)

                verified = facts.get("verified", False)
                reason = facts.get("verification_reason", "")
                details = facts.get("verification_details", {})

                if verified:
                    phase_stats[phase]["verified"] += 1
                    for fact_type, exists in details.items():
                        if exists:
                            phase_stats[phase]["fact_types"][fact_type] += 1
                elif reason == "cp_loss < 100 (not a real mistake)":
                    phase_stats[phase]["unverified_gate1"] += 1
                else:
                    phase_stats[phase]["unverified_no_fact"] += 1

            except Exception:
                pass

    # Calculate metrics and ratings
    print("PHASE-BY-PHASE ANALYSIS")
    print("=" * 100)
    print()

    ratings = {}

    for phase in ["opening", "middlegame", "endgame"]:
        stats = phase_stats[phase]
        total = stats["total_moves"]

        if total == 0:
            continue

        verified = stats["verified"]
        gate1 = stats["unverified_gate1"]
        no_fact = stats["unverified_no_fact"]
        cp_losses = stats["cp_loss_distribution"]

        coverage = 100 * verified // total if total > 0 else 0
        avg_cp_loss = sum(cp_losses) // len(cp_losses) if cp_losses else 0

        print(f"PHASE: {phase.upper()}")
        print("-" * 100)
        print(f"  Total moves analyzed: {total}")
        print(f"  Verified captions: {verified} ({coverage}%)")
        print(f"  Blocked Gate 1 (<100cp): {gate1} ({100*gate1//total}%)")
        print(f"  No facts detected: {no_fact} ({100*no_fact//total}%)")
        print(f"  Average cp_loss: {avg_cp_loss}cp")
        print()

        if stats["fact_types"]:
            print(f"  Detected facts in verified captions:")
            for fact_type, count in sorted(
                stats["fact_types"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"    - {fact_type}: {count}")
            print()

        # Calculate rating 0-10
        # Factors:
        # - Coverage (0-4 points): higher coverage = better
        # - Quality (0-3 points): verified captions are high quality
        # - Gap filling (0-3 points): fact diversity shows coaching depth

        coverage_score = min(4, coverage // 10)  # 0-4 based on coverage
        quality_score = min(3, verified // (total // 30)) if total > 0 else 0  # 0-3
        fact_diversity = min(3, len(stats["fact_types"]) // 2)  # 0-3 based on fact types

        rating = coverage_score + quality_score + fact_diversity

        ratings[phase] = {
            "rating": rating,
            "coverage": coverage,
            "verified": verified,
            "total": total,
            "fact_types": len(stats["fact_types"]),
        }

        print(f"RATING BREAKDOWN:")
        print(f"  Coverage score (0-4): {coverage_score} ({coverage}% of moves)")
        print(f"  Quality score (0-3): {quality_score} ({verified} verified captions)")
        print(f"  Fact diversity (0-3): {fact_diversity} ({len(stats['fact_types'])} fact types)")
        print(f"  TOTAL RATING: {rating}/10")
        print()

    # Overall rating
    print("=" * 100)
    print("OVERALL ASSESSMENT")
    print("=" * 100)
    print()

    overall_verified = sum(phase_stats[p]["verified"] for p in ["opening", "middlegame", "endgame"])
    overall_total = sum(phase_stats[p]["total_moves"] for p in ["opening", "middlegame", "endgame"])
    overall_coverage = 100 * overall_verified // overall_total if overall_total > 0 else 0

    for phase in ["opening", "middlegame", "endgame"]:
        if phase in ratings:
            r = ratings[phase]
            print(f"{phase.upper():15s} : {r['rating']}/10 (Coverage: {r['coverage']}%, "
                  f"Verified: {r['verified']}/{r['total']}, Facts: {r['fact_types']})")

    print()
    print(f"OVERALL        : {sum(r['rating'] for r in ratings.values())//len(ratings)}/10 "
          f"(Average coverage: {overall_coverage}%)")
    print()

    print("=" * 100)
    print("HONEST ASSESSMENT")
    print("=" * 100)
    print()

    for phase in ["opening", "middlegame", "endgame"]:
        if phase not in ratings:
            continue

        r = ratings[phase]
        rating = r["rating"]

        if rating >= 8:
            assessment = "EXCELLENT - App provides solid coaching for this phase"
        elif rating >= 6:
            assessment = "GOOD - App covers most important moments, some gaps"
        elif rating >= 4:
            assessment = "FAIR - App catches major mistakes, inconsistent coverage"
        else:
            assessment = "POOR - Limited coaching, mostly silent"

        print(f"{phase.upper()}: {rating}/10 - {assessment}")
        print()


if __name__ == "__main__":
    main()
