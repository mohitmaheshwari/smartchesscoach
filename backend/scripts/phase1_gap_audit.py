#!/usr/bin/env python3
"""
Coaching Engine v2, Phase 1: Cognitive Gap Accuracy Audit

Sample moves that ARE categorized (cp_loss >= 100) from bhutramohit's 584 games
and hand-verify them against Stockfish's view to identify:
  1. piece_safety: over-fires on incidental hangs?
  2. king_safety: mislabels queens-off endgame moves?
  3. Low-confidence cats (piece_activity, calculation_depth, pawn_structure): should they be excluded?

Target: 70% accuracy (vs current ~50%).
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from collections import Counter, defaultdict

async def audit():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ.get('DB_NAME','test_database')]

    user_id = 'user_8b599930d7ef'  # bhutramohit

    print("Phase 1: Cognitive Gap Accuracy Audit")
    print("=" * 70)
    print(f"Scanning bhutramohit's analyzed games for gap accuracy issues...\n")

    # Sample 50 games
    games = await db.game_analyses.find(
        {'user_id': user_id}
    ).limit(50).to_list(length=50)

    # Collect ALL gap-tagged moves for analysis
    gap_tagged_moves = []
    gap_dist = Counter()
    severity_dist = Counter()

    for game in games:
        game_id = game.get('game_id')
        sf = game.get('stockfish_analysis', {})
        moves = sf.get('move_evaluations', [])

        for m in moves:
            if m.get('is_opponent_move'):
                continue
            cp_loss = m.get('cp_loss', 0)
            if cp_loss < 100:
                continue  # Skip routine moves

            gap = m.get('cognitive_gap')
            classification = m.get('classification', 'unknown')
            gap_tagged_moves.append({
                'game_id': game_id,
                'move_number': m.get('move_number'),
                'move_san': m.get('move'),
                'cp_loss': cp_loss,
                'classification': classification,
                'cognitive_gap': gap,
                'best_move': m.get('best_move'),
                'fen_before': m.get('fen_before'),
            })
            if gap:
                gap_dist[gap] += 1
            severity_dist[classification] += 1

    print(f"Found {len(gap_tagged_moves)} moves with cp_loss >= 100 (potential mistakes):\n")

    # Categorization stats
    print("Gaps assigned to CRITICAL moves (cp_loss >= 100):")
    for gap, count in gap_dist.most_common():
        pct = 100 * count / len(gap_tagged_moves) if gap_tagged_moves else 0
        print(f"  {gap:25} {count:4} ({pct:5.1f}%)")

    none_count = len([m for m in gap_tagged_moves if not m['cognitive_gap']])
    print(f"  {'(None/Unknown)':25} {none_count:4} ({100*none_count/len(gap_tagged_moves):5.1f}%)")

    print(f"\nSeverity breakdown (classification):")
    for sev, count in severity_dist.most_common():
        pct = 100 * count / len(gap_tagged_moves) if gap_tagged_moves else 0
        print(f"  {sev:15} {count:4} ({pct:5.1f}%)")

    # Detailed sample for manual review
    print(f"\n" + "=" * 70)
    print("DETAILED SAMPLE (first 15 gap-tagged moves for manual review):\n")
    print(f"{'Game':12} {'M#':3} {'Move':6} {'Loss':6} {'Class':12} {'Gap':25} {'Best':7}")
    print("-" * 95)

    sample_count = 0
    for m in gap_tagged_moves[:20]:
        if m['cognitive_gap']:  # Only show tagged ones
            print(f"{m['game_id'][:8]}.. {m['move_number']:3} {m['move_san']:6} {m['cp_loss']:6} {m['classification']:12} {m['cognitive_gap']:25} {m['best_move'][:7]:7}")
            sample_count += 1
            if sample_count >= 15:
                break

    # Issue detection
    print(f"\n" + "=" * 70)
    print("ISSUES DETECTED (Phase 1 focus areas):\n")

    # Issue 1: piece_safety over-firing?
    piece_safety_moves = [m for m in gap_tagged_moves if m['cognitive_gap'] == 'piece_safety']
    if piece_safety_moves:
        print(f"1. piece_safety ({len(piece_safety_moves)} cases):")
        print(f"   - Over-firing? Check if engine just punished a pawn move")
        print(f"     Sample: {piece_safety_moves[0]['move_san']} (cp_loss={piece_safety_moves[0]['cp_loss']})\n")

    # Issue 2: king_safety mislabels?
    king_safety_moves = [m for m in gap_tagged_moves if m['cognitive_gap'] == 'king_safety']
    if king_safety_moves:
        print(f"2. king_safety ({len(king_safety_moves)} cases):")
        print(f"   - Mislabels queens-off endgame king moves as king_safety (should be endgame_technique)?")
        print(f"     Sample: {king_safety_moves[0]['move_san']} (cp_loss={king_safety_moves[0]['cp_loss']})\n")

    # Issue 3: Low-confidence categories?
    low_conf_gaps = ['piece_activity', 'calculation_depth', 'pawn_structure']
    low_conf_count = sum(1 for m in gap_tagged_moves if m['cognitive_gap'] in low_conf_gaps)
    if low_conf_count > 0:
        print(f"3. Low-confidence categories ({low_conf_count} cases):")
        for gap in low_conf_gaps:
            count = sum(1 for m in gap_tagged_moves if m['cognitive_gap'] == gap)
            if count > 0:
                print(f"   - {gap}: {count} moves (recommend exclusion from coaching?)\n")

    # None/Unknown count
    none_moves = [m for m in gap_tagged_moves if not m['cognitive_gap']]
    if none_moves:
        print(f"4. Unclassified ({len(none_moves)} moves with None cognitive_gap):")
        print(f"   - These were flagged critical (cp_loss >= 100) but detection returned None")
        print(f"   - Sample: {none_moves[0]['move_san']} (cp_loss={none_moves[0]['cp_loss']}, class={none_moves[0]['classification']})\n")

    print("=" * 70)
    print("\nPHASE 1 SUCCESS CRITERIA:")
    print("  ✓ cognitive_gap accuracy >= 70% (vs current ~50%)")
    print("  ✓ piece_safety filtered to real material loss (engine-grounded, not geometry)")
    print("  ✓ king_safety complete (queens-off endgame moves backfilled)")
    print("  ✓ Low-confidence excluded from coaching (piece_activity, calculation_depth, pawn_structure)")
    print("\nNext: Implement fixes, then re-audit to verify improvement.\n")

if __name__ == "__main__":
    asyncio.run(audit())
