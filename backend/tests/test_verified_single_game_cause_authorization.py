"""Evidence gate for the exact single-game Caption authorization."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.detector_quality import (
    QualityGrade,
    QualitySurface,
    get_authorization,
    is_authorized,
)


ROOT = Path(__file__).resolve().parents[2]
QUALITY_ID = "review:verified_single_game_cause"
PACKET = (
    ROOT
    / "backend"
    / "data"
    / "detector_gold"
    / "verified_single_game_cause_promotion_v1.json"
)
EXPECTED_CANONICAL_SHA256 = (
    "ec8657bd04df24ed3ded49a981141c4c4d326889131eaa0f089cc51fdc2cba94"
)


def test_authority_is_caption_only_and_points_to_real_evidence():
    authorization = get_authorization(QUALITY_ID)
    assert authorization.grade == QualityGrade.CAPTION
    assert is_authorized(QUALITY_ID, QualitySurface.CAPTION) is True
    assert is_authorized(QUALITY_ID, QualitySurface.PLAN) is False
    assert is_authorized(QUALITY_ID, QualitySurface.MASTERY) is False
    assert (ROOT / authorization.evidence_ref).exists()


def test_versioned_promotion_packet_meets_the_locked_truth_bar():
    packet = json.loads(PACKET.read_text(encoding="utf-8-sig"))
    canonical = json.dumps(
        packet,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == EXPECTED_CANONICAL_SHA256
    assert packet["summary"] == {
        "players": 1,
        "games_processed": 44,
        "fires": 70,
        "negatives": 30,
        "fires_with_automated_quality_issues": 0,
        "fires_with_claim_violations": 0,
        "failures": 0,
    }
    assert packet["manual_review"]["true_positives"] == 70
    assert packet["manual_review"]["true_negatives"] == 30
    assert packet["manual_review"]["critical_false_claims"] == 0
    assert all(
        case["manual_review"]["verdict"] == "true_positive"
        and not case["claim_violations"]
        and not case["automated_quality_issues"]
        for case in packet["fires"]
    )
    assert all(
        case["manual_review"]["correct_abstention"] is True
        and case["cause"] is None
        for case in packet["negatives"]
    )


def test_packet_contains_no_account_identifier_or_credentials():
    text = PACKET.read_text(encoding="utf-8").lower()
    assert "@" not in text
    assert "bhutramohit" not in text
    assert "mongo_url" not in text
    assert "password" not in text
