# Opening Source Consolidation — Scope

## ★ FINAL VERDICT (2026-06-17, after full data inspection)

**A big openings merge is NOT warranted.** Verified field-by-field, the "3-source duplication" is largely a mirage — every source is purpose-built and they share essentially only the family **name**:
- `opening_book` (66) = move→caption recognizer (unique caption text).
- `opening_theory_tree` (27) = theory lines / critical positions.
- `opening_curriculum` (24) = repertoire setup_order / golden_rules / lessons.
- tree↔curriculum real overlap = `name` only (plans are different text for different purposes).
- curriculum traps vs traps.json = 11 shared *names* but different schema/purpose (avoid-warning vs execute-line) — not a redundant copy.

**The only genuine cross-source duplicate is family IDENTITY** (name + aliases + eco), independently declared across ~6 places (tree keys, curriculum keys, opening_book names, traps.json keys, eco_openings, normalizer `_PRIORITY_MATCHES`) — which is why `opening_normalizer` exists to paper over "Grunfeld/Gruenfeld/Grünfeld" drift. The defensible fix is a small **family-identity registry** (id→name/aliases/eco/color) that surfaces reference for identity, while each keeps its own purpose-specific content. Low-to-medium value (kills name-drift; lets a future "add-an-opening" scaffold key off it). The rich KBs are NOT merged.

**The user's real pain** ("multiple files to add a new opening") is NOT a single-source violation — it's that 3 surfaces need genuinely different content. The fix for *that* is a **scaffold/generator** (one command stubs entries in all relevant files), not a merge.

**Recommendation:** close the big-merge plan. Optionally build the small family-identity registry and/or an add-opening scaffold. Everything below is superseded by this verdict (kept for the audit trail).

### ✅ DELIVERED: add-opening scaffold (`scripts/add_opening.py`)

One command stubs schema-correct entries for a new opening across all sources with a SINGLE identity (guards against duplicate/drift):
```
python scripts/add_opening.py --name "Vienna Game" --color white \
    --moves "e4 e5 Nc3" --eco C25 --caption "Vienna Game. ..." --apply
```
Writes stubs to `opening_theory_tree.json` (theory), `opening_curriculum.json` (repertoire), `traps.json` (canonical traps home, `[]`), and the `_OPENINGS` recognizer in `opening_book.py`; leaves TODO placeholders for content. Dry-run by default; aborts if the opening already exists. This addresses the real pain ("multiple files per new opening") without merging the purpose-built KBs. Family-identity registry NOT built (low value) — revisit only if name-drift actually bites.

---

**Status:** SUPERSEDED by the Final Verdict above. No code until Mohit approves.
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

## 1b. Phase-1 DATA FINDING (2026-06-17) — design revised

Ran `scripts/analyze_opening_sources.py` (normalizes every entry to a family via `opening_normalizer`). The sources are **two granularities, not three copies of one list**:

- **`opening_book` (66 entries)** = fine-grained move-sequence → caption. **25 normalize to "Other"** — specific lines (Bowdler, Giuoco, Two Knights…) with no family-level equivalent. Its **captions are unique** (the review-caption text nothing else has).
- **`tree` (27) + `curriculum` (24)** = coarse **family**-level knowledge. **9 families appear in both** — this is the genuine duplicate (same family name + plans/golden_rules stored twice).

**Implication:** merging all three into one FEN-keyed file (original §2 plan) is the WRONG shape — it flattens a legitimate two-layer design. Revised target below.

## 1c. Phase-1b DEEPER FINDING (2026-06-17) — "Layer A merge" is NOT warranted

Inspected shared families field-by-field (e.g. `italian_game` in both tree + curriculum):
- **tree fields:** name, eco_prefix, main_line, white_plan, black_plan, critical_positions, variations, move_ideas (THEORY).
- **curriculum fields:** name, color, summary, difficulty, setup_order, golden_rules, traps, tree, middlegame_plans, endgame_tips (REPERTOIRE/LESSONS).
- **Real overlap = the `name` only.** Plans are different *text* for different purposes. Merging tree+curriculum would FUSE two purpose-built KBs, not de-duplicate. **Do not merge them.**

**The genuine duplicate is TRAPS, not family theory:** `opening_curriculum.json` embeds **13 traps, 11 of which already exist in the canonical `data/traps.json`** (Fried Liver, Legal's Mate, Elephant Trap, Englund Gambit, Caro-Kann Smothered Mate, Magnus Smith, …). Same trap, two files.

**Corrected Layer-A target:** make `opening_curriculum_engine` read traps from the canonical `traps.json` (via `trap_library`) and **remove the embedded `traps` arrays from `opening_curriculum.json`**. The only other (minor) shared fact is the family `name` — optional tiny family-identity registry, low priority.

### (the two-layer target below is superseded by 1c — kept for history)

## 2. Target state — REVISED (two layers, each single-source)

**Layer A — Family knowledge base (the real duplicate to kill):** merge `tree` + `curriculum` into ONE family-level source (name, eco, white/black plans, golden_rules, repertoire setup_order, main_line, critical_positions, FEN patterns). ~30 families. PWC + tracking read this. *Adding a family = one edit here.*

**Layer B — Recognition→caption index:** `opening_book` stays as the fine-grained move-sequence→caption recognizer (it's a different job/granularity), BUT references Layer-A families by id instead of re-storing family names/plans. Its per-line **captions remain** (unique). *Adding a recognized line+caption = one edit here.*

The duplication we kill: the same FAMILY's facts living in BOTH tree and curriculum. The cross-layer link is by id, not copied data. "One edit" holds *within each layer*; a new family flows to PWC+tracking from one edit, a new recognized caption-line flows to review-captions from one edit.

### (original single-canonical target — superseded by the finding above)

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
