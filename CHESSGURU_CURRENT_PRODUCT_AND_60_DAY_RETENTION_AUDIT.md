# ChessGuru — Current Product and 60-Day Retention Audit

**Date:** 2026-09-16
**Audited against:** `origin/working-code` @ `39d12f42`; production deploy @ `0b32aaa5`
(container built 2026-09-16 14:31 UTC), production MongoDB `chess_coach` via the
27018 tunnel, and the live site `https://chessguru.ai`.
**Method:** read-only. No product code was changed. Every number below was
re-derived this session by a script run against production data, or by rendering
real user games through the live V5 pipeline with `persist_learning_side_effects=False`.

> **Note on the local checkout.** The working copy at `C:\Users\MIISCO\smartchesscoach`
> was **358 commits behind** origin when this audit started (local
> `V5_COACHING_VERSION = 137`, production `= 165`). Everything below was audited
> from a worktree at `origin/working-code`, not the stale local tree. Any audit run
> against the local checkout in recent weeks was auditing a different product.

---

## 1. Executive verdict

**AMBER, leaning red on the one thing that matters most.**

ChessGuru has built a genuinely good deterministic chess-coaching engine and
wrapped it in a product almost nobody completes. The engine is real: rendering
1,227 moves from 12 real user games through the live pipeline produced **zero
silent moves and a 97.4% claim-verification pass rate** — it abstains rather than
confabulates, which is rare and hard-won. But the product's central promise —
*"a coach that knows your mistakes and proves you're fixing them"* — has never been
delivered to a single real user. Across all of production history, **0 of 213
weakness-focus records have ever had an outcome measured** (`current_metric` is
null on every one), **0 have ever resolved to improved/regressed/stuck**, and 37
real users have been sitting on an "active focus" for 76 days with a
`locked_until` of `null`, which makes them permanently invisible to the job that
would close the loop. Meanwhile **65% of real users get no personal focus on their
home page at all**, and of the 35% who do, **100% receive the identical coaching
sentence, word for word**.

Retention is what you would predict from that: of 117 external users, **D7 return
is 5.3%**, only 2 users have ever had 10 active days, and the flagship
Play-with-Coach feature has a **median session length of 6 moves** with 48%
abandoned before move 6. Zero users have ever completed a payment.

The single biggest commercial risk is that **the differentiator is unproven, not
just unbuilt** — you cannot yet show one screenshot of ChessGuru telling a real
user "this stopped happening," because the measurement has never run end-to-end.
The single biggest opportunity is that **it is wiring, not research**: when I ran
the outcome measurement by hand against production today, it returned real
verdicts for 14 of 42 live focuses (4 improved, 6 regressed, 4 stuck). The proof
loop is one query fix and one backfill away from producing the exact sentence the
entire product is sold on.

**Verdict: Amber.** Do not charge yet. Do not run paid acquisition. You are roughly
two focused weeks of wiring away from having something worth a paid beta, and you
should not spend those weeks on new features.

---

## 2. What is genuinely working today

Each item here was verified this session, not taken from a doc.

**1. The caption engine has total coverage and does not lie.**
Rendered 12 real user games (1,227 moves) across four rating bands through
`generate_game_decryption_v5` at production version 165:

- 0 blank captions (0.00%)
- Verification verdicts: 1,195 `pass`, 21 `not_applicable`, 11 `fail_recovered`, **0 hard failures**
- `→HELD` / `→SOFTENED` fallback markers appear throughout, meaning the pipeline
  abstains from claims it cannot verify rather than inventing them.

This is the strongest asset in the codebase. It is not the bottleneck.

**2. The best mistake captions are genuinely good coaching.**
Real, unedited production output:

> *"Qa4 leaves your knight on f3 undefended, and after Qxf3 you simply lose it for
> nothing; better was Rg3, since it defends f3. Before you commit a move, check what
> your opponent can capture and count the trade first."*
> — 325-rated user, move 16, cp_loss 175, `distilled:one_move_blunder`

> *"Qxc4 runs into Nxc4, losing your queen on c4; instead Bxe4 was stronger because
> it captures the knight on e4, whereas Qxc4 hands material away. Before any quiet
> move, check that it doesn't run into a tactic that loses a piece."*
> — 1879-rated user, move 27, cp_loss 560, `distilled:walked_into_tactic`

What → why → better move → transferable rule, in plain English, no jargon, no
centipawns. That is the product working exactly as designed.

**3. Live in-game focus-aware nudges exist and are excellent when they fire.**

> *"⚠ Your queen on b3 is hanging — defend before you move. That's your piece safety
> focus this week."*

This is the promised product in one sentence: live, specific, tied to the user's
named weakness. It is real and it is in production.

**4. The engine work is fast, consistent, and cheap to serve.**

- Depth 18, engine version P2.4 across 15,352 analyses — no version drift.
- `started_at → completed_at`: **median 1.3 min, p90 2.4 min** per game. Tight distribution.
- `allow_llm_polish=False` on the production call path (`backend/routes/coach.py:1263`),
  and `llm_caption_generator` is not referenced by `caption_pipeline.py` or
  `game_decryption_v5_service.py`. **The coaching path makes no LLM calls.** Marginal
  cost per caption is effectively zero — a real and underrated commercial advantage.

**5. Analysis integrity is clean where it counts.**

- 0 orphan analyses, 0 duplicate analysis rows across 15,518 records.
- `cognitive_gap` category accuracy was measured and corrected (king_safety misfire 33.6% → 0.8%).

