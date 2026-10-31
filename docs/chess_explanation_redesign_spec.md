# Chess explanation engine redesign — discussion draft

**Status:** Offline chain-builder prototype explicitly requested by Mohit on 2026-10-31. Production integration is not approved by this request.
**Scope:** A reusable offline reasoning core; eventual production integration is a separate decision. This is a research-sized effort and no schedule is established.

## 1. The problem

ChessGuru needs to explain why a played move matters, including quiet moves,
in language a 600–1500 player can use. The engine must find the connection
without being given a position-specific reason and must expose uncertainty.

Run 4 found that the new support-chain certificate matched one of 129,553
stored mistakes under an upper-bound shape scan; the position was its own
development case. The separate pressure shape was frequent but its existing
family fired on none of eight sampled cases, and removing its last witness
gate would teach a false lesson in at least one. In the separate ChessGPT
review, its evidence pipeline gave no correct differential reason on 11
non-good positions. The GPT-6-luna evidence-dump experiment produced an
irrelevant draft and a false one. These are small or scoped tests, not universal
failure rates, but they rule out claiming the connection problem is solved.

The score-exclusion locator successfully highlighted ...c5 and Nxe5 in the
two development positions, but produced search reversals on other examples;
it does not identify a mechanism or attribute a root evaluation gap.

## 2. The shape — outcomes

```text
Input position + played move + known history
  -> played move and near-best alternatives, with actual opponent replies
  -> identity-aware board changes along legal lines
  -> candidate chains joining a move, changed relationship, reply and outcome
  -> challenge each chain with legal alternatives and matched searches
  -> choose an established teaching point, or report the remaining uncertainty
  -> controlled plain-English wording
```

Outcomes: (1) a supported, scoped mechanism; (2) a supported consequence with
no established reason; (3) an unresolved investigation; or (4) no useful
evidence. Report each as what it is. Even a good explanation need not be unique.

Illustrative target for the known c4 case, conditional on the engine finding
and checking the chain itself:

> c4 leaves d4 without the pawn on c3 protecting it. Black can attack d4 with
> ...c5. If the d4 pawn falls, your knight on e5 loses its defender while the
> queen on f6 attacks it. Before moving a pawn, check what depends on its protection.

The engine must follow and scope the actual replies, not imply a specific line
is forced unless its claims support that. The evidence also contains several
near-equal alternatives that preserve the c3 defender; no one alternative should
be presented as uniquely best if the searches do not show that.

## 3. Schema and existing files

Reuse the existing `services/reasoning/search.py`, `timeline.py`,
`counterfactual.py`, `services/stored_line_verifier.py`, and the ChessGPT
feature provider in `services/reasoning/positional.py`. Evolve the offline
reasoning result, not the production routes or central caption authority.

The new logical object is a **candidate explanation** containing: played and
alternative roots; physical piece identities; a sequence of relations before
and after events; a demonstrated consequence; branch and search IDs; tested
counterexamples; result strength; and unresolved questions. Numeric scores
and search budgets remain diagnostic evidence, not player-facing prose.

An eventual adapter would feed verified outcomes into existing Why/caption
surfaces; no new parallel player-facing authority is proposed in this milestone.

## 4. Evidence and candidate generation

Use legal replay to record changes and retained facts for every piece on the
played and alternative lines: support, attacks, control, blockers, captures,
checks, material and relevant position features. ChessGPT attributes are
candidate facts, not causes. Match physical pieces and the time/branch of
each claim; avoid comparing unrelated pieces simply because they occupy the
same square.

Start from consequences and meaningful opponent choices in searched replies,
then trace their prerequisites backwards through changed relations. Build
candidate chains using composable operations such as: a move removes support;
a reply attacks a newly vulnerable target; a legal continuation captures it;
the loss changes the protection of another piece. The grammar must compose
these operations without an authored whole-story detector for each example.
The c4 chain is a development example, not a lookup rule or acceptance test
for the design by itself.

## 5. Challenges before an explanation is accepted

- **Board truth:** replay and verify every actor, piece, square, relation and
  time. A geometric attack is not automatically a profitable legal capture.
- **Reply quality:** inspect actual opponent replies and credible defences,
  including the player's responses. A line is an example unless forcedness
  is independently established.
- **Decision connection:** identify the root move's relevant change and show
  how that change participates in the consequence. A later fact alone does
  not establish that the root move caused it.
