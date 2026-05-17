---
name: endgame-principles-backlog
description: Tiered backlog of endgame principles for the V5 caption pipeline. 1200-1500 amateur losses are dominated by endgame errors; current pipeline has only 2 endgame principles. Tier 1 ships the foundational 8.
metadata: 
  node_type: memory
  type: project
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

Mohit (2026-05-16, after the Walloo21 game where the square-rule miss
went uncaught) asked for the full endgame backlog rather than building
SQUARE_RULE alone in isolation. Reasoning: endgames are where 1200-1500
players actually lose the game; the pipeline has only `END_PASSED_PAWN`
and `END_KING_ACTIVE` currently and that's nowhere near enough.

## What we have

- **caption_principles.py**: 2 endgame principles
  - `END_PASSED_PAWN` (priority 50) — "Passed pawns must be pushed"
  - `END_KING_ACTIVE` (priority 65) — "King is a fighter in the endgame"
- **data/endgames.json**: 10 named lessons for the Play-with-Coach
  lesson library — a SEPARATE surface from V5 captions. The lessons
  (queen_checkmate, rook_checkmate, etc.) are interactive drills.
  Should be cross-referenced when naming principles so vocabulary stays
  consistent.

## What's missing (the backlog)

### Tier 1 — Foundational 1200-1500 (ship in order)

These are the named endgame patterns a 1200 player MUST internalize.
Each one is ~80-200 lines of code (detector + principle data + resolver
detail + verifier whitelist + per-fire audit).

| # | Principle ID | Concept | Detector complexity | Effort |
|---|---|---|---|---|
| 1 | `END_SQUARE_RULE` | King catches passed pawn iff Chebyshev distance ≤ pawn-to-promotion | EASY (geometric) | ~80 lines |
| 2 | `END_OPPOSITION` | Kings on same file/rank with one square between, opponent to move = you have the opposition | MEDIUM | ~120 lines |
| 3 | `END_KEY_SQUARES` | In K+P vs K, attacker's king must reach specific squares to win (depends on pawn rank + file) | MEDIUM-HARD (lookup table) | ~200 lines |
| 4 | `END_ROOK_BEHIND_PASSER` | Tarrasch rule: rook belongs behind a passed pawn (yours or theirs) | EASY | ~80 lines |
| 5 | `END_OUTSIDE_PASSED_PAWN` | A distant passer wins the race because the opponent's king is too far | MEDIUM | ~120 lines |
| 6 | `END_BREAKTHROUGH` | Sacrifice a pawn to create a passer (3 vs 2 majority breakthrough pattern) | HARD (mini-search) | ~200 lines |
| 7 | `END_PAWN_RACE` | Both sides have passed pawns racing to promote; count the tempo | MEDIUM | ~150 lines |
| 8 | `END_ACTIVE_KING` refinement | Existing `END_KING_ACTIVE` is too generic — narrow it to "centralise the king when material reduced" with specific evidence | EASY | ~40 lines |

**Tier 1 total: ~990 lines of new code + 8 per-fire audits.**

### Tier 2 — Important for 1500+ (after Tier 1 validates)

| Principle ID | Concept |
|---|---|
| `END_BAD_BISHOP` | Bishop locked behind own pawns of same colour |
| `END_WRONG_COLOR_BISHOP` | Rook pawn + bishop colour mismatch = drawn even up a piece |
| `END_OPPOSITE_COLOR_BISHOPS` | Drawing tendency in opposite-colour bishop endings |
| `END_KQ_VS_K_MATE` | Box the king to the edge, avoid stalemate |
| `END_KR_VS_K_MATE` | Coordinate king + rook to drive lone king to edge |
| `END_K2B_VS_K_MATE` | Drive king to corner, coordinate bishops |
| `END_PRINCIPLE_TWO_WEAKNESSES` | Create a second target the opponent's king can't defend |

### Tier 3 — Advanced (1800+, probably won't ship in v1)

| Principle ID | Concept |
|---|---|
| `END_LUCENA` | Building the bridge to win K+R+P vs K+R |
| `END_PHILIDOR` | Defending K+R vs K+R+P by holding the 3rd rank |
| `END_FORTRESS` | Defensive setup that's objectively losing but unbreakable |
| `END_TRIANGULATION` | King triangulating to lose a tempo |
| `END_ZUGZWANG` | Opponent's best move worsens their position |
| `END_CORRESPONDING_SQUARES` | Mirror-king-tracking in blocked pawn endgames |

## Pre-work that should land before Tier 1

1. **Audit phase detection.** V5 has a `phase` field on every move
   (opening / middlegame / endgame). When does endgame actually
   trigger? Material threshold? Queen exchange? Piece count? If the
   detection is unreliable, EVERY endgame principle inherits the
   noise. Run a quick audit on 50 games: read the FEN at the
   middlegame→endgame transition, manually assess whether the
   transition timing is right.

2. **Cross-reference with endgames.json.** Pick consistent naming.
   Don't have `END_SQUARE_RULE` in V5 captions and "King and Pawn"
   in Play-with-Coach lessons — same concept should use the same
   vocabulary across surfaces.

