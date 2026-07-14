# Coaching Pattern Detectors — Complete Launch Scope

## 0. Existing Surfaces Audit

**Single launch: EXTEND motif system + WIRE phase transitions + BUILD coordination/prophylaxis/opening detectors**

All five patterns ship together. No phased rollout. Complete testing before launch.

### Found:
1. **Motif Profile System** (exists, fork audited)
   - `backend/services/motif_profile_service.py` — detects fork/pin/skewer/discovered/loose
   - `backend/routes/player.py` — `/api/motif-profile` route
   - `player_profiles` collection stores motif strength/weakness
   - Status: Fork complete, pin/skewer in backlog, discovered/loose added 2026-07-07
   - UI: Route exists but not wired to Lab/HomePage coaching surfaces

2. **Phase Detection** (exists, not surfaced)
   - `analysis/intent_recognition_service.py` — detects opening/middlegame/endgame per move
   - Stored in game_analyses but never surfaces to coaching
   - No user-facing surface

3. **Piece Coordination** (scattered, P2)
   - Hardcoded detections in analysis_worker.py
   - No persistent tracking

4. **Prophylaxis** (scattered, P2)
   - coaching_classifier_service.py checks exist
   - Not surfaced to coaching

5. **Opening Understanding** (missing, P2)
   - No detector exists yet

### Overlap Analysis:
- Motif system is the home for fork/pin/skewer — no duplication. Completing it = extending existing.
- Phase detection exists but is dark data — wiring to coaching = new integration, not new detector.
- Coordination/Prophylaxis/Opening = new detectors (P2).

### Decision Path:
**Single Launch: EXTEND motif system + WIRE phase transitions + BUILD all new detectors (coordination, prophylaxis, opening)**

Everything ships together. Rigorous testing before launch. 100% confidence.

---

## 1. What It Is

ChessGuru reveals coaching blindspots users can't see on their own. Currently, the system detects what went WRONG in individual moves (cognitive_gap: piece_safety, king_safety, etc.). This feature makes the system detect what PATTERNS users are blind to (motif weaknesses like fork/pin/skewer) and what STRATEGIC PHASE they struggle with (why they win the opening but lose the middlegame).

Instead of "You made a mistake on move 15," users hear: "You have a fork weakness — 47 times. Here's why. Here's how to fix it." And: "You're solid at opening, but your middlegame transitions fail. That's a different kind of coaching."

This is the path from 600-rated "I keep hanging pieces" to 1200-rated "My strategy breaks down under pressure."

---

## 2. What the User Sees

