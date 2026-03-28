"""
Coach Personality System

Makes the chess coach feel like a real human mentor, not a robotic engine.

Key features:
1. Varied phrases - never repeats the same message twice in a row
2. Remembers past games - "Last time you struggled with knight forks..."
3. Adaptive tone - encouraging when user is struggling, challenging when doing well
4. Indian mentor style - calm, direct, supportive

This is the "secret sauce" that makes users feel coached, not analyzed.
"""

import random
from typing import Optional, Dict, List
from datetime import datetime


# ============================================
# COACH PHRASES - Varied and Human
# ============================================

OPENING_GREETINGS = [
    "Let's play! I'll guide you through some interesting positions.",
    "Ready when you are. Take your time with each move.",
    "Good to see you! Let's work on your game today.",
    "Perfect time for some chess. What would you like to practice?",
    "Welcome back! Let's make today's session count.",
]

GOOD_MOVE_PHRASES = [
    "Solid move.",
    "I like that.",
    "Good thinking.",
    "That's the right idea.",
    "Exactly what I'd consider.",
    "You're on the right track.",
    "Nice.",
    "Sensible.",
    "Good choice.",
    "That works well here.",
]

EXCELLENT_MOVE_PHRASES = [
    "Excellent! That's a strong move.",
    "Very well played. You saw the key idea.",
    "Impressive. That's the best move in this position.",
    "Beautiful. You're playing like a much stronger player.",
    "Perfect. Nothing more to say.",
    "You found it! That's exactly right.",
]

BLUNDER_PHRASES = [
    "Hmm, this move has a problem. Let's look at it together.",
    "Wait - there's something you might have missed here.",
    "Careful! This could give your opponent a chance.",
    "Let me show you what you overlooked.",
    "This is a learning moment. Let's see what went wrong.",
    "Ah - this is a common mistake. Let me explain.",
]

MISTAKE_PHRASES = [
    "Not the best choice here. Let me show you why.",
    "There was a better option. Can you see it?",
    "This is okay, but you missed something stronger.",
    "Close, but there's a more accurate move.",
    "Let's look at what you could have done instead.",
]

ENCOURAGEMENT_AFTER_BLUNDER = [
    "Don't worry - everyone makes this mistake. The key is learning from it.",
    "This is exactly why we practice. Now you'll remember this pattern.",
    "I've made this same mistake many times. Now you'll see it coming.",
    "Good players aren't the ones who never blunder - they're the ones who learn from them.",
    "This is progress. You're seeing patterns you couldn't see before.",
]

THINK_PROMPTS = [
    "Before you move - what's your opponent threatening?",
    "Take a moment. What's the best piece to improve here?",
    "Look at the whole board. Any tactical opportunities?",
    "What's your plan for the next few moves?",
    "Is your king safe? Is theirs?",
]

ENDGAME_TRANSITIONS = [
    "We're entering the endgame. Time to activate your king!",
    "With fewer pieces, king activity becomes crucial.",
    "Endgame time. Remember: passed pawns must be pushed!",
    "The endgame is about patience. Small advantages matter now.",
]

PATTERN_RECOGNITION_PROMPTS = {
    "fork": [
        "Watch out for knight forks here - they can be devastating.",
        "Be careful with your piece placement - fork potential exists.",
        "Your opponent's knight is active. Stay alert for double attacks.",
    ],
    "pin": [
        "Be careful about pins. Your pieces need to stay mobile.",
        "Watch that diagonal/file - a pin could be coming.",
        "Keep your valuable pieces off the same line as your king.",
    ],
    "back_rank": [
        "Your back rank looks a bit weak. Consider creating luft.",
        "Give your king some breathing room before it's too late.",
        "That back rank needs attention. One move could change everything.",
    ],
    "hanging_piece": [
        "Check if all your pieces are protected.",
        "Before moving, count the attackers and defenders.",
        "A hanging piece is an invitation for trouble.",
    ],
}

# ============================================
# PERSONALITY STATE
# ============================================

