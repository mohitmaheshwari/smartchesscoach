# Scope: Rating-Band Teaching Depth

**Status:** drafted 2026-08-03 by Claude, per Mohit's direction ("first do the doc
triage, so we can know more in details" → "go, do it" on this scope doc).
Real user feedback: captions are too hard for the target audience (players
stuck under 1400, still learning chess) — and it's not just vocabulary, it's
that a true beginner needs a coach who starts from simpler *concepts*, not
the same concept in simpler words.

## 0. Existing surfaces audit

**What already reads `user_rating` / `RATING_BANDS`, verified against live
code (not the docs' own claims — several were stale):**

1. **`deterministic_coach_service.py`** — `RATING_BANDS` (`beginner_low`
   0-999, `beginner_high` 1000-1399, `intermediate` 1400-1799, `advanced`
   1800+), each with a `strictness` float. Most of this file's original
   logic (round-prep, plan-audit) was deleted 2026-07-25; only
   `RATING_BANDS`/`get_rating_band()` remain, imported by
   `coaching_policy.py`, `rating_resolver.py`, `today_composer.py`.

2. **`realtime_coaching_feedback.py`** (PWC live-play coaching) — `user_rating`
   drives three real things:
   - Move-quality classification thresholds (inaccuracy/mistake/blunder
     cutoffs vary by band — the CLAUDE.md-documented "Rating-Aware
     Feedback").
   - Suppression: inaccuracies under 1200 with no substantive contrast are
     silenced entirely rather than shown as filler.
   - Interaction style: `is_beginner` (<1000) skips the Socratic
     "what were you thinking?" question and goes straight to a direct
     reveal; 1000+ gets asked first.

   **What it does NOT do, confirmed by direct read:** `_contrastive_
   explanation()` accepts `user_rating` as a parameter but never references
   it in the function body — the concept-priority tree (hanging piece →
   opponent's free capture → opening principle → tactical pattern) is
   identical for a 650 and a 1750. `user_rating` is threaded all the way
   into `_try_meta_pattern()` → `MetaContext.user_rating` →
   `meta_patterns.py`'s `detect_meta_patterns()`, which also never reads
   it (confirmed via grep — the field is declared, never consumed). The
   plumbing exists everywhere; nothing at the end of it uses rating to
   choose *which* concept or *how much* of it to explain.

3. **`caption_pipeline.py`** (game-review captions, the system worked on
   earlier today) — `user_rating` drives exactly one thing: the
   post-mistake "recovery phrasing" block (lines 2162-2187), a 3-tier
   suggestion ladder (<1000 / <1400 / else) for what to look for after a
   blunder. Every other caption in the review system — R08-R12, the
   distilled/verified caption layers, today's jargon sweep — is rating-blind
   past this one narrow slot.

4. **`pwc_skill_gate.py`** (`docs/pwc_skills_aware_coaching.md`, confirmed
   live in today's backlog triage) — downgrades/escalates coaching per
   concept based on *demonstrated mastery* for that specific user, not
   rating band. A different, complementary axis — "have you personally shown
   you know this" vs. "what does a player at your general level need." Not
   overlapping; should coexist, not be replaced.

5. **Puzzle/training difficulty scaling** (`DifficultySelector.jsx`,
   confirmed done in today's triage) — controls *which puzzles* get served,
   not how a mistake or caption is *explained*. Different surface.

**Overlap vs. genuine gap:** the rating-band infrastructure (`RATING_BANDS`,
`get_rating_band()`, `user_rating` threading) is pervasive and already
piped into exactly the places a depth feature would need it. The gap is
narrow and specific: nothing currently uses any of that plumbing to vary
*which concept gets taught* or *how many layers of "why" get included*.

**Decision: EXTEND, not PARALLEL.** Reuse `RATING_BANDS`/`get_rating_band()`
— do not invent new tiers or a second rating-threshold system. Extend the
already-threaded-but-unused `user_rating` parameter in both
`realtime_coaching_feedback.py` and `caption_pipeline.py` to actually drive
depth selection, through one shared depth-selection layer both call (not
two separate implementations — ties to the standing "one source of truth
for coaching" rule).

## 1. What it is

Right now, when the coach explains a mistake, it picks the same underlying
concept and explains it the same way regardless of whether the player is
650 or 1700 — only the vocabulary changed (today's jargon sweep) and
whether it's asked as a question first. This feature makes the *actual
explanation* simpler for lower-rated players — fewer, more foundational
concepts, not just softer words — and lets it go a layer deeper for
stronger players, reusing the rating-band system already used everywhere
else in the app.

## 2. What the user sees

Same real mistake (a knight on d7 hangs to a bishop already eyeing that
square, and the knight was the only defender of a pawn on e5), rendered at
each existing rating band:

**beginner_low (600-999)** — one fact, one rule. Nothing else.
> "Nd7 leaves your knight on d7 undefended — White's bishop takes it next
> move. Before every move, check: can any enemy piece capture one of mine
> for free?"

**beginner_high (1000-1399)** — fact + rule + one layer of *why the square
was unsafe*.
> "Nd7 runs into Bxd7 — the bishop was already watching that square from
> c6, so nothing defended the knight there. Before you move a piece, check
> whether the square you're moving to is already being watched by an enemy
> piece."

**intermediate (1400-1799)** — fact + why + the second-order consequence.
> "Nd7 hangs the knight to Bxd7 — the bishop's diagonal from c6 was already
> live, so d7 was never safe. Beyond the piece, this also gives up your
> last defender of the e5 pawn, so Qxe5 follows next, turning a one-piece
> loss into a much bigger problem."

**advanced (1800+)** — terse, assumes more, closer to today's existing tone.
> "Nd7?? Bxd7 costs the piece and, worse, e5 falls next (Qxe5) since d7 was
> its only defender. Nc4 kept both the knight and e5 covered."

The beginner_low version is not a shorter version of the advanced one — it
genuinely contains one idea instead of three.

## 3. In scope (V1)

- Extend `realtime_coaching_feedback.py` and `caption_pipeline.py` to select
  concept depth (not just severity/suppression) via one shared depth-tier
  function keyed off the existing `get_rating_band()`.
- **Pilot on `piece_safety` only** — the highest-frequency cognitive-gap
  category at exactly this audience's rating range (per CLAUDE.md's own
  gap table, 600-1200 typical). Prove the pattern on one category before
  expanding.
- Both PWC live coaching and game-review captions read the same depth
  logic — one implementation, not two.
- Reuse `RATING_BANDS` thresholds as-is. No new bands.

## 4. Explicitly out of scope (V1)

- Interaction style (Socratic-vs-direct) — separate, already-working
  mechanism, untouched.
- Severity thresholds — already tuned, untouched.
- Every other cognitive_gap category (king_safety, tactical_oversight,
  calculation_depth, etc.) — follow-on work after the pilot validates.
- Puzzle difficulty selection — different surface, already handled.
- Wiring together with `pwc_skill_gate.py`'s per-concept mastery
  downgrade — the two axes should eventually compose, but that integration
  is not V1.
- Retroactively rewriting existing R08-R12/distilled templates for
  non-piece_safety categories — they keep serving as-is until their own
  pilot.

## 5. Success criteria

- **Primary (launch gate):** a real rubric check on N actual piece_safety
  mistakes rendered at all 4 bands — beginner_low version contains exactly
  one idea with zero second-order concepts; advanced version contains at
  least one idea absent from beginner_low. Checked by Mohit against real
  positions, not self-graded.
- **Secondary (post-launch, lagging):** repeat-mistake rate specifically on
  piece_safety, before vs. after, for users in beginner_low/beginner_high —
  needs real usage time to read, not a V1 launch condition.

## 6. Open questions

- **Does PWC (live, time-pressured) use the same depth tiers as game
  review (post-game, reflective), or does live play need a length cap
  regardless of rating?** A wall of text mid-game is bad UX even for a
  beginner. Leaning toward "same tiers, but PWC caps total message length" —
  needs Mohit's call, not a guess.
- **Does `intermediate` get a genuinely new tier, or does it stay as
  today's existing default text** (with new tiers only added below/above
  it)? The mockup above assumes intermediate gets upgraded content
  (fact+why+consequence); confirm that's wanted vs. leaving it untouched.
- **Confirm `piece_safety` as the V1 pilot category** — recommended for
  frequency + clarity, but not yet signed off.

## 7. Pre-code requirements

- Mohit's explicit signoff on this document.
- Answers to the 3 open questions above.
- A locked, authored set of tier-specific concept rules for `piece_safety`
  across enough real positions to validate the pattern (the four example
  texts above are illustrative, not a final content set) — same
  author-then-verify discipline as `simple_english_captions_scope.md`'s
  hit-list.
