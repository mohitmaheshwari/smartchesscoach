# Product Residency — Session Notes

**Format, agreed 2026-08-05:** one screen per session. Not "what should
we improve" — five fixed questions, every time:

1. What is this screen trying to make the player think?
2. What is it trying to make the player feel?
3. What is it trying to make the player do next?
4. What work is the system doing that never reaches the player?
5. What evidence do we have that it's succeeding?

We redesign nothing until we understand everything. Every session ends
in something concrete — a decision, a document, an experiment, or a
shipped change — never an abstract discussion.

**Standing rule, added 2026-08-05: "Is it already built?"** Whenever
either of us says "the next big thing is X," the mandatory next
sentence is "is it already built?" — before any scope doc, any design
discussion, any estimate. Not a suggestion; a gate, same weight as the
five questions above. Earned its place by catching four real, separate
mistakes in one session: Coaching Prescriptions and the Universal Habit
Coach's live holdout were both nearly written off as dead when they
were real and running; the Razorpay payment system was nearly rebuilt
from scratch when it was live with real production credentials the
whole time; and a proposed "world's first learning graph" turned out to
have ~2,600 lines of prior art already sitting in `skill_tree.json`,
`engine2_skill_builder.py`, and `coaching_engine.py`. Answer with a real
grep/read, not a recollection — "I don't think so" is not the same
check as "I looked and it isn't there."

---

## Session 1 — Home (2026-08-05)

**Scores:** Pedagogy 9.5/10, Psychology 9/10, Simplicity 9.5/10,
Engineering efficiency 6/10.

### The four rendered sections