class CoachPersonality:
    """
    Manages coach personality state to avoid repetition and adapt tone.
    """
    
    def __init__(self):
        self.last_phrase_type: Optional[str] = None
        self.last_phrase: Optional[str] = None
        self.blunders_this_game: int = 0
        self.good_moves_this_game: int = 0
        self.total_moves: int = 0
        self.mood: str = "neutral"  # neutral, encouraging, challenging
    
    def _pick_phrase(self, phrases: List[str], phrase_type: str) -> str:
        """Pick a phrase, avoiding the last one used"""
        available = [p for p in phrases if p != self.last_phrase]
        if not available:
            available = phrases
        
        phrase = random.choice(available)
        self.last_phrase = phrase
        self.last_phrase_type = phrase_type
        return phrase
    
    def get_greeting(self) -> str:
        """Get opening greeting"""
        return self._pick_phrase(OPENING_GREETINGS, "greeting")
    
    def get_good_move_comment(self) -> str:
        """Comment for a good move"""
        self.good_moves_this_game += 1
        self.total_moves += 1
        
        # If many good moves in a row, give more praise
        if self.good_moves_this_game >= 3 and self.blunders_this_game == 0:
            return self._pick_phrase(EXCELLENT_MOVE_PHRASES, "excellent")
        return self._pick_phrase(GOOD_MOVE_PHRASES, "good")
    
    def get_excellent_move_comment(self) -> str:
        """Comment for an excellent/best move"""
        self.good_moves_this_game += 1
        self.total_moves += 1
        return self._pick_phrase(EXCELLENT_MOVE_PHRASES, "excellent")
    
    def get_blunder_comment(self) -> str:
        """Comment for a blunder"""
        self.blunders_this_game += 1
        self.good_moves_this_game = 0  # Reset streak
        self.total_moves += 1
        self.mood = "encouraging"
        return self._pick_phrase(BLUNDER_PHRASES, "blunder")
    
    def get_mistake_comment(self) -> str:
        """Comment for a mistake (less severe than blunder)"""
        self.total_moves += 1
        return self._pick_phrase(MISTAKE_PHRASES, "mistake")
    
    def get_encouragement_after_blunder(self) -> str:
        """Encouraging message after showing the blunder"""
        return self._pick_phrase(ENCOURAGEMENT_AFTER_BLUNDER, "encouragement")
    
    def get_think_prompt(self) -> str:
        """Prompt user to think before moving"""
        return self._pick_phrase(THINK_PROMPTS, "think")
    
    def get_endgame_transition(self) -> str:
        """Comment when entering endgame"""
        return self._pick_phrase(ENDGAME_TRANSITIONS, "endgame")
    
    def get_pattern_warning(self, pattern_type: str) -> Optional[str]:
        """Get warning for a specific pattern"""
        phrases = PATTERN_RECOGNITION_PROMPTS.get(pattern_type, [])
        if phrases:
            return self._pick_phrase(phrases, f"pattern_{pattern_type}")
        return None
    
    def get_adaptive_comment(self, eval_delta: float) -> str:
        """
        Get comment based on move quality (eval delta in centipawns).
        
        eval_delta > 0: User improved position
        eval_delta < -100: Blunder
        eval_delta < -50: Mistake
        """
        if eval_delta > 50:
            return self.get_excellent_move_comment()
        elif eval_delta > -20:
            return self.get_good_move_comment()
        elif eval_delta > -100:
            return self.get_mistake_comment()
        else:
            return self.get_blunder_comment()
    
    def get_session_summary(self) -> str:
        """Summary at end of game"""
        ratio = self.good_moves_this_game / max(1, self.total_moves)
        
        if ratio > 0.8:
            return "Excellent session! You played very accurately. Keep it up!"
        elif ratio > 0.6:
            return "Good game! A few mistakes to learn from, but solid overall."
        elif ratio > 0.4:
            return "Some ups and downs, but that's how we learn. Focus on the patterns we discussed."
        else:
            return "Tough game, but valuable lessons. Review the key moments and you'll improve."
    
    def reset_game(self):
        """Reset for new game"""
        self.blunders_this_game = 0
        self.good_moves_this_game = 0
        self.total_moves = 0
        self.mood = "neutral"


# ============================================
# MEMORY-AWARE COMMENTS
# ============================================

def get_memory_comment(user_stats: Dict) -> Optional[str]:
    """
    Generate a comment based on user's historical patterns.
    
    Args:
        user_stats: Dict with keys like:
            - common_mistakes: ["fork", "back_rank"]
            - recent_blunders: int
            - games_played: int
            - improvement_areas: List[str]
    """
    if not user_stats:
        return None
    
    common_mistakes = user_stats.get("common_mistakes", [])
    games_played = user_stats.get("games_played", 0)
    
    if games_played < 5:
        return "I'm still getting to know your playing style. Let's play a few more games!"
    
    if "fork" in common_mistakes:
        return "I notice knight forks have been tricky for you. Let's stay alert for those today."
    
    if "back_rank" in common_mistakes:
        return "Remember to watch your back rank - that's been a pattern in your games."
    
    if "time_pressure" in common_mistakes:
        return "Take your time today. Rushing has cost you in previous games."
    
    return None


# ============================================
# GLOBAL INSTANCE
# ============================================

_personality_instance: Optional[CoachPersonality] = None

def get_coach_personality() -> CoachPersonality:
    """Get or create the coach personality instance"""
    global _personality_instance
    if _personality_instance is None:
        _personality_instance = CoachPersonality()
    return _personality_instance


def get_coach_phrase(phrase_type: str, **kwargs) -> str:
    """
    Get a coach phrase of the specified type.
    
    Types: greeting, good_move, excellent_move, blunder, mistake, 
           encouragement, think_prompt, endgame
    """
    personality = get_coach_personality()
    
    if phrase_type == "greeting":
        return personality.get_greeting()
    elif phrase_type == "good_move":
        return personality.get_good_move_comment()
    elif phrase_type == "excellent_move":
        return personality.get_excellent_move_comment()
    elif phrase_type == "blunder":
        return personality.get_blunder_comment()
    elif phrase_type == "mistake":
        return personality.get_mistake_comment()
    elif phrase_type == "encouragement":
        return personality.get_encouragement_after_blunder()
    elif phrase_type == "think_prompt":
        return personality.get_think_prompt()
    elif phrase_type == "endgame":
        return personality.get_endgame_transition()
    elif phrase_type.startswith("pattern_"):
        pattern = phrase_type.replace("pattern_", "")
        return personality.get_pattern_warning(pattern) or ""
    
    return ""
