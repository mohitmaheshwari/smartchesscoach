# Progress Evidence Page — Scope

## 0. Existing surfaces audit

The routed `/progress` page is `UnifiedProgress`. It currently fetches `/progress/real`, `/progress/narrative`, `/progress/improvement-proof`, and the move-calibration endpoint. Its visible experience is led by the current weakness, “Our one focus right now,” “I’m watching these too,” practice buttons, and archived weaknesses. That repeats the job of the routed Learn experience, whose `PersonalCurriculum` and curriculum components already own the current lesson, its explanation, the next lesson, and exploration.

The backend already has a stronger and more honest progress source: `/progress/complete-coaching`. It separates recorded practice from a later unassisted game opportunity and refuses to call practice completion improvement. It also preserves the current focus identity and a server-owned transfer verdict. `move_observations` owns the exact board evidence behind that verdict, and the existing curriculum response owns the player-safe lesson title and destination.

The overlap is the current focus, lesson state, practice action, and weakness inventory. The genuine Progress value is the part Learn cannot answer: what changed after teaching, what evidence came from a later real game, what remains unproven, and what the coach needs to observe next.

**Decision: REPLACE existing.** Keep the canonical `/progress` route and replace its Learn-like content model. Reuse the existing curriculum, Phase 8 journey, and exact move-observation evidence. Do not add a second Progress page, progress store, learner reducer, or concept-name registry.

## 1. What it is

Progress is the coach’s evidence conversation. It tells the player whether a lesson has changed a decision in later unassisted games, shows the real positions that support that conclusion when exact evidence exists, separates practice from transfer, remembers meaningful steps in the journey, and explains what the coach must see next. It never uses lesson completion, puzzle success, a clean-looking move, or a rating change as proof by itself.

## 2. What the user sees

```text
PROGRESS · WHAT IS CHANGING IN YOUR CHESS

Your pieces are becoming safer.
You practised the idea, and I have now seen you handle the same
decision in a later game without help.

┌──────────────────────────────────────────────────────────────┐
│ THE EVIDENCE                                                 │
│                                                              │
│ Earlier                         Recently                      │
│ [your real position]            [your real position]         │
│ You left this piece available.  This time, you kept it safe. │
│ Review the game →               Review the game →             │
└──────────────────────────────────────────────────────────────┘

HOW THIS BECOMES YOURS
● Coach noticed it  ● Practice recorded  ● Seen in a later game  ● Holding
                     Practice is not proof by itself.

WHAT I AM STILL WATCHING
I want to see this decision hold again when the position is busy.

NEXT
Play naturally, then import your latest games. I’ll check the next
comparable decision without helping you first.
```

When the evidence is incomplete, the headline changes rather than pretending:

```text
You understand this in practice. I cannot call it improvement yet.
I need to see the same decision in a later unassisted game.
```

When the pattern returns:

```text
This is still showing up in your games.
The same decision appeared again, so it stays in your plan.
```

When exact position references cannot be resolved, the evidence card is omitted and the page explicitly says that no game-level proof is ready. It never substitutes a merely low-loss move from a vaguely similar phase.

## 3. In scope (V1)

- Replace the current Learn-like `/progress` hierarchy with one coach verdict, one evidence area, one practice-versus-transfer path, one “still watching” explanation, and one next action.
- Consume the existing canonical curriculum response for the player-safe focus title and lesson destination.
- Consume `/progress/complete-coaching` as the authority for practice, later-game opportunity, and improvement status.
- Extend that existing projection with a small public evidence view derived only from the enrolled player’s frozen baseline and complete Plan-authorized organic-game application events.
- Show at most one earlier miss and one recent handled-or-missed position, with FEN, move, move number, opponent label when available, and a link to the player’s own review.
- Render exact evidence boards as non-draggable previews; the game-review link owns deeper interaction.
- Show honest states for improvement proven, still recurring, waiting for a later game, lesson not yet completed, paused access, and insufficient history.
- Preserve the existing routed page, layout, responsive design system, dark mode, and reduced-motion behavior.
- Add frontend state tests and backend projection tests, including ownership and fail-closed evidence cases.

## 4. Explicitly out of scope (V1)

- A new lesson, weakness picker, concept catalogue, mastery engine, or Progress database.
- Showing the full Learn plan, tracked weakness inventory, or practice catalogue on Progress.
- Claiming transfer from puzzles, lesson completion, coached play, rating movement, generic accuracy, or clean games alone.
- Using the legacy same-phase before/after matcher as proof; it can pair unrelated positions and therefore remains excluded from the new page.
- Adding new detector rules, lowering authorization grades, running Stockfish, or using an LLM to create progress claims.
- Comparing players, forecasting Elo gain, streak gamification, or leaderboards.
- Automatically enrolling users, changing production flags, pushing, or deploying.

## 5. Success criteria

- A player can immediately distinguish “I practised this” from “I used this later without help.”
- Every improvement or recurrence sentence is a direct rendering of the canonical server verdict, not a frontend inference.
- Every displayed board resolves to the signed-in player, an exact stored observation, and the Plan-authorized detector family; unresolved or incomplete evidence produces no board and no substitute claim.
- The primary next action matches the missing evidence: continue the lesson, import later games, review the returning mistake, or return to Learn after improvement.
- The existing Phase 8 behavior-change gate remains the product outcome: later unassisted comparable decisions change the verdict; Progress views and practice clicks do not.
- Tests cover every player-facing state and prove that Learn inventory language and unsupported percentages are absent from the new page.

## 6. Open questions

- **Question:** When should a proven skill become “holding” rather than one successful application? **Why unresolved:** the delayed-retention threshold remains owned by the existing mastery contract and must not be invented in this page. **Unblocking step:** render the current server state now and adopt a future threshold only after its evidence lock is approved.
- **Question:** Should a later external game or a Focus Game be the preferred next action? **Why unresolved:** the current transfer contract accepts only verified organic-game application evidence. **Unblocking step:** V1 sends the player to import recent games; expand only if coached-game transfer becomes separately authorized.
- **Question:** What numeric click-through target should the redesign meet? **Why unresolved:** no clean baseline exists for this evidence-specific page. **Unblocking step:** preserve the existing Progress view measurement, add no curve-graded threshold, and lock a target after the first bounded pilot window.

## 7. Pre-code requirements

- The implementation must start from current `origin/working-code` in an isolated worktree.
- Mohit must explicitly approve the replacement mockup and implementation direction.
- `/progress` must remain routed to `UnifiedProgress`; Learn must remain the owner of curriculum browsing.
- `/progress/complete-coaching`, `get_pic_mastery_projection`, `move_observations`, and detector authorization must remain the single owners of their respective truths.
- No new numeric chess, mastery, or ranking threshold may be introduced.
- Exact evidence projection must fail closed on wrong user, missing observation, incomplete application evidence, or a non-Plan detector.
- Focused backend and frontend tests must pass before the work is handed to Claude for push and deployment.
