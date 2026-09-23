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

**AWAITING MOHIT'S RULING on EXTEND vs PARALLEL before sections 1–7 are
written and before any code.**
