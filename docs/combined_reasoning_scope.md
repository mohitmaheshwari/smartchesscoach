# Combined reasoning — extension of our existing offline engine

Status: implementation of the offline combination authorised by Mohit on
2026-10-30: “take best of both worlds and combine, our engine and chessgpt.”
This follows the concrete four-part plan presented in this chat. Mohit also
confirmed: “I have the author's permission” to reuse and modify ChessGPT.
This extends the already authorised general reasoning prototype; it does not
authorise deploying a new player-facing explanation pipeline.

## 0. Existing surfaces audit

- `backend/routes/coach.py:1423` serves the existing Why button using
  `why_on_demand.explain`. `GameDecryptionV5.jsx:2179` displays its text,
  arrows and explicit `found: false`. That path is already a player surface.
- `backend/services/reasoning/engine.py:45` is the offline general engine:
  typed scores, mandatory played-move search, identities/timelines,
  hypotheses, verification, reply/relevance admission and sentence receipts.
  Its callers are offline scripts/tests, not the player Why route.
- `stored_line_verifier` owns legal replay and relationship snapshots.
  `shape_detectors.simulate_knight_outpost` and
  `caption_concept_sentences.p_knight_outpost` already detect knight-placement
  situations. Their policies differ: current pawn safety versus potential
  pawn challenges, and piece support versus pawn support. These must not
  silently become interchangeable claims.
- `why_words` already provides optional fact-based narration and validation.
  It accepts resolver findings; it does not yet accept arbitrary proof graphs.
  Reusing its service later requires a deliberate contract adapter.
- ChessGPT's pinned feature extractor supplies reusable positional candidate
  evidence. Its search wrapper, fitted attribution, routing labels and prose
  prompts are not adopted as authorities. The trial found good root choices,
  but weak relevance, mate-distance collapse and long search times.

Decision: **EXTEND our offline reasoning core.** One search ledger, one
verified fact store, one selected account. ChessGPT becomes a candidate
evidence provider inside it. No second player engine or new page is created.
This direction was explicitly requested by Mohit before this document.

## 1. What it is

Our explanation engine gains ChessGPT's ability to describe positional
differences while retaining the work already invested in proving board facts,
testing replies and refusing unsupported claims. A feature can suggest what
to investigate; the engine must still connect the player's move to a useful
consequence and verify each link before describing it as a reason.

## 2. What the user sees

This milestone produces local evidence files through the existing offline
entry point. It makes no UI change. A target account, assembled from facts
rather than a position lookup, is:

```text
Attack the defender before exchanging

Taking the bishop immediately lets White recapture with the knight on e5.
That knight is protected by the pawn on d4, and Black's d- and f-pawns
cannot chase it away by advancing. In the compared line, g4 attacks the
knight on f3 first; after Nd2 and Nxe5, White recaptures with the pawn.

Scope: demonstrated legal lines with engine comparisons; this does not say
Nd2 is White's only legal reply or that every defence has been proved.
```

This is a review target, not an achieved output. Every named fact must have
an independent receipt. The system may return an incomplete account when
the comparison or reply checks do not support it.

## 3. In scope (first milestone)

- Preserve the public offline input/result contract and existing verified
  forcing, immediate-capture, equivalent-subject and mate-distance behaviour.
- Vendor only the necessary ChessGPT feature code at revision
  `b7ea991854f926250036105f152894881e7820a2`, with hashes and permission
  provenance. Do not invent a permissive licence for the upstream source.
- Derive feature differences from our existing legal primary timelines;
  record piece, square, actor, ply, timeline and feature-provider provenance.
  No second Stockfish instance or independent move-ranking policy is added.
- Treat feature values, labels and zero/nonzero fitted weights as proposal
  data. They cannot establish causality, certify a sentence or suppress a
  verified useful relation merely because its regression weight is zero.
- Add a reusable, board-derived recapture/preparation composition. It must
  connect the attacked defender, changed recapturing piece, resulting
  placement and legal comparison. No FEN, SAN-name, game-ID or square lookup
  may select the mechanism.
- Independently check positional properties before admitting them. Distinguish
  current attacks, pawn protection, potential advances on adjacent files and
  exhaustive claims about all possible future pawn captures.
- Keep settled material, typed mate scores, unrestricted reply provenance,
  relevance admission and honest abstention. Rank a complete supported chain
  ahead of an incidental positional observation; retain immediate material
  explanations when they explain the decision.
- Add tests before implementation and compare the baseline, ChessGPT and
  combined outputs on the disclosed regression set. Save timing, budgets,
  rejected candidates and unresolved links.

## 4. Explicitly out of scope (first milestone)

- Replacing the production Why route, changing captions, deploying, database
  writes/backfills or creating a second coaching surface.
- Copying ChessGPT's Stockfish wrapper, provider integrations, opening data,
  evaluation-as-material wording or regression-based causal percentages.
- Retraining weights, training a neural model, claiming exhaustive chess
  understanding, or hardcoding the explanations for the reviewed positions.
- A new LLM service. Existing fact narration is the later integration point;
  this milestone first needs a verified structured account and controlled text.
- Declaring the reviewed examples untouched or claiming player improvement
  from a mechanical validation count.

## 5. Success criteria

A reviewer can follow how the root decision changes the opponent's useful
reply and can reject an attractive but unsupported explanation. The Nxe5
account must identify the central-knight mechanism through reusable relations,
while the existing Na4, Qf8, Nf3, Qa2 and direct-capture regressions retain their
verified behaviour. Mutation checks must reject wrong actors, substituted
pieces, false pawn-safety claims and invented score/branch bindings.

Coverage and usefulness are graded separately from board truth. Runtime is
measured against the existing eight-second product requirement; exceeding it
keeps this work offline. No new ranking weights or shipping thresholds are
chosen without measurement. A frozen policy must later face fresh positions
before any broader usefulness claim. A later product study must test whether
players recognise the same mechanism in an unfamiliar position.

## 6. Open questions

- Which feature candidates add useful explanations beyond our existing facts?
  Resolve with recorded candidate admission and reviewed comparisons.
- Which search scheduling and feature horizon meet the product budget?
  Preserve explicit experimental settings and measure; do not promise eight
  seconds from the current slower baselines.
- How often does a generic preparation/recapture chain survive strong replies?
  Resolve through unrestricted reply checks and a subsequent fresh evaluation.
- When should this reach the player Why button and optional LLM narration?
  Resolve only after offline review, a response-contract adapter and a separate
  approved rollout. This milestone does not silently enable that migration.

## 7. Pre-code requirements

- Direction and implementation authority: Mohit's current request follows the
  four-part integration plan; no repeat approval of that action is requested.
- Reuse permission: explicitly confirmed in this chat on 2026-10-30. Preserve
  this provenance; it is not a claim that the repository has an open licence.
- Literal output contract, existing surfaces, overlap and EXTEND decision are
  recorded above. The current authorisation concerns this offline extension.
- Use our established evidence, search, verifier and test framework. External
  feature proposals never bypass them or become another canonical narrator.
- No unmeasured shipping threshold, automatic rollout or production integration
  is introduced. Existing regression data remains disclosed development data.
- Preserve the main `working-code` checkout and unrelated user edits.

Pre-code audit: applicable to this extension of the already authorised offline
prototype. The output is concrete, the teaching headline is a general pattern,
no new numeric policy is locked, success concerns useful reasoning and transfer,
deferred product changes stay deferred, and implementation was directly requested.