- **Comparison:** test adequate alternative roots and the corresponding
  opponent resources. Account for compensation and equivalent alternatives.
- **Counterfactual:** use matched legal searches, including reply exclusion,
  as evidence about a resource. Preserve search reversals and the possibility
  of substitutable replies. Excluding one move at one ply does not exclude the
  same plan later or prove that its whole score drop belongs to one relation.
- **Claim strength:** label unexamined branches, unstable evaluations and
  unfinished exchanges. A forced claim requires the appropriate legal proof;
  a searched PV alone is not one.

The selector must rank supported candidate explanations by their connection
to the decision and practical teaching value; the ranking and search budgets
are open research questions to be measured, not chosen from the c4 example.
An unverified candidate cannot become a coaching reason merely to avoid silence.

## 6. Test strategy

Before a new implementation, create a versioned evaluation set with cases
split by game, separating development examples from a sealed held-out set.
Include tactics, quiet moves, exchanges, defence, good moves, near-equivalent
alternatives and positions where an obvious story is wrong. Freeze inputs,
configuration and candidate-selection policy before evaluating the held-out
set; record engine version, search budgets, source and runtime.

For each result, independently review board truth, causal relevance, whether
the reason survives good responses, direction/alternative choice and teaching
clarity. Count unsupported claims, misleading explanations, shallow but true
consequences, and abstentions separately. Measure useful coverage and latency
as well as correctness. Compare against the current baseline under the same
conditions. Passing unit tests and naming a move in the engine line are not
proof that the reason is correct.

Use c4/Nxe5/Qf8/g4 and known misleading cases as development controls. A sealed
set must contain new games, not just new positions from those games. Avoid
choosing a new grammar rule after inspecting held-out failures; a new policy
requires a new untouched evaluation set.

## 7. Risk and rollback

Primary risks are plausible but irrelevant explanations, engine instability,
unexamined defences, excessive search cost and semantic drift in wording.
Start offline with an explicit resource budget and no automatic player output.
If later integrated, default off behind a dedicated flag; keep the current
central route as fallback, independently review outputs and roll back by
disabling the flag. Reuse the current 8-second Why budget as the target to
measure against, not a promise that the proposed searches fit it.

## 8. Out of scope

Production rollout, deployment, replacing existing captions, automatic
backfills, a new database, a promise to explain every move, or LLM authority
to decide chess facts and select causes. A wording model can be considered
only after the reasoning result is established; semantic faithfulness must be
verified before showing its text to a player.

## 9. Proposed work order

1. Establish the frozen, independently graded baseline and held-out protocol.
2. Prototype a candidate-chain generator and challenger offline using existing
   replay and search, without adding position-specific full-story families.
3. Test development positions, including negative controls and good moves;
   measure correctness, usefulness, coverage and search cost together.
4. Freeze the policy and run the held-out evaluation. Revise or abandon the
   approach if it fails; do not relabel a search dependency as an explanation.
5. Only after demonstrated transfer and acceptable latency, design integration
   with the central coaching authority, default-off rollout, comparison and
   rollback. Any later staged release needs its own review and sign-off.

## 10. Decisions and open questions

- How should candidate chains be generated and ranked without reproducing
  one hardcoded family per example? Compare alternative strategies on development data.
- How much search is necessary to establish a useful scoped connection, and
  which calculations can reuse existing game analysis? Measure correctness
  against cost before selecting budgets.
- What minimum accuracy, useful coverage and abstention rate justify an
  interactive trial? Set these with the owner using independent review.
- Which wording controls can preserve causality and uncertainty faithfully?
- How should quiet strategic positions with diffuse consequences be handled
  when no single reply dominates? Keep them unresolved until tested.

## Offline pre-code audit

The literal c4 teaching example and pattern-led output are in section 2.
The user explicitly requested building the chain builder and testing c4 plus
new positions. The approved scope is an offline experiment, with player
behaviour measurement deferred until a future product trial. Existing search,
replay and piece-identity sources remain authoritative. No new numerical
teaching thresholds or ranking formula are locked; return candidate chains
with their evidence and unanswered challenges. Production and model use stay
deferred. Six game-separated new inputs were frozen before implementation
from the pressure-shape export, excluding the known prior samples and known
regression game IDs. This is a deliberately narrow sample, not a population
quality estimate.
