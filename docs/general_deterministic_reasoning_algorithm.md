# General deterministic reasoning: executable design

Status: proposed offline implementation, 2026-10-30. No inference core described here has been implemented in this pass. The [audit](general_deterministic_reasoning_audit_2026_10_30.md) distinguishes existing code and reproduced results from this proposal. The [spec](general_deterministic_reasoning_spec.md) defines milestones and integration gates.

## 1. Contract and outcomes

```python
explain_fen(fen, played_move=None, player_level=1200, history=None,
            *, config, analysis_store=None) -> ExplanationResult
```

Accept standard-chess FENs passing syntax and `board.is_valid()` checks, with optional legal UCI/SAN played move. This validates board/rule consistency, not complete historical reachability. Reject illegal moves explicitly; never substitute a different stored SAN. Terminal positions still return context. FEN-only mode produces position context and useful choices, without inventing a played decision or intention. Rating affects teaching selection and wording, not chess truth. Optional history must reconstruct the supplied FEN; otherwise reject its use and mark history unavailable. Never infer repetition history, previous intentions, or “you moved this twice” from a standalone FEN. Halfmove and castling rights present in the FEN are available rule facts.

Separate `status` from `evidence_class`:

| Status | Meaning | Maximum default wording |
|---|---|---|
| `supported_consequence` | A useful outcome is demonstrated within recorded continuations, but the decision-to-outcome mechanism is not sufficiently established | “In this line, …”; engine mate may be “the engine finds mate” |
| `supported_mechanism` | A decision-specific dependency connects premises to an outcome, with named challenges completed within scope | “This keeps … available against the replies checked” |
| `incomplete_hypothesis` | An objective/connection is plausible but a required search or premise is missing, unstable, or unresolved | Exact context only; do not present the hypothesis as the reason |
| `insufficient_evidence` | No useful supported account; includes budget exhaustion and unavailable analysis | Short abstention with a machine-readable reason |

Refuted hypotheses are separately returned, including their counterexamples. An accepted consequence can coexist with rejected mechanisms. Do not convert low coverage into apparently complete coaching by relabelling context as explanation.

## 2. Minimal typed evidence model

Extend `stored_line_verifier` and the replay/branch transport from `candidate_caption_evidence`. Keep evidence data outside sentence renderers. Existing public dataclasses need versioned additions/adapters, not a silent incompatible change.

```text
PieceId = (root_position_id, color, root_square, root_piece_type)
PieceState = {id, color, current_type, square?, alive, promoted_from?}
PositionNode = {id, fen_all_6_fields, history_digest?, history_known,
                piece_states, snapshot_id, incoming_event_ids[]}
MoveEvent = {id, parent, child, ply, actor, move_uci, move_san,
             moved_piece_id, captured_piece_id?, captured_square?,
             promotion_transition?, castling_rook_event?,
             added_relation_ids[], removed_relation_ids[], retained_snapshot_id}
Score = Cp(value, fixed_root_pov) | Mate(winner, distance, distance_unit)
        | ExactOutcome(wdl, dtz?, rules_context) | Unknown(reason)
SearchRecord = {id, node_id, root_moves_uci[], purpose, engine_manifest_id,
                limit, actual_nodes, completed_depth, score, bound_kind,
                pv_events[], enumerated_legal_moves[], searched_moves[],
                omitted_moves[], pruned_nodes, leaf_stop_reasons[], runtime}
Relation = {id, subject, predicate, object, node_id, actor?, modality,
            geometry_or_rule_details, evidence_ids[]}
Objective = {id, beneficiary, kind, bound_entities, success_predicate,
             failure_predicate, horizon, source_ids[], proposed_status}
Hypothesis = {id, operation, root_move_uci, contrast_move_set[], objective_id,
              premises[], decision_links[], outcome_ids[], query_ids[],
              counterexamples[], status, permitted_strength}
Proposition = {id, subject, relation, object, node_or_event_id, ply?, actor,
               polarity, quantifier, evidence_class, evidence_ids[], scope_id}
```

Piece IDs identify pieces **at the supplied root**, not their actual starting-game identities. IDs follow moves, including both castling pieces. En passant removes the pawn on its actual capture square. A promoted pawn retains its lineage ID with a type transition; it never becomes indistinguishable from an original queen. The current replay already handles much of this (`stored_line_verifier.py:669-751`); add explicit type transitions and branch-wide identity propagation. Cross-branch transpositions may share analysis only when rule state/history are compatible; keep a mapping of lineage IDs rather than merging distinct pieces because their types/squares match.

Every node exposes a complete immutable snapshot or a root snapshot plus replayable deltas. Unchanged enabling facts remain addressable; they must not disappear merely because `relation_changes` omits them. Evidence references use node/event IDs, not ambiguous “at move 13.”

### Modalities must be mechanically distinct

