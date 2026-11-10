# Game review: the coach takes up the child's reflection — scope

Status: **awaiting Mohit's sign-off. No code yet.**
Asked for: Mohit, 2026-11-10 ("go with your recommendation"), after we found
that game review asks a reflection question but the answer changes nothing.

---

## 0. Existing surfaces audit

**What already touches this need (checked on `working-code` 5374d0f6, 2026-11-10):**

1. **Game review's "Before I explain" step.**
   - Where: `frontend/src/components/review/PersonalizedReviewCoach.jsx`, with the
     question from `backend/services/review_reflection_service.py`.
   - When it runs: on chapters marked reflection-eligible, before the explanation.
   - It asks "What were you thinking before this move?" with option buttons from
     `quick_tag_registry`, always including "not sure" and "none of these".
   - After the answer, it shows "What you told me: <label>", then the same caption
     and principle every child gets (lines 340-363).
   - Answers are saved in `reflection_sessions` (kind `game_review_event`).
   - On prod: 10 answers ever, from 1 user, the last on 2026-11-06 (counted in the
     database on 2026-11-10).
2. **The coach plan's tap reflection.**
   - Built and deployed 2026-11-09 in b2fbc660:
     `frontend/src/components/coachplan/ReflectFlow.jsx` and
     `backend/services/coach_plan_service.py`.
   - It runs on `/class/:token/reflect`, for academy children only, on up to 3
     moments a week that the plan picks.
   - Every answer is a board tap. The steps are: what the move was for (options come
     from the board), the check (tap the piece that can take it / the pieces aiming
     at the king / find the winning move), whether they saw it in the game, what
     happened next, and a try-again step.
   - The coach's lines change with each answer. The answers give a cause: not
     looking, doesn't know the pattern yet, or saw it but misjudged.
   - On prod: 0 answers. The only plan is a draft waiting for approval.
3. **The coach chat prototype** (https://claude.ai/artifact/NFHCgwFnt1tQXEDM4ye5ym).
   It's a demo page, not product code. It showed the same flow on three moments
   from Mohit's games.
4. **The `/reflect` page (Reflect V1).** It shares the `reflection_sessions` store.
   It isn't the game review page.

**Overlap:**
- Game review and the coach plan both ask the child about a moment before
  explaining it, and both store the answer in the same place.
- Today's game review ends up with two answer styles for one moment's question if
  we add the tap flow next to the buttons.

**What's genuinely different:**
- The tap flow tests what the child can see on the board. The button question asks
  them to guess their own thinking.
- The tap flow's reply depends on the answer. The button step only repeats the
  answer back.

**Decision: EXTEND.** On the moments the tap flow can grade, it replaces the button
question inside the existing game review chapter. Every other moment keeps today's
buttons. There's no new page and no new store.

---

## 1. What it is

When a child opens a moment in game review, the coach first asks them to look at
the board: what was the move for, and which of the opponent's pieces could take
it. The coach answers what they tapped, in plain words. Then it asks one honest
question: did you see this in the game? From those answers the coach knows *why*
the mistake happened. Did the child miss it because they didn't look (they find it
straight away when asked)? Or do they not know the pattern yet (they can't find it
even when asked)? Or did they see it and think it was fine? The coach's explanation
is then written for that reason. It isn't the same paragraph for everyone. The
child's answers are kept, so the coach plan and later reviews can use them.

---

## 2. What the user sees

Real moment: Mohit's game of 2026-11-05 (test account), move 8 as White, **Qf3**.
Black replied Nxf3+ with the knight from e5. The stored best move was Nf3. The facts
come from python-chess on the stored position. Not checked yet: whether game review
makes this move a chapter today (a pre-code item). Lines marked *[only if …]* appear
for that answer only.

