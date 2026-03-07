"""
Migration Script: learned_rules → smart_patterns
=================================================

This script migrates useful patterns from the legacy learned_rules collection
to the active smart_patterns collection, then deprecates learned_rules.

Run once to complete the migration.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
import uuid


async def migrate_learned_rules():
    """Migrate learned_rules to smart_patterns"""
    
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client['test_database']
    
    print("=" * 60)
    print("LEARNED_RULES → SMART_PATTERNS MIGRATION")
    print("=" * 60)
    
    # Get all learned_rules
    learned_rules = await db.learned_rules.find({}).to_list(100)
    print(f"\nFound {len(learned_rules)} learned_rules to process")
    
    # Get existing smart_patterns to avoid duplicates
    existing_patterns = await db.smart_patterns.find({}).to_list(100)
    existing_triggers = set()
    for p in existing_patterns:
        # Create a fingerprint based on pattern type or explanation
        fingerprint = p.get('pattern_type', '') + p.get('explanation_template', '')[:50]
        existing_triggers.add(fingerprint)
    
    print(f"Found {len(existing_patterns)} existing smart_patterns")
    
    migrated = 0
    skipped = 0
    
    for rule in learned_rules:
        rule_id = rule.get('rule_id', 'unknown')
        pattern_name = rule.get('pattern', '')
        pattern_desc = rule.get('pattern_description', '')
        status = rule.get('status', 'unknown')
        
        print(f"\nProcessing: {rule_id} - {pattern_name}")
        
        # Skip if not active
        if status != 'active':
            print(f"  ⏭ Skipping (status: {status})")
            skipped += 1
            continue
        
        # Create fingerprint
        fingerprint = pattern_name + pattern_desc[:50]
        
        # Check if similar already exists
        if fingerprint in existing_triggers:
            print(f"  ⏭ Similar pattern already exists")
            skipped += 1
            continue
        
        # Map learned_rules pattern to smart_pattern format
        pattern_type_map = {
            'WALKED_INTO_FORK': 'fork_walked_into',
            'CONTROL': 'control_loss',
            'DEFENSIVE_MOVE': 'defensive_resource',
            'KING_SAFETY': 'king_safety',
            'PAWN_STRUCTURE': 'pawn_structure',
            'PIECE_ACTIVITY': 'piece_activity',
            'ATTACK': 'attack_pattern',
            'TACTICAL': 'tactical_pattern',
            'ENDGAME': 'endgame_technique',
        }
        
        pattern_type = pattern_type_map.get(pattern_name, pattern_name.lower().replace(' ', '_'))
        
        # Create smart_pattern from learned_rule
        new_pattern = {
            "pattern_id": f"migrated_{uuid.uuid4().hex[:10]}",
            "rule_id": f"smart_migrated_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{migrated}",
            "source": "learned_rules_migration",
            "source_rule_id": rule_id,
            "pattern_type": pattern_type,
            "pattern_name": pattern_name,
            "pattern_description": pattern_desc,
            "detection_signals": rule.get('detection_signals', []),
            "explanation_template": rule.get('suggested_explanation', pattern_desc),
            "match_criteria": {
                "pattern_keywords": [w.lower() for w in pattern_name.split('_') if len(w) > 2],
                "description_keywords": [w.lower() for w in pattern_desc.split()[:10] if len(w) > 3]
            },
            "match_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "migrated_from": "learned_rules",
            "original_created_at": rule.get('created_at'),
            "status": "active"
        }
        
        # Insert into smart_patterns
        await db.smart_patterns.insert_one(new_pattern)
        print(f"  ✅ Migrated as {pattern_type}")
        migrated += 1
        
        # Mark original as migrated
        await db.learned_rules.update_one(
            {"rule_id": rule_id},
            {"$set": {
                "status": "migrated",
                "migrated_to": new_pattern["pattern_id"],
                "migrated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    # Final stats
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Migrated: {migrated}")
    print(f"Skipped: {skipped}")
    
    # Get final counts
    final_learned = await db.learned_rules.count_documents({"status": "active"})
    final_smart = await db.smart_patterns.count_documents({})
    
    print(f"\nFinal state:")
    print(f"  learned_rules (active): {final_learned}")
    print(f"  smart_patterns (total): {final_smart}")
    
    client.close()
    
    return {
        "migrated": migrated,
        "skipped": skipped,
        "final_smart_patterns": final_smart
    }


if __name__ == "__main__":
    result = asyncio.run(migrate_learned_rules())
    print(f"\nResult: {result}")
