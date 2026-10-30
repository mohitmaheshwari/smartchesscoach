"""GPT-6-luna proposes connections from evidence; no automatic truth promotion."""
from __future__ import annotations

import json
import time

from .contracts import fingerprint
from .evidence import model_packet

MODEL = 'gpt-6-luna'  # Explicitly requested by the user; never silently substituted.
SYSTEM = '''You analyse one chess move for a player rated 600-1500 using supplied engine evidence.
The initial state describes every piece. Apply each state's field, piece and feature changes to its parent to reconstruct later states. Unchanged relationships remain true until changed. Piece identities persist when they move; a pawn replacing a knight on the same square is a different piece. Material contains exact counts, separately from engine scores.
Identify what the played move changes, how the opponent can use that change in a searched continuation, and how the best searched alternative differs. Connect the root move to the consequence. Do not simply praise the alternative, repeat a score difference, or label any feature loss bad without considering exchanges and compensation. If no clear connection is supported, abstain. No suggested reason is supplied.
Board attacks/defenders are geometric: attacked, undefended or pinned does not by itself prove a winning capture. Positional labels and their raw values are candidate evidence, not authoritative causes or centipawn attribution. A PV is a searched example. An event's legal_reply_count counts legal replies to the move just played; only a count of 1 establishes that the next reply is the only legal move. Retain uncertainty when searched replies differ or requested depth was not reached.
Use only moves, squares and pieces present in the evidence. Do not mix a consequence from one branch into another. A comparison must explicitly identify itself as a comparison. Every connection needs evidence references to states and piece IDs. An end-of-line statement must cite that branch's final state, not a temporary earlier state. Every material-balance statement must have a corresponding material_claim with the exact cited balance_cp_white.
Return JSON only with these fields:
decision: explain or abstain;
assessment: brief;
connections: list of {claim, branch_id (an existing B-id, or comparison), strength (direct_fact, conditional_line, or interpretation), evidence_refs: [{state_id: existing N-id, piece_ids: list of physical piece IDs present at that state or moving/captured in the move arriving there}]};
explanation: short natural English teaching text, with a transferable habit at the end when decision=explain;
material_claims: list of {state_id, balance_cp_white};
uncertainty: brief.
Do not output private deliberation. Refer to the played move's side accurately. Use everyday language in the explanation: name the square and describe what happens rather than relying on a technical label. Scores have explicit POV. Do not turn score differences into material lost. You may propose a conditional account, but do not invent a certain reason to avoid abstaining.'''


