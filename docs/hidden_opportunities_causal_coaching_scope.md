# Hidden Opportunities Causal Coaching — Product Scope

**Status:** LOCKED — Mohit approved implementation on 2026-09-03  
**Date:** 2026-09-03  
**Program position:** Complete Coaching System, Phase 3A — the first required slice of chess-intelligence breadth

## 0. Existing surfaces audit

The canonical `/game/:gameId` experience already contains the correct home for this work. `GameDecryptionV5` provides the replay board and move navigation. `PersonalizedReviewCoach` already presents a small number of chapters, asks a pre-reveal reflection question, labels missed opportunities, explains what happened, preserves a lesson, and can draw verified relationships on the board. The central caption pipeline already owns move-level chess teaching, `VerifiedLineCause` already replays stored played and better continuations, `TeachableEvent` already projects verified evidence into Game Review, and the planner already chooses a limited number of moments.

Puzzle admission and attempt grading already own whether a training position is safe and whether the player's answer was correct. The learner evidence system already owns guided practice, independent attempts, later-game application, and retention. Those systems may consume a proved opportunity later; they must not become another chess-fact authority.

The overlap is substantial: the product can already show a better line, a short caption, a principle, and arrows. The genuine missing value is causal chess understanding. The current safe cause package recognizes only a narrow set of mate, exchange, and material outcomes. The legacy PV tactical analyzer often finds a true detail in the better line without proving that the detail distinguishes it from the played line. The current planner ranks content completeness, criticality, and engine loss; it does not know whether a position contains a memorable fork, clearance, decoy, move-order idea, promotion geometry, or other proved mechanism.

**Overlap decision: EXTEND existing and REPLACE legacy narration.** Hidden Opportunities will deepen the canonical Game Review evidence path and existing personalized chapter. It will not add a new review page, chess-fact service, content store, planner, or mastery system. The legacy PV tactical analyzer will stop being a player-facing narrator as equivalent verified coverage becomes available.

## 1. What it is

Hidden Opportunities makes ChessGuru stop at the few positions in a player's game where something memorable could have happened. Instead of showing an engine move or merely saying that material was available, the coach lets the player look first, then demonstrates the short alternative and explains why it worked: what the first move changed, what reply it forced or restricted, and what became possible next. The explanation is built only from legally replayed evidence and compared against what the player actually chose. If the complete idea cannot be proved, the coach gives a narrower factual caption or says nothing.

## 2. What the user sees

The opportunity appears inside the existing Game Review story at the exact position:

```text
THE CHECK THAT BUYS YOU A MOVE

You played Rxd8 immediately. Before I show you the game, what would you try?

                         [ interactive board ]

                    [ Play a move ]   [ Give me a hint ]

Hint: Can you make the king answer you before taking the bishop?

You found it: f5+!

The pawn move checks the king and clears your rook's line. Black must answer
the check, so the bishop cannot escape. Then Rxd8 wins it. Taking immediately
missed the extra tempo.

                 f5+  →  king must respond  →  Rxd8

WHAT MADE THIS WORK?

[ The check gave me an extra move ]
[ The pawn was undefended ]
[ My rook attacked two pieces ]
[ I am not sure yet ]

REMEMBER
Before taking back, look for a check that improves the recapture.

[ Replay the idea ]                         [ Continue the game ]
```

The board animates only through the proved payoff. It names pieces, squares, checks, lines, and constrained replies before introducing an optional motif label such as “in-between move.” If several engine moves are sound but only one has a clear teachable mechanism, the coach may prefer that move only after soundness and the mechanism are separately proved.

An ordinary correction remains ordinary:

```text
Nf3 was safer because it defended the bishop. I do not have enough evidence
to call this a combination, so I will not turn it into one.
```

An evidence-insufficient position receives no invented opportunity card.

## 3. In scope (V1)

