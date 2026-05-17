---
name: Visual Danger Language
description: Future product pillar — teach pattern recognition (shapes, geometry, danger signals), not just moves. 23 canonical rules; 22 board-verified math, 1 heuristic. Two-layer detection (geometry + verifier) is non-negotiable.
type: project
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
ChessGuru's next major pedagogy direction: teach players the *recognition reflex* underneath moves. Humans don't calculate first — they recognise shapes first, then calculate when something feels off. Strong players carry ~50K visual chunks (Chase & Simon, 1973). No mainstream chess software trains this directly; they all teach moves, tactics, engine lines.

**Why:** Real intuition is "this shape feels wrong." That's the layer that separates a 1500 from an 1800. Product story shifts from "we point out your mistakes" to "we teach you to see danger before you make the mistake."

**How to apply:** When designing any future surface (postgame copy, real-time warnings, training decks, puzzles), ask: does this teach pattern recognition or just point at moves? The 23 rules below are the canonical list. Numbered as in the design conversation 2026-05-09 (Rule 16 = Rule 1 stated formally; counted once).

## Two-layer detection — the misfire-prevention architecture

Every shape detector has two layers, and they fail differently:

1. **Geometric layer** — pure math. "Bishop on c3, knight on e5, two diagonal squares apart" — boolean, never wrong.
2. **Meaning layer** — does the shape *actually* create a concrete threat in this position? Requires verifier (Stockfish eval delta for tactical shapes; feature-count for positional shapes).

Misfires don't come from bad geometry. They come from firing the WARNING ("this is dangerous") on positions where the shape exists but the meaning doesn't. Same lesson as cognitive_gap Pass 1 — the old classifier saw "move on the king side" and called it king_safety. Geometry was right; meaning was wrong; misfire rate was 33%. Pass 1 added verifier gates and dropped it to 22%.

**Rule:** every shape detector = (geometric boolean) AND (verifier gate). Geometry alone is necessary but not sufficient. Never ship a shape detector with no verifier — that's a 30%+ false-alarm rate waiting to happen, and shape-warnings break trust faster than missed shapes do.

## The 23 rules — board-verified status

All entries below labeled **VERIFIED** were tested mechanically with python-chess on canonical FEN positions; the detection logic returned the expected pattern.

| # | Rule | Status | 1200-friendly summary |
|---|------|--------|----------------------|
| 1 | Bishop dominates edge knight | **VERIFIED** | Edge knight + enemy bishop 3 squares in on same line. Knight 4 jump squares all attacked. Knight undefended → frozen. |
| 2 | Aligned pieces + enemy attacker | **VERIFIED** | Two of your pieces on same file/rank/diagonal AND enemy long-range piece on the line = pin/skewer/discovered tactic. |
| 3 | Advanced knight, no pawn support | **VERIFIED** | Your knight on rank 5+ with zero friendly pawns defending the square. Lives or dies by attacker count. |
| 4 | Bishop blocked by own same-colour pawns | **VERIFIED** | Bishop's diagonals blocked by friendly pawns on same colour as bishop. Bishop has near-zero mobility. |
| 5 | Open diagonal aimed at king | **VERIFIED** | Enemy bishop/queen on a diagonal hitting any square in or near king zone, no piece blocking. |
| 6 | Rook with no open file | **VERIFIED** | Rook stuck behind own pawns, every file has a pawn somewhere. No open lines accessible. |
| 7 | Pieces pointed at different ends | **HEURISTIC** | "Coordination" has no clean math. Skip until we figure out a real measure. Don't ship as a real-time warning. |
| 8 | Queen out before army | **VERIFIED** | Queen has moved off starting square but knights/bishops still home. Each tempo loss is free for opponent. |
| 9 | King with no escape (back rank) | **VERIFIED** | King on back rank + 3 pawns directly in front + enemy heavy piece can reach back rank. |
| 10 | Pawn chain direction | **VERIFIED** | Connected friendly pawns; tip's file vs base's file determines kingside/queenside slope. (Geometric only — "attack there" advice is heuristic.) |
| 11 | Hook pawn near castled king | **VERIFIED** | Their king castled short, one of their pawns near king pushed forward, your pawn ready to lever it. |
| 12 | Knight on rim | **VERIFIED** | Knight on a-/h-file or 1st/8th rank. Maximum 4 legal moves vs 8 in centre. |
| 13 | Overworked defender | **VERIFIED** | One piece is the sole defender of ≥2 of your pieces under enemy attack. Removing it crashes multiple targets. |
| 14 | Locked centre | **VERIFIED** | Central pawns (d/e files) blocked head-to-head with no captures available either side. |
| 15 | Weak square near king | **VERIFIED** | Pawn pushed leaves a square within 2 of king that no enemy pawn can ever defend again. |
| 16 | (= Rule 1, formal version) | — | Counted once. |
| 17 | Battery on file/rank/diagonal | **VERIFIED** | ≥2 friendly heavy pieces stacked on same line. Doubled attack power. |
| 19 | Pawn one move from forking | **VERIFIED** | Pawn one square from advancing AND attacking 2 enemy pieces from the new square. |
| 21 | Trapped piece (SEE-style) | **VERIFIED** | Piece's every legal move lands on a square where SEE returns negative (loses material). |
| 22 | Pinned blocker | **VERIFIED** | Your piece between enemy long-range attacker and your king — can't move without exposing king. |
| 24 | Multi-piece knight trap | **VERIFIED** | Edge knight, both move-square diagonals covered by any mix of bishop/pawns/other pieces. |
| 25 | Rook 7th + king 8th | **VERIFIED** | Rook on enemy 7th, enemy king on 8th. King has zero legal moves to 7th rank. |
| 26 | Open file at castled king | **VERIFIED** | Enemy king's flank file has no pawn AND your heavy piece on the file. |
| 27 | Pinned defender | **VERIFIED** | The piece defending one of your targets is itself pinned along another line. |

