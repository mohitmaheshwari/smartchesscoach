# Play with Coach — "A coach beside you, not a coach stopping you"

Status: **DRAFT — awaiting Mohit sign-off.** No code until signed.
Written: 2026-10-13
Audit base: **`origin/working-code` at `9cfbbbf9`.** Every code claim below was
re-verified with `git grep origin/working-code` after the first pass, because the
local checkout was 134 commits behind. All claims held; line numbers are origin's.
Author: Claude (smartchesscoach-04), with verified input from sessions -24, -1d, -53, -01

---

## 0. Existing surfaces audit

### 0.1 The headline finding

**This vision is the third approved plan for Play with Coach in one month, and it
substantially restates the first one.** Before scoping anything new, that has to be
on the table, because two of the three plans contradict each other.

| | Plan | Mohit's sign-off | Built? | Reaching players? |
|---|---|---|---|---|
| 1 | `docs/play_with_coach_unified_experience_scope.md` | **2026-09-13** | Yes, 2026-09-13/14 | **No** |
| 2 | `docs/play_with_coach_v2_spec.md` | **2026-09-16** | Phase 1 of 5 only | **No** |
| 3 | This document ("coach beside you") | not yet | — | — |

Plan 2 was approved **two days after** plan 1 was built, and plan 2 says to delete
plan 1. From the V2 spec, section 10, decision 1:

> approve a new thin V2 runtime and eventual deletion of both legacy and Unified V1,
> while retaining verified services and data. **Recommendation: approve.**

And its implementation order, item 12:

> Delete legacy after two clean weeks at 100%. Remove CoachPlay.jsx legacy
> orchestration, CoachPlaySidebar legacy path, **Unified V1 selector/panel**,
> obsolete endpoints/states, and rollout flags.

So the already-built experience that matches this new vision is scheduled for
deletion by the plan approved after it. That is the single decision this document
needs from Mohit, and section 6 asks it directly.

### 0.2 The new vision is ~70% the approved Unified V1 scope

Plan 1's own mockup, written and approved in September, is the coach-beside-you
experience almost line for line:

- One coaching panel in one place for the whole game, no modals
- "Most moves produce no new message"
- "At most one coaching intervention is active at a time"
- An **"Ask coach"** affordance opening "no more than three contextual actions,
  such as 'What changed?', 'Explain their move', and 'Show the danger'"
- A warning that states the board fact and hands control back:
  `[ Try another move ] [ Play it anyway ]`
- A separate silent **Play a Game** mode
- A postgame that is one coaching summary, not a second engine review

That is sections 1, 7 and 8 of the new vision, already approved and already built.

### 0.3 What exists in code, feature by feature

Checked against the new vision's own priority list.

| # | Vision feature | What exists | State |
|---|---|---|---|
| 1 | Quiet on-demand coach chat | `UnifiedCoachPanel.jsx` → `onAskCoach("explain_last_move")`, `onAskCoach("focus_check")`, with a passing test on the callback. `POST /coach/play/chat` live. | **Built, dark** (gated on `unified_v1`) |
| 2 | Board Vision overlays | `PWC_BOARD_GEOMETRY=true`, `PWC_GEOMETRY_ARROWS=true` in production; `board_geometry_service.py`; arrows render | **Partly live.** Arrows yes; progressive layered reveal does not exist |
| 3 | Guided planning | `get_position_plan()` in `coach_play/personalized_coach.py`; `PositionCoachingPanel.jsx` **mounted and ungated** in `CoachPlayBoard.jsx:352` | **Live, and it is filler** — see 0.4 |
| 4 | Calculation sandbox ("Let me calculate") | nothing | **Genuinely new** |
| 5 | Coach's Notebook | `coach_memory` with decay states (active / declining / fading) and `improvement_note` | **Mostly built** |
| 6 | Coaching report | `postgame_analysis`; `coaching_decisions` event record | **Built, unusable** — see 0.5 |
| 7 | Opening Compass | `opening_curriculum.json`; only 41 of 79 openings teachable, 16 have no tree | **Content partial; memory broken** — see 0.6 |

