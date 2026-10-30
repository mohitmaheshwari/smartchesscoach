"""A model draft is never silently promoted to a verified chess explanation."""
import asyncio
import json
from importlib import import_module

from test_reasoning_evidence import sample


def api():
    return import_module('services.reasoning.evidence_words')


def response(packet):
    return {'decision': 'explain', 'assessment': 'A small concession in the supplied searches.',
        'connections': [{'claim': 'A relationship changes along the played line.',
            'branch_id': packet['branches'][0]['id'], 'strength': 'interpretation',
            'evidence_refs': [{'state_id': packet['initial_state_id'], 'piece_ids': ['black:pawn:g5']}]}],
        'explanation': 'Review the changed relationships before choosing a plan.',
        'uncertainty': 'The main reason requires independent review.', 'material_claims': []}


def test_exact_requested_model_receives_a_reason_free_lossless_packet():
    p = sample(); calls = []
    async def caller(system, user, **kwargs):
        calls.append((system, json.loads(user), kwargs))
        return json.dumps(response(p))
    result = asyncio.run(api().propose_evidence_reasoning(p, max_tokens=2000, caller=caller))
    assert calls[0][2]['model'] == 'gpt-6-luna'
    assert calls[0][1]['schema_version'].endswith('model.v1')
    assert result['status'] == 'unreviewed_proposal'
    assert result['review']['explanatory_relevance'] == 'not_reviewed'
    assert result['raw_response']


def test_unknown_state_or_piece_is_refused_with_raw_output_retained():
    p = sample(); value = response(p)
    value['connections'][0]['evidence_refs'][0]['state_id'] = 'invented'
    async def caller(*args, **kwargs): return json.dumps(value)
    r = asyncio.run(api().propose_evidence_reasoning(p, max_tokens=2000, caller=caller))
    assert r['status'] == 'refused'
    assert r['raw_response'] and r['checks']['errors']


def test_cross_branch_evidence_cannot_be_called_a_single_branch_consequence():
    p = sample(); value = response(p)
    value['connections'][0]['evidence_refs'][0]['state_id'] = p['branches'][1]['state_ids'][1]
    async def caller(*args, **kwargs): return json.dumps(value)
    r = asyncio.run(api().propose_evidence_reasoning(p, max_tokens=2000, caller=caller))
    assert r['status'] == 'refused'


def test_wrong_structured_material_claim_is_refused():
    p = sample(); value = response(p)
    value['material_claims'] = [{'state_id': p['initial_state_id'], 'balance_cp_white': 0}]
    async def caller(*args, **kwargs): return json.dumps(value)
    r = asyncio.run(api().propose_evidence_reasoning(p, max_tokens=2000, caller=caller))
    assert r['status'] == 'refused'
    assert any('material' in e for e in r['checks']['errors'])


def test_provider_errors_are_visible_and_do_not_leak_keys_or_generate_fallback_text():
    async def caller(*args, **kwargs): raise RuntimeError('secret-api-key')
    r = asyncio.run(api().propose_evidence_reasoning(sample(), max_tokens=2000, caller=caller))
    assert r['status'] == 'provider_error'
    assert r['raw_response'] is None
    assert 'secret-api-key' not in json.dumps(r)


def test_invalid_json_is_retained_and_refused():
    async def caller(*args, **kwargs): return 'This is not a structured result.'
    r = asyncio.run(api().propose_evidence_reasoning(sample(), max_tokens=2000, caller=caller))
    assert r['status'] == 'refused' and r['raw_response']
