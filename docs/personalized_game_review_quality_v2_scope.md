# Personalized Game Review Quality V2 — Product Scope

**Status:** LOCKED — original scope plus ten-game repair package approved by Mohit  
**Date:** 2026-09-01  
**Decision:** Extend the deployed Personalized Game Review Coach. Do not create another review page, coaching pipeline, detector authority, or chess-content store.

## 0. Existing surfaces audit

The existing `/game/:gameId` review already renders the board, legacy move captions, a personalized game plan, chapter navigation, reflection choices, board highlights and the private A/B validation panel. `GameDecryptionV5` and `PersonalizedReviewCoach` are therefore already the correct user surface.

The central caption pipeline already owns the move-level teaching decision. It knows the played move, best move, stored engine result, practical severity, detector provenance, arrows and highlighted squares. The review event adapter already turns that decision into a typed teachable event. The game-level planner already chooses a small number of moments. The reflection service already produces backend-owned options. The validation service already supports blinded human review. The detector-quality registry already decides which evidence may caption, plan or update mastery.

The production audit showed that these pieces can disagree. In the `Bh6` example, the detector and takeaway correctly identified the undefended rook on `a1`, but the caption described `Rd1` as an attack on the king, the board highlighted only `h6`, and the reflection choices omitted the likely intention of continuing the attack. The practical fields also showed that the player stayed overwhelmingly winning, while the review called the move a game-changing blunder. A second game showed that a stored schema-17 observation can disagree with the current schema-17 deriver.

The overlap is therefore almost complete. The genuine new value is a consistency contract: one verified cause must drive the caption, practical framing, board geometry, reflection choices and takeaway. The existing validation cohort then measures whether that coherent explanation beats the legacy review.

**Overlap decision: EXTEND existing.** No parallel product will be built. Quality V2 completes the already-locked Personalized Game Review scope and keeps the current route, components, feature flags, content sources and detector authorization.

## 1. What it is

Quality V2 makes each selected Game Review chapter sound like one coach looking at one position. The coach explains what actually happened, shows the exact relationship on the board, acknowledges whether the move changed the game or merely missed a cleaner finish, asks why the player chose it using plausible position-specific options, and ends with one lesson that follows from the same evidence. If those parts cannot agree, the chapter becomes narrower or stays silent.

## 2. What the user sees

For the audited production position, the review should read like this:

```text
YOU KEPT CONTROL — BUT LEFT ONE PIECE BEHIND

You were already winning and Bh6 did not throw the game away. But while
you continued the attack, your rook on a1 was still undefended. Their
knight on c2 could take it.

BEFORE I EXPLAIN  25. Bh6

What were you focused on when you played Bh6?

[ I was trying to continue the king attack ]
[ I did not notice the knight attacking my rook ]
[ I saw the rook was attacked, but expected my attack to come first ]
[ I thought the rook could not be taken ]
[ I wasn't sure ]
[ None of these ]

                 c2 ─────→ a1
                            │
                            └────→ d1
             amber: their threat   green: your safe move

WHAT ACTUALLY HAPPENED

Your attacking idea was real. The problem was the loose rook: the knight
on c2 attacked a1, and nothing defended your rook. Bh6 allowed ...Nxa1.
Rd1 moved the rook out of danger while keeping your winning position.

Before committing to your attack, check what their last move attacks.
```

When the engine score changes dramatically but the player remains clearly winning, the coach says “you missed a cleaner finish” or “you left material available,” not “the game turned here.” When the move truly changes a win to equality or a loss, the stronger turning-point language remains appropriate.

The review does not show arrows that it cannot verify, reflection options that are impossible in the position, recurrence language from one game, or a next action unsupported by the detector's evidence grade.

## 3. In scope (V1)

