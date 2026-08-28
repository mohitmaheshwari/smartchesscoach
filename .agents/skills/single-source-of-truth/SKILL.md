---
name: single-source-of-truth
description: Use BEFORE creating any new data file, hardcoded table/dict, recognizer, classifier, namer, or service that encodes a domain concept — and to audit the codebase for existing duplicate sources. Prevents the "same info in N places" disease (the openings sprawl: 3 lists + 5 recognizers).
---

# Single Source of Truth

**Core rule:** information about a domain concept lives in exactly ONE place. Every surface that needs it READS that place — it never stores its own copy. Adding one item must be one edit.

This skill has two modes: **PREVENT** (before you create something) and **AUDIT** (find existing duplication).

---

## MODE 1 — PREVENT (run before creating a new source)

You are about to add a `.json` data file, a hardcoded `_TABLE = [...]` / dict, a JSON of rules/templates, OR a service that recognizes / classifies / names / defines a concept. STOP and do this first:

1. **Name the concept.** "Openings." "Traps." "Cognitive gaps." "Rating bands." "Severity thresholds." "Caption rules."

2. **Search for an existing source** (all three forms — duplication hides in any):
   - Data files: `Glob backend/data/**/*.json` + grep filenames for the concept.
   - Hardcoded tables: `Grep` for `<Concept>\s*=\s*[\[{]`, `_<CONCEPT>`, and the concept's member names (e.g. an opening name, a gap label).
   - Services: `Grep "def .*(recognize|classify|name|detect|match|get).*<concept>"`.

3. **Find the canonical source** = the one the **central/most-trusted path** reads (e.g. for captions, whatever `caption_pipeline.build_move_teaching_decision` reads). If unsure which is canonical, that itself is a finding — there are already duplicates; do not add a third.

4. **Decide — in this order:**
   - ✅ **Source exists and serves the need** → add your item THERE. Done. (One edit.)
   - ✅ **Source exists but can't serve your need** → understand WHY, then EXTEND the canonical source's schema/coverage. Your surface reads it.
   - ⚠️ **Multiple sources exist** → you've found duplication. Do NOT add a 4th. Flag it, pick the canonical one, propose consolidation (scope-driven).
   - ❌ **Genuinely no source exists** → only then create one. Make it the single source; design so others can read it. FEN-key / id-key things that have transpositions/aliases.

5. **Never** copy-paste a concept's entries into a new file "because my surface needs a different shape." Different shape = a *view/derivation* of canonical, or a *new field* on canonical — not a fork.

**Red flags you're about to violate this:**
- "I'll just add a small table here for my use case."
- "The existing one doesn't have a recognizer, so I'll make my own list."  ← this is exactly how openings got 3 lists.
- "It's faster to hardcode these few entries."
- Adding the same item you just added elsewhere (I added Bowdler to `opening_book` AND should have used canonical).

---

## MODE 2 — AUDIT (find existing duplicate sources)

To sweep the codebase (or validate after a change):

1. **List candidate concepts** — anything with domain entries: openings, traps, endgames, cognitive-gap/weakness taxonomy, rating bands, caption rules / principle banks, coaching templates, severity/cp thresholds, puzzle/pattern tags, ECO names.

2. **For each concept, count sources:**
   - `Glob` data files + grep filenames.
   - `Grep` hardcoded tables (`= [`, `= {` near the concept) and member names.
   - `Grep` services that define/recognize/classify it.

3. **For each concept with >1 source, record:**
   - CONCEPT
   - the 2+ sources (paths)
   - what reads each
   - **ADD-COST** = how many files to add one item
   - one-line: "true duplicate" vs "legitimate separate concern" (a *view/index* of canonical is fine; a re-stored copy is not).

4. **Rank by ADD-COST** (worst first). Each true duplicate → a consolidation scope (`docs/<concept>_source_consolidation_scope.md`): pick canonical, migrate others to read it, collapse recognizers to one, add a guard test.

5. **Lock with a guard test** per consolidated concept: "every canonical entry is reachable on every surface; no surface references a retired source; adding an entry needs one file." A failing guard = someone re-forked.

---

## Distinguishing a real duplicate from a legitimate separate concern

- **Duplicate (fix it):** the same *facts* (names, ideas, thresholds, classifications) are stored independently in 2+ places, can drift, and adding one item edits multiple files.
- **Not a duplicate (fine):** a derived **view/index** (generated from canonical, or referencing it by id), a **cache** (regenerable from canonical), or genuinely **different concepts** that happen to share a word. A trainer keyed by chosen-opening (curriculum) vs a recognizer keyed by position are different *jobs* — but if they each re-store opening names/ideas, the DATA is still duplicated and should share one source.

---

## Reference

- Standing rule: [[feedback_single_source_of_truth]]
- Canonical-recognizer pin for openings: [[project_opening_recognizer_canonical]]
- Caption one-source: [[feedback_one_source_of_truth]] / [[project_caption_pipeline_central_layer]]
- Known parallel engine: [[project_pwc_runs_second_coaching_engine]]
- Pairs with `/scope-driven-development` (consolidation needs a signed-off scope) and `/audit-pre-code`.
