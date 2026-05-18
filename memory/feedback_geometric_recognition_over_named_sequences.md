---
name: geometric-recognition-over-named-sequences
description: Tactical detectors must encode the geometric trigger a human eye scans for during live play, not the historical move-tree of a named trap.
metadata:
  type: feedback
---

Tactical detectors must encode the **geometric trigger** a human eye scans for during live play, not the historical move-tree of a named trap.

**Why:** 1200-1500 players cannot recall move sequences ("on move 7 white takes queen, move 8 king to e2…"). They CAN recall danger shapes, vulnerable diagonals, trapped-king geometry. Pattern memory is geometric, not sequential — see [[sub1500-memory-anchors]]. Mohit's compression 2026-05-18: "If your bishop already stares at f2/f7, a pinned knight may not really be pinned." That single geometric sentence transfers across openings, mirrored colors, partial versions, and non-forced lines — which a memorized "this is Légal move 7" cannot.

**How to apply:** When building a tactical detector (Légal, Boden, smothered mate, Greco, etc.):
- DO: encode 4-6 board-verifiable geometric signals (pin axis, pressure square, king square, presence/absence of defenders, available forcing jump).
- DO: connect the geometry to the NAME in the caption, not to a move sequence ("Légal pattern: bishop on f7 + pinned knight + uncastled king = the pin may be fake").
- DON'T: hardcode named-trap move squares from the historical game (e.g. "bishop must be on g4/g5", "knight must land on e4/e5"). That over-fits and misses 90% of real-world fires in other openings.
- DON'T: tell the user "this is the position from Légal 1750 where on move 7…" — move-trees rot in memory under pressure; geometry persists.
- Builds a board-scan habit, not a memorization habit. A 1200 over-the-board: "wait… bishop on f7… pinned knight… this is that Légal geometry."

Companion principles: [[visual-danger-language]] (two-layer geometry+verifier non-negotiable), [[renderer-never-computes-chess-meaning]] (facts → IR → renderer split), [[no-hollow-coverage]] (audit the rendered string, not the internal label).
