# Play first, then prove it — scope

Status: DRAFT v2, awaiting Mohit's sign-off. No code until then.
Plain English on purpose. v1 written 2026-09-18; v2 the same day after Mohit
asked the question that broke v1.

---

## The question that changed this

Mohit, on v1: *"game with coach definitely works, but then only one game what
can they tell?? obviously this gives us quickest feedback, but what about
accuracy for that feedback?"*

He was right, and the number is worse than a guess would suggest. Measured on
48 real users with 15+ analysed games, drawing random samples and comparing the
top weakness found against that player's whole history:

| games used | how often it names the RIGHT top weakness |
|---|---|
| **1 game** | **34.4%** |
| 2 games | 41.6% |
| 3 games | 46.0% |
| 5 games | 49.8% |
| 10 games | 60.9% |
| 20 games | 71.3% |

**A one-game diagnosis is wrong two times out of three.** v1 was going to ship
that as "here's your pattern", which is the product lying on first contact.

## What that fact forces, and why it makes this better

There are two different claims, and only one of them needs many games:

- **"Here is what happened in this game."** 100% true from one game. It is a
  fact about a board.
- **"Here is your pattern."** 34% true from one game. It is a claim about a
  person.

So the first game makes a **prediction** and never a diagnosis. The import is
what **proves or disproves** it.

And the coach has to be genuinely willing to be wrong — because on these
numbers it will be, about a third of the time at ten games and more at one.
That is not a flaw to hide. Trust scores **3.0** in the launch readiness
report, the lowest score we have, because nothing in the product has ever
proved the coach *gets* the player. A coach that says *"I thought X, I checked
your games, I was wrong — it is actually Y"* is the most trustworthy thing we
could possibly show, and no chess app does it.

---

## The three acts

### Act 1 — Play. No signup. (~5 min)

One button on the landing page:

    ┌──────────────────────────────────────────┐
    │   Play a game. I'll tell you what        │
    │   I noticed.                             │
    │        [ Play the coach ]                │
    │   No signup. About 5 minutes.            │
    └──────────────────────────────────────────┘

This is the Play-with-Coach that already exists and that 62% of users find
unprompted. Nothing new is built here except letting a guest in.

### Act 2 — One fact, and an honest admission

    ┌──────────────────────────────────────────┐
    │  Here's the moment this game turned.     │
    │                                          │
    │  [ board: the position, arrow on Ne5 ]   │
    │                                          │
    │  Move 14. You put your knight on e5      │
    │  where a pawn could simply take it.      │
    │                                          │
    │  I think that's a habit, not an          │
    │  accident — but I've seen one game and   │
    │  I can't prove it from one game.         │
    │                                          │
    │  What's your Chess.com or Lichess name?  │
    │  I'll check your last 20 and tell you    │
    │  either way.                             │
    │                                          │
    │  [ username ______ ]  [ Check my games ] │
    └──────────────────────────────────────────┘

The board fact is verifiable and stays inside what one game licenses. The
pattern claim is explicitly marked unproven. **The admission is the ask.**

### Act 3 — The proof, live (~2 min)

Progress on screen while the analysis runs, then one of two endings — and the
second one matters more than the first:

    RIGHT                            WRONG
    ─────────────────────────────    ─────────────────────────────
    I checked 14 games.              I checked 14 games.
    It happened 23 times.            It happened twice.
    Here are the three worst.        I was wrong — that game was
                                     an off day.
    I was right. This is your
    pattern, not bad luck.           What actually costs you games
                                     is leaving your king's side
    [ Save this ]                    thin. 9 of 14 games.

                                     [ Save this ]

Only now do we ask for an account, and the button says **save this**, not
sign up.

---

## Can we actually do Act 3 in two minutes?

Measured on 6,000 completed jobs: **65 seconds of Stockfish work per game**
(median; 90s at the 75th percentile). Six workers have been seen active.

| games | serial | 2 workers | 6 workers |
|---|---|---|---|
| 10 | 10.8 min | 5.4 min | **1.8 min** |
| 20 | 21.6 min | 10.8 min | 3.6 min |

**10 games is reachable inside two minutes** and buys 61% accuracy. 20 games
buys 71% and takes ~4 minutes. Recommend starting at 10 with a "checking more
in the background" continuation, rather than making someone wait four minutes
on their first visit.

### The one thing that has to be fixed to make this work

Analysis *work* is 65s. Analysis *wait* is the problem: the 75th percentile
from queued to completed is **23.6 hours**, because a newcomer's games queue
behind a 15,000-job backlog.

**A first-time visitor's first 10 games need a priority lane.** Without it,
Act 3 does not happen in two minutes and the whole design fails. This is the
single most important piece of engineering in this scope.

Also: **705 games are imported and never analysed**, and 740 queue jobs have
failed (4.5%). Both need a sweep — a person whose games silently never analyse
gets no Act 3 at all.

---

## Why the import is the right bet

It is the part of the product that already works:

- **48 of 61** users who linked a chess account have **20+ games analysed** —
  the 71% tier
- only 5 linked and imported nothing
- 48% of all users have linked an account

Compare the diagnostic it replaces as a front door: **5% completion, 42%
answer zero positions.**

---

## How we know it worked

| | today |
|---|---|
| finish the 20-position diagnostic | **5%** |
| answer zero positions | **42%** |
| reach any coaching without an account | **0%** — structurally impossible |
| one-game diagnosis accuracy | **34%** |

After:

- % of landing visitors who finish a game
- % of those who give a username — the real trust test
- % who reach Act 3 within two minutes (if this is low, the priority lane failed)
- % who create an account after Act 3
- **how often the coach's Act-2 prediction was wrong** — we should watch this,
  not hide it. If it is never wrong, we are cheating by predicting something
  vague.

---

## Risks

- **Guest records pollute every metric.** Needs a marker and default exclusion
  from user counts.
- **Engine cost from people who never return.** 10 games x 65s per visitor.
  Acceptable at our size; needs a per-IP cap before any real traffic.
- **The Act-2 prediction could be wrong in an insulting way.** It must come
  from the categories we trust and must never name a weakness we cannot show
  a board for.
- **Act 3 being wrong two-thirds of the time would be bad** — at 10 games it is
  wrong ~39% of the time. That is why Act 3 reports what it counted, with
  positions, rather than asserting a label.

---

## Not in this scope

- Detector review and promotion — the coach's job now, not Mohit's, and not a
  launch blocker (coaching scores 8.0).
- Tier C tactics, endgames, second lesson category — all behind this door.
- Deleting the diagnostic. It stops being the front door; it stays available.
