"""Offline: up to 15 plies of piece evidence, optionally sent to GPT-6-luna."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.reasoning.contracts import ReasoningConfig
from services.reasoning.evidence import build_position_evidence, model_packet


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fen-before', required=True)
    parser.add_argument('--played-move')
    parser.add_argument('--fen-after')
    parser.add_argument('--history', type=Path, help='JSON with initial_fen and moves, when available')
    parser.add_argument('--config', type=Path, required=True, help='Existing explicit ReasoningConfig JSON')
    parser.add_argument('--engine', required=True)
    parser.add_argument('--depth', type=int, required=True, help='Requested depth; achieved depths are reported')
    parser.add_argument('--max-plies', type=int, default=15, help='User-requested horizon, at most 15')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--call-model', action='store_true', help='Explicitly send the model-facing evidence to GPT-6-luna')
    parser.add_argument('--env-file', type=Path, help='Explicit provider configuration; never auto-search credential files')
    parser.add_argument('--max-output-tokens', type=int)
    parser.add_argument('--reasoning-effort')
    args = parser.parse_args(argv)
    if not args.played_move and not args.fen_after:
        parser.error('--played-move or --fen-after is required')
    if args.call_model and (not args.max_output_tokens or args.max_output_tokens < 1):
        parser.error('--call-model requires a positive --max-output-tokens allocation')
    if not args.call_model and (args.env_file or args.max_output_tokens or args.reasoning_effort):
        parser.error('model configuration requires --call-model')
    if args.env_file and not args.env_file.is_file():
        parser.error('--env-file must exist')
    if args.call_model and args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=True)
    settings = json.loads(args.config.read_text(encoding='utf-8-sig'))
    settings['engine_path'] = args.engine
    history = json.loads(args.history.read_text(encoding='utf-8-sig')) if args.history else None
    # A nonempty destination is never silently overwritten.
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error('--output-dir must be new or empty')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        packet = build_position_evidence(args.fen_before, args.played_move, fen_after=args.fen_after,
            history=history, config=ReasoningConfig(**settings), depth=args.depth, max_plies=args.max_plies)
    except (ValueError, OSError, TypeError) as exc:
        save(args.output_dir / 'error.json', {'status': 'evidence_error', 'type': type(exc).__name__})
        print(json.dumps({'status': 'evidence_error', 'type': type(exc).__name__}))
        return 2
    save(args.output_dir / 'evidence.json', packet)
    view = model_packet(packet)
    save(args.output_dir / 'model_input.json', view)
    summary = {'evidence_status': packet['status'], 'played_move': packet['input']['played_san'],
               'branches': len(packet['branches']), 'states': len(packet['states']),
               'max_plies': max(b['available_plies'] for b in packet['branches']),
               'search_quality': packet['search_quality'], 'runtime': packet['runtime'],
               'model_status': 'not_called'}
    if args.call_model:
        from services.reasoning.evidence_words import propose_evidence_reasoning, SYSTEM
        (args.output_dir / 'model_system.txt').write_text(SYSTEM, encoding='utf-8')
        result = asyncio.run(propose_evidence_reasoning(packet, max_tokens=args.max_output_tokens,
            reasoning_effort=args.reasoning_effort))
        save(args.output_dir / 'model_result.json', result)
        if result['raw_response'] is not None:
            (args.output_dir / 'model_response.txt').write_text(result['raw_response'], encoding='utf-8')
        summary.update(model_status=result['status'], model_request=result['request'],
                       model_runtime_ms=result.get('runtime_ms'), checks=result.get('checks'))
        if result['status'] == 'unreviewed_proposal':
            summary['proposal_decision'] = result['proposal']['decision']
            summary['review'] = result['review']
            if result['proposal']['decision'] == 'explain':
                summary['unreviewed_explanation'] = result['proposal']['explanation']
    save(args.output_dir / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=True))
    return 3 if summary['model_status'] in ('provider_error', 'refused') else 0


if __name__ == '__main__':
    raise SystemExit(main())
