# Phase 1 Implementation - Schema Review Document

## 1. PlayerProfile Schema (`player_profiles` collection)

```javascript
{
  "profile_id": "profile_{user_id}",
  "user_id": "user_abc123",
  "user_name": "John Doe",
  
  // === DYNAMIC LEVEL ESTIMATION ===
  "estimated_level": "beginner" | "intermediate" | "advanced" | "expert",
  "estimated_elo": 1200,  // Integer, dynamically calculated
  
  // === RANKED WEAKNESSES WITH DECAY ===
  "top_weaknesses": [
    {
      "category": "tactical",
      "subcategory": "pin_blindness",
      "occurrence_count": 5,           // Raw count
      "decayed_score": 4.2,            // After time decay applied
      "last_occurrence": "2025-02-03T...",
      "first_occurrence": "2025-01-15T..."
    }
  ],  // Sorted by decayed_score DESC, max 10 items
  
  // === STRENGTHS ===
  "strengths": [
    {
      "category": "tactical",
      "subcategory": "fork_awareness",
      "evidence_count": 3
    }
  ],  // Max 5 items
  
  // === LEARNING PREFERENCES (AI-inferred, user-overridable) ===
  "learning_style": "concise" | "detailed",
  "coaching_tone": "firm" | "encouraging" | "balanced",
  
  // === PERFORMANCE TRACKING ===
  "improvement_trend": "improving" | "stuck" | "regressing",
  "games_analyzed_count": 15,
  "total_blunders": 23,
  "total_mistakes": 45,
  "total_best_moves": 89,
  
  // === TREND CALCULATION WINDOWS ===
  "recent_performance": [  // Last 10 games
    {"game_id": "...", "blunders": 2, "mistakes": 3, "best_moves": 5, "date": "..."}
  ],
  "historical_performance": [  // Games 11-30
    {"game_id": "...", "blunders": 3, "mistakes": 4, "best_moves": 3, "date": "..."}
  ],
  
  // === CHALLENGE MODE FEEDBACK LOOP ===
  "challenges_attempted": 25,
  "challenges_solved": 18,
  "weakness_challenge_success": {
    "tactical:pin_blindness": {"attempts": 10, "successes": 8}
  },
  
  // === TIMESTAMPS ===
  "created_at": "2025-02-01T...",
  "last_updated": "2025-02-03T..."
}
```

---

## 2. Coaching Explanation Contract (Strict JSON Schema)

Every mistake explanation MUST follow this exact structure:

```javascript
{
  "thinking_error": "What mental mistake led to this move (10-200 chars)",
  "why_it_happened": "The root cause - why this thinking occurred (10-200 chars)",
  "what_to_focus_on_next_time": "One actionable thing to focus on (10-150 chars)",
  "one_repeatable_rule": "A simple rule to remember (10-100 chars)"
}
```

### FORBIDDEN in explanations:
- ❌ Move lists or variations (e.g., "1.e4 e5 2.Nf3...")
- ❌ Engine language (e.g., "+0.3 advantage", "eval: -1.2")
- ❌ Computer evaluations or centipawn scores
- ❌ Multiple lessons per mistake - ONE core lesson only
- ❌ Vague advice like "be more careful"

### REQUIRED:
- ✅ Human, conversational language
- ✅ Specific, actionable advice
- ✅ Reference to player's history when relevant
- ✅ Short, speakable sentences

### Example Valid Explanation:
```javascript
{
  "thinking_error": "Focused too much on attacking, missed that the knight was pinned to the queen",
  "why_it_happened": "Tunnel vision - when planning an attack, didn't scan for opponent's tactical threats",
  "what_to_focus_on_next_time": "Before committing to an attack, check: 'Are any of my pieces pinned or vulnerable?'",
  "one_repeatable_rule": "Always scan for pins before moving"
}
```

---

## 3. Deterministic Habit Tracking Logic

### Time Decay Formula
```
decayed_score = occurrence_count × e^(-days_since_last / 30)
```

