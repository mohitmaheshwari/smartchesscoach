# Subtypes for all 8 remaining cognitive_gap tags — Scope

**Date:** 2026-07-02
**Author:** Claude (Mohit approved "go")
**Status:** Building.

## Problem

Only `piece_safety` has subtypes + board verification. The other 8 tags
fall through to a generic "detailed subtype breakdown will populate as
more games get analyzed" — that's an embarrassing punt in a paid
coaching product. Parth's active weakness right now shows this exact
message.

## What we're building

Subtype taxonomy + board-verified classifier for each of these 8 tags:
`king_safety`, `missed_tactic`, `tactical_oversight`, `calculation_depth`,
`piece_activity`, `opening_knowledge`, `endgame_technique`, `pawn_structure`.

Same architecture as piece_safety:
- 3-5 subtypes per tag
- Each subtype derives from board evidence (python-chess)
- Base severity per subtype, contextual promotion via same rules
- Verified-true rate ≥85% on 30-sample sample per subtype per user
- Subtypes that can't hit 85% are labeled `unverified_hint` with softer
  narrative language (honest silence over fake certainty)

## Taxonomies (subject to verification passing)

### king_safety
- `king_in_center` — king still on starting square past move 12 with ≥3 central pawn exchanges
- `weakened_shelter` — f/g/h pawn (or a/b/c mirror) pushed without castling, opp attackers on that flank
- `ignored_king_attack` — opp piece attacking within 2 squares of user's king, user's move didn't address it
- `king_walked_into_attack` — user king move to a square with more attackers than defenders

### missed_tactic
- `missed_fork` — engine best move creates ≥2 attacks on opp pieces ≥300cp each
- `missed_pin` — engine best move creates a pin on an opp piece
- `missed_skewer` — engine best move creates a skewer through opp piece
- `missed_discovered_attack` — engine best move uncovers attack from another piece
- `missed_generic_tactic` — engine best has cp_gain ≥200 but doesn't match specific patterns

### tactical_oversight
- `ignored_forcing_threat` — opp's previous move was forcing (capture/check), user's move didn't address it
- `overlooked_immediate_reply` — opp's next move is a forcing reply with cp gain ≥300
- `defender_removed_first` — opp captured user's defending piece, then user's defended piece

### calculation_depth
- `2ply_forcing_win` — opp's next 2 moves are forcing and win ≥300cp material
- `broken_forcing_sequence` — user's move breaks a multi-move forcing sequence they started

### piece_activity
- `piece_parked_on_start` — a user piece (N/B/R) has not moved for ≥8 moves since opening (≥move 10)
- `queen_out_early` — user queen moves before development is complete (move ≤8, other pieces still home)
- `worst_piece_not_activated` — hard to verify at 85%; ship as `unverified_hint`

### opening_knowledge
- `theory_deviation_early` — user's move within first 8 moves is not in book (uses existing opening_book service)
- `tempo_wasted_by_repeat` — user moved same piece twice in first 10 moves without capture
- `early_flank_pawn_move` — user pushed f/g/h/a/b/c pawn ≥2 squares in first 8 moves

### endgame_technique
- `passive_king_in_endgame` — endgame (≤6 pieces per side, no queens), user king further from board center than opp king by ≥3 squares
- `traded_into_lost_endgame` — user's move is a capture leading to KP endgame with material deficit ≤-100
- `passed_pawn_ignored` — opp has a passed pawn advancing, user's move doesn't address it

### pawn_structure
- `isolated_pawn_created` — user pawn move creates isolated pawn (no friendly pawn on adjacent files)
- `doubled_pawn_created` — user pawn move (capture usually) results in doubled pawns for user
- `backward_pawn_created` — user pawn move creates a backward pawn (behind adjacent-file friends, can't advance safely)
- `chain_broken` — user pawn move breaks their own pawn chain

## Severity mapping

Same schema as piece_safety:
```
Base severities (subtype → severity):
  All specific-detected subtypes: base=moderate
  All king-safety attack subtypes + tactic-missed subtypes: base=critical
  All "ignored" subtypes: base=critical (like threat_ignored in piece_safety)
  All "generic" fallbacks: base=minor
Promotion rules (same as piece_safety):
  A. execution_quality == "blunder" → +1
  B. Immediate material loss ≥300 → +1
  C. cp_loss ≥400 AND eval_before ≥-300 → +1
Cap at "critical".
```

## Verification bar

For each subtype:
1. Sample 30 events from the corpus classified as that subtype
2. Board-verify each with python-chess against the taxonomy rule
3. Report verified-true / verified-false / uncertain
4. **If verified-true ≥ 85% → ship**
5. **If <85% → tighten the rule OR relabel as `unverified_hint`
   (soft narrative: "we noticed a pattern in your play but couldn't
   verify the specific type")**

No subtype is shipped with a hard label if it can't clear 85%. Better to
soften the language than fake certainty (per
`feedback_verify_with_own_perspective.md`).

## Rollout

1. Write classifier module for all 8 tags
2. Bump SCHEMA_VERSION to 7
3. Backfill Parth + Mohit + 3 other users covering all rating bands
4. Board-verify — measure verified-true rate per subtype
5. Iterate any below 85%
6. Full corpus backfill
7. Reassign focuses so users get the enriched narratives
8. Commit + push

## Non-goals

- Sub-typing patterns that would require a full engine PV walker beyond
  what's already in `move_evaluations` (deferred — needs analyzer changes)
- Multi-move sequence detection beyond 2-ply (deferred)
- Positional-judgment subtypes that can't be board-verified at 85%
  (they ship as `unverified_hint` with softer language)

## Acceptance

- All 8 tags have at least ONE subtype ≥85% verified-true
- Users whose winner is any of the 8 tags now get an evidence-driven
  narrative (not the generic placeholder)
- Parth's active focus (king_safety) becomes actionable