**Lab page — Coaching Pattern Cards** (below Coach's Pick, in order):

```
┌─────────────────────────────────────┐
│ 🎯 Motif Weakness: Fork              │
│ You got forked 47 times.             │
│ 41 in games, 12 times after training │
│ (1 per 5 games now — improving)      │
│ [Drill fork puzzles →]               │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 📊 Phase Weakness: Middlegame        │
│ Opening: 82% | Middlegame: 61%       │
│ You transition hard → positions slip │
│ [Practice middlegame transitions →]  │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🔄 Coordination Gap                  │
│ Your rooks rarely support each other │
│ Drill: Positions where rooks matter  │
│ [Practice coordination →]            │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🛡️ Prophylaxis Gap                   │
│ You react instead of prevent threats │
│ Drill: Anticipatory defense puzzles  │
│ [Practice prophylaxis →]             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 📖 Opening Understanding             │
│ You deviate from Sicilian (41 times) │
│ Is it sound? Analyze your deviation  │
│ [Review your opening choices →]      │
└─────────────────────────────────────┘
```

**Home Dashboard — Coaching Priority**:
```
Your coaching priorities:
1. Fork weakness (most impactful, immediate drills)
2. Middlegame transitions (strategic shift needed)
3. Rook coordination (piece planning)
```

**Play with Coach — Integrated Coaching**:
- Fork threat detected → coach warns
- Phase transition (opening→middlegame, move ~12-15) → coach explains principles shift
- Passive rook move → coach notes coordination gap
- Prophylactic move ignored → coach teaches "prevent, don't react"
- Opening deviation detected → coach notes ("You're exploring off-theory")

---

## 3. In Scope (Complete Launch)

### Motif System (fork/pin/skewer/discovered/loose):
- ✅ Fork detection fully audited and shipped (2026-06-21)
- ✅ Pin detection audited (87% accuracy per motif_profile_service.py)
- ✅ Skewer detection audited (with value-gap gate)
- ✅ Discovered attack detection (2026-07-07, 4.59% probe rate)
- ✅ Loose piece detection (2026-07-07, 1.83% defensive rate)
- ✅ User motif weakness cards surfaced in Lab (all 5 motifs)
- ✅ Motif-filtered puzzle training (drill from own games)
- ✅ Progress tracking per motif (recovery %)
- ✅ Rating-aware thresholds per motif per RATING_BANDS
- ✅ Backend API: GET /api/motif-profile
- ✅ Tests: Motif detection regression suite (all 5 motifs)

### Phase Transitions (Wire existing detector):
- ✅ Surface phase accuracy (opening/middlegame/endgame %)
- ✅ Alert when phase accuracy dips below threshold
- ✅ Coach commentary on phase transitions during play
- ✅ Track weak phase per user
- ✅ Phase-aware training recommendations
- ✅ Backend API: GET /api/player/phase-analysis
- ✅ Frontend: Phase weakness card in Lab
- ✅ Tests: Phase detection and surfacing

### Piece Coordination (NEW detector):
- ✅ Detect passive rook/bishop/knight coordination patterns
- ✅ Surface as "Coordination Gap" card in Lab
- ✅ Coordination-filtered puzzle training
- ✅ Coach notes during play ("Your rooks should support each other")
- ✅ Rating-aware thresholds (1400+ emphasizes coordination more)
- ✅ Backend API: GET /api/player/coordination-analysis
- ✅ Tests: Coordination detection accuracy on gold corpus

### Prophylaxis (NEW detector):
- ✅ Detect reactive vs proactive thinking patterns
- ✅ Surface as "Prophylaxis Gap" card in Lab
- ✅ Prophylaxis-focused puzzle drills (preventive defense)
- ✅ Coach notes during play ("Prevent this threat, don't wait to react")
- ✅ Rating-aware thresholds (1300+ should show prophylactic thinking)
- ✅ Backend API: GET /api/player/prophylaxis-analysis
- ✅ Tests: Prophylaxis detection on game corpus

### Opening Understanding (NEW detector):
- ✅ Detect opening deviations (vs played ECO theory)
- ✅ Surface as "Opening Choices" card in Lab
- ✅ Do NOT label deviation as error (needs sound/unsound assessment first)
- ✅ Coach context during play ("You're playing Sicilian but exploring side variation")
- ✅ Rating-aware handling (1100+ players get more opening context)
- ✅ Backend API: GET /api/player/opening-analysis
- ✅ Tests: Opening recognition accuracy + deviation detection

---

## 4. Explicitly Out of Scope (Launch)

- **Motif strength** — Show only weaknesses at launch; strength leaderboard deferred
- **Cross-pattern interactions** — "You get forked AND pinned by same opponent" — research-only for now
- **Motif drilling beyond puzzles** — Games/live positions from motif scenarios deferred to P2
- **Opening sound/unsound assessment** — We detect deviation only; sound/unsound needs stronger validation
- **Prophylaxis leaderboard** — Personal tracking only; no social comparison at launch
- **Phase-specific training plans** — Recommendations only; full phase-based curriculum deferred
- **Realtime pattern alerts via SMS/email** — In-app only at launch

---

## 5. Success Criteria

**Behavior-changing, not vanity. Complete user arc (600→1200) must work:**

1. **Pattern clarity** — Users can articulate ALL their weaknesses:
   - "I have a fork weakness" (motif)
   - "I lose in the middlegame" (phase)
   - "My rooks don't work together" (coordination)
   - "I react instead of prevent" (prophylaxis)
   - "I play off-theory openings" (opening understanding)

2. **Motif improvement** — Fork weakness users show measurable recovery:
   - 600-rated: baseline ~1 fork per 3 games → 1 per 5 games within 2 weeks of drills
   - Measured via fork_mistakes_per_game in player_profiles

3. **Phase improvement** — Users recognize and improve their weak phase:
   - Middlegame-weak user sees 5%+ accuracy improvement within 3 weeks
   - Phase coaching CTR >= 35%

4. **Coordination improvement** — Coordination-weak users show:
   - Piece coordination score improves measurably in new games
   - Coordination puzzle CTR >= 30%

5. **Training conversion** — All patterns trigger training:
   - CTR on pattern-specific drills >= 35% across all 5 patterns
   - Puzzle attempt rate >= 3 per week per active pattern

6. **Retention + Rating progression** — The real signal:
   - 70% of users return within 7 days
   - Users who engage with 3+ patterns show +100 rating gain within 8 weeks
   - Users rate feature 4.5+/5 on feedback (clarity and usefulness)

7. **No false positives** — Detectors accurate enough to be trustworthy:
   - Motif detections >= 85% precision (users trust "you have a fork weakness")
   - Phase transitions >= 80% precision
   - Coordination/Prophylaxis >= 75% precision (new detectors, conservative threshold)

---

## 6. Open Questions

**Q1: Card ordering on Lab page**
- Order: Motif → Phase → Coordination → Prophylaxis → Opening? Or by severity?
- Why unresolved: affects user focus; needs Mohit's UX judgment on what matters most
- Unblocking step: Mockup review with Mohit + optionally A/B test two orderings

**Q2: Coordination detection scope**
- Do we detect just rooks, or all pieces (bishops/knights)? "Passive piece" is vague.
- Why unresolved: detection complexity vs coaching clarity tradeoff
- Unblocking step: Run `/lock-via-data` on coordination pattern distribution; set scope based on what's detectable with 75%+ confidence

**Q3: Prophylaxis detection accuracy**
- "React vs prevent" is hard to detect reliably. What's our confidence threshold before shipping?
- Why unresolved: prophylaxis detection may be 50-60% accurate on first pass
- Unblocking step: Build detector, audit on 100 games, set GATE accordingly (may suppress low-confidence detections)

**Q4: Opening deviation handling**
- "You deviated from Sicilian" — do we need to validate sound/unsound, or just note the deviation?
- Why unresolved: labeling deviation without soundness judgment could confuse users
- Unblocking step: Ship deviation detection only; sound/unsound assessment deferred unless we can verify it reliably

**Q5: Language accessibility for 600-rated**
- "Prophylaxis", "coordination", "phase transition" — are these terms clear to 600-rated players? Need simpler language?
- Why unresolved: jargon risk; 600-rated audience may not know chess terminology
- Unblocking step: User testing with 2-3 players from 600-900 range; adjust terminology if needed

**Q6: Coach commentary tone across all 5 patterns**
- Should coach voice be consistent across motif/phase/coordination coaching? Risk of repetition?
- Why unresolved: coaching voice design needed that works for 5 different pattern types
- Unblocking step: Mohit guidance on coaching voice + sample commentary review

---

## 7. Pre-Code Requirements

**Hard gates (ALL must be true before first line of code):**

- ✅ **Existing detectors audited**: Motif (fork/pin/skewer/discovered/loose) + Phase detection verified
- ✅ **New detectors designed**: Coordination, Prophylaxis, Opening — detection logic documented
- ✅ **Database schema ready**: Player_profiles supports all 5 patterns (already exists; verify fields)
- ✅ **Thresholds locked via data**: Run `/lock-via-data` histograms for:
  - Motif thresholds per rating band (if refinement needed beyond existing SOUND_CP/BLUNDER_CP)
  - Phase accuracy gates (when to alert user about weak phase)
  - Coordination detection confidence (at what % do we surface?)
  - Prophylaxis detection confidence (risky; may need conservative gate)
  - Opening deviation frequency (when is it significant enough to surface?)
- ✅ **Lab page mockup approved**: All 5 pattern cards, ordering, and CTAs reviewed by Mohit
- ✅ **Coach commentary tone approved**: Sample captions for all 5 patterns reviewed (avoid jargon for 600-rated)
- ✅ **One source of truth verified**: No parallel coaching systems; all patterns route through central layer
- ✅ **Testing plan documented**: How we'll audit each detector on gold corpus before launch
- ✅ **Accessibility check**: Language tested with 600-900 rated players (or Mohit confirms it's clear)
- ✅ **Mohit explicitly signs off**: This scope document locked before proceeding

---

## Timeline Estimate

**Complete launch (all 5 patterns together):**

- **Motif system wiring** (fork/pin/skewer/discovered/loose already detected): 2-3 days
  - Surface cards, puzzles, progress tracking
  - Frontend routing + API exposure

- **Phase transitions wiring** (already detected): 2-3 days
  - Surface card, alerts, coach commentary
  - Phase-aware recommendations

- **Coordination detector** (NEW): 3-4 days
  - Detection logic + testing
  - Surfacing + coach integration

- **Prophylaxis detector** (NEW): 3-4 days
  - Detection logic (risky; may need conservative gating)
  - Testing + accuracy audit
  - Surfacing + coach integration

- **Opening Understanding detector** (NEW): 2-3 days
  - Deviation detection + ECO mapping
  - Testing + frontend

- **Lab UI + Layout**: 2-3 days
  - All 5 pattern cards, ordering, CTAs

- **Coach Commentary** (all patterns): 2-3 days
  - Unified voice across motif/phase/coordination/prophylaxis/opening
  - PWC integration

- **Rigorous Testing (100% confidence gate):**
  - Unit tests per detector: 2 days
  - Integration tests (all patterns together): 2 days
  - Gold corpus audit (accuracy verification): 2-3 days
  - User accessibility testing (600-900 rated): 1-2 days
  - Regression testing (no interference with existing coaching): 2 days
  - **Total testing: ~2 weeks**

- **QA + Polish**: 1-2 days

**Grand Total: ~4-5 weeks**

No launch until 100% confidence on:
- Each detector accuracy (gold corpus verified)
- Pattern interactions (no conflicts or double-counting)
- User-facing language (accessible to 600-rated)
- Coach commentary (consistent, clear, actionable)

---

## Testing Requirements (Before Launch)

**100% confidence verification:**

1. **Detector Accuracy Audit** — each detector tested on 100+ gold games:
   - Fork detection: >= 85% precision
   - Pin detection: >= 85% precision
   - Skewer detection: >= 85% precision
   - Phase transitions: >= 80% precision
   - Coordination: >= 75% precision (conservative for new detector)
   - Prophylaxis: >= 70% precision (risky detector; use with gate)
   - Opening deviation: >= 80% precision

2. **User Language Audit** — test language clarity with 2-3 players in 600-900 range:
   - Can they understand "You have a fork weakness"? (goal: yes, without explanation)
   - Can they understand "Your middlegame accuracy is lower"? (goal: yes)
   - Does "Coordination gap" make sense without further context? (may need adjustment)
   - Is "Prophylaxis" jargon too thick? (likely yes; plan alternative: "Defensive thinking" or "Prevention")

3. **Integration Testing** — verify all 5 patterns work together without interference:
   - Motif + Phase don't conflict in same position
   - Coach doesn't spam multiple pattern alerts simultaneously
   - Training recommendations from multiple patterns don't overlap
   - Lab card ordering makes sense and doesn't overwhelm

4. **Regression Testing** — verify no breakage to existing systems:
   - Cognitive_gap system still works independently
   - Play with Coach coaching unchanged (patterns are additive)
   - Lab page performance not degraded by 5 new cards
   - API response times acceptable

---

**Awaiting Mohit signoff before proceeding to `/lock-via-data` (thresholds) and `/audit-pre-code` (pre-code checklist).**

All 5 patterns ship together. No phased rollout. 100% confidence before launch.
