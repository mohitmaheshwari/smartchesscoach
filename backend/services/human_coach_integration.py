"""
Integrated Human Coach Service
==============================

Combines all coaching systems into a single, human-like coaching experience:
1. Socratic questioning - Ask before telling
2. Deep memory integration - Reference past games
3. Indian-English conversational tone - Warm, natural language
4. Pattern-based coaching - Connect current position to habits
5. Personalized learning - Adapt to user's level and weaknesses

This is the SOUL of the coaching app - making it feel like a real human coach.
"""

import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class CoachingContext:
    """Context for generating human-like coaching."""
    user_id: str
    user_name: str
    user_rating: int
    
    # Current game state
    current_fen: str
    user_color: str
    move_number: int
    
    # Memory
    habits: List[Dict] = None
    recent_mistakes: List[Dict] = None
    learning_progress: Dict = None
    
    # Current session
    mistakes_this_game: int = 0
    good_moves_this_game: int = 0
    concepts_taught: List[str] = None


class HumanCoachIntegration:
    """
    The integrated human-like coaching experience.
    Feels like sitting with a warm, knowledgeable coach.
    """
    
    # =====================================================
    # INDIAN-ENGLISH CONVERSATIONAL TEMPLATES
    # Warm, encouraging, natural
    # =====================================================
    
    GREETINGS = [
        "Chalo {name}, let's play some chess! Ready?",
        "Ah {name}! Good to see you. Shall we start?",
        "{name}! Come, come. Let's see what you've got today.",
        "Welcome back {name}! Today we'll work on something interesting.",
    ]
    
    OPENING_COMMENTS = {
        "known_weakness": [
            "Dekho {name}, this opening can be tricky for you. Remember last time with {pattern}? Let's be careful.",
            "Ah, this position! You've struggled here before na? Watch out for {pattern}.",
            "See {name}, this type of position - you've had trouble with {pattern}. Let's go slow.",
        ],
        "strength": [
            "Good choice! You play this opening well. Remember your nice win last week?",
            "Ah, your favorite! You handle these positions nicely.",
            "I like this - you've been doing well in these structures.",
        ],
        "neutral": [
            "Interesting choice. Let's see how it develops.",
            "Okay, good start. What's your plan here?",
            "Chalo, let's play it out. Remember - think before each move!",
        ]
    }
    
    # Socratic questions - ASK before TELLING
    SOCRATIC_QUESTIONS = {
        "blunder": [
            "Arre {name}! That move... tell me, what were you thinking? Walk me through it.",
            "{name}, interesting choice. Why this move? What did you see?",
            "Hmm. Before I say anything - what was your idea with {move}?",
            "Hold on {name}. That {move} - explain your thinking.",
        ],
        "mistake": [
            "Okay {name}, tell me - why {move}? What was the plan?",
            "I see {move}. What were you hoping to achieve?",
            "{name}, walk me through this. Why did you choose {move}?",
            "Interesting. What made you play {move}?",
        ],
        "missed_tactic": [
            "Hmm {name}, did you feel something in this position? Look again...",
            "There was something special here. Did you see it?",
            "{name}, this position was calling for something. What do you notice?",
            "Look carefully at the board. Something powerful was possible...",
        ],
        "positional": [
            "{name}, what do you think about the pawn structure here?",
            "Tell me - which pieces are not doing much?",
            "What's the weakest point in the position? Think carefully.",
            "If you were my opponent, what would worry you?",
        ]
    }
    
    # After they respond or give up
    REVEAL_MESSAGES = {
        "gentle": [
            "Dekho {name}, the thing is - {explanation}",
            "Ah, I'll show you. See - {explanation}",
            "Let me explain na. {explanation}",
            "Here's the idea {name}: {explanation}",
        ],
        "encouraging": [
            "You were close! But see - {explanation}",
            "Good thinking, but here's what you missed: {explanation}",
            "Almost! The key point is: {explanation}",
        ],
        "direct": [
            "Look here: {explanation}",
            "See this: {explanation}",
            "The answer is: {explanation}",
        ]
    }
    
    # Pattern recognition messages
    PATTERN_RECOGNITION = {
        "recurring": [
            "Arre {name}! This is the {count}th time this week with {pattern}. Remember we discussed this?",
            "See, this {pattern} problem again. We need to fix this na?",
            "This same mistake - {pattern}. I've seen this {count} times from you recently.",
            "{name}, {pattern} again? Come on yaar, we've talked about this!",
        ],
        "first_time": [
            "This is new - {pattern}. Let me explain...",
            "Okay, you haven't seen this before: {pattern}. Pay attention.",
            "This is a common thing: {pattern}. Important to know.",
        ],
        "improvement": [
            "Hey, you used to do {pattern} a lot. But now you're catching it! Well done!",
            "I notice you're improving on {pattern}. Good work {name}!",
            "Remember when {pattern} was a problem? Look how far you've come!",
        ]
    }
    
    # Encouragement
    ENCOURAGEMENT = {
        "good_move": [
            "Shabash {name}! That's the move! 👏",
            "Excellent! You're thinking like a strong player now.",
            "Yes! {move} is exactly right. You saw it!",
            "Bahut accha! {move} - this shows real understanding.",
            "Beautiful move! You're improving {name}!",
        ],
        "after_mistake": [
            "It's okay {name}. Everyone makes mistakes. Even Grandmasters!",
            "Don't worry. This is how we learn na?",
            "Koi baat nahi. Let's understand why and move on.",
            "No problem {name}. The important thing is to learn from this.",
        ],
        "struggling": [
            "Take your time {name}. No rush.",
            "It's a tricky position. Think carefully.",
            "Chess is hard! But you're getting better, I can see it.",
            "Don't give up. Let's work through this together.",
        ]
    }
    
    # Memory reference
    MEMORY_REFERENCES = {
        "similar_game": [
            "Remember your game against {opponent} on {date}? Same type of position!",
            "You had this structure last week. Do you recall what happened?",
            "Dekho, this is like your {opening} game from {date}.",
        ],
        "learning_callback": [
            "We practiced this pattern last time, remember?",
            "This is what we worked on in the lab! {concept}",
            "You learned this trap! {trap_name} - can you see it here?",
        ],
        "progress": [
            "Two weeks ago, you would have missed this. Look at you now!",
            "Your {skill} has really improved. I can see it.",
            "This is exactly the kind of move you struggled with before. Well done!",
        ]
    }
    
    # Proactive teaching
    PROACTIVE_TEACHING = {
        "before_game": [
            "Based on your recent games, let's focus on {focus} today.",
            "I've noticed {pattern} coming up. Let's work on that.",
            "Today's goal: improve your {skill}. Ready?",
        ],
        "during_game": [
            "This is a chance to practice {concept}. What would you do?",
            "Remember what we said about {concept}? Apply it here.",
            "This is exactly the type of position where {advice}.",
        ],
        "end_game": [
            "Good game {name}! Today you showed improvement in {skill}.",
            "We need to keep working on {weakness}. But good effort!",
            "Progress! Your {skill} is getting stronger.",
        ]
    }

    def __init__(self, db=None, llm_func=None):
        """Initialize with database and LLM function."""
        self.db = db
        self.call_llm = llm_func
    
    async def get_personalized_greeting(self, user_id: str, user_name: str) -> str:
        """Get a warm, personalized greeting."""
        # Get user's recent history
        recent_games = []
        recent_focus = None
        
        if self.db:
            try:
                # Get recent games
                recent_games = await self.db.games.find({
                    "user_id": user_id
                }).sort("created_at", -1).limit(5).to_list(5)
                
                # Get learning focus
                memory = await self.db.coach_memory.find_one({"user_id": user_id})
                if memory and memory.get("learning_progress"):
                    recent_focus = memory["learning_progress"].get("current_focus")
            except Exception as e:
                logger.warning(f"Error fetching user data: {e}")
        
        # Generate greeting
        greeting = random.choice(self.GREETINGS).format(name=user_name or "friend")
        
        # Add context if available
        if recent_focus:
            greeting += f" Last time we were working on {recent_focus}. Shall we continue?"
        elif recent_games:
            greeting += " How was your practice since last time?"
        
        return greeting
    
    async def get_opening_comment(
        self, 
        ctx: CoachingContext, 
        opening_name: str
    ) -> str:
        """Get a comment about the opening based on user's history."""
        # Check if user has weakness in this opening
        if ctx.habits:
            for habit in ctx.habits:
                if opening_name.lower() in habit.get("name", "").lower():
                    if not habit.get("is_good", True):
                        return random.choice(
                            self.OPENING_COMMENTS["known_weakness"]
                        ).format(name=ctx.user_name, pattern=habit["name"])
        
        return random.choice(self.OPENING_COMMENTS["neutral"])
    
    def get_socratic_question(
        self, 
        ctx: CoachingContext,
        move_played: str,
        move_quality: str,
        position_type: str = "blunder"
    ) -> Dict[str, Any]:
        """
        Get a Socratic question - ASK before TELLING.
        
        Returns a question that prompts the user to think,
        rather than immediately giving the answer.
        """
        # Map quality to question type
        if move_quality in ["blunder"]:
            q_type = "blunder"
        elif move_quality in ["mistake"]:
            q_type = "mistake"
        elif position_type == "missed_tactic":
            q_type = "missed_tactic"
        else:
            q_type = "positional"
        
        questions = self.SOCRATIC_QUESTIONS.get(q_type, self.SOCRATIC_QUESTIONS["mistake"])
        question = random.choice(questions).format(
            name=ctx.user_name or "friend",
            move=move_played
        )
        
        return {
            "message": question,
            "expects_response": True,
            "response_type": "text",
            "socratic_mode": True,
            "question_type": q_type
        }
    
    def get_reveal_message(
        self,
        ctx: CoachingContext,
        explanation: str,
        user_was_close: bool = False
    ) -> str:
        """Get the reveal message after Socratic questioning."""
        if user_was_close:
            templates = self.REVEAL_MESSAGES["encouraging"]
        else:
            templates = self.REVEAL_MESSAGES["gentle"]
        
        return random.choice(templates).format(
            name=ctx.user_name or "friend",
            explanation=explanation
        )
    
    async def check_pattern_occurrence(
        self,
        ctx: CoachingContext,
        pattern_name: str
    ) -> Optional[Dict]:
        """Check if this pattern has occurred before for the user."""
        if not self.db:
            return None
        
        try:
            # Count occurrences this week
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            count = await self.db.mistakes.count_documents({
                "user_id": ctx.user_id,
                "pattern": pattern_name,
                "created_at": {"$gte": week_ago}
            })
            
            if count > 1:
                return {
                    "is_recurring": True,
                    "count": count,
                    "message": random.choice(
                        self.PATTERN_RECOGNITION["recurring"]
                    ).format(
                        name=ctx.user_name,
                        count=count,
                        pattern=pattern_name
                    )
                }
            elif count == 1:
                return {
                    "is_recurring": False,
                    "count": 1,
                    "message": random.choice(
                        self.PATTERN_RECOGNITION["first_time"]
                    ).format(pattern=pattern_name)
                }
        except Exception as e:
            logger.warning(f"Error checking pattern: {e}")
        
        return None
    
    def get_encouragement(
        self,
        ctx: CoachingContext,
        situation: str,
        move: str = ""
    ) -> str:
        """Get appropriate encouragement."""
        templates = self.ENCOURAGEMENT.get(situation, self.ENCOURAGEMENT["after_mistake"])
        return random.choice(templates).format(
            name=ctx.user_name or "friend",
            move=move
        )
    
    async def get_memory_reference(
        self,
        ctx: CoachingContext,
        current_position_type: str
    ) -> Optional[str]:
        """Get a reference to a past game or lesson if relevant."""
        if not self.db:
            return None
        
        try:
            # Look for similar positions/situations in past games
            # This is a simplified version - could be enhanced with position similarity
            await self.db.games.find({
                "user_id": ctx.user_id,
                "opening_name": {"$exists": True}
            }).sort("created_at", -1).limit(10).to_list(10)
            
            # Check if user learned relevant traps
            memory = await self.db.coach_memory.find_one({"user_id": ctx.user_id})
            if memory:
                traps_learned = memory.get("learning_progress", {}).get("traps_learned", [])
                if traps_learned:
                    return random.choice(
                        self.MEMORY_REFERENCES["learning_callback"]
                    ).format(
                        concept="opening traps",
                        trap_name=random.choice(traps_learned)
                    )
            
        except Exception as e:
            logger.warning(f"Error getting memory reference: {e}")
        
        return None
    
    def get_proactive_advice(
        self,
        ctx: CoachingContext,
        timing: str,  # "before_game", "during_game", "end_game"
        focus_area: str = "",
        concept: str = ""
    ) -> str:
        """Get proactive teaching advice."""
        templates = self.PROACTIVE_TEACHING.get(timing, [])
        if not templates:
            return ""
        
        return random.choice(templates).format(
            focus=focus_area,
            pattern=focus_area,
            skill=focus_area,
            concept=concept,
            advice=concept,
            weakness=focus_area,
            name=ctx.user_name or "friend"
        )
    
    async def generate_full_feedback(
        self,
        ctx: CoachingContext,
        move_played: str,
        best_move: str,
        move_quality: str,
        base_explanation: str,
        pattern_name: str = ""
    ) -> Dict[str, Any]:
        """
        Generate complete human-like feedback.
        
        Combines:
        - Socratic questioning
        - Pattern recognition
        - Memory references
        - Encouragement
        - Natural language
        """
        result = {
            "socratic_question": None,
            "pattern_reference": None,
            "memory_reference": None,
            "main_message": "",
            "encouragement": "",
            "expects_response": False
        }
        
        # For mistakes/blunders - use Socratic approach
        if move_quality in ["blunder", "mistake"]:
            # First, ask what they were thinking
            socratic = self.get_socratic_question(
                ctx, move_played, move_quality
            )
            result["socratic_question"] = socratic
            result["expects_response"] = True
            
            # Check if recurring pattern
            if pattern_name:
                pattern_info = await self.check_pattern_occurrence(ctx, pattern_name)
                if pattern_info:
                    result["pattern_reference"] = pattern_info
            
            # Add encouragement
            result["encouragement"] = self.get_encouragement(ctx, "after_mistake")
            
        elif move_quality in ["excellent", "good"]:
            # Celebrate good moves
            result["main_message"] = self.get_encouragement(
                ctx, "good_move", move_played
            )
            
            # Check for progress reference
            memory_ref = await self.get_memory_reference(ctx, "good_move")
            if memory_ref:
                result["memory_reference"] = memory_ref
        
        else:
            # Inaccuracies - gentle guidance
            result["main_message"] = self.get_reveal_message(
                ctx, base_explanation, user_was_close=True
            )
        
        return result


# Singleton instance
_human_coach = None

def get_human_coach(db=None, llm_func=None) -> HumanCoachIntegration:
    """Get or create the human coach integration instance."""
    global _human_coach
    if _human_coach is None or db is not None:
        _human_coach = HumanCoachIntegration(db, llm_func)
    return _human_coach
