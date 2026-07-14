#!/usr/bin/env python3
import os
import pymongo

mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(mongo_url)
db = client["test_database"]

print("\n" + "="*60)
print("DATA PIPELINE DEBUG")
print("="*60 + "\n")

# Check queue
queue_count = db.analysis_queue.count_documents({})
print(f"Analysis queue jobs: {queue_count}")
if queue_count > 0:
    pending = db.analysis_queue.count_documents({"status": "pending"})
    processing = db.analysis_queue.count_documents({"status": "processing"})
    completed = db.analysis_queue.count_documents({"status": "completed"})
    print(f"  Pending: {pending}, Processing: {processing}, Completed: {completed}\n")

# Sample game with analysis
game = db.games.find_one({"is_analyzed": True})
if game:
    game_id = game["game_id"]
    print(f"Sample analyzed game: {game_id}")

    analysis = db.game_analyses.find_one({"game_id": game_id})
    if analysis:
        print("✓ Analysis document exists")

        moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
        print(f"  Total moves: {len(moves)}")

        if moves:
            # Check first move
            m = moves[0]
            print(f"\n  First move:")
            print(f"    move: {m.get('move')}")
            print(f"    cp_loss: {m.get('cp_loss')}")
            print(f"    cognitive_gap: {m.get('cognitive_gap')}")

            # Count non-zero cp_loss
            nonzero = sum(1 for mv in moves if mv.get("cp_loss", 0) > 0)
            print(f"\n  Moves with cp_loss > 0: {nonzero}/{len(moves)}")

            # Check for gaps
            gaps = {}
            for mv in moves:
                gap = mv.get("cognitive_gap") or "NONE"
                gaps[gap] = gaps.get(gap, 0) + 1
            print(f"\n  Cognitive gap distribution:")
            for gap, count in sorted(gaps.items(), key=lambda x: -x[1])[:5]:
                print(f"    {gap}: {count}")
    else:
        print("✗ No analysis document found")
else:
    print("✗ No analyzed games found")

print("\n" + "="*60)

# Check if worker is running
import subprocess
result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
if "analysis_worker" in result.stdout:
    print("✓ analysis_worker process is running")
else:
    print("✗ analysis_worker process is NOT running")

client.close()
