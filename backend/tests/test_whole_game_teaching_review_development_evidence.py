import hashlib
import json
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
PACKET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_development_packet_v1.json"
)
WORKSHEET = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_codex_worksheet_v1.json"
)
MANIFEST = (
    BACKEND
    / "data/detector_gold/whole_game_teaching_review_development_adjudication_v1.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_development_review_accounts_for_every_game_and_binds_sources():
    packet = json.loads(PACKET.read_text(encoding="utf-8-sig"))
    worksheet = json.loads(WORKSHEET.read_text(encoding="utf-8-sig"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert packet["membership_sha256"] == manifest["source"]["membership_sha256"]
    assert _sha(PACKET) == manifest["source"]["packet_sha256"]
    assert _sha(WORKSHEET) == manifest["source"]["worksheet_sha256"]
    assert len(packet["games"]) == len(worksheet["games"]) == 100
    assert {
        game["anonymous_game_key"] for game in packet["games"]
    } == {
        game["anonymous_game_key"] for game in worksheet["games"]
    }
    assert manifest["review_contract"]["omitted_games"] == 0
    assert manifest["review_contract"]["duplicate_games"] == 0


def test_frozen_gold_contains_no_critical_claim_and_holdout_stays_closed():
    worksheet = json.loads(WORKSHEET.read_text(encoding="utf-8-sig"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    moments = [
        moment
        for game in worksheet["games"]
        for moment in game["moments"]
    ]

    assert len(moments) == manifest["accepted_gold"]["proved_moments"] == 219
    assert all(
        moment["evidence_verdict"] == "proved"
        and moment["critical_false_claim"] is False
        for moment in moments
    )
    assert manifest["accepted_gold"]["critical_false_claims"] == 0
    assert manifest["review_disposition"]["holdout_opened"] is False