Two further components, `components/coach-play/AskCoach.jsx` and `CoachChat.jsx`,
are imported by nothing at all. Their last substantive change was 2026-03-28,
six months before Unified V1. Read (per session -24) as orphans left behind when
`onAskCoach` was reimplemented inside the panel — not part of Unified V1.

### 0.4 The planning surface is live today, and it is filler

This is the most urgent thing in the audit, because a user can see it right now.

`PositionCoachingPanel` is mounted with no feature flag. It renders `main_idea`
from `get_position_plan()`. That function appends the following to **every** opening
position, regardless of what is on the board:

```
"Don't move the same piece twice unless necessary"
"Don't bring your queen out too early"
"Don't push too many pawns - develop pieces first"
```

`main_idea` is a constant per phase: *"Develop all your pieces and castle to safety."*
And the bishop advice reads *"Consider fianchetto (g3+Bg2)"* — a word the caption
voice rule bans by name for a 600–1500 audience.

This is the principle-bank-is-filler failure wearing a planning label. The new
vision calls Guided Planning the most distinctive thing worth building; in fact it
exists, it ships, and it needs fixing before it needs extending.

### 0.5 The coaching event record cannot answer any report question

Two writers push into the same `coaching_decisions` array:

- `coach_play.py:5586` — the real event: `move_key`, `source`, `layer`, `category`,
  `concept_key`, `text`, `move_quality`, `cp_loss`, `best_move`, `eval_before`,
  `eval_after`, `eval_valid`, `caption_verified`, `proposed_at`, `delivered_at`,
  `outcome`. Gated on `unified_v1`, so effectively nobody.
- `coach_play.py:6346` — a debug log, comment: *"Store decision in session for
  export/debugging"*. No `move_key`, no `outcome`. This is the live path.

Production (`chess_coach` database, read 2026-10-13):

```
coaching_decisions rows      1022
  outcome: (null)            1007   (98.5%)
  continued                    13
  silent                        1
  awaiting_choice               1
```

Outcomes are resolved by matching `coaching_decisions.move_key`. The live writer
never writes one, so those 1007 rows can never be resolved — the learning signal is
lost at write time, permanently. Every report section in the new vision consumes
this record.

Note: `CLAUDE.md` says the database is `test_database`. In production it is
`chess_coach` (498 coach sessions). `test_database` exists and is empty, so a query
against it returns a confident zero.

### 0.6 Three more measured constraints

**Session length.** The new vision's panel and report assume a game with an arc.
Across 385 production sessions holding any moves:

```
median      10 user moves
p75         32
p90         66
>= 20 moves 137  (36%)
```

Bimodal — a mass of very short sessions plus a real tail of full games. Anything
that needs a 20-move arc serves about a third of sessions.

**The on-demand chat is our least-verified surface.** `generate_response_to_user`
calls `call_llm`. Free-form LLM answering chess questions, with `position_plan` and
`personal_context` as context. Every other coaching surface routes through
`build_move_teaching_decision` and gets per-FEN claim verification. This one does
not. The new vision promotes it to priority 1.

**Opening memory works — corrected 2026-10-13.** I first wrote that this was
broken, because `coach_memory` fed `move_history_san` from `move_evaluations`
(user moves only), so book lines could never match. **That was fixed on
2026-09-19 in `3d4a4844`** and I had not checked. `coach_memory._history_by_position(pgn)`
now builds the full both-colour history from the PGN and falls back to the
user-only list only when the PGN is missing. Session -53 measured the fallback
rather than trusting the code, across 601 analyses: 600 of 600 PGNs parsed, and
per-move lookups hit 18,268 of 18,270 (100.0%). So the vision's "you have reached
this structure four times" coaching is *possible today*, and trap setup lines,
which alternate colours, can match too.

**Opening content is two populations, not one — corrected 2026-10-13.** I first
wrote "41 of 79 teachable, 16 with no tree". The honest split, verified against
`opening_curriculum.json`: **79 entries = 34 authored + 45 harvested**
(`from_games: true`). All 34 authored openings have a line or a tree — none is
half-finished — and 16 are richly stocked (italian_game has 13 steps and 10
traps). The 45 harvested entries were never authored as lessons and 38 of them
render an empty page. That is a ranked content backlog, not broken authoring.

