# Personalized Game Review Quality V2 — Spec

**Status:** LOCKED v2 — ten-game repair package approved by Mohit.  
**Version:** v2 (2026-09-01).  
**Scope:** largest extension of the deployed Personalized Game Review path; multi-day to ship and validate.

---

## 1. The problem

The deployed review can combine individually valid subsystems into one false coaching story. In the approved production regression, `Bh6` leaves the rook on `a1` available to the knight on `c2`, and `Rd1` saves it. The current caption instead says `Rd1` is a forcing attack on the king; the board highlights only `h6`; the reflection omits “I was continuing the attack”; and the practical label ignores that the player stayed winning.

The production lock found the same structural risks beyond one move: 464 of 943 joined `simple_hang` events omit a board-possible attack intention, six use forcing/check language without a checking or capturing best move, and zero of 166,417 current-schema observations has an exact deriver identity.

The ten-game acceptance audit expanded the proof: only 3/10 games received a plan, the highest-practical-impact moment was selected in 0/10, all 58 significant moves lacked arrows, and the lexical verifier missed eight clear false claims in the top 30. The problem is not missing pages or missing chess engines. The missing unit is one verified cause contract that every existing review surface must obey, plus complete authorized event admission so the planner can compare the game's real lessons.

## 2. The shape — four outcomes

| State | V2 result |
|---|---|
| Cause and best purpose both verified | Headline, practical lead, exact cause, best-move purpose, two-color geometry, contextual reflection and cue all render. |
| Cause verified; best purpose unproved | Exact cause, practical lead, threat geometry and reflection render; the best move is named without an invented “why.” |
| Detector fires; V2 cause fails | V2 projection abstains. The unchanged legacy personalized chapter remains available. |
| V2 flag off / account not enrolled | Public response is byte-compatible with the deployed legacy/personalized response. |

For `Bh6`, the projected chapter is:

```text
You kept control — but left one piece behind

You were already winning and Bh6 did not throw the game away. But while
you continued the attack, your rook on a1 was still undefended. Their
knight on c2 could take it with Nxa1. Rd1 moved the rook out of danger.

Before committing to your attack, check what their last move attacks.
```

The reflection appears before reveal. The threat arrow is amber; the saving move is green. No numeric evaluation or win-probability statistic is shown.

## 3. Schema / files touched

No new route, collection, detector registry or coaching page is added.

- `backend/services/caption_facts.py`: extend the canonical extractor with verified played/best move effects and exact relationship facts. Reuse existing recognizers; do not create parallel opening, trap, endgame or tactic tables.
- `backend/services/narrator_claim_verifier.py`: become the shared multi-ply text-claim boundary. Replay stored lines; validate net exchanges, recaptures, named purpose, checks/mates, attack counts, files and geometry. Board construction or claim parsing failure returns unverified, never clean.
- `backend/services/caption_pipeline.py`: add immutable `TeachingCause` / `PieceOnSquare` / purpose enums to `MoveTeachingDecision`. Populate a material-safety cause candidate from canonical facts. No review wording is rendered here.
- `backend/services/game_review_contracts.py`: add an optional V2 cause reference, practical frame, headline and arrow roles. V1 events remain valid; V2 fields are additive and strictly validated.
- `backend/services/game_review_event_adapter.py`: become the sole cause-to-review projector. For Caption-authorized `simple_hang`, render caption, principle and visual from the typed cause; otherwise preserve current behavior. Add the consistency gate.
- `backend/services/game_review_shadow_runtime.py`: adapt all Caption-authorized exact causes, attach practical fields and deriver identity, and compute validation-only ranking candidate metadata over the complete candidate set.
- `backend/services/game_review_planner.py`: consume the event’s projected principle for the takeaway. Do not independently reinterpret the position or add Plan-grade claims.
- `backend/quick_tag_registry.py`: extend the canonical option engine to accept verified purpose/cause context and produce contextual labels on existing stable option IDs.
- `backend/services/review_reflection_service.py`: pass the stored cause package to the canonical quick-tag engine; never parse caption prose.
- `backend/services/move_observation_deriver.py`: store `deriver_identity = {semantic_version, manifest_sha256, dependencies}` on regenerated observations.
- `backend/services/detector_quality.py`: remain the sole authorization owner. Add no player authority until a versioned promotion packet passes; a generic verified-line identity is Caption-only and cannot drive recurrence, mastery or prescription.
- `backend/services/canonical_curriculum_puzzle_proof.py` plus canonical content services: supply exact opening/trap/endgame references without copying their data into Review.
- `backend/services/game_decryption_v5_service.py`: persist the typed event/cause, bump `V5_COACHING_VERSION` once tests and snapshots pass, and leave historical refresh lazy except for the validation account.
- `backend/services/game_review_event_adapter.py` API projection: reject V2 events whose cause, visual, reflection or takeaway fingerprints disagree.
- `frontend/src/components/review/PersonalizedReviewCoach.jsx`: render `teaching.headline`, practical lead and role-colored relationship arrows. It performs no chess inference.
- `frontend/src/components/GameDecryptionV5.jsx`: map stored arrow roles to board colors and preserve the existing board/navigation path.

