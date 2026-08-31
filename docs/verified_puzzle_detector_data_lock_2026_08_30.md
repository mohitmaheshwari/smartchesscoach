# Verified Puzzle Detector Engine — Data Lock

Date: 2026-08-30
Status: locked for implementation

Evidence:

- `backend/data/corpus_snapshots/verified_puzzle_detector_corpus_2026-08-30.json`
- `backend/data/corpus_snapshots/current_detector_fires_2026-08-30.json`
- `backend/data/corpus_snapshots/personal_curriculum_selection_2026-08-28.json`

Every measurement is a full aggregate or deterministic replay. No sample row,
user, game, move, FEN, PGN, caption or credential is stored. Existing analyzed
games made zero new Stockfish calls.

## Decision 1 — admission policy

**Chosen: verified coverage ladder.**

1. Serve a specific concept only when canonical source reconstruction, stored
   engine evidence, a deterministic detector, an independent verifier and
   detector authorization all agree.
2. Serve a verified broader category when the exact concept is not proved.
3. Serve a generic calculation/threat exercise when a legal stored answer or
   deterministic acceptable-move set is proved but no narrower lesson is honest.
4. Quarantine only broken provenance, reconstruction, answer contradiction or
   positions with no honest prompt and grading rule.

Rejected candidates:

- **Legacy approval boolean:** would accept 11,433 `community_puzzles` rows while
  leaving all 38,122 `community_training_positions` outside any shared contract.
  It cannot prove concept attribution.
- **Exact stored answer only:** would retain 10,964/11,560 (94.84%) community
  puzzles but unnecessarily discard 596 detector-gradable lessons, including
  skills where a deterministic acceptable-move set is the honest answer.
- **Quarantine unsupported specifics:** appears precise but would turn detector
  incompleteness into product deletion. The ladder preserves truthful practice.

## Decision 2 — hard structural gates

Every served position must satisfy all of these; there is no confidence score
that can override a failed gate:

- canonical source reconstructs to the teaching board and side to move;
- the played move and stored engine move are legal in the reconstructed state;
- an exact-answer exercise has at least one verified acceptable move;
- the answer set contains no unresolved contradiction for the same canonical
  source position;
- detector, verifier, source and stored-analysis fingerprints are present;
- a specific label is authorized by `detector_quality`.

The gate is feasible rather than aspirational: all 13,744 analyses link to a
source PGN; all 49,682 live puzzle rows currently contain syntactically valid
boards; all 49,086 rows with exact answers have legal answers. The 32 conflicting
answer positions (0.06%) must be re-adjudicated before serving.

**Quarantine ceiling: 0.10% of re-adjudicated rows.** The measured structural
contradiction rate is 32/49,682 = 0.064%; 0.10% is the next one-decimal envelope.
Missing labels or narrow proof do not count as quarantine—they use the ladder.
Exceeding the ceiling blocks rollout and opens a detector/source repair batch.

## Decision 3 — stored Stockfish evidence

- Existing analyzed games are immutable evidence: zero Stockfish reruns.
- Reconstruction uses source PGN; objective consequence uses stored move,
  `cp_loss`, evaluation, best move and available stored continuations.
- 436,820/436,880 user-move records (99.99%) have a non-empty stored best move.
- Stored best/played continuations are non-empty for 32.58% of user moves. A PV
  may strengthen a proof but is not required for geometry that can be verified
  legally from the reconstructed board and stored best move.
- The 60 user moves without a stored best move cannot become best-move puzzles.
  They may become concept exercises only if an independent deterministic
  acceptable-move verifier exists; otherwise they remain shadow.
- Analysis documents have no explicit analysis-version field. The admission
  fingerprint therefore hashes the exact stored evidence used rather than
  pretending a missing version exists.

## Decision 4 — detector contradiction bands

The existing detector-quality scan bands are retained:

- an **applied** fire with stored loss greater than 100cp is a contradiction
  candidate and cannot be promoted without independent adjudication;
- a **missed** fire with stored loss at most 50cp cannot become a player-facing
  failure claim unless a legal counterfactual proves the concept was uniquely or
  materially necessary;
- centipawn loss is a contradiction signal, not the concept detector. A high
  loss does not identify the human lesson.

The bands discriminate strongly in this corpus: all seven Scholar's Mate misses
lost over 200cp, while 73.04% of opposition misses lost at most 25cp, 88.68% of
rule-of-square misses lost at most 25cp, and 92.86% of trap misses lost at most
50cp. Therefore Scholar's Mate enters verification first; the latter three must
be tightened before any failure claim.

## Decision 5 — evidence floors and review size

Natural detector opportunities have a clear gap: Lucena has 0 fires, Philidor
11, then the next family has 68.

