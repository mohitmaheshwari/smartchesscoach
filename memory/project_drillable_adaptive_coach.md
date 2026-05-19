---
name: drillable-adaptive-coach
description: Major architectural direction — the coach must be DRILLABLE on demand, explaining concepts at multiple depths the user can ask for. Today coach is one-shot static; needs to become multi-level adaptive. This is what makes it feel like a human coach vs a captioner.
metadata:
  type: project
---

**Major product direction (locked 2026-05-19 by Mohit):** the coach has to be ADAPTIVE and DRILLABLE — explains a concept once, but goes deeper when the user wants more, multiple levels deep.

**The gap today:** ChessGuru's coach emits a caption per move and moves on. No "tell me more." No "I don't get it." No drilling. This makes it feel like a captioner, not a coach. A human coach:
- Explains the concept once briefly
- If the student doesn't get it, goes a level deeper
- If asked "why?" they have an answer
- If asked again, they have a deeper answer
- Calibrates depth to the student's understanding
- Can go from "this is a pin" → "this is why pins matter geometrically" → "this is why YOU keep falling for them" → "this is what it means about your style"

**The four-level ladder** (from 2026-05-19 vision discussion):
1. **Principle recall** — "this is a pin"
2. **Geometry recall** — "bishop-on-f7 pressure keeps appearing in your games"
3. **Behavior recall** — "you trust pinned pieces when uncastled"
4. **Identity recall** — "you favor material over king safety"

The DRILL affordance is what lets the user climb this ladder. Click once → geometric layer. Click again → behavioral layer. Click again → identity layer. The system should know which layer is currently visible and what the next-deeper layer would say.

**Architectural requirements (sketch):**
1. Every caption gets a "Tell me more" affordance in the UI
2. Each principle has 4 levels of explanation generation (data-driven where possible)
3. Per-user understanding model that tracks WHICH principles + concepts they've grasped vs missed (foundation for adaptive depth)
4. Voice transitions smoothly between levels (not "Level 1:" / "Level 2:" — feels like one coach going deeper)
5. Default depth = Level 1; user-initiated depth-climbing only

**Why this matters most:** This is the single biggest differentiator from "AI explanations." Generic AI is static. A drillable coach is responsive. It's also what makes ₹199/month feel earned — the user can SEE the depth.

**Why not built yet:** Significant work. Needs:
- Frontend "Tell me more" UI patterns
- Backend depth-aware explanation engine per principle (Level 2-4 generation logic)
- Per-user comprehension tracking model
- Voice templates at each level for each principle

Probably 2-4 weeks of focused work depending on scope. Bigger than any single component we've shipped.

**Companion principles:** [[product-vision]], [[sub1500-memory-anchors]], [[coach-voice]], [[memory-voice-competence-not-history]] (the new memory framing).
