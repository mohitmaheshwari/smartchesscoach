---
name: parth-tester-profile
description: Parth Gilda — Mohit's primary tester for ChessGuru. 1800 chess.com Elo (well above the 1200-1500 target audience but a sharp chess-content reviewer). Files structured feedback (game_id + FEN + move + coaching_text_flagged + free-text issue note) via the in-app Lab feedback button.
metadata:
  type: user
---

Parth is the QA / test user of ChessGuru. 1800 chess.com rated — strong enough to catch chess-content errors that slip past the deterministic pipeline (mislabeled tactics, wrong principle names, false-positive "free piece" claims, etc.).

## How to apply

- Parth's feedback often comes in batches via the Lab page feedback widget; the entries land in MongoDB with structured fields (`feedback_id`, `game_id`, `fen`, `move_san`, `coaching_text_flagged`, `issue`, `severity`).
- His free-text `issue` notes are TERSE — often just "." or "explain" or "wrong." Don't take "wrong" at face value; pair with the FEN and reproduce the position to see what he meant.
- Treat his chess-content claims with the `[[no-yes-man]]` discipline: verify against the FEN, but expect ~80%+ of his named-pattern callouts ("not a pin, it's a skewer" / "no fork here") to be correct — he knows chess content well above the target rating.
- 117-bug audit (May 2026) was Parth's earliest batch. That batch broke trust on multiple earlier "verified clean" claims; led to the locked rule `[[feedback-chess-content-verification]]` (audit the rendered string vs FEN, not the internals).
- The 2026-05-17 batch: 27 items across two games (`aa60d98c-acc2-453f-bde5-62f29cc4a123` and `a50ddf30-c154-4486-81d9-0219eb621440`). Mix of "wrong principle name" (pin↔skewer, fork miscall) and "missing explanation" requests.

## Severity field meaning (from his feedback widget)

- `blunder` / `mistake` / `inaccuracy` / `good` — engine-classification mirror; helps locate the move in the game.
- `opp_blunder` / `opp_mistake` — same but the move was opponent's.
- `context` — explanatory caption rather than a move-quality call.

## Linked memories

- `[[feedback-chess-content-verification]]` — the rule born from his 117-bug audit
- `[[no-yes-man]]` — verify against FEN before accepting his framing OR mine
- `[[1200-test]]` — Parth's at 1800, but the captions he flags need to work for 1200; don't tune the captions FOR Parth specifically
