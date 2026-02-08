"""
Chess Journey Comprehensive Progress Dashboard Tests
Tests the GET /api/journey/comprehensive endpoint which returns:
1. Rating progression (started_at, current, change, peak, trend, history)
2. Phase mastery (opening/middlegame/endgame with mastery_pct and trend)
3. Improvement metrics (then vs now: accuracy, blunders, mistakes, best_moves)
4. Habit journey (conquered, in_progress, needs_attention categories)
5. Opening repertoire (win rates for openings as white and black)
"""

import pytest
import requests
import os

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "testuser@demo.com"


@pytest.fixture(scope="module")
def session_token():
    """Get a valid session token via demo login"""
    response = requests.post(
        f"{BASE_URL}/api/auth/demo-login",
        json={"email": TEST_EMAIL}
    )
    if response.status_code != 200:
        pytest.skip(f"Demo login failed: {response.status_code}")
    return response.json().get("session_token")


@pytest.fixture(scope="module")
def api_client(session_token):
    """Create authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {session_token}"
    })
    return session


@pytest.fixture(scope="module")
def journey_data(api_client):
    """Fetch journey data once for all tests"""
    response = api_client.get(f"{BASE_URL}/api/journey/comprehensive")
    assert response.status_code == 200, f"Failed to fetch journey: {response.status_code}"
    return response.json()


# ============ ENDPOINT AVAILABILITY ============

class TestJourneyEndpointAvailability:
    """Tests that the journey endpoint is accessible"""
    
    def test_journey_comprehensive_endpoint_exists(self, api_client):
        """Journey comprehensive endpoint should return 200"""
        response = api_client.get(f"{BASE_URL}/api/journey/comprehensive")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_journey_endpoint_requires_auth(self):
        """Journey endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/journey/comprehensive")
        assert response.status_code == 401, "Endpoint should require authentication"
    
    def test_journey_returns_json(self, api_client):
        """Journey endpoint should return valid JSON"""
        response = api_client.get(f"{BASE_URL}/api/journey/comprehensive")
        assert response.headers.get("content-type", "").startswith("application/json")
        # Should not raise
        data = response.json()
        assert isinstance(data, dict), "Response should be a dictionary"


# ============ TOP-LEVEL STRUCTURE ============

class TestJourneyStructure:
    """Tests the top-level structure of journey response"""
    
    def test_has_member_since(self, journey_data):
        """Response should have member_since field"""
        assert "member_since" in journey_data, "Missing member_since"
    
    def test_has_total_games_analyzed(self, journey_data):
        """Response should have total_games_analyzed"""
        assert "total_games_analyzed" in journey_data, "Missing total_games_analyzed"
        assert isinstance(journey_data["total_games_analyzed"], int)
    
    def test_has_rating_progression(self, journey_data):
        """Response should have rating_progression section"""
        assert "rating_progression" in journey_data, "Missing rating_progression"
        assert isinstance(journey_data["rating_progression"], dict)
    
    def test_has_phase_mastery(self, journey_data):
        """Response should have phase_mastery section"""
        assert "phase_mastery" in journey_data, "Missing phase_mastery"
        assert isinstance(journey_data["phase_mastery"], dict)
    
    def test_has_improvement_metrics(self, journey_data):
        """Response should have improvement_metrics section"""
        assert "improvement_metrics" in journey_data, "Missing improvement_metrics"
        assert isinstance(journey_data["improvement_metrics"], dict)
    
    def test_has_habit_journey(self, journey_data):
        """Response should have habit_journey section"""
        assert "habit_journey" in journey_data, "Missing habit_journey"
        assert isinstance(journey_data["habit_journey"], dict)
    
    def test_has_opening_repertoire(self, journey_data):
        """Response should have opening_repertoire section"""
        assert "opening_repertoire" in journey_data, "Missing opening_repertoire"
        assert isinstance(journey_data["opening_repertoire"], dict)


# ============ RATING PROGRESSION ============

