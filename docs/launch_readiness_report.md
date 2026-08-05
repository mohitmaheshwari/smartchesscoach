# ChessGuru — Launch Readiness Report

*A brutally honest, evidence-based assessment. Not marketing, not optimism, not
pessimism — only what we've verified. Every score is anchored to a check run
this cycle, not a gut read.*

---

## Headline verdict — read this if you read nothing else

**The evidence forces a two-axis answer, and conflating them is the mistake I made at 6.5:**

| Axis | Score | What it means |
|---|---|---|
| **Product quality** (is the thing good?) | **7.5 / 10** | Verified *up* from the 6.5 gut-read. The coach is genuinely strong; three of my headline criticisms deflated on inspection. |
| **Launch readiness** (will it convert a stranger?) | **6 / 10** | Held down by **one gate**: activation. Everything a new player must survive *before* meeting the coach. |

**The gap between those two numbers is the entire roadmap.** You do not have a
product that's mediocre across the board (the old 6.5). You have an **8-quality
coach behind a 3-quality front door.** Close the door problem and both numbers
become 8. Nothing else on this list is close in leverage.

**One-line summary:** *The coach is no longer the bottleneck. How fast a stranger
discovers the coach — that's the bottleneck, and it's a product problem, not an AI problem.*

---

## Scorecard at a glance

| # | Dimension | Score | Launch blocker? |
|---|---|---|---|
| 1 | Coaching Quality | **8.0** | No |
| 2 | Pedagogy | **6.0** | No |
| 3 | Trust (does the player believe it *gets* them?) | **3.0** | ⚠️ Growth-critical |
| 4 | Activation | **3.0** | **YES** |
| 5 | First Session | **3.5** | **YES** |
| 6 | UX | **5.5** | No |
| 7 | Product Coherence | **5.0** | No |
| 8 | Reliability | **6.5** | No (gaps fixed this cycle) |
| 9 | Observability | **5.0** | No |
| 10 | Research Culture | **6.5** | No |
| 11 | Experimentation | **5.0** | No |
| 12 | Launch Risk posture | — | see §12 |

---

## 1. Coaching Quality — 8.0 / 10 · Blocker: No

**Evidence (verified this cycle):** Re-rendered 120 real prod games (7,778 moves)
through the live V5 pipeline: **0% silent moves, 693/693 user blunders captioned
(100%), 4,640 distinct captions, 0 render failures, 0 surface violations** on
current version. Histogram shows pervasive `→HELD` fallbacks — the pipeline
**abstains rather than confabulate**. `cognitive_gap` category accuracy fixed
(king_safety misfire 33.6% → ~0.8%).

**Why:** This is engineering-confidence territory. Total coverage, right-or-silent
design, and a category classifier that was measured and corrected. Few early
coaching products would survive this audit.

**Recommendation:** **Freeze it for launch.** Rolling QA only. Do *not* spend
another engineering week here — it is no longer the limiting factor. (Not
exhaustively verified: per-caption "why-depth." Track as ongoing QA, not a blocker.)

## 2. Pedagogy — 6.0 / 10 · Blocker: No

**Evidence:** The diagnostic → weakness → training loop is now wired end-to-end
(cold-start users get a real `top_weaknesses` + routed focus). Captions carry a
real "why" (R12). Motif profiles, opening curriculum, endgame lessons exist.
**But:** for a true *learner* (no games to import), the teaching is scattered
across 50+ surfaces with no single guided path, and some captions lean on
principle-bank filler.

**Why:** Strong *for the plateau improver who already plays* (the stated target).
Weak/scattered for the "I want to learn chess" beginner.

**Recommendation:** For launch, fine — you're aimed at improvers. A sequenced
"Learn Chess" path is a **post-launch bet** for the learner segment, not a blocker.

## 3. Trust — 3.0 / 10 · Blocker: ⚠️ Growth-critical

**Evidence:** The coach's intelligence is real (§1) but reached *late*. There is
no instrumented "this coach gets me" moment, and the path designed to deliver it
(the diagnostic) is being abandoned before puzzle 1 (see §4). Time-to-Trust is
correctly **not yet** a named metric — we don't know what creates trust.

**Why:** Trust is the true activation currency, and right now the asset that would
earn it is discovered too late to earn it.

**Recommendation:** The "Trust in 30 Minutes" sprint. Expose the coach sooner with
**one uncanny-specific, true, right-or-silent insight** — *the first thing a player
couldn't have discovered without ChessGuru.* Build it only after watching 5 users.

## 4. Activation — 3.0 / 10 · Blocker: **YES (the #1 launch blocker)**

**Evidence:** 31% of signups are dead-on-arrival (no account, no coached game).
Activation Timeline on recent signups: candidate signals **B/C/D = 0%**; the
diagnostic is abandoned at **+18s, before answering puzzle 1**; nobody in the
recent sample completed it → nobody reached the insight; pure-learner cohort:
63% did nothing, ~2% returned a second day.

**Why:** The front door does not convert. Value is structurally back-loaded — the
landing sells the *day-90* coach; day one can't deliver it, and no one bridges the wait.

**Recommendation:** This is where launch is won or lost. Everything in the next two
weeks answers one question: *does this make a stranger reach the coach sooner?*
Nothing else.

## 5. First Session — 3.5 / 10 · Blocker: **YES**