```
┌──────────────────────────────────────────────────────────────────┐
│ A MOMENT WORTH UNDERSTANDING                              2 of 3 │
│ Move 8 · Qf3                                                     │
│                                                                  │
│  [board: position after Qf3; red ring on his knight f6]          │
│                                                                  │
│  Coach  You played Qf3.                                          │
│  Coach  What was Qf3 for? Tap everything it was about,           │
│         then press Done.                                         │
│         Red rings: his pieces it now attacks.                    │
│         [ Bring it into play ]  [ Something else ]  [ Done ]     │
│                                                                  │
│  You    To attack the knight on f6.                              │
│  Coach  Yes. From f3 your queen attacks his knight on f6.        │
│         Whatever the plan, there is one check that comes first.  │
│                                                                  │
│  Coach  Now the check. With your queen on f3, which of his       │
│         pieces could take it?                                    │
│         Tap every piece you think can reach it, then Done.       │
│                                                                  │
│  ── answer A: taps e5 ────────────────────────────────────────── │
│  Coach  Yes, his knight on e5. You saw it.                       │
│  ── answer B: taps nothing, or the wrong piece ───────────────── │
│  Coach  The piece that can take it is his knight on e5.          │
│         Knights jump. From e5 it reaches f3 in one hop, and      │
│         nothing can block a jump. Squares a knight can reach     │
│         often don't look close.                                  │
│  ──────────────────────────────────────────────────────────────  │
│                                                                  │
│  Coach  One honest question. In the game, before you played      │
│         Qf3, did you see his knight on e5?                       │
│         [ No, I didn't see it ] [ I saw it, but thought it was   │
│           fine ] [ Not sure ]                                    │
│                                                                  │
│  ── the coach's answer depends on the two answers ────────────── │
│  [only if found it + didn't see it]   NOT LOOKING                │
│  Coach  You found it just now in a few seconds. So this isn't    │
│         something new to learn. In the game you didn't look.     │
│         The job is doing the look every time a piece lands.      │
│  [only if didn't find it]             PATTERN NOT KNOWN YET      │
│  Coach  That's the most common reason, and it can be trained.    │
│         It was a knight jump, and that's what we'll practise.    │
│  [only if saw it, thought fine]       MISJUDGED                  │
│  Coach  Then the question is: if he takes, is that okay for me?  │
│         Let's see what happened.                                 │
│  ──────────────────────────────────────────────────────────────  │
│                                                                  │
│  Coach  What happened next: Nxf3+. You can take back, but that   │
│         is your queen for his knight.                            │
│                                                                  │
│  WHAT ACTUALLY HAPPENED                                          │
│  <today's verified caption for this moment, unchanged>           │
│                                                                  │
│  KEEP THIS WITH YOU                                              │
│  [not looking]  Before any piece lands, look from that square:   │
│                 pieces close by, knight jumps, and long lines.   │
│  [not known]    Before any piece lands, check every square a     │
│                 knight could jump to it from.                    │
│  [misjudged]    When it can be taken, count what you lose and    │
│                 what you get back before you play it.            │
│                                                                  │
│  [ Show the relationship ]  [ Previous ]        [ Next moment ]  │
└──────────────────────────────────────────────────────────────────┘
```

The coach's lines above come from today's `ReflectFlow.jsx` wording (lines 168-315),
so the voice matches the coach plan. The three "Keep this with you" lines are new
and are one of the open questions (6.3).

---

## 3. In scope (V1)

- On a game review chapter whose moment the tap flow can grade, the tap flow
  replaces the button question. The flow is: what it was for → the check → did you
  see it → the cause-specific reply → today's caption.
- Moments the tap flow can grade in V1. Each maps an existing review cause onto an
  existing tap test:
  - A piece left where it can be taken (`LegalMaterialLossCause`) → "which of his
    pieces could take it" (the coach plan's `landing` test).
  - A missed mate (`missed_forced_mate`) or missed material
    (`missed_material_opportunity`) → "find the winning move" (`find_move`).
- Every other review moment keeps today's button question, unchanged.
- The coach's reply after "did you see it" changes with the cause: not looking,
  pattern not known yet, or misjudged.
