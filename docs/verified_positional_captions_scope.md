# Verified Positional Captions — Scope

## 0. Existing surfaces audit

ChessGuru already has the main pieces of this product, but they are not connected into one learning loop.

- The game review in `frontend/src/components/GameDecryptionV5.jsx` shows the move caption and, when available, the principle and board pattern behind it.
- Play with Coach shows move feedback through `frontend/src/components/coach-play/MoveFeedbackPanel.jsx`.
- The progress and mastery surfaces already tell a player which concepts they repeatedly miss and when they are improving.
- `backend/services/caption_pipeline.py` is the central caption path. It extracts board facts, chooses a teaching idea, renders the caption, and verifies its claims before the caption is shown.
- `backend/services/distilled_caption_service.py` already supports deterministic captions built from verified facts.
- `backend/services/pattern_event_logger.py` records concept encounters, while `backend/services/concept_mastery_tracker.py` turns encounters into a player-level understanding record. At the time of this audit, the database contained about 110,000 pattern events and 3,953 mastery records.
- The `/admin/positional-reasons` page and its backend route exist on `origin/working-code`, although they are absent from this checkout. The page collects a reason and an optional concept label, but those answers currently do not become caption rules, tracker events, or mastery evidence.
- The admin caption drafts and reason-judging surfaces already provide parts of an author-and-review workflow.
- ChessGuru currently has overlapping concept names in the caption-principle system and the pattern-event system. Adding another positional taxonomy would make the same teaching idea appear under several identities.

The overlap is substantial: ChessGuru already renders captions, records patterns, tracks mastery, and has an admin reason queue. The missing value is a trusted path from a reviewed positional example to a reusable concept, a verified caption, and an opportunity-conditioned mastery event.

**Decision: EXTEND existing.** V1 upgrades the existing admin queue, central caption pipeline, pattern-event ledger, and mastery projection. It does not create a separate caption service, tracker, concept catalog, or player page.

## 1. What it is

Verified Positional Captions teaches a 900–1500 player why one move was meaningfully better than another in a quiet or strategic position. Each caption points to concrete pieces and squares, explains what the played move failed to do, and ends with a lesson the player can use in a future game. ChessGuru only shows the specific explanation when the board evidence proves it; otherwise it gives a modest fallback or stays silent. The same verified teaching idea is also used to remember whether the player misses or applies that idea in later games.

## 2. What the user sees

The player continues to see coaching in the existing game-review and Play with Coach surfaces. The teaching idea is the headline; the moves are supporting evidence. A successful caption reads like this:

```text
CHOOSE THE PIECE WITH FEWER JOBS

Your a1 rook was already helping to defend the queenside, while the f1
rook had no job. Using the f1 rook keeps that defence and activates the
idle rook. Before moving a piece, ask which piece can do the new job
without abandoning an old one.

Played: 28.Rac1                 Better: 28.Rfc1
```

Another valid caption can be shorter when the position supports fewer claims:

```text
COMPARE EACH PIECE'S JOB

Trading this bishop gives up its pressure on h6 and its support for d4.
The knight was not threatening anything, so the trade helps your opponent.
Before trading pieces, compare the job each piece is doing.

Played: 18.Bg5                  Better: 18.Be3
```

This caption fails the product contract:

```text
Re8 was inaccurate. Rc8 was better because it improves your position.
```

It names the moves but does not identify the board change, explain why it matters, or teach a reusable decision.

The upgraded admin queue shows the reviewer enough evidence to decide whether a position should teach anything:

```text
Position 34
Played: Rac1             Better choice: Rfc1
Disposition: Eligible positional mistake
Teaching idea: Choose the rook with fewer current duties
Board proof: a1 rook defends a2; f1 rook has no defensive assignment
Contrast: Rfc1 preserves both jobs; Rac1 leaves the f1 rook idle
Status: Reviewed gold example
```

Positions marked `not a mistake`, `already decided`, `tactical or forced`, `duplicate`, `unstable engine choice`, or `insufficient evidence` do not create a positional caption or affect the player’s mastery.

## 3. In scope (V1)

- Give every item in the 240-position seed queue an explicit disposition instead of treating every engine difference as a teachable positional mistake.
- Preserve `not a mistake` and `already decided` as first-class outcomes so they can be measured and excluded from learning data.
- Require every accepted reason to distinguish the better move from the played move: the claimed advantage must be present for the better choice and absent or materially weaker after the played move.
- Attach board proof to every accepted reason, using pieces, squares, legal moves, engine variations, and resulting positions.
- Group reviewed examples under the existing canonical concept system. Resolve the current principle-ID and pattern-ID overlap instead of adding a third namespace.
- Use exact labels and board features as the primary grouping tools. Optional semantic similarity may suggest offline clusters or duplicates, but a reviewer must approve the concept and its examples.
- Promote a recurring teaching idea only after it has a deterministic detector, required evidence fields, hard negative examples, a caption frame, and an independent verifier.
- Generate the player-facing text through the existing central caption pipeline.
- Write captions for a 900–1500 reading level: plain language, named pieces and squares, no unexplained jargon, and a final rule that transfers to another position.
- Make each caption answer four questions when the evidence permits: what happened, why it mattered, what the better move accomplished, and what to check next time.
- Omit any sentence that cannot be proved from the stored evidence. Use a modest fallback when the complete teaching explanation cannot be verified.
- Record concept opportunities in the existing event ledger as `hit`, `miss`, or `unknown`, with the canonical concept ID and the evidence and rule versions used for the decision.
- Count a `hit` when the player chooses any verified acceptable solution, rather than requiring the engine’s single first choice.
- Treat `unknown` as neutral. It does not improve or reduce mastery.
- Keep the existing mastery record as a rebuildable summary of the event ledger.
- Keep reviewer-visible provenance and confidence based on proof coverage, detector status, verifier result, and review status rather than an unsupported model probability.
- Ship behind the existing caption rollout controls so new positional concepts can be evaluated before they replace safe fallback text.

