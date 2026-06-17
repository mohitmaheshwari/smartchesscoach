# Opening Source Consolidation — Scope

**Status:** Draft for sign-off. No code until Mohit approves.
**Date:** 2026-06-17
**Why now:** Adding one new opening currently requires editing up to **3 separate sources** across 2 JSON files and 1 hardcoded Python list. The original "one edit" directive ([[project_opening_tracking_one_edit]]) was only ever implemented for the tracking subsystem; the caption and PWC subsystems each kept their own opening list. This scope makes "add an opening = one edit" true across **all** surfaces.

---

## 1. Current state (the problem, in plain English)

The same concept — "what opening is this, and what should the player know about it" — is stored in **three independent places**, each feeding a different surface:

| Source | Items | Keyed by | Read by | Surface |
|---|---|---|---|---|
| `data/opening_curriculum.json` | 24 | move sequence | `opening_lookup`, `opening_curriculum_engine` | Skill-tree / repertoire tracking |
| `data/coaching/opening_theory_tree.json` | 28 | **FEN** | `opening_namer`, `opening_theory_lookup`, `opening_theory_json_service` | PWC live opening teaching |
| `services/decryption_voice/opening_book.py` `_OPENINGS` | 67 | exact move order | `caption_pipeline.py` (central layer) | Game-review captions |

On top of those three data sources sit **~5 recognizers** that each answer "which opening is this game playing?" in their own way:
`opening_book.recognize_opening_from_history`, `opening_lookup.match_opening_for_mover`, `opening_namer`, `opening_theory_lookup`, `opening_mastery.detect_opening_from_moves`.

### Consequences
- **Add-cost is 3.** A new opening that should appear in tracking + PWC teaching + review captions = 3 edits, 2 formats (JSON + inline Python), no shared validation.
- **Inconsistent recognition.** `opening_book` matches by *exact move order*, so it misses transpositions (e.g. `1.e4 c5 2.Bc4` is a Sicilian/Bowdler but a different move order to the same position is not recognized). The FEN-keyed `opening_theory_tree` does not have that flaw.
- **Drift.** The same opening can be named/explained differently on different surfaces, and one source can gain an opening the others lack.
- **No single guard.** `opening_sync_check` guards the curriculum subsystem only.

---

## 2. Target state (one canonical source)

**One canonical opening knowledge base, FEN-keyed, that every surface reads.**

Recommended canonical: **`data/coaching/opening_theory_tree.json`** (FEN-keyed), because:
1. **FEN-keying handles transpositions** — the same position is recognized regardless of move order. This is the correctness win; `opening_book`'s exact-move-order matching cannot do it.
2. **PWC already uses it** and `opening_namer` reports it "verified 6/6" — it is the most trusted of the three.
3. It already carries per-position theory (moves + ideas), the richest shape.

Each consuming surface then reads the canonical source through a **single recognizer**:
- **Caption layer** (`caption_pipeline`) reads canonical instead of `opening_book._OPENINGS`.
- **Tracking** (`opening_curriculum_engine`) derives its skill-tree nodes from canonical (or curriculum.json becomes a thin *view* — repertoire grouping + golden_rules — that references canonical entries by id, never re-storing names/ideas).
- **PWC** already reads it — no change.

Adding an opening becomes: **one entry in the canonical JSON.** All surfaces pick it up.

---

## 3. What this scope explicitly covers vs. defers

**In scope:**
- Map every read of all three sources (exhaustive grep).
- Choose + lock the canonical schema (must serve: name, per-position idea/caption, recognition, repertoire grouping for tracking, PWC theory moves).
- Migrate `opening_book`'s 67 entries into canonical (superset merge; de-dupe; keep the best caption per opening).
- Repoint `caption_pipeline` to read canonical via one recognizer.
- Make `opening_curriculum.json` a derived view (or generated) so tracking reads canonical.
- Collapse the ~5 recognizers to **one** canonical recognizer function; others become thin wrappers or are deleted.
- One guard test: "every opening in canonical is recognizable + has a caption; no surface has an opening canonical lacks."

**Deferred / out of scope (note, don't do):**
- ECO full-database import (`eco_openings.json`) — separate effort.
- Rewriting PWC's broader theory teaching.
- Any non-opening duplication (tracked separately — see the duplicate-source audit).

---

## 4. Migration steps (high level, for sign-off — not implementation)

1. **Freeze + map.** Grep every reader of the 3 sources; record exact call sites. (No code change.)
2. **Lock canonical schema** on `opening_theory_tree.json` — confirm it can hold everything the other two need (esp. the review-caption text + repertoire grouping). If a field is missing, add it to the schema first.
3. **Merge data.** Union the 67 `opening_book` entries + 24 curriculum + 28 theory-tree into canonical, FEN-keyed, one caption per opening (pick the best-verified wording). Engine/board-verify each caption survives (no hallucinated claims).
4. **One recognizer.** Write/keep a single `recognize_opening(fen | history)` on the canonical source. Point `caption_pipeline` at it. Make the other recognizers thin shims that call it (or delete + update imports).
5. **Tracking derives.** `opening_curriculum_engine` reads canonical; `opening_curriculum.json` becomes a thin repertoire-grouping view (ids only) or is generated from canonical.
6. **Guard.** Add `test_opening_single_source`: asserts (a) every canonical entry is recognized + captioned, (b) no reader references a retired source, (c) adding an entry needs no second file.
7. **Delete** `opening_book._OPENINGS` (and the duplicate recognizers) once readers are repointed. Update `opening_sync_check`.

**Back-compat:** captions are cached in `decryption_v5_data`; a `V5_COACHING_VERSION` bump forces regen so existing games pick up canonical naming. Flag-gate the caption repoint if needed.

---

## 5. Acceptance criteria

- Adding a new opening = **one edit** to the canonical JSON; it appears in tracking, PWC teaching, and review captions with no other file touched.
- Exactly **one** opening recognizer function in the codebase (others deleted or thin shims).
- A guard test fails if anyone adds a second opening source or an opening that only one surface knows.
- No regression: review captions still name the openings they did before (spot-check the demo game + a London/Italian/Ruy mainline).

---

## 6. Open questions for Mohit

1. Canonical = `opening_theory_tree.json` (FEN-keyed) as recommended? Or keep `opening_curriculum.json` as canonical and add FEN-keying to it?
2. Should `opening_curriculum.json` survive as a thin repertoire-grouping view, or be fully generated from canonical?
3. Acceptable to bump `V5_COACHING_VERSION` (forces caption regen for all games) as part of the caption repoint?