| Representation | Exact meaning | How obtained |
|---|---|---|
| `geometric_attack(piece,square)` | Piece's attack geometry under current occupancy; may include a pinned piece | `board.attacks/attackers`, with pin annotations |
| `coverage(piece,square)` | Same geometric relation to an occupied or empty square | Snapshot, not attack counts alone |
| `legal_action(actor,move)` | Legal for the actual side to move, including check/pin/EP/rights rules | Enumerate `board.legal_moves` on that actual node |
| `checking_action(move,king)` / `legal_capture(move,piece)` | Legal move gives check/captures that identity | Legal replay plus rule check |
| `searched_acceptable(action,objective)` | Restricted search supports the action/outcome under named budget, responses, and comparison | `SearchRecord`; never a board fact |
| `only_legal_reply(move)` | Complete legal enumeration at that exact node contains one move | Exact rule fact |
| `only_reply_avoiding(C,move)` | Every other legal reply has a demonstrated C outcome under the explicitly stated proof/search scope | Obligation table; no unknown replies permitted for an unqualified claim |
| `best_defence_found(move)` | Best among searched replies, with bounds and budget recorded | Engine/search evidence |

Do not flip `board.turn` and call the resulting actions currently legal. For the other color, geometry may suggest an opportunity, but legal status is measured when a real legal continuation gives that color the turn. Artificial turn/null probes are labelled interventions.

Additional typed facts:

- **Responsibilities:** `duty(piece, relation_or_resource, threatened_outcome)`. Proposed from an opponent opportunity, then tested by legal ways to abandon/maintain the duty; geometric defence alone is only a seed.
- **Lines:** slider ray endpoints, blocker identities, opened/closed segments and newly revealed targets. Name both occupancy and legal-action effects.
- **King:** adjacent geometric coverage, currently legal king moves, other legal check evasions, and searched safe destinations as separate fields. “No king move” does not mean mate.
- **Material:** exact capture/promotion ledger by identity and a separately bounded settled outcome. CP assessment is not material.
- **Pawns:** file/rank, legal push/capture, passed/isolated/doubled relations, neighboring pawn contacts, candidate breaks, resulting lines/targets. A candidate break requires a real legal sequence and response investigation.
- **Routes/restrictions:** piece, target/entry square, obstruction identities, projected route, actual witnessed route events, opponent interruption resources, and acceptance status. Geometric reachability is a suggestion, not a safe route.
- **Exchanges:** offered/taken/declined captures, surviving identities, resulting structural predicates and opponent alternatives. Material equality alone does not decide whether an exchange is favourable.

Coverage transitions compare the same piece lineage and target at the correct nodes: `gained` = absent before/present after; `maintained` = present both; `abandoned` = present before/absent after. `alternative_would_add` refers to another legal root's timeline and never rewrites the original before-state. Tactical responsibility has a separate transition from mere coverage.

## 3. Search service and reproducibility

Introduce one offline `ReasoningSearchSession` adapter. Do not reuse the adjustable-strength warm coach opponent. Its interface accepts explicit `SearchQuery` data and returns typed `SearchRecord` objects:

```text
Q_RANK(node, candidate_count, node_budget)
Q_MOVE(node, one_legal_root_move, node_budget)
Q_REPLY(node, root_move_set, node_budget, requested_width)
Q_OBJECTIVE(node, objective, policy_constraints, search_budget)
Q_SETTLE(node, capture_ledger, unresolved_resources, forcing_budget)
Q_INTERVENE(node, edit, diagnostic_budget)  # never legal-history evidence
```

For example, `Q_MOVE` invokes `engine.analysis(board_with_available_history, Limit(nodes=N), root_moves=[move])`. Capture the last complete unbounded iteration; retain incomplete/bound information independently. `Q_RANK` snapshots require all reported ranks from one completed iteration with distinct roots, as demonstrated by the audit probe. Root enumeration and root verification have different purposes; do not infer absent played scores from rank cutoff.

Mandatory played analysis is its own `Q_MOVE`, regardless of ranking, severity, score size, or whether an interesting explanation has already been found. Discover strong alternatives through `Q_RANK`, then verify each compared root with the same independent budget policy. A MultiPV ranking query alone does not allocate equal search to every root. Store roots missing complete results as unknown, never “bad.”

Comparative acceptance is a function of typed scores and a versioned policy: finite CP roots are provisionally near-equivalent when their completed scores differ by at most `config.equivalence_cp` at both investigation budgets; a bound, a CP/mate change or inconsistent ordering outside that band makes the comparison unresolved. Mate wins/losses remain distinct ordered score classes; mate distances can rank resistance within a class but are never subtracted from CP. For a proposed action at a later node, obtain that actor's best unrestricted score and its restricted action score under the same policy. Mark it `searched_acceptable` only when the comparison and the objective predicate both pass. This assessment is bounded search evidence, not a theorem of soundness. The policy values must be calibrated/frozen on development data, not inferred from the three examples here.

