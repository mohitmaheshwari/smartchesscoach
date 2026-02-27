# ChessGuru Audit vs Product Spec

## Summary: What You Already Have

| Spec Requirement | Status | What Exists | Gap |
|------------------|--------|-------------|-----|
| **Reflection-first post-game** | ✅ BUILT | `Reflect.jsx` - captures intent, confidence, tags BEFORE showing answer | Minor UX polish |
| **Behavioral memory model** | 🟡 PARTIAL | `cognitive_gap_history` stores gaps. Missing: advice effectiveness tracking | Need to add advice tracking |
| **Coach Home - One hero card** | ✅ BUILT | `CoachHome.jsx` - prioritizes: Fresh Loss > Active Mission > Advice | Clean, not cluttered |
| **Post-loss recovery screen** | ✅ BUILT | `PostLossRecovery.jsx` - emotional headline, one issue, one CTA | Needs more pattern context |
| **Last Game Coach Insight** | ✅ BUILT | `CoachGameReviewCard.jsx` - combines game + coaching | Could add more "recurring pattern" context |
| **One active mission** | ✅ BUILT | Mission system with behavior-linked missions | Working |

---

## What's Aligned with Spec ✅

### 1. Reflection-First Flow (STRONG)
**File:** `Reflect.jsx`

Your reflection engine already:
- Shows position BEFORE revealing the answer
- Captures user's **intent** ("I saw a tactic", "I was attacking", etc.)
- Captures **confidence** level (very sure → guessing)
- Uses **quick tags** for fast input
- Diagnoses cognitive gap and shows it

**This is your core differentiator. Keep it.**

### 2. Coach Home - Focused Layout (GOOD)
**File:** `CoachHome.jsx`

Current priority order:
1. Development Phase Banner (stage context)
2. **Fresh Loss Card** OR **Active Mission** (one hero card)
3. Active Advice (THE one thing)
4. Post-Game Review (only if new)
5. Recommended Drill
6. Quick Actions

**This is NOT dashboard clutter. It's hierarchical.**

### 3. Post-Loss Recovery Screen (EXISTS)
**File:** `PostLossRecovery.jsx`

Current elements:
- Board with critical moment
- Emotional headline ("Let's fix this moment")
- Main issue card
- "Fix this now" CTA
- "See full analysis" secondary

**Matches spec direction. Could add:**
- Pattern context ("This is the 3rd time this week...")
- Reflection chips inline

### 4. Cognitive Gap Storage (FOUNDATION EXISTS)
**Collection:** `cognitive_gap_history`

Currently stores:
- `gap_type` (e.g., "threat_blindness")
- `confidence` (user's feeling)
- `intent` (what user was trying)
- `evidence` (proof from position)
- `created_at` (for trending)

**This IS behavioral memory. It's just not surfaced prominently.**

---

## What's Missing from Spec 🟡

### 1. Advice Effectiveness Tracking
**Spec says:** "Store whether advice worked later"

**Current state:** We give advice but don't track if it helped.

**To add:**
```javascript
// New collection: advice_effectiveness
{
  user_id: "user_123",
  advice_given: "Check opponent threats before attacking",
  given_at: ISODate(),
  gap_type_targeted: "threat_blindness",
  
  // Track outcomes
  games_since_advice: 5,
  gap_occurrences_after: 2,  // Did this gap still happen?
  improvement_detected: true,
  
  // Adapt coaching
  advice_still_relevant: false  // Stop repeating if fixed
}
```

### 2. "This is Recurring" Context in UI
**Spec says:** Surface recurring patterns, not just this mistake

**Current state:** We compute patterns but don't always show "3rd time this week"

**To add:**
- In `PostLossRecovery.jsx`: Add line like "You've had this pattern 3 times recently"
- In `CoachGameReviewCard.jsx`: Add "This is familiar..." prefix when recurring

### 3. Coach Tone Preference Memory
**Spec says:** "Store coach tone preference"

**Current state:** Not tracked

**To add:** Simple preference in player_profiles:
```javascript
coaching_preferences: {
  tone: "direct" | "supportive" | "analytical",
  detail_level: "minimal" | "standard" | "detailed"
}
```

### 4. Weekly Progress Story
**Spec says:** Show as priority screen #7

**Current state:** `Progress.jsx` exists but is more dashboard-like

**To refine:** Make it a narrative story, not a stats page:
- "This week, you played 12 games..."
- "Your threat blindness appeared twice (down from 5 last week)"
- "The advice seems to be working"

---

## What to NOT Change (Already Good)

1. **Don't simplify Coach Home further** - It's already focused
2. **Don't remove the reflection flow** - It's your core IP
3. **Don't remove cognitive gap types** - They power the memory
4. **Don't add chat interface** - Keep it structured

---

## Priority Implementation Order

### Phase 1: Enhance Memory Surfacing (Low effort, High impact)
1. Add "recurring pattern" context to `PostLossRecovery.jsx`
2. Add "this is familiar" to `CoachGameReviewCard.jsx`
3. Surface pattern counts in Home intelligence

### Phase 2: Add Advice Tracking (Medium effort)
1. Create `advice_effectiveness` collection
2. Track advice given and whether gap recurs
3. Use in coaching decisions ("You've been working on X, let's check progress")

### Phase 3: Refine Weekly Progress Story (Medium effort)
1. Convert progress page to narrative format
2. Show trend: "Your X has improved from Y to Z"
3. Show coach memory: "We've been working on threat awareness for 2 weeks"

---

## Copy Direction Check ✅

Current copy in your app:

| Screen | Current Copy | Spec Check |
|--------|--------------|------------|
| PostLossRecovery headline | "Let's fix this moment." | ✅ Good - not "Your accuracy was 58%" |
| Active Advice | "Before every move, ask: What can my opponent do?" | ✅ Good - actionable |
| Coach Game Review | "Clean game. Good discipline." | ✅ Good - coaching voice |
| Development Phase | "Building solid foundations" | ✅ Good - journey language |

**Your copy is already coaching-oriented, not analytics-oriented.**

---

## Conclusion

**You're closer than you think.**

The architecture for "behavioral memory" exists in `cognitive_gap_history`. The reflection-first flow is built. The Coach Home is focused.

**What's missing is surfacing the memory more prominently:**
- "This is the 3rd time" callouts
- "Your pattern is improving" feedback
- Tracking whether advice worked

This is enhancement work, not rebuilding.
