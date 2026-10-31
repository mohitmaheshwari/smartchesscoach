"""Offline chain candidates from unrestricted opponent replies; no LLM."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chess
from services.reasoning import ReasoningConfig
from services.reasoning.chain_builder import build_candidate_chains
from services.reasoning.chain_challenge import challenge_candidates
from services.reasoning.contracts import fingerprint
from services.reasoning.engine import input_board
from services.reasoning.search import SearchSession, fingerprint_bytes
from services.reasoning.timeline import build_timeline
from services.stored_line_verifier import parse_legal_move


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--engine', required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--depth', type=int, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error('output directory must be new or empty')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    settings = json.loads(args.config.read_text(encoding='utf-8-sig'))
    settings['engine_path'] = args.engine
    config = ReasoningConfig(**settings)
    source = Path(__file__).resolve().parents[1] / 'services' / 'reasoning'
    files = [*source.glob('*.py'), Path(__file__).resolve(), source.parent / 'stored_line_verifier.py']
    frozen = {str(p): fingerprint_bytes(p) for p in files}
    def save(name, value):
        (args.output_dir / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    save('freeze.json', {'manifest_sha256': fingerprint_bytes(args.manifest), 'source_hashes': frozen,
        'config': asdict(config), 'requested_depth': args.depth, 'model_called': False,
        'selection_policy': 'all_maximal_candidate_paths_from_unrestricted_played_reply; no ranking or automatic teaching'})
    rows = []
    for case in cases:
        start = time.perf_counter()
        try:
            root, history = input_board(case['fen'], None)
            move = parse_legal_move(root, case['played_move'])
            if move is None:
                raise ValueError('illegal played move')
            session = SearchSession(config, root.turn, fingerprint([root.fen(), []]))
            played_root = session.query(root, 'chain_played_root', roots=[move], depth=args.depth)
            after = root.copy(); after.push(move)
            reply = session.query(after, 'chain_opponent_unrestricted', depth=args.depth)
            ranking = session.query(root, 'chain_root_ranking', width=config.rank_width, depth=args.depth)
            complete = lambda r: r.status == 'complete_iteration' and r.lines and all(x.get('depth', 0) >= args.depth for x in r.lines)
            if not reply.lines:
                result = {'status': 'no_reply_line', 'candidates': [], 'coaching': None}
            else:
                played = build_timeline(root, [move.uci(), *reply.lines[0]['moves_uci']], reply.id, config.max_plies)
                alternate = None
                if ranking.lines and ranking.lines[0]['root_uci'] != move.uci():
                    alternate = build_timeline(root, ranking.lines[0]['moves_uci'], ranking.id, config.max_plies)
                result = build_candidate_chains(root, played, alternate)
                result['challenges'] = challenge_candidates(root, played, alternate, result['candidates'],
                    played_root.document(), reply.document(), ranking.document(), depth=args.depth)
                result.update(status='complete_search' if all(map(complete, (played_root, reply, ranking))) else 'partial_search',
                    played_moves=played['moves_san'], alternative_moves=alternate['moves_san'] if alternate else [],
                    history_status=history, played_timeline=played, alternative_timeline=alternate)
            result.update(searches=[r.document() for r in session.records], reproducibility=session.document(),
                runtime={'wall_ms': round(1000 * (time.perf_counter()-start), 3),
                    'query_count': session.executed_queries, 'actual_nodes': sum(r.actual_nodes for r in session.records)})
            save(case['id']+'.json', result)
            row = {'id': case['id'], 'status': result['status'], 'candidates': len(result['candidates']),
                'candidate_needs_review': sum(c['status'] == 'candidate_needs_review' for c in result.get('challenges', [])),
                'moves': result.get('played_moves', [])[:5], 'runtime': result['runtime']}
        except (ValueError, KeyError, TypeError, OSError) as exc:
            row = {'id': case['id'], 'status': 'error', 'error': str(exc)}
            save(case['id']+'.json', row)
        rows.append(row)
        print(json.dumps(row), flush=True)
    unchanged = all(fingerprint_bytes(Path(p)) == h for p, h in frozen.items())
    save('summary.json', {'rows': rows, 'source_unchanged': unchanged, 'model_called': False})
    return 0 if unchanged and all(r['status'] != 'error' for r in rows) else 2


if __name__ == '__main__':
    raise SystemExit(main())