Pin engine binary and NNUE hashes, python-chess version, CPU/build identifier, all effective UCI options, Threads=1, Hash, engine strength options, tablebase files/rules if any, process/hash-reset policy, node budgets, query order, legal-move order, generator/verifier/render versions and configuration digest. Canonical sort order is UCI and stable evidence IDs. Use fresh processes per query initially; only adopt a clear-hash/ucinewgame pool after byte-level repeat and query-order tests establish its contract. Wall time/RSS are metadata, excluded from deterministic-result equality.

Use all six FEN fields plus available history/rule context in cache identity; current caption lookups using four fields must not define this engine's cache contract. Keep terminal/repetition/50-move claims scoped to known history and rules. Engine tablebase evidence is optional; this audit did not verify a local Syzygy installation.

## 4. Executable candidate generation

No detector per complete chess story. Use a finite **objective grammar**, rule-derived action prerequisites, and bounded joining/search. Adding a new chess fact primitive can improve coverage; composing old primitives must not require another named detector.

### 4.1 Enumerate roots and obtain seeds

1. Validate FEN/history and enumerate **all legal root moves**. Always include the played root. Derive immediate geometry/rule deltas for every legal move; this is cheap and gives quiet roots a chance before engine ranking.
2. Search root rankings, near-equivalent candidates, and played move. Add relevant natural roots from legal checks/captures/recaptures/pawn breaks, direct duty responses, legal same-piece destinations, and route-unblocking moves. An existing pinned human-policy model may propose candidates, but its output cannot be chess evidence; record its version/context or omit it.
3. Replay legal returned branches with events. Seed objectives from **any ply**, not only leaf material: mate/promotion/capture/exchange, a checking resource, a legal entry square, a useful pawn break, a retained defence, a route reaching activity, castling availability, or an irreversible structure change.
4. Also seed unobserved quiet objectives from board enumeration: potential pawn contact breaks; slider entry squares on openable rays/files; targets reachable by short piece routes; exchange offers changing a diagnosed restriction; king routes to pawns; passed-pawn block/advance routes; castle prerequisites. These remain proposals until alternating legal search finds support.

Finite objective terms are `Achieve(action_or_event)`, `Reach(piece,target,constraints)`, `Avoid(opponent_resource,outcome)`, `Preserve(relation_or_option)`, and `Transform(piece_set,structure_predicate)`. Objects are actual board entities, legal actions or rule-defined predicates, not names such as “play actively.” The generator records the source of each objective and negative results too.

### 4.2 Extract prerequisites and join them with events

For each seeded action, produce its executable prerequisite set: actor to move, source identity present, correct movement, target occupancy/capture identity, all required empty ray squares, promotion rank, EP/castling rights, and own-king legality after replay. A checking action additionally has the post-move king attack relation. Promotion consequences bind the promoting actor and actual promoted type. Do not treat these legal prerequisites as proof of tactical effectiveness.

Build a dependency index from `(entity_or_square, predicate, node)` to facts/events that establish, preserve or destroy each prerequisite. Walk the actual timeline backward from the candidate outcome, not an abstract reverse chess search. For each satisfied prerequisite:

- If the chosen move establishes it while the played/contrast branch does not, propose **ENABLE**.
- If it remains true only because a root retains a duty/option that another root loses, propose **PRESERVE**.
- If the relevant prerequisite belongs to an opponent resource and is removed or made ineffective, propose **PREVENT**.
- If it belongs to a later own action and requires intervening play, propose **PREPARE**.
- If overlapping actions compete for turn order or a forcing reply, enumerate their legal orderings and propose **SEQUENCE**.
- If an exchange/pawn transformation creates the target structure or route, propose **TRANSFORM**.

A prerequisite that was already true becomes a retained premise. It cannot be described as created by the decision. Candidate explanation = a root event linked to at least one supported downstream objective through these premises; a collection of feature differences is not enough.

### 4.3 Generate missing quiet connections with an actual search

For `Reach(piece,target)` compute a relaxed movement-distance index to suggest paths, with blockers and destination occupancy. Then execute bounded best-first **alternating legal** search, using states `(board_with_history, objective_state, own_moves_spent, lineage_mapping)`:

- Own children: legal moves on a proposed route, legal moves removing its blockers, engine strong choices, and all legal checks/captures/necessary responses affecting its duty. If the objective requires proving necessity, enumerate every legal own alternative instead of this reduced set.
- Opponent children: strong engine replies plus legal checks/captures/promotions, captures/blocks/attacks on the objective's entities/path/king, relevant pawn breaks, and counterexamples previously found for this hypothesis.
- Advance objective state only by rule-checked events. Deduplicate with full rule/history context and canonical IDs. A route is successful only on witnessed legal nodes; a fixed path is replaced by a conditional policy when the opponent interrupts it.
- Queue order is deterministic: unresolved verification obligation, objective progress, then canonical UCI. Node, own-move and branch budgets bound expansion. Record reduced move sets; failure to find a route is not proof no route exists.

