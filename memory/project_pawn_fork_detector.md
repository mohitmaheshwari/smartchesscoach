---
name: pawn-fork-detector-backlog
description: "Backlog. Add a \"creates pawn-fork-against-self geometry\" shape detector + verifier. Mohit fb_eb1d11ba227f exposed the gap on game move 8 (Qd6)."
metadata: 
  node_type: memory
  type: project
  originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---

The 23-pattern shape catalog covers Knight/Bishop/Rook fork but NOT
"your move puts two of your pieces on squares attackable by a single
enemy pawn push." Mohit feedback `fb_eb1d11ba227f` (2026-05-16) flagged
the canonical case:

- Move 8: black plays Qd6 → black queen on d6, black knight on f6
- e6 pawn sits between them on rank 6 (doesn't defend the squares)
- White's e4-e5 push attacks BOTH d6 and f6 — pawn fork wins material
- White instead played exd5 (still good but missed the fork);
  user got lucky

The V5 pipeline correctly marked Qd6 as severity=blunder with
cp_loss=902, and fired OP_QUEEN_OUT_EARLY. But it never named WHY the
queen was bad in this specific position — the geometric pawn-fork
threat. A 1200 player learns "don't queen out early" from this but
NOT "putting pieces on the same rank 2 squares apart invites pawn
forks" — the actual transferable pattern.

**Why:** Pawn-fork-against-self is one of the most common tactical
losses for 800-1500 players. Not naming it leaves the principle
abstract ("queen gets chased") instead of geometric ("d6 and f6 are
e5-pawn-fork range"). [[sub1500-memory-anchors]] says <1500 players
remember named geometric shapes — this shape isn't yet in our catalog.

**How to apply:**
- New shape pattern entry in [services/shape_patterns.py] with
  `dynamic_policy: "pawn_push_simulated"` (similar to
  back_rank_trap's `mate_in_1_simulated`): simulate every legal
  opponent pawn push, see if it attacks two of mover's pieces, fire if so.
- New detector in [services/shape_detectors.py] — find every pair of
  the mover's pieces 2 squares apart on the same rank, check if any
  enemy pawn can push to the attacking square.
- New verifier in [services/shape_layer.py] under
  `_DYNAMIC_POLICY_VERIFIERS` that confirms the push actually attacks
  both pieces (no occlusion, no defender of the push square that
  makes the capture losing).
- The detector should fire on the move that CREATES the geometry
  (Qd6 in the case above), not on the punishing pawn push.

**Estimated cost:** ~half day of detector + verifier + per-fire audit
on the V5 corpus. See [[per-fire-audit-pattern]].

**Related gaps in same flag:**
- Move 9 exd5 had `best_move_san: null` even though `e5` was the
  obvious refutation. V5 facts extractor isn't capturing the best
  move on opp_blunder moves. Separate fix.

Status: backlog. Don't start until after style-layer modularization
in [[caption-voice-evolution]] Phase 1 — that work has higher impact.
