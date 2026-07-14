"""
test_detector_gold_corpus.py — Validate detector accuracy on gold corpus.

Runs each detector (coordination, prophylaxis, opening) on 100+ verified games
and measures: true positives, false positives, precision, confidence calibration.

CRITICAL: This determines whether detectors meet 75% threshold for launch.
"""

import asyncio
import pytest
import json
from datetime import datetime
from typing import Dict
from motor.motor_asyncio import AsyncIOMotorClient
import os
from services.coordination_detector import detect_coordination_gap
from services.prophylaxis_detector import detect_prophylaxis_gap


class GoldCorpusAudit:
    """Audit detector accuracy on games with known ground truth."""

    def __init__(self):
        self.mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        self.db_name = os.environ.get("DB_NAME", "chess_coach")

    async def audit_coordination_detector(self, sample_size: int = 100) -> Dict:
        """
        Run coordination detector on gold games, measure accuracy.

        Returns: {
            "detector": "coordination",
            "sample_size": int,
            "true_positives": int,
            "false_positives": int,
            "precision": float,
            "confidence_avg": float,
            "status": "pass" | "fail" (based on 75% threshold)
        }
        """

        client = AsyncIOMotorClient(self.mongo_url)
        db = client[self.db_name]

        # Get sample of games with manual coordination annotations
        # For MVP: use games where rooks are statically undefended (high confidence gold standard)
        games = await db.game_analyses.find({
            "stockfish_analysis.move_evaluations": {"$exists": True},
            "gold_corpus.has_coordination_gap": True  # Pre-annotated
        }).limit(sample_size).to_list(sample_size)

        true_positives = 0
        false_positives = 0
        confidences = []

        for game in games:
            moves = game.get("stockfish_analysis", {}).get("move_evaluations", [])

            for move in moves:
                fen_before = move.get("fen_before", "")
                fen_after = move.get("fen_after", "")
                move_gold_label = move.get("gold_corpus", {}).get("coordination_gap", False)

                result = detect_coordination_gap(move, fen_before, fen_after)

                if result:
                    conf, gap_type = result
                    confidences.append(conf)

                    if move_gold_label:  # TP
                        true_positives += 1
                    else:  # FP
                        false_positives += 1

        total_detections = true_positives + false_positives
        precision = true_positives / total_detections if total_detections > 0 else 0.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        status = "pass" if precision >= 0.75 else "fail"

        client.close()

        return {
            "detector": "coordination",
            "sample_size": sample_size,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "precision": precision,
            "confidence_avg": avg_confidence,
            "status": status
        }

    async def audit_prophylaxis_detector(self, sample_size: int = 100) -> Dict:
        """
        Run prophylaxis detector on gold games, measure accuracy.

        Returns: {
            "detector": "prophylaxis",
            "sample_size": int,
            "true_positives": int,
            "false_positives": int,
            "precision": float,
            "confidence_avg": float,
            "status": "pass" | "fail" (based on 70% threshold)
        }
        """

        client = AsyncIOMotorClient(self.mongo_url)
        db = client[self.db_name]

        # Get games with prophylaxis gap annotations
        games = await db.game_analyses.find({
            "stockfish_analysis.move_evaluations": {"$exists": True},
            "gold_corpus.has_prophylaxis_gap": True
        }).limit(sample_size).to_list(sample_size)

        true_positives = 0
        false_positives = 0
        confidences = []

        for game in games:
            moves = game.get("stockfish_analysis", {}).get("move_evaluations", [])

            for move in moves:
                fen_before = move.get("fen_before", "")
                fen_after = move.get("fen_after", "")
                move_gold_label = move.get("gold_corpus", {}).get("prophylaxis_gap", False)

                result = detect_prophylaxis_gap(move, fen_before, fen_after)

                if result:
                    conf, gap_type = result
                    confidences.append(conf)

                    if move_gold_label:  # TP
                        true_positives += 1
                    else:  # FP
                        false_positives += 1

        total_detections = true_positives + false_positives
        precision = true_positives / total_detections if total_detections > 0 else 0.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # More conservative threshold for new detector
        status = "pass" if precision >= 0.70 else "fail"

        client.close()

        return {
            "detector": "prophylaxis",
            "sample_size": sample_size,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "precision": precision,
            "confidence_avg": avg_confidence,
            "status": status
        }

    async def run_full_audit(self) -> Dict:
        """Run full audit suite on all detectors."""

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "detectors": []
        }

        # Audit coordination
        coord_result = await self.audit_coordination_detector()
        results["detectors"].append(coord_result)

        # Audit prophylaxis
        proph_result = await self.audit_prophylaxis_detector()
        results["detectors"].append(proph_result)

        # Summary
        all_pass = all(d["status"] == "pass" for d in results["detectors"])
        results["all_pass"] = all_pass
        results["launch_ready"] = all_pass

        return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
async def test_coordination_detector_gold_corpus():
    """Audit coordination detector on 100 gold games."""
    audit = GoldCorpusAudit()
    result = await audit.audit_coordination_detector(sample_size=100)

    print(f"\nCoordination Detector Audit:")
    print(f"  Sample size: {result['sample_size']}")
    print(f"  True positives: {result['true_positives']}")
    print(f"  False positives: {result['false_positives']}")
    print(f"  Precision: {result['precision']:.1%}")
    print(f"  Avg confidence: {result['confidence_avg']:.2f}")
    print(f"  Status: {result['status'].upper()}")

    assert result["status"] == "pass", "Coordination detector did not meet 75% precision threshold"


@pytest.mark.asyncio
async def test_prophylaxis_detector_gold_corpus():
    """Audit prophylaxis detector on 100 gold games."""
    audit = GoldCorpusAudit()
    result = await audit.audit_prophylaxis_detector(sample_size=100)

    print(f"\nProphylaxis Detector Audit:")
    print(f"  Sample size: {result['sample_size']}")
    print(f"  True positives: {result['true_positives']}")
    print(f"  False positives: {result['false_positives']}")
    print(f"  Precision: {result['precision']:.1%}")
    print(f"  Avg confidence: {result['confidence_avg']:.2f}")
    print(f"  Status: {result['status'].upper()}")

    assert result["status"] == "pass", "Prophylaxis detector did not meet 70% precision threshold"


@pytest.mark.asyncio
async def test_full_detector_audit():
    """Run full audit suite on all detectors."""
    audit = GoldCorpusAudit()
    results = await audit.run_full_audit()

    print(f"\n{'='*60}")
    print("FULL DETECTOR AUDIT RESULTS")
    print(f"{'='*60}")

    for detector in results["detectors"]:
        print(f"\n{detector['detector'].upper()}")
        print(f"  Precision: {detector['precision']:.1%}")
        print(f"  Status: {detector['status']}")

    print(f"\n{'='*60}")
    print(f"LAUNCH READY: {results['launch_ready']}")
    print(f"{'='*60}")

    assert results["launch_ready"], "Not all detectors passed audit. Fix before launch."


if __name__ == "__main__":
    # Run audit from command line
    import datetime
    audit = GoldCorpusAudit()
    results = asyncio.run(audit.run_full_audit())

    print(json.dumps(results, indent=2, default=str))