- Make this the first required subphase of Complete Coaching System Phase 3; breadth work cannot bypass it by merely increasing detector count.
- Reuse the canonical `VerifiedLineCause → TeachableEvent → PersonalizedReviewCoach` path.
- Replay and record both the played continuation and the stored better continuation as typed board events: captures, exchanges, checks, legal replies, mates, promotions, attacks, defenders, mobility changes, and opened or closed lines.
- Permit a causal claim only when the useful fact occurs in the better branch, is absent or materially weaker in the played branch, reaches a concrete payoff or result-preserving defense, and is visible within the stored evidence horizon.
- Represent each full opportunity as a proved chain: setup event → forced response or constrained choice → payoff event.
- Support composable proof primitives for loose-target captures; forks; pins, skewers and x-rays with payoff; discovered attacks and clearance; removal, overload and deflection of defenders; zwischenzugs; decoys and attraction; trapped-piece mobility; promotion races and promotion stops; correct-piece geometry; key-square and opposition play; back-rank patterns and mating nets.
- Keep product-friendly wording separate from proof. A renderer may call a proved decoy “using the rook as bait,” but prose cannot create the decoy fact.
- Lead every opportunity with the proved pattern, geometry, or positional idea—not SAN and not a generic “something beautiful” headline.
- Produce one of exactly three surface grades: Opportunity, Caption, or Evidence insufficient.
- Let the player try the first move, request a square-based hint, replay the proved line, and answer one backend-owned recognition question.
- Keep assistance visible in learning evidence. A hinted or revealed answer cannot count as an independent solve.
- Hand a proved opportunity to existing puzzle, curriculum, and mastery adapters only through their existing admission and authorization contracts.
- Rank opportunity moments only after truth is established. Ranking candidates will consider causal completeness, forcing nature, concrete payoff, conceptual clarity, novelty for this player, recurrence, and whether the idea is appropriate for the player's demonstrated knowledge.
- Use the locked anonymized 100-position packet for architecture and regression work. Use stored Stockfish continuations only; do not rerun Stockfish on analyzed games.
- Preserve every existing Stage 1 mate-direction correction and require the branch-owned final verifier for all visible claims.
- Add no runtime LLM chess authority. Maia or Otter may later rank human findability among already-safe moves; neither may establish correctness or widen the safe set.
- Keep the entire phase default-off until independent chess review and the existing validation cohort gates pass.

### Inherited work — mandatory non-regression contract

Phase 3A is additive. It starts from the work below and may extend its contracts; it may not silently fork, bypass, overwrite, or forget them.

| Earlier work | What Phase 3A inherits | Required disposition |
| --- | --- | --- |
| Personalized Game Review Phases 1–6 | Typed review contracts, canonical event adapter, backend-owned reflection, shadow planner, learning adapter, personalized frontend chapter and blinded validation harness | **KEEP AND EXTEND.** Hidden Opportunities becomes another verified chapter capability inside this flow. |
| Personalized Game Review Quality V2 | One-cause consistency across caption, practical framing, board geometry, reflection and takeaway; stayed-winning versus true-turning-point language | **KEEP AS A HARD GATE.** A beautiful line may not break cause consistency or exaggerate importance. |
| Stage 1 branch-owned mate truth | Separate played/better mate results, mover-relative transition, independent rendered-claim verifier and repaired mate captions | **KEEP AS THE FIRST REGRESSION FAMILY.** Phase 3A generalizes branch ownership; it does not replace the mate fix. |
| Full-game chess-fact audit | The 80-game/5,931-ply evidence, caption failures, classification findings and clean-base comparison | **KEEP AS BROAD REGRESSION EVIDENCE.** New mechanisms must not reintroduce actor, direction, material or mate failures. |
| Hidden Opportunities 100-position blind gold | Legal stored branches, human dispositions, mechanism annotations, current-runtime comparison and known failure families | **LOCK AND REUSE.** It is the first architecture packet and permanent regression suite, not disposable research. |
| Complete Coaching System Phases 0–2 | Canonical concept identity, verified claim set, authorization boundaries, LessonResult v2, one evidence ledger and shadow learner projection | **CONSUME, NEVER DUPLICATE.** Phase 3A emits through these contracts rather than creating another profile or mastery store. |
| Personal curriculum and Home Replay Diagnostic | One current focus, guided-versus-independent evidence, later-game application and the existing recognition experience | **KEEP.** A review opportunity may supply learning evidence and a later Home checkpoint; it cannot declare the lesson learned by itself. |
| Openings, traps, endgames, principles and skill tree | Canonical content IDs, explanations and prerequisites already authored and validated | **REFERENCE BY ID.** Phase 3A may attach matching knowledge only after the position fact is proved; it may not copy or shrink the catalogs. |
| Puzzle admission and attempt evidence | Fail-closed answer verification, provenance, assistance tracking and quarantine rules | **KEEP AS PUZZLE AUTHORITY.** A proved review opportunity is only a candidate until puzzle admission independently approves it. |
| Exact endgame and human-policy work | Fathom/Syzygy as exact covered-endgame truth; Otter/Maia as subordinate human-likelihood evidence | **KEEP THE AUTHORITY BOUNDARY.** Exact truth may prove an endgame; human models may rank only already-safe choices. |
| Existing useful captions and legacy review behavior | Working fallback for unsupported events and non-enrolled users | **PRESERVE UNTIL VERIFIED PARITY.** Retire a legacy path only after its replacement covers the same useful behavior with equal or stronger proof. |

