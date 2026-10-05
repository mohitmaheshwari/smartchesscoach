# One home page — merging the curriculum home and the dashboard

Mohit, 2026-10-06: *"personal curriculum is good, but can both be merged
together, keeping the best of both worlds."*

## The two pages today

There are two home pages and which one you get depends on your account type.
`PERSONAL_CURRICULUM_ROLES=admin,super_admin`, and `HomePageNew` returns early
into `CurriculumHome` for those roles.

**3 of 128 accounts see the curriculum home. The other 125 see the dashboard.**

Mohit is one of the three. Every home-page change made on 2026-10-05 went to the
dashboard, so he could not see any of it, and every judgement he gave was about
a page nobody was editing. That is the cost of leaving a redesign behind a role
gate for five weeks, and it is the thing this scope ends.

## What each is good at

**Curriculum home (43 lines).** Greeting, one headline, one panel, one button. It
answers *what do I do today* and answers it better than the dashboard does. No
menu, no sprawl.

**Dashboard.** Carries the evidence — the coach narrative, the chances reading,
the practice links. It answers *is any of this working*.

The curriculum home has no answer to the second question at all. A player does
the one thing and leaves, and nothing ever says it is moving. That is the
retention hole, because "did it work" is the only reason to come back.

## The rule

> **The curriculum decides what you do. The evidence proves it is working.**

One instruction, then one card of proof. In that order, never reversed.

## What the player sees

```
Good evening, Mohit.

I'VE BEEN THINKING ABOUT YOUR GAMES
Let's fix one thing that keeps getting in your way.
Here's today's one thing...

┌─ LEARNING ────────────────────────────────┐
│ Time management                           │   unchanged
│ Today, ask one question every few moves   │
│                 [Practise with your coach] │
│ ────────────────────────────────────────── │
│ BEFORE YOU MOVE ON                         │
│ Undefended Pieces        [Revisit one]     │
└────────────────────────────────────────────┘

┌─ THE CHANCES YOU GOT ─────────────────────┐
│ You take about half of what the board      │   added
│ offers you.                                │
│ free material  ████████████████            │
│ skewers        ███████                     │
│ Lining pieces up is what costs you.        │
│                     [Practise skewers →]   │
└────────────────────────────────────────────┘

See the rest of my plan
```

## What is removed

**"Also showing in your games."** It reads `activeFocus.runners_up`, which the
canonical payload never sends, AND it sits inside the `pic` branch which 51 of
52 users never reach. Dead twice over.

Nothing is removed from the curriculum home.

### The nav tiles STAY — an earlier draft of this scope was wrong

This document first called the four tiles "a literal duplicate of the sidebar"
and removed them. Checked before deleting, and that was false:

    sidebar     /admin /home /play-with-coach /progress /review /settings /lab
    home tiles  /lab /openings /play-with-coach /training

**`/openings` and `/training` appear nowhere in the sidebar.** The tiles are the
only way to reach either section, and deleting them would have removed the only
route to Openings and Training from the whole application.

They also already carry an instruction of their own — Mohit, 2026-07-31: *"I'd
fade those into the background"* — which is why they are rendered at reduced
opacity under "Other ways to improve". That instruction stands; they are
utilities, not today's mission, and they are not duplicates.

## The placement bug this fixes

`ChancesCard` was added to the dashboard on 2026-10-05 inside the `pic` branch.
The branch a player takes is decided at `{canonicalContext ? ... ) : pic ? ...`,
and **51 of 52 users carry a canonical context**, so the card renders for almost
nobody. The same is true of the runners-up block.

The reading does not depend on which focus shape a player has, so it must not
live inside a test for one. It is mounted **outside every branch** on both pages.

This is the third time in two days a surface was wired into a branch its users do
not take. It is the failure mode of this codebase and it is worth naming as one.

## What this scope does NOT do

**It does not flip `PERSONAL_CURRICULUM_ROLES`.** Making the curriculum home the
page for all 125 users is a rollout decision and it is Mohit's, not a side effect
of a merge. After this change both pages carry the evidence card, so the two can
finally be compared on equal terms — which has not been possible until now.

## How we will know it worked

Mohit can see, on his own account, the same evidence a user sees. That is the
immediate test and it has been failing for five weeks.
