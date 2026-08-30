# Personalized teaching voice audit — 2026-08-30

## Verdict

**PASS for invited validation.** The personalized lesson path speaks as one
coach to one student, uses board-specific language, and does not invent a
permanent learner type. Chess truth remains in the canonical lesson owners;
only the order, prompt, help, and explanation are adapted.

## Audited surfaces

- Personalized board workspace, help choices, feedback, completion, and
  evidence drawer.
- Home and Learn primary-plan copy.
- Compact curriculum state shown on Game Review, Progress, Lab, and Play with
  Coach.
- Server-generated reason choices, misconceptions, corrections, review copy,
  and evidence language.
- Derived opening, trap, endgame, and concept lesson descriptors.

## Rules checked

1. Write for a 600–1500 player: short sentences and a concrete piece, pawn,
   square, capture, check, or threat where an explanation is needed.
2. Do not expose internal taxonomy as coaching language.
3. Do not describe centipawn loss as pieces or pawns lost.
4. Do not claim a fixed visual, verbal, or other learner type.
5. Do not call a lesson mastered from a lucky move, a revealed answer, or a
   repeated taught position.
6. Do not create a second chess-truth or caption pipeline.
7. State missing real-game and later-recall evidence plainly.

## Corrections made during the audit

- Replaced `forcing threat` with `check, capture, or direct threat`.
- Replaced `wins material` with `wins a piece or pawn`.
- Replaced `undeveloped piece` with `piece still on its starting square`.
- Replaced `repertoire evidence` with `which you already play`.
- Replaced `board relationship` with the exact piece-or-square question.
- Added player-facing sentences for every stored misconception key so labels
  such as `piece_safety_relationship_unclear` never reach the student.
- Rewrote completion and cross-surface evidence copy in the coach's first
  person while retaining the honest “not measured yet” meaning.

## Evidence

- All **80** published canonical lessons that enter the workspace are checked
  offline: **37 openings, 23 traps, and 20 endgames**.
- The descriptor gate requires a legal unique FEN, a private server grading
  path, a reason choice, one primary skill, source provenance, and a distinct
  transfer position before independent credit is possible.
- The public descriptor strips private expected moves and expected reasons.
- Help preference is remembered only for the same skill and only when that
  help preceded a correct answer. The profile explicitly stores no permanent
  learner type.
- `Reliable` remains unavailable. The UI shows the highest proved state and
  says when game use or later recall has not been measured.
- New coaching copy contains none of the rejected phrases `forcing threat`,
  `repertoire evidence`, `board relationship`, `wins material immediately`,
  or the forbidden centipawn-as-material wording.

## Boundary

This audit covers the new personalized curriculum path and the canonical copy
it publishes. Existing unrelated coaching and caption surfaces retain their
own established audits and are not silently rewritten by this feature.