**"Train With My Coach"** — raised last in the vision as a challenge to the design —
is the cheapest item on the list. ~30k positions already exist in
`community_training_positions`. It is also the only item that serves the median
10-move session, because a short session cannot carry a coaching arc but a
three-position drill can.

### 0.7 Why Unified V1 is dark

From `docs/qa/play_with_coach_unified_experience_qa_gate_2026_09_14.md`, which
Mohit wrote. The doc carries **two** verdicts:

```
Isolated staging feature verdict: PASS
Production deployment verdict:    HOLD
```

> **Why production is held:** no deployable remote staging environment is
> configured, remote post-deploy smoke testing has not run, and human UAT has not
> signed off.

Not one code defect. Six staging defects were found and all six fixed, with proof
recorded. Frontend suite 148 passed; 65 suites / 288 tests passed. One honest
caveat in the doc: a clean-base suite was never rerun — the feature-branch suite
was run instead.

**The consequence that decides this document:** all three hold reasons are process
gates, not engineering. And the V2 spec's own Phase 0 instruction is *"complete
existing Unified V1 UAT"*. So **completing Unified V1 UAT is the next action under
either plan.** There is no fork to resolve before doing it.

### 0.8 Decision

**EXTEND.** Specifically:

1. Finish and light what is already approved and built (Unified V1), because its
   blockers are process, its scope is this vision, and V2 requires it anyway.
2. Fix the two things that are live and wrong (planning filler, event record).
3. Then build the genuinely new capabilities: progressive Board Vision, the
   planning workspace, the calculation sandbox, Train With My Coach.

This is explicitly **not** a fourth parallel PWC. Writing one would make four
coaching experiences in one product.

---

## 1. What it is

Play with Coach becomes a coach who sits beside the player instead of standing in
front of them. The player plays a real game at their own pace. The coach watches
every move and quietly records what it sees, but speaks rarely — only when the
moment can teach something, and never by taking the move away. Whenever the player
wants help, they ask for it: to see what is happening on the board, to work out a
plan, to check whether the position has a tactic, or to understand the opening. The
coach answers from facts it can prove, and says a general principle when it cannot
prove anything specific. After the game it writes a short note about what it saw,
what the player did about it, and what to practise next — and it remembers that for
the next game.

The important shift is that the player controls the conversation while the coach
keeps control of the record. Watching is always on. Talking is on request.

## 2. What the user sees

### 2.1 During the game — the resting state

```
TODAY'S WORK
Keep every piece protected

COACH
I'm watching. Your turn.

                                        [ Ask coach ]
```

Most moves change nothing here. The standing line is how the player knows the
coach is present; it replaces a stream of messages.

### 2.2 Asking for help

`Ask coach` opens at most four choices. Which ones appear depends on the position —
an option is never shown if the coach has nothing provable behind it.

```
WHAT WOULD HELP?

  Help me see        What can my opponent do right now?
  Help me plan       I don't know what to aim for
  Check tactics      Is there something forcing here?
  Opening ideas      What is this position about?
```

### 2.3 Help me see — progressive, not a floodlight

One layer at a time. The player asks for more.

```
HELP ME SEE                                      step 1 of 3

Two of your pieces have nothing defending them.

I won't say which yet. Look for pieces that no other
piece of yours is protecting.

[ Show me which ]            [ I found them ]
```

Then:

```
HELP ME SEE                                      step 2 of 3

Your knight on e5 and your bishop on c4 are both undefended.

Only one of them is actually in danger. Which one can
your opponent attack right now?

[ Show me ]                  [ I know which ]
```

Then:

```
HELP ME SEE                                      step 3 of 3

The knight on e5. Their pawn on d6 can take it, and
nothing of yours can take back.

Undefended pieces are what tactics feed on. Before you
move, find your loose pieces.
```

The last line is the transferable part and is always present.

### 2.4 Help me plan — the planning workspace