- Extend the current personalized review chapter; no new route or permanent parallel UI.
- Make the shared caption path truthful for every reviewed mistake/blunder, not only planner-selected `simple_hang` chapters. The first release gate is the fixed ten-game account corpus: 58 significant moves, 30 manually adjudicated highest-impact captions and all selected chapters.
- Extend the existing narrator verifier from lexical/one-ply checks to a deterministic multi-ply claim verifier that replays stored lines, values captures and recaptures, and validates named geometry, move purpose, checks, mates, attack counts and open-file claims.
- Create one canonical, typed cause package for every selected chapter, containing the observed failure, affected piece and square, verified attacker or tactical relationship, best-move purpose, practical state and claim provenance.
- Require the caption, chapter takeaway, reflection prompt, reflection options and board geometry to consume that same cause package.
- For `simple_hang`, name the hanging or threatened piece, its square, the attacking piece and the safe purpose of the best move when each fact is independently board-verifiable.
- Prevent a generic missed-mate or forcing-move explanation from replacing a verified piece-safety explanation merely because a mate score creates a very large centipawn loss.
- Use existing practical fields—state before and after, `stayed_winning`, decisiveness change and win-probability movement—to distinguish a missed cleaner finish from a real turning point.
- Generate verified geometry for the selected cause: threat arrow, affected square and safe-move arrow when legal and relevant. Each visible arrow must have a deterministic board proof.
- Add position-specific reflection choices for the played move's verified purposes, including attacking the king, creating a threat, winning material, developing, defending, responding to a threat and knowingly accepting risk when those options are possible.
- Keep “not sure” and “none of these.” A reflection answer remains self-report and never changes objective board truth.
- Add a consistency gate that fails closed when caption cause, practical framing, visual claim, reflection possibilities and takeaway do not refer to the same verified event.
- Store an exact deriver identity with observations and shadow plans so code changes cannot masquerade as the same evidence version. A mismatch triggers honest regeneration or silence.
- Build a versioned `simple_hang` quality corpus that includes stayed-winning moves, missed mates, genuine result changes, attacking intentions and conflicting engine-scale signals.
- Produce evidence packets for the next detector families with the greatest player-facing coverage. Promotion remains governed by the existing precision, recall, adversarial and authorization requirements; no detector is promoted by feature code.
- Adapt every already-authorized exact single-game cause into the shared review event graph. Existing Shadow opening, trap, endgame, tactical and positional sources remain invisible until their own promotion packet passes; exact canonical sources may be promoted only with independent proof and explicit detector-quality evidence.
- Add a detector-independent, Caption-only authorization for a fully replayed stored-line cause after the ten-game and expanded gold gates pass. It may explain one observed move; it may not name an unproved motif, claim recurrence, drive mastery or prescribe training.
- Attach canonical opening, trap, endgame, geometry and principle content by ID when the exact verified event supports it. Content enriches the concrete move explanation and can never overwrite it.
- Rank from the complete authorized event set, not the `simple_hang` subset. The fixed ten-game gold supplies the first importance labels; the final visible formula remains validation-only until the blinded expansion set confirms it.
- Keep the release inside the existing validation cohort until blinded human review passes. `CAUSAL_PERSONAL_CAPTIONS_ENABLED` remains independently reversible.
- Preserve legacy captions and responses for non-enrolled users and for events that do not satisfy the V2 consistency contract.

## 4. Explicitly out of scope (V1)

- A new Game Review page, a new generic coaching engine or a runtime LLM deciding chess truth.
- Hand-editing the legacy R12 cascade or authoring per-position overrides to force individual examples to read correctly.
- Promoting `simple_hang` to Plan-grade or allowing Caption-grade evidence to claim recurrence, prescribe training or update mastery.
- Automatically promoting missed mate, threat awareness, opening, trap, endgame or positional detectors without their evidence packets passing the existing quality gates. Building and evaluating those packets is in scope; bypassing them is not.
- Bulk-regenerating every historical review before the shadow and validation results are known.
- Replacing Stockfish, tablebases or deterministic legal-board verification with Maia, Otter or another human-likelihood model.
- Redesigning the entire Game Review layout; V1 improves the existing chapter content and board evidence.
- Free-text reflection, a question on every move, or pretending the system knows the player's intention before the player answers.
- A new concept, opening, trap, endgame, principle or reflection-option database that duplicates an existing canonical source.
- Changing mastery or personal-curriculum progression from these captions until the relevant detector has independent Mastery-grade evidence.

## 5. Success criteria

