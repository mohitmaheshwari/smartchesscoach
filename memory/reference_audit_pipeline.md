---
name: Mock-games audit pipeline
description: Reference for the three-script audit infrastructure that validates the chess caption pipeline (Path B + concept_dispatcher + punishment_puzzle) on synthetic Stockfish-vs-Stockfish games
type: reference
originSessionId: f0992052-301f-4ed6-a982-93dbe42a53ec
---
Three scripts in `backend/scripts/` together cover three different questions:

1. **`caption_coverage_audit.py`** — "Did a template fire?"
   Walks every analyzed game in MongoDB (decryption_v5_data + stockfish_analysis fallback), runs the production caption pipeline per move, reports source-label distribution. Output structure: per-source counts, severity × source matrix, top good_generic signatures, sample positions per source. Use to find detector gaps.

2. **`mock_games_audit.py`** — "Does the pipeline work end-to-end on fresh games?"
   Generates N synthetic games using two Stockfish instances at different skill levels (rating-mapped via `rating_to_skill`). Runs the same caption pipeline used in production. Reports coverage + sample captions + punishment-puzzle hits + a regex scan for forbidden filler words. Use to compare against real-corpus audit and stress-test the puzzle service.

3. **`mock_correctness_audit.py`** — "Are the captions actually true and pedagogically useful?"
   Reuses `mock_games_audit`'s game generator. For every fired caption, runs two checks:
   - **Factual verifier** — re-derives the template's chess claim from board state and compares with rendered text. ~48 per-template verifiers cover the major templates.
   - **1200-test** — checks the caption pairs concept words with concrete consequences (regex set: "wins the X", "attacks Y on Z", "no defender", "sets up [SAN]", "checkmate", "no escape squares", "escapes the check", "now controls", etc.). Forbidden filler ("repositions", "controls the column", "active diagonal" alone) fails.

**How to run on the server (typical):**
```bash
cd ~/smartchesscoach && git pull
docker cp backend/scripts/<script>.py chess-coach-backend:/app/backend/scripts/<script>.py
# also docker cp any modified detector files (per_move_caption.py, middlegame_patterns.py, endgame_technique.py)
docker exec -it chess-coach-backend python scripts/<script>.py \
  --pairs '1200v1100,1200v1300,1300v1200,1400v1400,1100v1400' \
  --output /tmp/<output>.txt
docker cp chess-coach-backend:/tmp/<output>.txt ~/<output>.txt
# then scp from a fresh PowerShell on laptop
```

**Runtime**:
- coverage_audit on full DB (~3000 games): ~10 min
- mock_games / mock_correctness on 5 games: ~6 min
- mock_games / mock_correctness on 10 games: ~12-15 min

**Last clean state (2026-05-08)**:
- Coverage on real corpus: 84.9% substantive, 7.1% engine_review_needed
- Correctness on mock corpus: 100% (254/254)
- 1200-test on mock corpus: 100% (254/254)
- Stockfish skill levels are randomised per move so re-runs sample different positions; results are reproducible to within ~5%.

**When to re-run**:
- After any caption template change → mock_correctness to confirm 100%/100% holds
- After any detector logic change → mock_correctness + spot-check WRONG-FIRE samples
- Periodically as a regression check before shipping to Parth

**Caveats**:
- Stockfish skill-level approximations of low ratings are not exact. Don't make statistical claims about real 1200 players from these audits.
- Open templates without verifiers (centre_game, english_opening, fianchetto, rook_seventh, combination) are tracked separately in the report; they're either self-verifying (opening_book) or known low-risk.