```
HELP ME PLAN

Nothing is forced here, so this is a choice about direction.

Before we pick, two things are true about this position:
  · Your pieces are all developed; theirs are not
  · The d-file is open and no rook is on it yet

Where should your play be aimed?

  Get a rook onto the open file
  Attack on the side where I have more pieces
  Improve my worst-placed piece
  Deal with something they are threatening

                                  [ I'd rather you tell me ]
```

After a choice:

```
YOUR PLAN: get a rook onto the open file

That works here. Your rook on a1 is your least useful piece
and the d-file is the only open one.

Two moves do it: Rd1 and Rad1.

One thing to check first: after Rd1, is anything of yours
left undefended? Look before you play it.

[ Looks safe, I'll play it ]      [ Show me the problem ]
```

If the chosen plan is not supported by the position, the coach separates the idea
from the execution and never calls a reasonable idea wrong:

```
YOUR PLAN: attack on the kingside

The idea is reasonable, but not yet. You have one piece
near their king and they have three.

Attacks need more attackers than defenders. Count both
sides before you commit.

Want to look at a plan the position supports instead?
```

### 2.5 Check tactics — four levels, player-paced

```
CHECK TACTICS                                    level 1 of 4

Start with checks, captures and threats.
Look at every capture you have, even the bad-looking ones.

[ Nothing found — help more ]        [ I see something ]
```

Levels 2–4 narrow to the relevant relationship, then highlight the squares, then
show the line and why it works. The player chooses the move at every level.

### 2.6 Let me calculate

```
LET ME CALCULATE

Play the line you are thinking of. Nothing here counts
toward your game.

  1. Nxe5  dxe5  2. Qh5

[ Check this line ]                        [ Back to my game ]
```

```
YOUR LINE: Nxe5 dxe5 Qh5

The first two moves are right. Qh5 is where it goes wrong.

You expected their queen to have to defend. It doesn't —
their knight covers that square, so Qh5 just loses time.

The habit: after your last move in a line, check what
THEY can do, not what you want to do next.

[ Try a different line ]                   [ Back to my game ]
```

Nothing from the sandbox enters the game's move history.

### 2.7 Coach presence

```
COACH PRESENCE

  ( ) Quiet     Only speak when I ask
  (•) Gentle    Speak at a few important moments
  ( ) Active    Speak more often, but never pause my game

Either way I watch every move and remember what I see.
```

Default is **Gentle** below 1200, **Quiet** at 1200 and above. The last line is
not decoration: it is the contract that keeps the notebook fed in every mode.

### 2.8 After the game — the coach's note

```
WHAT WE LEARNED TODAY

TODAY'S WORK
Keep every piece protected

WHAT I SAW
On 6 of the 8 moves where it mattered, you checked what
became loose. Twice you didn't.

THE MOMENT
After 18.Bg5 your knight on e5 had nothing defending it.
You asked for help, found it yourself at step 2, and played
a move that fixed it.

Before moving a defender, check what it leaves loose.

WHAT I'M REMEMBERING
You needed one hint to find a loose piece today. Last game
you needed two. I'll test this again without hints.

NEXT
                [ Practise this in 3 positions ]
                [ Play another game ]
```

If the player never asked and never answered, the note says what they played and
what the board showed — never what they were thinking.

### 2.9 Train With My Coach

A second entry alongside the game, sharing the same memory and notebook.

```
TRAIN WITH MY COACH

Three positions. About five minutes.
Today: spotting loose pieces before you move.

                                           [ Start ]
```

## 3. In scope (V1)

**Part A — finish what is built**

- Complete Unified V1 human UAT and record the result against the existing QA gate
- Stand up the remote staging target the QA gate names as missing, or record an
  explicit decision to accept a different proving ground
- Rerun the suite against a clean base, closing the one caveat the QA doc records
- Light Unified V1 for a named cohort, verified **to the screen** with
  `scripts/what_a_real_user_sees.py` before and after

**Part B — fix what is live and wrong**

- One writer for `coaching_decisions`, carrying `move_key` and `outcome`, plus a
  `source` field on every row so a row's origin is never inferred later
