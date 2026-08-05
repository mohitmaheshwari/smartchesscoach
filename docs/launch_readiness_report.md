# ChessGuru — Launch Readiness Report

*A brutally honest, evidence-based assessment. Not marketing, not optimism, not
pessimism — only what we've verified. Every score is anchored to a check run
this cycle, not a gut read. Facts and interpretations are kept separate
throughout (2026-08-05 revision) — six months from now, someone should be able
to challenge an interpretation without ever needing to challenge the evidence
underneath it.*

---

## Headline verdict — read this if you read nothing else

**A single "Product Quality" number was the wrong instrument.** The original
7.5 blended two different things: how good the engine is, and how well a
stranger actually experiences it. Those move independently — this report's own
evidence keeps saying "the coach is excellent" in one breath and "activation is
weak" in the next. Averaging them into one number hid the exact shape of the
problem.

| Axis | Score | Confidence | What it means |
|---|---|---|---|
| **System Quality** (is the engine good?) | **8.0 / 10** | High | Coaching (8.0, very high confidence) + Reliability (6.5) + Research Culture (6.5), weighted toward the most rigorously verified dimension |
| **Experience Quality** (does a stranger actually get it?) | **4.0 / 10** | High | Trust (3.0) + Activation (3.0) + First Session (3.5) are the three dimensions that actually measure this, and they're the three worst scores in the whole report. Weighting them evenly with UX (5.5) and Product Coherence (5.0) would understate the severity — that's a real disagreement with an earlier draft of this section, not a rounding choice. |
| **Launch Readiness** (how ready is the plan to close that gap?) | **6 / 10** | Medium | Distinct from Experience Quality — this is a judgment about trajectory (a narrow, well-diagnosed gap with real fixes already shipping), not a restatement of the current snapshot. |

**The gap between System Quality and Experience Quality *is* the roadmap.** You
do not have a mediocre product. You have an 8-quality coach behind a
4-quality front door. Close the door problem and Experience Quality moves
toward System Quality's number. Nothing else on this list is close in leverage.

**Interpretation, kept separate from the evidence above by design:** the coach
is no longer the bottleneck. How fast a stranger discovers the coach — that's
the bottleneck, and it's a product problem, not an AI problem.

---

## Scorecard at a glance

| # | Dimension | Score | Confidence | Launch blocker? |
|---|---|---|---|---|
| 1 | Coaching Quality | **8.0** | Very High | No |
| 2 | Pedagogy | **6.0** | Medium | No |
| 3 | Trust (does the player believe it *gets* them?) | **3.0** | **Low** — see note below | ⚠️ Growth-critical |
| 4 | Activation | **3.0** | High | **YES** |
| 5 | First Session | **3.5** | Medium-High | **YES** |
| 6 | UX | **5.5** | Medium | No |
| 7 | Product Coherence | **5.0** | Medium | No |
| 8 | Reliability | **6.5** | High | No (gaps fixed this cycle) |
| 9 | Observability | **5.0** | High | No |
| 10 | Research Culture | **6.5** | Medium | No |
| 11 | Experimentation | **5.0** | Medium-High | No |
| 12 | Launch Risk posture | — | — | see §12 |

**Why Trust is flagged Low confidence despite having a score:** the score
itself is inferred from the *absence* of an instrumented trust moment, not
from a measured trust failure. A number derived from "we don't know" should
carry a visibly lower confidence than one derived from a 120-game re-render.

---

## 1. Coaching Quality — 8.0 / 10 · Confidence: Very High · Blocker: No

**Evidence.** Re-rendered 120 real prod games (7,778 moves) through the live
V5 pipeline: 0% silent moves, 693/693 user blunders captioned (100%), 4,640
distinct captions, 0 render failures, 0 surface violations on current version.
Histogram shows pervasive `→HELD` fallbacks — the pipeline abstains rather
than confabulates. `cognitive_gap` category accuracy fixed (king_safety
misfire 33.6% → ~0.8%).

**Interpretation.** This is engineering-confidence territory. Total coverage,
right-or-silent design, and a category classifier that was measured and
corrected. Few early coaching products would survive this audit.

