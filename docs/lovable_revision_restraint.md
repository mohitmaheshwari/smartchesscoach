# ChessGuru — Revision Pass: Make It Calm

> Paste into Lovable as a revision on the existing project. This is a **subtraction pass**, not new
> features. The build is good but too busy — too many elements share one screen at once, which fights
> the "calm coach" intent. Fix that with **progressive disclosure: one main thing in frame at a time.**

## The one rule

**At any moment, each screen has ONE primary element in frame.** Everything else is either (a) below
the fold, (b) collapsed/secondary, or (c) revealed only when it's that element's turn. Empty, quiet
space is a feature — silence is intentional. If a panel could be empty, let it be empty.

---

## Play with Coach — the priority fix

Right now the coaching panel stacks ~6 elements at once (user card + predict + coach card + rate +
reinforcement + profile + habit reminder). Replace the stack with a **single coaching slot** that
shows ONE state at a time. The board is always the hero; the right panel (bottom sheet on mobile)
holds exactly one card.

**States of the single coaching slot (only one visible at a time):**
1. **Idle / your turn, nothing wrong:** slot is nearly empty — just a calm one-line "your move."
   No cards. This is the default and should feel restful.
2. **Instructive move played → Rate Your Move:** the 3-button self-grade. After the user answers,
   it *transforms in place* into the verdict card (don't stack a second card under it).
3. **Verdict card (user-move coaching):** one CoachCard with the why + better idea. On a blunder, the
   board locks with a single "I see it" button. Acknowledging dismisses the card.
4. **Coach's turn → Predict Coach's Move:** the candidate buttons. After the guess, it *transforms in
   place* into the coach-move card. Not both.
5. **Reinforcement on a good move:** a brief, auto-dismissing inline note or toast — NOT a persistent
   card competing for space.

**Move these OUT of the always-on stack:**
- **Early Profile card** → into the "Ask the coach" sheet, or a collapsed "About my game" disclosure.
  Not on screen during play.
- **Habit reminder** → show it once at game start, then keep it dismissed; don't keep it pinned.
- **Opening guidance strip** → keep it, but make it a single thin line that **silences once out of
  book** (it already does — just ensure it disappears, not lingers).
- **Session goal** → keep as one quiet line at the top; shrink it.

Net effect: board + at most one coaching card + one thin context line. That's it.

---

## Home — second-worst offender

It risks becoming a wall of cards. Establish a clear hierarchy:
- **One hero:** Today's Mission (with the streak chip beside it). This is the only thing above the
  fold that demands attention.
- **One coach line:** the "your coach remembers" / Pattern-of-the-Day message as a single calm
  sentence, not a dense card.
- Everything else (fundamentals, trend, last game, win banner) goes **below the fold**, lighter
  weight, scannable — not all shouting at full saturation. Reduce competing accent colors; let the
  amber hero be the only strong color above the fold.

---

## Global tone adjustments

- **One strong accent per view.** Reduce simultaneous use of amber + teal + emerald + violet + rose
  on the same screen. Pick the one that matters; mute the rest to soft/neutral.
- **More whitespace, fewer borders.** Prefer spacing and subtle elevation over boxing every item in
  its own bordered card. Group with space, not lines.
- **Calmer motion.** Entrances are fine; remove anything pulsing/looping (e.g. glow-pulse) during
  normal use — it reads as anxious, not calm.
- **Progress screen:** it has many sections (Currently Working On / Also Tracking / Mastery /
  Archived / Learned). Keep them, but **collapse all but the first by default** (accordions), so the
  user lands on one focus, not a report.

## What NOT to change

- Keep the design system, palette, typography, components, voice, and responsive structure — those
  are right. This pass is purely about **what's shown at once.** Subtract; don't redesign.
