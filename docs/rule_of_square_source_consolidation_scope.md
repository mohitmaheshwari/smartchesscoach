# Rule-of-Square Source Consolidation - Scope

**Status:** LOCKED BY MOHIT; PRE-CODE GATES PASSED
**Section 0 path:** EXTEND the existing concept-detector source and retire duplicate logic behind compatible adapters.

## 0. Existing surfaces audit

Three backend paths independently decide whether the rule of the square applies:

- `services/concept_detectors/rule_of_the_square.py` grades whether a player
  applied or missed the skill and feeds mastery, coach memory and training.
- `services/caption_facts.py` separately computes pawn distance, promotion
  square and king-in-the-square geometry for game-review captions.
- `services/endgame_detectors/rule_of_square_detector.py` contains an older
  detector used by the legacy endgame principle registry and puzzle-position
  validation.

They overlap on the same chess fact but disagree about eligibility, tempo and
pawn direction. The legacy implementation even infers pawn color from its rank,
which fails for an advanced white pawn or a black pawn that has not crossed the
middle. The caption path is narrower in some places and broader in others.
Consequently, one game can be called a rule-of-square lesson by one surface and
rejected by another.

The genuine differentiation is not the chess truth:

- captions need wording and evidence squares;
- mastery needs an `applied` / `missed` verdict;
- puzzle extraction needs a position-eligibility decision.

Those are legitimate derived views of one fact, not reasons to maintain three
recognizers.

**Decision: EXTEND.** The existing concept-detector module becomes the one
canonical source of rule-of-square chess truth. Caption, legacy endgame and
puzzle consumers keep their existing public contracts but derive their answers
from that source. Duplicate geometry and pawn-color inference are retired.

## 1. What it is

ChessGuru will have one definition of the rule of the square. It will decide
whether a pawn race is genuinely controlled by the defending king, whether the
king can catch the pawn, and whether the player's move demonstrated or missed
that idea. Every coaching surface will read that same answer. Ambiguous
positions stay silent rather than receiving a confident but debatable lesson.

## 2. What the user sees

There is no new page or control. Existing review, Play with Coach and training
surfaces become consistent.

When the rule genuinely decides the position:

```text
Your king needed to step into the pawn's square now.
Kf4 keeps the pawn catchable; h4 lets it run.
```

When the player correctly uses it:

```text
Good - your king stepped into the pawn's square.
You can catch it before it promotes.
```

When another piece, another pawn race or a tactical move determines the result,
ChessGuru gives no rule-of-square claim and lets another verified lesson speak.

## 3. In scope (V1)

- Make `services/concept_detectors/rule_of_the_square.py` the canonical
  runtime source for rule-of-square geometry, eligibility and move outcome.
- Represent enough neutral evidence for every consumer: critical pawn,
  promotion square, defending king, pawn distance, king distance, side to move,
  catchable-before, catchable-after and applicability reason.
- Use the pawn's actual color; never infer direction from its rank.
- Account for tempo, including the defending side's immediate legal king step.
- Restrict V1 coaching claims to clean king-and-pawn races where non-king pieces
  cannot decide the pawn's fate.
- Convert the caption principle, mastery detector, legacy registry and
  rule-of-square puzzle eligibility into derived views of the canonical fact.
- Preserve existing public detector result words through thin adapters.
- Add a committed, provenance-recorded set of tablebase-adjudicated positive,
  negative and adversarial positions.
- Include advanced white pawns, advanced black pawns, blocked pawns, double-push
  tempo, occupied promotion paths, illegal king steps, extra defending pieces,
  mutual pawn races and visually similar non-examples.
- Add a guard test proving the retired modules no longer contain independent
  square/distance/pawn-direction logic.
- Keep every rule-of-square authorization Disabled while validation runs.
- Require a separate evidence-reviewed promotion change after the locked
  Detector Quality Gate is satisfied.

## 4. Explicitly out of scope (V1)

- Runtime calls to an online tablebase, Stockfish or an LLM.
- Claiming every pawn endgame is a rule-of-square lesson.
- Lucena, Philidor, opposition, corresponding squares or general pawn-endgame
  coaching.
- Multi-piece endgames where a rook, queen, bishop or knight can stop or escort
  the pawn.
- New UI, lessons, notifications, pricing or opening content.
- Re-enabling the detector merely because the code is consolidated.
- Backfilling player mastery, focus history or stored captions before the new
  detector earns authorization.
- Deleting historical user evidence; any later correction is a separate,
  audited migration.

## 5. Success criteria

- Every runtime rule-of-square consumer derives its result from the canonical
  source; the duplicate-source guard fails if new independent geometry appears.
- All committed tablebase-adjudicated V1 positions match the canonical
  catchable/uncatchable verdict.
- Every adversarial non-example abstains, including the known positions where
  another defending piece controls the pawn.
- Caption, mastery, legacy and puzzle adapters agree on applicability for every
  shared test position.
- No rule-of-square output reaches a player while its authorization remains
  Disabled.
- A reviewer can trace a future claim from the surface back to one canonical
  evidence object and one gold-corpus case.

## 6. Open questions

- **Question:** Which exact tablebase source and snapshot will certify the gold
  positions?
  **Why unresolved:** no tablebase provenance file for this detector exists in
  the repository yet.
  **Unblocking step:** select an official Syzygy-compatible source, record its
  version/checksum or API response provenance, and independently replay every
  committed FEN before coding runtime changes.

- **Question:** Should mutual passed-pawn races be eligible in V1 or remain
  explicit non-examples?
  **Why unresolved:** the three current detectors disagree and the existing
  production pilot found many broad candidates without semantic adjudication.
  **Unblocking step:** adjudicate a targeted mutual-race packet and include the
  family only if one pawn's square remains the load-bearing lesson across the
  packet.

- **Question:** Does the current-schema production corpus provide enough
  independently reviewable fires for Caption-grade after consolidation?
  **Why unresolved:** the earlier 21/29 audit predates the canonical design.
  **Unblocking step:** rerun the per-fire audit after implementation; remain
  Disabled if the minimum reviewed-fire and negative-case counts are not met.

## 7. Pre-code requirements

- [x] Existing surfaces and duplicate logic audited.
- [x] EXTEND path selected; no fourth recognizer.
- [x] Player-facing contract states when the coach speaks and abstains.
- [x] Existing rule-of-square paths explicitly Disabled.
- [x] Mohit explicitly signs off this complete scope document.
- [x] Tablebase source/provenance selected and reachable for offline validation.
- [x] Mutual-race V1 decision resolved from a targeted packet.
- [x] Gold-case format and held-out split recorded.
- [x] Pre-code audit passes before the first runtime recognizer edit.
