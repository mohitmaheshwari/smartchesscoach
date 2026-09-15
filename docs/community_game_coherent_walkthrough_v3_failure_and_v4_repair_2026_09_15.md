# Community Game Coherent Walkthrough — v3 Failure and v4 Repair

**Date:** 2026-09-15

**State:** repair implemented; independent terminal evidence pending; runtime exposure remains none

**Owner boundary:** Codex builds and verifies. Claude independently reviews, pushes and deploys.

## 1. Frozen failed evidence

The v3 review is preserved rather than edited or regenerated:

- source packet: `backend/data/detector_gold/community_game_study_neutral_review_v3.json`
- source SHA-256: `67454bad5f352c6420ff515ba5df3ade51016a748e1db7ea0286e89576abe0ed`
- reviewed packet: `backend/data/detector_gold/community_game_study_neutral_review_v3.reviewed.json`
- reviewed SHA-256: `8b0090e7b9b55fc010f8e5cb612cb31ac163326a6fc79239512777ebc99fcf8a`
- reviewer: Claude Opus 5, independent

The review passed factual precision, legal demonstrations, headline style,
principle de-duplication and teachability. It failed the two product gates:

| Gate | Result | Required |
| --- | ---: | ---: |
| coherent whole-game story | 2/32 = 6.2% | strictly above 9.8% |
| assignment-worthy study | 10/32 = 31.2% | strictly above 48.8% |

No threshold is lowered. The reviewed verdicts are not edited. The v3 packet
cannot be admitted.

## 2. Root causes accepted

The reviewer found two implementation defects rather than a chess-truth
failure:

1. All 64 selected chapters used only `setup`, `turning_point` and
   `consequence`; none used the existing `finish` role. Fifteen games ended in
   checkmate, twelve of those finishes were uncovered, and every study had
   exactly two chapters.
2. Every proof-supporting prediction answer occupied option index zero. The
   interaction therefore rewarded always choosing the first button and did not
   measure recognition. The `better_line` wording also exposed the target
   square and offered bare SAN choices.

The planner already reserved an admitted terminal event. The missing wire was
an authorized terminal fact. It is not valid to set `terminal=True` on an
unrelated detector or to treat a played checkmate as the existing
`tactic:forced_mate_exact` family, which proves a different claim.

## 3. Repair architecture

### 3.1 Exact played-checkmate fact

`ExactTerminalFact` is now the sole typed fact for a played move that leaves
the opposing king checkmated. It is reconstructed from the exact FEN and legal
move using python-chess. It requires all of the following:

- the move is legal;
- the resulting position is check;
- the checked king exists;
- the opposing side has zero legal replies;
- at least one checking piece exists;
- proof authority and proof version are exact and immutable;
- serialized evidence matches its SHA-256 fingerprint.

It claims only the terminal board state. It does not claim that mate was
forced earlier, that another defense also loses, or that a player has learned
the idea.

The central renderer produces one pattern-led chapter:

- headline: `The king has no legal reply`
- board explanation naming the checked king's square;
- the three defenses to test: move the king, take the checking piece, or block;
- one legal demonstration beginning with the played move;
- one position-specific prediction and bounded hint.

The fact is registered as `review:exact_terminal_checkmate` at **Shadow**.
The runtime adapter returns no event at all until this exact quality id earns
Caption authorization. A test-only registry substitution proves the future
promoted event reaches the planner with `terminal=True` and without a false
mistake frame; the production registry remains unchanged.

### 3.2 Blinded Caption-promotion evidence

The separate packet is frozen at:

- review packet: `backend/data/detector_gold/exact_terminal_checkmate_caption_review_v1.json`
- packet SHA-256: `ce4a47e77a3a0391395dd896d7af77ec25824e94ea1410523fe63f91ce780c30`
- sealed membership key: `backend/data/corpus_snapshots/exact_terminal_checkmate_caption_answer_key_v1.json`

It was built from the same bounded prefix of the official August 2026 Lichess
CC0 archive used by the frozen community study evidence:

- full release SHA-256: `6bf6fa8a5dee7bb81d1874ac312160060daf12f18a29dc2740a3bf6f5e5e6248`
- bounded 8 MiB prefix SHA-256: `d8e9c900da9dbcd275a84e4fa08097fcca2c164ba183c04f2659929c10c8ab38`
- 25,530 games scanned;
- 1,829 exact checkmate fires available;
- 11,737 negative controls available;
- 50 fires and 20 controls selected from 70 distinct games and 70 distinct positions.

