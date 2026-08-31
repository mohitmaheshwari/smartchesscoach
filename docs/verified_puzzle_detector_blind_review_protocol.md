# Verified Puzzle Detector Engine — Blind Codex Review Protocol

Protocol version: `blind_review_v1_2026_08_30`
Status: frozen before detector implementation

## Purpose

Codex independently reviews the human chess lesson after a detector is frozen.
It does not run Stockfish, replace tablebases, see detector output, or decide
production truth at runtime. Its chess reasoning must be supported by the stored
Stockfish evidence supplied in the packet.

## Packet construction

Each case receives a random review ID unrelated to the user, game or detector.
The sealed input contains only:

- reconstructed board before the player move;
- player colour and rating band, without identity;
- played legal move;
- stored best move, evaluation before/after and centipawn loss;
- stored `pv_after_best` and `pv_after_played` when present;
- legal source continuation required to understand the position;
- whether the case came from a real game or canonical/adversarial control;
- the exact player-facing prompt and grading contract being proposed.

The packet excludes detector ID, concept label, confidence, proof, admission
status, existing caption, curriculum recommendation and previous reviewer result.
The ordered packet is hashed and frozen before review begins.

## Independent Codex response

For each review ID, Codex records:

- `teachable`: yes/no;
- `primary_lesson`: plain-language chess idea for a 600-1500 player;
- `geometry`: relevant pieces, squares, lines and defensive resources;
- `why_played_move_fails_or_succeeds`;
- `acceptable_moves`: every move the supplied evidence supports, or an explicit
  statement that the packet cannot prove a complete set;
- `claim_boundary`: what must not be inferred from this position;
- `adversarial_risk`: sound sacrifice, pin, x-ray, zwischenzug, transposition,
  multiple solution, tablebase exception or other likely false-positive cause;
- `verdict`: specific / broader lesson / generic exercise / unsafe to teach;
- `evidence_sufficient`: yes/no.

The response may replay legal chess moves with python-chess. It may not request a
new Stockfish evaluation, an LLM opinion, production identifiers or hidden
detector output.

## Sampling lock

- Review all natural fires for families with at most 500 fires.
- For larger families, review 500 cases stratified by outcome, source unit,
  rating/phase and stored cp-loss band.
- Add every detector/engine contradiction case.
- Add all frozen positive, negative and adversarial controls.
- Keep related games, duplicate positions and transpositions in one split.

## Reveal and comparison

Only after the Codex response file is sealed and hashed are detector fields
revealed. Comparison is exact on: teachability, primary canonical concept,
relevant geometry, success/failure direction, acceptable-move contract and claim
boundary. Wording differences do not count as disagreements.

## Adjudication

Every disagreement is resolved against, in order:

1. legal reconstruction from source;
2. supplied stored Stockfish evidence;
3. tablebase/canonical endgame truth where applicable;
4. independent verifier proof;
5. recorded human chess adjudication when the evidence supports multiple lessons.

The affected detector family remains shadow until no false player-facing claim
is unresolved. A broad or generic downgrade is a valid resolution. Deleting a
valid position merely to improve the score is not.

## Release artefacts

The frozen packet hash, blind Codex response hash, detector output hash,
comparison report and adjudication log are versioned. Production receives only
deterministic detector/verifier code and authorization data—never Codex output or
an LLM dependency.