- **Natural-evidence floor: 50 fires.** Below 50, natural games are reviewed in
  full but cannot establish generalization alone; canonical/tablebase positions
  and constructed adversarial controls are mandatory.
- **Blind Codex packet:** review every distinct natural fire when a family has
  at most 500 fires. The measured distribution jumps from 424 to 1,041, so 500
  preserves complete review for eight of ten current detectors.
- Above 500 fires, review 500 cases stratified by outcome, source, rating/phase
  and cp-loss band, plus every contradiction case and every adversarial control.
- Release requires zero unresolved false player-facing claims in the frozen
  packet. A disagreement blocks only the affected detector family.

## Decision 6 — corpus split

Discovery, development and held-out review split by stable user/source unit,
never by individual position:

- 70% discovery
- 15% development
- 15% held-out

The current-schema corpus covers 46 users. An 80/10/10 split would leave only
about four or five users in each holdout. The chosen split leaves about seven in
each holdout while retaining about 32 for discovery. Related games, duplicate
positions, sessions and transpositions stay in the same partition. Canonical
lesson/tablebase/adversarial cases form a separate frozen control partition.

## Decision 7 — repair order

1. **Admission/provenance and authorization:** all 38,122 training positions
   lack approval; 2,565 duplicate-answer rows and 32 answer conflicts exist;
   shadow detectors currently influence mastery because enforcement is off.
2. **Piece safety and tactical geometry:** player exposure is highest—10,762
   hanging-piece, 5,902 missed-threat, 5,319 generic-tactical, 4,805 pin and
   3,121 piece-safety puzzle labels; `simple_hang` affects 36/46 current-schema
   users. Reuse legal exchange and central shape facts.
3. **Opening and trap reasoning:** opening identity reaches 10,189/13,744 games
   (74.13%) and in-book application fires 4,071 times, but harmful deviations,
   plans and principles are ungraded. Trap detection fires 234 times, but 82/98
   misses lost at most 25cp and require mechanism/counterfactual proof.
4. **Core endgames:** tighten opposition and rule of square, retain proven basic
   mates, and build tablebase/canonical gold for the naturally rare Lucena and
   Philidor families.
5. **Pawn, positional, king, calculation and remaining geometry families:**
   extend canonical facts in descending exposure, with the same admission and
   review contract.

All five waves are in scope. The ordering controls implementation risk; it does
not remove later chess knowledge.

## Decision 8 — fallback ratchet

There is no universal fallback percentage because family opportunity rates differ
by orders of magnitude (0 Lucena fires versus 4,071 opening fires). Each family
records its shadow-run specific/broad/generic rates. Promotion must hold or raise
truthful specific coverage and may not raise that family's broad/generic baseline.
Every release ratchets the measured fallback ceiling downward; no family may buy
apparent accuracy by increasing quarantine above 0.10%.

## Shared admission result

One result is consumed by every extraction and serving path:

- canonical source kind/reference/fingerprint and reconstructed ply;
- stored-analysis fingerprint plus only the engine fields actually consumed;
- status: `specific`, `broad`, `generic` or `quarantine`;
- canonical concept/family ID, never copied lesson content;
- detector proof: pieces, squares, causal before/after facts, counterfactual,
  acceptable moves, detector ID/version;
- independent verifier ID/version/verdict;
- detector-quality authorization ID/grade;
- stable reason codes and audit timestamps.

The result stores proof references and derived evidence, not a new opening, trap,
endgame or tactical knowledge catalogue.

## Required chokepoints

Writers that become callers of the shared contract:

- `puzzle_extraction_service`
- `skill_puzzle_extraction`
- `community_training_service`
- `coach_puzzle_extractor`

Readers that reject missing/stale verdicts and use the same contract:

- prescribed/pattern training puzzle serving
- skill drill serving
- personalized lesson workspace
- diagnostic and curriculum puzzle selection

## Rollout and rollback

1. Dry-run re-adjudication writes aggregate reports only.
2. Add versioned verdict/proof fields non-destructively; never delete original
   rows, attempts, labels or source evidence.
3. Dual-read behind a default-off feature flag and compare old/new reach.
4. Enable shadow telemetry, then internal accounts, then staged production.
5. Rollback switches readers to the previous verdict version; it does not erase
   source or learning history.
6. Historic attempts retain the move result but unsupported concept credit is
   versioned/withdrawn until re-proved.

## Behavior metric

The primary success measure is transfer, not puzzle clicks: after a verified
lesson, does the player correctly apply the proved concept in a later real game
and retain it at delayed review? Coverage, fallback and quarantine are safety and
operational metrics, not substitutes for learning.