The public packet contains no username, player id, game id, email, URL, exact
rating, correct-answer id or candidate/control label. Check and mate suffixes
are removed from displayed SAN so notation does not disclose membership. The
proposed headline, explanation and principle are identical to the central
renderer on verified positives. The legal move is exposed separately by UCI
without exposing a check or mate suffix. The
temporary identity-bearing source prefix was deleted after generation.

Independent machine recomputation before review found:

- 50/50 sealed candidates reconstruct as exact checkmate;
- 20/20 sealed controls make the detector abstain;
- the sealed key matches the packet SHA;
- zero candidate/control overlap;
- zero duplicate case ids or source groups;
- zero email, URL or answer-field leakage.

Those checks validate packet construction, not Caption promotion. An
independent reviewer must still freeze one verdict per case without opening
the membership key or implementation.

### 3.3 Deterministic answer placement

One shared `order_deterministic_choices` helper now owns answer order for both
personalized lessons and community chapters. It hashes a stable event/evidence
seed with each choice id. The same position retains the same order across
reloads, different positions do not share a fixed answer slot, and `not sure`
may remain deliberately last where the lesson contract requires it.

The v3 population comparison was:

| Formula | correct at index 0 | correct at index 1 | Decision |
| --- | ---: | ---: | --- |
| existing hard-coded order | 64 | 0 | rejected |
| always reversed | 0 | 64 | rejected |
| existing stable seeded hash | 29 | 35 | selected |

The community admission gate now recomputes the sealed answer positions and
rejects the entire release if the proof-supporting answer occupies only one
position. The initial player payload still omits the answer.

### 3.4 Position-specific choices

The missed-material question no longer names the answer square. Both choices
are complete chess ideas rather than bare SAN moves: one describes the
verified stronger line and one describes the played line. Exact endgame
choices likewise describe preserved versus changed result rather than asking
the learner to choose between unexplained notation.

## 4. Evidence sequence that cannot be skipped

1. Give Claude only
   `exact_terminal_checkmate_caption_review_v1.json` and its SHA. Do not give
   the sealed membership key, builder, scorer, runtime adapter or quality
   registry before the review is frozen.
2. Claude legally replays all 70 cases, fills every `reviewer_response`, adds a
   packet-bound `independent_review` attestation and saves a new reviewed file.
3. Run `score_exact_terminal_checkmate_caption_review.py` with the frozen
   packet, frozen reviewed packet and sealed key.
4. Keep the family Shadow unless all locked Caption bars pass, plus zero exact
   fact false positives and all candidate copy is correct and teachable.
5. Only after that evidence passes, update the quality registry to Caption and
   bind it to the immutable reviewed evidence and score.
6. Generate a fresh v4 community study review packet and separate sealed
   admission packet. Do not reuse or edit v3.
7. Obtain a new independent whole-game review of v4.
8. Run the v4 admission dry-run. It now includes the fixed-answer-position
   gate in addition to every prior truth, teaching, coherence and assignment
   gate.
9. Only if every gate passes may Claude prepare a dark deployment. Visibility
   remains a later isolated-cohort decision.

## 5. Stop conditions

Keep both community flags false and keep the terminal family Shadow on any:

- terminal candidate that is not exact legal checkmate;
- incorrect or unteachable candidate copy;
- critical candidate false claim;
- incomplete or unbound independent review;
- v4 study below either locked rate;
- uncovered admitted checkmate finish;
- repeated primary principle;
- fixed proof-answer slot;
- answer, identity or source leakage;
- illegal demonstration or replay;
- changed personal-review behavior with the flags off.

No production database read or write, engine run, model call, push, deployment,
admission or flag change is part of this repair state.

## 6. Local verification

The complete affected in-process regression selection passed:

- 317 backend tests passed;
- Python compilation passed for `backend/services`, `backend/scripts` and
  `backend/tests`;
- `git diff --check` passed (Windows line-ending warnings only).

`backend/tests/test_all_flows.py` is not green or red in this worktree. Its
repository-mandated direct entry point is an HTTP harness and stopped on the
first request because no local backend was listening. Running the file through
pytest is also not a substitute because its async functions are script entry
points rather than pytest-native async tests. Treat the HTTP suite as
inconclusive until a deployment candidate is running; do not report it as
passing and do not interpret the connection failure as a product regression.
