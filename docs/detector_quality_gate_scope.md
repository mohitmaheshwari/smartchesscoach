# Detector Quality Gate — Scope

**Status:** SIGNED OFF; V1 IMPLEMENTED BEHIND DEFAULT-OFF ROLLOUT
(`DETECTOR_QUALITY_GATE_ENFORCED`, 2026-08-27)
**Section 0 path:** EXTEND existing systems + Lichess validation — signed off by
Mohit on 2026-08-27.

## 0. Existing surfaces audit

### What already exists

ChessGuru does not have one detector system. It has several legitimate detector
layers, plus some overlapping ones:

| Existing source | What it already provides | Main consumer |
|---|---|---|
| `services/shape_patterns.py` | Named tactical and board-shape evidence such as forks, pins, skewers, free pieces and weak squares | Central caption pipeline and stored caption facts |
| `services/caption_principles.py` + `caption_facts.py` | Board-verified teaching-principle violations and structured evidence | Central caption pipeline, game review and PWC captions |
| `services/concept_detectors/registry.py` | Grades whether a learned skill was applied or missed in a real game | Learning/mastery transfer runner |
| `services/chess_brain/detector_registry.py` | Tactical, strategic and behavioral position detections | Intelligent position coach |
| `services/cognitive_gap_subtypes.py` + `move_observation_deriver.py` | Converts analyzed moves into stored weakness categories, subtypes and D_live evidence | Player diagnosis, focus selection and progress measurement |
| Standalone modules such as `prophylaxis_detector.py`, `opening_deviation_detector.py`, `board_concepts.py` and `concept_attribution.py` | Narrow specialist detections or experimental naming | Mixed: some production, some shadow, some not integrated |
| Audit scripts and tests | Individual precision, recall, geometry and implementation-agreement checks | Developer review only; results are not a runtime authority |

### What is already strong

- D_live has a stable opportunity denominator and a reproducible independent
  implementation-agreement audit.
- Current-schema `simple_hang` has strong positive precision evidence and a
  reproducible recall audit.
- The shape-pattern layer has an independent geometric verifier and passed all
  382 sampled checks in the 2026-08-27 production run.
- The central caption pipeline already consumes the canonical shape and
  principle sources; it must remain the only player-facing caption authority.
- The coach test strategy already requires precision and recall regression
  floors in a committed source, but that authority has not been implemented.

### Overlap and failure risk

- Detector membership, names and thresholds are spread across several
  registries. Some separation is legitimate because position geometry,
  teaching attribution, weakness classification and mastery transfer are
  different claims. A new universal detector implementation would incorrectly
  collapse those concerns and duplicate working code.
- Quality evidence is not canonical. Precision claims live in module comments,
  tests and documents; production consumers do not have one enforceable answer
  to “may this detector select a plan, write a caption, measure mastery, run in
  shadow, or remain disabled?”
- Tests often prove geometry or implementation agreement while downstream copy
  treats that as semantic attribution. Those are different evidence claims.
- The new `board_concepts` and `concept_attribution` path overlaps existing
  lesson-transfer and caption geometry but is not integrated. Production
  sampling found clear rule-of-square scope errors, so it must not become a
  third player-facing path.
- The current working tree contains extensive unrelated user changes, including
  edits in detector-adjacent files. Any implementation must avoid overwriting or
  mechanically rewriting those files.

### Decision based on overlap

**Recommended path: EXTEND existing systems.**

The product should add one canonical *quality and authorization authority* over
the existing detector sources. It will reference their existing IDs and
evidence; it will not copy detector logic, concept definitions, names or
threshold tables. Existing production consumers will consult that authority
before allowing a detector to drive a player-facing claim, active focus,
mastery verdict or improvement measurement.

The existing detector implementations remain in their appropriate canonical
layers. Weak detectors are improved in place or quarantined. The experimental
`board_concepts` attribution work is either tightened and admitted through the
same gate or kept shadow-only; no parallel caption path is created.

**Rejected paths:**

- **PARALLEL:** a new detector registry or coaching engine would duplicate at
  least four existing sources and deepen the current fragmentation.
- **REPLACE:** rewriting all detectors would discard proven D_live, caption and
  tactical-geometry machinery, while creating a much larger validation burden.

### Section 0 decision

**LOCKED: EXTEND existing systems + Lichess validation.** Numeric quality floors
will be measured and locked through the production corpus rather than chosen
from intuition.

## 1. What it is

Detector Quality Gate makes ChessGuru earn the right to make every chess claim.
Each existing detector is tested on real player games, independent chess truth,
hard counterexamples and relevant Lichess positions. The result decides what the
detector is allowed to do: choose an improvement plan, measure progress, explain
a move, collect evidence silently, or remain disabled. A weak detector does not
get confident wording; it is improved in its existing home or made silent until
the evidence is strong enough.

