# Curriculum Truth and Delivery Scope

Status: **approved for implementation** on 2026-08-29. The existing-surface
audit was reviewed with Mohit, and the explicit response “go for it please”
approved the work. Mohit then explicitly corrected the release direction:
incomplete content must be completed and strengthened, not left hidden as the
product outcome. Quarantine remains a temporary safety gate only.

## 0. Existing surfaces audit

ChessGuru already has the right product surfaces, so this work extends them
instead of adding another curriculum page:

- `/home` is the coach's short, personal direction.
- `/learn` is the player's one-plan-at-a-time curriculum.
- `/openings` and `/endgames/*` contain subject-specific lessons.
- `/play-with-coach` is where guided practice and game application happen.
- `/games` and `/game/:gameId` are the evidence and review surfaces.

The problem is behind those surfaces. Three subjects have duplicate active
inventories, and the copies disagree:

- Openings: `backend/data/opening_curriculum.json` has 79 records, but only
  25 have teaching trees, only 28 have main lines, and 42 have neither. Four
  authored moves are currently illegal or structurally misplaced.
- Traps: `backend/data/traps.json` has 54 records, while Play with Coach uses
  a separate 18-trap hardcoded library. Three canonical lines are illegal,
  the practice adapter discards most winning lines, and several outcome
  claims are not demonstrated by their authored line.
- Endgames: the routed theory tree has 18 lessons and 54 positions, but five
  positions are invalid and nine tablebase-eligible answers throw away a win
  or draw. A second six-lesson legacy file has three invalid starting
  positions and four illegal continuations.

The current delivery also exposes lesson names before it can always deliver a
safe lesson, leaks empty opening explanations, reveals the first endgame
answer before the player tries, and does not require an unseen proof position.
That makes the catalog look larger than the reliable teaching product.

Decision:

- **EXTEND** the existing player surfaces.
- **REPLACE** duplicate runtime inventories with adapters over one canonical
  source per subject.
- Canonical owners are:
  - openings: `backend/data/opening_curriculum.json`
  - traps: `backend/data/traps.json`
  - endgames: `backend/data/coaching/endgame_theory_tree.json`
- Unsafe or incomplete records are not rendered as locked promises while they
  are being repaired. They stay in the canonical source, are completed in the
  same release sequence, and return to the player catalog as soon as they pass
  the content gate.

## 1. Player outcome

A 600–1500 player should feel that one coach has chosen the next useful thing,
explained it in ordinary language, watched them try it, and remembered whether
they could do it alone.

After this work:

- Every visible lesson opens and can be completed.
- Every position and move shown as correct is chess-legal and verified.
- The player learns why a move works, not only which move the engine prefers.
- The player receives help first, then proves the idea on a different position
  without the answer being exposed.
- The result returns to the same personal coaching plan and becomes evidence
  for review, refresh, or progression.

## 2. User stories

1. As a newer player, I can learn the opening habits that matter before I am
   asked to memorize named variations.
2. As a player with a recurring opening mistake, I see a compact repertoire
   lesson chosen for my games, with explanations attached to the moves.
3. As a player vulnerable to an opening trap, I first learn the danger and the
   safe defense; I am not taught to gamble on a trick as if it were sound.
4. As a player learning an endgame, I see the goal and geometry before any
   specialist word such as “opposition” or “zugzwang.”
5. As a player completing a lesson, I must solve a distinct unseen checkpoint
   before the coach says I know it.
6. As a returning player, I see one active lesson, the natural next lesson,
   and optional exploration without losing my place.
7. As a coach or maintainer, I cannot expose content that fails structural,
   legality, outcome, delivery, or voice validation.

## 3. UX and UI contract

No new primary navigation item is added. Home stays brief; Learn owns the
plan; subject pages own browsing; Play with Coach owns board practice.

The Learn primary card uses this literal sequence:

```text
YOUR COACHING PLAN

Learning now
Piece safety
You start an attack and stop checking what your opponent can take.

[Continue with your coach]

Next: Opening basics — get every piece ready
```

A delivered lesson uses four clearly named stages:

```text
1. Watch
   “Before you capture, follow every reply until nobody can capture again.”

2. Try with help
   “What can your opponent take after your move?”
   [Show one hint] [Choose a move]

3. Prove it
   “New position. This time I will not show the answer.”
   [Choose a move]

4. Use it in a game
   “Play with Coach. I’ll watch for this idea and bring you back here if it
   still trips you up.”
   [Practise with your coach]
```

The first essential endgame lesson is introduced without unexplained jargon:

```text
Can the king catch the pawn?

Imagine a box from the pawn to its promotion square. If the king can step
inside that box, it can usually catch the pawn. If it cannot, the pawn usually
promotes.

Rule to remember: check the box before you start calculating moves.
```

Trap lessons are defense-first:

```text
Scholar's Mate danger

The queen and bishop are both aiming at f7. Do not chase the queen while f7 is
unprotected. Develop a piece that also guards the threat.

Rule to remember: when two pieces attack the same square near your king,
answer the threat before starting your own plan.
```

