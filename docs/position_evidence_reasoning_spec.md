# Position evidence to GPT-6-luna — spec

Status: authorised offline implementation, 2026-10-30. See the agreed
[scope](position_evidence_reasoning_scope.md).

## 1. The problem

Searches and piece facts exist, but the general evidence-to-model process was
only an untracked experiment. The first full dump used 114k input tokens and
the model produced irrelevant reasoning plus a material error. A reusable
runner must preserve the evidence without disguising model quality failures.

## 2. The shape — three outcomes

Input -> bounded searches -> legal timelines -> initial/per-ply inventories ->
lossless evidence projection -> explicit GPT-6-luna request -> saved proposal.
Outcomes: complete evidence, partial/unavailable evidence, or model proposal
with mechanical checks. None of these labels certifies coaching relevance.

## 3. Schema / files touched

Extend `services/reasoning` with evidence collection and a model adapter; add
`scripts/explain_position_evidence.py`. Reuse ReasoningConfig, SearchSession,
input_board, canonical timelines and ChessGPTFeatures. Keep explain_fen and
all existing callers compatible. Tests cover the new contracts independently.
The saved schema includes input, settings, provider/source hashes, all searched
records, states, branches, per-ply events, changes and exact material inventories.

## 4. New facts / data the system needs

No new chess detector taxonomy. Derive piece support/threat facts from canonical
relationships; retain raw positional evidence and scope. Map evidence to a
piece only when ownership and square/type binding are unambiguous. Preserve
unmapped evidence as board-level features. Every physical piece retains its
identity across moves, capture, castling, en passant and promotion.
Model input uses compact state/piece IDs plus the initial state and lossless
deltas. Exact material counts at every state prevent reliance on an aggregate
feature weight. Source paths and credentials are excluded from model input.

## 5. Gating — preventing true-but-irrelevant narration

The model must cite existing evidence fields and identify the relevant branch.
Unknown references, invalid shapes and unsupported structured material claims
are refused. Valid references do not prove the free-text claim follows from
them; even a structurally valid result is an unreviewed proposal. Preserve
errors and uncertainty, including failed provider calls and unreached depth.
No forced-move statement follows merely from a PV. The prompt supplies no
preselected chess reason or targeted diagnostic probes.

## 6. Test strategy

Commit failing contract tests first. Test legal pair validation, per-ply scans
including unmoved pieces, material counts, piece identity through special moves,
15-ply cap, short PVs, partial searches, source binding, deduplicated branches,
lossless projection, wrong evidence references, provider failures and exact
model selection. Run the existing offline reasoning suite and required local
core flow check. Run a frozen engine-backed development example, then an
explicit real model call; save failed reasoning instead of silently correcting it.

## 7. Risk + rollback

Purely additive offline command, with model calls opt-in. Packet-only operation
requires no model credentials. Keep production imports unchanged. The model
may still select a wrong reason; draft status and saved evidence make that
visible. Removing the new entry points restores the previous offline workflow.

## 8. What this spec does not cover

Production routing, broad model benchmarking, subjective feature weights,
automatic semantic verification, model training or new chess-specific rules.

## 9. Implementation order

1. Commit scope/spec and failing contracts.
2. Implement evidence collection and lossless projection.
3. Add the explicit GPT-6-luna adapter and CLI.
4. Run unit, engine-backed and real-model development checks; record limits.
5. Production adaptation is later work. It would use default-off
   CHESSGURU_EVIDENCE_REASONING_ENABLED, reviewer A/B, then measured 10%/100%
   rollout and legacy retirement after two clean weeks. Those phases are not
   performed by this additive offline milestone.

## 10. Decisions / open questions

Decided by the user: at most 15 plies, all-piece initial and per-move evidence,
GPT-6-luna reasoning. Decided by overlap audit: extend existing offline sources.
Current request authorises implementation; production rollout is not included.
Open: general explanation relevance and runtime. Preserve measurements and
failures rather than treating test counts as evidence these are solved.
