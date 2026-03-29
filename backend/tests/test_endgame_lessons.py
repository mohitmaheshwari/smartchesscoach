"""
Test Endgame Lessons API
========================

Tests for the endgame lesson system:
- GET /api/endgames/categories - returns 3 categories with 10 total lessons
- GET /api/endgames/lesson/{category}/{lesson} - returns lesson with positions
- POST /api/endgames/check-move - validates user moves
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEndgameCategories:
    """Test GET /api/endgames/categories endpoint"""

    def test_get_categories_returns_200(self):
        """Categories endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/endgames/categories returns 200")

    def test_categories_structure(self):
        """Categories should have correct structure"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        data = response.json()
        
        assert "categories" in data, "Response should have 'categories' key"
        categories = data["categories"]
        assert isinstance(categories, list), "Categories should be a list"
        print(f"✓ Categories is a list with {len(categories)} items")

    def test_three_categories_exist(self):
        """Should return exactly 3 categories"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        data = response.json()
        categories = data["categories"]
        
        assert len(categories) == 3, f"Expected 3 categories, got {len(categories)}"
        
        category_keys = [c["key"] for c in categories]
        assert "king_and_pawn" in category_keys, "Missing king_and_pawn category"
        assert "rook_endgames" in category_keys, "Missing rook_endgames category"
        assert "queen_vs_pawn" in category_keys, "Missing queen_vs_pawn category"
        print(f"✓ Found all 3 categories: {category_keys}")

    def test_ten_total_lessons(self):
        """Should have 10 total lessons across all categories"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        data = response.json()
        categories = data["categories"]
        
        total_lessons = sum(len(c.get("lessons", [])) for c in categories)
        assert total_lessons == 10, f"Expected 10 total lessons, got {total_lessons}"
        
        # Print breakdown
        for cat in categories:
            print(f"  - {cat['name']}: {len(cat.get('lessons', []))} lessons")
        print(f"✓ Total lessons: {total_lessons}")

    def test_category_structure(self):
        """Each category should have required fields"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        data = response.json()
        categories = data["categories"]
        
        for cat in categories:
            assert "key" in cat, f"Category missing 'key'"
            assert "name" in cat, f"Category missing 'name'"
            assert "description" in cat, f"Category missing 'description'"
            assert "lessons" in cat, f"Category missing 'lessons'"
            assert isinstance(cat["lessons"], list), f"Lessons should be a list"
        print("✓ All categories have required fields")

    def test_lesson_structure_in_categories(self):
        """Each lesson in categories should have required fields"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        data = response.json()
        categories = data["categories"]
        
        for cat in categories:
            for lesson in cat.get("lessons", []):
                assert "key" in lesson, f"Lesson missing 'key'"
                assert "name" in lesson, f"Lesson missing 'name'"
                assert "rule" in lesson, f"Lesson missing 'rule'"
                assert "description" in lesson, f"Lesson missing 'description'"
                assert "position_count" in lesson, f"Lesson missing 'position_count'"
                assert lesson["position_count"] >= 1, f"Lesson should have at least 1 position"
        print("✓ All lessons have required fields")


class TestEndgameLesson:
    """Test GET /api/endgames/lesson/{category}/{lesson} endpoint"""

    def test_get_opposition_lesson(self):
        """Should return opposition lesson with 3 positions"""
        response = requests.get(f"{BASE_URL}/api/endgames/lesson/king_and_pawn/opposition")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["lesson_key"] == "opposition"
        assert data["category_key"] == "king_and_pawn"
        assert data["name"] == "Opposition"
        assert "positions" in data
        assert len(data["positions"]) == 3, f"Expected 3 positions, got {len(data['positions'])}"
        print(f"✓ Opposition lesson has {len(data['positions'])} positions")

    def test_lesson_position_structure(self):
        """Each position should have required fields (no answers exposed)"""
        response = requests.get(f"{BASE_URL}/api/endgames/lesson/king_and_pawn/opposition")
        data = response.json()
        
        for pos in data["positions"]:
            assert "index" in pos, "Position missing 'index'"
            assert "fen" in pos, "Position missing 'fen'"
            assert "side_to_move" in pos, "Position missing 'side_to_move'"
            assert "prompt" in pos, "Position missing 'prompt'"
            # Should NOT expose correct moves
            assert "correct_move_san" not in pos, "Position should not expose correct_move_san"
            assert "correct_move_uci" not in pos, "Position should not expose correct_move_uci"
        print("✓ Positions have correct structure (no answers exposed)")

    def test_opposition_position_0_data(self):
        """Opposition position 0 should have correct FEN and prompt"""
        response = requests.get(f"{BASE_URL}/api/endgames/lesson/king_and_pawn/opposition")
        data = response.json()
        
        pos0 = data["positions"][0]
        assert pos0["index"] == 0
        assert pos0["fen"] == "8/4k3/8/8/4K3/4P3/8/8 w - - 0 1"
        assert pos0["side_to_move"] == "white"
        assert "progress" in pos0["prompt"].lower() or "move" in pos0["prompt"].lower()
        print(f"✓ Position 0 FEN: {pos0['fen']}")
        print(f"✓ Position 0 prompt: {pos0['prompt']}")

    def test_lucena_lesson(self):
        """Should return Lucena lesson with 3 positions"""
        response = requests.get(f"{BASE_URL}/api/endgames/lesson/rook_endgames/lucena")
        assert response.status_code == 200
        
        data = response.json()
        assert data["lesson_key"] == "lucena"
        assert data["name"] == "Lucena — Building a Bridge"
        assert len(data["positions"]) == 3
        print(f"✓ Lucena lesson has {len(data['positions'])} positions")

    def test_nonexistent_lesson_returns_404(self):
        """Nonexistent lesson should return 404"""
        response = requests.get(f"{BASE_URL}/api/endgames/lesson/king_and_pawn/nonexistent")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent lesson returns 404")

    def test_nonexistent_category_returns_404(self):
        """Nonexistent category should return 404"""
        response = requests.get(f"{BASE_URL}/api/endgames/lesson/nonexistent/opposition")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent category returns 404")


class TestEndgameCheckMove:
    """Test POST /api/endgames/check-move endpoint"""

    def test_correct_move_opposition_position_0(self):
        """Correct move e4d5 for opposition position 0 should return correct=true"""
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "king_and_pawn",
                "lesson_key": "opposition",
                "position_index": 0,
                "user_move_uci": "e4d5"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["correct"] == True, f"Expected correct=True, got {data}"
        assert data["move_san"] == "Kd5"
        assert data["move_uci"] == "e4d5"
        assert "on_correct" in data
        assert "idea" in data
        assert "rule_reminder" in data
        print(f"✓ Correct move e4d5 returns correct=True")
        print(f"  - on_correct: {data['on_correct'][:50]}...")

    def test_wrong_move_opposition_position_0(self):
        """Wrong move e3e4 for opposition position 0 should return correct=false"""
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "king_and_pawn",
                "lesson_key": "opposition",
                "position_index": 0,
                "user_move_uci": "e3e4"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["correct"] == False, f"Expected correct=False, got {data}"
        assert data["correct_move_san"] == "Kd5"
        assert data["correct_move_uci"] == "e4d5"
        assert "on_wrong" in data
        assert "idea" in data
        assert "rule_reminder" in data
        print(f"✓ Wrong move e3e4 returns correct=False")
        print(f"  - on_wrong: {data['on_wrong'][:50]}...")

    def test_correct_move_lucena_position_0(self):
        """Correct move h1h4 for Lucena position 0 should return correct=true"""
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "rook_endgames",
                "lesson_key": "lucena",
                "position_index": 0,
                "user_move_uci": "h1h4"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["correct"] == True, f"Expected correct=True, got {data}"
        assert data["move_san"] == "Rh4"
        print(f"✓ Correct move h1h4 (Lucena) returns correct=True")

    def test_is_last_flag_on_last_position(self):
        """is_last should be True on the last position of a lesson"""
        # Opposition has 3 positions (0, 1, 2), so position 2 is last
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "king_and_pawn",
                "lesson_key": "opposition",
                "position_index": 2,
                "user_move_uci": "d4d5"  # Correct move for position 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_last"] == True, f"Expected is_last=True for last position"
        print("✓ is_last=True on last position")

    def test_is_last_flag_on_non_last_position(self):
        """is_last should be False on non-last positions"""
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "king_and_pawn",
                "lesson_key": "opposition",
                "position_index": 0,
                "user_move_uci": "e4d5"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_last"] == False, f"Expected is_last=False for non-last position"
        print("✓ is_last=False on non-last position")

    def test_invalid_position_index_returns_400(self):
        """Invalid position index should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "king_and_pawn",
                "lesson_key": "opposition",
                "position_index": 99,
                "user_move_uci": "e4d5"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid position index returns 400")

    def test_invalid_category_returns_400(self):
        """Invalid category should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "nonexistent",
                "lesson_key": "opposition",
                "position_index": 0,
                "user_move_uci": "e4d5"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid category returns 400")

    def test_invalid_lesson_returns_400(self):
        """Invalid lesson should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/endgames/check-move",
            json={
                "category_key": "king_and_pawn",
                "lesson_key": "nonexistent",
                "position_index": 0,
                "user_move_uci": "e4d5"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid lesson returns 400")


class TestEndgameDataIntegrity:
    """Test data integrity across all endgame lessons"""

    def test_all_lessons_have_3_positions(self):
        """Each lesson should have exactly 3 positions"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        categories = response.json()["categories"]
        
        for cat in categories:
            for lesson_info in cat["lessons"]:
                lesson_res = requests.get(
                    f"{BASE_URL}/api/endgames/lesson/{cat['key']}/{lesson_info['key']}"
                )
                assert lesson_res.status_code == 200
                lesson_data = lesson_res.json()
                
                pos_count = len(lesson_data["positions"])
                assert pos_count == 3, f"Lesson {lesson_info['key']} has {pos_count} positions, expected 3"
                print(f"  ✓ {cat['name']} / {lesson_info['name']}: {pos_count} positions")
        
        print("✓ All lessons have 3 positions")

    def test_total_30_positions(self):
        """Should have 30 total positions (10 lessons × 3 positions)"""
        response = requests.get(f"{BASE_URL}/api/endgames/categories")
        categories = response.json()["categories"]
        
        total_positions = 0
        for cat in categories:
            for lesson_info in cat["lessons"]:
                total_positions += lesson_info["position_count"]
        
        assert total_positions == 30, f"Expected 30 total positions, got {total_positions}"
        print(f"✓ Total positions: {total_positions}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
