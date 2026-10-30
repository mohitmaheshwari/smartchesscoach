# Combined reasoning — implementation spec

Status: offline extension requested by Mohit, 2026-10-30. The
[scope](combined_reasoning_scope.md) records authority and reuse permission.
This addendum implements the existing general-reasoning design, not a new UI.

## 1. The problem

Our prototype can verify facts and reject irrelevant searched events but lacks
useful positional candidates. ChessGPT supplies those candidates but can select
an incidental feature as the explanation. In Nxe5 it detects White's secure
e5 knight, yet selects mobility/tempo. The combined system must retain the
candidate without treating a regression coefficient as causal proof.

## 2. The shape — three outcomes

`our search → our legal timelines → positional proposals → joined explanation
→ independent fact/dependency verification → existing selection and rendering`.

- A verified, root-connected mechanism may become the teaching point.
- A true positional observation with no verified connection stays diagnostic.
- Failed reply, stability or budget checks leave an incomplete hypothesis.

The existing literal response target and its conditional limits are in scope
section 2. Baseline operation remains available for a controlled comparison.

## 3. Schema / files touched

- Preserve `ReasoningConfig`, `Score`, `SearchRecord`, `Proposition`,
  `Hypothesis` and `explain_fen`'s existing input/result fields.
- Add explicit optional positional-provider/horizon/verification allocation
  arguments to the offline entry point and CLI. Existing callers are off.
- Record provider revision/hash, raw feature value, board-node/timeline IDs,
  ply, actor and typed proposal evidence. No fitted causal percentage.
- Add a generic preparation/recapture composition and independent verifier
  integration to `services/reasoning`; extend its existing renderer/admission.
- Place the unchanged necessary upstream feature source in a small vendor
  package with a provenance notice. Omit upstream search, prompts and weights.
- Extend source manifests so vendor code and experimental arguments are bound
  to results. Do not claim a sealed evaluation unless its hashes include them.

## 4. New facts / data the system needs

Derive candidate differences from our already searched boards. Retain raw
outpost/support evidence even when its upstream fitted weight was zero.
An accepted placement fact independently binds the actual piece, its pawn
defenders, current enemy attackers and the scope of pawn-advance challenges.
These are primitive board claims, not an unqualified permanent-outpost label.
Existing caption detectors keep their separate current acceptance policies.

A recapture mechanism joins: the originally captured piece, its defender,
the alternative root's attack on that defender, the defender's retreat in a
searched reply, the same capture later, and a different recapturing piece.
Both variants are legal. Search records separately compare the original roots
and the recapture choices; fresh unrestricted opponent searches check relevant
branch prefixes at depth 20. A restricted counterfactual is labelled as such.

## 5. Gating — preventing the true-but-irrelevant trap

Feature-provider statements are untrusted proposals. Our verifier checks each
admitted positional fact from the board and every joined dependency against
piece identities, branches, timing and bound typed scores. Conditional lines
stay conditional. Do not say a reply is forced because it is the engine's PV.
Require the current root-stability agreement and completed opponent-reference
depth; a requested-but-unreached depth supplies no permission to render.
Existing immediate-capture, forcing-certificate and equivalent-subject policies
remain in force. No imported search process bypasses our query/node allocation.

## 6. Test strategy

First add failing engine-free tests for feature provenance, recapture identity
joins, mirroring, incorrect placements, fabricated score/branch bindings,
unreached depth and disabled-provider compatibility. Then implement.
Run the existing package tests and meaningful engine-backed regressions.
Compare baseline and combined Nxe5 plus Na4/Qf8/Nf3/mate/capture regressions;
retain every failure and abstention. The reviewed corpus is development data.
Freeze before later fresh game-level evaluation. Never grade a route label as
an independently useful explanation. Run the required backend core flow check;
record any unavailable local service rather than count it as passing.

## 7. Risk + rollback

The first milestone is opt-in offline operation only; production imports do
not change. Disable the provider to retain the baseline behaviour. Permission
was supplied by Mohit, not inferred from a nonexistent upstream licence.
Feature extraction may cost time; reserve validation work before optional
resources and record actual latency. Any quality-search allocation above the
existing baseline is disclosed as an experiment, not a shipping default.

## 8. What this spec does not cover

No route migration, caption replacement, data backfill, deployment, new LLM
service, neural training, weight refit or general chess-understanding claim.
No hardcoded example FENs/moves in implementation. Fixtures may contain them.

## 9. Implementation order

1. Record scope, freeze the upstream source and capture our unchanged baseline.
2. Add boundary/composition tests before feature code.
3. Add the candidate provider and proof composition to the existing core.
4. Run combined development probes and regressions; report quality and cost.
5. A future product adapter requires explicit approval. For that replacement,
   use default-off `CHESSGURU_COMBINED_REASONING_ENABLED`, reviewer A/B for one
   week, then a measured 10% week, 100%, and retirement after two clean weeks.
   Those rollout phases are not silently included in this offline milestone.

## 10. Decisions / open questions

- Decided: EXTEND our core; keep one search/verifier/selector; permission to
  reuse and modify upstream code confirmed by Mohit in this chat.
- Pending measurement: provider horizon, verification allocation and shortlist
  ordering. Experimental inputs are explicit; no new numeric policy is locked.
- Pending review: useful comparative coverage on fresh positions and latency
  against the existing eight-second product requirement.
- Pending approval: player-route integration and LLM proof-graph narration.
  These questions do not revoke the requested offline implementation.