def check_proposal(packet, proposal):
    errors = []
    if not isinstance(proposal, dict):
        return {'passed': False, 'errors': ['response_not_object']}
    states = {s['id']: s for s in packet['states']}
    branches = {b['id']: set(b['state_ids']) for b in packet['branches']}
    arrivals = {key: set() for key in states}
    for branch in packet['branches']:
        for state_id, event in zip(branch['state_ids'][1:], branch['events']):
            arrivals[state_id].update(identity for identity in
                (event['moving_piece_id'], event['captured_piece_id']) if identity is not None)
    decision = proposal.get('decision')
    if decision not in ('explain', 'abstain'):
        errors.append('invalid_decision')
    for key in ('assessment', 'explanation', 'uncertainty'):
        if not isinstance(proposal.get(key), str):
            errors.append('missing_text_' + key)
    connections = proposal.get('connections')
    if not isinstance(connections, list):
        errors.append('connections_not_list'); connections = []
    if decision == 'explain' and (not connections or not isinstance(proposal.get('explanation'), str)
                                  or not proposal['explanation'].strip()):
        errors.append('explanation_without_connections')
    for index, connection in enumerate(connections):
        prefix = 'connection_' + str(index) + ':'
        if not isinstance(connection, dict):
            errors.append(prefix + 'not_object'); continue
        branch = connection.get('branch_id')
        if not isinstance(branch, str) or (branch != 'comparison' and branch not in branches):
            errors.append(prefix + 'unknown_branch')
        if not isinstance(connection.get('claim'), str) or not connection.get('claim', '').strip():
            errors.append(prefix + 'empty_claim')
        if connection.get('strength') not in ('direct_fact', 'conditional_line', 'interpretation'):
            errors.append(prefix + 'invalid_strength')
        refs = connection.get('evidence_refs')
        if not isinstance(refs, list) or not refs:
            errors.append(prefix + 'missing_evidence'); continue
        for ref in refs:
            if not isinstance(ref, dict) or not isinstance(ref.get('state_id'), str) or ref['state_id'] not in states:
                errors.append(prefix + 'unknown_state'); continue
            state = states[ref['state_id']]
            if isinstance(branch, str) and branch in branches and state['id'] not in branches[branch]:
                errors.append(prefix + 'cross_branch_evidence')
            ids = ref.get('piece_ids')
            if not isinstance(ids, list) or any(not isinstance(i, str) or
                    (i not in state['pieces'] and i not in arrivals[state['id']]) for i in ids):
                errors.append(prefix + 'unknown_or_stale_piece')
    claims = proposal.get('material_claims')
    if not isinstance(claims, list):
        errors.append('material_claims_not_list'); claims = []
    for claim in claims:
        if (not isinstance(claim, dict) or not isinstance(claim.get('state_id'), str) or claim['state_id'] not in states
                or isinstance(claim.get('balance_cp_white'), bool)
                or not isinstance(claim.get('balance_cp_white'), int)
                or claim['balance_cp_white'] != states[claim['state_id']]['material']['balance_cp_white']):
            errors.append('wrong_material_claim')
    return {'passed': not errors, 'errors': errors,
            'scope': 'shape, state/arrival-event identity, branch references and explicit material claims only; free-text entailment is not proven'}


async def propose_evidence_reasoning(packet, *, max_tokens, reasoning_effort=None, caller=None):
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError('max_tokens must be an explicit positive output allocation')
    view = model_packet(packet)
    payload = json.dumps(view, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    if reasoning_effort is None:
        from services.why_words import WHY_WORDS_EFFORT
        reasoning_effort = WHY_WORDS_EFFORT
    if caller is None:
        from llm_service import call_llm
        caller = call_llm
    result = {'schema_version': 'reasoning.position_proposal.v1', 'model': MODEL,
              'status': 'not_called', 'raw_response': None, 'proposal': None,
              'request': {'model': MODEL, 'reasoning_effort': reasoning_effort, 'max_tokens': max_tokens,
                          'input_characters': len(payload), 'input_digest': fingerprint(view),
                          'system_digest': fingerprint(SYSTEM)},
              'review': {'prose_factuality': 'not_checked', 'explanatory_relevance': 'not_reviewed'}}
    started = time.perf_counter()
    try:
        raw = await caller(SYSTEM, payload, model=MODEL, max_tokens=max_tokens, reasoning_effort=reasoning_effort)
    except Exception as exc:
        result.update(status='provider_error', error={'type': type(exc).__name__,
            'status_code': getattr(exc, 'status_code', None)})
        result['runtime_ms'] = round(1000 * (time.perf_counter() - started), 3)
        return result
    result['runtime_ms'] = round(1000 * (time.perf_counter() - started), 3)
    result['raw_response'] = raw
    try:
        if not isinstance(raw, str):
            raise TypeError('provider_result_is_not_text')
        text = raw.strip()
        if text.startswith('```json') and text.endswith('```'):
            text = text[7:-3].strip()
        proposal = json.loads(text)
    except (ValueError, TypeError):
        result.update(status='refused', checks={'passed': False, 'errors': ['invalid_json']})
        return result
    result['proposal'] = proposal
    result['checks'] = check_proposal(packet, proposal)
    result['status'] = 'unreviewed_proposal' if result['checks']['passed'] else 'refused'
    return result