This does not promise mathematically perfect detectors. It promises that the
product never presents an unproven detector as a personal coaching truth.

## 2. What the user sees

There is no new detector dashboard or settings page. The change is visible in
the reliability of the existing coached experience.

When evidence is strong enough to drive a plan:

```text
YOUR PRIMARY FOCUS

Before moving, check whether the square is safe.

Why this?
I found this in 6 of your recent games. Here are the positions.

[Review the first moment]   [Practise this]
```

When a detector is safe for one move but cannot measure mastery:

```text
Move 24

Your knight on e5 can be taken by the pawn on f6.
Move it or defend it before continuing your attack.
```

The move may be explained, but the product does not turn that detector into a
long-term weakness or say that it has been fixed.

When evidence is incomplete:

```text
I found a possible endgame pattern here, but I do not have enough evidence to
make it part of your plan yet. I will keep watching.
```

In many cases the user sees nothing at all. Silence is the correct output when
the detector cannot support an honest and useful claim.

## 3. In scope (V1)

- Inventory every detector reachable from a player-facing caption, game review,
  Play with Coach intervention, active-focus selector, mastery update or
  improvement verdict. Record its canonical implementation and consumer.
- Give each inventoried detector one authorization state:
  - **Plan-grade:** may select a focus and contribute to real-game progress.
  - **Caption-grade:** may explain a verified move but may not select a focus or
    prove mastery.
  - **Shadow:** may run and collect audit evidence but may not speak to players.
  - **Disabled:** may neither run in production coaching nor affect player state.
- Keep one canonical quality authority referencing existing detector IDs. It
  does not copy detector logic, concept names, chess rules or rating tables.
- Enforce authorization at the existing central chokepoints so a shadow detector
  cannot accidentally become a caption, plan, mastery event or verdict.
- Store separate evidence for geometry correctness, move consequence,
  attribution correctness, precision, recall, rating-band behavior, opportunity
  count and adversarial performance. One kind of evidence cannot silently stand
  in for another.
- Reuse the 4,110,434-row production `lichess_puzzles` corpus for theme-positive
  tactical validation. Do not import a duplicate puzzle collection.
- Build a separate, reproducible research corpus from public Lichess standard
  games for random negatives, recall measurement and rating/time-control strata.
  External games never enter user `games`, `move_observations`, active-focus or
  improvement evidence.
- Use tablebase-verified and independently reviewed gold positions for rare
  endgame concepts that broad Lichess themes cannot identify precisely.
- Include adversarial examples: sound sacrifices, already-lost positions,
  forced moves, alternative winning moves, other pieces stopping a passer,
  promotion with check and visually similar non-examples.
- Fix or quarantine the known highest-risk families first:
  `rule_of_square`, `trapped_piece`, broad `king_safety`, time-management claims
  and any lesson-transfer detector with zero or insufficient real fires.
- Preserve D_live, current-schema `simple_hang` and canonical tactical-shape
  machinery. Improve them in place; do not rewrite proven components.
- Produce one reproducible quality report showing every live detector, its
  evidence, authorization state, limitations and most recent audit version.
- Add regression checks so a detector cannot lose required evidence or gain a
  more powerful authorization without review.
- Keep experimental detector output out of the player-facing central caption
  pipeline until its authorization permits it.

## 4. Explicitly out of scope (V1)

- Claiming that every detector is “10/10,” perfect, complete or incapable of a
  future false positive.
- Making every detector Plan-grade. Detectors without adequate opportunities or
  gold truth remain Shadow or Disabled.
- Rewriting all detector implementations into one universal engine.
- Creating a second caption generator, active-focus picker, mastery engine or
  cognitive-gap taxonomy.
- Using an LLM as the final chess-truth judge.
- Treating a Lichess theme as unquestionable ground truth. Disagreements remain
  review items because theme tags and ChessGuru detectors answer different
  questions in some positions.
- Mixing public Lichess games with ChessGuru-user evidence or using them to
  claim that a ChessGuru player improved.
- Depending on the live Lichess API during coaching or analysis. External
  validation is an offline research process.
- Adding new lessons, detector-driven UI pages, pricing changes or the
  multi-focus product model. Those are separate product scopes.
- Inferring player emotion, motivation or intent from external games.
- Shipping new named concepts merely because the external corpus contains many
  examples. This scope grades and repairs existing claims first.

## 5. Success criteria

V1 succeeds when all of the following are true:

- Every detector that can affect a player-facing caption, focus, mastery state
  or improvement verdict has a canonical authorization state and traceable
  evidence. Unknown authorization fails closed.
- No Shadow or Disabled detector can change a player-facing response or learner
  state in integration tests.
