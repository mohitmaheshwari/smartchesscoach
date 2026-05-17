---
name: Game Review Redesign
description: Replace V5 narratives in game review with fundamentals + phase analysis + opening awareness + position commentary
type: project
---

## Plan

Replace the current game review coaching (V5 LLM narratives) with the same systems built for Play with Coach:

1. **Fundamentals timeline** — Run fundamentals evaluator across all moves. Show how each fundamental changed during the game.
2. **Phase analysis** — Opening/Middlegame/Endgame accuracy breakdown at the top.
3. **Opening awareness** — Which opening was played, where user deviated from theory, trap detection from JSON tree.
4. **Position commentary** — Replace V5 narratives with position reader output (outposts, overloaded pieces, blocked pawns, plans).

## Status: In progress (2026-04-13)

### Done:
- Two tabs: Review + Insights (Coach tab removed)
- Insights tab: phases, opening analysis, behaviors, fundamentals, key moments
- Coach Session guided flow built (CoachSession.jsx) but rendering issue
- Backend /games/{id}/coach-review with pattern_context + session data

### TODO — Enrich Decrypt/Review tab:
1. Add position commentary from read_board_like_a_coach per move (pins, forks, plans)
2. Add opening theory awareness (are we in theory? deviation? traps?)
3. Add move intention detection (what was user trying to do?)
4. Add stockfish branching "what if" lines (move from old Coach tab)
5. Add structured reflection form per move (what were you thinking?)
6. Connect to user's weakness pattern ("this is the type of moment you miss")
7. Fix CoachSession rendering in LabV2 (sessionDismissed logic)

### UNIVERSAL RULE (must apply everywhere):
- Any chess move in text (Bc4, Nf3, O-O, etc.) must be CLICKABLE
- Clicking shows the move on the board with an arrow
- Applies to: decrypt, coach, commentary, game review, everywhere
- Use regex to detect SAN notation in text and wrap in clickable spans