class TestRatingProgression:
    """Tests rating_progression structure"""
    
    def test_rating_has_started_at(self, journey_data):
        """Rating progression should have started_at"""
        rating = journey_data.get("rating_progression", {})
        assert "started_at" in rating, "Missing started_at"
    
    def test_rating_has_current(self, journey_data):
        """Rating progression should have current rating"""
        rating = journey_data.get("rating_progression", {})
        assert "current" in rating, "Missing current"
    
    def test_rating_has_change(self, journey_data):
        """Rating progression should have change value"""
        rating = journey_data.get("rating_progression", {})
        assert "change" in rating, "Missing change"
    
    def test_rating_has_peak(self, journey_data):
        """Rating progression should have peak rating"""
        rating = journey_data.get("rating_progression", {})
        assert "peak" in rating, "Missing peak"
    
    def test_rating_has_trend(self, journey_data):
        """Rating progression should have trend indicator"""
        rating = journey_data.get("rating_progression", {})
        assert "trend" in rating, "Missing trend"
        valid_trends = ["improving", "declining", "stable"]
        assert rating["trend"] in valid_trends, f"Invalid trend: {rating['trend']}"
    
    def test_rating_has_history(self, journey_data):
        """Rating progression should have history array"""
        rating = journey_data.get("rating_progression", {})
        assert "history" in rating, "Missing history"
        assert isinstance(rating["history"], list), "history should be a list"
    
    def test_rating_values_are_consistent(self, journey_data):
        """Rating change should equal current - started_at"""
        rating = journey_data.get("rating_progression", {})
        started = rating.get("started_at")
        current = rating.get("current")
        change = rating.get("change")
        
        if started is not None and current is not None and change is not None:
            expected_change = current - started
            assert change == expected_change, f"Change {change} != current({current}) - started({started})"


# ============ PHASE MASTERY ============

class TestPhaseMastery:
    """Tests phase_mastery structure (opening, middlegame, endgame)"""
    
    def test_phase_mastery_has_opening(self, journey_data):
        """Phase mastery should have opening phase"""
        phase = journey_data.get("phase_mastery", {})
        assert "opening" in phase, "Missing opening phase"
    
    def test_phase_mastery_has_middlegame(self, journey_data):
        """Phase mastery should have middlegame phase"""
        phase = journey_data.get("phase_mastery", {})
        assert "middlegame" in phase, "Missing middlegame phase"
    
    def test_phase_mastery_has_endgame(self, journey_data):
        """Phase mastery should have endgame phase"""
        phase = journey_data.get("phase_mastery", {})
        assert "endgame" in phase, "Missing endgame phase"
    
    def test_opening_has_mastery_pct(self, journey_data):
        """Opening phase should have mastery_pct"""
        opening = journey_data.get("phase_mastery", {}).get("opening", {})
        assert "mastery_pct" in opening, "Opening missing mastery_pct"
        assert isinstance(opening["mastery_pct"], (int, float))
    
    def test_opening_has_trend(self, journey_data):
        """Opening phase should have trend"""
        opening = journey_data.get("phase_mastery", {}).get("opening", {})
        assert "trend" in opening, "Opening missing trend"
        valid_trends = ["improving", "declining", "stable"]
        assert opening["trend"] in valid_trends
    
    def test_middlegame_has_mastery_pct(self, journey_data):
        """Middlegame phase should have mastery_pct"""
        middlegame = journey_data.get("phase_mastery", {}).get("middlegame", {})
        assert "mastery_pct" in middlegame, "Middlegame missing mastery_pct"
    
    def test_endgame_has_mastery_pct(self, journey_data):
        """Endgame phase should have mastery_pct"""
        endgame = journey_data.get("phase_mastery", {}).get("endgame", {})
        assert "mastery_pct" in endgame, "Endgame missing mastery_pct"
    
    def test_phase_mastery_pct_in_valid_range(self, journey_data):
        """All mastery percentages should be 0-100"""
        phase = journey_data.get("phase_mastery", {})
        for phase_name in ["opening", "middlegame", "endgame"]:
            pct = phase.get(phase_name, {}).get("mastery_pct", 0)
            assert 0 <= pct <= 100, f"{phase_name} mastery_pct {pct} out of range"


# ============ IMPROVEMENT METRICS (THEN VS NOW) ============

