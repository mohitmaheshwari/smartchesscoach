#!/usr/bin/env python3
"""
Analyze the latest 20 feedback items from the admin queue.

This script:
1. Connects to MongoDB
2. Fetches the latest 20 feedback items (move_feedback collection)
3. For each one, identifies the issue and suggests a fix

Run: python3 scripts/analyze_feedback.py
"""

import asyncio
import json
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime

async def analyze_feedback_batch():
    """Fetch and analyze latest 20 feedbacks"""
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    db = client["chess_coach"]

    print("Fetching latest 20 feedbacks...")
    feedbacks = []
    async for fb in db.move_feedback.find({}, {"_id": 0}).sort("created_at", -1).limit(20):
        feedbacks.append(fb)

    print(f"\n{'='*120}")
    print(f"FEEDBACK ANALYSIS REPORT — Latest {len(feedbacks)} Items")
    print(f"{'='*120}\n")

    for i, fb in enumerate(feedbacks, 1):
        feedback_id = fb.get("feedback_id", "unknown")
        user_id = fb.get("user_id", "unknown")
        source = fb.get("source", "unknown")  # 'pwc' | 'review' | 'training'
        status = fb.get("status", "pending")
        game_id = fb.get("game_id", "unknown")
        move_number = fb.get("move_number", 0)
        move_san = fb.get("move_san", "unknown")
        fen = fb.get("fen", "")
        user_note = fb.get("user_note", "")
        coaching_text = fb.get("coaching_text", "")
        suggested_caption = fb.get("suggested_caption")
        is_authoring = fb.get("is_authoring_submission", False)
        created_at = fb.get("created_at", "unknown")
        rule_name = fb.get("rule_name")
        inaccuracy_reason = fb.get("inaccuracy_reason")

        # Diagnostics
        diag = fb.get("diagnostics", {})
        severity = diag.get("severity")  # 'wrong_move' | 'misleading' | 'incomplete' | 'terse'
        cp_loss = diag.get("cp_loss", 0)
        best_move = diag.get("best_move", "unknown")
        eval_before = diag.get("eval_before")
        eval_after = diag.get("eval_after")
        phase = diag.get("phase")  # 'opening' | 'middlegame' | 'endgame'

        print(f"\n{'─'*120}")
        print(f"FEEDBACK #{i:2d} | ID: {feedback_id}")
        print(f"{'─'*120}")
        print(f"Source:  {source:15} | Status: {status:12} | User: {user_id}")
        print(f"Game:    {game_id:15} | Move #{move_number:2d} ({move_san})")
        print(f"Created: {created_at}")
        print(f"\nCoaching received: {coaching_text[:100]}..." if len(coaching_text) > 100 else f"\nCoaching received: {coaching_text}")

        # Severity analysis
        print(f"\n📊 ISSUE CLASSIFICATION:")
        print(f"  Severity:  {severity}")
        if rule_name:
            print(f"  Rule hit:  {rule_name}")
        if inaccuracy_reason:
            print(f"  Why wrong: {inaccuracy_reason}")

        # Diagnostic data
        print(f"\n🔍 DIAGNOSTIC DATA:")
        print(f"  CP loss:      {cp_loss:+.0f} cp (centipawns)")
        print(f"  Best move:    {best_move}")
        print(f"  Phase:        {phase}")
        print(f"  Eval before:  {eval_before}")
        print(f"  Eval after:   {eval_after}")

        # User feedback
        if user_note:
            print(f"\n💬 USER NOTE: {user_note}")

        # Authoring submission
        if is_authoring and suggested_caption:
            print(f"\n✍️  AUTHORING SUBMISSION:")
            print(f"  Suggested caption: {suggested_caption}")

        # Issue summary
        print(f"\n🎯 ISSUE SUMMARY:")
        if severity == "wrong_move":
            print(f"  → Coaching suggested the WRONG move ({move_san} was played, {best_move} was better)")
            print(f"  → User lost ~{abs(cp_loss)} centipawns due to this coaching error")
        elif severity == "misleading":
            print(f"  → Coaching explanation was MISLEADING or confusing")
            print(f"  → The move {move_san} might be okay, but the reasoning was off")
        elif severity == "incomplete":
            print(f"  → Coaching explanation was INCOMPLETE (missing key details)")
            print(f"  → User needed more depth to understand the position")
        elif severity == "terse":
            print(f"  → Coaching was TOO TERSE / not teaching-focused")
            print(f"  → User wanted more explanation, not just 'move X is better'")
        else:
            print(f"  → Unknown severity: {severity}")

        # Actionable recommendation
        if is_authoring:
            print(f"\n✅ ACTION: Update caption template with suggested text")
        else:
            print(f"\n✅ ACTION: Investigate why rule '{rule_name}' fired with wrong logic")

asyncio.run(analyze_feedback_batch())