- Ungate the `revised` outcome write, so a player who takes the coach's advice and
  plays something else is recorded. This is the one event the product currently
  throws away
- Replace `get_position_plan`'s unconditional advice and constant `main_idea` with
  position-conditional text; remove banned vocabulary ("fianchetto")
- Route `POST /coach/play/chat` through verified evidence: it may state a
  position-specific claim only when the claim is proven, and must fall back to a
  general principle otherwise

**Part C — new capability**

- `Help me see`: progressive layers, one step at a time, player-controlled
- `Help me plan`: the planning workspace in 2.4, including the
  reasonable-idea-wrong-moment response
- `Check tactics`: the four-level ladder
- `Let me calculate`: the sandbox, with no effect on game history
- Coach Presence setting, with recording always on in every mode
- `Train With My Coach`: three-position drills drawn from the existing
  `community_training_positions` pool, sharing the game's memory and notebook
- The coach's note in 2.8, built only from resolved events

## 4. Explicitly out of scope (V1)

- **PWC V2's runtime replacement.** If Mohit confirms V2, this document's Part A
  becomes V2's Phase 0 and Parts B and C are re-planned against the V2 runtime.
  Both cannot proceed at once.
- **Deleting legacy or Unified V1.** Deletion stays with whichever plan wins.
- **Voice, avatars, coaching personalities.** Explicitly out in the V2 spec too.
- **Unrestricted chat.** The chat answers from verified evidence; open-ended
  conversation is not in V1.
- **New detectors or new authored content.** Detector promotion is measurably
  exhausted — no remaining promotion changes any user's focus topic.
- **Opening Compass as a full panel.** *Not* cut for missing data — both reasons I
  first gave were out of date (see 0.6). It is cut on scope discipline: Parts A, B
  and C are already a large V1, and naming the opening on an ordinary move runs
  against the standing rule that the opening is named only where the lesson is
  opening-specific. V1 names an opening idea in the panel only where the position
  supports it. The capability is now unblocked, which makes a full Compass the
  strongest candidate for the release after this one.
- **Pricing, entitlements, premium tiers.** ChessGuru is not live; the current
  accounts predate these features, so their numbers are not signal for packaging.
- **Spaced repetition scheduling.** Train With My Coach V1 serves positions; the
  one-day/three-day/seven-day schedule is a follow-up.
- **Retention and transfer measurement.** Needs a resolved event record first.
  This is the main thing Part B unblocks for a later release.

## 5. Success criteria

Behaviour-changing only. Each is measured against the live legacy experience.

1. **The record resolves.** Within two weeks of Part B, at least 90% of
   `coaching_decisions` rows written carry a non-null `outcome`. Current baseline:
   1.5%.
2. **The revised move is captured.** At least 50 `outcome: "revised"` events exist
   across the cohort — the event the product keeps none of today. Baseline: 0.
3. **Help is asked for.** At least 40% of coached sessions contain one or more
   `Ask coach` interactions. If players never ask, the player-initiated premise is
   wrong and section 6 question 3 is answered by the data.
4. **Help resolves without the reveal.** Of `Help me see` and `Check tactics`
   interactions, at least 35% end before the final level — the player found it with
   partial help. This is the only measure of growing independence we can take in
   V1.
5. **No claim regression.** Zero unverified position-specific claims in the chat
   and the planning surface, measured by the per-FEN claim verifier on rendered
   output, not by keyword scan.
6. **Short sessions are served.** Median-length sessions (about 10 user moves)
   produce a coach's note that names a specific moment, in at least 80% of cases.
7. **Nothing breaks the board.** Zero reports of a legal move being rejected or
   trapped. This has happened before and is the one unrecoverable failure.

Deliberately not success criteria: time in app, messages shown, sessions started.

## 6. Open questions

**1. Is PWC V2 still the plan?**
Why unresolved: Mohit approved the V2 spec on 2026-09-16, two days after Unified
V1 was built, and it calls for deleting Unified V1. This document assumes Unified
V1 is finished and lit. Those are different futures and the work is not shared
beyond Part A.
Unblocking step: Mohit's decision. One sentence is enough. Note that Part A is
required under either answer, so it can start before this is settled.