UX constraints:

- Do not show invalid or undeliverable lessons as disabled/locked cards.
- Do not show raw detector names, centipawn values, internal percentages, tier
  codes, or empty explanations.
- Explain a specialist chess term in plain language before using the term.
- Every lesson ends with one short rule the player can reuse in another game.
- Exploration never replaces or silently advances the active coaching plan.

## 4. Technical behavior

### Canonical content

- All opening readers and recognizers adapt
  `opening_curriculum.json`; no second opening record table may be authored.
- All trap catalogs and Play-with-Coach modes adapt `traps.json`; execution,
  recognition, and avoidance use the canonical setup and full line.
- All current and proactive endgame teaching adapts
  `endgame_theory_tree.json`; `endgames.json` stops being a runtime source.

### Content gate

A reusable offline validator checks every player-visible record:

- required identifiers, names, goals, explanations, and reusable principle;
- structurally valid FEN;
- legal and unambiguous SAN from the stated position;
- a fully playable authored sequence;
- side-to-move and response-tree correctness;
- exact Syzygy preservation for eligible positions;
- engine verification for positions outside tablebase coverage;
- demonstrated terminal/result claims rather than an unsupported label;
- a guided example and a distinct independent checkpoint;
- no answer exposed before the player's first attempt;
- player-safe wording and no empty teaching copy.

The catalog response contains only records that pass the gate. Development and
CI fail if a record marked for player exposure does not pass. Quarantined
records remain in their canonical source so they can be repaired without
creating a shadow inventory.

### Lesson state

The lesson contract records:

- `lesson_id` and canonical `content_version`;
- stage: `watch`, `guided_try`, `independent_proof`, or
  `game_application`;
- attempts, hint use, correctness, and completion;
- the source game/topic that caused the prescription when one exists;
- a return target to the active personal plan.

A lesson is demonstrated only after the independent checkpoint succeeds. A
guided success may move the player forward, but it is not proof of mastery.
Game evidence can later schedule a refresh without erasing the completed
lesson.

## 5. Edge cases and honesty rules

- If no lesson in a requested topic passes validation, the coach says it does
  not yet have a verified lesson and chooses another useful topic. It does not
  fabricate copy or expose a broken board.
- If analysis evidence is insufficient, the coach says it needs more verified
  games; it does not invent a personal weakness.
- If a tablebase and authored answer disagree, the record is quarantined until
  repaired. Runtime code never guesses.
- If engine verification is unavailable, positions outside tablebase coverage
  remain unverified and hidden.
- If a player's saved lesson version no longer exists, restart at Watch on the
  current version and explain that the lesson was improved.
- If a hint is used, the attempt stays guided; it cannot satisfy independent
  proof.
- If a player explores a different lesson, preserve the active plan and return
  them to it afterward.
- If an opening has recognition metadata but no teachable line, it may identify
  the game opening but may not appear as an available lesson.

## 6. Acceptance scenarios

1. Running the content gate reports every canonical failure with subject,
   record key, position/ply, and an actionable reason.
2. Every lesson returned by a public catalog can be started, played legally to
   completion, and returned to the personal plan.
3. No catalog returns a quarantined opening, trap, or endgame.
4. Opening move responses retain their authored explanations.
5. Trap practice uses the canonical full line and can enter recognition,
   avoidance, and execution modes.
6. A current endgame lesson never exposes `correct_move_san` before an
   attempt.
7. An answer that loses a tablebase win or draw fails validation.
8. A guided success does not mark the lesson demonstrated; an unseen correct
   answer does.
9. The player can browse optional lessons and return to the unchanged active
   coaching plan.
10. Home, Learn, subject pages, and Game Review all point to their canonical
    player routes with no duplicate curriculum surface.
11. Focused backend contract tests, frontend component tests, the production
    frontend build, and the offline content audit pass before handoff.

## 7. Pre-code requirements

- Scope and repair order were explicitly approved by Mohit.
- The literal learner flow and player-facing copy are defined above.
- The implementation begins at shared content loaders/validators, not by
  patching individual screens.
- Chess truth comes from deterministic legality checks, Syzygy where exact,
  and a pinned engine verification path where Syzygy is not eligible.
- Existing corpus snapshots decide repair priority. No engagement threshold is
  locked against contaminated pre-launch analytics.
- The release outcome is a stronger catalog, not a smaller one: repair content,
  complete missing teaching, validate it, and restore it.
- Completion order is locked to existing evidence: finish the 12 already-legal
  opening lines first; add defense teaching to the 21 chess-verified traps;
  add the essential queen-mate, rook-mate, stop-promotion, and active-rook
  endgames; then repair the remaining records by player frequency and level.
- The validator may temporarily quarantine a broken record during development,
  but a quarantine count is unfinished work and cannot be reported as the
  completed curriculum.
- Manual verification by Mohit and the invited coaches is the final product
  stage, after automated development evidence is green.