**6. The team's own honesty instrument is real.**
`docs/product_correctness_review_2026_09_11.md` is a standing list of 6 fixed and
11 open correctness defects, each with a re-derivation script. Finding 15 ("The
outcome loop could never finish a focus, and the obvious fix would have lied") and
finding 17 (Phase 8 counts always zero) were written by the team *against itself*.
I independently re-verified findings 8 and 17; both hold. This culture is an asset
and should be cited, not re-derived.

---

## 3. What is claimed, incomplete, broken, generic, or unproven

### 3.1 The proof-of-improvement loop has never run. Not once. (**Critical**)

This is the finding that decides everything else.

| Check | Result |
|---|---|
| Weakness-focus records in production | 213 |
| …with `baseline_metric` written | 213 (100%) |
| …with `current_metric` written | **0 (0%)** |
| …ever resolved `improved` / `regressed` / `stuck` | **0** |
| Stored resolutions | `measurement_pending` 36, `metric_gap` 18, `no_data` 9, `None` 164 |
| Active focus statuses | dominated by `superseded_v6/v7/v8/v9` — replaced by an algorithm version bump, never by the user fixing anything |

**Why it never runs.** `focus_outcome_loop()` in `backend/server.py:95-146` selects
foci whose `locked_until` is a date or string ≤ now. **39 of 92 active foci have
`locked_until = null`** — they match no branch of that query and can never be
selected. 37 belong to external users and have been stuck for a median *and*
maximum of **76 days**. Of the rest, none are currently due (next unlock in 2 days,
furthest in 15).

And when one does come due, the nightly cron log at `/var/log/assign_focuses.log`
shows what happens:

```
=== Step 1: 2 expired active focuses to check ===
  user user_3798d8af93ed  topic=missed_tactic        → measurement_pending (None%)  action=extend
  user user_d35b37459e10  topic=tactical_oversight   → no_data (None%)              action=extend
```

`action=extend` pushes `locked_until` forward. The focus never closes. The user is
never told anything.

**But the measurement now works.** I ran `check_focus_outcome` directly against all
42 live external focuses this session:

| Verdict it would return today | Count |
|---|---|
| `no_data` (fewer than 3 games since the focus started) | 17 |
| `measurement_pending` | 11 |
| **`regressed`** | **6** |
| **`stuck`** | **4** |
| **`improved`** | **4** |

**14 of 42 users (33%) could be told something true and specific about their own
improvement right now.** The intelligence exists. It is sitting behind a `null` in
a query filter.

### 3.2 "A coach that knows *your* mistakes" is not what users experience (**Critical**)

I called `get_active_focus_bundle` — the function feeding the home-page rail — for
all 117 external users:

| Outcome | Users | % |
|---|---|---|
| **No focus bundle at all** (home shows nothing personal) | **76** | **65.0%** |
| Has a focus bundle | 41 | 35.0% |
| …of those, with **zero** recent decisions measured | 41 | **100%** |
| …of those, receiving the **identical** coaching narrative | **41** | **100%** |

All 41 users who see a diagnosis see this exact sentence:

> *"I found the same board problem in several of your games: the piece you had just
> moved could be taken immediately. We will build one final safety check into your move."*

It is a good sentence. It is the same sentence for everyone.

Underneath, the diagnosis concentration is worse:

| Focus topic | Users | % of active foci |
|---|---|---|
| `piece_safety` (`destination_safety_exact`) | 34 | **81.0%** |
| `threat_awareness` | 5 | 11.9% |
| `missed_tactic` / `tactical_oversight` / `punish_blunders` | 3 | 7.1% |

33 of those 34 were assigned on a single day — **2026-09-11** — by
`migrate_destination_safety_focus.py`. That is a migration, not a diagnosis. The
three heaviest users in the system (1,722 / 1,245 / 1,197 analysed games; ratings
1369 / 1734 / 1214) all carry the identical topic, identical metric name, and
identical start date.

**Worse: five users have a named weakness supported by zero evidence.**

```
user_ec372fe556a  threat_awareness  value=0.0  occurrences=0  over 18 games
user_59c9df7e4a3  threat_awareness  value=0.0  occurrences=0  over 21 games
user_10df6acaf61  threat_awareness  value=0.0  occurrences=0  over 11 games
user_fcee29728e5  threat_awareness  value=0.0  occurrences=0  over 10 games
user_e6ae24675e2  threat_awareness  value=0.0  occurrences=0  over 11 games
```

Mitigating fact, verified: `get_active_focus_bundle` returns `null` for these
users, so the false claim is **not rendered** — they simply see nothing. The system
fails safe. But the record still says "this is your weakness" on zero occurrences,
and any future surface that reads it without the same guard will publish a false
statement about a real person.

### 3.3 The live Play-with-Coach voice violates the project's own rules (**Critical**)

288 coach messages were sent in the last 45 days; **162 went to external users**, so
this is not internal testing. Scanned against rules this project has already
written down for itself:

| Violation | Count | % | Example (verbatim, production) |
|---|---|---|---|
| Raw centipawns shown to a 600–1500 audience | 145 | **50.3%** | *"You played f3 in 0.0s — that turned into a blunder (605cp lost)."* |
| Impossible move time `0.0s` → advice built on false data | 104 | **36.1%** | *"…Take a few more seconds before you move next time."* |
| Pure move announcement, zero coaching | 110 | 38.2% | *"I played Nf6. Your turn!"* |
| **Failure scoreboard** ("your Nth … today") | 61 | **21.2%** | *"That's your 13th tactical seq loss today."* |
| **Detector id leaked to the user** | 41 | 14.2% | *"…your 13th destination safety exact today."* |
| **Clean coaching (no violation, not a bare announcement)** | **33** | **11.5%** | |

Three of these are explicit, documented violations of rules this project wrote for
itself: never show a failure scoreboard, never leak a detector id, never show
centipawns to this audience. They are live right now.

The `0.0s` figure is a data bug, not a phrasing bug: `coach_sessions.move_history`
contains **no `time_taken` values at all**. The coach is telling users they moved
instantly, and prescribing "slow down", from an empty field.

### 3.4 Game-review captions explain *what*, not *why*, more than half the time (**High**)

Across the 130 mistake-class moves in the 12 freshly rendered games:

| | Count | % |
|---|---|---|
| Caption carries a causal "why" | 57 | 43.8% |
| **Caption names a better move but never says what went wrong** | **73** | **56.2%** |

And it is worst precisely in the target market:

| Rating band | Captions carrying a why |
|---|---|
| **under 1000** | **39%** |
| **1000–1399** | **30%** |
| 1400–1799 | 57% |
| 1800+ | 41% |

Real examples of the hollow path:

> *"You played cxb5; Qg4 was stronger — it attacks the knight on f3."* (cp_loss 279)

> *"You played Nf3; Ne2 was stronger — it develops a piece."*
> (cp_loss **10,452** — the opponent has mate-in-one after this move. The caption
> says "develops a piece.")

> *"Again you pass up Re1 (taking the open file) — it's still the strongest move here."*
> (cp_loss **9,684**; the actual event is that the opponent now has `Qh2#`)

The mate information exists — it is sitting in the `socratic_coaching` object on
those same moves. The headline caption, which is what the user reads first, does
not use it.

### 3.5 Severity labels contradict the engine on 1 in 9 flagged moves (**High**)

**14 of 130 (10.8%)** mistake-class moves carry a `cp_loss` under 50. Five are
labelled **blunder with `cp_loss = 0`** and carry a *praise* caption:

| Move | Label | cp_loss | Caption shown |
|---|---|---|---|
| Kf7 | **blunder** | 0 | *"Kf7 answers the check, and it is the move to play here."* |
| Kh2 | **blunder** | 0 | *"With only 3 legal moves, Kh2 was close to forced and it is the right one."* |
| fxe4 | **blunder** | 0 | *"fxe4 takes the pawn back to level the material — an even trade."* |
| c4 | **blunder** | 0 | *"You moved your pawn with c4. This helps guard your other pieces…"* |
| e5 | **blunder** | 0 | *"You moved your pawn with e5…"* |

This is user-visible: `frontend/src/components/GameDecryptionV5.jsx:1312-1324`
renders the severity badge and only suppresses it when severity is absent or
`"context"`. A beginner is shown a red "blunder" badge on a forced, correct king
move. Nothing destroys a coach's credibility faster.

Two of those captions also teach opening principles ("let your pieces come out to
play") at **move 26 and move 29** — wrong phase of the game entirely.

### 3.6 The return-trigger machinery reaches nobody (**Critical for retention**)

| Mechanism | Reality |
|---|---|
| In-app notifications | **13,395 total. 13,394 are `game_analyzed`. 100% unread — not one has ever been opened.** |
| Daily digest email | 43 sent since 2026-07-14. **All 43 went to one address: the founder's.** Zero external users have ever received one. |
| Re-engagement email | **2, ever**, across the product's lifetime. |
| `prescription_completed` notification | **1, ever.** |

The subjects are good (*"Yesterday's games: king safety showed up again"*). They
have simply never been sent to a customer. There is no cron entry for the digest on
the production box — `crontab -l` contains a backup job and `run_assign_focuses.sh`,
nothing else for ChessGuru.

### 3.7 The product cannot see half of every game (**High — caps the coaching ceiling**)

Independently verified this session: of **96,056 stored move evaluations across
3,000 analyses, exactly 0 are opponent moves.**

ChessGuru analyses the user's moves and discards the opponent's. At 600–1500,
opponents blunder 2.6–4.0 times per game. *"Your opponent just hung a rook and you
played something else"* is the single most motivating coaching category at this
rating — and it structurally does not exist in this product. It also means `/lab`,
`/review` and every "what did I miss" surface can only ever show the user's own
errors, never their missed opportunities.

### 3.8 Data-trust defects a coach cannot afford (**High**)

| Defect | Measurement |
|---|---|
| **Failed analyses** | 733 games (4.5%), affecting **43 of 65 users with games (66%)** |
| **Duplicate imports** | 557 extra copies of identical PGNs; **26 of 65 users (40%)** affected; worst user has **81 duplicates**. Import is not idempotent — and duplicates inflate every "you did this N times" count the coaching rests on. |
| **Mixed eval units in one field** | In an 11,646-value sample, 9,004 look like centipawns and 2,642 look like pawns. Already logged as finding 7 in the correctness review; still open. |
| **No account deletion** | There is no delete-account or data-export endpoint anywhere in `backend/routes/`. The product takes live Razorpay payments from Indian users and publishes a privacy policy, with no erasure path. |

### 3.9 Time-to-first-insight is measured in days, not minutes (**Critical for activation**)

The raw material arrives fast. The diagnosis does not.

| Stage | Median | p90 |
|---|---|---|
| Signup → 10 games **imported** | **4.3 min** (77% within 1 hour) | — |
| Per game: queued → analysis complete | 1.9 min | **204 min (3.4 h)**; p99 **9.6 days** |
| Signup → 10 games **analysed** (the threshold to get a focus at all) | **~19 days** | — |

- Reached a usable diagnosis **within 1 hour of signup: 10%**
- **Within 24 hours: 12%**
- **Ever: 44%**

The bottleneck is unambiguously the analysis queue's tail — not import, and not the
engine (engine time itself is a tight 1.3 min median). A new user connects, sees
their games appear in four minutes, then waits — often days — for the product to
have anything personal to say.

### 3.10 Monetisation is wired but hollow (**High**)

- Razorpay **live** key (`rzp_live_…`) is configured in production. `/pricing`,
  `/terms`, `/privacy`, `/refund`, `/contact` all exist and return 200. The plumbing
  is real.
- Price: `PRO_PLAN_PRICE_PAISE = 14900` → **₹149/month**.
- **The only enforced gate in the entire product is 1 Coach-Mode Play-with-Coach
  session per day** (`backend/routes/coach_play.py:7509-7531` → `can_start_pwc_session`).
- `PLAN_LIMITS` declares `monthly_analysis_limit` of 5 (free) and 25 (pro) — but
  **`monthly_analyses_used` is never incremented anywhere in the codebase**. It is
  only ever *reset to 0* on upgrade (`backend/routes/billing.py:255`). The limit
  never bites. Game import, analysis, game review, patterns, training and progress
  are all free and unlimited.
- Total payments: **3 `payment_intent` records ever, all from test accounts
  (`test@chessguru.ai`, `test1@gmail.com`), all still `status: created`. Zero
  captured payments. Zero external users have ever reached checkout.**
- A pro plan capped at 25 analyses/month would be *worse* than the free experience
  users get today, for a user playing 5 games a week. If that limit were ever
  switched on as written, it would break the product for paying customers.

---

## 4. Exact new-user experience audit

### The activation funnel, measured (117 external users; internal/test accounts excluded)

| Stage | Users | % |
|---|---|---|
| Signed up | 117 | 100% |
| Completed onboarding | 80 | 68.4% |
| **Connected Chess.com or Lichess** | **58** | **49.6%** |
| Has ≥1 imported game | 65 | 55.6% |
| Has ≥1 analysed game | 65 | 55.6% |
| Has ≥10 analysed games (threshold to get a focus) | 53 | 45.3% |
| Has an active focus record | 51 | 43.6% |
| **Actually sees a focus on Home** | **41** | **35.0%** |
| Played ≥1 Play-with-Coach game | 73 | 62.4% |
| Attempted ≥1 puzzle | 26 | 22.2% |
| Started the diagnostic | 23 | 19.7% |
| **Completed the diagnostic** | **2 of 40 sessions** | **5%** |
| **Paid** | **0** | **0%** |

Half of everyone who signs up never connects an account — and connection is the one
action the entire product depends on.

### Persona 1 — "Rahul", 900, adult casual, 3–5 rapid games/week

**First 5 minutes.** The landing page is strong and on-message ("Your games already
contain the answer", "Free to start · No credit card"). He signs up, connects
Chess.com, and within ~4 minutes sees his games listed. So far, good.

**Then he waits.** With ~90% probability he does not have a usable diagnosis within
the hour. The most likely next action is "Play a game with your coach" — 62% of
users do this.

**In that game**, on the evidence of the last 45 days, roughly one message in nine
is clean coaching. He is more likely to see *"You played d4 in 0.0s — that turned
into a blunder (386cp lost). Take a few more seconds before you move next time."* He
did not move in 0.0 seconds; he does not know what 386cp means. Median session
length across all Play-with-Coach games is **6 moves**, and **48% end before move 6**.

**Can Rahul answer the five questions after one session?**

| Question | Answer today |
|---|---|
| What am I doing wrong repeatedly? | **No.** 65% chance Home shows nothing personal. If he's in the lucky 35%, he gets the same "piece safety" sentence as 40 other people. |
| What should I focus on this week? | Partially — *if* he has 10 analysed games, which 88% of users don't have within 24h. |
| What exactly should I do in my next game? | **Weakly.** `next_action` is the literal string `"practice"` for 33 of 42 users. |
| How will I know if I'm improving? | **No.** Zero users have ever had an improvement measured. `/progress` is unavailable to 87 of 128 accounts. |
| Why return tomorrow? | **No mechanism.** No digest email has ever been sent to a real user; 13,394 notifications sit 100% unread. |

**Verdict: Rahul does not convert.** The measured D7 return rate for users like him
is 5.3%.

### Persona 2 — "Aarav", 1200, ambitious teen, 1–2 games most days

Aarav is the user who *would* generate the data that makes ChessGuru work — he
plays daily, so the "did it stop happening?" measurement would actually have games
to run on.

- **Does it detect patterns across games?** Yes, technically — `user_pattern_events`
  holds 116,833 rows and `move_observations` 497,659. The detection is real.
- **Does it distinguish a one-off from a recurring leak?** In the data model, yes
  (recency-weighted decay, `picker_evidence_count`). In what Aarav sees, no — he
  gets the same one-line piece-safety narrative as everyone else.
- **Does it produce relevant exercises?** Barely used: **121 puzzle attempts by 17
  external users, ever** (one user accounts for 49 of them), plus 74 training solves
  by 11 users. The training loop is built and unvisited.
- **Does training connect to later games?** **No.** `puzzle_recovery_credits` has 10
  rows. The link from "I drilled this" to "it stopped happening in my games" does
  not exist in the data.
- **Will he detect shallow repetition?** Immediately. Half of the 1,035 live coach
  messages are exact duplicates of another message. The most repeated non-opening
  message is *"This position has a complex structure character. Look for tactical
  opportunities and strategic imbalances"* — 30 times, saying nothing about any
  position.

**Verdict: Aarav is the best-fit user and the harshest critic.** He would conclude
within two sessions that the feedback is templated. He would be right — and the fix
is the same one everything else needs.

### Persona 3 — "Neha", parent of an 8–12 learner, not a chess player

- **Can she understand it without chess knowledge?** The landing page and focus
  narrative, yes — they are written in plain English and that is a real achievement.
  The game review, no: she hits `Qa4`, `Rg3` and severity badges immediately.
- **Does it show growth in language a parent values?** **No.** There is no
  parent-facing view, no child account, no weekly summary that has ever been sent,
  and the improvement metric has never been computed for anyone. `/progress` shows
  an "unavailable" state to 68% of accounts.
- **Visible proof beyond rating change?** None today. `user_active_focus.current_metric`
  is null for every user in the system.
- **Safe, structured, worth paying for?** Structure exists in the code (focus →
  lesson → drill → re-measure) but has never completed a single cycle. There is also
  no account-deletion path, a hard blocker for a product asking parents to enrol a
  minor.

**Verdict: Neha is not addressable today.** She needs a separate product surface
(child profile, weekly parent report, "what your child learned this week") that does
not exist in any form. Do not chase this segment until the improvement loop produces
output — the parent offer *is* the improvement report.

---

## 5. Chess coaching-quality scorecard

| Dimension | Score | Basis |
|---|---|---|
| Chess correctness | **8/10** | 97.4% verification pass on 1,227 rendered moves; 0 hard failures; depth-18 consistency. Docked for 10.8% severity/engine contradictions and mixed eval units. |
| Explanation clarity | **7/10** | The good captions are genuinely excellent plain English. Docked hard because 50.3% of *live* coach messages leak centipawns. |
| Rating appropriateness | **5/10** | Thresholds are rating-banded in code, but why-coverage is *worst* in the target band (30–39% vs 57% at 1400–1799), and beginner captions teach opening principles at move 29. |
| Personalisation | **3/10** | 65% of users see nothing personal; 100% of the rest see the identical sentence; 81% get the same topic, 33 of them assigned by a migration on one day. |
| Actionability | **5/10** | Best captions end with a transferable rule. But `next_action` is the literal string `"practice"` for 33 of 42 users, and 56.2% of mistake captions never say what went wrong. |
| Pattern-detection credibility | **6/10** | Detection is real and large (116k pattern events, 497k move observations) and precision work has been done. Docked for 5 users assigned a weakness on **zero** occurrences, and duplicates inflating counts for 40% of users. |
| Training relevance | **4/10** | Pools are large (23k community puzzles, 43k training positions) but only 26 users have ever attempted one, and nothing connects a drill to a later game. |
| **Proof of improvement** | **1/10** | 0 of 213 focuses ever measured. 0 verdicts ever issued. `/progress` unavailable to 68% of accounts. Phase 8 post-enrollment counts always zero. The one point is for the code now being capable. |
| Emotional motivation | **3/10** | Failure scoreboards ("your 13th … today") in 21% of live messages; no celebration has ever fired; no digest has reached a user; 100% of notifications unread. |
| Trustworthiness | **5/10** | Right-or-silent design and self-audit culture are real strengths. Undercut by "blunder" badges on forced correct moves, `0.0s` claims from an empty field, and 66% of users having a failed analysis. |

**Weighted read: the engine scores ~7.5; the experience scores ~3.5.** That gap is
the whole roadmap — and it is the same conclusion the team's own launch-readiness
report reached, here independently confirmed with fresh numbers.

---

## 6. 60-day retention diagnosis

### Measured retention

117 external users. Activity derived from logins, sessions, coach games, puzzle
attempts, learning sessions, diagnostics and product events; backfill-contaminated
sources excluded.

| Window | Returned at least once |
|---|---|
| D1 | **5.2%** (6/115) |
| D7 | **5.3%** (6/114) |
| D14 | **4.5%** (5/112) |
| D30 | **5.7%** (6/105) |
| D60 | **8.9%** (8/90) |

| Depth of use | Users |
|---|---|
| ≥2 distinct active days | 35 (30%) |
| ≥5 active days | 6 (5%) |
| **≥10 active days** | **2 (1.7%)** |

**Corroborated independently.** A reasonable objection is that this activity-based
measure undercounts — a user who browses without triggering any of the eight event
sources would be invisible. So I checked a second, unrelated signal:
`users.last_login`. **Only 8 of 117 external users have a `last_login` more than one
day after their `created_at`.** Two independent methods agree on the same order of
magnitude (6/114 vs 8/117), so the low figure is not a measurement artefact.

> **Required caveat, and it is a real one.** These ~120 accounts predate most of the
> features audited here, and ChessGuru has not launched. These numbers are *not* a
> verdict on the current feature set. What they do measure honestly is the **front
> door** — connect rate, time-to-diagnosis, first-session behaviour — none of which
> has materially changed. Treat D7 = 5.3% as a measurement of the onboarding path,
> not of the coach.

### The 60-day journey, as the product behaves today

| Time | What the user does | What ChessGuru gives | Value felt | Reason to return | Dropout risk | What should happen and does not |
|---|---|---|---|---|---|---|
| **First 5 min** | Signs up, connects Chess.com | Games list populates in ~4 min (median) | "It found my games" — mild | Curiosity only | **50% never connect at all** | One true, specific, uncanny observation from game 1 — inside 60 seconds |
| **First game synced** | Waits | Nothing personal yet. p90 analysis wait 3.4 h, p99 9.6 days | Anticlimax | None | Highest-leverage drop point | Analyse 3 games at depth 12 immediately; show the first mistake card while the rest queue |
| **Day 1** | Likely clicks "Play with Coach" | 1 free Coach session/day; ~11.5% of messages are clean coaching; median session **6 moves** | Mixed to negative — cp numbers, `0.0s` claims | None | **48% abandon before move 6** | A finished game with 2–3 real teaching moments and an end-of-game summary |
| **Days 2–7** | Plays elsewhere, may return | **No email. No push. Notifications 100% unread.** 65% chance Home is still impersonal | None | **Nothing exists** | Where 95% are lost (D7 = 5.3%) | The post-game digest that already exists and has only ever been sent to the founder |
| **Week 2** | If they return | Focus may now exist (needs 10 analysed games — only 44% ever get there) | "It named my weakness" — the real aha, when it lands | Weak | Focus is `piece_safety` for 81%, identical prose | The name should be *theirs*: their position, their move, their count |
| **Days 15–30** | Plays more games | Focus locked for 14–21 days. `current_metric` stays null. `/progress` unavailable to 68% | Flat | None | **Repetition becomes obvious here** — the churn point for anyone who survived week 1 | "Three weeks ago this happened 4× per 10 games. Now it's 1×." The data to say this exists. |
| **Days 31–60** | Mostly gone | Focus gets `superseded_v9` by an algorithm bump, or extends forever on `measurement_pending` | None | None | Terminal | The 60-day payoff: a closed cycle, a named leak that stopped, and the next one chosen |

### Direct answers

- **Current aha moment:** the first genuinely specific mistake caption in game review
  (*"Qa4 leaves your knight on f3 undefended…"*). It is real and it lands. **But it is
  reached by roughly 35% of users and typically not on day one.**
- **Current return triggers:** **none that function.** No digest reaches users, no
  notification is ever opened, no streak, nothing scheduled.
- **Current dropout triggers, in order:** (1) the connect step — 50% lost; (2) the
  analysis wait — 88% have no diagnosis at 24 h; (3) the first PWC session — 48% quit
  before move 6; (4) day 2, when nothing pulls them back.
- **Earliest churn point:** minute 5, at the connect screen. Second: the silent wait
  after it.
- **Why they'd return in week 5:** on today's product, they would not. There is no
  mechanism, and the one thing that would create one — "here's what changed" — has
  never been computed for anyone.
- **Why they'd pay in month 2:** they would not. The only thing behind the paywall is
  unlimited Coach-Mode sessions, and the median session is 6 moves.
- **Evidence of improvement visible today:** none. Evidence that *exists and is not
  shown*: 4 users are genuinely improving, 6 regressing, 4 stuck — computed this
  session. That is the missing loop, and it is one query away.

---

## 7. Competitive truth

| User need | Best free alternative | Does ChessGuru beat it today? | Why | Required differentiation |
|---|---|---|---|---|
| "What was my mistake in this game?" | Chess.com / Lichess review | **No — it loses.** | Their analysis is instant and covers both sides. ChessGuru's p90 is 3.4 h and it **cannot see opponent moves at all** (0 of 96,056 evaluations). | Speed on the first 3 games, plus opponent-blunder coaching, which nobody does well |
| "Why was it a mistake, in words I understand?" | Chess.com Game Review; ChatGPT with a pasted PGN | **Yes, when it fires — 44% of the time.** | The good captions genuinely beat both: verified, no hallucination, plain English, ending in a rule. ChatGPT hallucinates board facts constantly. | Raise why-coverage from 44% to 85%+, especially in the 600–1399 band where it is 30–39% |
| "What is my recurring weakness?" | None of them do this | **Tie — because ChessGuru doesn't deliver it either.** | The data model is genuinely differentiated. But 65% see nothing and 81% of the rest get the same answer. | Per-user specificity: their count, their positions, their name for it |
| **"Am I actually getting better?"** | **Nobody offers this. Rating is the only proxy.** | **No — this is the wide-open moat and it has never run.** | 0 of 213 focuses ever measured. | **Ship the closed loop. This is the entire business.** |
| "Give me practice on my weakness" | Chess.com Puzzle Rush / Lichess puzzles (huge, polished, instant) | **No.** | Their puzzle UX is far better and infinitely available. ChessGuru has 23k puzzles and 121 lifetime attempts. | Only wins if puzzles come from *the user's own games* and feed the improvement measurement |
| "Play and get coached live" | Nothing comparable free | **Yes in principle, no in execution.** | Guardian / focus-aware nudges are a genuine innovation. But 11.5% clean messages and a 6-move median session. | Fix the voice; it is a text-template problem, not a research problem |
| "Structure / what do I do next" | A ₹500–1,500/hr human coach | **No.** | A human coach remembers you, adapts, and tells you when you improved. That is exactly the thing that has never fired here. | The closed loop is also what makes the human-coach comparison winnable |

**The honest summary.** ChessGuru is **better than every free alternative at
explaining why a specific move was wrong, in words a 900-rated player can use — when
it fires.** It is **worse** than free tools at speed, at coverage (it sees half of
each game), and at puzzles. And on the one axis where nobody competes — *longitudinal
proof that a specific leak closed* — it currently ships **nothing**, despite having
the data, the detectors and the measurement code to ship it this week.

> Does ChessGuru create a longitudinal understanding that isolated tools do not?
> **In the database, yes — genuinely and impressively. In the product a user
> experiences, no.** The gap between `user_active_focus` (274 records of real
> longitudinal reasoning) and what a user reads on Home (nothing, for 65% of them) is
> the entire company.

---

## 8. Monetisation recommendation

**Do not launch paid. Do not run paid acquisition. Recommendation: free only for
roughly four more weeks, then a limited paid beta.**

### Evidence for that level

- 0 captured payments, ever. 3 test payment intents, none completed.
- The only enforced paywall is 1 Coach session/day, and the median Coach session is
  6 moves — the gated asset is the one users abandon fastest.
- The declared Pro limit of 25 analyses/month would be *worse* than today's free
  experience for the target user (5 games/week ≈ 20/month, before any history import).
- No account deletion / data export exists, a genuine problem for taking money from
  Indian consumers and a hard blocker for the parent segment.
- Nothing worth paying for has been demonstrated to a single user, because the
  differentiator has never rendered.

### Answers to the pricing questions

1. **What is worth paying for?** Only one thing: *"This leak was costing you 4 games
   in 10. After three weeks it's costing you 1. Here's the next one."* It is currently
   unshipped. Nothing else justifies a subscription against free Chess.com.
2. **What must stay free?** Connect, import, analysis of recent games, the first
   diagnosis, and the first *closed* improvement cycle. The user must experience the
   loop completing at least once before being asked to pay — that completion **is** the demo.
3. **When should the paywall appear?** At the moment the first cycle closes — the
   screen that says "this stopped happening." Not before. That is the only moment in
   the product with earned emotional weight.
4. **What goes behind it?** Continuous re-measurement (cycles 2, 3, 4…), unlimited
   Coach Mode, full history analysis, and the weekly digest. Never gate the first diagnosis.
5. **Is ₹99 too cheap?** ₹99 is the wrong instrument right now — it signals a utility.
   Price on the outcome, not the volume. **₹149/month is correctly placed** and already
   coded; hold it. Discount only via the annual plan (₹1,199/yr ≈ ₹100/mo).
6. **Which segment converts first?** **Adults like Rahul — but only after the loop
   closes.** Teens (Aarav) generate the best data but have the least payment authority.
   Parents (Neha) have the highest willingness to pay and the highest trust bar; the
   parent offer *is* the improvement report, so they are downstream of the same fix.
7. **First commercial wedge:** the ~50 existing users who already have 10+ analysed
   games and a live focus. They are the only cohort whose loop can close within days.
8. **Proof needed before paid acquisition:** at least 20 users who have seen a closed
   cycle, of whom a measurable share returned the following week, plus 3–5 verbatim
   quotes. You have zero of these today.
9. **Do the unit economics work?** **Yes, and this is genuinely good news.** The
   coaching path makes **no LLM calls**. Cost is Stockfish CPU: median 1.3 min/game at
   depth 18. At 20 games/month that is ~26 CPU-minutes/user/month — well under ₹10 at
   any sane cloud rate against ₹149. **The constraint is capacity, not margin:**
   production is a 4-vCPU / 15 GB box (13 GB already used, load 2.7/4) **shared with
   three unrelated products**. That box supports a paid beta; it does not support
   acquisition. Budget a dedicated analysis box before any growth spend.

### The one pricing experiment to run — *after* the loop ships

| | |
|---|---|
| **Target** | The ~50 existing users with ≥10 analysed games and a live focus |
| **Trigger** | The first time their focus closes with a real verdict |
| **Wording** | *"Three weeks ago, you were leaving a piece where it could be taken about once every five games. Over your last 12 games it's happened twice. That's the check becoming automatic. Want me to keep watching and pick your next one? — ₹149/month, cancel anytime."* |
| **Free forever** | Connect, import, game review, the first diagnosis, the first closed cycle |
| **Paid** | Every cycle after the first, unlimited Coach Mode, full history, weekly digest |
| **Conversion event** | `payment_intents.status == "captured"` — which has **never** been written and must be instrumented before the test |
| **Success** | ≥15% of users shown a closed cycle start checkout; ≥8% capture; ≥60% of payers still active at D30 |
| **Failure** | <5% start checkout → the loop closing is not the value moment, and the positioning needs revisiting |

---

## 9. Prioritised roadmap — only what creates 60-day value

| # | Task | Why it matters | User story | Acceptance criteria | Dependencies | Effort | If we don't |
|---|---|---|---|---|---|---|---|
| **1** | **Close the improvement loop.** Backfill `locked_until` on the 39 null foci; make `focus_outcome_loop` select null-lock rows; render the verdict on Home and `/progress`. | The differentiator. 14 of 42 live users would get a true verdict **today**. | "It told me the thing I was working on actually stopped." | ≥20 external users have non-null `current_metric`; `improved`/`regressed`/`stuck` all render on Home; `/progress` unavailable rate below 20%. | None. Measurement code already correct. | **2–3 d** | You have no differentiator and no reason to charge. |
| **2** | **Fix the PWC coaching voice.** Strip centipawns, remove failure scoreboards and detector ids, suppress every message built on the empty `time_taken` field. | 88.5% of live messages are unusable; this is the surface 62% of users touch first. | "The coach talks like a coach." | Clean-message rate ≥80% on a fresh 200-message sample; 0 cp leaks, 0 `0.0s`, 0 scoreboards, 0 detector ids; `pwc_coaching_lint.py` green. | None — text templates. | **2–3 d** | Every first session actively damages trust. |
| **3** | **Analyse the first three games immediately at depth 12.** A priority lane ahead of the bulk queue. | 88% of users have no diagnosis at 24 h. Engine time is only 1.3 min/game — this is queue policy, not compute. | "It told me something true about my chess before I closed the tab." | ≥80% of new users get a first personal insight within 10 min of connecting (today: 13%). | Analysis-worker priority lane. | **3–4 d** | Half the funnel dies in silence. |
| **4** | **Turn on the daily digest for real users.** It exists, is well-written, and has only ever been sent to the founder. | The only return mechanism in the product. D7 is 5.3% with zero triggers. | "It emailed me what yesterday's game showed." | Digest sends to all consenting active users; open and click rates instrumented; cron entry exists on the box. | Email consent + unsubscribe. | **2 d** | There is no reason to come back on day 2. |
| **5** | **Kill the false severity badge.** Suppress blunder/mistake labels when `cp_loss < 50`; reconcile label to caption. | 10.8% of flagged moves contradict the engine; five show a red "blunder" on a forced correct move. | "It doesn't call my forced king move a blunder." | 0 mistake-class moves with `cp_loss < 50` render a severity badge, on a 2,000-move re-render. | None. | **1 d** | One badge destroys the credibility the caption engine earned. |
| **6** | **Raise why-coverage in the 600–1399 band from ~34% to ≥80%.** Route the `socratic_coaching` facts already computed on those moves into the headline caption. | The target market gets the *worst* explanations. The mate-in-1 caption saying "develops a piece" is the canonical failure. | "It told me why my move was bad, not just what to play instead." | Why-coverage ≥80% for u1000 and 1000–1399 on a fresh 200-mistake sample; 0 regression in verified-claim rate. | Use `/distill-caption-template`; do **not** hand-edit R12 predicates. | **5–7 d** | You're a move-recommender, which Stockfish does free. |
| **7** | **Make the diagnosis personal.** Replace the shared narrative with the user's own count, their own positions, and a short memorable name for the leak. | 100% of users who see a focus see the identical sentence; 81% get the same topic. | "It described *my* mistake, with my games as proof." | ≥5 distinct narratives across users; every focus card shows ≥2 of the user's own positions and their own occurrence count. | Task 1 (so the count is live). | **4–5 d** | "Personal AI coach" is not a defensible claim. |
| **8** | **Make import idempotent and retry failed analyses.** | 40% of users have duplicate games (worst: 81); 66% have a failed analysis. Duplicates inflate every count the coaching asserts. | "It doesn't show me the same game twice or count it twice." | 0 new duplicates on a re-sync test; failed-analysis rate <1%; existing 557 duplicates merged. | None. | **3 d** | Every "N times" claim is provably wrong for 40% of users. |
| **9** | **Analyse opponent moves going forward at depth 12.** | Unlocks "you missed a free rook" — the highest-motivation category at 600–1500, currently structurally absent (0 of 96,056 evaluations). | "It showed me the chance I missed when my opponent blundered." | Opponent evaluations present on 100% of new analyses; ≥1 missed-opportunity caption per game at these ratings. | Task 3 (queue capacity). Do **not** backfill 15k games. | **4–5 d** | You permanently coach half of chess. |
| **10** | **Cut the diagnostic from 20 positions to 5.** | 42% abandon before answering puzzle 1; 2 of 40 sessions have ever completed. | "I finished it and it told me where to start." | Completion rate ≥50% on the next 20 sessions. | None. | **2 d** | The no-games cold start stays a dead end. |
| **11** | **Ship account deletion and data export.** | No erasure path exists while taking live payments from Indian consumers. Hard blocker for the parent segment. | "I can delete my account and my data." | `DELETE /api/account` removes or anonymises all user rows; export returns games + analyses; linked from `/settings`. | None. | **2 d** | Compliance exposure and a blocked segment. |
| **12** | **Instrument the funnel end-to-end** (see §10). | `product_events` has 131 rows total. You currently cannot tell whether any of the above worked. | — | All 8 core events firing; a dashboard showing the §4 funnel refreshed daily. | None. | **3 d** | You'll ship 1–11 and still be guessing. |

**Explicitly do not build now:** new lesson content, more openings, social/leaderboards,
voice, mobile apps, new detectors, the parent product, or anything behind a new
feature flag. The codebase already has **62 routes, 109 collections and ~23,000
community puzzles that 26 people have ever touched.** The disease is not missing
features — it is that built features never reach users. Every hour spent on tasks
1–5 is worth more than any new capability.

---

## 10. Metrics and instrumentation to add now

`product_events` currently holds **131 rows for the product's entire history**.
Everything below must be a server-side event so it cannot be lost to ad-blockers or
client failures.

| Metric | Event definition | Numerator / Denominator | Why it matters |
|---|---|---|---|
| **Connect rate** | `platform_connected{platform}` | users with ≥1 connect ÷ users with `account_created` | Today **49.6%**. Half the funnel dies here; cheapest thing to move. |
| **Time to first personal insight** | `first_insight_shown{kind, seconds_since_signup}` | p50 / p90 of the delta | Today only **13%** within 10 min. This is the activation number. |
| **Diagnosis coverage** | `focus_rendered{topic}` vs `focus_empty{reason}` | users seeing a focus ÷ active users | Today **35%**. Must exceed 80% before any paid test. |
| **Diagnosis distinctness** | distinct `coaching_narrative` hashes | distinct narratives ÷ users with a focus | Today **1 ÷ 41**. The cleanest single measure of "is this actually personal". |
| **Cycle completion (north star)** | `focus_closed{resolution, delta_pct, days_open}` | focuses closed with a real verdict ÷ focuses opened | Today **0 ÷ 213**. If this stays 0, nothing else matters. |
| **Coaching cleanliness** | nightly lint over sent messages | clean messages ÷ total sent | Today **11.5%**. Gate deploys on ≥80%. |
| **Why-coverage** | offline render audit, per rating band | mistake captions with a causal why ÷ all mistake captions | Today 44% overall, **30–39% in the target band**. |
| **First coaching action** | `coaching_action_completed{kind}` | users completing ≥1 ÷ users shown a focus | Today ~22% attempt a puzzle; drill→game linkage absent. |
| **PWC session depth** | `pwc_session_ended{moves, reason}` | median moves; % under 6 | Today **median 6, 48% under 6**. Clearest engagement-quality signal. |
| **D1 / D7 / D14 / D30 / D60** | any qualifying activity event | returning users ÷ cohort eligible at that age | Today 5.2 / 5.3 / 4.5 / 5.7 / 8.9%. Re-measure monthly on a fresh cohort only. |
| **Digest performance** | `digest_sent` / `digest_opened` / `digest_clicked` / `digest_return` | opens ÷ sends; returns ÷ sends | Today unmeasurable — 43 sends, all internal. |
| **Notification value** | `notification_opened` | opens ÷ sent | Today **0 ÷ 13,395**. If it stays 0, delete the surface. |
| **Felt-personal signal** | one-tap 👍/👎 on the focus card, plus free text | positives ÷ responses | You have **no** direct user-perception signal today. Cheapest to add, most informative. |
| **Checkout / conversion** | `checkout_started` → `payment_captured` | captured ÷ shown paywall | `payment_intents` has never reached a state past `created`; capture is not instrumented. |
| **Churn** | subscription cancel / lapse | cancels ÷ active payers | Cannot exist until there are payers. |
| **Cost per analysed game** | engine seconds × instance rate, from `duration_seconds` | total CPU-seconds ÷ games analysed | Today ~1.3 CPU-min/game. Watch the **capacity** ceiling (4 shared vCPUs), not the margin. |
| **Behaviour change by category** | `focus_closed.delta_pct` grouped by topic | mean delta per topic | The evidence base for every future coaching claim — and for the marketing. |

---

## 11. Final decision

**1. What should we build next week?**
Tasks 1–5 only: close the improvement loop (backfill the 39 null `locked_until` rows
and widen the selector), clean the Play-with-Coach voice, give new users a depth-12
fast lane for their first three games, switch the daily digest on for real users, and
kill the false severity badge. That is roughly 10 working days, and it converts the
product from "an engine nobody finishes using" into "a coach that closed a loop."

**2. What should we stop building for now?**
New detectors, new lesson content, new openings, the parent product, voice, mobile,
and anything behind a new feature flag. Stop adding surfaces — 62 routes, 109
collections and 23,000 puzzles that 26 people have touched is already the problem.
Also stop auditing from the local checkout: it was 358 commits and 28 caption
versions behind production when this audit began.

**3. What should we test with real users in the next 14 days?**
Take the ~50 users who already have 10+ analysed games and a live focus, close their
cycle, and show them the verdict — including the 6 who are *regressing* and the 4 who
are *stuck*, not only the 4 improving. Then watch two things: did they come back
within 7 days, and what did they say. Five observed sessions beats any dashboard at
this stage.

**4. What result would prove ChessGuru is on a strong path?**
≥20 users see a closed cycle; ≥40% of them return within 7 days; and at least five say
some version of *"it knew that had stopped"* unprompted. Plus: connect rate above 65%,
first insight within 10 minutes for ≥80% of new users, and coaching-cleanliness lint
above 80%. If those land, run the ₹149 experiment in §8 and start planning a dedicated
analysis box.

**5. What result would tell us to revisit the positioning or target segment?**
If users are shown a true, verified closed cycle — *"this leak was costing you 4 games
in 10, now it's 1"* — and they still do not return, the core hypothesis is wrong. Proof
of improvement would not be the motivator we believe it is, and the answer would be to
pivot toward what users *do* engage with: live in-game coaching during play, sold as a
practice partner rather than a progress tracker. Watch for a second signal too — if
after task 7 the diagnosis still collapses onto `piece_safety` for most users, then the
weakness taxonomy is too coarse to support a personal-coach claim at all, and that is a
research problem to solve before any growth spend.

---

## Appendix — what could not be verified, and how that limits confidence

| Not verified | Effect on confidence |
|---|---|
| **Visual / mobile rendering.** No browser tool was available; all frontend findings come from source. The app is Tailwind + a `cg-*` design system with a viewport meta and 8 media queries, but I did not see a page render at phone width. | Mobile UX claims in §4 are **inference, not observation**. Given India-first positioning, this needs a real device pass before launch. |
| **Live signup walkthrough.** Registering would have written to production. The new-user path is reconstructed from code plus real timestamps of 117 users. | Funnel percentages are measured and solid. The subjective first-5-minutes narrative is reasoned, not observed. |
| **Retention attribution.** The ~120 accounts predate most audited features and ChessGuru has not launched. | D1–D60 figures measure the **front door**, which has not changed, not the current coach. Flagged wherever cited. |
| **`analyzed_at` timestamps** are rewritten by re-analysis backfills — an early 12-day median computed from that field was contaminated and is not used. All latency figures come from `analysis_queue` (`queued_at`/`started_at`/`completed_at`, `reanalysis` excluded), n=13,246. | Latency figures are sound; the discarded one is noted so it is not repeated. |
| **Email deliverability / open rates.** No provider data accessible; `digest_email_log` records sends only. | Cannot assess spam risk or engagement. Instrument before turning the digest on (task 4). |
| **Razorpay dashboard.** Assessed from `payment_intents` and code only. | "Zero captured payments" is inferred from the absence of any state past `created`; a dashboard check should confirm. |
| **Caption sample size.** The quality audit covers 12 games / 1,227 moves / 130 mistake-class moves across 4 rating bands — enough for the large effects reported (56% no-why, 81% topic concentration), not enough to characterise rare caption categories. | Directional findings are safe; per-subtype rates need a larger render. |
