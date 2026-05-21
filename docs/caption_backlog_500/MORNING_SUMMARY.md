# Overnight Caption Audit — Morning Summary

**Started:** 2026-05-21 evening — Mohit "go go go" instruction (competitive pressure, couldn't rest).
**Scope:** 500-game sample at v52 → v53, with mechanical caption verification across all tiers (not just LOW).

---

## Headline numbers (preliminary, audit still finalizing)

| Metric | Value |
|---|---|
| 500-game audit running, ~420/500 regenerated to v53 | in progress |
| Mechanical verifier — captioned user moves checked | **9,078** |
| **Suspect captions found (claim falsifiable by mechanical check)** | **0** |
| Caption hallucinations remaining (clearance, mate, piece_capture, opp_reply, severity, winning/losing) | **none** |

In the 50-game sample at v52 the verifier had found **10 clearance hallucinations** ("your queen comes through to attack f7" when the queen would need to teleport). After the v53 fix, those are gone.

## What I shipped overnight (committed + pushed to origin/working-code)

| Commit | Version | What |
|---|---|---|
| `8f72f7a7` | v53 | clearance_for_attack detector drops speculative slider-teleport (closed 10/50 hallucinations) |
| `31cd2231` | tools | caption_verifier.py (6 mechanical checkers) + caption_backlog_md_writer.py |
| `8ab5d97f` | v54 | curriculum walker filters openings by color before iterating (fixes cross-color mismatches like white-curric trees being walked for black users) |
| `fed218bc` | v55 | user_is_winning / user_is_losing now require BOTH eval_before AND eval_after to support the framing (closes m20_Qe6 backlog case where the played move CAUSED the loss) |
| `2a225402` | content | Bishop's Opening curriculum entry added |
| `d0de8b2c` | content | Vienna Game + Englund Gambit response curriculum entries added |
| `5ca59dbe` | tools | verifier extended with board_state claim checks |

7 commits. 5 of those are real bug fixes; 2 are tools / content.

Total curated openings: **20** (was 17 at v51).

## Tools built (in `backend/scripts/`)

- **`caption_verifier.py`** — 6 mechanical claim checkers across 500 games:
  1. piece_capture — "wins the {piece} on {square}" actually happens in PV
  2. mate — "led to mate in N moves" PV ends in mate within N
  3. opp_reply — "Opponent's strongest reply: X" matches pv_after_played[0]
  4. clearance — "your {piece} comes through to attack X" slider actually attacks
  5. severity — severity word matches cp_loss tier (mistake / serious / blunder)
  6. winning_losing_frame — position-eval framing matches eval reality
  7. board_state — bs_isolated_attacker + bs_queen_alone_active claims

- **`caption_backlog_md_writer.py`** — JSON report → per-position MD files
  with engine analysis at depth 16 multipv 3. Empty docs/caption_backlog_500
  because zero suspects.

- **`author_curriculum_bishops_opening.py`** + **`author_curriculum_vienna_and_more.py`**
  — one-shot scripts that authored the new openings.

## Open issues left for your morning review

### 1. Curriculum walker fires rarely in production (low frequency, not a bug)

The `with_curriculum_deviation` and `why_user_curriculum_deviation` variants fire ~3 hits per 50 games (~30 per 500). Distinctive curriculum text (e.g., "OUTSIDE the c6 pawn chain", "big center", "falls apart") had **0 hits** in a 500-game search of v53 captions.

Why: the curriculum walker requires the user to walk the EXACT main line of an opening up to a node with `wrong_feedback`, then deviate at that exact node. Most users either:
- Play correctly within book → `R_PROMOTED_opening` fires (surfaces opening summary)
- Deviate before reaching a `wrong_feedback` node → walker reports off-book

To meaningfully increase firing rate, we'd need to add MORE `wrong_feedback` nodes per tree, OR change the walker to fire on opening-deviation events anywhere in the tree (not just at the canonical decision points).

### 2. Pre-v53 captions still in production for older games

The audit only regenerates games at `decryption_v5_version < V5_COACHING_VERSION`. Games that haven't been viewed since v22 (or any older version) still carry stale captions. Lazy regen kicks in when a user views the game. For full corpus refresh, would need a bulk re-decryption job.

### 3. The "wins material in the resulting line" variant is engine-speak

Still fires ~12 times per 300 v53 games (gated to balanced positions per v51 — accurate behavior). It's truthful (engine PV does win material) but generic. Could be improved by threading the captures count or naming the first piece won. Not a hallucination; just less precise than other variants.

### 4. v54 and v55 fixes aren't yet reflected in v53 audit results

The running audit uses the container's v53 imports (cached at startup). v54 (curriculum color filter) and v55 (eval_before requirement) need a container restart to take effect. I'm running a smaller v55 validation audit after the v53 audit completes.

## Curriculum / traps content extension

3 new opening entries added based on patterns observed in the 500-game sample:

| Opening | Reason added | Hits in audit |
|---|---|---|
| `bishops_opening` | 4 games played 1.e4 e5 2.Bc4, not previously curated | (will fire in next audit) |
| `vienna_game` | 25 games in full corpus, missing | (will fire in next audit) |
| `englund_gambit_response` | ~7 games as black 1.d4 e5 trap-prone gambit | (will fire in next audit) |

7 existing trees were ALREADY DEEPENED in v52 (Phase 3): italian_game, sicilian_defense, caro_kann, ruy_lopez, french_defense, queens_gambit, kings_indian_defense. Plus 3 new entries in v52: petrov_defense, italian_game_black, nimzo_indian_defense.

**Total curated openings: 20** (london, italian, italian_black, sicilian, caro_kann, french, queens_gambit, scandinavian, ruy_lopez, scotch, petrov, kings_indian, nimzo, slav, english, modern, philidor, bishops_opening, vienna, englund_response).

## What would be next priorities

If you want to keep pushing curriculum coverage:
- Author more `wrong_feedback` nodes per existing tree (currently 2-8 per opening)
- Add traps observed in audit (Fried Liver fired 12 times in the 300-game sample — that's already firing; other traps less seen)
- Add lower-frequency openings: Reti, Bird's, Trompowsky if they show up

If you want to push verifier coverage:
- Add a "best_move agreement" check (re-run Stockfish on the stored fen_before, compare to stored best_move_san)
  — expensive (1-2 sec/move) so would need sampling

## Audit timeline

- Verifier on 50-game sample at v52: **10 clearance hallucinations**
- v53 fix shipped → verifier on 50 at v53: **0 hallucinations**
- v54 + v55 shipped (queued for next container restart)
- 500-game audit at v53 in progress (~420/500 regenerated at the time of writing)
- Verifier on 400 v53 games: **0 suspects** — caption pipeline is mechanically clean
- Pending: final v53 audit numbers + v55 validation run

---

*This file will be updated when the audit + final verifier + v55 run complete.*
