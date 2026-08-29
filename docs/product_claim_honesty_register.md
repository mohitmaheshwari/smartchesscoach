# Product Claim Honesty Register

**Status:** Phase A guardrail  
**Last audited:** 2026-08-28  
**Canonical outcome contract:** `docs/personal_improvement_cycle_spec.md`

## Purpose

ChessGuru may encourage a player freely, but it may only claim improvement,
resolution or mastery when the evidence named by the canonical Personal
Improvement Cycle (PIC) contract exists. This register records the copy
boundary; it does not create a second progress engine.

## Claim levels

| Level | What the product may say | Minimum evidence |
|---|---|---|
| Observation | “You won three games in a row.” | Direct stored fact |
| Window comparison | “The latest 5 had fewer blunders than the previous 5.” | Two complete, BSON-dated, comparable analysis windows; state the windows |
| Promising | “This looks promising, but it is not proven yet.” | Canonical PIC `checkpoint_promising` evidence |
| Resolved / proven in games | “You proved this in games.” | Canonical PIC eligible independent evidence and `resolved` verdict |
| Mastery | Learner projection owned by `concept_mastery_service` | Its independent-game evidence contract; activity completion alone is insufficient |

The following never proves durable improvement by itself: a win streak, one
better game, completing puzzles, reflection accuracy, an assisted Coach Play
session, a focus-window compliance threshold, a zero-fire detector result, or
legacy profile labels without chronological evidence.

## Surface register

| Surface | Previous risk | Current allowed behavior | Runtime owner |
|---|---|---|---|
| Home | Win streak called “real improvement”; undated windows could produce a trend | Win streak is momentum only. Directional copy requires two 5-game BSON-dated analysis windows and names that comparison. | `backend/home_intelligence_service.py` |
| Game Review | `created_at` windows and broad “you’re getting better” summary | Requires at least 10 BSON-dated analyses; reports a directional window comparison, not durable improvement. | `backend/services/coach_review_service.py` |
| Progress | Legacy resolved/reflection records rendered as “Fixed” or “Mastered” | Render the stored history and reflection score without claiming transfer to games. PIC/concept mastery remains authoritative for proof. | `backend/routes/player.py` |
| Focus lock | Passing one compliance window rendered as “Rule mastered” | “Focus checkpoint passed”; describes only the observed target window. | `backend/coach_state/focus_lock_service.py` |
| Re-engagement email | Legacy `player_profiles.improvement_trend` drove “you’re getting better” | Uses the profile only to choose a next-step message; no improvement claim. | `backend/scripts/generate_reengagement_emails.py` |
| Landing | Claimed the decay system “knows when you’ve improved” | Describes the implemented comparison capability only. | `frontend/src/pages/Landing.jsx` |
| Pricing | Offered a monthly claim through a one-time order flow and promised a complete loop | Recurring Pro is “coming soon” until the verified subscription lifecycle and complete coaching loop pass their gates. | `frontend/src/pages/Pricing.jsx`, `backend/routes/billing.py` |

## Deliberate non-progress uses of similar words

Move-local descriptions such as “you improved your worst piece” describe a
chess move, not player development. Opening/puzzle lesson completion may label
content completion internally, but it must not be presented as proven transfer
to external games. These are separate semantics and are not promoted into the
PIC learner outcome.

## Regression enforcement

`backend/tests/test_product_claim_honesty.py` guards the high-risk exact claims
above. Behavioral tests for PIC verdicts and concept mastery remain the
authority for positive `promising`, `resolved`, and “proven in games” states.

When adding a player-development claim:

1. Identify its canonical evidence owner.
2. Include the evidence state/basis in the backend response.
3. Provide an insufficient-evidence rendering.
4. Add positive, negative and insufficient-evidence tests.
5. Add the surface to this register before enabling the copy.
