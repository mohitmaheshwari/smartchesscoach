# PWC Opening / Trap / Name Wiring — Scope

_Status: DRAFT for sign-off. No code until Mohit approves. (2026-06-09.)_
_Trigger: Mohit playing an Italian in PWC — "there are no openings, traps, name wired
in pwc, see the last game." Confirmed on session `908b8da0`._

---

## Problem (what the user sees)

In a live PWC game that is clearly a named opening, the coach surfaces **nothing about
the opening**: no name ("Italian Game"), no trap warnings, no opening teaching offer.

**Evidence — session `908b8da0`** (1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 — Italian Game / Giuoco
Piano):
- `detected_opening: None`
- `teaching_opening: None`
- `opening_offer_shown: None`, `openings_taught_this_game: None`

So the coaching reads as opening-blind even in textbook theory.

---

## Root cause — it's a WIRING break, not a detection break

1. **The detector works.** `_detect_opening_from_moves(["e4","e5","Nf3","Nc6","Bc4","Bc5"], "white")`
   ([coach_play.py:28](../backend/routes/coach_play.py#L28)) correctly returns
   **`italian_game`**. The curriculum (`opening_curriculum_engine._load_curriculum`,
   20 openings) includes `italian_game`. Detection is fine.

2. **`detected_opening` is the key that unlocks everything downstream — and it's
   almost never written.** A whole-repo search found exactly ONE writer:
   `opening_teaching_integration.py:242`. It did not fire for this game, so
   `detected_opening` stayed `None`.

3. **Everything opening-related gates on `detected_opening`:**
   - **Traps** — `get_applicable_traps_for_moves(detected_opening, ...)` is gated on it
     ([coach_play.py:3203-3212](../backend/routes/coach_play.py#L3203)). `None` → no traps, ever.
   - **Name / teaching** — surfaced from the detected opening.
   - **Postgame** — `opening_played=session_doc.get("detected_opening")` ([coach_play.py:8367](../backend/routes/coach_play.py#L8367)).

4. **The opening logic is fragmented across 3+ overlapping, inconsistently-wired paths:**
   - `/opening-guide` endpoint ([coach_play.py:3673](../backend/routes/coach_play.py#L3673)) runs the
     *working* detector → writes `teaching_opening` (NOT `detected_opening`). It's a
     separate endpoint, not called during normal move play.
   - The move flow calls `check_opening_and_offer_teaching` (7739 / 8078) → writes
     `opening_offer_shown`; it didn't produce an offer for this Italian.
   - Only `opening_teaching_integration.py:242` writes `detected_opening` — and it
     didn't run here.

   Net: the detector that works isn't the one wired to the field that matters, and the
   field that matters (`detected_opening`) is written by a path that didn't fire.

---

## The fix (in scope)

**One wire, in the live move flow:** after 3+ moves, call the working
`_detect_opening_from_moves(moves_san, user_color)` and, when it returns a key,
**persist `detected_opening`** (and `teaching_opening` if unset) on the session — once
per game, idempotent (skip if already set).

That single persistence unlocks the existing downstream, using machinery that already
works:
- **Name** — "Italian Game" available for display + postgame.
- **Traps** — line 3208's `get_applicable_traps_for_moves` starts firing (Italian:
  Fried Liver, etc., from the 18-trap library).
- **Teaching offer** — the offer paths can key off a real detected opening.

### Data: existing JSONs ONLY — create nothing new (Mohit 2026-06-09)
This fix authors **no new data**. It reads files that already exist:
- **`data/opening_curriculum.json`** — the detector's source (20 curated openings +
  trees), via `opening_curriculum_engine`.
- **`verified_opening_traps.py`** (existing verified-trap data) — `get_applicable_traps_for_moves`
  already reads it; we just stop gating it on a `None` opening.
- **`data/eco_openings.json`** — the broad ECO name database, already present, available
  if we want *any* opening named (not only the 20 curriculum ones).

**No new JSON, no new openings, no new traps. Pure wiring over the common data files.**

### Acceptance (what "done" looks like)
On replaying session `908b8da0`:
- `detected_opening == "italian_game"` after move 3.
- The opening **name** surfaces in the coaching/header.
- Trap detection **runs** for the Italian (fires if an applicable trap is on the board;
  silent-but-active otherwise — not dead).
- No regression: a non-curriculum opening still plays fine (detector returns None →
  behaves as today, no crash, no false name).

---

## Out of scope (explicitly deferred)

- **Consolidating the 3+ opening systems into one** (the proper "one source" cleanup).
  Real work; this scope only adds the missing wire so the foundation works. File a
  separate scope for consolidation. (Per [[feedback_one_source_of_truth]] the eventual
  goal is one path — but not in this fix.)
- **Expanding the opening curriculum or trap library** (new openings/traps).
- **New opening teaching UX** (the guided-opening flow lives in the coaching-presence
  scope's adaptive-guidance section).
- **Changing the detector logic** (it works; don't touch it).

---

## Verification plan

1. Unit: `_detect_opening_from_moves` on the Italian → `italian_game` (already confirmed).
2. After the wire: simulate/replay `908b8da0`'s moves through the move flow → assert
   `detected_opening` gets set to `italian_game`.
3. Assert trap detection is reached (not skipped on `None`) for the Italian.
4. Regression: a junk/non-curriculum line → `detected_opening` stays None, no crash.
5. Run `pwc_coaching_lint.py` — no new mechanical defects in any opening captions.

---

## Risks

- **Hot move path.** The wire goes in `_process_move_and_respond` (or the equivalent
  per-move point). Must be idempotent (set once), best-effort (never block a move on
  detection failure), and not conflict with the existing `check_opening_and_offer_teaching`
  / `opening_teaching_integration` writes (avoid double-fire / contradictory state).
- **Two writers of opening state.** After the fix, `detected_opening` may be set by both
  the new wire and `opening_teaching_integration`. Decide precedence (new wire only sets
  when unset; integration path can still upgrade it). Document it.
- **Name accuracy.** The curriculum detector matches the user's line; if the user
  transposes out of the curriculum line, detection may stop — acceptable (name reflects
  the recognised line), but note it.

---

## Why this matters beyond the bug

This is the **foundation for the coaching-presence adaptive-guidance feature**
(`coaching_presence_scope.md` Part 2): "coach detects you struggle in the Italian →
offers a guided opening." That feature *requires* `detected_opening` to be reliably set
in the live flow. Fixing this wire is a prerequisite, not just a cosmetic fix.

---

## Open questions / needs Mohit

- **Precedence** when both the new wire and `opening_teaching_integration` could set the
  opening — new-wire-sets-if-unset is the proposed default; confirm.
- **Should the name show in the header/coaching by default**, or only when a trap or
  teaching moment is relevant? (Restraint vs. always-on naming — ties to the
  "opening name only at critical lessons" rule, [[feedback_opening_name_only_at_critical_lessons]].)
- **Naming coverage:** name only the **20 curriculum openings** (the detector's source),
  or broaden to **any opening** using the already-present `data/eco_openings.json`?
  Either way it's existing data — no new content.

_Resolved 2026-06-09 (Mohit):_ **Use the common existing JSONs only — create nothing new.**
Traps come from the existing `verified_opening_traps` data as-is (trap *content* is NOT
in scope, not a follow-up — we use what's there).

---

## Definition of done for THIS doc

Signed off when Mohit blesses: the one-wire fix, the acceptance criteria, the
out-of-scope list, and the precedence/naming decisions above. Then implement as a
focused, tested change on the move path — verified on `908b8da0` before claiming it works.
