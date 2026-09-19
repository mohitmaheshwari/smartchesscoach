"""Engine-free route/CAS regressions. In-memory Mongo boundary, not a live DB test."""
import asyncio
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import chess
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import routes.diagnostic as route
from services.diagnostic_service import DIAGNOSTIC_GRADE_VERSION, diagnostic_grade_fingerprint


ABSENT = object()


def get(doc, path):
    for part in path.split('.'):
        if not isinstance(doc, dict) or part not in doc:
            return ABSENT
        doc = doc[part]
    return doc


def matches(doc, query):
    for key, expected in query.items():
        actual = get(doc, key)
        if isinstance(expected, dict) and '$exists' in expected:
            if (actual is not ABSENT) != expected['$exists']:
                return False
        elif isinstance(expected, dict) and '$in' in expected:
            if actual not in expected['$in']:
                return False
        elif expected is None:
            if actual is not ABSENT and actual is not None:
                return False
        elif actual != expected:
            return False
    return True


class Collection:
    def __init__(self, docs):
        self.docs = deepcopy(docs)

    async def find_one(self, query, projection=None):
        return next((deepcopy(d) for d in self.docs if matches(d, query)), None)

    async def update_one(self, query, update):
        doc = next((d for d in self.docs if matches(d, query)), None)
        if doc is None:
            return SimpleNamespace(matched_count=0)
        for operator, fields in update.items():
            for path, value in fields.items():
                target = doc
                parts = path.split('.')
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                if operator == '$set':
                    target[parts[-1]] = deepcopy(value)
                elif operator == '$unset':
                    target.pop(parts[-1], None)
                elif operator == '$push':
                    target.setdefault(parts[-1], []).append(deepcopy(value))
                else:
                    raise AssertionError(operator)
        return SimpleNamespace(matched_count=1)


def pool_doc(multi=False):
    board = chess.Board()
    doc = {'puzzle_id': 'p1', 'concept': 'calculation' if multi else 'piece_safety',
           'tier': 'low', 'puzzle_rating': 850, 'fen': board.fen(),
           'moves': ['e2e4', 'e7e5', 'g1f3'] if multi else ['e2e4'],
           'grade_version': DIAGNOSTIC_GRADE_VERSION, 'step_grades': []}
    for index, move in enumerate(doc['moves']):
        if index % 2 == 0:
            doc['step_grades'].append({'fen': board.fen(), 'solution_uci': move,
                'grade_by_uci': {move: {'verdict': 'UNDERSTOOD', 'cp_loss': 0, 'eval_after_cp': 0}}})
        board.push_uci(move)
    doc['grade_fingerprint'] = diagnostic_grade_fingerprint(doc)
    return doc


def session_for(doc):
    return {'user_id': 'u1', 'version': 2, 'status': 'in_progress', 'started_at': 'session-one',
            'attempts': [], 'concept_order': [doc['concept']], 'concept_progress': {},
            'used_puzzle_ids': ['p1'], 'current': {'puzzle_id': 'p1', 'concept': doc['concept'],
            'tier': 'low', 'move_idx': 0, 'fen_current': doc['fen'], 'step_verdicts': []}}


@pytest.fixture
def setup(monkeypatch):
    def configure(multi=False, next_puzzle=True):
        puzzle = pool_doc(multi)
        session = session_for(puzzle)
        db = SimpleNamespace(diagnostic_sessions=Collection([session]), diagnostic_pool=Collection([puzzle]))
        monkeypatch.setattr(route, 'db', db)
        following = {**puzzle, 'puzzle_id': 'p2'} if next_puzzle else None
        monkeypatch.setattr(route, '_v2_pick_puzzle', AsyncMock(return_value=following))
        monkeypatch.setattr(route, '_user_analyzed_game_count', AsyncMock(return_value=0))
        monkeypatch.setattr(route, 'apply_diagnosis_v2_to_training', AsyncMock(return_value={}))
        req = route.AttemptRequest(puzzle_id='p1', user_move_san='e4',
                                   feedback_session=session['started_at'], feedback_fen=puzzle['fen'])
        return db, session, req
    return configure


def run(coro):
    return asyncio.run(coro)


def test_lost_response_is_replayed_without_double_counting(setup):
    db, _, req = setup()
    user = SimpleNamespace(user_id='u1')
    response = run(route.record_attempt(req, user))
    assert run(route.record_attempt(req, user)) == response
    assert len(db.diagnostic_sessions.docs[0]['attempts']) == 1
    route._user_analyzed_game_count.return_value = 999
    resumed = run(route.start_diagnostic(user))
    assert resumed['status'] == 'feedback'  # even after background analysis supersedes diagnostic
    assert resumed['feedback'] == response
    assert resumed['puzzle']['puzzle_id'] == 'p1'
    expected = chess.Board(req.feedback_fen)
    expected.push_san('e4')
    assert resumed['played_fen'] == expected.fen()
    assert 'step_grades' not in str(resumed)
    assert 'grade_by_uci' not in str(resumed)


