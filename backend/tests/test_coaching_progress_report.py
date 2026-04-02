"""
Test suite for the Coaching Progress Report feature.
Tests the /api/progress/coaching-report endpoint and its components.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestCoachingProgressReport:
    """Tests for GET /api/progress/coaching-report endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with dev login"""
        self.session = requests.Session()
        # Dev login to get session
        resp = self.session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200, f"Dev login failed: {resp.text}"
        
    def test_coaching_report_returns_200(self):
        """Test that coaching report endpoint returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("✓ Coaching report endpoint returns 200")
        
    def test_coaching_report_has_required_fields(self):
        """Test that coaching report contains all required fields"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        assert resp.status_code == 200
        data = resp.json()
        
        # Required top-level fields
        required_fields = [
            "has_data", "headline", "recent_form", "big_picture",
            "weakness_control", "habits_evolution", "phase_understanding",
            "review_impact", "game_stats"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"✓ All required fields present: {required_fields}")
        
    def test_has_data_is_boolean(self):
        """Test that has_data is a boolean"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        assert isinstance(data["has_data"], bool), "has_data should be boolean"
        print(f"✓ has_data is boolean: {data['has_data']}")
        
    def test_headline_is_coaching_style(self):
        """Test that headline is a coaching-style message (not generic)"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"]:
            headline = data["headline"]
            assert isinstance(headline, str), "headline should be string"
            assert len(headline) > 10, "headline should be meaningful"
            # Should not be generic placeholder text
            assert headline.lower() != "progress", "headline should not be generic"
            assert "loading" not in headline.lower(), "headline should not be loading text"
            print(f"✓ Coaching headline: '{headline}'")
        else:
            print("✓ No data - headline check skipped")
            
    def test_recent_form_structure(self):
        """Test recent_form (Last 5 Games) structure"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"]:
            recent = data["recent_form"]
            required = ["label", "games", "wins", "losses", "draws", "accuracy", "blunder_rate"]
            for field in required:
                assert field in recent, f"recent_form missing: {field}"
            
            assert recent["label"] == "recent", "recent_form label should be 'recent'"
            assert isinstance(recent["accuracy"], (int, float)), "accuracy should be numeric"
            assert isinstance(recent["blunder_rate"], (int, float)), "blunder_rate should be numeric"
            print(f"✓ Recent form: {recent['wins']}W/{recent['losses']}L/{recent['draws']}D, {recent['accuracy']}% accuracy, {recent['blunder_rate']}/g blunders")
            
    def test_big_picture_structure(self):
        """Test big_picture (Overall) structure"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"]:
            big = data["big_picture"]
            required = ["label", "games", "wins", "losses", "draws", "accuracy", "blunder_rate"]
            for field in required:
                assert field in big, f"big_picture missing: {field}"
            
            assert big["label"] == "all", "big_picture label should be 'all'"
            print(f"✓ Big picture: {big['games']} games, {big['accuracy']}% accuracy")
            
    def test_weakness_control_structure(self):
        """Test weakness_control patterns with direction"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"]:
            weaknesses = data["weakness_control"]
            assert isinstance(weaknesses, list), "weakness_control should be list"
            
            for w in weaknesses:
                assert "pattern" in w, "weakness missing pattern"
                assert "label" in w, "weakness missing label"
                assert "direction" in w, "weakness missing direction"
                assert "total" in w, "weakness missing total"
                assert "recent" in w, "weakness missing recent"
                assert "message" in w, "weakness missing message"
                
                # Direction should be one of: improving, worsening, stable
                assert w["direction"] in ["improving", "worsening", "stable"], \
                    f"Invalid direction: {w['direction']}"
                    
            print(f"✓ Weakness control: {len(weaknesses)} patterns tracked")
            for w in weaknesses:
                print(f"  - {w['label']}: {w['direction']} ({w['total']}x total, {w['recent']}x recent)")
                
    def test_phase_understanding_structure(self):
        """Test phase_understanding (Opening/Middlegame/Endgame)"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"]:
            phases = data["phase_understanding"]
            assert isinstance(phases, dict), "phase_understanding should be dict"
            
            for phase in ["opening", "middlegame", "endgame"]:
                if phase in phases:
                    p = phases[phase]
                    assert "score" in p, f"{phase} missing score"
                    assert "direction" in p, f"{phase} missing direction"
                    assert isinstance(p["score"], (int, float)), f"{phase} score should be numeric"
                    
            # Check weakest phase logic - only flagged if score < 75%
            if "weakest" in phases:
                weakest_phase = phases["weakest"]
                weakest_score = phases.get(weakest_phase, {}).get("score", 100)
                assert weakest_score < 75, f"Weakest phase {weakest_phase} has score {weakest_score} >= 75%, should not be flagged"
                print(f"✓ Weakest phase correctly flagged: {weakest_phase} ({weakest_score}%)")
            else:
                # Verify all phases are >= 75% if no weakest flagged
                for phase in ["opening", "middlegame", "endgame"]:
                    if phase in phases and phases[phase].get("score", 0) > 0:
                        score = phases[phase]["score"]
                        if score < 75:
                            pytest.fail(f"Phase {phase} has score {score} < 75% but not flagged as weakest")
                print("✓ No weakest phase flagged (all scores >= 75% or no data)")
                
            print(f"✓ Phase understanding: {phases}")
            
    def test_review_impact_structure(self):
        """Test review_impact section"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"]:
            review = data["review_impact"]
            assert "has_data" in review, "review_impact missing has_data"
            
            if review["has_data"]:
                required = [
                    "games_reviewed", "before_blunders", "after_blunders",
                    "blunder_change_pct", "before_accuracy", "after_accuracy",
                    "accuracy_change", "improving"
                ]
                for field in required:
                    assert field in review, f"review_impact missing: {field}"
                    
                # Verify percentage change is calculated
                assert isinstance(review["blunder_change_pct"], (int, float)), "blunder_change_pct should be numeric"
                assert isinstance(review["accuracy_change"], (int, float)), "accuracy_change should be numeric"
                
                print(f"✓ Review impact: {review['games_reviewed']} games reviewed")
                print(f"  - Blunders: {review['before_blunders']}/g → {review['after_blunders']}/g ({review['blunder_change_pct']}%)")
                print(f"  - Accuracy: {review['before_accuracy']}% → {review['after_accuracy']}% ({review['accuracy_change']:+.1f})")
                print(f"  - Improving: {review['improving']}")
            else:
                print("✓ Review impact: no data yet")
                
    def test_game_stats_timeline_structure(self):
        """Test game_stats for timeline display"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"]:
            stats = data["game_stats"]
            assert isinstance(stats, list), "game_stats should be list"
            
            for g in stats:
                assert "game_id" in g, "game missing game_id"
                assert "opponent" in g, "game missing opponent"
                assert "accuracy" in g, "game missing accuracy"
                assert "result" in g, "game missing result"
                assert "reviewed" in g, "game missing reviewed"
                
                # Result should be W/L/D
                assert g["result"] in ["W", "L", "D"], f"Invalid result: {g['result']}"
                
                # lesson_label is optional but should be string if present
                if "lesson_label" in g and g["lesson_label"]:
                    assert isinstance(g["lesson_label"], str), "lesson_label should be string"
                    
            print(f"✓ Game timeline: {len(stats)} games")
            for g in stats:
                reviewed_mark = "✓" if g["reviewed"] else ""
                lesson = f" [{g.get('lesson_label', '')}]" if g.get('lesson_label') else ""
                print(f"  - vs {g['opponent']}: {g['result']} {g['accuracy']}%{lesson} {reviewed_mark}")
                
    def test_game_ids_are_valid_for_navigation(self):
        """Test that game_ids can be used for navigation to /game/{gameId}"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"] and data["game_stats"]:
            game_id = data["game_stats"][0]["game_id"]
            assert game_id, "game_id should not be empty"
            assert isinstance(game_id, str), "game_id should be string"
            print(f"✓ Game IDs valid for navigation: {game_id}")
            
    def test_weakness_patterns_valid_for_training_navigation(self):
        """Test that weakness patterns can be used for /training?focus={pattern}"""
        resp = self.session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        if data["has_data"] and data["weakness_control"]:
            pattern = data["weakness_control"][0]["pattern"]
            assert pattern, "pattern should not be empty"
            assert isinstance(pattern, str), "pattern should be string"
            # Pattern should be URL-safe (no spaces, lowercase with underscores)
            assert " " not in pattern, "pattern should not contain spaces"
            print(f"✓ Weakness patterns valid for training navigation: {pattern}")


class TestEmptyStateHandling:
    """Test empty state when no data available"""
    
    def test_empty_state_structure(self):
        """Test that empty state returns has_data: false"""
        # This test would need a user with no games
        # For now, we verify the structure is correct
        session = requests.Session()
        resp = session.get(f"{BASE_URL}/api/auth/dev-login")
        assert resp.status_code == 200
        
        resp = session.get(f"{BASE_URL}/api/progress/coaching-report")
        data = resp.json()
        
        # If has_data is false, other fields may be minimal
        if not data.get("has_data"):
            assert "has_data" in data
            assert data["has_data"] == False
            print("✓ Empty state correctly returns has_data: false")
        else:
            print("✓ User has data - empty state test skipped")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
