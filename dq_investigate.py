"""
Data-quality investigation: verify each finding with evidence.
For each issue: schema sample, distribution, root-cause check, fix location hint.
"""
import os, asyncio, json
from collections import Counter
from motor.motor_asyncio import AsyncIOMotorClient

OUT = '/tmp/dq_report.json'

async def main():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    report = {}

    # ============================================================
    # ISSUE 1: rating null on user_profile / no rating in users
    # ============================================================
    iss = {}
    sample_user = await db.users.find_one({'chess_com_username': {'$ne': None}}, projection=None)
    iss['users_doc_keys'] = sorted(list(sample_user.keys())) if sample_user else []
    iss['users_has_current_rating_field'] = 'current_rating' in (sample_user or {})
    # Count how many users have any rating-ish field populated
    iss['users_with_current_rating'] = await db.users.count_documents({'current_rating': {'$exists': True, '$ne': None}})
    iss['users_total'] = await db.users.count_documents({})

    # Do games have white_rating / black_rating?
    sample_game = await db.games.find_one({'is_analyzed': True})
    iss['games_doc_keys'] = sorted(list(sample_game.keys())) if sample_game else []
    iss['game_white_rating_sample'] = sample_game.get('white_rating') if sample_game else None
    iss['game_black_rating_sample'] = sample_game.get('black_rating') if sample_game else None
    iss['game_white_type'] = type(sample_game.get('white')).__name__ if sample_game else None
    iss['game_white_sample'] = sample_game.get('white') if sample_game else None
    # Are ratings present at all on games?
    games_with_wr = await db.games.count_documents({'white_rating': {'$exists': True, '$ne': None}})
    games_with_br = await db.games.count_documents({'black_rating': {'$exists': True, '$ne': None}})
    iss['games_total'] = await db.games.count_documents({})
    iss['games_with_white_rating'] = games_with_wr
    iss['games_with_black_rating'] = games_with_br
    # Profiles have current_rating?
    sample_prof = await db.player_profiles.find_one()
    iss['profile_doc_keys'] = sorted(list(sample_prof.keys())) if sample_prof else []
    iss['profile_with_current_rating'] = await db.player_profiles.count_documents({'current_rating': {'$exists': True, '$ne': None}})
    iss['profiles_total'] = await db.player_profiles.count_documents({})
    report['issue_1_rating'] = iss

    # ============================================================
    # ISSUE 2: cognitive_gap empty in move_evaluations
    # ============================================================
    iss = {}
    sample_a = await db.game_analyses.find_one({'move_evaluations': {'$ne': []}})
    moves = sample_a.get('move_evaluations', []) if sample_a else []
    iss['sample_analysis_id'] = str(sample_a.get('analysis_id') or sample_a.get('_id')) if sample_a else None
    iss['n_moves_in_sample'] = len(moves)
    iss['move_keys_sample'] = sorted(list(moves[0].keys())) if moves else []
    iss['move_sample_0'] = moves[0] if moves else None
    # User moves: how many have cognitive_gap set?
    user_moves = [m for m in moves if m.get('is_user_move')]
    iss['user_moves_in_sample'] = len(user_moves)
    iss['user_moves_with_cognitive_gap_field'] = sum(1 for m in user_moves if 'cognitive_gap' in m)
    iss['user_moves_with_non_none_gap'] = sum(1 for m in user_moves if m.get('cognitive_gap') not in (None, 'none', ''))
    iss['gap_value_distribution_sample'] = Counter([m.get('cognitive_gap') for m in user_moves])
    # Sample across many analyses for a more reliable picture
    gap_dist = Counter(); total_user_moves = 0; total_with_gap = 0
    cur = db.game_analyses.find({'move_evaluations': {'$exists': True, '$ne': []}}).sort('analyzed_at', -1).limit(50)
    async for a in cur:
        for m in a.get('move_evaluations', []):
            if not m.get('is_user_move'): continue
            total_user_moves += 1
            g = m.get('cognitive_gap')
            if g not in (None, 'none', ''):
                total_with_gap += 1
                gap_dist[g] += 1
    iss['cohort_user_moves_50games'] = total_user_moves
    iss['cohort_with_gap'] = total_with_gap
    iss['cohort_gap_distribution'] = dict(gap_dist.most_common(20))
    report['issue_2_cognitive_gap'] = iss

    # ============================================================
    # ISSUE 3: top_weaknesses always one_move_blunder + complex_tactical_miss
    # ============================================================
    iss = {}
    # Distribution of distinct subcategories across all profiles
    sub_counts = Counter()
    profile_count = 0
    async for p in db.player_profiles.find({}, {'top_weaknesses': 1}):
        profile_count += 1
        for w in (p.get('top_weaknesses') or []):
            sub_counts[w.get('subcategory')] += 1
    iss['profiles_inspected'] = profile_count
    iss['distinct_subcategory_distribution'] = dict(sub_counts.most_common(20))
    # How many distinct subcategories ever appear?
    iss['unique_subcategories_count'] = len(sub_counts)
    report['issue_3_weaknesses_lockin'] = iss

    # ============================================================
    # ISSUE 4: style placeholder
    # ============================================================
    iss = {}
    confidence_set = Counter(); primary_set = Counter(); tactical_set = Counter()
    async for ident in db.player_identities.find({}, {'style_profile': 1}):
        sp = ident.get('style_profile') or {}
        if isinstance(sp, dict):
            confidence_set[round(sp.get('confidence', 0), 2)] += 1
            primary_set[sp.get('primary_style')] += 1
            tactical_set[round(sp.get('tactical_tendency', 0), 2)] += 1
    iss['identities_inspected'] = sum(primary_set.values())
    iss['primary_style_distribution'] = dict(primary_set)
    iss['confidence_distribution'] = dict(confidence_set)
    iss['tactical_tendency_distribution'] = dict(tactical_set)
    report['issue_4_style_placeholder'] = iss

    # ============================================================
    # ISSUE 5: avg_accuracy null
    # ============================================================
    iss = {}
    iss['profiles_with_avg_accuracy'] = await db.player_profiles.count_documents({'avg_accuracy': {'$exists': True, '$ne': None}})
    iss['profiles_total'] = await db.player_profiles.count_documents({})
    # Is per-game accuracy stored?
    iss['game_analyses_with_accuracy'] = await db.game_analyses.count_documents({'accuracy': {'$exists': True, '$ne': None}})
    sample_ga = await db.game_analyses.find_one({'accuracy': {'$exists': True, '$ne': None}}, {'accuracy': 1, 'user_id': 1})
    iss['sample_game_analysis_accuracy'] = sample_ga
    report['issue_5_avg_accuracy'] = iss

    # ============================================================
    # ISSUE 6: improvement_trend null
    # ============================================================
    iss = {}
    iss['profiles_with_improvement_trend'] = await db.player_profiles.count_documents({'improvement_trend': {'$exists': True, '$ne': None}})
    # Sample a non-null trend
    sample_pt = await db.player_profiles.find_one({'improvement_trend': {'$exists': True, '$ne': None}})
    iss['sample_profile_with_trend'] = sample_pt
    report['issue_6_improvement_trend'] = iss

    # ============================================================
    # BONUS: duplicate accounts (same chess.com handle, different user_id)
    # ============================================================
    dupes = {}
    handles = Counter()
    async for u in db.users.find({'chess_com_username': {'$ne': None}}, {'chess_com_username': 1}):
        handles[u['chess_com_username']] += 1
    dupes = {h: n for h, n in handles.items() if n > 1}
    report['bonus_duplicate_chesscom_handles'] = dupes

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, default=str, indent=2)
    print(f'wrote {OUT}')

asyncio.run(main())
