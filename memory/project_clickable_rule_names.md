---
name: clickable-rule-names
description: Named principles + shape patterns in captions should be clickable. Tapping the name opens a rule-info surface (definition, geometric anchor diagram, real-game examples). Closes the "first time seeing this rule" gap for 1200-1500 players.
metadata:
  type: project
---

Mohit (2026-05-17) flagged after reviewing the Phase 2 audit captions: every time a caption uses a named rule ("Rule of the Square", "Pawn Fork", "The Opposition", etc.), the name should be a click-target. Clicking opens a learn-this-rule surface so the player isn't expected to already know the rule.

## Why this matters

Direct application of `[[sub1500-memory-anchors]]` — 1200-1500 players remember named principles, geometric shapes, and process habits. But for them to remember a rule, they must first LEARN it. The caption alone surfaces the name; the click is the on-ramp to actually understanding the rule.

Pairs naturally with `[[named-rule-real-game-examples]]` — the clickable surface is the entry point; the real-game examples are part of what shows up inside.

## Backend status (mostly ready)

The V5 move record already carries the metadata needed:
- `principle_id_used` — e.g., `"END_RULE_OF_SQUARE"` (the canonical ID, frontend uses for routing)
- `caption_facts_principles_violated[].principle_id` — list when multiple fire
- `shape_pattern_id` / `shape_pattern_name` — for Tier 3 shape-pattern hits
- Resolver decision dict (server-side) includes `anchor_name` — the display string

**Blocker:** as of 2026-05-17 the resolver's `anchor_detail` text never reaches the polish prompt — the polish draft is the legacy R12 renderer output, so captions don't actually contain the rule name. Fix the deterministic_draft sourcing first ([[v5-caption-rewrite-no-patches]] gate applies — needs Mohit signoff).

## Frontend work (when backend ready)

1. **Caption renderer** — when displaying a caption, find substrings matching the move record's `anchor_name` (or the names from `caption_facts_principles_violated`), wrap each match in a clickable component (button/link).
2. **Rule-info modal** — opens on click, keyed by `principle_id_used` (or shape_pattern_id). Renders:
   - Rule name + one-line definition
   - Geometric diagram (mini-board showing the canonical shape)
   - 2-3 real-game examples (sourced via [[named-rule-real-game-examples]])
   - "Practice this" CTA → puzzle / lesson if available
3. **Content source** — one entry per principle/shape in a content collection (or static JSON). Cross-reference `endgames.json` vocabulary for endgame rules per `[[no-parallel-surfaces]]`.

## Open questions

- Visual treatment of clickable rule name: underline + cursor:pointer? Hover preview? Distinct color? Needs a 1200-test pass (does the link affordance read clearly without distracting from the chess content?).
- Tap target on mobile chessboard sidebars: the caption text is small. Either make the entire rule-name word a generous tap target, or add an info-icon adjacent to it.
- Anchor scoping: only the first occurrence of the name is clickable, or every occurrence? First-only avoids dead clicks in repeated mentions.
- Multi-principle moves: when 2+ principles fire (e.g., Walloo21 has both DEF_WALK_KING and END_RULE_OF_SQUARE), only the resolved primary anchor is in the caption text. Surface secondary anchors via a separate UI element ("also: Walk the king") — not by stuffing the caption.

## Dependency chain

```
1. Fix deterministic_draft sourcing in caption_priority_resolver.py
   (so caption text actually contains anchor_name)
   [BLOCKER — see [[v5-caption-rewrite-no-patches]]]
        ↓
2. Implement clickable-rule frontend component
        ↓
3. Implement rule-info modal + content
        ↓
4. Wire real-game examples per [[named-rule-real-game-examples]]
```