| Days Since | Decay Factor | 10 occurrences → |
|------------|--------------|------------------|
| 1 day      | 0.967        | 9.67             |
| 7 days     | 0.792        | 7.92             |
| 14 days    | 0.627        | 6.27             |
| 30 days    | 0.368        | 3.68             |
| 60 days    | 0.135        | 1.35             |

### Weakness Promotion/Demotion Rules:
1. **Promotion**: New occurrence → increment count, update last_occurrence, recalculate score
2. **Demotion**: Score naturally decays over time
3. **Resolution**: When challenge success rate > 70% (min 5 attempts):
   - Occurrence count halved
   - Decayed score halved
   - Weakness moves down in ranking

### Predefined Weakness Categories (STRICT - no invention):

```javascript
{
  "tactical": [
    "one_move_blunders",
    "pin_blindness",
    "fork_misses",
    "skewer_blindness",
    "back_rank_weakness",
    "discovered_attack_misses",
    "removal_of_defender_misses"
  ],
  "strategic": [
    "center_control_neglect",
    "poor_piece_activity",
    "lack_of_plan",
    "pawn_structure_damage",
    "weak_square_creation",
    "piece_coordination_issues"
  ],
  "king_safety": [
    "delayed_castling",
    "exposing_own_king",
    "king_walk_blunders",
    "ignoring_king_safety_threats"
  ],
  "opening_principles": [
    "premature_queen_moves",
    "neglecting_development",
    "moving_same_piece_twice",
    "ignoring_center_control",
    "not_castling_early"
  ],
  "endgame_fundamentals": [
    "king_activity_neglect",
    "pawn_race_errors",
    "opposition_misunderstanding",
    "rook_endgame_errors",
    "stalemate_blunders"
  ],
  "psychological": [
    "impulsive_moves",
    "tunnel_vision",
    "hope_chess",
    "time_trouble_blunders",
    "resignation_too_early",
    "overconfidence"
  ]
}
```

---

## 4. API Endpoints Added

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile` | Get player's full coaching profile |
| GET | `/api/profile/weaknesses` | Get top 5 weaknesses with decay |
| GET | `/api/profile/strengths` | Get identified strengths |
| PATCH | `/api/profile/preferences` | Update learning_style, coaching_tone |
| POST | `/api/profile/challenge-result` | Record puzzle result, trigger weakness resolution |
| GET | `/api/weakness-categories` | Get all predefined categories |

---

## 5. Integration Points

### Profile Injection into AI Prompts
The `build_profile_context_for_prompt()` function generates context like:

```
=== PLAYER COACHING PROFILE ===
Player Level: INTERMEDIATE (Est. ELO: 1350)
Trend: 📈 IMPROVING

TOP 3 WEAKNESSES (ranked by frequency with time decay):
  1. Pin Blindness (tactical) - Score: 4.2
  2. Center Control Neglect (strategic) - Score: 3.1
  3. Delayed Castling (king_safety) - Score: 2.8

STRENGTHS:
  - Fork Awareness (tactical)
  - Good Development (opening_principles)

COACHING PREFERENCES:
  - Learning style: CONCISE (keep explanations brief and actionable)
  - Tone: ENCOURAGING

Games Analyzed: 15
Note: Player is IMPROVING - acknowledge their progress!
```

### Challenge Feedback Loop
1. Generate puzzle → Store `target_category`, `target_subcategory`
2. User solves puzzle → POST to `/api/profile/challenge-result`
3. Update `weakness_challenge_success` tracking
4. If success rate > 70% after 5+ attempts → Weakness auto-resolves

---

## Awaiting Your Review

Please confirm:
1. ✅ PlayerProfile schema matches requirements?
2. ✅ Time decay (30-day window) logic is correct?
3. ✅ Explanation JSON schema is strict enough?
4. ✅ Predefined weakness categories are complete?

Once approved, I can proceed to Phase 2 (Challenge Feedback Loop + Progress Summaries).
