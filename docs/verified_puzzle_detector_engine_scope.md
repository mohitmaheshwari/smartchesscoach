# Verified Puzzle Detector Engine — Scope

## 0. Existing surfaces audit

**What already touches this need**

- puzzle_extraction_service turns analyzed imported games into
  community_puzzles. It verifies board syntax and uses a forcing-move or
  tactical-PV heuristic, then writes approved=true. Its fallback classifier
  can label a large engine loss as piece safety even when no piece-safety fact
  has been proved.
- community_training_service and coach_puzzle_extractor populate
  community_training_positions from imported games and Play with Coach games.
  They have separate thresholds and text/category heuristics. This pool has no
  shared approval field or admission contract.
- skill_puzzle_extraction turns detector evidence into drill positions. Only
  rule of the square currently has a concept-specific position validator;
  other registered skills preserve ungated behavior and are written approved.
- concept_detectors and move_observation_deriver already detect learned-skill
  use and recurring mistake subtypes. They are legitimate consumers of shared
  chess facts, but they are not a complete puzzle admission engine.
- detector_quality is the canonical authorization authority for whether an
  existing detector may affect a caption, plan, prompt or mastery claim.
  Unknown detectors fail closed in its model, but puzzle ingestion and both
  puzzle-serving paths do not consistently consult it.
- caption_facts already owns the strongest reusable chess primitives,
  including legal, board-mutating exchange truth. Shape, endgame, opening and
  lesson systems own other canonical facts. These sources should be reused;
  another chess-rule library must not be created.
- curriculum_content_validator verifies that a personalized lesson is legal,
  playable, answer-private and honest about evidence. It validates the derived
  lesson contract, not whether every imported puzzle's named concept is the
  correct human lesson.
- PersonalizedLessonWorkspace, SkillDrill, prescribed pattern training and the
  diagnostic consume these pools. The user experiences the pools as one coach,
  even though the backend currently admits and labels them differently.
- verified_detector_loop and the detector quality gate already establish
  verify-or-abstain and authorization principles for captions and detector
  output. They do not yet provide one admission and repair loop for every
  training puzzle.

**Production evidence**

A read-only aggregate audit on 2026-08-30 found:

- community_puzzles: 11,551 rows; 11,424 approved; 596 detector-graded rows
  without a stored best move; 21 duplicate position/answer rows; 6 positions
  with conflicting stored answers.
- community_training_positions: 38,119 rows; none covered by an approval
  contract; 19 invalid stored positions; 2,643 duplicate position/answer rows;
  32 positions with conflicting stored answers.
- The source corpus is strong: 14,021 games, 13,425 analyzed games and 428,906
  move observations. It is suitable for detector discovery and hard-negative
  mining, but repeated games from roughly 120 users are not independent proof
  of generalization.

**Overlap and genuine differentiation**

The overlap is chess truth, detector authorization, engine analysis and lesson
grading. Those already exist and must remain canonical. The missing capability
is a single fail-closed admission decision that every extraction and serving
path uses, plus a high-coverage improvement loop that turns broad-but-valid
positions into specifically taught concepts over time.

**Decision**

EXTEND the existing canonical fact producers, detector quality authority and
training pools. Add one shared verified-puzzle admission contract and one
offline detector-improvement loop. Do not create a parallel chess engine,
taxonomy, puzzle collection, caption system or runtime LLM path.

Quarantine is the final safety valve, not the main strategy. A valid,
engine-stable real-game position that lacks a proven specific detector remains
useful as a broader calculation or threat-recognition exercise. Only broken
provenance, illegal reconstruction, unstable answers or positions with no
honest teaching prompt are quarantined.

## 1. What it is

Verified Puzzle Detector Engine turns ChessGuru's real games into dependable
teaching material through deterministic chess reasoning. It reconstructs each
position from its source game, proves the solution and acceptable alternatives,
uses the smartest verified detector available to explain the idea, and serves a
broader truthful lesson when a narrower concept is not yet proved. Runtime
behavior uses no LLM. Codex contributes offline chess reasoning to discover
detectors, author adversarial cases and perform a blinded independent review
after detector code is frozen. Existing analyzed games are never sent through
Stockfish again: their stored engine analysis is immutable consequence evidence,
while this project improves the detector layer that explains it.

