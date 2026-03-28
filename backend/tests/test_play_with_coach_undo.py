import sys

import pytest

sys.path.insert(0, '/app/backend')

from services.opening_teaching_integration import undo_teaching_move


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


class _FakeDB:
    def __init__(self, doc):
        self.coach_sessions = _FakeCollection(doc)


@pytest.mark.asyncio
async def test_undo_teaching_move_rewinds_user_move_and_auto_reply():
    session_doc = {
        'session_id': 'lesson-1',
        'teaching_mode': 'main_line',
        'action_revision': 0,
        'current_fen': 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
        'teaching_data': {
            'variation_name': 'Italian lesson',
            'main_line_moves': ['e4', 'e5', 'Nf3', 'Nc6'],
            'current_move_index': 4,
            'user_plays_white': True,
            'lesson_start_fen': 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
            'teaching_fen': 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
        }
    }

    result = await undo_teaching_move(_FakeDB(session_doc), 'lesson-1')

    assert result['success'] is True
    assert result['current_move_index'] == 2
    assert result['instruction']['move'] == 'Nf3'
    assert session_doc['teaching_data']['current_move_index'] == 2


def test_regular_undo_history_truncation_logic():
    move_history = [
        {'move': 'd4', 'by': 'player', 'fen_before': 'start', 'fen_after': 'fen1', 'move_number': 1},
        {'move': 'd5', 'by': 'coach', 'fen_before': 'fen1', 'fen_after': 'fen2'},
        {'move': 'c4', 'by': 'player', 'fen_before': 'fen2', 'fen_after': 'fen3', 'move_number': 2},
        {'move': 'e6', 'by': 'coach', 'fen_before': 'fen3', 'fen_after': 'fen4'},
    ]

    last_player_index = next(
        index for index in range(len(move_history) - 1, -1, -1) if move_history[index].get('by') == 'player'
    )
    truncated_history = move_history[:last_player_index]
    restored_fen = move_history[last_player_index]['fen_before']
    previous_player_count = sum(1 for move in truncated_history if move.get('by') == 'player')

    assert last_player_index == 2
    assert restored_fen == 'fen2'
    assert [move['move'] for move in truncated_history] == ['d4', 'd5']
    assert previous_player_count == 1