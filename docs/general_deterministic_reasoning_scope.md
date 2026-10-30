# General deterministic reasoning — offline prototype scope

Status: offline implementation authorised by Mohit's “okay, move ahead” on 2026-10-30, following the repository audit, algorithm and spec presented in this chat. This records that authorisation; it does not request it again.

## 0. Existing surfaces audit

The completed [repository audit](general_deterministic_reasoning_audit_2026_10_30.md) traced the existing Why button, caption framework, admin reasoning trace, worker, replay and candidate evidence. Why returns resolver text/arrows or an explicit inability to explain. Captions have their own fact/purpose/renderer path and optional stored LLM text. The admin trace runs a six-question framework, rather than the player Why pipeline.

Decision: **EXTEND existing evidence infrastructure**. The prototype reuses `stored_line_verifier` for legal event/identity extraction and material definitions. It supplies one common internal reasoning result for eventual existing adapters. No new player page, runtime caption writer, route or database collection is created. This overlap and direction were surfaced before Mohit authorised proceeding.

## 1. What it is

A local explanation engine that reads a chess position, investigates useful moves and replies, and returns what it can support together with the limits of that investigation. With a played move, it always analyses that decision too. It records both successful explanations and rejected or unfinished ideas so that we can judge correctness and usefulness before exposing it to players.

## 2. What the user sees

No UI change in this milestone. A command writes a reviewable explanation JSON file, with controlled text such as:

```text
Look for a move with check during an exchange
In the analysed line, the knight takes the bishop on e7 with check.
The king has only one legal reply at that point.
Before taking back, look for a stronger move with check.

Scope: demonstrated continuation; earlier opponent choices remain searched,
not exhaustively proved.
```

A quiet example must show legal preparation and the opponent's resources. It must say an explanation is unfinished when a fixed route fails against a strong reply. It must never use the root FEN or a game ID as a template lookup.

## 3. In scope (V1)

- Typed scores and four separate result outcomes from the approved spec.
- FEN-only and FEN-plus-played-move operation; optional validated legal history.
- Explicit bounded engine queries with fresh process isolation, mandatory played search, score bounds and a reproducibility manifest.
- Legal branching timelines, root-based identities and retained enabling facts derived from canonical replay.
- Reusable objective generation from legal choices, event differences, checking captures, opened lines, protection changes, pawn transformations and preparation routes.
- Composed reasoning links with legal reply challenges and recorded counterexamples.
- Independent proposition verification for actor, relation, direction, time and claim strength.
- Controlled narration and an offline CLI/benchmark report, without an LLM.
- Tactical and quiet experiments, safe-sacrifice/alternative-defence boundaries, equivalent choices and already-losing context.

## 4. Explicitly out of scope (V1)

- Product integration, deployment, backfills, database writes, caption replacement and new player pages.
- Arbitrary LLM rewriting, exact causal allocation of engine scores, and exhaustive general chess proof.
- Shipping numeric thresholds or a measured-generalisation claim based on the development examples.
- Using the previously inspected examples or reviewed gold as an untouched evaluation set.

## 5. Success criteria

A reviewer can use the generated account to identify the actual move/reply relationship and reject a tempting false explanation: for example, avoid saying that an attacked queen must move, or that Qf8 abandoned protection it never supplied. Verification must measure factual/support correctness and useful coverage together. The first experiment includes quiet decisions and their counterplay, not only material wins. Runtime, query/node consumption, memory and all abstentions are reported.

These are offline learning/decision criteria. A later product experiment must measure whether players recognise the same opportunity in an unfamiliar position, before claiming player improvement.

## 6. Open questions

- **Question:** Which search settings and comparison policy should ship? **Why unresolved:** no general core benchmark yet. **Unblocking step:** expose required experimental configuration and compare measured runs; do not lock defaults now.
- **Question:** What useful supported coverage does this achieve across games and quiet decisions? **Why unresolved:** implementation and blinded review pending. **Unblocking step:** development experiment, then freeze and seal an untouched game-level set.
- **Question:** What is the eventual interactive latency target? **Why unresolved:** no product budget selected. **Unblocking step:** use measured query/runtime data for the later integration decision.
- **Question:** Can current local reviewed data be queried? **Why unresolved:** existing Mongo configuration requires authentication. **Unblocking step:** use authorised local fixtures now; require a readable export for representative production measures.

## 7. Pre-code requirements

- Scope and literal offline output recorded above; no new player surface.
- Authorisation: Mohit's direct “okay, move ahead” after the concrete plan.
- Existing evidence, geometry and piece-value sources identified; extend/reuse them.
- Search caps are explicit experimental inputs. No new unmeasured shipping threshold or teaching-ranking formula is locked.
- Instrument queries, rejection reasons, coverage and cost before evaluating outputs.
- Leave production adapters, all deferred items and pre-existing user work untouched.

Pre-code audit: **PASS for the offline prototype**. Gates 1–2: literal output and teaching-point headline above. Gate 3: no shipping numeric locks; configuration is required and recorded. Gate 4: decision/transfer usefulness, not activation. Gate 5: deferred product work excluded. Gate 6: direct authorisation in this chat. New verification scripts live outside `backend/tests` and are never committed as product tests.
