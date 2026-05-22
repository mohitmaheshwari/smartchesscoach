# Approved caption rewrites — voice reference for future detector/template work

Captions Mohit approves during FEN-review sessions live here. Each entry pairs
the shipped v55 caption with the approved-style rewrite + notes. Once we have
5-10 examples, we'll have enough pattern to propose a single detector change
or template rewrite covering the family.

**Voice rules so far** (from approvals on 2026-05-22):
- Name what the engine's best move DOES mechanically ("kicks the bishop", "hits with tempo"), not just the resulting eval ("wins material").
- Name the consequence concretely: which square / which piece / which line opens.
- Avoid chess jargon — say "your g2 bishop" not "your fianchetto bishop". Target audience is 600-1500 (see [feedback_caption_voice_avoid_chess_jargon](../../../.claude/projects/c--Users-MIISCO-smartchesscoach/memory/feedback_caption_voice_avoid_chess_jargon.md)).

---

## #1 — game 6569e93f-a90 m6 Qe2

**FEN:** `rnbqk1nr/pppp1ppp/8/2b1P3/5p2/2N2N2/PPPP2PP/R1BQKB1R w KQkq - 1 6`

**Engine PV:** `d4 Bb4 Bxf4 d5 Bd3 Bxc3+` (+225cp)

**Shipped (LOW, `why_user_missed_material`):**
> Qe2 is a mistake. d4 was better. d4 wins material in the resulting line.

**Approved rewrite:**
> Qe2 is a mistake. d4 was better — it hits the bishop on c5 with tempo and lets you recapture f4.

**Why this works:** Names two things the move accomplishes (hits bishop + opens line to f4). The player sees "d4 with tempo" and learns the mechanism, not just the verdict.

---

## #2 — game 461ece5c-604 m11 e4

**FEN:** `r2qk2r/1ppn1p2/p2bpp1p/5b2/2pP4/2N2NP1/PP2PPBP/R2QR1K1 w kq - 0 11`

**Engine PV:** `Nh4 Bh7 Bxb7 Rb8 Bxa6 Rxb2` (+155cp)

**Shipped (LOW, `why_user_missed_material`):**
> e4 is a mistake. Nh4 was better. Nh4 wins material in the resulting line.

**Approved rewrite:**
> e4 is a mistake. Nh4 was better — it kicks the bishop off the long diagonal, so your g2 bishop can take on b7.

**Why this works:** Names the mechanism (kick), the resource being created (long diagonal opens up), and the target (b7). Avoids "fianchetto" — says "g2 bishop" concretely.

---

## #3 — game fc97ee1d-ba3 m7 Bb5 (v53 regression case → fixed in v56)

**FEN:** `r1bqkbnr/pppp3p/n4p2/3Pp1p1/4P3/2P2N1P/PP3PP1/RNBQKB1R w KQkq - 0 7`

**Engine PV:** `Nxe5 Ke7 d6+ cxd6 Nc4 d5` (+408cp). PV #2: `Nxg5 Nh6 Qh5+ Ke7 ...` (+343cp) — the Légal's pattern.

**Shipped v55 (LOW, `why_user_missed_material`):**
> Bb5 is a mistake. Nxe5 was better. Nxe5 wins material in the resulting line.

**v56 caption (HIGH, NEW variant `why_user_missed_clearance_then_check`):**
> Bb5 is a mistake. Nxe5 was better. Nxe5 opens the line — your queen can then play Qh5+ to chase the king on e8.

**Why this is the right shape:** Names the mechanism (opens the line), the piece (queen), the follow-up move (Qh5+), and the target (king on e8). Honest about the 2-move plan — says "can then play" so there's no 1-move hallucination.

**This case was a v53 regression** — the 2-move clearance detection existed pre-v53 but I deleted it overnight to silence a 1-move-caption hallucination instead of fixing the template. v56 restores the detection as a distinct evidence type with a proper multi-move template. See [feedback_fix_framing_not_detection](../../../.claude/projects/c--Users-MIISCO-smartchesscoach/memory/feedback_fix_framing_not_detection.md).

---

## Shared pattern across #1 and #2

Both shipped captions hit `why_user_missed_material` because the engine's PV
shows a material gain but the eval-guard rejected the more specific
`piece_capture` claim. In both cases the engine's *best move* is doing
something tactical (hits a piece with tempo) that the existing template
doesn't surface.

The proposed detector / template angle:
- **Input:** the engine's PV after best move.
- **Detect:** does white's best move attack a piece (i.e. opponent's first PV
  response moves that piece away)?
- **If yes:** caption claims "Nh4 was better — it [attacks/hits/kicks] the
  [piece] on [square]."
- **Optionally extend:** if the *next* white move in the PV captures a different
  piece/pawn, append "so you can take on [square]" — this gives the consequence
  without the engine-speak.

This needs to wait for 5-10 examples before designing the detector — premature
generalization from 2 examples will likely miss edge cases.