## 2. What the user sees

There is no new detector dashboard. Existing training and personalized lessons
become more specific and more reliable.

When the exact concept is proved:

    PIECE SAFETY

    Your knight on d4 can be taken by the bishop on a7.
    Find a move that saves the knight or answers the attack.

When the position is valid but the exact human cause is not yet proved:

    CALCULATE THE RESPONSE

    Your opponent has a forcing reply here.
    Check their captures and checks before choosing your move.

When several moves work:

    Good. Your move solves the problem.
    Ne6 was the engine's first choice, but your move keeps the position safe.

Opening, trap and endgame lessons use the same proof contract:

    OPENING: DEVELOPMENT BEFORE ATTACK

    You moved your bishop for a second time while your king was still in the
    centre. Find a developing move that also prepares castling.

    TRAP: REMOVE THE f7 DEFENDER

    This is the Fried Liver move sequence, but the lesson is the mechanism:
    Black cannot safely defend both f7 and the pinned knight on d5.

    ENDGAME: TAKE THE OPPOSITION

    Move your king so one square remains between the kings and Black must move.
    The lesson is not considered applied merely because the final move matched;
    the detector must prove the relevant opening plan, tactical mechanism or
    endgame geometry.

The player never sees an internal detector ID, confidence score, quarantine
state, unsupported diagnosis or falsely unique answer. A broken position is
silently replaced with another verified position.

## 3. In scope

- One shared admission result used by community_puzzles,
  community_training_positions, skill puzzles, diagnostic puzzles and
  personalized lessons.
- Reconstruct every imported position from source PGN plus ply. Reconstruct
  Play with Coach positions from the canonical session move history. Stored
  FEN is evidence to compare, not truth to trust blindly.
- Verify board legality, side to move, played move, engine move, source
  ownership, move number and provenance before teaching.
- Consume the Stockfish facts already stored on every analyzed game: best move,
  evaluation change, centipawn loss and stored principal variations where
  available. Replaying the corpus must make zero new Stockfish analysis calls.
- Use stored continuations plus deterministic board and concept verification to
  establish the lesson and its supported answer set. If an older analysis lacks
  enough evidence for a narrow claim, keep the position broad or shadow it;
  never recompute the game merely to force a specific label.
- Use tablebases for supported endgames and canonical legal-exchange truth for
  material claims.
- Require each specific detector to return structured proof: concept ID,
  relevant pieces and squares, causal before/after facts, counterfactual
  evidence, acceptable moves, verifier version and provenance.
- Require an independent verifier for every detector family. A detector may
  propose a fact but may not verify itself using the same calculation.
- Consult detector_quality before a detector may name a lesson, grade concept
  application, affect mastery or enter a personal coaching plan.
- Replace keyword, prose and raw-centipawn concept inference with verified
  facts. Engine loss may establish consequence; it does not establish the
  human lesson by itself.
- Use a coverage ladder:
  - verified specific concept;
  - verified broader chess category;
  - verified generic calculation/threat exercise;
  - quarantine only when the position itself is unsafe or unteachable.
- Mine the production corpus for common target-player opportunities, missed
  concepts, near misses and adversarial negatives. Split by user, game and
  source unit so related positions cannot leak into held-out review.
- Improve canonical detectors in place for common tactical, material, king,
  pawn, opening, endgame and positional geometries. Do not add per-surface
  copies.