If a Phase 3A change cannot identify which row it extends and which regression proves preservation, it does not enter implementation.

The implementation sequence inside this phase is:

1. **Phase 3A.1 — Differential evidence:** build and independently verify the two branch traces and their differences.
2. **Phase 3A.2 — Causal proof families:** implement and promote mechanism families against blinded gold and adversarial false friends.
3. **Phase 3A.3 — Coaching-moment selection:** rank only proved opportunities and compare the selected moments with human labels.
4. **Phase 3A.4 — Canonical review interaction:** add try, hint, replay, recognition, and continue states to the existing personalized chapter.
5. **Phase 3A.5 — Learning-loop handoff:** send assisted and independent results through existing lesson and mastery contracts, then look for the same decision in later games.

## 4. Explicitly out of scope (V1)

- A separate Hidden Opportunities route, dashboard, review engine, fact database, player model, or mastery score.
- Showing an opportunity merely because Stockfish's evaluation changed or a named geometric relationship exists on the board.
- Generating one opportunity for every mistake, padding a game to a fixed number, or treating silence as a product failure.
- Claiming a motif when only the material transaction is proved.
- Exploring unlimited branches, running Stockfish again on historical analyzed games, or inventing continuations beyond stored evidence.
- Letting Maia, Otter, an LLM, caption prose, or user reflection override legal-board and stored-engine truth.
- Treating a correct guided answer as mastery, or ending the lesson after two assisted puzzles.
- Automatically changing the player's durable weakness, curriculum, or mastery state from one review moment.
- Promoting a whole detector family because several showcase positions look good.
- Free-text reflection, a motif quiz on every move, or a large Game Review redesign.
- Community-authored explanations, reputation, moderation, and human-coach marketplace mechanics; those require a separate trust and safety scope.
- Complete coverage of every positional chess idea in V1. Unsupported mechanisms remain Caption-grade or silent until independently proved.

## 5. Success criteria

- Every Opportunity-grade statement is reproducible from the stored position and continuations, survives independent legal replay, and contains a complete setup → constraint → payoff proof. One false chess claim blocks promotion.
- The played-branch comparison is substantive: the surfaced mechanism must explain why the candidate teaches something the player's move did not achieve.
- The locked 100-position packet remains deterministic and becomes a regression suite. The known king-as-falling-target output, incidental-pin explanations, same-payoff-in-both-branches explanations, promotion-race compression, and runtime crash are all rejected by shared rules rather than position IDs.
- Selection precision, mechanism precision, wording quality, and opportunity recall are measured separately. No strong recall number may hide weak precision.
- A mechanism family reaches Opportunity-grade only after its own reviewed positives, true negatives, false friends, horizon failures, and branch-comparison cases pass the existing promotion discipline.
- On positions graded Caption, the ordinary correction remains useful and makes no cinematic or causal claim it cannot prove. Evidence-insufficient positions stay silent.
- Blinded human review prefers the selected opportunity and explanation over the current review for chess truth, importance, clarity, memorability, and teaching value. Numeric promotion thresholds are locked from the completed validation distribution, not invented in advance.
- Players can attempt before reveal, understand the demonstrated line, answer what made it work, and replay it without the interface exposing the answer prematurely.
- Assistance, independent recognition, later transfer, and comparable real-game application remain distinct evidence. The product never tells a player that the lesson is learned solely because the demonstration was completed.
- Flag-off API responses and non-enrolled user behavior remain compatible with the existing product.