(Rules 18, 20, 23 from the design conversation were dropped during audit — bishop-pair-on-diagonals, colour-complex collapse, and a vague mate-net rule. None survived the math check.)

## Detection difficulty for shipping order

**Mechanically clean — verifier is light** (eval-delta or feature-count, no deep search):
3, 4, 6, 8, 9, 11, 12, 14, 15, 17, 19, 26

**Medium — verifier needs a small SEE or single-step lookahead**:
1, 2, 5, 10 (direction), 21, 22, 24, 25, 27

**Heavier verifier — multi-step search needed**:
13 (overworked defender — runs "what if this piece is gone" through each defended target)

**Don't ship without redesign**:
7 (no clean math)

## Deployment surfaces — roll-out plan

Aligned with `feedback_no_parallel_surfaces.md`: extend existing surfaces; don't fragment.

### Phase 1 — Game Analysis (Shapes tab)
**First production surface.** Lowest blast radius, biggest verifier safety net (Stockfish confirms post-hoc whether each detected shape was actually dangerous). Lives next to existing cognitive-gap and critical-moment surfaces in the game analysis page — natural extension, not a parallel surface.

Why first: wrong shape callouts here are mildly annoying. Wrong callouts anywhere else break trust harder. Audit misfire rates here before any real-time deployment.

### Phase 2 — Puzzle Deck (parallel with Phase 1)
**"Spot the danger" puzzle type** — extension of the existing pattern-puzzle infrastructure (`PatternTraining.jsx` + `community_puzzles` collection). Show position, ask which shape is on the board, give coach voice on why it matters.

Safest of all surfaces — no live judgement, no interrupting flow, user explicitly asked for the challenge. Ships in parallel with Phase 1, not after, because puzzles *train* the recognition reflex while analysis only points at it post-hoc. They teach different things.

### Phase 3 — Play with Coach (real-time, post-audit)
**Last and most cautious.** Extend the existing `pre_move_guardian.py` ("Are you sure?") — it already gates risky moves; shape warnings are a natural addition to the same mechanic.

**Hard gate:** only rules with <5% misfire rate on a 1000-game audit qualify for real-time deployment. Likely starting subset: knight on rim, hook pawn, open file at king, pinned blocker, queen too early — the 4-5 cleanest. Not all 22.

### Engine 2 — branding strategy
Frame internally from day one: **ChessGuru has Engine 1 (Stockfish — the calculator) and Engine 2 (the pattern engine — what a master sees at a glance).** Two modes of thinking, both available to the player. Strong differentiator vs all chess software (none of them have this).

**Surface the Engine 2 tag only after the audit confirms reliability.** Internal name from day one; UI tag once Phase 1 is shipping clean; marketing copy only after Phase 1 misfires are <5%. Earn the brand, then claim it. If we brand before it works, one bad demo kills the story.

## Pace and rigor

Heavier than cognitive_gap by an order of magnitude — 22 shape rules, each needing detector + verifier + coach copy + 1000-game audit. We spent two passes fixing ONE classifier (cognitive_gap Pass 1, lab summary voice Pass 2). Visual danger language is 22 of those at the same rigour bar.

**Realistic cadence:** one rule per week, audited end-to-end before the next ships. Not a sprint — a programme. Skipping the audit on any single rule reintroduces the misfire problem the whole architecture exists to prevent.

## Coach voice samples

Sample warnings for each pattern (from the design conversation — these are voice exemplars, not the final shipping copy):

- Rule 1: "That bishop is sitting 3 squares from your knight on the same rank. Every square your knight can jump to is covered."
- Rule 2: "Your queen and rook are on the same file. One enemy rook on that file and the queen has to step out — you lose the rook behind it."
- Rule 5: "Their bishop on b2 has a clear diagonal to your king on g8. The attack isn't here yet, but the road is built."
- Rule 11: "Their h-pawn pushed to h6. Your g-pawn can march up. Either they capture (file opens) or it stays (you have a wedge to sacrifice on)."
- Rule 13: "Your knight on f3 is the only defender of both d2 and h2. Anything that hits the knight loses one of those pawns."
- Rule 25: "Your rook on a7, their king on h8. King can't step down. One more piece anywhere near and it's mate."

## Verification record

2026-05-09: 22 of 22 mechanically-testable rules verified on canonical FEN positions via python-chess. Rule 7 not testable — flagged as heuristic, not shipping until reformulated.
