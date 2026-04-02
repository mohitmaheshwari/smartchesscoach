"""
Learning Database Operations

Handles all database operations for the self-learning pattern system:
- Storing user feedback
- Storing learned classification rules
- Tracking rule performance statistics
- Managing rule lifecycle (pending -> active -> deprecated)
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class LearningDB:
    """Database operations for the pattern learning system"""
    
    def __init__(self):
        self.mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        self.db_name = os.environ.get("DB_NAME", "chess_coach")
        self._client = None
        self._db = None
    
    @property
    def client(self):
        if self._client is None:
            self._client = AsyncIOMotorClient(self.mongo_url)
        return self._client
    
    @property
    def db(self):
        if self._db is None:
            self._db = self.client[self.db_name]
        return self._db
    
    # ==================== FEEDBACK OPERATIONS ====================
    
    async def store_feedback(self, feedback: Dict) -> str:
        """Store user feedback on a coach explanation"""
        feedback["created_at"] = datetime.now(timezone.utc)
        feedback["status"] = "pending"  # pending -> processed -> applied
        
        result = await self.db.pattern_feedback.insert_one(feedback)
        return str(result.inserted_id)
    
    async def get_pending_feedback(self, limit: int = 50) -> List[Dict]:
        """Get unprocessed feedback for the pattern learner"""
        cursor = self.db.pattern_feedback.find(
            {"status": "pending"},
            {"_id": 0}
        ).sort("created_at", 1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def mark_feedback_processed(self, feedback_id: str, rule_id: Optional[str] = None):
        """Mark feedback as processed, optionally linking to generated rule"""
        await self.db.pattern_feedback.update_one(
            {"feedback_id": feedback_id},
            {
                "$set": {
                    "status": "processed",
                    "processed_at": datetime.now(timezone.utc),
                    "generated_rule_id": rule_id
                }
            }
        )
    
    async def get_feedback_stats(self) -> Dict:
        """Get statistics about collected feedback"""
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        cursor = self.db.pattern_feedback.aggregate(pipeline)
        results = await cursor.to_list(length=100)
        
        stats = {"pending": 0, "processed": 0, "applied": 0, "total": 0}
        for r in results:
            stats[r["_id"]] = r["count"]
            stats["total"] += r["count"]
        
        return stats
    
    # ==================== LEARNED RULES OPERATIONS ====================
    
    async def store_rule(self, rule: Dict) -> str:
        """Store a newly learned classification rule"""
        rule["created_at"] = datetime.now(timezone.utc)
        rule["updated_at"] = datetime.now(timezone.utc)
        
        # Initialize performance stats
        if "stats" not in rule:
            rule["stats"] = {
                "times_triggered": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "accuracy_rate": 1.0
            }
        
        result = await self.db.learned_rules.insert_one(rule)
        return str(result.inserted_id)
    
    async def get_active_rules(self) -> List[Dict]:
        """Get all active learned rules for classification from both collections"""
        # First get from learned_rules (legacy)
        cursor = self.db.learned_rules.find(
            {"status": "active"},
            {"_id": 0}
        ).sort("priority", -1)
        learned = await cursor.to_list(length=500)
        
        # Also get from smart_patterns (new system)
        smart_cursor = self.db.smart_patterns.find(
            {"status": "active"},
            {"_id": 0}
        )
        smart = await smart_cursor.to_list(length=500)
        
        # Combine both, with smart_patterns taking priority
        combined = smart + learned
        return combined
    
    async def get_rule_by_id(self, rule_id: str) -> Optional[Dict]:
        """Get a specific rule by ID"""
        return await self.db.learned_rules.find_one(
            {"rule_id": rule_id},
            {"_id": 0}
        )
    
    async def get_rules_by_pattern(self, pattern: str) -> List[Dict]:
        """Get all rules for a specific tactical pattern"""
        cursor = self.db.learned_rules.find(
            {"pattern": pattern, "status": "active"},
            {"_id": 0}
        )
        return await cursor.to_list(length=100)
    
    async def update_rule_status(self, rule_id: str, status: str, reason: str = None):
        """Update rule status (pending_review -> active -> deprecated)"""
        update = {
            "status": status,
            "updated_at": datetime.now(timezone.utc)
        }
        if reason:
            update["status_reason"] = reason
        
        await self.db.learned_rules.update_one(
            {"rule_id": rule_id},
            {"$set": update}
        )
    
    async def increment_rule_trigger(self, rule_id: str, was_correct: bool):
        """Track when a rule is triggered and whether it was correct"""
        inc_update = {"stats.times_triggered": 1}
        if was_correct:
            inc_update["stats.positive_feedback"] = 1
        else:
            inc_update["stats.negative_feedback"] = 1
        
        await self.db.learned_rules.update_one(
            {"rule_id": rule_id},
            {"$inc": inc_update}
        )
        
        # Recalculate accuracy rate
        rule = await self.get_rule_by_id(rule_id)
        if rule and rule.get("stats", {}).get("times_triggered", 0) > 0:
            stats = rule["stats"]
            accuracy = stats.get("positive_feedback", 0) / stats["times_triggered"]
            await self.db.learned_rules.update_one(
                {"rule_id": rule_id},
                {"$set": {"stats.accuracy_rate": accuracy}}
            )
    
    async def get_low_accuracy_rules(self, threshold: float = 0.7) -> List[Dict]:
        """Get rules with accuracy below threshold for review"""
        cursor = self.db.learned_rules.find(
            {
                "status": "active",
                "stats.times_triggered": {"$gte": 5},  # At least 5 uses
                "stats.accuracy_rate": {"$lt": threshold}
            },
            {"_id": 0}
        )
        return await cursor.to_list(length=100)
    
    async def get_rules_stats(self) -> Dict:
        """Get overall statistics about learned rules from both collections"""
        # Stats from learned_rules (legacy)
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "total_triggers": {"$sum": "$stats.times_triggered"},
                    "avg_accuracy": {"$avg": "$stats.accuracy_rate"}
                }
            }
        ]
        cursor = self.db.learned_rules.aggregate(pipeline)
        learned_results = await cursor.to_list(length=100)
        
        # Stats from smart_patterns (new)
        smart_cursor = self.db.smart_patterns.aggregate(pipeline)
        smart_results = await smart_cursor.to_list(length=100)
        
        stats = {
            "by_status": {},
            "total_rules": 0,
            "total_triggers": 0,
            "smart_patterns_total": 0,
            "learned_rules_total": 0
        }
        
        # Process learned_rules
        for r in learned_results:
            status = f"learned_{r['_id']}"
            stats["by_status"][status] = {
                "count": r["count"],
                "triggers": r["total_triggers"],
                "avg_accuracy": r.get("avg_accuracy", 0)
            }
            stats["learned_rules_total"] += r["count"]
        
        # Process smart_patterns
        for r in smart_results:
            status = f"smart_{r['_id']}"
            stats["by_status"][status] = {
                "count": r["count"],
                "triggers": r["total_triggers"] or 0,
                "avg_accuracy": r.get("avg_accuracy", 0) or 0
            }
            stats["smart_patterns_total"] += r["count"]
        
        stats["total_rules"] = stats["smart_patterns_total"] + stats["learned_rules_total"]
        
        return stats
    
    # ==================== PATTERN SIGNATURE OPERATIONS ====================
    
    async def store_pattern_signature(self, signature: Dict) -> str:
        """Store a tactical pattern signature for similarity matching"""
        signature["created_at"] = datetime.now(timezone.utc)
        result = await self.db.pattern_signatures.insert_one(signature)
        return str(result.inserted_id)
    
    async def find_similar_signatures(self, signature: Dict, threshold: float = 0.8) -> List[Dict]:
        """Find similar pattern signatures (for cross-position learning)"""
        # This is a simplified version - in production, you'd use vector similarity
        # For now, we match on key tactical indicators
        query = {
            "tactical_motif": signature.get("tactical_motif"),
            "piece_types_involved": {"$all": signature.get("piece_types_involved", [])},
        }
        
        cursor = self.db.pattern_signatures.find(query, {"_id": 0}).limit(20)
        return await cursor.to_list(length=20)
    
    # ==================== CORRECTION CACHE ====================
    
    async def store_correction(self, correction: Dict) -> str:
        """Store a verified correction for future reference"""
        correction["created_at"] = datetime.now(timezone.utc)
        correction["use_count"] = 0
        
        result = await self.db.verified_corrections.insert_one(correction)
        return str(result.inserted_id)
    
    async def find_correction(self, pattern_signature: Dict) -> Optional[Dict]:
        """Find a verified correction for a similar pattern"""
        # Match on tactical motif and key indicators
        query = {
            "tactical_motif": pattern_signature.get("tactical_motif"),
            "attacker_piece": pattern_signature.get("attacker_piece"),
            "is_sequential": pattern_signature.get("is_sequential", False)
        }
        
        correction = await self.db.verified_corrections.find_one(query, {"_id": 0})
        
        if correction:
            # Increment use count
            await self.db.verified_corrections.update_one(
                {"correction_id": correction.get("correction_id")},
                {"$inc": {"use_count": 1}}
            )
        
        return correction
    
    async def get_correction_stats(self) -> Dict:
        """Get statistics about verified corrections"""
        total = await self.db.verified_corrections.count_documents({})
        pipeline = [
            {
                "$group": {
                    "_id": "$tactical_motif",
                    "count": {"$sum": 1},
                    "total_uses": {"$sum": "$use_count"}
                }
            }
        ]
        cursor = self.db.verified_corrections.aggregate(pipeline)
        by_motif = await cursor.to_list(length=100)
        
        return {
            "total_corrections": total,
            "by_motif": {r["_id"]: {"count": r["count"], "uses": r["total_uses"]} for r in by_motif}
        }