3. **Audit existing `END_PASSED_PAWN` and `END_KING_ACTIVE`.**
   They've been firing in production. Are they firing in the right
   positions? Are their captions concrete enough (1200-test compliant)?
   Refine if needed BEFORE adding 8 more.

## Implementation pattern (for each principle)

The successful Pawn Fork addition (2026-05-16) established the
pattern. Apply it for each endgame principle:

1. **Data first** — add the entry in `caption_principles.py` with
   evidence schema, priority, phase, cue templates.
2. **Detector** — pure-Python geometric check in `caption_facts.py`.
   No engine reliance unless the concept genuinely requires it
   (BREAKTHROUGH needs mini-search; SQUARE_RULE doesn't).
3. **Resolver detail** — specialised phrasing in
   `caption_priority_resolver.py:_principle_detail_text` that
   builds the named-pattern caption from evidence fields.
4. **Verifier whitelist** — add anchor name to `_OPENING_NAMES` /
   shape names lookup if relevant; protect the pattern name as a
   `protected_entity`.
5. **LLM example** — add one example caption to the principle focus
   block in `llm_caption_generator.py` so the LLM has rhythm
   calibration.
6. **Per-fire audit** — same pattern as
   `[[per-fire-audit-pattern]]`. Run on the V5 corpus, geometric
   verify each fire, scrub false positives, mark principle as
   board-verified.
7. **V5 version bump** — `V5_COACHING_VERSION` += 1 so existing
   games regenerate. ([[v5-lazy-generation-mechanic]] rule.)

## Strategic ordering rationale

- **SQUARE_RULE first** because Mohit personally flagged it (live
  validation already in hand from game `611c1fc6`).
- **OPPOSITION next** because it pairs with KEY_SQUARES — both feed
  the same K+P teaching unit. Together they cover ~40% of basic
  pawn-endgame mistakes.
- **ROOK_BEHIND_PASSER** before OUTSIDE_PASSED_PAWN because the
  geometry is simpler and gives a quick win for backlog momentum.
- **BREAKTHROUGH last in Tier 1** because it needs mini-search; treat
  it as a stretch target. If audit shows the simpler ones cover most
  cases, deprioritise.

## Pace expectation

Realistic: **one principle per week, audited.** Skipping the per-fire
audit is the bug Mohit keeps catching me on. Eight Tier 1 principles
= ~8 weeks of focused work, properly. Not a sprint.

## Cross-cutting concerns

- **Phase noise.** If phase detection mis-classifies a position as
  "endgame" when material is still middlegame-heavy, every endgame
  principle fires inappropriately. Phase audit is gating.
- **Detection cost.** Some endgame detectors need to walk the board
  (find passed pawns, count attackers/defenders for KEY_SQUARES).
  Per-move overhead adds up across 1900+ games in the corpus. Profile
  before shipping Tier 1 wholesale.
- **Priority conflicts.** Endgame principles will sit alongside
  middlegame ones. If a move triggers both `END_SQUARE_RULE` and
  `DEF_WALK_KING` (likely), priority must put the more specific one
  first. Document priorities in a single table so the resolver routing
  is predictable.

## Locked-in refinements from Mohit signoff (2026-05-16)

- **RULE_OF_SQUARE v1 stays `cp_loss ≥ 30`-gated.** Future v2: broaden
  to `(cp_loss ≥ 30) OR (engine best enters square AND played stays
  outside)` — geometric violation alone is sometimes enough. Defer.
- **OPPOSITION must additionally require best move is a king move.**
  Without this gate, technically-true opposition fires on positions
  where triangulation / breakthrough is the actual lesson, not
  opposition. False pedagogical positive risk is high.
- **ROOK_BEHIND_PASSER restricted to single-passed-pawn positions
  in v1.** "Behind" is perspective-sensitive (restraining theirs vs
  supporting yours, multiple passers, partial alignment). Multi-passer
  positions are deferred to v2 once the single-passer audit is clean.

## Future backlog (saved here so it doesn't get lost)

- **Principle confidence tiers.** Add `"confidence": "high"|"medium"|"low"`
  to each principle. Geometric certainties (rule of square) = high.
  Positional heuristics (active king centralisation) = medium. Used
  later for surfacing priority, silence decisions, educational pacing.
- **Cross-vocabulary lock.** Whenever a principle has a corresponding
  Play-with-Coach lesson in `endgames.json`, the V5 caption pipeline
  MUST use the same display name. Established: `END_RULE_OF_SQUARE`
  → "Rule of the Square", `END_OPPOSITION` → "The Opposition".

## Related memories

- [[pattern-skill-tracking]] — once these principles fire reliably,
  the per-player applied/missed counts feed personalisation
- [[v5-lazy-generation-mechanic]] — version bumps required per
  principle launch
- [[per-fire-audit-pattern]] — audit discipline non-negotiable
- [[sub1500-memory-anchors]] — 1200-1500 remember NAMED principles;
  every endgame principle MUST have a memorable name + geometric anchor
- [[no-yes-man]] — don't claim a principle "fires correctly" without
  a per-fire audit