class TestImprovementMetrics:
    """Tests improvement_metrics comparing early vs recent games"""
    
    def test_has_data_indicator(self, journey_data):
        """Improvement metrics should have has_data field"""
        metrics = journey_data.get("improvement_metrics", {})
        assert "has_data" in metrics, "Missing has_data field"
    
    def test_has_accuracy_comparison(self, journey_data):
        """Should compare accuracy: then vs now"""
        metrics = journey_data.get("improvement_metrics", {})
        if metrics.get("has_data"):
            assert "accuracy" in metrics, "Missing accuracy comparison"
            acc = metrics["accuracy"]
            assert "then" in acc, "Missing accuracy.then"
            assert "now" in acc, "Missing accuracy.now"
    
    def test_has_blunders_comparison(self, journey_data):
        """Should compare blunders_per_game: then vs now"""
        metrics = journey_data.get("improvement_metrics", {})
        if metrics.get("has_data"):
            assert "blunders_per_game" in metrics, "Missing blunders_per_game"
            blunders = metrics["blunders_per_game"]
            assert "then" in blunders, "Missing blunders.then"
            assert "now" in blunders, "Missing blunders.now"
    
    def test_has_mistakes_comparison(self, journey_data):
        """Should compare mistakes_per_game: then vs now"""
        metrics = journey_data.get("improvement_metrics", {})
        if metrics.get("has_data"):
            assert "mistakes_per_game" in metrics, "Missing mistakes_per_game"
            mistakes = metrics["mistakes_per_game"]
            assert "then" in mistakes, "Missing mistakes.then"
            assert "now" in mistakes, "Missing mistakes.now"
    
    def test_has_best_moves_comparison(self, journey_data):
        """Should compare best_moves_per_game: then vs now"""
        metrics = journey_data.get("improvement_metrics", {})
        if metrics.get("has_data"):
            assert "best_moves_per_game" in metrics, "Missing best_moves_per_game"
            best = metrics["best_moves_per_game"]
            assert "then" in best, "Missing best_moves.then"
            assert "now" in best, "Missing best_moves.now"
    
    def test_metrics_have_improved_indicator(self, journey_data):
        """Each metric should have improved boolean"""
        metrics = journey_data.get("improvement_metrics", {})
        if metrics.get("has_data"):
            for key in ["accuracy", "blunders_per_game", "mistakes_per_game", "best_moves_per_game"]:
                if key in metrics:
                    assert "improved" in metrics[key], f"Missing improved flag in {key}"
                    assert isinstance(metrics[key]["improved"], bool)


# ============ HABIT JOURNEY ============

class TestHabitJourney:
    """Tests habit_journey with conquered/in_progress/needs_attention"""
    
    def test_has_conquered_list(self, journey_data):
        """Habit journey should have conquered array"""
        habits = journey_data.get("habit_journey", {})
        assert "conquered" in habits, "Missing conquered"
        assert isinstance(habits["conquered"], list)
    
    def test_has_in_progress_list(self, journey_data):
        """Habit journey should have in_progress array"""
        habits = journey_data.get("habit_journey", {})
        assert "in_progress" in habits, "Missing in_progress"
        assert isinstance(habits["in_progress"], list)
    
    def test_has_needs_attention_list(self, journey_data):
        """Habit journey should have needs_attention array"""
        habits = journey_data.get("habit_journey", {})
        assert "needs_attention" in habits, "Missing needs_attention"
        assert isinstance(habits["needs_attention"], list)
    
    def test_has_total_cards(self, journey_data):
        """Habit journey should have total_cards"""
        habits = journey_data.get("habit_journey", {})
        assert "total_cards" in habits, "Missing total_cards"
        assert isinstance(habits["total_cards"], int)
    
    def test_has_total_mastered(self, journey_data):
        """Habit journey should have total_mastered"""
        habits = journey_data.get("habit_journey", {})
        assert "total_mastered" in habits, "Missing total_mastered"
        assert isinstance(habits["total_mastered"], int)
    
    def test_habit_item_structure(self, journey_data):
        """Habit items should have required fields"""
        habits = journey_data.get("habit_journey", {})
        # Check any non-empty category
        for category in ["in_progress", "needs_attention", "conquered"]:
            items = habits.get(category, [])
            if items:
                item = items[0]
                assert "key" in item, f"{category} item missing key"
                assert "display_name" in item, f"{category} item missing display_name"
                break  # Found an item, structure verified


# ============ OPENING REPERTOIRE ============

