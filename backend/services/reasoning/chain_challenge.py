"""Reject forged, weakly sourced or unstable candidate chains."""
from .chain_builder import build_candidate_chains
from .objectives import common_prefix


def challenge_candidates(root, played, alternative, candidates, played_root, reply, ranking, *, depth):
    canonical = {c['id']: c for c in build_candidate_chains(root, played, alternative)['candidates']}
    def at_depth(record):
        return (record.get('status') == 'complete_iteration' and bool(record.get('lines'))
                and all(line.get('depth', 0) >= depth for line in record['lines']))
    base_lines, reply_lines, rank_lines = (r.get('lines', []) for r in (played_root, reply, ranking))
    base_moves = base_lines[0].get('moves_uci', []) if base_lines else []
    reply_moves = reply_lines[0].get('moves_uci', []) if reply_lines else []
    rank_moves = rank_lines[0].get('moves_uci', []) if rank_lines else []
    agreement = common_prefix(played['moves_uci'], base_moves)
    base_binding = (played_root.get('fen') == root.fen() and played_root.get('root_moves') == [played['root_uci']]
                    and bool(base_moves) and base_moves[0] == played['root_uci'])
    reply_binding = (reply.get('fen') == played['nodes'][1]['fen'] and not reply.get('root_moves')
                     and reply.get('id') == played['search_id']
                     and played['moves_uci'] == [played['root_uci'], *reply_moves][:len(played['moves_uci'])])
    ranking_binding = (ranking.get('fen') == root.fen() and not ranking.get('root_moves') and alternative is not None
                       and ranking.get('id') == alternative['search_id'] and bool(rank_moves)
                       and alternative['moves_uci'] == rank_moves[:len(alternative['moves_uci'])])
    results = []
    for candidate in candidates:
        facts = candidate.get('facts', [])
        checks = {'canonical_candidate': canonical.get(candidate.get('id')) == candidate,
            'played_root_binding': base_binding, 'unrestricted_reply_binding': reply_binding,
            'alternative_ranking_binding': ranking_binding,
            'played_root_at_requested_depth': at_depth(played_root),
            'reply_at_requested_depth': at_depth(reply), 'ranking_at_requested_depth': at_depth(ranking),
            'played_line_agreement_plies': agreement,
            'facts_within_agreement': bool(facts) and max(f.get('ply', depth + 1) for f in facts) <= agreement,
            'root_relation_preserved': candidate.get('contrast', {}).get('root_relation_preserved') is True}
        passed = all(value for key, value in checks.items() if key != 'played_line_agreement_plies')
        results.append({'candidate_id': candidate.get('id'), 'checks': checks,
            'status': 'candidate_needs_review' if passed else 'incomplete', 'mechanism_verified': False,
            'unresolved': ['multiple_defences_and_compensation', 'root_score_comparison',
                           'causal_relevance', 'independent_coaching_review']})
    return results