## 4. Explicitly out of scope (V1)

- Runtime RAG, vector-database lookup, or semantic nearest-neighbour search for choosing the player-facing explanation.
- Allowing an LLM to invent the reason from a FEN or engine score during a player request.
- A new player-facing page for positional captions or mastery.
- A separate positional tracker, caption engine, or concept catalog.
- Automatically approving a concept because several written reasons sound similar.
- Guaranteeing a detailed positional caption for every legal engine preference.
- Solving every quiet-position concept in chess. V1 promotes only concepts supported by enough reviewed positive and hard negative examples.
- Reworking the existing tactical, opening, or endgame caption families except where canonical concept IDs must be reconciled.
- Personalized prose for separate ratings inside the 900–1500 band. V1 uses one plain teaching standard that remains useful across the band.
- Changing mastery thresholds based on intuition. Those numbers must be selected from the event distribution after the scope is signed off.

## 5. Success criteria

- On the held-out gold set, every specific board claim in a shipped positional caption is supported by the independent verifier. A concept with an unverified claim does not ship.
- At least 85% of held-out eligible positions receive a caption that independently passes both questions: “Does this explain why the better move is better here?” and “Does this teach something I can look for in another game?”
- In blind review by players or coaches judging for the 900–1500 band, at least 85% of shipped captions are rated understandable without needing a chess term explained.
- Every one of the 240 seed positions has an auditable disposition, including the 41 currently suspected to be `already decided` or `not a mistake`.
- Every mastery-changing event can be traced to one canonical concept, one eligible opportunity, one outcome, and the detector and verifier versions that produced it.
- `not a mistake`, `already decided`, and `unknown` events cause zero mastery movement in replay tests.
- After enough repeated opportunities exist, players who have previously received a verified lesson show a lower later miss rate for that same concept than on their first recorded opportunity. The required improvement and minimum sample size are locked from the baseline distribution before implementation.
- No new caption-emitting runtime path bypasses the central caption pipeline.

## 6. Open questions

- **Question:** Which existing concept ID becomes canonical when a caption principle and a tracked pattern describe the same lesson?
  **Why unresolved:** The current stores contain overlapping uppercase principle IDs, lowercase pattern IDs, and some older plan IDs.
  **Unblocking step:** Produce a crosswalk from live events, caption principles, and mastery records; choose one existing identity per concept and document migrations or adapters.

- **Question:** How many of the 240 positions remain eligible after the deterministic disposition pass?
  **Why unresolved:** The 41 positions identified so far are a useful estimate, but the full queue has not received the same engine-stability and teaching-value review.
  **Unblocking step:** Freeze the seed set, rerun it with one engine configuration, and publish the disposition counts and examples.

- **Question:** What evidence is sufficient to call a move an acceptable `hit` for a strategic concept?
  **Why unresolved:** Exact-best-move equality is too strict, while a loose evaluation tolerance could count moves that miss the lesson.
  **Unblocking step:** Compare top engine moves and resulting board-goal changes on the reviewed gold set, then lock the rule from the observed data.

- **Question:** How many clean opportunities should change a player from “working on this” to “showing improvement” or “mastered”?
  **Why unresolved:** The existing default clean-streak rule was not selected from this positional event distribution.
  **Unblocking step:** Run the threshold bake-off required by the data-locking workflow and replay candidate rules on historical events.

- **Question:** Which positional concepts have enough gold examples to ship in V1?
  **Why unresolved:** A frequent written label may still lack hard negatives or reliable board evidence.
  **Unblocking step:** Cluster the eligible queue offline, count reviewed positives and hard negatives per concept, and promote only the concepts that pass held-out verification and blind teaching review.

## 7. Pre-code requirements

- Mohit has explicitly signed off on this full scope document.
- The `/admin/positional-reasons` implementation from `origin/working-code` is reconciled with the current checkout without overwriting unrelated work.
- The 240-position seed set is frozen with engine name, engine version, search settings, move choices, variations, and evaluation evidence.
- The deterministic disposition rules have been written in plain language and tested against representative examples of every outcome.
- The concept-ID crosswalk is complete, and the existing canonical concept identity for every V1 concept is chosen.
- Every candidate V1 concept has reviewed positive examples, hard negatives, required evidence fields, and a clear contrast between the played and acceptable choices.
- Numeric choices for acceptable moves, detector promotion, caption coverage, and mastery updates have passed the data-locking workflow.
- The held-out evaluation set and blind-review questions are frozen before detector or template tuning.
- Safe fallback behaviour is defined for missing evidence, detector disagreement, verifier failure, and unstable engine choices.
- The rollout flag and replay plan are defined so existing captions can be compared with the new output before exposure.
- The pre-code audit has been run after all preceding requirements pass.