- Every Plan-grade detector has independently measured positive accuracy and
  opportunity/recall evidence on held-out data appropriate to its claim. A
  detector with no stable opportunity denominator cannot prove improvement.
- Every Caption-grade detector has independently measured attribution accuracy;
  geometry-only evidence cannot authorize causal coaching language.
- The known rule-of-square false cases with other defending pieces no longer
  produce player-facing rule-of-square claims.
- The known king-safety and trapped-piece suspicious cases are either corrected
  and admitted through the gate or made silent.
- A fixed held-out corpus produces the same quality report on repeated runs, and
  detector changes show an explicit before/after comparison.
- CI fails when a detector drops below its locked evidence floor, loses its
  verifier, changes its evidence version without review, or receives an
  authorization stronger than its evidence allows.
- A full real-game pipeline test proves that a Plan-grade detector can still
  reach review, PWC, focus selection and progress, while a Shadow detector
  cannot reach any of them.
- A reviewer can answer “why is this detector allowed to say this?” from one
  report without searching module comments, planning documents and old audit
  output.

## 6. Open questions

### Q1. What evidence floors authorize each grade?

- **Why unresolved:** existing documents contain several different precision
  floors, chosen for different detectors and sometimes without a current
  distribution. A universal gut-chosen number would recreate the problem this
  scope is meant to solve.
- **Unblocking step:** bake off candidate floor policies against every currently
  inventoried detector, showing how many detectors qualify, which false cases
  pass, confidence intervals, sample sizes and the cost of false speech versus
  silence. Lock the result through `/lock-via-data`.

### Q2. How large must the raw Lichess validation corpus be?

- **Why unresolved:** the relevant unit is detector opportunities, not total
  games. Common forks and rare Philidor positions need different game counts.
- **Unblocking step:** stream a bounded pilot stratified by rating and time
  control, plot opportunities per detector, then choose corpus sizes at the
  point where additional games stop materially improving confidence. Do not
  choose one sample size for every detector.

### Q3. What is the canonical persisted shape of the quality authority?

- **Why unresolved:** a committed manifest is auditable, while a generated
  report avoids duplicated detector membership. The implementation must achieve
  both without copying concept sources.
- **Unblocking step:** architecture review after the detector inventory. Compare
  a generated manifest, a committed evidence ledger, and a hybrid where
  registries declare identity while audit evidence supplies authorization.

### Q4. Who supplies independent semantic gold?

- **Why unresolved:** Stockfish and Lichess can verify consequence and geometry,
  but not always whether “king safety,” “trapped piece” or another human lesson
  is the correct attribution.
- **Unblocking step:** define a blinded review packet with FEN, played move,
  alternatives and engine line. Require an independent board reviewer for
  ambiguous attribution families and record disagreements rather than forcing
  consensus silently.

### Q5. Which detector aliases refer to the same underlying claim?

- **Why unresolved:** the code contains several registries and older standalone
  detectors. Some are legitimate layers; others may duplicate facts under
  different names.
- **Unblocking step:** complete the single-source audit and create explicit
  aliases or retirements before the quality authority is implemented.

### Q6. What licensing and provenance must be retained for external material?

- **Why unresolved:** the official Lichess database is designed for reuse, but
  the validation artifact must preserve source identifiers, download version,
  checksums and any required attribution without leaking player evidence into
  product collections.
- **Unblocking step:** document the exact official dataset, license/provenance
  requirements, monthly file/checksum and retention policy before ingestion.

## 7. Pre-code requirements

Every item below is a hard gate:

- [x] Section 0 path explicitly signed off: EXTEND existing systems + Lichess
  validation.
- [x] Mohit explicitly signs off the complete Sections 0–7 scope.
- [x] Produce the full reachable-detector inventory with canonical source,
  downstream consumers and duplicate/alias findings.
- [x] Decide the single quality-authority architecture without duplicating
  detector membership, chess rules, labels or thresholds.
- [x] Run `/lock-via-data` for grade floors, uncertainty treatment and minimum
  evidence policies; cite the production measurements and rejected candidates.
- [x] Run the bounded Lichess raw-game pilot and lock corpus strata/sizes from
  observed detector opportunities rather than total-game intuition.
- [x] Define the independent semantic-gold review packet and adjudication rule.
- [x] Verify and document Lichess dataset provenance, checksum and permitted use.
- [x] Freeze held-out splits by player/source unit so related moves cannot leak
  between tuning and validation.
- [x] Record the current detector-quality baseline and known false cases as the
  before-state.
- [x] Inspect all overlapping dirty-worktree files before editing; preserve the
  user's existing changes and avoid bulk rewrites.
- [x] Make the required detector/audit test suites runnable in CI before their
  numbers can authorize production behavior.
- [x] Run `/audit-pre-code` after every preceding gate passes and before the
  first production-code change.
