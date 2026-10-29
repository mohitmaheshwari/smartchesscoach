"""Seed claude_reason_reviews -- the fourth geometry-gaps queue -- from the offline run.

Run inside the backend container on the server (writes go through ssh, never
from the local container, whose Mongo user is read-only):

    docker exec chess-coach-backend python scripts/seed_claude_reason_reviews.py

The data file is the 2026-10-29 run: 61 silent positions out of 320, one exact
duplicate dropped (1.e4 d5 appeared twice from the same game). Idempotent: replaces only
rows from the same source tag, so a later run with new positions can add to
the set without touching what a reviewer has already ruled on."""
import io, json, os, sys
from pymongo import MongoClient

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "..", "data", "claude_reason_reviews_2026_10_29.json")
docs = json.load(io.open(path, encoding="utf-8"))
db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
col = db.claude_reason_reviews
before = col.count_documents({})
sources = sorted({d.get("source") for d in docs})
col.delete_many({"source": {"$in": sources}})
col.insert_many(docs)
col.create_index("key", unique=True, name="claude_reason_review_key")
col.create_index("judge_overall", name="claude_reason_review_judge")
print("db:", db.name, "| before:", before, "| now:", col.count_documents({}))
print("by judge:", {k: col.count_documents({"judge_overall": k})
                    for k in ("confirmed", "refuted", "not_probeable", "cannot_test")})
print("indexes:", sorted(col.index_information()))
