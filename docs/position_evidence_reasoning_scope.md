# Position evidence to GPT-6-luna — scope

Status: implementation authorised by Mohit's explicit request on 2026-10-30
to prepare the discussed solution: Stockfish punishment lines up to 15 plies,
initial and per-move piece strengths/weaknesses, then GPT-6-luna reasoning.
This records that agreed direction; it does not claim Mohit reviewed this
subsequently written document. No repeat implementation approval is needed.

## 0. Existing surfaces audit

The production Why route calls `why_on_demand`, with resolver-specific optional
wording in `why_words`. It does not consume a generic fact timeline. The
offline `services/reasoning` package already owns isolated bounded Stockfish
searches, legal timelines, identities and ChessGPT candidate features. Its
deterministic explanation selection uses individual mechanism composers.
`llm_service.call_llm` owns provider calls. The untracked g4 experiment already
demonstrates the desired data but is not a reusable supported entry point.

Decision: EXTEND the offline reasoning package and reuse its canonical replay,
features, search ledger and existing LLM caller. No new player page, second
Stockfish wrapper or replacement production caption path is introduced.

## 1. What it is

A reusable offline command accepts a chess position and move, calculates
searched continuations, describes every piece before the move and after each
half-move, and asks GPT-6-luna to propose why the move matters. It saves the
facts, exact model input, raw answer and checks so the explanation can be
reviewed without trusting the wording alone.

## 2. What the user sees

No UI change. Local output has this shape:

```text
Played: ...g4
Search: target depth 24; achieved depths recorded separately
Line horizon: at most 15 plies; no invented continuation
Initial board: every piece, its support, attacks and positional attributes
Per move: moved/captured identities and every changed relationship
GPT-6-luna reasoning: a cited proposal for review
Mechanical checks: passed / refused / unavailable
Teaching relevance: not automatically established
```

Any example reasoning is model output, never a hardcoded target for this
position. Facts and candidate positional labels retain different authority.

## 3. In scope

- Accept FEN before plus legal move and/or FEN after; verify the pair.
- Use the existing search configuration and explicit requested depth/budgets.
- Calculate the played branch and best searched alternative, plus unrestricted
  replies where budget permits; retain source and achieved-depth information.
- Replay only available legal PV moves, with a maximum of 15 plies.
- Scan all pieces initially and at every available ply, including unmoved
  pieces affected by changed defenders, attackers or opened lines.
- Save identity-aware relationships, exact material counts and ChessGPT
  positional attributes such as passed pawns/outposts with provenance.
- Produce full saved snapshots and a losslessly deduplicated model view using
  initial facts and per-ply changes. Do not silently drop facts to fit a prompt.
- Pin the reasoning request to `gpt-6-luna`, preserve raw responses, and make
  every call explicit. Use the existing caller and selected environment file.
- Check response shape and evidence references; any accepted response remains
  an unreviewed proposal. Reference validity alone is not factual or teaching
  correctness. Errors never become a plausible fallback explanation.
- Commit tests before implementation and run the g4 development case.

## 4. Out of scope

- Production Why routing, frontend work, deployments, database writes/backfills
  or automatically showing model drafts to players.
- A new provider service, rewritten Stockfish search or duplicated detector
  definitions. The existing feature extractor remains candidate evidence.
- Encoding the manually identified g4/f4 reason into prompts or source rules.
- A guarantee that 15 plies are forced, a unique cause of a score gap, or all
  chess strengths and weaknesses are exhaustively detected.
- Shipping latency promises, calibrated new ranking weights or quality rates.

## 5. Success criteria

A reviewer can reconstruct every provided board state, follow a model claim
to its exact branch/ply/piece, and distinguish raw model reasoning from checked
facts. The pipeline runs from arbitrary legal input without a position lookup.
The initial development run may fail relevance; failures must be retained.
Player usefulness and fresh-position correctness remain separate evaluation
gates before any product rollout.

## 6. Open questions

- Which amount of evidence yields reliable reasoning? Measure input size and
  retain all facts through lossless deltas; do not fit a cutoff to this case.
- Does GPT-6-luna select the right reason? Save its unedited response and grade
  independently. Mechanical checks cannot resolve that question.
- Can this meet the eight-second Why budget? Measure separately; this milestone
  stays offline regardless of the local result.

## 7. Pre-code requirements

The current user request authorises this exact implementation after the design
discussion. The literal output, existing overlap and EXTEND decision are above.
The 15-ply limit and model are user-specified; search/token allocations remain
explicit experimental inputs. Reuse the existing sources and keep deferred
production work deferred. Preserve the main working-code checkout and edits.
