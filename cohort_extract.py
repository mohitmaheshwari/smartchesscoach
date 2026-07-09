"""
Extract deep per-user data for the >20-games cohort.
Writes /tmp/cohort.json inside the backend container.
"""
import os, asyncio, json
from collections import Counter
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

GAP_PRETTY = {
    'piece_safety': 'Hanging pieces (gives away unprotected material)',
    'missed_tactic': 'Misses tactics (forks/pins/skewers available)',
    'tactical_oversight': 'Sees one move ahead, misses the 2nd',
    'calculation_depth': 'Shallow calculation (needs deeper thinking)',
    'king_safety': 'King safety (slow castling, weak king)',
    'pawn_structure': 'Pawn-structure decisions (creates weaknesses)',
    'piece_activity': 'Passive pieces (poor coordination)',
    'time_pressure': 'Time-pressure blunders',
    'opening_knowledge': 'Drops out of opening theory early',
    'endgame_technique': 'Endgame conversion (loses winning endgames)',
}

async def main():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]

    pipeline = [
        {'$group': {'_id': '$user_id', 'total': {'$sum': 1}}},
        {'$match': {'total': {'$gt': 20}}},
        {'$sort': {'total': -1}},
    ]
    uids = []
    async for r in db.games.aggregate(pipeline):
        uids.append((r['_id'], r['total']))

    out = []
    for uid, total in uids:
        u = await db.users.find_one({'user_id': uid}) or {}

        analyzed = await db.games.count_documents({'user_id': uid, 'is_analyzed': True})

        cutoff_7  = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        cutoff_14 = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        cutoff_30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        r7  = await db.games.count_documents({'user_id': uid, 'imported_at': {'$gte': cutoff_7}})
        r14 = await db.games.count_documents({'user_id': uid, 'imported_at': {'$gte': cutoff_14}})
        r30 = await db.games.count_documents({'user_id': uid, 'imported_at': {'$gte': cutoff_30}})

        first_game = await db.games.find_one({'user_id': uid}, sort=[('imported_at', 1)])
        last_game  = await db.games.find_one({'user_id': uid}, sort=[('imported_at', -1)])
        first_at = first_game.get('imported_at') if first_game else None
        last_at  = last_game.get('imported_at')  if last_game  else None

        # Rating from most recent analyzed game
        rating = None
        cur = db.games.find({'user_id': uid, 'is_analyzed': True}, {'white_rating':1,'black_rating':1,'user_color':1,'date_played':1}).sort('date_played', -1).limit(3)
        async for g in cur:
            col = g.get('user_color')
            r = g.get('white_rating') if col == 'white' else g.get('black_rating')
            if r is not None:
                try:
                    rating = int(r)
                    break
                except (TypeError, ValueError):
                    pass

        # Win/loss/draw (last 30)
        wld = {'win':0,'loss':0,'draw':0,'unknown':0}
        async for g in db.games.find({'user_id': uid}, {'result':1,'user_color':1,'date_played':1}).sort('date_played', -1).limit(30):
            res = (g.get('result') or '').strip()
            col = g.get('user_color')
            if res == '1-0':
                if col == 'white': wld['win'] += 1
                elif col == 'black': wld['loss'] += 1
                else: wld['unknown'] += 1
            elif res == '0-1':
                if col == 'white': wld['loss'] += 1
                elif col == 'black': wld['win'] += 1
                else: wld['unknown'] += 1
            elif res in ('1/2-1/2','½-½'):
                wld['draw'] += 1
            else:
                wld['unknown'] += 1

        # Top cognitive gaps from last 30 analyses
        gap_counts = Counter()
        analyses = db.game_analyses.find({'user_id': uid}, {'move_evaluations':1}).sort('analyzed_at', -1).limit(30)
        async for a in analyses:
            for m in (a.get('move_evaluations') or []):
                if not m.get('is_user_move'): continue
                g = m.get('cognitive_gap')
                if g and g != 'none':
                    gap_counts[g] += 1
        top_gaps = gap_counts.most_common(5)

        # Top openings
        op_counts = Counter()
        async for g in db.games.find({'user_id': uid}, {'opening':1}).limit(300):
            op = g.get('opening')
            if op:
                if isinstance(op, dict):
                    op = op.get('name')
                if op:
                    op_counts[op] += 1
        top_openings = op_counts.most_common(5)

        prof = await db.player_profiles.find_one({'user_id': uid}) or {}
        ident = await db.player_identities.find_one({'user_id': uid}) or {}

        row = {
            'uid': uid,
            'name': u.get('name'),
            'email': u.get('email'),
            'chess_com': u.get('chess_com_username'),
            'lichess': u.get('lichess_username'),
            'rating': rating,
            'total': total,
            'analyzed': analyzed,
            'r7': r7, 'r14': r14, 'r30': r30,
            'first_at': first_at,
            'last_at': last_at,
            'win_loss_draw_last30': wld,
            'avg_accuracy': prof.get('avg_accuracy'),
            'top_gaps': [(GAP_PRETTY.get(g, g), n) for g, n in top_gaps],
            'top_openings': top_openings,
            'style': (ident.get('style_profile') or {}) if isinstance(ident.get('style_profile'), dict) else {},
            'top_weaknesses_profile': (prof.get('top_weaknesses') or [])[:5],
            'improvement_trend': prof.get('improvement_trend'),
        }
        out.append(row)

    with open('/tmp/cohort.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, default=str, indent=2)
    print(f'WROTE {len(out)} users to /tmp/cohort.json')

asyncio.run(main())