Contract additions:

```text
TeachingCause
  schema_version                 personalized_review.cause.v1
  kind                           legal_material_loss
  affected                       {piece, square}
  attacker                       {piece, square}
  punishment_san                 legal winning capture
  material_loss_cp               proof metadata; not rendered
  played_purposes[]              verified enum values
  best_move_san
  best_move_purpose?             moves_affected_piece | removes_attacker | adds_defender
  proof                          {authority, version}

PracticalFrame
  kind                           stayed_winning | state_changed | material_missed | neutral
  headline
  lead
  source                         stored practical booleans; no UI numbers

VerifiedLineCause
  played_line[]                  legal replay after the played move
  best_line[]                    legal replay after the best move
  exchange_ledger[]              captures, captured values and legal recaptures
  net_material_delta_cp          proof metadata; never narrated as engine loss
  relationship_claims[]          typed attack/defend/pin/fork/file/check/mate facts
  content_refs[]                 canonical IDs only; never copied lesson prose
```

## 4. New facts / data the system needs

No new engine analysis is required. The source hierarchy is locked as follows:

1. Stockfish’s stored move/evaluation/PV data remains engine truth.
2. `caption_facts.legally_hanging_pieces` remains legal-exchange truth.
3. `caption_facts.extract_facts` owns board geometry and played/best move effects.
4. `MoveTeachingDecision.cause` is the one typed cause candidate read by Review and available to PWC.
5. `detector_quality` alone decides whether that candidate may caption.
6. `game_review_event_adapter` is the one Review wording/visual projection.
7. `quick_tag_registry` is the one reflection-option authority.
8. `caption_principles.TAC_HANGING_PIECE` remains the lesson source; one contextual attack variant may be added there, not in the frontend.
9. `canonical_curriculum_puzzle_proof` and its existing content services own exact opening/trap/endgame matches.
10. `narrator_claim_verifier` owns the final concrete-language verification; `final_verified` is false when a supported claim cannot be proved.

The versioned data lock proves 913 clean legal-exchange causes (96.82% of joined events). The approved `Bh6` packet plus stayed-winning, state-changing, missing-purpose, invalid-move and no-hang negatives become the regression corpus. Personal IDs and credentials are excluded.

Deriver identity uses a canonical JSON manifest containing the semantic version and SHA-256 hashes of the observation deriver plus the material-safety and opponent-threat dependencies. Its SHA-256 is the cache identity. It is cached per process, not recomputed per move.

## 5. Gating — preventing the “five different coaches” trap

`validate_event_consistency(event, prompt)` blocks the V2 projection unless:

- the quality ID is Caption-authorized and the cause proof is verified;
- the named piece/squares exist with the claimed colors on the correct board;
- the punishment is a legal capture with the stored legal-exchange gain;
- every visual arrow is an exact relationship in the cause;
- every non-escape reflection option maps to a verified cause or played purpose;
- headline/lead use practical-state fields, never raw `cp_loss` alone;
- takeaway references the same cause/principle and does not imply recurrence;
- the event carries the current deriver manifest identity;
- the final narrator verifier accepts the rendered caption.
- the selected concept, caption cause, principle, reflection options, arrows and plan role share the same cause fingerprint;
- any opening/trap/endgame enrichment references an exact canonical proof authorized by `detector_quality` and cannot replace the move consequence.

Failure is per-event and recoverable: omit V2 fields and keep the existing response. It never disables the whole game review.

## 6. Test strategy