1. **Greeting** — ephemeral, orientation only, zero backend cost.
2. **"Since you last played" (the Mirror)** — `build_game_mirror()`,
   deliberately wins over a coach-session recap whenever any analyzed
   imported game exists ("imported games are where in-the-wild habits
   show up"). Deliberately describes the *shape* of what happened, not
   the SAN — a 2026-06-01 decision, explicit in the code: *"a 1200
   doesn't anchor memory on 'Rf1 on move 16.'"* **Never regress this.**
3. **The Coach Conversation** — gated on `games_analyzed > 0` AND a
   settled focus (`focus_bridge.get_active_focus_bundle`). Stage opener
   → continuity + hedged theory → one action → encouragement, per
   `docs/home_page_coach_conversation_scope.md`. The theory text
   includes a `_get_tilt_overlay()` step — the tilt/post-blunder-
   collapse theory from this session's own research work is **already
   partially wired into what a real user reads**, not just sitting in
   the ledger untested.
4. **Faded nav tiles** — deliberately de-emphasized, a direct 2026-07-31
   quote in the code: *"I'd fade those into the background."*

### The engineering-efficiency finding

`dashboard-v2` computes 11 top-level fields; the frontend reads 3. See
the Evidence Board's new "Home page — orphaned fields" section for the
per-field ownership recommendations. **Decision: do not trim yet** —
ownership-before-deletion, consistent with this session's governance
discipline. Trim only after every field is labeled Owned (real target
surface within 90 days) or Retired.

### Ephemeral vs. cumulative — refined, with one pushback on the draft

| Element | Ephemeral or cumulative | Why |
|---|---|---|
| Greeting | Ephemeral | Pure time-of-day, no memory |
| Mirror | Episodic | Anchored to one specific recent game |
| Coach Conversation — stage opener | Cumulative | Keyed to `games_analyzed`, deepens over months |
| Coach Conversation — continuity + theory-of-why | Cumulative | A persistent belief about a recurring pattern, revised over many games |
| Coach Conversation — **one action** | **Episodic in delivery, cumulative in origin** | Pushback on the draft table: this was marked purely "Cumulative," but the artifact itself is a specific, today-only instruction — the *reasoning behind it* is cumulative, the *instruction* is not. Worth keeping these distinct since they could diverge (a cumulative diagnosis producing a stale-feeling daily instruction is a real failure mode to watch for) |
| Coach Conversation — encouragement/closing | Mixed, leaning cumulative | Relationship-toned, not tied to today's specific event |
| Nav tiles | N/A | Pure utility |

### The open product question: "here's what happened" vs. "here's who you're becoming"

Real answer, not a vague "yes there's a gap": **the Coach Conversation
genuinely does carry identity framing** — the stage opener and the
theory-of-why are claims about who the player is, not what happened
yesterday. The gap isn't in that section's content. It's in **emphasis
order**: the Mirror is unconditional and renders *first*, every single
day, whenever it exists — and the Mirror is 100% episodic by design. So
the very first thing a returning user reads on Home, every day, is
"here's what happened," and only after that "here's who you're
becoming." Not a content problem. An ordering-and-emphasis one, worth
watching rather than acting on yet — noted here so it isn't lost, not
prescribing a fix before more screens are reviewed.

### Concrete outputs, this session

- ✅ Home instrumented with 6 real analytics events (Experiment 0 — pure
  observation, no behavior change). See `frontend/src/lib/analytics.js`
  for the event vocabulary.
- ✅ Ownership table for all 8 unused `dashboard-v2` fields, added to
  the Evidence Board.
- ❌ Did not trim `dashboard-v2` — correctly deferred pending ownership
  decisions above.

**Standing question, added after Session 2:** every screen review now
also ends with — *what promise is this screen making to the player?*
The highest-level product lens, above the original five.

---

## Session 2 — Diagnostic (2026-08-05)

**Scores:** Pedagogy 10/10, Psychology 10/10, Product clarity 8.5/10,
Observability 2/10. Unlike Home, this screen doesn't have a product
problem — it has an observability problem.

**The promise this screen makes:** *"I'll understand how you think."*
Complementary to Home's *"I remember who you are"* — see the pushback
below before treating that pairing as fully settled.

### Findings

- **Zero analytics, same gap as Home** — `funnel_diagnostic_done` was
  documented in the vocabulary comment and never once fired; the
  existing 8.3%-completion number came from querying `diagnostic_sessions`
  directly, not from any instrumentation.
- **18 of 24 sessions (75%) sit in `in_progress` indefinitely** — not a
  metric, an absence of one. "In progress" today can't distinguish
  thinking / interrupted / confused / device-switched / genuinely gone.
- **Two diagnostic systems exist** (curated V2, consequence-graded;
  legacy `community_puzzles`-based fallback), selected by whether
  `diagnostic_pool` has 20+ docs. Confirmed 60 in production — comfortably
  above threshold, so legacy is currently dormant, not live. Real latent
  risk if the pool ever shrinks: the current frontend only handles V2's
  response shape.
- **The 60-puzzle pool is not a hard ceiling** — `build_diagnostic_pool.py`
  draws from a 4.1M-row Lichess puzzle set and is manually re-run,
  wiping and rebuilding each time. Predictability-over-time is a real,
  forward-looking concern, but the fix (re-curate a larger/rotating set)
  is cheap whenever it matters — not a structural constraint today.

### Decisions

- ✅ **Ship analytics now** — unlike Home's `dashboard-v2` trim, this is
  pure observation, doesn't change behavior, doesn't lock in a direction.
  Implemented: `diagnostic_started`, `diagnostic_resumed`,
  `diagnostic_first_answer`, `diagnostic_puzzle_completed` (funnel
  position only — no verdict/correctness in the props, a deliberate
  interpretation of "don't grade every answer"), `diagnostic_pause`
  (tab backgrounded mid-puzzle, via `visibilitychange`), `diagnostic_exit_intent_shown`,
  `diagnostic_abandoned`, `diagnostic_completed` (one event, `exited_early`
  as a prop, not two parallel events for full-vs-partial), `diagnostic_training_started`.
- ✅ **Derive dormancy, don't mutate status** — correct principle, but it
  required one addition first: `diagnostic_sessions` had no per-session
  "last activity" timestamp anywhere (`started_at` and `completed_at`
  only). Added `last_activity_at`, set on every attempt, alongside the
  existing per-attempt fields — a raw fact, not an interpretation.
  Dormancy itself (whatever cutoff — 24h, 72h, 7d) gets computed at
  reporting time from this field, never stored as a status.
- ✅ **Pool health check shipped** — `daily_digest_loop` now logs an
  ERROR-level alert if `diagnostic_pool` drops below `V2_POOL_MIN`,
  instead of waiting for a user to hit a broken "undefined" screen.
- ⏸ **Legacy fallback untouched**, per agreement.
- **Interview question** ("at what point did you become convinced this
  wasn't just another puzzle trainer?") — folding into the existing
  10-user interview plan from the earlier roadmap rather than spinning up
  a separate qualitative study; same method, one more question on the list.

### Pushback: Home = "becoming," Diagnostic = "today" — real, but not fully clean

The framing is genuinely good and I don't think it's an accident. But
it deserves the same scrutiny as everything else this week: Session 1
already found that Home's *first* daily read is the Mirror — 100%
episodic ("here's what happened last game"), rendered unconditionally
before the identity-framed Coach Conversation. So "Home = who you're
becoming" is true of the page's strongest content, not its first
impression. The pairing with Diagnostic ("today's baseline") is real and
worth keeping, but it's not as symmetrically clean as it sounds until
that ordering question from Session 1 gets resolved one way or another.
Flagging the connection, not re-opening the decision.

---

## Activation Timeline — Five User Watch (2026-08-05)

Run before locking any Mountain-1 target, per the "instrument before
inventing a target" discipline — `backend/scripts/activation_timeline.py`
against the 5 most recent real signups (`--recent 5` first returned a
demo account, `demo_guru_guest_chessguru_ai`, swapped for the next real
signup before reading the result as data).

| User | First Insight Reached? | Time | Action After Insight | Returned? | Observer's Trust Moment | Notes |
|---|---|---|---|---|---|---|
| Meghanshu (…7875f2) | Unmeasurable — no signal | — | — | No | *not yet observed* | Zero events after signup. Never started the diagnostic. |
| Meghanshu (…0b381e) | Unmeasurable — no signal | — | — | No | *not yet observed* | Same — signup, then nothing. |
| Sergei Kryvosheya | Unmeasurable | — | — | No | *not yet observed* | Diagnostic started at +18s, no `diagnostic_completed` — abandoned mid-way. |
| Partha Sarathi Bhattacharyya | Unmeasurable | — | Started PWC (+56s) | No | *not yet observed* | Skipped the diagnostic entirely, went straight to Play-with-Coach. |
| Scareinz | Unmeasurable | — | Started PWC (+42s), imported a game (+28m) | No | *not yet observed* | Most active of the five. Still no next-day return. |

**Aggregate over these 5:** 0/5 `diagnostic_completed`, 0/5 returned a
later day, 2/5 started Play-with-Coach, 2/5 generated zero events after
signup.

**Finding, and it changes Mountain 1's framing:** every "First Insight
Reached?" cell is Unmeasurable, not ambiguous — none of the 5 have a
`diagnostic_completed` event in the database, and the script itself has
no server-side event meaning "insight delivered" (its own comment: that
signal is UI-only, lives in PostHog, "not server-derivable"). Mountain
1 assumed the failure mode was *the insight lands but doesn't feel
personal*. This data points somewhere further upstream: most recent real
signups aren't reaching diagnostic completion at all, so there's no
insight yet to land. The 70/40/50 targets stay unset until this is
resolved — either by adding a real "insight shown" server event, or by
pairing the next batch of signups with an actual live watch to fill the
Observer's Trust Moment column, per the plan below.

**Next step, revised 2026-08-05 after two checks that change the
logistics:**

1. **PostHog session recording has been live since 2026-04-21**
   (`frontend/public/index.html`'s `posthog.init(...)` call), long
   before any of the 5 users above signed up. Recordings for these
   *exact* 5 sessions likely already exist, unwatched — this may not
   require waiting for new signups at all. Check the PostHog dashboard
   for these 5 `user_id`s before scheduling anything.
2. **Passive recordings will not fill the "User Says" column.** They
   show behavior (hesitation, dead clicks, rage clicks, backtracking)
   but carry no verbal reasoning — that column needs either a
   moderated think-aloud session or a follow-up interview. Since real
   emails exist for all 5 users above, a short, specific follow-up
   question ("what were you hoping ChessGuru would do when you signed
   up?") is a cheap way to test the "job to be done" hypothesis without
   waiting for new traffic — proposed, not sent; contacting real users
   needs an explicit go-ahead.
3. **The "next 5 real signups" framing undersells the real pace.**
   Excluding demo/test accounts, the last 45 days produced ~25 real
   signups (~1 every 1.8 days) — a Day-1–2 window for 5 *organic*
   signups isn't realistic. If the 2-day timeline matters, that
   requires recruiting dedicated study participants, which is a
   different population from "the next real signup."
4. **No acquisition-channel signal exists** (checked `routes/auth.py` —
   no UTM/referrer/signup-source capture) — so the "job to be done"
   hypothesis (analyze-my-games vs. teach-me-chess) currently has no
   cheap, larger-N proxy. It can only be tested qualitatively for now.

`insight_shown` is now live (shipped 2026-08-05) — wired only into the
diagnostic results screen (`source: "diagnostic"`). Home and Game
Review are deliberately not wired yet; see the vocabulary note in
`analytics.js` for why.

## Full-population check (2026-08-06) — the 5-user sample generalizes, and reframes the question

Requested directly: don't wait on new organic signups to trickle in,
use the existing-user data that's already sitting there. Pulled all 105
real (non-demo/test/admin) users, lifetime, not just the 5 recently
watched:

| Metric | Full population (n=105) |
|---|---|
| Ever imported a game | 55% |
| Ever started the diagnostic | 12% |
| Ever *completed* the diagnostic | **4% (5 people, lifetime)** |
| Ever started a Play-with-Coach session | **59%** |
| Returned on some later calendar day, ever | 50% |
| Zero activity of any kind, forever | 31% |
| Active in the last 30 days of data | 38% |

**The diagnostic-abandonment finding generalizes** — 4% lifetime
completion across the whole history, not a fluke of the last 5 signups.

**New finding that reframes Mountain 1 and Priority 1: PWC, not the
diagnostic, is already the de facto front door.** 59% of all real users
have started Play-with-Coach; only 12% have even started the
diagnostic. This matches what 2 of the 5 watched users actually did
(Partha and Scareinz both skipped the diagnostic and went straight to
PWC) — at n=105 it stops being anecdote. Open question worth carrying
into whatever comes after the deferred trigger resolves: not just "why
do people abandon the diagnostic" but "should the diagnostic be the
front door at all, given real user behavior already votes for PWC by a
5-to-1 margin."

**Correction to the small sample's pessimism, not a contradiction of
it:** 50% of all real users return on *some* later day, ever — much
better than "0 of 5." But this answers a different question (do they
ever come back) than the one that mattered for activation (do they come
back *fast*). Both can be true at once.

**Surprising, evidence against "the diagnostic is necessary for
engagement":** diagnostic completers average *fewer* total games than
non-completers (22 vs. 117) — the deepest, most engaged real users
mostly never touched the diagnostic. They came in through game import
or PWC directly.

---

## Session 3 — Play with Coach (2026-08-07)

**Queue reorder, on record (see Decision Log 2026-08-07):** Game Review
was slotted as Session 3. PWC goes first instead — 59% of real users
start it vs. 12% who even start the diagnostic (full-population check,
2026-08-06). Game Review becomes Session 4.

**The promise this flow makes:** *"I'm coaching you, right now, in real
time — and I'll remember this game when we talk about the next one."*

**Method:** not read-only code tracing. Two real, distinct users' actual
`coach_sessions` / `coach_messages` / `postgame_analyses` documents were
pulled directly, end to end — one whose first-ever session never
finished, one who played two full sessions back to back — then
cross-referenced against the serving code (`routes/coach_play.py`,
60+ endpoints, `/start` at line 6607, `/move` at 7034, `/postgame` at
9817). Real data first, code second, matching tonight's own repeated
lesson about which order actually catches the truth.

### Traced journey 1 — a real first-ever session that never finished

User `user_00b3f69b42d6` (Partha, real signup, 2026-07-28). Signed up,
started Play with Coach **56 seconds later**.

| Step | What actually happened | Source |
|---|---|---|
| Session created | `session_goal`: *"Today we're working on spotting your opponent's threats before you move."* — `source: "band_default"`, `band: "beginner_high"`, `confidence: "getting_to_know_you"` | `coach_game_session.py` |
| First coach message | An `opening_teaching_offer` — *"Let's learn the King's Pawn Opening!... Can lead to Italian Game, Ruy Lopez, Scotch, or many others."* Generic, keyed off the opening name, not the player. Shown ~2 minutes in. | `coach_messages` |
| Per-move coaching | Real, substantive, correct — e.g. *"You moved your pawn with e4. This helps guard your other pieces and opens a path so more of your friends can come out and join the game."* | `move_snapshots[].coaching` |
| Ambient reinforcement | *"Good. You chose stability over aggression here."* / *"Your pieces are not fully coordinated yet."* — real per-move quality read, not cross-game personalization (nothing to personalize against yet — a genuine first game) | `coaching_decisions[]` |
| First mistake | **Never reached.** All captured moves this session are `severity: "good"`. | — |
| Personalized observation | **Never reached**, for the same reason. | — |
| Game completion | **Never happened.** `status: "active"`, `result: null`, `ended_at: null` — still open, 10 days later, as of this check. | `coach_sessions` |
| Postgame / return | N/A — there was no postgame, and this is this user's *only* `coach_sessions` document. | — |

**This is the single most important finding in this residency.** The
question wasn't "does the diagnostic lose people" — that was already
known. It's that PWC, the surface we just re-ordered the whole queue
around, loses people too, mid-session, with no resolution — not a
clean loss, not a clean win, just an open session with no coach message
in the last 10 days. Also worth naming precisely: this player never got
far enough for the coach to say anything specific about *them* — every
message shown was correct, well-written, and completely generic.

### Traced journey 2 — a real user who played two full sessions back to back

User `user_2d219f0b2815` (real signup, 2026-07-28, non-admin). Signed up
09:16:43, started PWC at 09:16:58 — **15 seconds** after signup.

**Session 1** (09:16:58 → 10:37:34, ~80 minutes, ended by resignation,
loss): 51.9% accuracy, 2 blunders, 3 mistakes, 8 inaccuracies.

**Postgame 1 — correction, 2026-08-07.** The stored `postgame_analyses`
document for this session has `coach_prescription: "hanging_piece"`,
`prescription_reason: "Cost you 6 centipawns across 5 occurrences."`
That's a real, specific, evidence-cited observation. But traced through
the actual live code tonight (not just the DB doc): **neither field is
ever returned to the PWC postgame screen.** `coach_prescription`/
`prescription_reason` are written by `postgame_analysis.py` and read
only by `home_intelligence_service.py`/`today_composer.py`/
`focus_resolver.py`/`coach_memory.py` — i.e. they shape the *next*
session's Home narrative, not this one's in-session card. What the
player actually sees post-game is one of two mutually-exclusive
components (`CoachPlaySidebar.jsx`): `PostGameReflection` when
`GET /coach/play/postgame/{id}` returns `has_data`, driven by a
*different* real mechanism — `pattern_verdict` (Case A: failed /
B: partial / C: success), computed live in `routes/coach_play.py`
from `pattern_memory_service.get_top_patterns` (the same decay model
behind Lab's Coach's Pick) — or `PostGameLesson` as a fallback when
`has_data` is false, which is what actually renders `performance_rating`.
So `estimated_rating: 750 ... rating_change_suggested: -400` genuinely
was shown to this user (via `PostGameLesson`, confirmed by grepping
its render code) — that part of the original finding stands. The
"real personalization starts at postgame via `coach_prescription`"
claim was wrong; the real immediate signal is `pattern_verdict`, and
it requires an already-established top pattern (from the decay model)
to exist at all — meaning it typically can't fire on a brand-new
user's very first PWC game, which is consistent with this user's
session 1 falling through to the `PostGameLesson` fallback.

**Session 2 started 75 seconds after session 1 ended** — a real,
fast, voluntary return, no prompting needed. `coach_prescription`
being carried forward as `"hanging_piece"` in the stored doc is real
continuity in the *data*, but per the correction above, nothing on
either live postgame surface actually shows the player that phrase —
the continuity a real user would perceive, if any, would have to come
from Home on their next visit there, not from this screen.

**Session 2 lasted 52 seconds. `evaluations: []`, 0 coach_messages.**
The user resigned before making a real move that got evaluated.

**Postgame 2**, generated from that empty session anyway: *"Clean game
for this pattern! Keep it up."* — `accuracy: 100.0`, `blunders: 0`,
`performance_rating: {estimated_rating: 1250, confidence: "low",
comparison_to_actual: "at", rating_change_suggested: +100}`.

**This is a second, distinct, important finding.** The postgame system
computed a technically-true statistic (0 blunders out of 0 evaluated
moves = 100%) and phrased it as personalized praise — *"keep it up"* —
for a session with no real engagement. This isn't the same bug as the
dead-behavioral-fields finding (that was fields never computed at all);
this is a *real* computation producing a *misleading* result, because
nothing gated it on "did anything actually happen this game." The
rating estimate also swung 750 → 1250, a 500-point move, across two
games totaling under a minute and a half of real play combined.

Also confirmed on session 2's own stored state: `session_goal` is the
*exact same* band-default text as journey 1's completely different
user — *"Today we're working on spotting your opponent's threats
before you move,"* still `source: "band_default"`, still
`confidence: "getting_to_know_you"` — **on this user's second session,
not just their first.**

### What this residency actually found

1. **PWC has a real, uninvestigated mid-session abandonment problem.**
   Not "12% complete the diagnostic" — a parallel, distinct leak inside
   the surface we just decided is the front door. No instrumentation
   currently distinguishes "resigned deliberately" from "left the tab
   open and never came back."
2. **The first thing every new player sees is generic, and it says so
   honestly** (`band_default`, `getting_to_know_you`) — this is a
   defensible, honest design choice, not a bug. But per-move coaching
   quality is real and good from move one, which the generic session
   goal undersells.
3. **Real personalization at postgame is real, but not the field this
   residency first pointed to — correction below.** The actual
   in-session postgame signal is `pattern_verdict` (Case A/B/C, backed
   by the pattern-decay model), which genuinely can say "again, you
   hung a piece" with a real move number — but it only exists once a
   top pattern is already established, so it typically cannot fire on
   a brand-new user's first game. `coach_prescription` + its
   evidence-cited reason is real and specific, but lands on Home next
   session, not here. The "minute-two trust moment" candidate is
   `pattern_verdict`'s first non-null appearance, which is instrumented
   now (`pwc_insight_shown`, see `frontend/src/lib/analytics.js`) —
   this funnel wasn't measurable at all until tonight.
4. **A confidence-labeled system can still show a harsh or hollow
   number.** Honest confidence labels (`medium`, `low`) don't prevent a
   large, blunt claim (`-400`, `+100`) from landing badly, and don't
   prevent a real computation from being trivially, misleadingly
   positive when the underlying sample is empty.
5. **`getting_to_know_you` can persist past session 1.** Confirmed on a
   real user's second session. Whatever the graduation trigger is meant
   to be, it didn't fire between a real user's first and second games.

### Population-scale confirmation (`scripts/pwc_first_session_funnel.py`, 60 real recent signups)

The abandonment finding above wasn't an edge case. Traced on real
production data, same night:

| Stage | Count / 60 | % |
|---|---|---|
| Signed up | 60 | 100% |
| Started PWC | 28 | 47% |
| First move evaluated | 18 | 30% |
| Reached a real mistake | 9 | 15% |
| Session resolved (has a result) | 7 | 12% |
| Unresolved, still active, **under 2h old** (not a leak — could be genuinely in progress) | 0 | 0% |
| Unresolved, active, **2h–7d old** | 0 | 0% |
| **Unresolved, active, over 7 days old (`unresolved_stale`)** | **18** | **30%** |
| Reached postgame | 6 | 10% |
| Returned for a 2nd session | 7 | 12% |

**Correction, same night, after external review**: the first version of
this script had no minimum age before calling a session "abandoned" — a
session started 30 seconds ago and still being genuinely played would
have been counted identically to one dead for months. Real fix, not a
wording change: the script now buckets by age
(`backend/scripts/pwc_first_session_funnel.py`) and only counts a
session as a leak once it's been sitting unresolved for over 2 hours
(chosen from this dataset's own resolved-game durations, not a round
number — see the script's own comment). Rerun for real: **the number
is unchanged, 18/60 (30%)**, and every one of the 18 falls in the
`unresolved_over_7d` bucket — minimum age 10.2 days, oldest 108.9 days,
zero sessions in the 2h–7d range. The original finding was correct; the
query just didn't have a safety margin proving it wasn't a fluke.

**18 of 60 real recent signups — 30% — have a PWC session sitting
unresolved for at least 10 days**, several over a month old (46 days,
in one case; oldest 108.9 days). Of the 28 who started PWC at all,
that's roughly two-thirds never resolving one way or the other. This is
a bigger, more precise number than "PWC is the front door, diagnostic
isn't" — it says the front door itself has a real leak nobody had
quantified before tonight.

### Concrete outputs, this session

- Extends the Surface Matrix / residency format — no new audit
  framework, as decided.
- Five real findings above, each grounded in two actual users' actual
  stored documents, not inference from code alone — then confirmed at
  30-signup population scale via a new script,
  `backend/scripts/pwc_first_session_funnel.py`.
- Feeds directly into Sprint 1/2 planning: the "first insight" concept
  now has a real, instrumented candidate location — `pattern_verdict`
  (Case A/B/C, backed by the pattern-decay model), the actual signal a
  PWC player sees on the in-session postgame card (correction above:
  earlier in this doc this was misattributed to `coach_prescription`,
  which is real but never reaches this screen). Now fired as
  `pwc_insight_shown` (`frontend/src/lib/analytics.js`,
  `PostGameReflection.jsx`), with a real `move_number` field added
  server-side. The mid-session abandonment finding is a genuinely new
  item, quantified at 30% of real signups, not previously tracked
  anywhere in the Evidence Board or Surface Matrix.

### What this residency could not do

Sprint 1 also asked for five real-session observations (watching actual
user sessions, not database traces). **Blocked, flagged explicitly
rather than fabricated**: this requires live PostHog session-replay
access or equivalent, which I don't have. PostHog session recording has
been live since 2026-04-21 (confirmed earlier this governance cycle),
so the capability exists — it just needs a human with dashboard access
to either watch 5 real sessions directly, or grant/share that access.
Everything in this residency that *could* be done without it — the two
full journeys traced from raw stored documents, the 60-signup funnel,
the `pattern_verdict`/`coach_prescription` architecture correction, and
the new instrumentation — was done. This one item is a genuine capability
gap, not a shortcut taken.

---

## Session 4 — Game Review (not yet started)
