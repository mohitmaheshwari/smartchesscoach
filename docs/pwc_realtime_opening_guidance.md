# PWC Real-Time Opening Curriculum Guidance — Spec

**Status:** DRAFT v1 — awaiting Mohit sign-off.
**Version:** v1 (2026-06-02).
**Scope:** medium of the three PWC specs; ~half-day to ship.

---

## 1. The problem

PWC consults `opening_curriculum.json` only at **two checkpoints** during a session: pre-game (the route handler in `routes/coach_play.py` loads it for opening identification) and post-opening (the `get_opening_theory_note()` call at [realtime_coaching_feedback.py:1471](backend/services/realtime_coaching_feedback.py#L1471) attaches a sidebar note).

During the actual moves of the opening, PWC says nothing curriculum-anchored. A user playing the Italian Game's standard book moves gets no real-time validation, no "in this line, the principled developer is Bc4", no warning when they're about to deviate from theory. They just get the generic shape/trap detectors and the engine eval.

For a premium coaching feature, the user expects to feel taught *through* the opening. The curriculum data is there. The wiring is what's missing.

---

## 2. The shape

Wire `opening_curriculum_engine.get_opening_guidance()` into the per-move feedback loop. For every move within the opening phase (move_number ≤ 12 by default):

1. **Look up curriculum for the current opening + move number.** Returns: `{move_san, idea, principle, common_mistakes, next_book_moves}`.
2. **Compare user's played move to curriculum's recommendation.**
3. **Emit one of three flavors of coaching nudge:**

   | User move vs curriculum | Coaching response |
   |---|---|
   | **Matches book** (played == recommended) | One-line confirmation + the `idea`. E.g., "Nf3 — keeps the f3 square ready for the knight and prepares O-O. In the Italian, develop the kingside first." |
   | **Plays a curriculum alternative** (one of `next_book_moves` but not the top pick) | Pointer note: "{played} is also fine here — the most-played line is {top}, which {top_reason}. Either keeps the opening on book." |
   | **Deviates from book entirely** | Soft warning: "{played} steps outside the {opening} main line. The book move is {top}, which {top_reason}. Deviation is fine if you have a reason, but you'll get less guidance from here." |

4. **Stop at the curriculum's `last_book_move` for that line.** Once the user is out of book (either by their move or by the curriculum running out of authored guidance), the opening-guidance nudges silence themselves and per-move feedback falls back to existing shape/trap/curriculum-note behaviour.

---

## 3. Where the change lands

[backend/services/realtime_coaching_feedback.py](backend/services/realtime_coaching_feedback.py):

The existing `get_opening_theory_note()` (line 1471) is a *post-opening summary*. The new live guidance is a *during-opening primary nudge*. They're different surfaces — one fires per move within the book, the other fires once at the transition out of book.

Add a new function `get_live_opening_nudge()` in [backend/services/opening_curriculum_engine.py](backend/services/opening_curriculum_engine.py):

```python
def get_live_opening_nudge(
    move_history: List[str],
    move_number: int,
    user_color: str,
    played_san: str,
) -> Optional[LiveOpeningNudge]:
    """Returns a per-move coaching nudge based on curriculum, or None
    when out of book / no curriculum hit / not user's color's turn."""
```

Call this from `realtime_coaching_feedback.py` BEFORE the shape/trap layer (curriculum-anchored teaching wins over generic geometry inside the opening). When `LiveOpeningNudge` returns non-None, it becomes the primary coaching message; shape/trap nudges run as a secondary line.

---

## 4. Data the curriculum needs

`opening_curriculum.json` already has per-opening move sequences. For each move, the spec needs four fields:

| Field | Current state | Notes |
|---|---|---|
| `move_san` | ✓ Present | The recommended book move at this ply |
| `idea` | ✓ Present | Short reason ("develops knight + controls center") |
| `principle` | ⚠ Partial | Universal teaching ("In open positions, knight before bishop"). Some entries missing it. Need a coverage pass. |
| `next_book_moves` | ✗ Missing | List of alternative book continuations + their reasons. Need to author. |

**Pre-shipping data work:** add `principle` to any entry missing it (estimate: ~30 entries) and add `next_book_moves` to the top-10 most-played openings (estimate: ~50 entries authored). This is a separate task gated by Mohit's review of the authored content.

---

## 5. Voice rules to apply

Per [memory/feedback_caption_voice_avoid_chess_jargon] — these run through `/check-voice`:

- Name the square, not the concept ("Bc4 to e6 diagonal", not "fianchetto-prep")
- No `book` as jargon — say "the main line of the {opening}" or "the principled move"
- Keep the universal principle at the end ("In open positions, knight before bishop")
- Avoid `tempo` in middlegame contexts; OK in endgame-ish openings (queen out early)

Each authored `idea` and `principle` text goes through `/check-voice` before shipping.

---

## 6. Testing strategy

1. **Stateless probe** `probe_live_opening_nudge.py` — feed synthetic move sequences from 3-4 openings and check that the right nudge fires for matches, alternatives, and deviations.
2. **Per-opening regression**: snapshot the 8-12 most-played openings in our analyzed corpus, capture which moves produce which nudges. Re-run after data-authoring passes to verify no regressions.
3. **End-to-end on a real PWC session** (local dev): play through Italian Game, Sicilian, Queen's Gambit, French. Walk through 8-12 moves of each. Capture nudges; eyeball voice quality.

---

## 7. Risk + rollback

**Blast radius:** narrower than spec #1 (skill-aware coaching) — only affects moves where the curriculum has a hit, only in the opening phase. Most users will see ~6-10 nudges per game.

**Failure modes:**
- Wrong curriculum entry: nudge says "the book move is X" when X isn't actually the main line. Mitigated by the data-authoring review pass.
- Curriculum coverage hole: only top-10 openings authored well, the long tail of B-list openings (Bird's, Larsen, etc.) gets no live guidance. Acceptable — silence is OK in opening tails.
- Over-nudging: every single book move getting a confirmation line could feel chatty. Mitigated by a per-game cap (default: 5 confirmations max, then default to silence on remaining book moves).

**Rollback:** env var `PWC_LIVE_OPENING_NUDGE_ENABLED` (default false on first ship). Disabling reverts to today's post-opening theory note only.

---

## 8. Implementation order

1. **Audit existing curriculum data** for `principle` coverage. Surface entries missing it.
2. **Author `next_book_moves`** for the top-10 openings. ~50 entries. Each goes through `/check-voice`.
3. **Add `get_live_opening_nudge()` to opening_curriculum_engine.py.** Unit-tested.
4. **Wire into realtime_coaching_feedback.py** behind env var, default off.
5. **Stateless probe + regression snapshots** before flipping the flag.
6. **A/B with Mohit + Parth.** Two PWC games each across 3-4 openings. Eyeball quality.
7. **Default on** after one week of clean usage.

---

## 9. Interaction with Spec #1 (skill-aware coaching)

If both #1 and #2 ship: skill-aware gate runs LAST in the coaching pipeline. So a curriculum nudge for `defend_fried_liver` might be suppressed by the skill gate if the user has mastered that skill (applied ≥ 3, wrong/seen < 0.2). That's the correct ordering — curriculum teaches the lesson, skill gate decides whether the user still needs to be taught.

---

## 10. Out of scope

- Variation trees: the spec only covers main-line book moves, not deep variation analysis. Adding variation coverage is a curriculum-content scope, not pipeline scope.
- New openings: this spec doesn't add openings to the catalogue. Existing ones in `opening_curriculum.json` are the universe.
- Out-of-book guidance: once the user (or the game) leaves book, generic shape/trap nudges take over — no replacement for "what should I think about now" in the middlegame.
