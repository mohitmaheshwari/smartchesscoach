# Player profile on Home — scope

Status: **Section 0 only. Awaiting Mohit's ruling on EXTEND vs PARALLEL.**
Sections 1–7 deliberately unwritten — Section 0 found significant overlap and
the skill says stop and surface it rather than write six more sections that
may be invalidated.

---

## 0. Existing surfaces audit

### What was about to be built

A "what we've learnt about you" card on `/home` — two strengths, two
weaknesses, one focus, in plain English, no numbers.

### What already exists

**Three different things render at `/home`, and which one you get depends on
your role.**

**1. `CurriculumHome.jsx` — admins and super-admins only.**
`PERSONAL_CURRICULUM_ENABLED=true` with
`PERSONAL_CURRICULUM_ROLES=admin,super_admin`, gated at
`personal_curriculum.py:409`. This is the page Mohit sees. Its headline comes
from `curriculumHeadline(outcome)` — **six fixed strings**, identical for
every user in the same state. It says "Let's fix one thing that keeps getting
in your way" and never names the thing.

**2. `HomePageNew.jsx` ordinary branch — what real users actually see.**
This is the surface that matters, and it **already has a narrative coach
card**: `coachConversation.thinking_signature`, then
`narrative.stage_opener`, then `narrative.continuity` + `narrative.belief`,
then `CanonicalFocusRail`. Built by `services/home_coach_conversation.py`.
Alive for 52 of 56 users with 10+ analysed games.

**3. The approved redesign scope** already specified the profile sentence.
`docs/inner_product_experience_redesign_scope.md`, Home mockup:

> *"I've been looking at your games. **You are finding attacking ideas**, but
> when one of your pieces is attacked, you often answer before checking what
> that piece was protecting."*

### What surface 2 actually says today

Rendered live for four real users:

```
stage_opener: I'm starting to see your habits.          <- 3 of 4 identical
continuity:   We've worked on piece safety for 12 days now.
belief:       In a slow game the board feels settled, so it stops getting
              re-checked every move...                   <- 2 variants total
```

So the coach card already exists, already speaks in coach voice, and already
has three slots. **What it lacks is anything that distinguishes one player
from another.** Every user reads "piece safety" because only one detector is
PLAN-graded (see `docs/picker_sources_scope.md`); `stage_opener` is one of a
handful of stage strings; `belief` has two variants.

It is a personalisation-shaped surface carrying no personalisation.

### Overlap vs differentiation

**Overlap is near-total.** A new profile card would sit directly above an
existing card that occupies the same slot, speaks in the same voice, and is
built for the same job. Two coach cards in sequence, one generic and one
specific, is exactly the shelf clutter this audit exists to prevent.

**The genuine gap is narrower than "there is no profile".** It is that
`stage_opener` is a stage label rather than an observation, and `continuity`
inherits the picker's single topic.

### Decision: EXTEND, not PARALLEL

Replace the generic `stage_opener` with a **measured observation** built from
the datasets that do NOT route through the picker, and leave `continuity`,
`belief` and the focus rail untouched.

Why this is the right shape:

- It uses the slot the approved redesign already described.
- It needs no new component, route, collection or card.
- It sidesteps the plan gate entirely. Motif events, repertoire and phase are
  read directly; nothing waits on `topic_can_be_planned`.
- It fails safe: no measured observation means today's stage string, which is
  what ships now.

### What the observation can honestly be built from

| dataset | coverage | usable |
|---|---|---|
| tactics — 124,483 motif events, 23 motifs, two-sided | strong | **yes** |
| openings — repertoire 69/69, 16,418 deviations | strong, unused | **yes** |
| phase — 532,343 labelled moves | 61/69 users | **yes** |
| style — tactical vs positional tendency | 69/69 | **yes** |
| positional — 1,771 of 532,399 moves | 0.3% | **no** |
| behaviour — measured stats | 0/69 | **no** |

Coverage floor, measured: at 3 games, 95% of users can yield one motif fact;
several facts need 10 games.

### Open question for Mohit — this is the ruling I need

The redesign that produced surface 2 was a **Codex delivery**, not Mohit's
design decision — the earliest trace anywhere is him pasting a completion
report on 2026-08-31, and he classed it himself as a Codex-built delivery to
deploy and audit. Its success criteria ban "unexplained decimal scores,
centipawn values, statistical rates, or report-style language", which the
proposed observation satisfies (plain prose, no numbers) — and its own Home
mockup contains the observation.

So the question is not whether the profile conflicts with the redesign. It
does not. The question is whether Mohit wants to EXTEND a surface he did not
commission, or rule on that surface first.

**RULED 2026-09-24: EXTEND.** Mohit approved extending the existing coach
card rather than ruling on the Codex surface first.

---

## 1. What it is

One sentence at the top of the coach card on Home that tells a player
something true about how they play, drawn from their own games.

Today that line is a stage label — "I'm starting to see your habits" — which
is the same for almost everyone. It becomes an observation: what this player
is good at, and what keeps costing them games. It is written like a coach
talking, never like a report. No numbers, no percentages, no chess jargon.

Nothing else on the card changes.

---

