from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.rating_resolver import get_current_rating, resolve_current_rating


def test_rating_provenance_prefers_profile():
    evidence = resolve_current_rating(
        {"detected_rating": 1100},
        {"current_rating": 1250},
    )
    assert evidence == {
        "rating": 1250,
        "source": "player_profiles.current_rating",
        "measured": True,
    }
    assert get_current_rating({"detected_rating": 1100}, {"current_rating": 1250}) == 1250


def test_default_rating_is_explicitly_not_measured():
    evidence = resolve_current_rating({}, {})
    assert evidence["rating"] == 1200
    assert evidence["source"] == "config.DEFAULT_RATING"
    assert evidence["measured"] is False