1. **Stateless probe:** legal-board tests for cause extraction, best-purpose proof, move-purpose facts, practical frames and `Bh6`. Include pinned attackers, x-rays, recaptures, multiple hanging pieces, already-loose pieces, a saving move that still loses material, and malformed SAN.
2. **Boundary suite:** contract tests prove caption/cause/visual/reflection/takeaway consistency; authorization and deriver mismatches fail closed; no purpose means narrower text rather than no chapter.
3. **Snapshot and corpus:** encode the ten games as immutable gold fixtures, reject all eight documented false claim families, rerun the 913-event clean corpus with zero false structured claims, compare flag-off API snapshots byte-for-byte and preserve Phase 6 A/B packet blinding.
4. **Frontend:** component tests for headline, reflection-before-reveal, contextual option labels, amber threat arrow, green saving arrow, missing-purpose fallback and legacy isolation.
5. **Integration:** regenerate only the approved account’s reference games at the new V5 version, test the real endpoints and submit/reread one temporary reflection with cleanup.
6. **Human gate:** candidate ranking first matches the ten-game labels, then Mohit and the two coaches judge the 13 existing ranking-disagreement games plus a blinded multi-player expansion set. One critical chess falsehood blocks rollout.

## 7. Risk + rollback

Blast radius is limited to enrolled Personalized Game Review accounts. `PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED` defaults false and is subordinate to the existing master flag and validation enrollment.

Risks are excessive abstention, wrong affected-piece selection when several pieces hang, plausible-but-misleading reflection options, stale V5 payloads and frontend arrow-role mismatch. Corpus coverage, exact proof ordering, escape options, version identity and contract tests address them.

Rollback: set `PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED=false` and restart the backend. Projection immediately rejects stored V2 events and plans. The next enrolled-account read detects the V2 formula mismatch, clears the stale caption/plan pair together and regenerates the V1 plan lazily. No database restore is required; the brief regeneration state is explicit rather than serving a mixed-version review.

## 8. What this spec does NOT cover

- Promoting any Shadow detector, changing mastery, or prescribing a plan from Caption-grade evidence.
- Changing an unverified Shadow detector into a visible claim without a passing promotion packet.
- Runtime LLM chess reasoning, Maia/Otter, new Stockfish runs or bulk historical regeneration.
- Approximate opening, trap, endgame or positional claims without exact evidence. Building and promoting evidence packets is part of the implementation, but unsupported families remain shadow.
- A free-text reflection system or inferred player intention.
- A Game Review layout redesign beyond rendering the new headline/practical lead/relationship colors.

## 9. Implementation order

1. Ship docs and measurement artifacts; no behavior change.
2. Encode the ten-game cause/importance gold and add failing shared-verifier, selection and consistency tests.
3. Add canonical multi-ply cause facts, typed contracts, claim verification and deriver identity; flag remains false.
4. Add authorized event adapters, cause-based Review projection, practical framing, contextual reflection and consistency gate; retain V1 output alongside it internally.
5. Add exact canonical content references and frontend rendering with full flag-off/validation snapshot tests.
6. Bump V5, regenerate the approved validation account only, and run production API/board verification.
7. Ship default-off. Mohit + two coaches run blinded A/B for one week.
8. If zero critical truth failures and paired validation wins, roll out to 10% for one week.
9. Roll out to 100%; monitor abstention, reflection escape choices and recurrence outcomes.
10. Delete the V1 projection only after two clean weeks at 100%; keep canonical cause contracts.

No implementation commit is bundled with this spec. Claude remains the commit/push/deployment owner after Codex completes and verifies the working tree.

## 10. Decisions / Open questions for Mohit

Approved decisions for implementation:

1. **Ranking:** keep deployed visible ranking for V1 and send the practical candidate only into blinded validation. Recommended: yes; the corpus has no independent importance labels.
2. **Refresh:** lazy-refresh historical games, plus an explicit bounded backfill for the validation account. Recommended: yes; avoid a 13k-game regeneration before validation.
3. **Purpose wording:** reuse stable quick-tag IDs but allow cause-specific labels such as “I was trying to continue the king attack.” Recommended: yes; IDs remain analytically stable while the words become truthful to the position.
4. **Cause failure:** fall back to the existing personalized/legacy chapter for that event rather than removing the whole review. Recommended: yes; this preserves useful content while V2 remains strict.
5. **Arrow roles:** extend the existing visual contract with `threat` and `safe_move` roles rather than create a second board overlay. Recommended: yes.
