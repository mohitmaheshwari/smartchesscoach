#!/usr/bin/env python3
"""
Backend Testing for Play with Coach Opening Engine Updates

This test verifies:
1. build_opening_coaching_context() for various openings
2. get_variation_teaching() for deep variations
3. Color-aware plans_for_user functionality
4. No regressions in Queen's Gambit family
5. API endpoints for live coach messages
"""

import requests
import json
import sys
import asyncio
from typing import Dict, List, Optional
import traceback

# Add backend path for imports
sys.path.insert(0, '/app/backend')

from coach_engine.opening_plans import build_opening_coaching_context, get_opening_by_moves
from services.move_by_move_coach import get_variation_teaching

# Test configuration
BASE_URL = "https://thinking-simulator-1.preview.emergentagent.com/api"
TEST_USER_ID = None
TEST_SESSION_TOKEN = None

class OpeningTestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.total = 0
        
    def add_test(self, test_name: str, success: bool, error: str = None):
        self.total += 1
        if success:
            self.passed.append(test_name)
            print(f"✅ {test_name}")
        else:
            self.failed.append((test_name, error or "Unknown error"))
            print(f"❌ {test_name}: {error}")
            
    def summary(self):
        print(f"\n=== OPENING ENGINE TEST RESULTS ===")
        print(f"Total tests: {self.total}")
        print(f"Passed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")
        
        if self.failed:
            print("\nFAILED TESTS:")
            for test_name, error in self.failed:
                print(f"  - {test_name}: {error}")
        
        return len(self.failed) == 0

results = OpeningTestResults()