For structure objectives, replace route progress with specific persistent predicates and the resources they enable: e.g. removing a pawn blocker enables a rook entry which survives a tested challenge. Enumerate opposing pawn captures/breaks that can change the predicate. Label permanent only where the rule supports permanence; “our pawns can never guard this square” must account for future captures changing files, not just same-file forward pushes.

Intervention seeds are optional: edit only entities adjacent to an unresolved prerequisite/delta, using the existing teleport/pass/remove utilities and a fixed edit budget. Record validity and all changed rule/material state. A score swing can prioritize another **legal** investigation; it cannot discharge a legal dependency, prove necessity, or allocate a percentage of the original loss.

### 4.4 Orchestrator and objective-search semantics

```python
root = validate_and_bind_input(fen, played_move, history)
ledger.reserve_mandatory_played_query()
played_record = Q_MOVE(root, played_move, config.root_nodes) if played_move else None
ranking = Q_RANK(root, config.rank_width, config.rank_nodes)
roots = canonical_union(played_move, ranking.roots, natural_roots_from_legal_deltas(root))
records = verify_compared_roots(roots, ledger, config)  # skipped roots explicitly unknown
timelines = canonical_replay(records.complete_legal_lines, include_snapshots=True)
seeds = canonical_union(observed_event_objectives(timelines), board_objectives(root, roots))
worklist = join_action_prerequisites_to_events(seeds, timelines)
while worklist and ledger.can_expand():
    h = worklist.pop_canonical_obligation()
    h.add(verify_exact_premises(h))
    h.add(search_legal_objective_policy(h, ledger))
    h.add(challenge_outcome_and_plan(h, ledger))
    h.add(challenge_with_adequate_alternative_roots(h, ledger))
    if h.has_unresolved_tactical_tail:
        h.add(Q_SETTLE(h.tail_node, h.capture_ledger, h.resources, ledger.remaining))
    if h.can_support_a_claim and ledger.can_run_stability_check():
        h.add(recheck_roots_and_critical_resources_at_larger_budget(h))
    classify_hypothesis_and_cap_strength(h)  # unknown stays unknown
    worklist.extend(type_compatible_joins_of_newly_supported_propositions(h))
verified = independently_verify_all_proposed_propositions_and_dependencies()
return select_point_and_render_frames(verified, complete_scope_ledger(), manifest())
```

`search_legal_objective_policy` is a bounded AND/OR search over the actual children described in §4.3. For a beneficiary's goal, an own-turn node is OR: one legal acceptable continuation can witness an option. A defender-turn node is AND **over the enumerated challenge set**: every such reply must have a successful continuation to support that scoped policy. Reverse these roles for avoidance queries. A counterexample is the actual reply/policy whose objective predicate fails while its assessment is adequate, or any legal contrary reply when the claim is universal. Each leaf is `goal_satisfied`, `counterexample`, or `unknown`; reaching a horizon with the goal unresolved is unknown, never success or refutation.

Goal predicates are executable over events/states: `captured(target_id)`, `checkmated(color)`, `promoted(pawn_id,type)`, `legal_entry(piece_id,square)` plus the action's searched-acceptability check, a bound pawn-topology predicate, or a conjunction/explicit disjunction of these. Material goals additionally require the settlement obligation; a captured piece is not necessarily material won. Quiet goals require a specified usable resource after the structure/route change, rather than a feature-count increase. A node with all legal moves enumerated but only some continuations expanded is recorded as partial. AND/OR over a reduced reply set can produce only searched-scope support.

The hard stops are `max_queries`, `max_total_engine_nodes`, `max_expanded_legal_nodes`, `max_events_per_branch`, `max_hypotheses`, `max_chain_edges`, and `max_interventions`, all in the manifest. Refutation stops that claim immediately; a terminal rule/tablebase result can close an obligation; otherwise budget exhaustion propagates unknown. Queries remain sequential in the initial prototype for reproducible admission and memory use. Total cost is explicitly the sum of query node budgets plus bounded legal expansion; memory is capped by retained nodes/events and measured process footprints. A later wall-time cancellation is an external incomplete outcome with its own metadata, not a silent change in the deterministic success rule.

## 5. Operations, verification queries, and costs

Here `L(n)` is the number of legal moves at node n, `R` the configured relevant reply set, `N` an engine node budget, and `H` a legal timeline horizon. Caps are named configuration parameters, not production numbers selected in this document. Each operation pays against one shared query/node/branch ledger.

### ENABLE

