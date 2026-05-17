---
name: ChessGuru Coach Voice — Canonical Rules
description: The locked voice for every player-facing string in ChessGuru. Use as the test for any new coaching text and as the ruler when auditing existing surfaces.
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
The smartest friend who plays better than you and tells you the truth without making you feel small. That is the coach. Every coaching string — Play with Coach, Lab, Reflect, Training, Mirror, Landing, FAQ, opening lessons, trap lessons, puzzle feedback, position commentary — must sound like that person.

**Why:** Voice was iterated multiple times before locking ("very sharp English" → "talk like a friend who plays chess" → multiple coaching_library.py rewrites). Pre-premium quality bar requires one voice across surfaces, applied uniformly. Tested 2026-04-30 with the user; these rules are the agreed-on canonical set.

**How to apply:** When writing or auditing any coaching text, the text must satisfy every rule below. Anti-patterns must be removed on sight. Run new copy past the character test in the opening line: would the smartest friend who plays chess actually say this?

## The 6 Rules

1. **Talk like a smart friend who plays chess. Not a textbook.**
   Use "you." Use contractions. Short sentences. Sometimes very short. Skip "consider," "potentially," "you might want to."

2. **Name the thing.**
   The move. The square. The piece. The pattern. *"Bg5 hangs to ...h6"* — not *"this move is risky."* *"You missed Nxf7"* — not *"there was a better move available."*

3. **No engine talk to the player.**
   No cp loss, accuracy %, evaluation. Translate to felt language: *"loses a pawn," "drops a piece," "gives up the center."* Numbers belong in dashboards, never in coaching.

4. **Plain words. Keep only the chess words players already know.**
   - Out: prophylactic, outpost, minority attack, in-between move, zugzwang (use plain phrasing).
   - In: fork, pin, skewer, fianchetto, en passant, discovered attack, sacrifice. These teach themselves through use.

5. **Show, don't lecture.**
   Bad: *"Developing your pieces is important in the opening."*
   Good: *"Your knight and bishop are still home. Get them out."*

6. **Empathy without softness. End with one specific thing.**
   Bad: *"That's okay, blunders happen!"* (too soft — patronizing)
   Bad: *"You blundered the queen."* (too cold — clinical)
   Good: *"You hung the queen. Painful — and the kind of thing that fades once you check captures first."*
   Every coaching message ends on a single concrete action or observation, never a generic platitude.

## Anti-patterns — delete on sight

- Generic praise without specifics ("Nice move!" with no *why*)
- Multi-paragraph lectures
- "Consider X, Y, or Z" — pick one and recommend it
- Hedging words: potentially, might be, could be, possibly
- First person ("I see that…", "I think…") — the coach is the player's voice, not a third party watching
- Engine words leaking through (cp, eval, accuracy %)
- Bullet lists where a single sentence would do
- Excessive punctuation, excessive emoji
- Restating what the player did before commenting on it ("You played Bg5. Bg5 attacks the queen…")

## Side-by-side calibration

These pairs anchor what "in voice" means.

**Opening tip — pawn flank move**
- Off-voice: "A pawn move on the side of the board doesn't help your development right now. You're using your turn for something small instead of getting your pieces into the game."
- In-voice: "A side pawn move buys nothing here. Your knight and bishop are still home — get them out first."

**Move classification — mistake**
- Off-voice: "This move loses approximately 150cp. There were better alternatives such as Nf3."
- In-voice: "Nd5 was sharper here — Nf3 gives up the center."

**Position commentary — pinned piece**
- Off-voice: "Their piece is pinned. Add more pressure to the pinned piece."
- In-voice: "Their knight on d7 can't move — it's pinned to their king. Hit it again."

**Puzzle feedback — wrong move**
- Off-voice: "Incorrect. The correct move was Rxe1#."
- In-voice: "Rxe1 was mate — your move missed the back-rank weakness."

## Surfaces to keep aligned

Every place where text reaches a player. The audit covers (non-exhaustive):

- backend/services/coaching_library.py
- backend/services/realtime_coaching_feedback.py
- backend/services/puzzle_miss_coaching.py
- backend/services/game_decryption_v5_service.py
- backend/services/coach_commentary.py
- backend/services/coach_personality.py
- backend/services/position_intelligence.py (PLAN_RULES + summaries)
- backend/services/position_reader.py (feature titles + descriptions)
- backend/services/coach_memory.py
- backend/coach_play/* (commentary, pre-move guardian, teaching integration)
- backend/data/traps.json (trap explanations)
- backend/data/endgames.json (endgame lesson copy)
- backend/data/opening_curriculum.json (opening teaching copy)
- frontend/src/pages/Landing.jsx (already in voice as of 2026-04-30 Phase 1.5)
- frontend/src/components/coach/*.jsx (UI labels, hint text)
- frontend/src/components/GameDecryptionV5.jsx (section labels, explanations)

When adding any new coaching text, run it past the 6 rules and the anti-patterns list before commit.
