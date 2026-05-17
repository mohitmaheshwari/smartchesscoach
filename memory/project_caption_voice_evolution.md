---
name: caption-voice-evolution
description: "Backlog for evolving caption voice AFTER pilot validates the bounded-improvisation pipeline. Three phases: style-layer modularization → persistent coach memory wire-up → identity design."
metadata: 
  node_type: memory
  type: project
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

The bounded-improvisation pipeline (resolver + compact prompt + repair
verifier, shipped 2026-05-15 in commit 886457bb) solves caption
CORRECTNESS. It does NOT solve caption SOUL — phrase diversity,
emotional pacing, personality continuity. Three evolutions are
sequenced for after the pilot proves the floor moved up:

**Phase 1 — Style-layer modularization.**
Split the caption generator into two passes:
  Pass 1 (semantic IR): resolver output → minimal teaching core
    { focus, move, anchor, secondary, tone, severity }
  Pass 2 (stylistic): teaching core → final sentence
Unlocks phrase diversity, emotional variation, multiple coach
personalities, adaptive harshness — WITHOUT growing the prompt.
Cost: each layer is another place to be wrong; seam design is the
hard part.

**Phase 2 — Persistent coaching memory wire-up.**
We already have `coach_memory` and `player_identities` MongoDB
collections sitting unused in the LLM context path. Wire them into
build_user_prompt so the prompt carries:
  { tilts_after_blunders: bool,
    responds_to_directness: bool,
    recurring_issue: str,
    coach_style: "firm-but-respectful" | ... }
Restores per-player calibration without returning to fat prompts.
HIGH ROI — wires up existing data, no new collections.

**Phase 3 — Identity design / personality continuity.**
Coach has a stable voice across sessions: streak callbacks,
"yesterday you played e4, today f4 — same plan?", silence after
blunders for a turn, timing of praise. Needs Phase 1 + Phase 2
underneath. Overlaps with [[situational-personality]] (7 tones)
but goes further into multi-session continuity.

**Why:** User articulated this as "you solved correctness — now
ChessGuru becomes identity design." The moat shifts from "correct
chess captions" (now solved) to "I feel coached by someone smart"
(emotional/pedagogical continuity).

**How to apply:**
- Do NOT start any of these before running the pilot on real games
  with the just-shipped pipeline. Validate the floor first.
- Phase 2 before Phase 1 if pilot shows captions are correct but
  feel impersonal — coach memory injection is faster.
- Phase 1 before Phase 2 if pilot shows captions are correct but
  feel templated — style-layer is the unlock.
- Phase 3 is destination, not next step.

See [[llm-as-controlled-narrator]] (the architectural law these
must respect), [[coach-voice]] (canonical voice rules these
must preserve), [[situational-personality]] (7 tones this
will eventually realize).
