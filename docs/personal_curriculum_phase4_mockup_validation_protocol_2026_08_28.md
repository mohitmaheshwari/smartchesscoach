# Personal Curriculum Phase 4 — Representative-Player Mockup Validation

**Status:** READY TO RUN — protocol prepared 2026-08-28; no player sessions have been completed or claimed.

## Purpose

Test whether the signed Home/Learn proposal feels like one coach guiding one student, not a reorganized library. This is a comprehension and navigation check before implementation, not a preference poll about colors or visual polish.

## Mockups under test

Use the literal Home, Learn, Explore, lesson-return, and mobile contracts in `docs/personal_curriculum_route_ux_contract_2026_08_28.md`. Do not improve the words while a participant is testing them; record confusion first so the contract can be corrected deliberately.

Required states:

1. Home with one new lesson and one short review.
2. Learn with Learning now, Keeping fresh, Naturally next, and Explore.
3. Explore lesson header that preserves the coach's recommendation.
4. Lesson completion returning to the plan.
5. The same Home and Learn states at a mobile viewport.

## Participants

Recruit representative players, not internal chess-product experts:

- at least one 600–900 player;
- at least one 1000–1200 player;
- at least one 1300–1500 player; and
- at least one participant who normally prefers browsing or choosing a topic rather than accepting a recommendation.

One participant may satisfy both a rating-band slot and the browse-oriented slot. Record self-reported rating source and whether the player has used ChessGuru before. Do not coach participants toward the intended answer.

### Recruitment evidence

`backend/data/corpus_snapshots/funnel_and_recruitment_2026-08-28.json` is the
date-versioned, aggregate-only server source for structural reach. It records
45 users with at least five analysed games, including 8 at 600–899, 8 at
900–1199, and 7 at 1200–1499. Those counts establish that the required rating
cohorts are recruitable; select the actual participants using their exact
rating, and do not expose identifiers in the validation report.

The snapshot is explicitly **not** an engagement baseline. Do not use
pre-launch PostHog history to set mockup-validation thresholds or interpret
missing client events as non-use.

## Moderator rules

- Start with: “Please think aloud. I am testing the page, not you.”
- Present the state without explaining Personal Curriculum, Explore, or Naturally next.
- Ask the task, then remain silent unless the participant is completely stuck.
- Do not point, paraphrase labels, or say that an answer is correct.
- Record the participant's first action, exact words where useful, hesitation, wrong turns, and whether help was needed.
- After each state, ask what they believe will happen next before allowing the click.
- Run the mobile tasks on a real phone or a faithfully sized touch viewport; a desktop window described as “mobile” is not evidence.

## Tasks and questions

### Task 1 — Understand Home

Show Home and ask:

1. “What is your coach asking you to learn today?”
2. “Why did the coach choose that for you?”
3. “What would you do next?”
4. “Is anything else expected today?”

Observe whether the review competes with the primary action and whether the personal reason is distinguishable from generic praise.

### Task 2 — Understand the plan

Show Learn and ask:

1. “What are you working on now?”
2. “What has to happen next with it?”
3. “What does Keeping fresh mean here?”
4. “Can you study something else if you are curious? Show me.”
5. “Is Naturally next locked? What makes you think that?”

Observe whether the participant treats the page as a syllabus wall, mistakes sequence guidance for a paywall, or cannot find Explore.

### Task 3 — Browse without losing the plan

Ask the participant to explore an endgame or opening that was not recommended. On the Explore lesson header ask:

1. “What happened to the lesson your coach recommended?”
2. “If you finish this lesson, what do you expect your main plan to be?”
3. “How would you return to the coach's plan?”

The intended understanding is that browsing records real learning evidence but does not silently replace the active plan.

### Task 4 — Finish a lesson

Show the lesson-completion state and ask:

1. “What does the coach believe you can do now?”
2. “Does this say you have mastered the idea? Why or why not?”
3. “What will happen later?”
4. “Where would you go next?”

Observe whether “learning” is understood as honest partial progress and whether Back to your plan is the natural exit.

### Task 5 — Mobile priority

On mobile ask the participant to:

1. find the primary recommendation and explain why it was chosen;
2. continue the current lesson;
3. find Explore;
4. return from a lesson to the plan.

Record whether the primary action and reason appear before history/library content, whether Continue is reachable before scrolling through a catalogue, and whether any two-column assumption makes the board or coaching panel unusable.

## Per-participant record

```text
Participant code:
Rating and source:
ChessGuru familiarity:
Browse-oriented: yes / no / unclear
Device and viewport:

HOME
Named current lesson without help:
Explained personal reason without help:
Named next action without help:
First action / hesitation / wrong turn:
Participant's words:

LEARN
Identified Learning now:
Understood Keeping fresh:
Understood Naturally next as guidance, not a lock:
Found Explore without help:
First action / hesitation / wrong turn:
Participant's words:

EXPLORE
Understood current recommendation remains active:
Expected result of finishing browsed lesson:
Found return path:
Participant's words:

LESSON RETURN
Understood honest current state:
Understood later review/application:
Chose Back to your plan:
Participant's words:

MOBILE
Primary action/reason encountered before library:
Continue reachable before full library:
Explore found:
Board/coaching panel usable:

Moderator help given, if any:
Observed confusion:
Proposed contract change (after session, not during):
```

## Synthesis

Report results by rating band and browse orientation. For every failure, distinguish:

- wording comprehension;
- visual hierarchy;
- navigation/findability;
- expectation mismatch; or
- prototype limitation.

Keep exact examples beside summaries. Do not turn a participant's silence into agreement, and do not average away a severe navigation failure in one cohort.

## Decision rule

The signed qualitative criteria remain the authority:

- players can answer what they are learning, why the coach chose it, and what to do next without assistance;
- the experience is described as guidance from one coach rather than disconnected tools;
- a browse-oriented student can find openings, traps, endgames, principles, and thinking lessons without unexplained locks; and
- the mobile priority contract works in practice.

No numeric pass bar is invented in this protocol, and none may be backfilled
from contaminated PostHog history. After the sessions, Mohit must review the
cohort evidence and either sign the mockups, require contract changes and a
retest, or explicitly narrow the first cohort before Phase 4 code begins.
