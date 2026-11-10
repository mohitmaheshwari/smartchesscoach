# Game review: the coach takes up the child's reflection — scope

Status: **signed by Mohit 2026-11-10 and built.**
Asked for: Mohit, 2026-11-10 ("go with your recommendation"), after we found
that game review asks a reflection question but the answer changes nothing.

## Sign-off and decisions (2026-11-10)

Mohit: "do what you recommend and we will take from there, just one thing, user
shouldn't write free text, interface should be very very easy for him to submit
his answers".

- Open question 2: option (a). The stored best move is accepted. Any other
  tapped move gets one short engine look (depth 12) on the server.
- Open question 3: the draft lines ship as written in `KEEP` in
  `services/review_tap_reflection.py`.
- Open question 4: the "what was it for" step stays. It's the step where the
  coach answers the child's own thinking.
- "Very easy": every step is a board tap or one button. Find-the-move has a
  one-tap "Show me". A failed save offers one "Try again" button. No typing
  anywhere.

**Open question 1, measured on prod 2026-11-10 (read-only).**
- Who sees the personalized review: rollout `validation`, 49 users have the flag.
- Last 30 days: 614 reflection-eligible moments.
  - Exchange sequence: 223
  - Missed material: 137
  - Simple hang with no typed cause: 123. These get **no question today**, because
    the button builder needs a typed cause.
  - Material loss: 72
  - Allowed mate: 48
  - Missed mate: 11
- A dry run of the builder over all 614 gives the tap flow to **363 (59%)**,
  across 221 games:

  | Kind | Tap flow |
  |---|---|
  | Missed material | 136 of 137 |
  | Simple hang | 114 of 123 |
  | Material loss | 72 of 72 |
  | Exchange sequence | 30 of 223 |
  | Missed mate | 11 of 11 |

**Changes from the signed text, found while building:**
- The piece that can be taken is often not the piece that moved: 145 of the
  first dry run's moments. Example: Ne2 left the queen on f3 to the knight on
  e5. So the question names the piece that can be taken ("After Ne2, which of
  his pieces could take your queen on f3?"). Takers are legal captures only, so
  a pinned piece is never offered.
- Exchange-sequence moments are now in V1. They use the same "which piece could
  take it" test, but only when his actual reply took the piece. Without that
  rule, the first dry run asked about pieces he never took.
- "What happened next" states a cost only when taking back still leaves the
  child behind. An even trade no longer reads as a loss.
- Answers are stored as reflection kind `game_review_tap`, not
  `game_review_event`, so the option-answer readers (learning adapter,
  accepted causes) never see a shape they don't expect.
- **Deferred:** the coach plan counting game review answers. Academy children
  reach their reflection through the class link, not game review, so there is
  nothing to share yet.
- The section-2 Qf3 move isn't a review chapter on prod. Your main-account copy
  of that game has Ne2 (move 9) as the chapter, which is the case above. The
  tests use both positions.

## Amendment 2: walk through it the way a coach would (signed 2026-11-10, "do it")

**Why.** Mohit, on his Qf3: "it never tells about queen hanging". Then: "first
think how a human coach would take us through that position ... how player
thinks really".

**What happened in that game.** Checked with python-chess and depth-18
Stockfish on prod.
- Black's knight on f6 attacked e4. The only guard was the knight on c3, pinned
  by the bishop on b4.
- Qf3 guarded e4 and hit f6. But the knight on e5 hits f3.
- Black castled. White played Ne2, then exd5, with the queen still on f3. Only
  then did Black play Nxf3+.
- The review was silent on Qf3, because a wrong claim in the free caption hid
  the proven cause. It taught Ne2 and exd5 as separate chapters instead.

**What changes.**
1. **Gate.** In quality V2 a proven typed cause is shown even when the free
   caption failed its check (`game_review_event_adapter`). Without a cause,
   nothing changes.
2. **One story.** A later moment that only leaves the same piece on the same
   square en prise is evidence for the first moment, not a chapter of its own.
   This holds when the first moment can be shown, and within six plies of the
   previous one (`piece_story_continuations`, planner `continuation_of`). The
   formula id becomes `E_transition_then_teaching.origin_story_v1`, so stored
   plans regenerate when a flagged user next opens the game.
3. **The flow for a piece-left-en-prise moment.**
   - When the player had a problem of their own before the move, the flow
     starts there: "Before Qf3, what were you worried about?". They tap e4.
     The coach answers: "Right. His knight on f6 was attacking it, and your
     knight on c3 couldn't help: his bishop on b4 pins it to your king."
   - Credit: "Qf3 guards it, and it also attacks his knight on f6. Good idea."
   - The landing check: which of his pieces could take the queen.
   - The story, from the stored game: "He didn't take it. He played O-O. Then
     you played Ne2, he played d5, and you played exd5. Your queen was still on
     f3. Then he took it with Nxf3+ ..."
   - The cause, read from the game: if the piece stayed there on a later move,
     "did you see it?" isn't asked. The answer is "no", and the server enforces
     that.
   - "How else could you look after your pawn on e4?" The player taps a move,
     graded by one engine look (depth 12, multipv 4). A good answer gets words
     built from the board, such as "Bd2 breaks the pin, so your knight on c3
     guards e4 again." "Show me" reveals one.
   - Keep line: "When you answer a threat, check the new square too: knight
     jumps first."
4. **Wording rules found in the prod dry run.**
   - The move that rescues the piece is never told as "still there".
   - More than two of the player's moves are summarised in one phrase.
   - "Guarding wasn't enough" says why: a cheaper attacker, or more attackers
     than guards.

**Dry run on prod, last 30 days (read-only).**
- 218 piece-left-en-prise tap moments.
- 43 start from the player's own problem.
- 67 tell a story.
- In 34 the game answers "did you see it?".

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
The knight on e5 could take the queen with Nxf3+. **Correction, 2026-11-10:** an
earlier version said Black replied Nxf3+. Black actually castled, and took the
queen only two moves later (see amendment 2). The stored best move was Nf3. The facts
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