- Every visible V2 chess claim passes an independent board verifier. One false claim is a rollout blocker; unverifiable clauses abstain.
- The fixed ten-game acceptance set selects the human-adjudicated main lesson whenever an authorized verified cause exists, with zero critical false claims among all 58 significant captions and zero cross-surface cause mismatches.
- The eight concrete falsehoods documented in `personalized_game_review_ten_game_audit_2026_09_01.md` are rejected by shared verification tests, not by game-ID overrides.
- On the clean `simple_hang` reference corpus, the caption, practical framing, geometry, reflection choices and takeaway identify the same cause package for every selected chapter.
- The audited `Bh6` position explains the `c2` knight attacking the undefended rook on `a1`, shows the relevant relationship, offers the attacking-intention option and does not call `Rd1` a check or king attack.
- Stayed-winning positions are not narrated as though the game result changed. True state changes retain appropriately strong language.
- Blinded coaches can trace every visible claim to stored engine evidence, deterministic board facts and authorized detector provenance, with zero critical truth failures.
- Blinded validation rates V2 higher than legacy for moment choice, explanation clarity, personalization, reflection usefulness and story coherence. The numeric promotion threshold is locked from the first complete paired-validation distribution rather than chosen in this scope.
- Reflection choices produce useful diagnostic separation: position-specific intentions are selected often enough that “not sure” and “none of these” are not acting as a catch-all. The acceptable rate is locked from validation data.
- A deriver-code change cannot reuse an indistinguishable stored evidence identity. Reprocessing the same versioned input with the same deriver identity is deterministic.
- Non-enrolled accounts and unsupported events remain byte-compatible with the legacy public response.
- The longer-term product outcome remains reduced recurrence on comparable real-game opportunities after a completed lesson; V2 does not substitute review ratings for learning evidence.

## 6. Open questions

- **Question:** Which practical-state ranking formula should choose between a huge mate-score loss that stays winning and a smaller move that changes the game state?  
  **Why unresolved:** The ten-game review supplies initial labels but is one player's corpus; it cannot establish population validity.  
  **Unblocking step:** Implement candidate formulas behind validation mode, require exact agreement on the ten-game gold, then lock the visible winner from a blinded multi-player coach-labelled expansion set.

- **Question:** Which additional detector families should receive promotion packets first?  
  **Why unresolved:** User value depends on both detector quality and how often the family supplies a missing review lesson.  
  **Unblocking step:** Join detector grade, precision, recall, adversarial status and current-schema production coverage; rank candidates by honest reachable reviews, not detector count.

- **Question:** Which verified move purposes are sufficiently reliable to appear as reflection options?  
  **Why unresolved:** A legal attack or check can be present without being the player's actual intention, while omitting the obvious purpose forces “none of these.”  
  **Unblocking step:** Measure option validity and likely-purpose coverage on the coach-reviewed corpus; retain only board-possible options and let the player choose.

- **Question:** What exact deriver identity should invalidate stale observations?  
  **Why unresolved:** A schema number describes output shape but not code semantics, content dependencies or detector versions.  
  **Unblocking step:** Compare content hash, explicit semantic version and dependency-manifest approaches for reproducibility and deployment operability.

- **Question:** Which historical reviews should refresh after V2 ships?  
  **Why unresolved:** Lazy regeneration is safer, while a bounded backfill gives validators immediate coverage.  
  **Unblocking step:** Measure revisit frequency, eligible-review count and generation cost, then choose lazy refresh plus an explicit validation-account backfill if justified.

## 7. Pre-code requirements

- Mohit explicitly signed off the original scope and the complete ten-game repair package on 2026-09-01.
- Implementation uses a clean isolated worktree based on deployed commit `7bc99da4ee61542ca9050dc7b698368045d07835`; the stale, heavily dirty main worktree is not used for coding or verification.
- A separate technical spec identifies the existing source of truth for cause facts, captions, visuals, reflection options, practical severity, detector authorization and evidence identity. No duplicate recognizer or hardcoded concept table is introduced.
- The production `Bh6` packet and a representative stayed-winning/result-changing corpus are versioned as regression evidence without personal credentials or unnecessary account data.
- The `simple_hang` gold set is cleaned and independently board-verified before template comparison. Runtime claims target 100% verified truth; style match is measured only on a stable, sufficiently large clean sample.
- The moment-ranking bake-off measures candidate formulas before any new weighting or threshold is selected.
- The ten audited games are encoded as immutable gold fixtures before shared product behavior changes; no game-ID-specific runtime code is permitted.
- Reflection-option coverage and false-option rates are measured before locking which purpose options ship.
- Detector promotion candidates receive a coverage-and-quality matrix; existing authorization is never relaxed to satisfy this feature.
- Current legacy, A/B packet, no-plan and eligible-plan outputs are snapshotted before adapters change.
- The default-off flags, validation-only cohort, rollback path and automated critical-false-claim block remain operational.
- The pre-code audit passes all six gates after the technical spec and data locks are complete.