**Why not higher than 8?** Coverage, correctness, and abstention are verified.
What is *not* yet systematically verified: per-caption explanation depth (a
separate 140-caption audit this cycle found 0% of captions carry any
next-game/cross-game action framing — a real, measured gap, not covered by
this dimension's coverage numbers), longitudinal educational impact, and
direct user perception of coaching quality. Those three gaps are exactly what
keeps this at 8, not 9 — coverage tells you the pipe doesn't leak; it doesn't
tell you the water tastes good or that anyone remembers drinking it.

**Recommendation.** Freeze it for launch. Rolling QA only. Do not spend
another engineering week here — it is no longer the limiting factor.

## 2. Pedagogy — 6.0 / 10 · Confidence: Medium · Blocker: No

**Evidence.** The diagnostic → weakness → training loop is wired end-to-end
(cold-start users get a real `top_weaknesses` + routed focus). Captions carry
a real "why" (R12). Motif profiles, opening curriculum, endgame lessons exist.
For a true *learner* (no games to import), teaching is scattered across 50+
surfaces with no single guided path, and some captions lean on principle-bank
filler.

**Interpretation.** Strong for the plateau improver who already plays (the
stated target). Weak/scattered for the "I want to learn chess" beginner.

**Recommendation.** Fine for launch — you're aimed at improvers. A sequenced
"Learn Chess" path is a post-launch bet for the learner segment, not a blocker.

## 3. Trust — 3.0 / 10 · Confidence: Low · Blocker: ⚠️ Growth-critical

**Evidence.** The coach's intelligence is real (§1) but reached late. There is
no instrumented "this coach gets me" moment. The path designed to deliver it
(the diagnostic) is abandoned before puzzle 1 (see §4). Time-to-Trust is
correctly not yet a named metric — we don't know what creates trust.

**Interpretation.** Trust is the true activation currency, and right now the
asset that would earn it is discovered too late to earn it.

**Recommendation.** The "Trust Moment" work below (see Success Criteria) —
expose the coach sooner with one uncanny-specific, true, right-or-silent
insight: the first thing a player couldn't have discovered without ChessGuru.
Build it only after watching 5 real users.

## 4. Activation — 3.0 / 10 · Confidence: High · Blocker: **YES (the #1 launch blocker)**

**Evidence.**
- 31% of signups create no account and no coached game.
- Activation Timeline on recent signups: candidate trust signals B/C/D = 0%.
- Diagnostic abandonment occurs before puzzle 1, at +18s on the recent sample.
- Nobody in the recent sample completed the diagnostic → nobody reached the insight it's meant to produce.
- Pure-learner cohort: 63% did nothing at all; ~2% returned a second day.

**Interpretation.** The current onboarding does not consistently get new users
to the coach. Value is structurally back-loaded — the landing sells the
day-90 coach; day one can't deliver it, and nothing currently bridges the wait.

**Recommendation.** Prioritize reducing time-to-first-trust over adding new
capabilities. Everything in the next sprint answers one question: does this
make a stranger reach the coach sooner? Nothing else.

## 5. First Session — 3.5 / 10 · Confidence: Medium-High · Blocker: **YES**

**Evidence.** The activation hub shipped (value-first, no account wall) — a
real improvement. The designed trust-path (diagnostic) is abandoned instantly;
engagement instead leaks straight to Play-with-Coach. The landing promises a
coach that "remembers you"; the first session can't prove the coach even
exists yet.

**Interpretation.** The best asset is still being discovered as a reward for
persistence rather than made obvious immediately.

**Recommendation.** The first session must prove the coach exists in the
first two minutes, not reward the patient.

## 6. UX — 5.5 / 10 · Confidence: Medium · Blocker: No

**Evidence.** Individual screens are genuinely well-built (the hub,
diagnostic, Home are polished and considered, confirmed directly in the
product residency sessions this cycle). The connective tissue between them —
no single "what do I do next" for a newcomer — is not.

**Interpretation.** Good rooms, no floor plan.

**Recommendation.** An opinionated first-run spine — one path, one next-step
— is higher ROI than any individual screen polish.

## 7. Product Coherence — 5.0 / 10 · Confidence: Medium · Blocker: No

**Evidence.** Homepages are consolidated (`/home` → `HomePageNew`,
`/dashboard` redirects, old HomePage unimported). 50+ routes remain, and the
Lab area still overlaps (`/lab` = Dashboard, `/lab/*` = LabV2 + Lab).

**Interpretation.** Consolidated at the top, still sprawling underneath —
product visibility debt made visible: assets exist that players never
cleanly experience. The Evidence Board's own "8 of 11 Home fields unused" and
Game Review's "7 sub-products, no confirmed hero" findings are the same
pattern independently confirmed at two other layers.

**Recommendation.** The weekly question — "what do we already have that
players never experience?" — is the right forcing function. Prune/merge the
Lab overlap.

## 8. Reliability — 6.5 / 10 · Confidence: High · Blocker: No (specific gaps fixed this cycle)

**Evidence.** 202 analyses were silently stranded (failed with a code error,
never retried) — fixed by shipping auto-retry-on-transient-failure. The
frontend had been un-deployable on a case-sensitivity bug — fixed. Prod Mongo
is now firewalled. Honest debit: the first auto-retry deploy crashed the
worker (naive/aware datetime) for ~2 minutes before being caught in
verification.

**Interpretation.** Real gaps existed and are now closed, but that they
existed — and that a fix itself briefly broke something — means reliability
isn't yet boring.

**Recommendation.** Make reliability boring: CI that catches the case-bug
class, a deploy that can't silently no-op, a mandatory post-deploy DB-touch
check.

## 9. Observability — 5.0 / 10 · Confidence: High · Blocker: No

**Evidence.** A PostHog funnel existed and was fully instrumented but unread.
The server-side Activation Timeline assembler now exists. Candidate
trust-signals are defined but unproven. Separately confirmed this cycle: Home
and Diagnostic both had zero page-level analytics until the product residency
sessions added them; Game Review still only tracks "opened," nothing inside.

**Interpretation.** The instruments existed; nobody was looking. That's
organizational, not technical.

**Recommendation.** A standing weekly ritual: what behavior did each shipped
change move? Instrumentation without a reading habit is theater.

## 10. Research Culture — 6.5 / 10 · Confidence: Medium · Blocker: No

**Evidence.** Scope-driven development, lock-via-data (no threshold before
the histogram), verify-first, product residencies, a pre-registered
experiment doc, an Evidence Board, and a Research Ledger tracking belief
confidence separately from evidence all exist and are in active use this
cycle. The founder runs real user-watching.

**Interpretation.** The scientific instinct is real and, notably, has
compounded *during* this cycle rather than just being present at the start.
The gap is aim — pointing the rigor at exposure, not just building.

**Recommendation.** Adopt Reveal → Measure → Refine as the standing order.
Never refine what isn't yet exposed and measured.

## 11. Experimentation — 5.0 / 10 · Confidence: Medium-High · Blocker: No

**Evidence.** The machinery exists — PostHog funnel, default-off feature
flags for clean A/B (`VERIFIED_CAPTIONS`, `PWC_GAP_ENRICHMENT`), a
pre-registration doc, a formal one-experiment-at-a-time policy. Experiment #1
(Habit Coach holdout) is pre-registered and mid-rollout. No experiment has
yet turned specifically on activation.

**Interpretation.** Capable of experiments; not yet running the one that
matters most for launch.

**Recommendation.** The trust-moment experiment, measured on the Activation
Timeline, should be next in the queue behind Experiment #1.

## 12. Launch Risk posture

**Ranked, honestly:**
1. **Activation / First Session (highest).** A stranger doesn't reach the coach. This is where launch is decided.
2. **Product visibility debt (organizational).** Building outpaces exposing — the deeper pattern behind risk #1, independently confirmed in Home's unused fields and Game Review's unclear hero.
3. **Reliability discipline.** Specific fires are out; the habit of boring reliability isn't in yet.

**Not on the risk list, and this is the story of the cycle:** coaching
quality, category accuracy, homepage sprawl, XP being "dead," silent-on-
blunder — every one of these was a suspected risk that the evidence cleared.

---

## Competitive Position

**Flagged explicitly: no formal competitive research exists in this
codebase.** What follows is informed judgment, not verified data the way
every section above is — it should carry visibly lower confidence than
anything backed by a real query or re-render, and it's written separately for
exactly that reason.

- **What Chess.com/Lichess already do better today:** raw analysis speed and
  familiarity at zero friction, community/social features, sheer breadth of
  content and game volume. Neither is trying to solve "did this specific
  player's specific recurring mistake actually change" — that's not a
  criticism of them, it's outside their stated scope.
- **What no one currently does, as far as this assessment can tell:** track
  a player's specific recurring mistake with recency-weighted decay (not a
  lifetime count) and confirm behaviorally whether it's fading — the
  mechanism this cycle's own research work (the tilt/collapse theory, the
  Habit Coach holdout) is actively trying to validate, not yet proven at
  scale.
