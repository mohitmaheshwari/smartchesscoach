# PIC line 220 — execution plan: repair the active-focus outcome path

**This is not a scope.** `docs/personal_improvement_cycle_scope.md` is
APPROVED FOR IMPLEMENTATION v1.3 and already contains this work:

> line 39 — "The focus lifecycle produces a trustworthy next-game/weekly
> verdict and automatically advances only when the evidence supports it."
> line 65 — "continue the same focus, resolve it, or choose the next focus."
> line 49 — `… → canonical focus outcome → Progress/next focus → Pro renewal`
> **line 220 — "Repair the active-focus outcome path."**

This document is the execution plan under that line. No new surface, no new
collection, no competing definition.

---

## Why it matters, in Mohit's words (2026-09-25)

> "until coach finds out that you have mastered Italian and you keep playing
> Italian and then is the time to switch to other openings … that's when
> people will come back to us."

**The focus changing IS the return mechanism.** Measured 2026-09-24:

```
193 focuses ended
  163 as superseded_v6 … v9     killed by OUR picker version bumps
    0 because a player mastered the thing
```

Every resolution value that exists is a failure mode: `measurement_pending`
35, `metric_gap` 18, `detector_not_authorized_for_plan` 11. **There is no
success value in the system.** A user's focus history is a log of our
deploys.

---

## What already works, and must not be rebuilt

`server.py:focus_outcome_loop` runs daily and measures every active focus.
With `FOCUS_OUTCOME_RENDER_ENABLED` off (the default, and unset in prod) it
writes to `focus_outcome_shadow` instead of closing the focus.

That shadow holds **427 rows across 54 users**:

```
 240  no_data               median  1 game since focus start
  79  measurement_pending   median  7 games
  54  regressed             median 43 games   delta +57.9%
  35  stuck                 median 97 games   delta  +0.1%
  19  improved              median 63 games   delta -29.1%
```

`stuck` landing at **+0.1%**, dead centre between improved and regressed, is
good evidence the thresholds cut the distribution sensibly. The measurement
is sound. **Five specific things stop it closing a focus.**

---

## The five repairs, in order

### R1 — stability gate (the actual blocker)

**31 of 54 users carry more than one distinct verdict over time.** A player
could be told "improved" Monday and "regressed" Tuesday off one focus. That
is worse than silence and it is why the flag is off.

Require the **same verdict on two consecutive passes** before it may close a
focus. Shadow keeps recording every pass; only agreement graduates.

*Proof it worked:* re-run over the existing 427 shadow rows and report how
many users would have received a stable verdict. Must be ≥90% of those who
get any verdict.

### R2 — `MIN_DECISIONS_FOR_PROOF` 100 → 60

`primary_weakness_picker.py:999`. Measured decisions-per-game histogram
across 56 users (p50 = 4.55/game, tight distribution):

```
threshold  20:  55 of 56 users (98%) measurable within 25 games
threshold  40:  54 of 56 (96%)
threshold  60:  54 of 56 (96%)   <- top of the flat region
threshold  80:  51 of 56 (91%)
threshold 100:  39 of 56 (69%)   <- today
```

100 sits exactly on the cliff. 60 is the top of the flat region — most
evidence per verdict at no cost in reach. **Nobody chose 100 against this
curve; it was inherited.**

*Proof it worked:* judgeable users go 39/56 → 54/56.

### R3 — `BASELINE_WINDOW_GAMES` 30 → 25

`primary_weakness_picker.py:473`. Mohit's design is a 25-game window. The
code says 30. No measurement needed; align the code to the decision.

### R4 — exclude bullet

There is **no bullet filter anywhere** in the picker. Read `time_control`,
NOT `time_control_category` — the category is null on **7,554** games, so a
filter written against it silently drops half the corpus.

```
time_control:           rapid 8834 · blitz 7555 · untimed 270 · daily 242
time_control_category:  None 7554 · rapid 5891 · blitz 3761 · bullet 12
```

Only 12 games are categorised bullet, so this is right in principle and
nearly free in practice. Do it for correctness, expect no rescue.

### R5 — floor the baseline, and always record `metric_name`

`regressed` maxes at **+1920.2%**, which is a near-zero baseline divide.
And `metric_name` is null on **351 of 427** shadow rows, so most verdicts
cannot be audited after the fact.

*Proof it worked:* no delta beyond a sane bound; `metric_name` present on
100% of new rows.

---

## The constraint PIC already imposes

> line 184 — "A casual coached game cannot silently resolve the focus …
> zero detected hangs is not proof that the instruction was followed."

**Graduation cannot come from "nothing bad happened."** Playing twenty more
Italians without disaster is not mastery of the Italian. R1–R5 make the
verdict trustworthy; they do not by themselves satisfy line 184, which needs
positive evidence the player did the thing. That is a separate piece of work
and it is NOT in this plan.

---

## Order and gating

R2–R5 are safe with the flag off — they change what the shadow records, not
what a user sees. Land them first and let the shadow re-accumulate.

**R1 is the gate.** `FOCUS_OUTCOME_RENDER_ENABLED` stays off until the
stability re-run passes on real data. More coverage from R2 makes instability
*worse* before better — more users judged on thinner evidence — so shipping
R2 without R1 would increase the number of people told contradictory things.

**Nothing here flips the flag. That decision stays Mohit's.**

---

## What this does not fix

The graduated player needs somewhere to go. Today `topic_can_be_planned` is
true for exactly one topic, so a successful graduation would hand them
`piece_safety` again. The naming work (-8f, `ignored_king_attack` at 4,035
fires across all 57 users) is what gives graduation a destination.

**Closing a focus and having a next focus are two different repairs.** This
plan is the first.
