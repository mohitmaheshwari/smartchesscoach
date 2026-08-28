# Personal Curriculum — V1 Lesson Audit

**Status:** COMPLETE 2026-08-28. No proposed knowledge lesson currently satisfies the full teach → independent recall → Plan-grade real-game application contract.

## Audit standard

A V1 Personal Curriculum lesson must have:

1. one stable curriculum identity and canonical content source;
2. board-verified chess truth;
3. plain language for 600–1500 players;
4. demonstration, guided practice, and a distinct unassisted checkpoint;
5. recorded assistance and result evidence;
6. a reviewed opportunity detector before claiming real-game use;
7. one valid destination and a return to the same coaching plan.

## Verdict table

| Candidate | Existing strength | Blocking gap | Verdict |
|---|---|---|---|
| Develop your pieces | `coached_development` identity, focused PWC prompts, `OP_FINISH_DEVELOPMENT` facts | `development_basics` has no canonical lesson; generic coached play does not form a demonstration/guided/checkpoint sequence; application output is not Plan-grade | **Not V1-ready** |
| Castle before attacking | Strong `OP_NOT_CASTLED` fact/copy and board geometry | No curriculum skill identity, lesson, distinct positions, assistance evidence, or Plan-grade application contract | **Not V1-ready** |
| Defend Scholar’s Mate | Stable skill ID and focused detector with passing unit tests | `traps.json` entry teaches a later punishment line, not the immediate defensive choices promised by the skill; no canonical defensive lesson or Plan-grade authorization | **Not V1-ready** |
| Defend Fried Liver | Stable skill ID, canonical recognition geometry, passing unit tests | Existing trap content teaches White’s attacking line; detector treats every move except `Nxd5` as applied, which proves trap avoidance but not necessarily sound defense; no defensive lesson or Plan-grade authorization | **Not V1-ready** |
| Rule of the Square | Canonical legal-race truth, routed interactive lesson, three legal verified answers | Answer is revealed before retry; no assistance/session evidence; no delayed checkpoint; application detector is explicitly **Disabled** due five eligible positions from one game | **Best first lesson shell, not full-loop ready** |
| Opposition | Routed interactive lesson, three legal verified answers, focused detector tests | Jargon-heavy content, no assistance/session evidence, same-position answer reveal, no delayed checkpoint; application detector is Shadow, not Plan-grade | **Partial, follows Rule of the Square** |

## Verification performed

- Parsed all six Rule-of-the-Square/Opposition positions with `python-chess`.
- Every stored correct UCI move is legal.
- Every generated SAN exactly matches the authored SAN.
- Focused detector suite passed: **37 tests** across Rule of the Square, Opposition, Scholar’s Mate defense, and Fried Liver defense.
- Runtime quality authority reports:
  - `concept:endgame_rule_of_square`: **Disabled**, cannot influence mastery;
  - `concept:endgame_opposition`: **Shadow**;
  - `concept:defend_scholars_mate`: **Shadow**;
  - `concept:defend_fried_liver`: **Shadow**.
- Shadow output currently reaches product surfaces only because detector-quality enforcement defaults off. Personal Curriculum must enforce Plan-grade eligibility itself; it must not inherit that permissive legacy behavior.

## Voice findings

The check-voice rules found these blocking examples:

- **Jargon:** “Opposition” and “outflank” are used without first describing the board geometry. The lesson should first say “put the kings facing each other with one square between them.”
- **Harsh/unsupported framing:** “You threw away the win” is unnecessary in a teaching exercise and does not help the student see the transferable rule.
- **Overclaim:** “The diagonal entering move is always the best” is broader than the three authored positions prove.
- **Incomplete principle ending:** several correct/wrong responses explain the stored move but do not consistently finish with a rule the student can use in a different position.
- **Internal mastery framing:** “Lesson Complete” after three positions is acceptable as session completion, but must not be rendered as concept mastery.

No user-facing text is changed by this audit. Rewrites require their own board review and voice check.

## Interaction findings

The current endgame UI is a useful teaching component, but not yet a learning-evidence component:

- the concept card is visible before every attempt, so some attempts are guided by design;
- a wrong answer immediately reveals the correct move;
- retrying the same position after reveal cannot count as independent recall;
- “first try” score exists only in page state;
- no hint type, answer reveal, attempt, session completion, or resume event is persisted;
- completion sends the student to “More Lessons,” not back to a coach-owned next step;
- there is no delayed review mode that withholds the rule until after the move.

## V1 lesson decision

Use **Rule of the Square** as the first lesson-contract vertical slice because it has the strongest canonical board truth and the most complete existing interaction. Its first slice may advance only through **Can do alone** using controlled lesson evidence.

Do not claim **Used in games** or **Reliable** until:

- the application detector receives Plan-grade authorization from independent multi-game evidence;
- opportunity/non-opportunity behavior is audited;
- the shared curriculum evidence contract records post-teaching game opportunities.

Then adapt Opposition. Development, castling, and trap defense require actual lesson authoring before they enter V1; existing captions and trap lines are not substitutes.

## Required changes before the first lesson can ship

- Add a shared lesson-session envelope around the existing endgame component.
- Record shown explanation, hint/reveal, first attempt, retries, assistance, and completion.
- Add an independent checkpoint using a distinct position with teaching text hidden until after the move.
- Return the student to the Personal Curriculum plan, not the generic lesson catalogue.
- Translate completion honestly: Learning, Can do with help, or Can do alone.
- Keep application claims suppressed unless the detector is Plan-grade.
- Rewrite and board-review the audited voice issues.