## 6. Open questions

- **Question:** Which proof families earn Opportunity-grade first?
  **Why unresolved:** The 100-position audit demonstrates breadth but is deliberately stratified and too small to set population priority.
  **Unblocking step:** Join blind-gold correctness, adversarial pass rate, distinct-position coverage, evidence-horizon sufficiency, and player relevance; lock the order from those measurements.

- **Question:** What exact evidence thresholds promote a proof family from Caption to Opportunity?
  **Why unresolved:** Existing detector-quality thresholds are a starting discipline, but causal-chain failures and selection errors are different failure modes.
  **Unblocking step:** Run candidate gates across the locked gold, adversarial false friends, and a separate blinded holdout; choose the gate that permits zero critical false claims without collapsing useful coverage.

- **Question:** How should several proved opportunities in one game be ranked?
  **Why unresolved:** Centipawn loss and generic criticality do not measure memorability or teaching value.
  **Unblocking step:** Compare predeclared ranking formulas against blinded coach labels. Do not hand-pick weights.

- **Question:** How much line depth is sufficient for future games?
  **Why unresolved:** Four stored plies were insufficient for 41 of the 100 audited positions, while unbounded analysis would add cost and complexity.
  **Unblocking step:** Measure proof completion at candidate stored horizons on future analysis jobs; change the normal analysis envelope only after the marginal coverage curve is known.

- **Question:** When may human findability influence the selected move?
  **Why unresolved:** A sound, beautiful engine line can still be unrealistic for the player's level, but human-likelihood models are not chess-truth authorities.
  **Unblocking step:** Shadow-rank already-verified candidate moves with Maia/Otter and compare with coach judgments before any visible use.

- **Question:** What validation distribution is sufficient for visible rollout?
  **Why unresolved:** The initial packet is an architecture sample, not a production incidence estimate, and the current validation cohort is intentionally small.
  **Unblocking step:** Collect the first complete paired human-review distribution, then lock promotion and rollback thresholds through the data-lock process.

## 7. Pre-code requirements

- Mohit explicitly signed off this full scope and confirmed implementation should proceed on 2026-09-03.
- The existing 100-position gold packet, annotations, runtime comparison, full-game audit, and Stage 1 mate validation artifacts are immutable or fingerprinted before implementation changes their consumers.
- The canonical ownership map is enforced: `caption_facts` owns verified branch causes, Game Review contracts own projection, the existing planner owns selection, puzzle admission owns answer safety, and the learner ledger owns mastery evidence.
- A data lock selects the initial proof-family order, promotion measurements, candidate moment-ranking formulas, and any numeric thresholds. No value is chosen from intuition.
- The pre-code audit confirms schema-first contracts, the exact move-led player narrative, instrumentation before visible validation, forecasted bottlenecks, and all deferred work.
- Existing Game Review, personalized-review, caption, puzzle-admission, lesson-result, mastery, flag-off, and A/B packet fixtures are snapshotted before runtime behavior changes.
- Every new proof primitive has positive, true-negative, adversarial false-friend, incomplete-horizon, played-and-best-same-payoff, legal-alternative, and branch-reversal cases before it becomes visible.
- The UI contract is tested for answer hiding, legal board interaction, hint accounting, replay accuracy, accessibility, mobile layout, and exact event identity.
- The implementation remains in the isolated worktree. No production mutation, historical Stockfish rerun, broad regeneration, commit, push, or deployment is authorized by this scope.