- **What moat is already real, not aspirational:** the causal-intervention
  discipline itself — Threats to Validity, pre-registered experiments, a
  belief ledger with confidence that moves in both directions. That's
  organizational, hard to copy quickly, and it's the thing this cycle
  actually built, more than any single feature.
- **Launch readiness is relative, not absolute** — a stranger comparing
  ChessGuru's day-one experience to Chess.com's day-one experience is the
  real comparison that matters for activation, not a comparison of long-run
  coaching depth.

---

## Biggest Unknowns

The real next experiments, not just open questions:

- Does one uncanny, specific, true insight — delivered early — actually
  create trust, measurably (return rate, activation signal), or does trust
  require sustained exposure regardless of any single moment?
- Does diagnostic completion predict retention, or is it just correlated
  with the kind of user who was already going to stay?
- Does the Home Coach Conversation increase return rate, independent of the
  Mirror's episodic content that renders alongside it?
- Does root-cause coaching outperform move-specific coaching? (Tracked in
  the Research Ledger, Low-Medium confidence, queued as Experiment #2.)

---

## Success Criteria — replacing "Trust in 30 Minutes" with something measurable

Within four weeks:
- Diagnostic completion rate at least doubles off its measured baseline
  (8.3%, n=24 real sessions) — a concrete number, not a vibe.
- A candidate trust signal (one of B/C/D on the Activation Timeline) is
  identified, named, and shows above 0% on a fresh cohort.
- Five observed real user sessions completed and written up.
- One activation-focused experiment completed, with a pre-registered
  analysis document, same discipline as Experiment #1.
- The dead-on-arrival rate (currently 31%) is re-measured, not assumed
  improved.

Now the sprint has a finish line, not a slogan.

---

## Q3 Priorities

**P0 — Activation.** Owner: Product. Measure: Activation Timeline, dead-on-
arrival rate, diagnostic completion rate.

**P1 — Trust Moment.** Owner: Product + AI. Measure: candidate trust signals
(B/C/D) showing a non-zero, repeatable rate on a fresh cohort.

**P2 — User Observation.** Owner: Founder. Measure: five real sessions
observed and written up.

**P3 — Reliability.** Owner: Engineering. Measure: zero silent failures
across the next deploy cycle; post-deploy DB-touch check in place.

**P4 — Experiment Culture.** Owner: Whole team. Measure: one experiment
completed end-to-end (pre-registration → data → verdict → next action),
beyond Experiment #1 alone.

Nobody should have to ask "what should we do Monday" after reading this list.

---

## Closing

ChessGuru is no longer constrained by its ability to coach. It is constrained
by its ability to help a new player experience that coaching before they
leave. Every priority in the next sprint should shorten the distance between
those two moments.

*— Assessment grounded in checks run this cycle: 120-game caption re-render,
cognitive_gap accuracy backfill, Activation Timeline on recent signups,
funnel/instrumentation audit, reliability incident + fix, the 140-caption
next-game-action audit, and the Home/Diagnostic/Game Review product
residency sessions. Nothing here is asserted from memory.*