def test_build_opening_coaching_context():
    """Test 1: Unit verification for build_opening_coaching_context()"""
    
    test_cases = [
        # Italian Game (Two Knights / Fried Liver ideas)
        {
            "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],
            "expected_name": "Italian Game",
            "should_have_variations": True,
            "expected_variation": "two_knights_defense"
        },
        
        # Sicilian Defense (Open Sicilian)
        {
            "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4"],
            "expected_name": "Sicilian Defense",
            "should_have_variations": True,
            "expected_variation": "open_sicilian_classical"
        },
        
        # French Defense (Advance Variation)
        {
            "moves": ["e4", "e6", "d4", "d5", "e5"],
            "expected_name": "French Defense",
            "should_have_variations": True,
            "expected_variation": "advance_french"
        },
        
        # Caro-Kann Defense (Classical Development)
        {
            "moves": ["e4", "c6", "d4", "d5", "Nc3"],
            "expected_name": "Caro-Kann Defense",
            "should_have_variations": True,
            "expected_variation": "classical_caro_kann"
        },
        
        # King's Indian Defense (Main Setup)
        {
            "moves": ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7"],
            "expected_name": "King's Indian Defense",
            "should_have_variations": True,
            "expected_variation": "main_kings_indian"
        },
        
        # London System (...c5 challenge)
        {
            "moves": ["d4", "d5", "Nf3", "Nf6", "Bf4", "c5"],
            "expected_name": "London System",
            "should_have_variations": True,
            "expected_variation": "main_london_c5"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            context = build_opening_coaching_context(test_case["moves"])
            
            if context is None:
                results.add_test(f"Context Test {i} ({test_case['expected_name']})", False, 
                                "Context is None - opening not recognized")
                continue
                
            # Test opening name
            if context["name"] != test_case["expected_name"]:
                results.add_test(f"Context Test {i} ({test_case['expected_name']})", False, 
                                f"Expected name '{test_case['expected_name']}', got '{context['name']}'")
                continue
                
            # Test variations exist
            if test_case["should_have_variations"] and not context.get("variations"):
                results.add_test(f"Context Test {i} ({test_case['expected_name']})", False, 
                                "Expected variations but none found")
                continue
                
            # Test specific variation exists
            if test_case.get("expected_variation") and test_case["expected_variation"] not in context.get("variations", {}):
                results.add_test(f"Context Test {i} ({test_case['expected_name']})", False, 
                                f"Expected variation '{test_case['expected_variation']}' not found")
                continue
                
            # Test teaching moments exist
            if not context.get("teaching_moments"):
                results.add_test(f"Context Test {i} ({test_case['expected_name']})", False, 
                                "No teaching moments found")
                continue
                
            results.add_test(f"Context Test {i} ({test_case['expected_name']})", True)
            
        except Exception as e:
            results.add_test(f"Context Test {i} ({test_case['expected_name']})", False, str(e))


def test_get_variation_teaching():
    """Test 2: Unit verification for get_variation_teaching()"""
    
    test_cases = [
        # Italian Game Two Knights - test white side
        {
            "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"],
            "user_color": "white",
            "expected_variation": "Italian Game — Two Knights / Fried Liver Ideas",
            "should_have_teaching": True,
            "should_have_plans": True
        },
        
        # Sicilian Open - test black side (important for color-aware plans)
        {
            "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
            "user_color": "black",
            "expected_variation": "Sicilian Defense — Open Sicilian",
            "should_have_teaching": True,
            "should_have_plans": True
        },
        
        # French Advance - test black side
        {
            "moves": ["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6"],
            "user_color": "black",
            "expected_variation": "French Defense — Advance Variation",
            "should_have_teaching": True,
            "should_have_plans": True
        },
        
        # Caro-Kann Classical - test black side
        {
            "moves": ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"],
            "user_color": "black",
            "expected_variation": "Caro-Kann Defense — Classical Development",
            "should_have_teaching": True,
            "should_have_plans": True
        },
        
        # King's Indian Main - test black side
        {
            "moves": ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6"],
            "user_color": "black",
            "expected_variation": "King's Indian Defense — Main Setup",
            "should_have_teaching": True,
            "should_have_plans": True
        },
        
        # London c5 Challenge - test white side
        {
            "moves": ["d4", "d5", "Nf3", "Nf6", "Bf4", "c5", "e3"],
            "user_color": "white",
            "expected_variation": "London System — ...c5 Challenge",
            "should_have_teaching": True,
            "should_have_plans": True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            context = build_opening_coaching_context(test_case["moves"])
            if not context:
                results.add_test(f"Variation Test {i}", False, "No opening context")
                continue
                
            teaching = get_variation_teaching(test_case["moves"], context, test_case["user_color"])
            
            if not teaching:
                results.add_test(f"Variation Test {i}", False, "No variation teaching found")
                continue
                
            # Test variation name
            if teaching["variation_name"] != test_case["expected_variation"]:
                results.add_test(f"Variation Test {i}", False, 
                                f"Expected '{test_case['expected_variation']}', got '{teaching['variation_name']}'")
                continue
                
            # Test color-aware plans_for_user
            if test_case["should_have_plans"]:
                plans = teaching.get("plans_for_user", [])
                if not plans:
                    results.add_test(f"Variation Test {i}", False, 
                                    f"No plans_for_user found for {test_case['user_color']}")
                    continue
                    
                # For black-side openings, verify we have plans appropriate for black
                if test_case["user_color"] == "black":
                    # Check that plans mention black-side concepts (more flexible criteria)
                    plan_text = " ".join(plans).lower()
                    black_keywords = ["counter", "pressure", "break", "challenge", "fight", "attack", "active", "free", "equalizer", "queenside"]
                    if not any(keyword in plan_text for keyword in black_keywords):
                        results.add_test(f"Variation Test {i}", False, 
                                        f"Plans for black don't seem color-appropriate: {plans}")
                        continue
                        
            results.add_test(f"Variation Test {i} ({test_case['user_color']} in {test_case['expected_variation']})", True)
            
        except Exception as e:
            results.add_test(f"Variation Test {i}", False, str(e))


def test_queens_gambit_no_regressions():
    """Test 3: Confirm no regressions in Queen's Gambit family"""
    
    qg_test_cases = [
        # Queen's Gambit Declined
        {
            "moves": ["d4", "d5", "c4", "e6"],
            "expected_name": "Queen's Gambit Declined",
            "expected_family": "Queen's Gambit",
            "should_have_qgd_variation": True
        },
        
        # Queen's Gambit Accepted
        {
            "moves": ["d4", "d5", "c4", "dxc4"],
            "expected_name": "Queen's Gambit",
            "should_have_qga_variation": True
        },
        
        # Slav Defense
        {
            "moves": ["d4", "d5", "c4", "c6"],
            "expected_name": "Slav Defense",
            "expected_family": "Queen's Gambit",
            "should_have_slav_variation": True
        }
    ]
    
    for i, test_case in enumerate(qg_test_cases, 1):
        try:
            context = build_opening_coaching_context(test_case["moves"])
            
            if not context:
                results.add_test(f"QG Regression Test {i}", False, "No context found")
                continue
                
            # Test opening name
            if context["name"] != test_case["expected_name"]:
                results.add_test(f"QG Regression Test {i}", False, 
                                f"Expected '{test_case['expected_name']}', got '{context['name']}'")
                continue
                
            # Test family inheritance for QGD and Slav
            if test_case.get("expected_family"):
                if context.get("family_name") != test_case["expected_family"]:
                    results.add_test(f"QG Regression Test {i}", False, 
                                    f"Expected family '{test_case['expected_family']}', got '{context.get('family_name')}'")
                    continue
                    
            # Test specific variations
            variations = context.get("variations", {})
            if test_case.get("should_have_qgd_variation") and "qgd_main" not in variations:
                results.add_test(f"QG Regression Test {i}", False, "QGD main variation missing")
                continue
                
            if test_case.get("should_have_qga_variation") and "qga_main" not in variations:
                results.add_test(f"QG Regression Test {i}", False, "QGA main variation missing")
                continue
                
            if test_case.get("should_have_slav_variation") and "slav_main" not in variations:
                results.add_test(f"QG Regression Test {i}", False, "Slav main variation missing")
                continue
                
            results.add_test(f"QG Regression Test {i} ({test_case['expected_name']})", True)
            
        except Exception as e:
            results.add_test(f"QG Regression Test {i}", False, str(e))


def test_black_side_plans():
    """Test 4: Specific test for plans_for_user in black openings"""
    
    black_openings = [
        {
            "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3"],  # Add one more move to trigger variation
            "opening_name": "Sicilian Defense",
            "user_color": "black"
        },
        {
            "moves": ["e4", "e6", "d4", "d5", "e5"],
            "opening_name": "French Defense",
            "user_color": "black"
        },
        {
            "moves": ["e4", "c6", "d4", "d5", "Nc3"],
            "opening_name": "Caro-Kann Defense",
            "user_color": "black"
        }
    ]
    
    for i, test_case in enumerate(black_openings, 1):
        try:
            context = build_opening_coaching_context(test_case["moves"])
            if not context:
                results.add_test(f"Black Plans Test {i}", False, "No context")
                continue
                
            teaching = get_variation_teaching(test_case["moves"], context, test_case["user_color"])
            if not teaching:
                results.add_test(f"Black Plans Test {i}", False, "No variation teaching")
                continue
                
            plans_for_user = teaching.get("plans_for_user", [])
            if not plans_for_user:
                results.add_test(f"Black Plans Test {i}", False, "No plans_for_user found")
                continue
                
            # Verify plans are appropriate for black
            plan_text = " ".join(plans_for_user).lower()
            black_keywords = ["counter", "challenge", "pressure", "fight", "break", "attack", "control", "active", "free", "equalizer"]
            
            if not any(keyword in plan_text for keyword in black_keywords):
                results.add_test(f"Black Plans Test {i}", False, 
                                f"Plans don't seem appropriate for black: {plans_for_user}")
                continue
                
            results.add_test(f"Black Plans Test {i} ({test_case['opening_name']})", True)
            
        except Exception as e:
            results.add_test(f"Black Plans Test {i}", False, str(e))


def authenticate():
    """Get authentication for API testing"""
    global TEST_USER_ID, TEST_SESSION_TOKEN
    
    try:
        # Use dev login with session cookies
        session = requests.Session()
        response = session.get(f"{BASE_URL}/auth/dev-login")
        if response.status_code == 200:
            data = response.json()
            TEST_USER_ID = data.get("user_id")
            
            if TEST_USER_ID:
                # Store the session for later use
                authenticate.session = session
                return True
    except Exception as e:
        print(f"Authentication failed: {e}")
    
    return False


def test_api_endpoints():
    """Test 5: API endpoints for live coach functionality"""
    
    # Try to authenticate
    try:
        if not authenticate():
            results.add_test("API Authentication", False, "Failed to authenticate")
            return
        
        results.add_test("API Authentication", True)
    except Exception as e:
        results.add_test("API Authentication", False, f"Auth error: {str(e)}")
        return
    
    # Test 1: Start a coach session
    try:
        start_payload = {
            "user_color": "white",
            "difficulty": "intermediate",
            "focus_areas": ["opening"]
        }
        
        # Use the authenticated session
        session = getattr(authenticate, 'session', requests.Session())
        response = session.post(f"{BASE_URL}/coach/play/start", json=start_payload)
        
        if response.status_code == 200:
            session_data = response.json()
            session_id = session_data.get("session_id")
            
            if session_id:
                results.add_test("API Start Session", True)
                
                # Test 2: Get opening plan
                try:
                    plan_response = session.get(f"{BASE_URL}/coach/play/opening-plan?session_id={session_id}")
                    if plan_response.status_code == 200:
                        plan_data = plan_response.json()
                        if plan_data.get("success"):
                            results.add_test("API Opening Plan", True)
                        else:
                            results.add_test("API Opening Plan", False, "Plan response unsuccessful")
                    else:
                        results.add_test("API Opening Plan", False, f"HTTP {plan_response.status_code}")
                except Exception as e:
                    results.add_test("API Opening Plan", False, str(e))
                
                # Test 3: Make a move to test coach response
                try:
                    move_payload = {
                        "session_id": session_id,
                        "move": "e4",
                        "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                    }
                    
                    move_response = session.post(f"{BASE_URL}/coach/play/move", json=move_payload)
                    if move_response.status_code == 200:
                        move_data = move_response.json()
                        if move_data.get("success"):
                            results.add_test("API Make Move", True)
                        else:
                            results.add_test("API Make Move", False, f"Move unsuccessful: {move_data}")
                    else:
                        results.add_test("API Make Move", False, f"HTTP {move_response.status_code}: {move_response.text}")
                except Exception as e:
                    results.add_test("API Make Move", False, str(e))
                
                # Clean up: End session
                try:
                    end_payload = {"session_id": session_id}
                    session.post(f"{BASE_URL}/coach/play/end", json=end_payload)
                except:
                    pass  # Best effort cleanup
                    
            else:
                results.add_test("API Start Session", False, "No session_id in response")
        else:
            results.add_test("API Start Session", False, f"HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        results.add_test("API Start Session", False, str(e))


def main():
    """Run all opening engine tests"""
    print("=== PLAY WITH COACH OPENING ENGINE VERIFICATION ===\n")
    
    print("Testing build_opening_coaching_context()...")
    test_build_opening_coaching_context()
    
    print("\nTesting get_variation_teaching()...")
    test_get_variation_teaching()
    
    print("\nTesting Queen's Gambit family (no regressions)...")
    test_queens_gambit_no_regressions()
    
    print("\nTesting black-side plans_for_user...")
    test_black_side_plans()
    
    print("\nTesting API endpoints...")
    test_api_endpoints()
    
    # Final summary
    success = results.summary()
    
    if success:
        print("\n🎉 ALL TESTS PASSED! Opening engine is working correctly.")
    else:
        print(f"\n⚠️  {len(results.failed)} tests failed. See details above.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)