def test_continue_is_idempotent_and_isolated_by_account(setup):
    db, _, req = setup()
    user = SimpleNamespace(user_id='u1')
    result = run(route.record_attempt(req, user))
    ack = route.FeedbackAcknowledgement(feedback_id=result['feedback_id'])
    with pytest.raises(HTTPException) as denied:
        run(route.acknowledge_feedback(ack, SimpleNamespace(user_id='other')))
    assert denied.value.status_code == 409
    assert 'pending_feedback' in db.diagnostic_sessions.docs[0]
    assert run(route.acknowledge_feedback(ack, user)) == result
    assert run(route.acknowledge_feedback(ack, user)) == result
    assert 'pending_feedback' not in db.diagnostic_sessions.docs[0]
    assert len(db.diagnostic_sessions.docs[0]['attempts']) == 1


def test_multistep_resume_preserves_answered_board_not_opponent_reply(setup):
    db, _, req = setup(multi=True)
    user = SimpleNamespace(user_id='u1')
    response = run(route.record_attempt(req, user))
    assert response['step_verdict'] == 'UNDERSTOOD' and response['verdict'] is None
    assert not db.diagnostic_sessions.docs[0]['attempts']
    resumed = run(route.start_diagnostic(user))
    assert resumed['played_fen'] != response['puzzle']['fen']
    assert db.diagnostic_sessions.docs[0]['current']['move_idx'] == 1
    assert run(route.record_attempt(req, user)) == response
    run(route.acknowledge_feedback(route.FeedbackAcknowledgement(feedback_id=response['feedback_id']), user))
    second = route.AttemptRequest(puzzle_id='p1', user_move_san='Nf3',
        feedback_session=req.feedback_session, feedback_fen=response['puzzle']['fen'])
    run(route.record_attempt(second, user))
    assert len(db.diagnostic_sessions.docs[0]['attempts']) == 1


def test_stale_concurrent_snapshot_cannot_write_twice(setup):
    db, snapshot, req = setup()
    first = run(route._v2_record_attempt('u1', deepcopy(snapshot), req))
    duplicate = run(route._v2_record_attempt('u1', deepcopy(snapshot), req))
    assert duplicate == first
    assert len(db.diagnostic_sessions.docs[0]['attempts']) == 1


@pytest.mark.parametrize('field,value', [('feedback_session', 'wrong'), ('feedback_fen', 'wrong')])
def test_stale_identity_or_board_is_rejected_without_mutation(setup, field, value):
    db, original, req = setup()
    req = req.model_copy(update={field: value})
    with pytest.raises(HTTPException) as denied:
        run(route.record_attempt(req, SimpleNamespace(user_id='u1')))
    assert denied.value.status_code == 409
    assert db.diagnostic_sessions.docs[0] == original


def test_final_answer_and_feedback_are_saved_together(setup):
    db, _, req = setup(next_puzzle=False)
    user = SimpleNamespace(user_id='u1')
    response = run(route.record_attempt(req, user))
    assert response['status'] == 'complete'
    assert db.diagnostic_sessions.docs[0]['status'] == 'complete'
    assert run(route.start_diagnostic(user))['feedback'] == response
    assert run(route.record_attempt(req, user)) == response
    ack = route.FeedbackAcknowledgement(feedback_id=response['feedback_id'])
    # A failed profile projection leaves the receipt recoverable.
    route.apply_diagnosis_v2_to_training.side_effect = RuntimeError('unavailable')
    with pytest.raises(RuntimeError):
        run(route.acknowledge_feedback(ack, user))
    assert 'pending_feedback' in db.diagnostic_sessions.docs[0]
    route.apply_diagnosis_v2_to_training.side_effect = None
    run(route.acknowledge_feedback(ack, user))
    assert route.apply_diagnosis_v2_to_training.call_args.kwargs == {'record_weakness': False}
    assert len(db.diagnostic_sessions.docs[0]['attempts']) == 1


def test_different_answer_cannot_replace_unread_feedback(setup):
    db, _, req = setup()
    run(route.record_attempt(req, SimpleNamespace(user_id='u1')))
    changed = req.model_copy(update={'user_move_san': 'd4'})
    with pytest.raises(HTTPException):
        run(route.record_attempt(changed, SimpleNamespace(user_id='u1')))
    assert len(db.diagnostic_sessions.docs[0]['attempts']) == 1


@pytest.mark.parametrize('last', [False, True])
def test_legacy_puzzle_feedback_is_also_atomic_and_resumable(setup, monkeypatch, last):
    db, _, req = setup()
    session = {'user_id': 'u1', 'status': 'in_progress', 'started_at': 'session-one',
               'puzzle_ids': ['p1'] if last else ['p1', 'p2'], 'attempts': []}
    db.diagnostic_sessions = Collection([session])
    db.community_puzzles = Collection([{'_id': 'p2', 'fen': chess.Board().fen()}])
    import services.verified_puzzle_runtime as runtime
    monkeypatch.setattr(runtime, 'resolve_verified_puzzle', AsyncMock(return_value={
        'fen': chess.Board().fen(), 'issue_type': 'piece_safety', 'difficulty': 'easy'}))
    monkeypatch.setattr(runtime, 'grade_resolved_puzzle', lambda *a: {
        'correct': True, 'quality': 'good', 'best_move_san': 'e4', 'feedback': 'Verified fixture.'})
    user = SimpleNamespace(user_id='u1')
    response = run(route.record_attempt(req, user))
    assert response['status'] == ('complete' if last else 'in_progress')
    assert response['is_correct'] is True
    assert run(route.record_attempt(req, user)) == response
    assert run(route.start_diagnostic(user))['feedback'] == response
    assert len(db.diagnostic_sessions.docs[0]['attempts']) == 1