## 2. What the user sees

The card as it renders today:

```
  I've been thinking about your games.

  I'm starting to see your habits.              <- generic, this line changes

  We've worked on piece safety for 12 days now.

  In a slow game the board feels settled, so it stops getting re-checked
  every move. Then one capture changes it.

  [ Practise this with me  -> ]
```

**After — a player with 25 games:**

```
  I've been thinking about your games.

  You play for the attack, and you spot pins well. Forks are where
  games slip away — you find them, but you walk into them just as often.

  We've worked on piece safety for 12 days now.

  In a slow game the board feels settled, so it stops getting re-checked
  every move. Then one capture changes it.

  [ Practise this with me  -> ]
```

**It grows with how much we have seen.** The same player earlier:

```
  3 games    You play for the attack.

 10 games    You play for the attack. Forks are where games slip
             away from you.

 25 games    You play for the attack, and you spot pins well. Forks are
             where games slip away — you find them, but you walk into
             them just as often.
```

**When nothing can be measured honestly, today's line ships unchanged.**
Silence is not a state the player ever sees; they see what they see now.

### Rules the sentence must obey

- **No numbers.** Not counts, not percentages, not centipawns, not "8 of your
  last 10". If it cannot be said in words it is not said.
- **Name the behaviour, not the tally.** "Forks are where games slip away",
  never "you walked into 17 forks".
- **Very easy English.** Short sentences, one idea each, common words.
- **No jargon.** No fianchetto, prophylaxis, zwischenzug. "Pin" and "fork"
  are allowed — they are the vocabulary the training already teaches.
- **Strength first, always.** A player opens Home to a sentence about what
  they are good at, then what is costing them. Never the other way round.
- **At most two strengths and two gaps**, so it stays a sentence and never
  becomes a list.

---

## 3. In scope (V1)

- A new `observation` field on the home coach conversation payload, replacing
  `stage_opener` in the card when present.
- Observation built from four sources only: **motif events** (two-sided —
  finds vs walks into), **repertoire**, **phase**, **style**.
- Three depth tiers by games seen: 3+ (one clause), 10+ (two), 25+ (full).
- **25-game window.** Games older than the last 25 are not read.
- **Refresh on every 5th newly analysed game**, not on page load.
- Phrasings authored offline as deterministic templates and approved through
  the existing caption authoring path. **No LLM at request time.**
- Falls back to today's `stage_opener` whenever no tier is met.
- Coverage measured across all users before it ships.

---

## 4. Explicitly out of scope (V1)

- **Positional observations.** 1,771 of 532,399 moves carry positional state.
  Nothing honest can be said yet.
- **Behavioural observations** ("you get loose when winning"). 0 of 69 users
  have measured behaviour stats.
- **Any change to `continuity`, `belief`, the focus rail, or the CTA.**
- **Any change to `CurriculumHome`** — that is the admin surface and a
  separate question.
- **Progress claims** ("this is improving"). Requires a trend the profile
  does not yet compute.
- **Opening-variation prompts** ("you always play d3") — real, measured, and
  a different card. Filed, not built here.
- **Rating-band phrasing differences.** One voice for V1.

---

## 5. Success criteria

- **Coverage:** at least 80% of users with 10+ analysed games receive a
  measured observation rather than the fallback. Measured before release.
- **Distinctness:** no single observation sentence is shown to more than 25%
  of users. This is the criterion the current card fails — `stage_opener` is
  identical for 3 of 4 sampled users and `belief` has two variants.
- **Truth:** every shipped observation is re-derivable from stored move
  observations for that user, verified per-user on a sample, with zero
  claiming a motif the events do not support.
- **Behavioural:** click-through on the focus-rail action is higher for users
  who see a measured observation than for those who see the fallback. This is
  the real test — knowing *why it is for me* should make the action more
  likely, and if it does not, the sentence is decoration.

---

## 6. Open questions

**Q: Can the observation contradict the line below it?**
The observation may say "you play for the attack" while `continuity` says
"we've worked on piece safety". Those can read as two unrelated coaches.
*Why unresolved:* needs rendered pairs across real users to judge.
*Unblocking step:* render both lines for 50 users and read them together
before authoring the final templates.

**Q: Is "you walk into forks just as often" a failure scoreboard?**
It names a weakness in words with no count, which satisfies the rule as
written, but it sits close to a line Mohit has drawn twice.
*Why unresolved:* Mohit's judgement, not a measurement.
*Unblocking step:* he reads the three tiers above and says yes or no.

**Q: Where does the every-5-games counter live?**
*Why unresolved:* no existing field tracks games-since-last-profile-refresh.
*Unblocking step:* decide during implementation — stored on the profile doc
or derived from analysed-game count.

---

## 7. Pre-code requirements

1. **Mohit signs off on this document**, specifically the three-tier mockup
   in Section 2 — that is the product contract.
2. The two-sided motif profile is confirmed queryable per user over a
   25-game window (it is computed live today, not stored).
3. Observation templates authored and approved before wiring, not after.
4. Coverage dry-run across all users, reported before anything ships.
5. Distinctness check runnable — the 25% criterion needs a measurement that
   exists before release, not after.
