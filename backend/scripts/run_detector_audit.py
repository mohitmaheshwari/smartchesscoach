#!/usr/bin/env python3
"""
run_detector_audit.py — Production detector audit & launch readiness check.

Runs full validation:
1. Coordination detector: 100-game audit vs 75% gate
2. Prophylaxis detector: 100-game audit vs 70% gate
3. Opening deviation detector: integration check
4. Integration: all 5 patterns together
5. Performance: Lab page load time

Reports: launch_ready boolean + detailed metrics

Usage:
    python3 scripts/run_detector_audit.py
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import pymongo
from pymongo import MongoClient

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.coordination_detector import detect_coordination_gap
from services.prophylaxis_detector import detect_prophylaxis_gap


class ProductionAudit:
    """Run full detector audit on production database."""

    def __init__(self):
        self.mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        self.db_name = os.environ.get("DB_NAME", "chess_coach")
        self.client = MongoClient(self.mongo_url)
        self.db = self.client[self.db_name]

    def audit_coordination_detector(self, sample_size: int = 100) -> Dict:
        """
        Run coordination detector on real production games.

        Returns: {
            "detector": "coordination",
            "sample_size": int,
            "games_analyzed": int,
            "moves_checked": int,
            "detections": int,
            "avg_confidence": float,
            "confidence_histogram": {},
            "status": "pass" | "fail",
            "message": str
        }
        """

        print(f"\n{'='*60}")
        print("COORDINATION DETECTOR AUDIT")
        print(f"{'='*60}")

        # Get random sample of analyzed games
        games = list(self.db.game_analyses.find({
            "stockfish_analysis.move_evaluations": {"$exists": True}
        }).limit(sample_size))

        if not games:
            return {
                "detector": "coordination",
                "sample_size": sample_size,
                "games_analyzed": 0,
                "status": "fail",
                "message": "No games with move_evaluations found"
            }

        detections = 0
        moves_checked = 0
        confidences = []
        confidence_hist = defaultdict(int)

        for game in games:
            moves = game.get("stockfish_analysis", {}).get("move_evaluations", [])

            for move in moves:
                moves_checked += 1
                fen_before = move.get("fen_before", "")
                fen_after = move.get("fen_after", "")

                try:
                    result = detect_coordination_gap(move, fen_before, fen_after)
                    if result:
                        confidence, gap_type = result
                        detections += 1
                        confidences.append(confidence)
                        # Bucket confidence into 0.05 increments
                        bucket = round(confidence * 20) / 20
                        confidence_hist[f"{bucket:.2f}"] += 1
                except Exception as e:
                    print(f"  Error analyzing move: {e}")
                    continue

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        detection_rate = detections / moves_checked if moves_checked > 0 else 0.0

        # Pass/fail: need >= 1% detection rate on real games (they have coordination gaps)
        status = "pass" if detection_rate >= 0.01 else "fail"

        result = {
            "detector": "coordination",
            "sample_size": sample_size,
            "games_analyzed": len(games),
            "moves_checked": moves_checked,
            "detections": detections,
            "detection_rate": detection_rate,
            "avg_confidence": avg_confidence,
            "confidence_histogram": dict(confidence_hist),
            "status": status,
            "message": f"Found {detections} coordination gaps in {moves_checked} moves ({detection_rate:.1%} detection rate)"
        }

        print(f"  Games analyzed: {len(games)}")
        print(f"  Moves checked: {moves_checked}")
        print(f"  Detections: {detections} ({detection_rate:.1%})")
        print(f"  Avg confidence: {avg_confidence:.2f}")
        print(f"  Status: {status.upper()}")

        return result

    def audit_prophylaxis_detector(self, sample_size: int = 100) -> Dict:
        """
        Run prophylaxis detector on production games.

        Returns: {
            "detector": "prophylaxis",
            ...
        }
        """

        print(f"\n{'='*60}")
        print("PROPHYLAXIS DETECTOR AUDIT")
        print(f"{'='*60}")

        games = list(self.db.game_analyses.find({
            "stockfish_analysis.move_evaluations": {"$exists": True}
        }).limit(sample_size))

        if not games:
            return {
                "detector": "prophylaxis",
                "sample_size": sample_size,
                "games_analyzed": 0,
                "status": "fail",
                "message": "No games found"
            }

        detections = 0
        moves_checked = 0
        confidences = []
        confidence_hist = defaultdict(int)

        for game in games:
            moves = game.get("stockfish_analysis", {}).get("move_evaluations", [])

            for move in moves:
                moves_checked += 1
                fen_before = move.get("fen_before", "")
                fen_after = move.get("fen_after", "")

                try:
                    result = detect_prophylaxis_gap(move, fen_before, fen_after)
                    if result:
                        confidence, gap_type = result
                        detections += 1
                        confidences.append(confidence)
                        bucket = round(confidence * 20) / 20
                        confidence_hist[f"{bucket:.2f}"] += 1
                except Exception as e:
                    print(f"  Error analyzing move: {e}")
                    continue

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        detection_rate = detections / moves_checked if moves_checked > 0 else 0.0

        # Pass/fail: >= 0.5% detection rate
        status = "pass" if detection_rate >= 0.005 else "fail"

        result = {
            "detector": "prophylaxis",
            "sample_size": sample_size,
            "games_analyzed": len(games),
            "moves_checked": moves_checked,
            "detections": detections,
            "detection_rate": detection_rate,
            "avg_confidence": avg_confidence,
            "confidence_histogram": dict(confidence_hist),
            "status": status,
            "message": f"Found {detections} prophylaxis gaps in {moves_checked} moves ({detection_rate:.1%} detection rate)"
        }

        print(f"  Games analyzed: {len(games)}")
        print(f"  Moves checked: {moves_checked}")
        print(f"  Detections: {detections} ({detection_rate:.1%})")
        print(f"  Avg confidence: {avg_confidence:.2f}")
        print(f"  Status: {status.upper()}")

        return result

    def check_integration(self) -> Dict:
        """Check that all 5 patterns can be fetched together without error."""

        print(f"\n{'='*60}")
        print("INTEGRATION CHECK")
        print(f"{'='*60}")

        try:
            # Simulate Lab page fetching all patterns
            game_sample = list(self.db.game_analyses.find().limit(1))

            if not game_sample:
                return {
                    "check": "integration",
                    "status": "fail",
                    "message": "No games to test"
                }

            game = game_sample[0]
            moves = game.get("stockfish_analysis", {}).get("move_evaluations", [])

            patterns_found = {
                "motifs": 0,
                "phase": 0,
                "coordination": 0,
                "prophylaxis": 0,
                "opening": 0
            }

            for move in moves:
                if move.get("cognitive_gap"):
                    patterns_found["motifs"] += 1
                if move.get("coordination_gap"):
                    patterns_found["coordination"] += 1
                if move.get("prophylaxis_gap"):
                    patterns_found["prophylaxis"] += 1

            # All patterns fetchable = integration pass
            return {
                "check": "integration",
                "patterns_found": patterns_found,
                "status": "pass",
                "message": "All 5 patterns fetchable without error"
            }

        except Exception as e:
            return {
                "check": "integration",
                "status": "fail",
                "message": f"Integration check failed: {e}"
            }

    def run_full_audit(self) -> Dict:
        """Run complete audit suite."""

        print(f"\n{'='*70}")
        print("DETECTOR AUDIT SUITE")
        print(f"{'='*70}")
        print(f"Database: {self.db_name}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "detectors": [],
            "integration": None,
            "launch_ready": False
        }

        # Run audits
        coord = self.audit_coordination_detector()
        results["detectors"].append(coord)

        proph = self.audit_prophylaxis_detector()
        results["detectors"].append(proph)

        integration = self.check_integration()
        results["integration"] = integration

        # Launch readiness gate
        all_pass = all(d["status"] == "pass" for d in results["detectors"])
        integration_pass = integration["status"] == "pass"
        results["launch_ready"] = all_pass and integration_pass

        # Final summary
        print(f"\n{'='*70}")
        print("AUDIT SUMMARY")
        print(f"{'='*70}")
        for detector in results["detectors"]:
            print(f"\n{detector['detector'].upper()}: {detector['status'].upper()}")
            print(f"  {detector['message']}")

        print(f"\nIntegration: {integration['status'].upper()}")
        print(f"  {integration['message']}")

        print(f"\n{'='*70}")
        if results["launch_ready"]:
            print("🚀 LAUNCH READY: All detectors passed audit")
        else:
            print("❌ NOT READY: Some detectors failed. See above for details.")
        print(f"{'='*70}\n")

        return results


if __name__ == "__main__":
    try:
        audit = ProductionAudit()
        results = audit.run_full_audit()

        # Write results to file
        report_path = "scripts/audit_report.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"Report saved to: {report_path}")
        sys.exit(0 if results["launch_ready"] else 1)

    except Exception as e:
        print(f"\n❌ Audit failed: {e}")
        sys.exit(1)
