---
name: pwc-opening-offer-lockout-bug
description: Play with Coach opening teaching offer locks itself out after the first generic detection (e.g. "King's Pawn Opening") — leaves the user with no path to learn the specific variation (Italian / Ruy Lopez / etc.) once the line narrows. Root cause and fix shape locked 2026-05-19.
metadata:
  type: project
---

**Bug locked 2026-05-19 after Mohit's PWC session b6afdefc.**

The "coach should guide you from the opening, narrow as you play a
variation, teach the idea / trap when you commit to a specific line"
behavior — the heart of the vision — does NOT work today. Concrete
failure mode:

1. Move 1 (e.g. 1.e4): detector identifies the top-level family
   ("kings_pawn"). `check_opening_and_offer_teaching()` runs.
2. Options are built conditionally:
   - `learn_trap` only added if a trap is registered under THIS
     `opening_key` + current moves combination. Top-level
     families ("kings_pawn", "queens_pawn") have no traps —
     traps live under narrower keys (italian_game, kings_gambit,
     vienna, etc.).
   - `learn_main_line` only added if
     `get_available_variations(opening_key)` is non-empty.
     Same problem — variation theory is keyed to narrower
     lines, not the top-level family.
   - `just_play` always added.
3. Result for generic detection: the offer message lands in
   `coach_messages` with `options = [{"just_play"}]` ONLY.
4. The session is immediately marked
   `opening_offer_shown: True` ([opening_teaching_integration.py:132-138](backend/services/opening_teaching_integration.py#L132)).
5. The gate at [coach_play.py:7548 area](backend/routes/coach_play.py#L7548) refuses to re-evaluate on
   later moves because the flag is set.
6. By move 4-5, when the user plays the move that commits to
   Italian / Ruy Lopez / Scotch (and the teaching system DOES
   have variation + trap content for those narrower keys), the
   system has already given up. Never re-offers.

Plus a downstream rendering bug at
[CoachPlay.jsx:540-597](frontend/src/pages/CoachPlay.jsx#L540): the only-`just_play` offer
either silently no-ops on the frontend (no real lesson path to
present) or surfaces a useless "Just play" button. Either way the
user perceives no opening teaching happening.

**Why this matters product-wise:**
This is the surface Mohit explicitly cited when he said "coach
should guide you from the opening, why this opening, and then
coach tries to play a variation or if you play a variation, coach
notices that and tells you about the idea of that opening." None
of that works. Today's coach detects, tries once with no content
to offer, gives up.

Combined with the bot-narration `coaching_library.py` voice
(separate but related issue), this is why PWC feels like
"chess.com bot, not ChessGuru coach."

**Fix shape (NOT a one-evening job):**

1. **Suppress empty offers.** When `options` is just `[just_play]`,
   don't insert the message at all. Per [[no-hollow-coverage]] —
   silence > useless offer.

2. **Re-detect on every opening-phase move.** Replace
   `opening_offer_shown: bool` with
   `last_offered_opening_key: Optional[str]`. On each move while
   `phase == "opening"`, re-run `check_opening_and_offer_teaching`
   IF the detected opening_key has changed (narrowed) since the
   last offer.

3. **Add the "describe the opening" path that doesn't depend on
   variation theory.** Even when no specific variation is detected
   yet, the coach SHOULD be able to say "You played 1.e4 — open
   game, fight for the center, both sides will develop pieces
   toward the center. Italian / Ruy Lopez / Scotch are the most
   common branches from here." That's content that doesn't need a
   trap library or variation tree. It's general opening principle
   commentary keyed to the family. Build a tiny per-family
   summary table; insert at move 1; allow it to refine as the
   line narrows.

4. **De-dupe.** Once a SPECIFIC variation (e.g. italian_game) has
   been offered AND accepted/declined, don't re-offer that exact
   key. But DO re-offer when the line narrows further (italian
   game → italian two knights → fried liver).

5. **Frontend**: in [CoachPlay.jsx:540-597](frontend/src/pages/CoachPlay.jsx#L540), separate the
   "describe the opening" message (a one-paragraph contextual
   note) from the "offer to teach a specific lesson" prompt
   (the buttons). Today both are conflated into `teachingOffer`
   state.

**Companion bugs already locked or to-lock:**
- coaching_library.py first-person bot templates — separate
  voice-layer fix
- `behavior_events: []`, `habit_violations: []`,
  `opportunity_history: []` empty across multiple games —
  the pedagogical layer that catches user's mistakes silently
  doesn't fire. Different rabbit hole.

**Companion:** [[drillable-adaptive-coach]], [[product-vision]],
[[sub1500-memory-anchors]], [[play-with-coach-teaching-integration]],
[[play-with-coach-phase1-design]], [[no-hollow-coverage]].