**Evidence:** The activation hub shipped (value-first, no account wall) — a real
improvement. But the designed trust-path (diagnostic) is abandoned instantly, and
engagement instead leaks straight to Play-with-Coach. The landing promises a coach
that "remembers you"; the first session can't prove the coach even *exists*.

**Why:** The best asset is still being discovered as a *reward for persistence*
rather than made obvious immediately.

**Recommendation:** The first session must **prove the coach exists** in the first
two minutes, not reward the patient. That's the sprint.

## 6. UX — 5.5 / 10 · Blocker: No

**Evidence:** Individual screens are genuinely well-built (the hub, diagnostic,
Home are polished and considered). But the connective tissue is a maze — no single
"what do I do next" for a newcomer.

**Why:** Good rooms, no floor plan.

**Recommendation:** An opinionated first-run **spine** — one path, one next-step —
is higher ROI than any individual screen polish.

## 7. Product Coherence — 5.0 / 10 · Blocker: No

**Evidence:** Homepages *are* consolidated (`/home` → `HomePageNew`, `/dashboard`
redirects, old HomePage unimported — better than I first claimed). But 50+ routes
remain and the Lab area still overlaps (`/lab` = Dashboard, `/lab/*` = LabV2 + Lab).

**Why:** Consolidated at the top, still sprawling underneath. This is **product
visibility debt** made visible: assets exist that players never cleanly experience.

**Recommendation:** The weekly question — *"what do we already have that players
never experience?"* — is the right forcing function. Prune/merge the Lab overlap.

## 8. Reliability — 6.5 / 10 · Blocker: No (specific gaps fixed this cycle)

**Evidence (this cycle):** 202 analyses were **silently stranded** (failed with a
code error, never retried) — fixed by shipping auto-retry-on-transient-failure.
The frontend had been **un-deployable** on a case-sensitivity bug — fixed. Prod
Mongo is now firewalled (good). *Honest debit:* my first auto-retry deploy crashed
the worker (naive/aware datetime) for ~2 min before I caught it in verification.

**Why:** Real gaps existed and are now closed, but that they existed — and that a
change could crash the worker — means reliability isn't yet *boring*.

**Recommendation:** Make reliability boring: CI that catches the case-bug class, a
deploy that can't silently no-op, a mandatory post-deploy DB-touch check.

## 9. Observability — 5.0 / 10 · Blocker: No

**Evidence:** A PostHog funnel exists and was **fully instrumented but unread** —
the purest example of visibility debt. The server-side **Activation Timeline**
assembler now exists (built this cycle) giving queryable server-truth. Candidate
trust-signals are defined but unproven; no dashboard habit yet.

**Why:** The instruments existed; nobody was looking. That's organizational, not technical.

**Recommendation:** A standing weekly ritual: *"what behavior did each shipped
change move?"* Instrumentation without a reading habit is theater.

## 10. Research Culture — 6.5 / 10 · Blocker: No

**Evidence:** Genuinely strong disciplines are in place — scope-driven development,
lock-via-data (no threshold before the histogram), verify-first, product
residencies, and a pre-registered experiment doc. The founder runs real
user-watching. This is above the bar for an early-stage team.

**Why:** The scientific instinct is real. The gap is *aim* — pointing the rigor at
**exposure**, not just building.

**Recommendation:** Adopt Reveal → Measure → Refine as the standing order. Never
refine what isn't yet exposed and measured.

## 11. Experimentation — 5.0 / 10 · Blocker: No

**Evidence:** The machinery exists — PostHog funnel, default-off feature flags for
clean A/B (`VERIFIED_CAPTIONS`, `PWC_GAP_ENRICHMENT`), a pre-registration doc. But
no experiment loop has yet *turned* on activation; the timeline only just became measurable.

**Why:** Capable of experiments; not yet running the one that matters.

**Recommendation:** First real experiment = the trust-moment, measured on the
Activation Timeline. One change, one observable behavior moved.

## 12. Launch Risk posture

**Ranked, honestly:**
1. **Activation / First Session (highest).** A stranger doesn't reach the coach. This is where launch is decided.
2. **Product visibility debt (organizational).** Building outpaces exposing — the deeper pattern behind risk #1.
3. **Reliability discipline.** Specific fires out; the *habit* of boring reliability isn't in yet.

**Not on the risk list (and this is the story of the cycle):** coaching quality,
category accuracy, homepage sprawl, XP being "dead," silent-on-blunder — **every
one of these was a suspected risk that the evidence cleared.**

---

## The instruction this report implies

Do not ask *"what else can ChessGuru do?"* Ask *"what has ChessGuru already earned
the right to say?"* — because the honest answer to the second question is: **a great
deal, and the player almost never hears it in time.**

- **Reveal** the coach sooner (the sprint).
- **Measure** it on the Activation Timeline (built; now used weekly).
- **Refine** only what's exposed and measured — never before.

**Overall: a strong product one activation sprint away from being launch-ready.**
That is a far better position than the 6.5 suggested — not because the number moved
much, but because we now know *exactly which one number to move.*

*— Assessment grounded in checks run this cycle: 120-game caption re-render, cognitive_gap
accuracy backfill, Activation Timeline on recent signups, funnel/instrumentation audit,
reliability incident + fix. Nothing here is asserted from memory.*
