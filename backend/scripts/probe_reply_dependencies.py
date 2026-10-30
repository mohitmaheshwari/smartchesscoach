"""Offline generic reply deletion on an explicit manifest; no model calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.reasoning import ReasoningConfig, locate_reply_dependency
from services.reasoning.search import fingerprint_bytes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True,
        help='JSON list of {id, fen, played_move, optional continuation/exclude_move}')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--engine', required=True)
    parser.add_argument('--depth', type=int, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    cases = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if (not isinstance(cases, list) or not cases or any(not isinstance(c, dict) or not isinstance(c.get('id'), str) or
            not re.fullmatch(r'[A-Za-z0-9_-]+', str(c.get('id', ''))) for c in cases)
            or len({c['id'] for c in cases}) != len(cases)):
        parser.error('manifest needs nonempty cases with unique simple IDs')
    clean = [{k: c[k] for k in ('id', 'fen', 'played_move', 'continuation', 'exclude_move') if k in c} for c in cases]
    settings = json.loads(args.config.read_text(encoding='utf-8-sig'))
    settings['engine_path'] = args.engine
    config = ReasoningConfig(**settings)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error('output directory must be new or empty')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (args.output_dir / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    sources = [*Path(__file__).resolve().parents[1].joinpath('services/reasoning').glob('*.py'), Path(__file__)]
    frozen = {str(p): fingerprint_bytes(p) for p in sources}
    save('freeze.json', {'source_hashes': frozen, 'manifest_sha256': fingerprint_bytes(args.manifest),
                         'config': settings, 'depth': args.depth, 'model_called': False})
    save('inputs.json', clean)
    summary = []
    for case in clean:
        try:
            result = locate_reply_dependency(case['fen'], case['played_move'], config=config, depth=args.depth,
                continuation=case.get('continuation'), exclude_move=case.get('exclude_move'))
            save(case['id'] + '.json', result)
            probe = result['probe']
            row = {'id': case['id'], **{k: probe[k] for k in ('status', 'actor', 'excluded_san', 'signal')},
                   'drops_cp': [m['drop_cp'] for m in probe['measurements']], 'runtime': result['runtime']}
        except (ValueError, OSError, KeyError, TypeError) as exc:
            row = {'id': case['id'], 'status': 'error', 'type': type(exc).__name__}
            save(case['id'] + '.json', row)
        summary.append(row)
        print(json.dumps(row), flush=True)
    unchanged = all(fingerprint_bytes(p) == frozen[str(p)] for p in sources)
    save('summary.json', {'rows': summary, 'source_freeze_unchanged': unchanged, 'model_called': False})
    return 0 if unchanged and all(r['status'] != 'error' for r in summary) else 2


if __name__ == '__main__':
    raise SystemExit(main())
