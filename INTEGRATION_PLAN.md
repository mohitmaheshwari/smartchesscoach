"""
CONSOLIDATED FEEDBACK & TEMPLATE SYSTEM
========================================

Merges:
1. EXISTING pattern_learning system (4,827 lines) - self-learning from feedback
2. NEW template system - deterministic explanations without LLM

Architecture:
- Pattern feedback (existing) → learns smart_patterns
- Template feedback (new) → tracks template effectiveness  
- Both feed into improvement loop

NO DUPLICATES - extends existing system.
"""

## INTEGRATION GUIDE

### What Already Exists (DON'T DUPLICATE):
```
/backend/routes/feedback.py (697 lines)
  ↓
POST /coach/pattern-learning/feedback
  - Submit when explanation is wrong
  - Auto-generates corrected explanation
  - Learns new classification rules
  - Returns immediate correction

GET /coach/pattern-learning/stats
  - System learning statistics
  - Rule approval workflow
```

```
/backend/services/pattern_learning/ (4,827 lines total)
  ├── auto_correction_service.py - Main orchestrator
  ├── feedback_collector.py - Collects feedback
  ├── pattern_learner.py - AI learns new rules
  ├── rule_validator.py - Validates rules
  ├── rule_executor.py - Applies learned rules
  ├── smart_pattern_matcher.py - Matches positions
  ├── deep_position_analyzer.py - Position analysis
  └── concrete_feature_extractor.py - Feature extraction

Database Collections:
  - pattern_feedback - User corrections
  - verified_corrections - Approved corrections
  - smart_patterns - Learned patterns
  - learned_rules - Classification rules
```

### What's NEW (Keep This):
```
/backend/services/explanation_templates.py (318 lines)
  - Deterministic templates (NO LLM)
  - Rating-adaptive language
  - Multiple variations per pattern
  - Template selection logic
```

### Integration Points:

#### 1. Add Template Tracking to Existing Feedback
Enhance `/backend/routes/feedback.py`:

```python
@router.post("/feedback")
async def submit_pattern_feedback(request: Dict, user: User):
    # EXISTING: Auto-correction service
    result = await service.submit_feedback_and_correct(...)
    
    # NEW: Also track if this was from a template
    if request.get("template_id"):
        await track_template_performance(
            template_id=request["template_id"],
            was_helpful=False,  # They submitted feedback = not helpful
            user_rating=user.rating
        )
    
    return result
```

#### 2. Add Simple Rating to Existing UI
Don't need new component - extend existing feedback button:

```javascript
// In existing game review UI:
<FeedbackButton 
  onWrong={() => openFeedbackModal()}  // Existing
  onHelpful={() => submitQuickFeedback(true)}  // NEW: Quick thumbs up
  onNotHelpful={() => submitQuickFeedback(false)}  // NEW: Quick thumbs down
/>
```

#### 3. Template Selection Uses Existing Smart Patterns
```python
# In explanation_templates.py
def select_best_template(mistake_type, user_rating, position_fen):
    # NEW: Check if smart_pattern exists for this position
    smart_pattern = await db.smart_patterns.find_one({
        "pattern_type": mistake_type,
        "match_criteria": matches_position(position_fen)
    })
    
    if smart_pattern:
        # Use learned pattern (from existing feedback system)
        return smart_pattern["explanation_template"]
    else:
        # Fall back to base templates
        return base_templates[mistake_type]
```

### Unified Flow:

```
User sees explanation (template or LLM)
  ↓
[Quick Feedback] Was this helpful?
  ├─ ✅ Yes → Track template effectiveness (NEW)
  └─ ❌ No → "What should it say instead?"
      ↓
      EXISTING pattern_learning system:
        - Collects correction
        - Learns smart_pattern
        - Generates rule
        - Applies to future positions
      ↓
      NEW template system:
        - Marks template as low-performing
        - If user suggests better text → queue for coach approval
        - Approved suggestions → new template variation
```

### Database Schema Addition:

```javascript
// Add to EXISTING collections (don't create new ones)

// Extend pattern_feedback with template tracking
pattern_feedback: {
  // ... existing fields ...
  template_id: "fork_beginner_v1",  // NEW
  generation_method: "template" | "llm",  // NEW
  quick_rating: true | false | null  // NEW: thumbs up/down
}

// Extend smart_patterns with template info
smart_patterns: {
  // ... existing fields ...
  template_variation: "Your move walked into...",  // NEW
  template_effectiveness: 0.85,  // NEW: learned from feedback
  last_updated: "2025-01-15"
}
```

### API Additions (extend existing routes):

```python
# In /backend/routes/feedback.py (EXTEND, don't duplicate)

@router.post("/quick-rating")  # NEW endpoint
async def submit_quick_rating(
    template_id: str,
    is_helpful: bool,
    user: User
):
    """Quick thumbs up/down without full feedback form"""
    await update_template_stats(template_id, is_helpful)
    return {"success": True}

@router.get("/template-performance")  # NEW endpoint
async def get_template_performance():
    """See which templates perform well"""
    # Aggregate from existing pattern_feedback collection
    # Filter by template_id, count helpful vs not helpful
    return performance_report
```

### Implementation Steps:

1. ✅ Keep explanation_templates.py (genuinely new)
2. ✅ Delete duplicate feedback files (already done)
3. ⏭️ Add 2 new endpoints to EXISTING /backend/routes/feedback.py
4. ⏭️ Add template_id field to EXISTING feedback submission
5. ⏭️ Create simple thumbs up/down UI (10 lines, not full component)
6. ⏭️ Integrate template selection with smart_patterns

### Result: Best of Both Worlds

**From EXISTING system:**
- ✅ Full self-learning pipeline
- ✅ Auto-correction service
- ✅ Smart pattern matching
- ✅ Cross-user learning
- ✅ Rule validation
- ✅ 4,827 lines of battle-tested code

**From NEW system:**
- ✅ Deterministic templates (no LLM)
- ✅ Rating-adaptive language
- ✅ Multiple variations
- ✅ Template performance tracking
- ✅ Simple quick feedback

**Total:** Unified system with no duplication, builds on what exists.
