"""
Mistake Fingerprint Service
============================

Manages persistent storage and retrieval of user mistake patterns.
Implements decay scoring to weight recent mistakes more heavily.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient

from .schemas import MistakeFingerprint
from .enums import MistakeCategory

logger = logging.getLogger(__name__)


class FingerprintService:
    """
    Service for managing user mistake fingerprints with MongoDB persistence.
    
    Decay Formula:
        decay_score = 0.9 ^ days_since_last_seen
        
    This means:
        - Day 0: decay_score = 1.0 (just happened)
        - Day 7: decay_score = 0.48 (half strength)
        - Day 30: decay_score = 0.04 (very weak)
        - Day 60: decay_score = 0.002 (negligible)
    """
    
    def __init__(self, db=None):
        """
        Initialize fingerprint service.
        
        Args:
            db: MongoDB database instance (optional, will connect if not provided)
        """
        if db is None:
            mongo_url = os.environ.get('MONGO_URL')
            db_name = os.environ.get('DB_NAME', 'chess_coach')
            client = AsyncIOMotorClient(mongo_url)
            self.db = client[db_name]
        else:
            self.db = db
        
        self.collection = self.db['player_fingerprints']
    
    async def get_fingerprint(self, user_id: str) -> MistakeFingerprint:
        """
        Get user's mistake fingerprint from database.
        Creates a new one if it doesn't exist.
        
        Args:
            user_id: User identifier
            
        Returns:
            MistakeFingerprint object
        """
        try:
            doc = await self.collection.find_one({"user_id": user_id})
            
            if doc:
                return MistakeFingerprint(
                    user_id=doc["user_id"],
                    tactical=doc.get("tactical", {}),
                    strategic=doc.get("strategic", {}),
                    phase=doc.get("phase", {}),
                    behavioral=doc.get("behavioral", {}),
                    total_mistakes=doc.get("total_mistakes", 0),
                    games_analyzed=doc.get("games_analyzed", 0),
                    last_updated=doc.get("last_updated")
                )
            else:
                # Create new fingerprint
                return MistakeFingerprint(user_id=user_id)
        
        except Exception as e:
            logger.error(f"Error loading fingerprint for {user_id}: {e}")
            return MistakeFingerprint(user_id=user_id)
    
    async def update_fingerprint(
        self,
        user_id: str,
        pattern_type: str,
        category: str,
        update_decay: bool = True
    ) -> bool:
        """
        Record a new mistake occurrence and update the fingerprint.
        
        Args:
            user_id: User identifier
            pattern_type: Pattern name (e.g., "MISSED_FORK")
            category: Category ("TACTICAL", "STRATEGIC", "BEHAVIORAL")
            update_decay: Whether to update decay scores for all patterns
            
        Returns:
            True if successful
        """
        try:
            fingerprint = await self.get_fingerprint(user_id)
            
            # Record the mistake
            fingerprint.record_mistake(pattern_type, category)
            
            # Update decay scores if requested
            if update_decay:
                self._update_decay_scores(fingerprint)
            
            # Save to database
            await self._save_fingerprint(fingerprint)
            
            logger.info(f"Updated fingerprint for {user_id}: {pattern_type} ({category})")
            return True
        
        except Exception as e:
            logger.error(f"Error updating fingerprint for {user_id}: {e}")
            return False
    
    async def increment_games_analyzed(self, user_id: str) -> bool:
        """
        Increment the games_analyzed counter.
        Call this after each game analysis.
        """
        try:
            result = await self.collection.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"games_analyzed": 1},
                    "$set": {"last_updated": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error incrementing games_analyzed for {user_id}: {e}")
            return False
    
    async def get_pattern_stats(
        self,
        user_id: str,
        pattern_type: str,
        category: str
    ) -> Dict[str, Any]:
        """
        Get statistics for a specific pattern.
        
        Returns:
            Dict with: count, last_seen, decay_score, relevance_score
        """
        try:
            fingerprint = await self.get_fingerprint(user_id)
            
            source = {
                MistakeCategory.TACTICAL.value: fingerprint.tactical,
                MistakeCategory.STRATEGIC.value: fingerprint.strategic,
                MistakeCategory.BEHAVIORAL.value: fingerprint.behavioral
            }.get(category, {})
            
            pattern_data = source.get(pattern_type, {
                "count": 0,
                "last_seen": None,
                "decay_score": 0.0
            })
            
            relevance = fingerprint.get_relevance_score(pattern_type, category)
            
            return {
                "count": pattern_data.get("count", 0),
                "last_seen": pattern_data.get("last_seen"),
                "decay_score": pattern_data.get("decay_score", 0.0),
                "relevance_score": relevance
            }
        
        except Exception as e:
            logger.error(f"Error getting pattern stats: {e}")
            return {
                "count": 0,
                "last_seen": None,
                "decay_score": 0.0,
                "relevance_score": 0.0
            }
    
    async def get_top_weaknesses(
        self,
        user_id: str,
        limit: int = 5
    ) -> list[Dict[str, Any]]:
        """
        Get user's top weaknesses sorted by relevance score.
        
        Returns:
            List of dicts with: pattern_type, category, count, relevance_score
        """
        try:
            fingerprint = await self.get_fingerprint(user_id)
            
            weaknesses = []
            
            # Collect all patterns
            for category_name, patterns in [
                (MistakeCategory.TACTICAL.value, fingerprint.tactical),
                (MistakeCategory.STRATEGIC.value, fingerprint.strategic),
                (MistakeCategory.BEHAVIORAL.value, fingerprint.behavioral)
            ]:
                for pattern_type, data in patterns.items():
                    relevance = fingerprint.get_relevance_score(pattern_type, category_name)
                    weaknesses.append({
                        "pattern_type": pattern_type,
                        "category": category_name,
                        "count": data.get("count", 0),
                        "last_seen": data.get("last_seen"),
                        "decay_score": data.get("decay_score", 0.0),
                        "relevance_score": relevance
                    })
            
            # Sort by relevance and return top N
            weaknesses.sort(key=lambda x: x["relevance_score"], reverse=True)
            return weaknesses[:limit]
        
        except Exception as e:
            logger.error(f"Error getting top weaknesses: {e}")
            return []
    
    async def _save_fingerprint(self, fingerprint: MistakeFingerprint) -> bool:
        """Save fingerprint to database."""
        try:
            doc = {
                "user_id": fingerprint.user_id,
                "tactical": fingerprint.tactical,
                "strategic": fingerprint.strategic,
                "phase": fingerprint.phase,
                "behavioral": fingerprint.behavioral,
                "total_mistakes": fingerprint.total_mistakes,
                "games_analyzed": fingerprint.games_analyzed,
                "last_updated": fingerprint.last_updated
            }
            
            result = await self.collection.replace_one(
                {"user_id": fingerprint.user_id},
                doc,
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
        
        except Exception as e:
            logger.error(f"Error saving fingerprint: {e}")
            return False
    
    def _update_decay_scores(self, fingerprint: MistakeFingerprint):
        """
        Update decay scores for all patterns based on time elapsed.
        
        Decay formula: 0.9 ^ days_since_last_seen
        """
        now = datetime.now(timezone.utc)
        
        for patterns in [fingerprint.tactical, fingerprint.strategic, fingerprint.behavioral]:
            for pattern_type, data in patterns.items():
                last_seen_str = data.get("last_seen")
                
                if not last_seen_str:
                    continue
                
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    if last_seen.tzinfo is None:
                        last_seen = last_seen.replace(tzinfo=timezone.utc)
                    
                    days_elapsed = (now - last_seen).days
                    
                    # Apply exponential decay: 0.9 ^ days
                    decay_score = 0.9 ** days_elapsed
                    data["decay_score"] = round(decay_score, 4)
                
                except Exception as e:
                    logger.warning(f"Error calculating decay for {pattern_type}: {e}")
                    data["decay_score"] = 0.5  # Default to moderate decay


# Global service instance
_fingerprint_service = None


def get_fingerprint_service(db=None) -> FingerprintService:
    """
    Get or create the global fingerprint service instance.
    
    Args:
        db: Optional database instance
        
    Returns:
        FingerprintService instance
    """
    global _fingerprint_service
    
    if _fingerprint_service is None:
        _fingerprint_service = FingerprintService(db)
    
    return _fingerprint_service
