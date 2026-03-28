import sys

import pytest

sys.path.insert(0, '/app/backend')

from services.opening_teaching_integration import check_opening_and_offer_teaching


class _FakeCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, query):
        if self.doc and self.doc.get('session_id') == query.get('session_id'):
            return self.doc
        return None

    async def update_one(self, query, update):
        if self.doc and self.doc.get('session_id') == query.get('session_id'):
            self.doc.update(update.get('$set', {}))


class _FakeProgressCollection:
    async def find_one(self, query):
        return None


class _FakeDB:
    def __init__(self, session_doc):
        self.coach_sessions = _FakeCollection(session_doc)
        self.user_opening_progress = _FakeProgressCollection()


@pytest.mark.asyncio
async def test_trap_offer_uses_exact_current_line_match():
    session_doc = {
        'session_id': 'trap-offer-1',
        'teaching_mode': None,
        'opening_offer_shown': False,
    }
    db = _FakeDB(session_doc)
    move_history = [
        {'move': 'e4'}, {'move': 'c5'}, {'move': 'Nf3'}, {'move': 'e6'},
        {'move': 'd4'}, {'move': 'cxd4'}, {'move': 'Nxd4'}, {'move': 'Nf6'},
        {'move': 'Nc3'}, {'move': 'Bb4'}
    ]

    offer = await check_opening_and_offer_teaching(
        db=db,
        session_id='trap-offer-1',
        move_history=move_history,
        user_color='white',
        user_id='user_test'
    )

    assert offer is not None
    assert offer['trap_name'] == 'Siberian Trap'
    assert offer['trap_available'] is True


@pytest.mark.asyncio
async def test_trap_offer_does_not_hallucinate_for_other_sicilian_branch():
    session_doc = {
        'session_id': 'trap-offer-2',
        'teaching_mode': None,
        'opening_offer_shown': False,
    }
    db = _FakeDB(session_doc)
    move_history = [
        {'move': 'e4'}, {'move': 'c5'}, {'move': 'Nf3'}, {'move': 'd6'},
        {'move': 'd4'}, {'move': 'cxd4'}, {'move': 'Nxd4'}, {'move': 'Nf6'},
        {'move': 'Nc3'}, {'move': 'a6'}
    ]

    offer = await check_opening_and_offer_teaching(
        db=db,
        session_id='trap-offer-2',
        move_history=move_history,
        user_color='white',
        user_id='user_test'
    )

    assert offer is not None
    assert offer['trap_available'] is False
    assert offer['trap_name'] is None