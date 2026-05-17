---
name: Sub-1500 memory anchors are principles, geometry, and process — not games
description: HARD product rule. Teaching surfaces never reference games / opponents / move-sequences as memory hooks for the sub-1500 audience — they remember named principles and visual patterns, not what they played.
type: feedback
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
HARD product principle locked 2026-05-11.

A 600–1500 player does NOT remember:
  - Their own games (no recall of positions, sequences, results)
  - Opponent names ("your game vs Patrick on May 5")
  - cp_loss numbers from past moves
  - Move 18 of any specific game

A 600–1500 player DOES remember:
  - Named principles ("don't move the same piece twice in the opening")
  - Geometric patterns shown on a board (pin / fork / smothered-mate shapes)
  - Process habits ("CCT scan — captures, checks, threats")
  - Labels they say out loud (naming creates the memory)

**Why:** Said directly by Mohit 2026-05-11 — "a guy with less than 1500 doesn't
remember what he played in the game, he doesn't remember chess, you know? his
memory is around things that he can remember, may be geometry or teaching
principle or similar things, if you tell him you hung your rook in game vs xyz,
it doesn't ring a bell." This is the foundational audience-memory model that
gates every coaching surface in ChessGuru.

**How to apply:**

1. NEVER write coaching prose that uses a game / move / opponent reference as a
   memory hook. Forbidden patterns include:
     "in your last game against X..."
     "you did this in 3 of your last 5 games"
     "remember your blunder at move 18"
   The user reads these as empty — they don't trigger recall.

2. ALWAYS anchor recall language to the principle / pattern itself:
     "Same principle again — same shape, same fix."
     "{principle_name} — this is the pattern."
     Show the mini-board diagram with the geometric signature.
   The visual + principle name IS the recall hook.

3. Cross-game pattern tracking still happens in the DB (needed for drill
   selection, "stopped doing it" detection, prioritisation). But the SURFACE
   text never surfaces a count or a game reference — it surfaces the principle.

4. Each teachable concept ships with:
     - Name (sticky, ≤6 words)
     - Visual (mini-board diagram with arrows/highlights — same shape every time)
     - Explanation (≤20 words)
     - Process cue ("before you move...")
     - Drill (3 positions where this pattern is the right call)

5. Drill loops > count loops. A repeating principle triggers a drill served
   in isolation, NOT a count-up message. The drill is the memory.

6. The "celebration" moment when a player stops violating a principle is
   anchored to the NAMED principle, not the game history:
     "You've fixed this. {principle name}. The shape doesn't show up anymore."