- **Precondition:** action A has a rule prerequisite or effective-use condition that differs after candidate m and contrast a.
- **Enumeration:** join added/removed occupancy, ray, coverage, legal-check/capture or reply-window facts to A's prerequisites; include A observed later or suggested by an objective search.
- **Connection:** m establishes a prerequisite for A; A supports objective O. Both links need evidence.
- **Tests:** `Q_MOVE` for m/a; `Q_OBJECTIVE` searches A against R; search legal alternatives to m that preserve A and legal replies that remove A or make it unsound.
- **Refutation:** prerequisite does not actually differ; A was already effective; A fails against an adequate defence; an equally good contrast reaches O without the alleged prerequisite.
- **Strength:** legal availability can be exact; effective availability is searched, scoped to replies. Never “wins” from geometry alone.
- **Cost/stop:** geometry joins plus up to `|R| * N` before reuse; stop on refutation, resolved obligations, or ledger cap, yielding incomplete when capped.

### PREVENT

- **Precondition:** identifiable opponent resource A succeeds or creates a supported risk in a legal contrast branch.
- **Enumeration:** opponent legal actions at their actual-turn nodes, checking/capture opportunities, entry routes, pawn breaks and continuing threats in compared lines; join root changes to A's prerequisites.
- **Connection:** m blocks A, removes its tactical effect, or answers its consequence.
- **Tests:** search A after each root wherever legal; search replacement resources and sacrificial/zwischenzug responses, not just the named move.
- **Refutation:** A was unsound already; m merely delays A harmlessly; A or a substitute still achieves O; a strong non-preventing alternative holds equally well.
- **Strength:** “makes A illegal” can be exact at one node; “answers the threat” needs searched effectiveness. “Only defence” needs all alternatives accounted for.
- **Cost/stop:** up to root count times relevant resources times N; stop at the first adequate defeating resource or at cap. Resource absent from a PV is not prevented.

### PRESERVE

- **Precondition:** an existing relation/option R enables O, and a contrast abandons or disrupts its effective use.
- **Enumeration:** retain unchanged snapshot facts on outcome prerequisite paths; compare legal moved supporters, blocking moves, duty transfers and destination coverage. Include maintained protection, not only new protection.
- **Connection:** m keeps R available at the time O matters; a loses it. The mere existence of a defended piece is not a duty.
- **Tests:** direct attack/capture/entry on the protected target; legal duty-abandoning alternatives; counter-defences that replace the supporter; route/timing checks while retaining R.
- **Refutation:** lost protection has no supported consequence; another supporter replaces it; sacrifice is adequate; a lost relation remains true; O is independent of R.
- **Strength:** exact maintained coverage plus searched responsibility. Do not report an unchanged fact as the mistake itself.
- **Cost/stop:** dependency-path joins plus `|R| * N` for each nominated duty, capped by the shared hypothesis ledger.

### PREPARE

- **Precondition:** a future action F is supported after m, with an identifiable prerequisite m creates/preserves, and is unavailable or ineffective without that preparation.
- **Enumeration:** actual later line actions plus quiet route/pawn-break/exchange objectives, joined to prerequisite differences. Both sides' preparation may be relevant.
- **Connection:** m -> prerequisite -> legally reachable F -> benefit O, with opponent turns between them explicitly represented.
- **Tests:** alternating route/policy search; opponent immediate breaks, occupation of the entry square, exchanges of the relevant piece, and strong neutral replies; compare playing F immediately when legal.
- **Refutation:** F works immediately; a strong reply defeats F and no useful adaptive policy survives; m adds no needed prerequisite; equally strong alternatives show the alleged urgency is absent.
- **Strength:** “prepares F against these responses” or “keeps F as an option.” No claim of actual player intent.
- **Cost/stop:** up to `O((own_branch_cap * |R|)^H)` without memoisation, therefore strictly capped by expanded nodes/own moves/query ledger. A relaxed route alone never resolves the operation.

### SEQUENCE

- **Precondition:** at least two candidate actions share entities, obligations or a reply window; legal ordering can change a capture, defence or intermediate check.
- **Enumeration:** pairs of events on dependency paths plus legal forcing moves at the contested node. Enumerate orderings by replaying them; never transpose a move across an opponent turn without searching that turn.
- **Connection:** ordering A before B changes an exact prerequisite or reply set, which supports a different outcome.
- **Tests:** restricted first actions for both orderings, all legal evasions of any intermediate check, relevant non-capturing defences, alternatives that keep an attacked queen in place or sacrifice it acceptably.
- **Refutation:** both legal orderings achieve the same objective; an adequate defence avoids the alleged difference; one assumed action is illegal; only a passive reply makes the sequence work.
- **Strength:** exact legality/reply count, then scoped outcome comparison. “Must save the queen” requires rejecting legal adequate counter-actions.
- **Cost/stop:** `O(event_pair_cap * |R| * N)` with memoised continuations; stop after both orderings' critical obligations or cap. An exact one-reply node does not prove the earlier whole combination forced.

### TRANSFORM