class TestOpeningRepertoire:
    """Tests opening_repertoire with win rates"""
    
    def test_has_as_white(self, journey_data):
        """Opening repertoire should have as_white section"""
        repertoire = journey_data.get("opening_repertoire", {})
        assert "as_white" in repertoire, "Missing as_white"
        assert isinstance(repertoire["as_white"], dict)
    
    def test_has_as_black(self, journey_data):
        """Opening repertoire should have as_black section"""
        repertoire = journey_data.get("opening_repertoire", {})
        assert "as_black" in repertoire, "Missing as_black"
        assert isinstance(repertoire["as_black"], dict)
    
    def test_as_white_has_total_games(self, journey_data):
        """as_white should have total_games count"""
        white = journey_data.get("opening_repertoire", {}).get("as_white", {})
        assert "total_games" in white, "Missing total_games in as_white"
        assert isinstance(white["total_games"], int)
    
    def test_as_white_has_openings_list(self, journey_data):
        """as_white should have openings array"""
        white = journey_data.get("opening_repertoire", {}).get("as_white", {})
        assert "openings" in white, "Missing openings in as_white"
        assert isinstance(white["openings"], list)
    
    def test_as_black_has_total_games(self, journey_data):
        """as_black should have total_games count"""
        black = journey_data.get("opening_repertoire", {}).get("as_black", {})
        assert "total_games" in black, "Missing total_games in as_black"
        assert isinstance(black["total_games"], int)
    
    def test_as_black_has_openings_list(self, journey_data):
        """as_black should have openings array"""
        black = journey_data.get("opening_repertoire", {}).get("as_black", {})
        assert "openings" in black, "Missing openings in as_black"
        assert isinstance(black["openings"], list)
    
    def test_opening_has_win_rate(self, journey_data):
        """Each opening should have win_rate"""
        repertoire = journey_data.get("opening_repertoire", {})
        for color in ["as_white", "as_black"]:
            openings = repertoire.get(color, {}).get("openings", [])
            if openings:
                opening = openings[0]
                assert "win_rate" in opening, f"{color} opening missing win_rate"
                assert "name" in opening, f"{color} opening missing name"
                assert "games" in opening, f"{color} opening missing games"
                break
    
    def test_opening_win_rate_valid_range(self, journey_data):
        """Win rates should be 0-100"""
        repertoire = journey_data.get("opening_repertoire", {})
        for color in ["as_white", "as_black"]:
            for opening in repertoire.get(color, {}).get("openings", []):
                wr = opening.get("win_rate", 0)
                assert 0 <= wr <= 100, f"Win rate {wr} out of range"


# ============ WEEKLY SUMMARY ============

class TestWeeklySummary:
    """Tests weekly_summary section"""
    
    def test_has_weekly_summary(self, journey_data):
        """Response should have weekly_summary"""
        assert "weekly_summary" in journey_data, "Missing weekly_summary"
        assert isinstance(journey_data["weekly_summary"], dict)
    
    def test_weekly_summary_has_games_this_week(self, journey_data):
        """Weekly summary should have games_this_week"""
        summary = journey_data.get("weekly_summary", {})
        assert "games_this_week" in summary, "Missing games_this_week"


# ============ INSIGHTS ============

class TestInsights:
    """Tests insights array"""
    
    def test_has_insights(self, journey_data):
        """Response should have insights array"""
        assert "insights" in journey_data, "Missing insights"
        assert isinstance(journey_data["insights"], list)
    
    def test_insight_structure(self, journey_data):
        """Insights should have type, title, message"""
        insights = journey_data.get("insights", [])
        if insights:
            insight = insights[0]
            assert "type" in insight, "Insight missing type"
            assert "title" in insight, "Insight missing title"
            assert "message" in insight, "Insight missing message"


# ============ DATA INTEGRITY ============

class TestDataIntegrity:
    """Tests data consistency and integrity"""
    
    def test_mastered_not_exceeds_total(self, journey_data):
        """total_mastered should not exceed total_cards"""
        habits = journey_data.get("habit_journey", {})
        total = habits.get("total_cards", 0)
        mastered = habits.get("total_mastered", 0)
        assert mastered <= total, f"Mastered ({mastered}) > total ({total})"
    
    def test_games_count_reasonable(self, journey_data):
        """total_games_analyzed should be non-negative"""
        games = journey_data.get("total_games_analyzed", 0)
        assert games >= 0, "total_games_analyzed should be non-negative"
    
    def test_no_mongodb_id_leak(self, journey_data):
        """Should not expose MongoDB _id"""
        import json
        data_str = json.dumps(journey_data)
        assert '"_id"' not in data_str, "MongoDB _id should not be in response"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
