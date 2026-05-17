---
name: Teaching Coach Move Selector Design
description: Coach deliberately creates learning positions — plays "good but not perfect" moves to give student tactical opportunities to find. Mechanics shipped; feedback loop unverified.
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
## What it does

Coach's move selector in Play with Coach does NOT always play the best move. It deliberately steers positions toward learning moments — pins, forks, skewers, hanging pieces, discovered attacks — chosen to match the student's profile gaps.

## Tennis analogy (the why)

A human coach hits to your backhand, not winners. Coach plays REAL chess but creates *exploitable* positions every 3-4 moves. If student finds the tactic → praise; if they miss it → point it out.

## What's BUILT (verified in code as of 2026-04-25)

[coach_play/teaching/move_selector_v2.py](backend/coach_play/teaching/move_selector_v2.py) and supporting modules:

- **TeachingIntent enum** in [types.py](backend/coach_play/teaching/types.py): `HANGING_PIECE_PUNISHMENT`, `FORK_OPPORTUNITY`, `THREAT_AWARENESS`, `PIN_EXPLOITATION`, `SKEWER_OPPORTUNITY`, `DISCOVERED_ATTACK`, `OVERLOADED_PIECE`
- **Wide candidate generation** in [candidate_generator.py](backend/coach_play/teaching/candidate_generator.py): `teaching_mode=True` → 15 candidates within 250cp (not 6 within 75cp). Hanging-piece moves are KEPT (not filtered out) so the coach can deliberately leave a piece undefended.
- **Position-based scoring**: `PositionFeatures` dataclass tracks pins, skewers, discovered attacks, overloaded defenders, fork opportunities ON THE RESULTING POSITION. Score moves by what they create for the student to find.
- **Intent selection driven by student profile**: `select_intent()` reads `student_weaknesses` + `last_game_violations` to pick which intent to pursue this turn.
- **Wired into Play with Coach**: [coach_opponent.py:485](backend/coach_play/coach_opponent.py#L485) constructs `TeachingMoveSelectorV2` and calls `select_move()`.
- **Opportunity tracking**: `MoveSelection.created_opportunity` and `opportunity_details` are populated after the coach moves — what pattern got created.

## Gaps still to verify

1. **Announce-and-test loop**: when coach plays a deliberate weakness, does the user get a "look carefully" prompt and a follow-up check ("did you spot the pin?")? The data is there in `opportunity_details` — is it surfaced in the UI/coaching message?
2. **Mirror → student_weaknesses pipeline**: when the home-page Mirror flags `piece_safety` in imported games, does that propagate to `student_weaknesses` for the next coach session, or are they parallel signals that don't talk?
3. **"You missed it" voice**: if the student doesn't exploit the created opportunity, does the coach explicitly point it out, or just move on?

## How to apply

When working on Play-with-Coach features: the deliberate-weakness selector is already running. Don't rebuild it. Instead, find these three gaps and close them — that's what unlocks the full teaching flow the user described.