- **Precondition:** an exchange or irreversible structural move changes material/structure/available routes in a way connected to O.
- **Enumeration:** legal captures/recaptures, exchange offers in searched lines, pawn contact moves and breaks; derive surviving pieces, pawn structure and newly opened/closed paths.
- **Connection:** transformation T removes a restriction or creates/retains a specific usable resource, rather than “the ending looks better.”
- **Tests:** accept/decline the trade, alternate recaptures, intermediate checks, simplification into actual endgame responses, competing pawn breaks and entry-route denial; tablebase only with explicit supported files/rules.
- **Refutation:** the opponent can decline without the alleged disadvantage; an alternate recapture reverses the benefit; a better counterbreak removes it; the feature survives but cannot be used.
- **Strength:** capture ledger/structural predicate exact; favourable outcome or persistent practical benefit searched. No claim every equal trade is good.
- **Cost/stop:** exchange tree up to all relevant recaptures/evasions, then `|R| * N` and a bounded route search. Stop unresolved at the horizon rather than banking transient material.

## 6. Composition and adversarial verification

Compose operations as **typed dependency hyperedges**. For example:

```text
vacate c3 -> open Bb2-d4 ray  [ENABLE]
Nd5 -> legal Nxe7+ resource [ENABLE]
Bb2-d4 ray + Nd5 resource + Bxe2 reply
    -> queen exchange with an intermediate check [SEQUENCE]
    -> extra bishop captured in demonstrated continuation [TRANSFORM/consequence]
```

An edge consumes actual proposition IDs bound to actor, piece lineage, node and timing, and produces another proposition. Repeatedly join newly accepted outputs to compatible operation preconditions using a worklist. Reject circular justifications and mismatched branches; “Bishop guards f5 at ply 2” cannot satisfy a requirement at ply 6 without retained coverage evidence. Stop at a configured chain/edge cap; preserve unfinished obligations. This permits new combinations without a detector for the entire story.

Accepted explanatory mechanisms require a decision-specific edge, a useful outcome, retained necessary premises, and **completed** verification obligations for their stated strength. A common background fact can be a premise; a common outcome can make the alleged disadvantage non-discriminating. A changed feature that distinguishes two moves is still only a candidate until the consequence link survives testing.

For each hypothesis, build the following explicit obligation table:

1. **Rule replay:** independently replay every event; regenerate the claimed geometry, actor, capture type, identity, check/reply count and transition from boards. Reject illegal suffixes, rather than retaining their attractive prefix as complete evidence.
2. **Defender avoids outcome:** at the earliest vulnerable node, try opponent strong moves, all checks/captures/promotions, direct saves/blocks/exchanges, quiet counter-threats relevant to the objective, and previously found refuters. For each selected reply use `Q_MOVE`/`Q_OBJECTIVE`. A legal defence that avoids the named outcome is a counterexample to “unavoidable,” even if it leads to a different bad outcome; either express the supported disjunction or weaken the original claim.
3. **Opponent defeats plan:** challenge the proposed plan's policy with pawn breaks, route interruption, removing a supporter, king escapes, declined trades, and equally strong neutral play. Search is asymmetric by the objective, not just “more of the same PV.”
4. **Alternative contradicts mechanism:** compare alternative roots that share the allegedly bad feature, and roots lacking the allegedly necessary feature. If an adequate alternative keeps the outcome, necessity fails. Equivalent plans receive neutral comparison, not invented criticism.
5. **Resolve tactics:** extend relevant material/check sequences adaptively, using the canonical bounded settlement as a starting tool. All check evasions are considered when in check; also search non-capturing forcing moves and relevant quiet defences. Fixed equal PV lengths and last-square recapture checks cannot close this obligation alone.
6. **Search stability:** re-search compared roots and critical challenges at the larger configured budget with fresh processes. Compare score classes and hypothesis outcome, not exact best-SAN equality. A rank flip among equivalent choices is not a refutation; a lost resource/mate transition or unresolved score bound is material instability.
7. **Competing accounts:** verify the strongest alternative objective explaining the same decision with different premises; reject a mechanism that is incidental, and retain multiple accounts when the evidence does not distinguish them.

Record every legal first-ply move enumerated, which received search, and what remains unknown deeper down. When a finite exhaustive verifier explores all required descendants to terminal/rule/tablebase outcomes, it may produce `exhaustive_within_rules`. Search of every legal move at one node, a bounded quiescence tree, and a Stockfish mate score are otherwise **different** evidence classes. A mate score can support “the engine finds mate,” without claiming this service has an independently exhaustive proof.

## 7. Quiet reasoning and teaching selection

Quiet reasoning is part of the first offline milestone. It uses the same operations and obligations:

| Need | Candidate source | Required connection and challenge |
|---|---|---|
| Plans gained/lost | Reachable own actions in compared continuations and route search | Which prerequisite/root move changes the usable plan; interrupt its route |
| Opponent pawn break | Legal pawn contacts/pushes in actual-turn nodes | Break opens a concrete line/target; test captures and delaying/ignoring it |
| Restricted piece | Geometric mobility/blocker facts, then legal routes | Show a realistic improvement and opponent denial; mobility count is insufficient |
| Entry square/duty | Slider rays, support identities, opponent route | Test occupation/capture/trade/coverage and duty transfer |
| Favourable exchange | Legal exchange tree and resulting structure | Accept/decline/alternative recaptures; show the resulting resource remains useful |
| Persistent structure | Exact pawn topology plus future opportunities | Test opponent breaks/captures; persistence of a feature alone is not benefit |
| Timing/preparation | Prerequisite chains and order permutations | Try the intended action now and after waiting; test opponent's intervening resource |
| Endgames | King/pawn routes, blocking, promotion, exchanges | Race timing, legal opposition/escape resources; exact outcome only when established |