- The coach-grade detector-family map includes:
  - opening identity, repertoire coverage, principled development, king safety,
    central control, tempi, sound deviations, typical pawn structures and
    opening-to-middlegame plans;
  - named opening traps plus their underlying tactical mechanism, soundness,
    victim escape, setter punishment and move-order/transposition boundaries;
  - pawn endings, key squares, opposition, corresponding squares, shouldering,
    zugzwang, triangulation, breakthroughs and pawn races;
  - rook endings including Lucena, Philidor, active-rook principles, checking
    distance, cutting off the king and rook placement behind passed pawns;
  - basic mates, queen-versus-pawn, minor-piece endings, wrong-bishop rook-pawn
    cases, fortresses and stalemate resources where deterministic truth exists;
  - forks, pins, skewers, discovered and x-ray attacks, double attacks, removal
    of defender, overload, deflection, decoy, attraction, interference,
    clearance, zwischenzug, trapped pieces, back-rank and mating geometries;
  - hanging pieces, legal exchange sequences, unsound sacrifices, loose pieces,
    overloaded protection and defensive resources;
  - pawn weaknesses and breaks, weak squares, outposts, files, diagonals, colour
    complexes, space, piece activity, exchanges, prophylaxis and king zones;
  - calculation habits: candidate moves, checks/captures/threats, the opponent's
    forcing reply, move order, quiet defenses and completing the forcing line.
- Each named opening or trap is a curriculum view over the same canonical move
  history and geometry facts. Sequence recognition alone cannot prove that the
  player understood the chess mechanism.
- Log broad fallbacks and quarantines as an offline repair backlog. Cluster
  repeated geometries, improve the corresponding detector, rerun held-out
  gates and automatically upgrade old positions when the new detector proves
  them.
- Freeze every detector before independent Codex review. The review packet
  shows the reconstructed board, source move, engine/tablebase evidence and
  relevant continuations, but hides detector output, chosen label and
  confidence.
- Codex independently records whether the position is teachable, the best
  human lesson, relevant geometry, acceptable alternatives and false-case
  risks. Detector output is revealed only after that gold is sealed.
- Treat every detector/Codex disagreement as a failed release case until it is
  resolved by board truth, engine/tablebase evidence and recorded
  adjudication.
- Run adversarial review after the blind comparison: sound sacrifices, pinned
  attackers, x-ray recaptures, zwischenzugs, multiple winning moves,
  already-decided games, promotion races, forced moves and visually similar
  non-examples.
- Re-adjudicate existing records without deleting source games or learning
  history. Preserve old status and verifier versions for auditability.
- Reverify at serve time when a detector, engine or admission version changes;
  stale approval cannot silently survive a truth change.
- Provide aggregate operational reporting for coverage, broad fallbacks,
  quarantines, detector disagreements, repair rate and serving blocks.
- Keep all deployed move selection, detection, verification and grading
  deterministic and available without any LLM or external AI service.

## 4. Explicitly out of scope

- An LLM, Codex call or narrator deciding chess truth during production use.
- Changing Stockfish settings or rerunning Stockfish over existing analyzed
  games. This project improves detectors over trusted stored analysis.
- Treating Codex's offline opinion as a replacement for Stockfish, tablebases,
  legal board reconstruction or deterministic verifiers.
- Claiming mathematical perfection across every possible chess position.
- Achieving apparent accuracy by quarantining every difficult position.
- Forcing every valid puzzle into a narrow named concept.
- Training a black-box runtime classifier whose reason cannot be independently
  verified.
- Creating new puzzle collections when existing rows can be versioned and
  re-adjudicated.
- Rewriting the central caption pipeline, curriculum, focus picker or mastery
  model.
- Deleting original source games, attempts or historic detector evidence.
- Promoting every detector at once. Rare concepts without enough independent
  opportunities remain broad or shadow until adequate evidence exists.
- Using production-user games as the only generalization corpus. External
  public corpora, tablebases and constructed adversarial positions may validate
  claims without entering user coaching history.

## 5. Success criteria

- No puzzle can be served without a current admission verdict whose source,
  board, solution, label and verifier versions are traceable.
- Every served board and move reconstructs from its canonical source, or from a
  separately provenance-checked public/canonical lesson source.
- No specific lesson label reaches the player unless its detector and
  independent verifier both support the same concrete claim.
- Valid engine-stable positions are retained through the coverage ladder;
  quarantine is limited to genuinely unsafe or unteachable records.
- Specific-concept coverage and broad-fallback coverage are measured
  separately. The detector-improvement loop must increase specific truthful
  coverage on frozen data without lowering the locked accuracy gate.