- The "Keep this with you" line changes with the cause.
- Every tap is graded on the server against the board (the same rule as the coach
  plan: never show a question the board can't grade). If the board and the review
  cause disagree (for example, nothing can take the piece), the moment falls back
  to the button question.
- Answers are saved in `reflection_sessions` as kind `game_review_event`, with the
  cause added. The coach plan's cause count reads them too, so a child who reflects
  in game review doesn't answer the same moment twice.
- One answer per moment. Re-opening the moment shows the earlier answers and the
  reply, not the questions again (today's behaviour).
- No typing anywhere.
- The flow works for the account owner reviewing their own game and for an academy
  child opening their own game review.

## 4. Explicitly out of scope (V1)

- **The "try another square" practice step** from the coach plan. It grades every
  legal move with the engine (about 85 s per child for 3 moments on the shared box).
  That's too slow for a page the child opens, and analysis is already the
  bottleneck (about 8 games an hour on 2026-11-09). Revisit after V1.
- **Allowed-mate moments** (`allowed_forced_mate`). The right tap test ("which of
  his moves gives mate") isn't built. Keep the buttons.
- **Trade-counting moments** (`exchange_sequence`). They need a counting question,
  not a "who can take it" question. Keep the buttons.
- **Endgame moments.** Keep the buttons.
- **Ignored king attack.** The coach plan has this test, but game review has no
  matching cause today.
- **Typed answers or chat with Claude.** Decided earlier: board taps only.
- **A child-specific warning sign.** It needs the baseline bar that isn't locked
  (see `docs/coach_assistant_plan_scope.md`).
- **Changing the verified caption itself.** "What actually happened" stays exactly
  as today. Only the lines before it and the "Keep this with you" line change.
- **Opponent moves.** Only the child's own moves are reflected on.
- **A coach-facing view of game review answers.** The coach plan already shows the
  cause. V1 only feeds it.

## 5. Success criteria

Both are measured per child and never blended into one number. The thresholds are
proposals to lock with `/lock-via-data` after two weeks of data.

1. **The flow is finished.** Of tap flows started, at least 60% reach the
   cause-specific reply. If fewer do, the flow is too long for game review and
   gets cut before anything else is built on it.
2. **The habit changes.** For each child with at least 3 answered moments of one
   kind, compare the rate of that detector per game in the 14 days after their
   first answer with the 28 days before. Success means it drops for most such
   children and they spend longer on those moves (the coach plan's week check,
   reused). With today's user count this is a direction, reported child by child,
   not a percentage.

Not success: number of reflections stored, number of chapters opened.

## 6. Open questions

1. **How many review moments would get the tap flow?**
   - Why unresolved: the mix of cause kinds on reflection-eligible chapters hasn't
     been counted.
   - Unblocking step: count, over the last 30 days of analysed games, how many
     reflection-eligible chapters have each cause kind. If V1 kinds are a small
     share, V1 changes little and allowed-mate or trade-counting may need to come
     in.
2. **How is "find the winning move" graded without grading every move?**
   - Why unresolved: the coach plan accepts any move within 50 cp of best, which
     needs every move graded.
   - Options: (a) accept the stored best move, and check any other tapped move with
     one short engine look on the request (about a second); (b) precompute at
     analysis time for the review chapters only; (c) accept only the stored best
     move.
   - My recommendation, not a decision: (a).
   - Unblocking step: Mohit picks.
3. **The three "Keep this with you" lines.**
   - Why unresolved: the wording in section 2 is a draft.
   - Unblocking step: Mohit approves or rewrites them. They go through
     `/rewrite-for-1200` and the caption lint first.
4. **Should the "what was it for" step stay in game review?**
   - Why unresolved: it adds one tap step. In game review the child may want the
     answer faster than on the weekly plan.
   - Unblocking step: Mohit decides. Success criterion 1 shows whether it costs
     finishes.

## 7. Pre-code requirements

- Mohit signs off this document explicitly.
- Open question 1 is counted on prod (read-only), and V1 kinds still make sense.
- Open question 2 is decided.
- Confirm that game review makes the section-2 moment (Qf3, game 86164614) a
  chapter with a material-loss cause. If not, swap in one that is.
- The section-2 mock is checked on a second real moment of each V1 kind (one
  missed-mate or missed-material moment), with facts from python-chess and the
  stored engine data, not written by hand.
- The PR check: no open PR or branch touches `PersonalizedReviewCoach.jsx`,
  `review_reflection_service.py`, `ReflectFlow.jsx` or `coach_plan_service.py`.
  Checked 2026-11-10: the only open PR is #1 ("Latest code", branch
  `latest_code`). Re-check its files before the first edit.
- `/audit-pre-code` passes.