def test_feedback_copy_does_not_turn_capture_or_theme_into_material_or_mastery_claim():
    grader = route.DiagnosticGrader()
    # Capturing a defended pawn is a capture, not proof of winning material.
    fen = '4k3/8/4p3/3p4/2B5/8/8/4K3 w - - 0 1'
    board = chess.Board(fen)
    assert board.is_valid()
    text = grader._generate_verdict_explanation({'concept': 'piece_safety'}, 'Bxd5', 'Bxd5',
        'UNDERSTOOD', is_exact=True, eval_after=-300, fen=fen, solution_uci='c4d5')
    assert 'captures the pawn' in text
    assert 'wins' not in text and 'nothing left hanging' not in text
    board.push_san('Bxd5')
    assert board.parse_san('exd5') in board.legal_moves
    alternate = grader._generate_verdict_explanation({'concept': 'mate_patterns'}, 'Kd2', 'Bxd5',
        'UNDERSTOOD', is_exact=False, eval_after=-300, fen=fen, solution_uci='c4d5')
    assert 'accepted' in alternate and 'on top' not in alternate and 'you saw' not in alternate


def test_checkpoint_on_explicit_session_does_not_add_weakness_occurrence(setup):
    db, _, req = setup()
    run(route.record_attempt(req, SimpleNamespace(user_id='u1')))
    run(route.exit_diagnostic(SimpleNamespace(user_id='u1'), checkpoint=True))
    assert route.apply_diagnosis_v2_to_training.call_args.kwargs == {'record_weakness': False}
    assert 'pending_feedback' in db.diagnostic_sessions.docs[0]


@pytest.mark.parametrize('v2', [False, True])
def test_repeatable_focus_projection_never_calls_weakness_counter(monkeypatch, v2):
    import services.diagnostic_service as service
    import player_profile_service as profiles
    monkeypatch.setattr(profiles, 'get_or_create_profile', AsyncMock(return_value={}))
    counter = AsyncMock()
    monkeypatch.setattr(profiles, 'update_weakness_tracking', counter)
    memory = SimpleNamespace(update_one=AsyncMock())
    db = SimpleNamespace(users=Collection([{'user_id': 'u1', 'name': 'Test'}]), coach_memory=memory)
    if v2:
        monkeypatch.setattr(service, 'score_diagnostic_v2', lambda session: {'headline_gap': 'piece_safety'})
        project = service.apply_diagnosis_v2_to_training
        evidence = {}
    else:
        monkeypatch.setattr(service, 'score_diagnostic', lambda attempts: {})
        monkeypatch.setattr(service, '_worst_issue_type', lambda diagnosis: 'piece_safety')
        project = service.apply_diagnosis_to_training
        evidence = []
    run(project(db, 'u1', evidence, record_weakness=False))
    run(project(db, 'u1', evidence, record_weakness=False))
    assert counter.await_count == 0
    assert memory.update_one.await_count == 2
    assert memory.update_one.await_args_list[0] == memory.update_one.await_args_list[1]


def test_http_contract_requires_auth_and_rejects_another_accounts_receipt(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    _, _, req = setup()
    result = run(route.record_attempt(req, SimpleNamespace(user_id='u1')))
    app = FastAPI()
    app.include_router(route.router)
    async def unauthorized():
        raise HTTPException(401, 'Authentication required')
    app.dependency_overrides[route.get_current_user] = unauthorized
    with TestClient(app) as client:
        body = {'feedback_id': result['feedback_id']}
        assert client.post('/diagnostic/feedback/continue', json=body).status_code == 401
        app.dependency_overrides[route.get_current_user] = lambda: SimpleNamespace(user_id='other')
        assert client.post('/diagnostic/feedback/continue', json=body).status_code == 409
        app.dependency_overrides[route.get_current_user] = lambda: SimpleNamespace(user_id='u1')
        assert client.post('/diagnostic/feedback/continue', json=body).json() == result
        assert client.post('/diagnostic/feedback/continue', json=body).json() == result


def test_delayed_final_continue_preserves_real_game_focus(setup):
    _, _, req = setup(next_puzzle=False)
    user = SimpleNamespace(user_id='u1')
    result = run(route.record_attempt(req, user))
    route._user_analyzed_game_count.return_value = 999
    assert run(route.start_diagnostic(user))['feedback'] == result
    run(route.acknowledge_feedback(route.FeedbackAcknowledgement(feedback_id=result['feedback_id']), user))
    route.apply_diagnosis_v2_to_training.assert_not_awaited()