- Every promoted detector has independent positives, opportunity-based
  negatives, hard adversarial controls, rating/phase strata and a held-out
  blind review.
- Frozen independent Codex review produces no unresolved false player-facing
  claim among release-eligible cases. Disagreements block the affected detector
  family, not the rest of training.
- Precision, recall, engine-stability, review-size and maximum acceptable
  fallback/quarantine rates are locked from measured distributions before
  implementation; no number is selected from intuition.
- Both production pools are re-adjudicated under the same contract, including
  all existing duplicate, conflicting and structurally invalid records.
- The same source game, stored analysis snapshot, detector version and verifier
  version produce the same admission and grading result.
- A complete replay of all existing analyzed games invokes zero Stockfish
  analysis calls. Future games consume the analysis already produced by the
  normal game-analysis pipeline; the detector engine never duplicates it.
- Runtime network tracing and tests prove that the complete lesson flow makes
  no LLM or Codex request.
- A reviewer can answer why a puzzle was admitted, what exact claim was proved,
  what alternatives are accepted and which evidence version authorized it.

## 6. Open questions

- **Question:** Which detector families enter the first repair batch?
  **Why unresolved:** frequency, false-label risk and available independent
  truth differ across the production corpus.
  **Unblocking step:** measure opportunity and current-label distributions,
  then rank families by player exposure and harm.

- **Question:** Which stored analysis fields are sufficient for a specific
  lesson versus a broader exercise?
  **Why unresolved:** older analysis versions do not all store the same best
  move, UCI and principal-variation fields.
  **Unblocking step:** measure field coverage by analysis version and detector
  family, then define deterministic evidence requirements without rerunning
  Stockfish.

- **Question:** What measured evidence authorizes specific, broad and generic
  publication?
  **Why unresolved:** tactical geometry, human attribution and rare endgames
  need different opportunity denominators.
  **Unblocking step:** use lock-via-data to compare candidate grade policies by
  detector family rather than choosing one universal threshold.

- **Question:** How large must each independent Codex review packet be?
  **Why unresolved:** common hanging-piece cases and rare Philidor cases have
  different available opportunities and confidence.
  **Unblocking step:** determine packet sizes from independent opportunity
  counts, source diversity and disagreement confidence intervals.

- **Question:** Which valid positions may become broad generic exercises?
  **Why unresolved:** a stable best move does not always create a useful lesson.
  **Unblocking step:** define deterministic teachability checks and audit their
  rejected/accepted boundary through blind coaching review.

- **Question:** How should historic attempts behave when a puzzle is relabeled
  or an answer set expands?
  **Why unresolved:** preserving earned learning evidence must not preserve a
  false concept attribution.
  **Unblocking step:** design an evidence migration that preserves the move
  attempt while versioning or withdrawing only the unsupported concept claim.

## 7. Pre-code requirements

- [x] Mohit explicitly signed off this complete scope on 2026-08-30, including
  the opening, trap, endgame and broader coach-grade detector families.
- [x] Version the aggregate production audit without positions, moves, user
  identifiers or credentials.
- [x] Complete the single-source inventory for every chess fact used by puzzle
  detectors and retire or adapt duplicate fact owners.
- [x] Define the shared admission result and all existing ingestion/serving
  chokepoints that must consume it.
- [x] Run lock-via-data for stored-evidence requirements, quality grades,
  evidence floors, review sizes and fallback/quarantine limits.
- [x] Freeze train, development and held-out source units before detector
  iteration begins.
- [x] Define the first detector-family repair batch from measured production
  exposure and risk.
- [x] Define the independent verifier for each first-batch detector and commit
  positive, negative and adversarial gold.
- [x] Define and freeze the blinded Codex review packet and adjudication
  protocol before showing Codex any detector output.
- [x] Prove the planned runtime path contains no LLM or Codex dependency.
- [x] Define the reversible backfill, versioning and rollback plan for both
  puzzle collections.
- [x] Make the relevant detector, extraction, grading and route gates runnable
  in CI.
- [x] Run audit-pre-code and pass all six gates immediately before the first
  production-code change.