After correctness gates, teaching selection can initially use a **draft deterministic lexicographic order**: evidence strength, verified decision connection, relevance to the biggest supported outcome, concrete transferable content appropriate to level, then shorter explanation and canonical ID. Compare this against a Pareto shortlist with reviewer selection during development; do not lock weights or this ordering without measured usefulness/coverage data. There is no largest-ablation-recovery rule and no exact allocation of a CP gap among stories.

If played and alternative are near-equivalent under stable analysis, say they offer different options. If the position was already losing, explain the best resistance/resource found and the additional consequence of this move; do not imply that the alternative saves the game. If stored severity disagrees with fresh stable search, return a reassessment outcome instead of rationalising the old label.

## 8. Structured result and controlled rendering

```text
ExplanationResult = {
  schema_version, status, reason_codes,
  input: {canonical_fen, played_uci?, player_level, history_status},
  context: {turn, material_ledger, checks, threats_with_scope, assessment},
  candidates: [{move_uci, roles[], assessment, equivalence_group?, search_ids[]}],
  objectives: [...], hypotheses: {accepted: [...], rejected: [...], incomplete: [...]},
  positions: [...], events: [...], relations: [...], propositions: [...],
  support: {continuations: [...], counterexamples: [...]},
  selected_teaching_point: {hypothesis_ids[], proposition_ids[], transfer_frame_id}?,
  coaching: {sentences: [{frame_id, proposition_ids[], bound_slots}], text},
  search_scope: {complete_obligations, unresolved_obligations, omitted_branches,
                 stopping_reasons, permitted_wording_strength},
  reproducibility: {manifest, config_digest, engine_hash, history_digest, query_log_digest},
  runtime: {wall_ms, cpu_ms, query_count, nodes, sampled_engine_rss, parent_rss,
            process_peak_method, cache_hits, cancelled_queries}
}
```

The independent proposition verifier checks subject/object identity and color, relation direction, negation/polarity, exact node/ply, before/after/alternative semantics, branch membership, dependency timing, evidence class and quantifier. Critical claims render only through closed sentence frames over verified proposition IDs. The renderer imports no chess library, calls no engine, and chooses no facts.

For example, a frame may say “In this line, your knight can take the bishop with check.” It requires accepted `legal_capture(knight,bishop)` and `gives_check(move,king)` propositions at the same event. “This wins a bishop” requires a separately settled/verified comparative outcome. “Only Kh8 is legal” requires the exact one-reply node. General teaching habits such as “Before moving an attacked queen, check for a stronger move” are non-position-specific advice, clearly separated from factual claims.

Arbitrary LLM rewriting cannot currently be reliably validated for semantic equivalence by the repository's validators. Do not add it to the prototype. Later, an LLM may select/order approved sentence frames or write connective non-chess language; critical factual spans remain controlled. A new subject, relationship, timing or necessity claim requires new structured acceptance, not a vocabulary pass.

## 9. Tactical walkthrough: Na4 versus Nd5

Root FEN: `r4rk1/ppp1bppp/5n2/4p3/1PPq2b1/P1N5/1B1PBPPP/R2QR1K1 w - - 0 13`.

**Local exact facts:** both knight moves vacate c3, opening Bb2's diagonal to Qd4. Thus that shared geometry alone cannot explain their difference. `Na4 Bxe2 Bxd4 Bxd1 Raxd1` is legal, exchanges queens, and has zero net material change under the audit's simple capture ledger. The queen does not have to escape after ...Bxe2.

**Additional resource:** Nd5 puts the same knight where it can capture Be7 with check. The legally replayed alternative `Nd5 Bxe2 Nxe7+ Kh8 Bxd4 Bxd1 Raxd1` finishes a bishop ahead. At the node immediately after Nxe7+, **Kh8 is the only legal reply**; that is an exact board fact. The branch does not prove ...Bxe2 forced at its earlier node.

**Search evidence:** fresh 600k-node root queries give Na4 +29 cp, Nd5 +410 cp. The current helper's depth-18 query finds Nd5 +388 and omits Na4 from its top eight; it returns no explanation. The searched best continuation actually orders the moves `Nd5 Bxe2 Bxd4 Bxd1 Nxe7+ Kh8 Bxe5 ...`, showing why the generator must examine ordering rather than memorialise a single fixture line. The reply investigation after Nd5 includes Bxe2, Qxb2, Nxd5 and Qxd5; Bxe2 is the best defence found at that budget, not the only legal move.

