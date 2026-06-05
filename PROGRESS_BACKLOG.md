# Progress Page Backlog — Filed for Future

Items surfaced during the 2026-06-05 Engine 2 deploy session that aren't already covered by a scope document. Each entry is a problem statement, not a fix — design before implementing.

See also: [CAPTION_BACKLOG.md](CAPTION_BACKLOG.md) for caption-voice items, [docs/mastery_panel_cleanup_scope.md](docs/mastery_panel_cleanup_scope.md) for the "Not started" override scope (separate, in active review).

---

## 1. Scholar's Mate lesson PGN runs past the teaching moment

**Status:** Filed 2026-06-05. Mohit caught it via MasteryPanel evidence modal on the "Defend against Scholar's Mate" entry.

**Symptom:** The lesson title says "Defend against Scholar's Mate" but the PGN shown extends 5+ moves past the threat resolution:

```
1. e4    e5
2. Qh5   Nc6
3. Bc4   g6
4. Qf3   Nf6    ← threat is dead here (queen pushed to f3, Nf6 covers f7)
5. c3    Bc5
6. b4    Bb6?
7. a4    a6
8. d3    d6
9. h3
```

Moves 5-9 are middlegame play unrelated to the Scholar's Mate scenario. A user reading the lesson reasonably asks "wait, where's the mate?" — the teaching moment is gone by move 4.

**Why filed not fixed:** the lesson content lives in `data/coaching/` or similar; trimming the PGN is a one-line content fix but the broader question is "for every lesson, where does the teaching moment end and how do we mark it?" That's a content-curation question, not an engineering one. Design once for all lessons, not ad-hoc for this one.

**Concrete fix sketch:**
- Mark each lesson with a `teaching_moment_ends_on_ply` field
- Renderer truncates the PGN at that ply by default
- Optional "show full game" toggle for users who want context

**Adjacent concern (file separately if confirmed):** the evidence modal credited "Nf6 on move 4" as a Scholar's-Mate defense in 3 different games. Nf6 on move 4 in a `1.e4 e5` game is normal knight development — it only counts as Scholar's-Mate defense if the opponent attempted the mating sequence (`Qh5`, `Bc4` aimed at f7, etc.). Need to probe the 3 games to see whether the opponent actually attempted Scholar's Mate, or whether the detector is crediting on any Nf6 in a `1.e4 e5` game.

**When to design:**
- After signing off the MasteryPanel cleanup scope (which is the current active product work)
- Or now if Mohit prioritizes the lesson trust gap

---

## 2. MasteryPanel "Not started" framing for skills already demonstrated (in scope)

**Status:** Scope doc shipped 2026-06-05 → [docs/mastery_panel_cleanup_scope.md](docs/mastery_panel_cleanup_scope.md). Awaiting Mohit sign-off + 4 open-question decisions before code.

**Symptom:** "Develop your pieces — Not started · Study" rendered on a 165-game player who develops pieces every game. Reads as patronizing.

**Status:** in scope, this entry is just a pointer.

---

## 3. PWC Mastery Gate artifact-mastery cleanup (shipped fix is partial)

**Status:** Filed 2026-06-05. Tonight's `42f4b0be` fix covered the obvious bugs (slipping logic + dead-namespace filtering). The deeper issue remains: 749 of 763 `mastered_at` stamps in `user_concept_understanding` are from the 2026-06-04 one-shot backfill, meaning many "mastered" concepts may not reflect genuine in-game streak accumulation.

**Why filed not fixed:** the Path C scope (`docs/pwc_mastery_gate_scope.md`) explicitly noted this as a V1.1 concern. Cleanup needs `/scope-driven-development` + `/lock-via-data` work to:
- Define the criterion for a "real" mastery (e.g. N actual clean games AFTER the most recent violation)
- Lock the threshold against the actual distribution of clean-game spacing
- Run a one-time cleanup pass that strips `mastered_at` from rows that don't meet the stricter rule
- Let natural events re-master the legitimate ones over 2-4 weeks

**When to design:** ~2 weeks after deploy (let natural events accrue first so the distribution is meaningful, not backfill-dominated).