**2. Which cohort, and how many people is it?**
Why unresolved: I have been using "49 users" and cannot source it. Measured on
2026-10-09: 128 accounts; 32 active in 7 days, 42 in 30, 67 in 90. 49 matches no
window.
Unblocking step: define the cohort by a query, not a number, and exclude the
super-admin account. Beware: `games` has no `created_at` (use `played_at_utc`), and
`coach_sessions.created_at` is an ISO string, so a datetime comparison silently
matches nothing.

**3. Will 600–1500 players actually ask for help?**
Why unresolved: the whole vision rests on the player initiating, but not knowing
when you need help is the condition we are treating. If they never tap, the
notebook and the report starve.
Unblocking step: success criterion 3 answers it with data. Mitigated in advance by
recording in every mode and defaulting sub-1200 to Gentle — but if criterion 3
fails, the premise needs revisiting, not the UI.

**4. How much Board Vision is too much?**
Why unresolved: the vision says progressive reveal and warns about visual noise,
but the number of layers and what each shows is unlocked.
Unblocking step: show the distribution of loose pieces, attacked pieces and
forcing moves per position across 500 games before fixing the layers. No threshold
before the histogram.

**5. What does "a reasonable plan" mean, concretely?**
Why unresolved: section 2.4 must accept plans the engine does not prefer, and must
reject plans the position refutes. The boundary between those is not defined and
cannot be a centipawn cut-off alone.
Unblocking step: measure which plan categories survive the opponent's best reply
across a real sample, then lock the rule from that.

**6. Is `onAskCoach` connected to anything that answers?**
Why unresolved: the callback is built and has a passing test, but a tested callback
proves the button fires, not that a response arrives.
Unblocking step: trace it end to end before costing Part C.

**7. Is the flag the only gate?**
Why unresolved: on a `/play-with-coach` load, two adjacent systems report
themselves off — `coach/personal-curriculum` returns
`{"enabled":false,"reason":"flag_disabled"}` and `progress/complete-coaching`
returns `{"enabled":false,"reason":"composition_disabled"}`. If the unified panel
leans on either, flipping one flag is not enough.
Unblocking step: trace both during Part A.

## 7. Pre-code requirements

Hard gates. Each must be true before the first line of code.

1. Mohit answers question 1 (V2 or this).
2. Mohit signs off on this document explicitly.
3. The cohort is defined as a query and the super-admin account is excluded.
4. `onAskCoach` is traced end to end and the result recorded here.
5. The two adjacent gates in question 7 are traced.
6. The Board Vision distribution from question 4 exists, before any layer count is
   chosen.
7. Coordination with session -f8, who is actively changing
   `build_move_teaching_decision` (v203→v210). PWC and game review share that
   function, so any change to what PWC asks it for lands on review captions too.
8. A baseline snapshot of rendered coaching output over a fixed game sample, so
   Part B's changes can be diffed per row rather than judged by a headline number.
9. `scripts/what_a_real_user_sees.py` run and recorded as the before-state.

---

## Appendix — what the audit changed about my own earlier claims

- I said the teaching work for this vision needed building. Most of it is built.
- I said Unified V1 might be "unfinished or parked". It is neither: it passed
  staging QA and was superseded two days later by an approved replacement.
- I used "49 users" for the pilot. I cannot source that number; see question 2.
- I described `position_plans` as having zero readers. That is true of that name,
  but `get_position_plan` exists, runs, and reaches a screen. The planning gap is
  quality, not absence.
- I said opening memory was broken at the input. It was fixed on 2026-09-19 and I
  had not checked. Corrected in 0.6 with -53's measurement.
- I said "41 of 79 openings teachable, 16 with no tree". The real shape is 34
  authored (all teachable) plus 45 harvested observations. Corrected in 0.6.
- Both of those were the stated grounds for cutting Opening Compass from V1. The
  grounds were wrong; the cut now rests on scope discipline instead, and the
  feature is explicitly named as the next release's best candidate.