**Generated chain:** shared opened diagonal + new knight capture/check resource -> compare exchange orderings -> check forces a king reply at the critical point -> resolve material and remaining bishop/rook obligations. Discover this from identities, action prerequisites and event ordering, not a “Na4 detector.” Return `supported_consequence` for the demonstrated bishop-gain line; promote the full account to `supported_mechanism` only after the planned refutation obligations complete.

**Permitted sample coaching from this audit:** “Nd5 gives your knight a way to take the bishop on e7 with check during the queen exchange. Na4 misses that option. Before moving an attacked queen, look for a stronger move.” Do not claim the full combination forced from the root.

## 10. Quiet walkthrough: getting ready to castle

Root FEN: `rnbqk2r/pppp1ppp/5n2/2b1p3/2P5/2N3P1/PP1PPP1P/R1BQKBNR w KQkq - 1 4`; compare e4 with Nf3, Bg2 and d3.

**Board seeds:** White has castling rights; Ng1 and Bf1 still occupy its path. Bg2 is already legal because g2 was vacated; Nf3 also is legal. This gives a compound prerequisite objective for castling, independent of any intervention. d3 can open Bc1's route; it is another quiet objective, not evidence that every good move has one identical plan.

**Witnessed plan:** `Nf3 Nc6 Bg2 O-O O-O` is legally replayed. The exact root move clears g1 while maintaining castling rights; the bishop move clears f1; the actual later king move passes the attack/rights checks. Fresh single-root searches at 150k give Nf3 +28 and Bg2 +31; e4 -21. At 600k Nf3 +29 versus e4 -25. These are engine assessments, not a proof that castling timing accounts for exactly 54 cp.

**Useful counterexample:** the post-Nf3 reply search also finds **...e4** among strong replies. The line becomes `Nf3 e4 Nh4 O-O Bg2 ...`; the fixed “Bg2 then castle immediately” script fails to answer the knight attack. Another reply, ...Bd4, produces `Nb5 Nc6 Nbxd4 exd4 Bg2 ...`. The generator must search an adaptive policy that includes the knight response and verify the resulting plan against these resources.

**Conclusions:** legal route/available choices are exact. Development/castling is a reasonable seeded objective with searched witnesses; “e4 is bad because it delays castling” remains **incomplete as a causal account** until the mechanism survives the specified comparisons and challenges. Reject claims that Nf3 uniquely solves the position, that ...e4 is prevented by Nf3, or that extra geometric mobility equals safety.

**Permitted sample coaching now:** “Nf3 and Bg2 are useful options. They move pieces out of the king’s way. After Nf3, watch for ...e4 attacking the knight.” This explains a relevant choice and opponent resource without falsely allocating the entire evaluation difference. The future engine should report incomplete comparative reasoning rather than disguise it as a complete explanation of e4.

## 11. Qf8 and the remaining regression contract

Root FEN: `4r2r/2Q1bkq1/p2p3p/3Np3/4P3/3P1P2/PPP2P2/2K3RR b - - 2 24`. Exact coverage: Qg7->f5 **false**, Qf8->f5 **false**, Qh7->f5 **true**. Correct transition is **protection the alternative would add**, never protection abandoned by Qf8. Black is already badly behind in the local searches; Qh7 is better resistance found, not a rescue. At 600k nodes Qf8 receives mate-against-Black in 10, while Qh7 is -858 cp. The engine-provided mate line is a searched continuation; this service has not exhaustively established all its branches. No further tactical explanation is accepted from coverage alone.

Required development/regression groups, including explicit expected failures:

| Group | Fixture/evidence now | Required behavior |
|---|---|---|
| Attacked piece can be sacrificed | Audit Qa1 attacked / Re8# counterexample | Reject “must move” from attack counts; accept exact mate-in-one |
| Apparently forcing line has another defence | Nd5 has multiple legal Black replies; quiet ...e4 disrupts fixed castle route | Distinguish one legal reply at Nxe7+ from best defence at Nd5; retain counterexamples |
| Equal moves / different plans | Nf3 and Bg2 near-equivalent locally; add different-plan quiet pairs from new games | No arbitrary fault label; explain choice-specific options neutrally |
| Unchanged essential premise | Na4/Nd5 share Bb2 diagonal after vacating c3; castling rights are retained | Keep background enabling facts in dependency chains |
| Good move flagged as inaccurate | Inject stale loss on a freshly supported good root; later add actual stored reversals | Reassess, do not manufacture a mistake explanation; production reversals pending |
| Already losing | Qf8 root | Distinguish deterioration, mate discovery and resistance; no false saving claim |
| Material/identity/rule boundaries | Existing settlement fixtures plus promotion, castling, EP, underpromotion and pin transitions | Preserve identity/type/actor; reject un-settled or illegal claims |

Full cross-domain generalisation remains an experiment to conduct, not a result of these examples.
