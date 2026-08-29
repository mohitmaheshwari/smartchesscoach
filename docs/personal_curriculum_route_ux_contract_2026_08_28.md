# Personal Curriculum — Route and UX Contract

**Status:** SIGNED OFF v1 — 2026-08-28. Mohit: “go ahead.” Amended
2026-08-29 after live validation showed that `/lab` still renders the legacy
learning path; player Game Review therefore uses the existing `/games`
index.

## Route ownership

| Route | Product job |
|---|---|
| `/home` | Relationship and today’s one primary coaching action |
| `/learn` | Canonical Personal Curriculum: current lesson, due review, naturally next, Explore |
| `/games` | Player-facing Game Review index; lists the player's games and opens `/game/:gameId` |
| `/lab` | Legacy mixed learning path and evidence laboratory; preserved during migration, but not labeled Game Review |
| `/progress` | Improvement ledger; reports repair and knowledge evidence without choosing the next lesson |
| `/training/*` | Drill/detail destinations selected by the coach or student |
| `/openings/*` | Opening Explore and opening lesson details |
| `/endgames/*` | Endgame lesson details |
| `/play-with-coach` | Coached application environment |

`/learn` is deliberately new during the flag-protected migration. The existing `/lab` continues unchanged for legacy users until its learning sections have parity on `/learn`. This avoids destroying the current mixed page before the replacement is proven.

## Navigation contract

Flag off:

```text
Home
Learn        → existing /lab
Progress
Play with Coach
```

Flag on:

```text
Home
Learn        → /learn
Game Review  → /games
Progress
Play with Coach
```

Training and Openings stop competing as top-level “what next?” destinations. They remain fully available inside Explore and through direct links.

## Home contract

Home receives the same canonical curriculum decision as `/learn`. It does not build, rerank, or rewrite a second recommendation.

```text
TODAY WITH YOUR COACH

You kept your pieces safe in both recent games.
Today I want to add one new idea.

Rule of the square
Know whether your king can catch a pawn without counting every move.

                         [ Learn with your coach · 6 min ]

One quick review
Castle before attacking                         [ 1 position ]
```

Rules:

- one primary action;
- at most one review;
- a personal reason when evidence exists;
- honest universal wording during cold start;
- no percentages, tiers, locks, engine names, or internal skill IDs.

## Learn contract

```text
YOUR COACHING PLAN

Learning now
  Rule of the square
  You understood the example. Next, solve one without help.
                                                [ Continue ]

Keeping fresh
  Castle before attacking      Review after your next 2 games

Naturally next
  Put the kings face-to-face
  I’ll teach this after the pawn-race lesson.

Explore
  Openings · Tactics & traps · Endgames · Plans · Thinking habits
```

The player never sees a skill-tree wall. “Naturally next” explains sequence but remains browseable.

## Explore autonomy

Opening an Explore lesson does **not** silently replace the coach’s primary plan.

The lesson header says:

```text
You chose to explore this.
Your coach’s current recommendation is still Rule of the square.
```

If the student finishes an Explore lesson, its evidence is recorded normally. The composer may select it later, but completion does not overwrite the active plan in the same session.

An explicit future action—“Make this my focus”—is out of scope for the first read-only slice.

## Plan continuity

Persist only a compact active-plan reference under the existing learning memory owner:

```text
active curriculum reference
  decision id
  outcome: OBSERVE / REPAIR / EXPAND / CONTINUE / REVIEW / APPLY
  canonical skill/content id
  selected at
  evidence watermark
  resume destination
```

Do not copy lesson text, chess moves, mastery state, recurrence counts, or detector verdicts into the plan reference. Those remain derived from their canonical owners.

The reference exists so one coach does not change subjects between Home and Learn or after a refresh. It is invalidated only when the evidence watermark changes materially, the student completes/declines it, or its canonical destination disappears.

## Lesson return contract

Every lesson exits to one of three coach-owned outcomes:

```text
Continue
  “You used a hint. I’ll give you a different position next.”

Review later
  “You solved it alone. I’ll bring it back after more games.”

Apply
  “You can solve the lesson position. Now I’ll watch for it in play.”
```

The default completion CTA is **Back to your plan**, not More Lessons.

## Mobile contract

- The primary action and reason appear before any history or Explore content.
- Board lessons use one board plus one coaching panel, never a two-column dependency.
- “Continue” remains reachable without scrolling past the full lesson library.
- Explore categories use a simple vertical list.
- Progress labels remain text-first; color is supplementary.

## Migration contract

1. Add `/learn` behind `PERSONAL_CURRICULUM_ENABLED=false`.
2. Flag-on Home and `/learn` consume the same read-only decision.
3. Preserve `/lab`, `/training/*`, `/openings/*`, and `/endgames/*` unchanged.
4. Run desktop/mobile parity and deep-link checks.
5. Move the sidebar Learn destination only for eligible A/B users.
6. After two clean weeks at 100%, remove curriculum selection from `/lab`
   and decide its redirect from observed deep-link use. `/games` remains the
   player-facing Game Review index.
7. Redirect only superseded index routes; retain detail URLs.

## Decisions signed off by Mohit

- `/learn` is canonical and `/games` is the player-facing Game Review
  index. `/lab` remains a preserved legacy route during migration.
- Explore is non-replacing by default.
- A compact active-plan reference may live in `coach_memory.learning` with no copied truth.
- Rule of the Square is the first lesson-contract slice, with real-game claims suppressed until Plan-grade authorization.
