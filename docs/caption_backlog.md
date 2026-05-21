# Caption Authoring Backlog

Living document tracking positions in the audit where current captions
are LOW-specificity, with chess analysis + suggested detector / fact /
teaching content. Use this to design ONE good architecture rather
than building per-pattern detectors reactively.

**Last audit:** v40, 50 games, 1111 captioned moves, 175 LOW captions
(15.1%). This doc lists the 15 LOW samples captured + their root
patterns.

## Method

For each LOW position:
- **Played vs best:** what user did vs engine's pick
- **Chess theme:** the underlying principle the user missed
- **Current caption:** what the system says today
- **Better caption (what 1200 needs):** the coach voice teaching
- **Missing fact:** what detector / fact would surface the right teaching
- **Pattern bucket:** category for grouping into a shared detector

---

## Positions

### 1. Premature capture (missed pile-on)

- **Game:** c25fea91 m10 — Black to move
- **FEN:** `r2q1rk1/p1p2ppp/2pbb3/3nN3/8/3P4/PPP2PPP/RNBQR1K1 b - - 0 10`
- **Played → best:** Bxe5 → Qf6
- **Caption today:** *"Bxe5 is a mistake. Qf6 was better."*
- **Chess theme:** White's Ne5 has 1 attacker (Bd6) vs 1 defender (Re1) — capturing yields equal trade. Qf6 adds a 2nd attacker → 2 vs 1 → black wins the knight outright (and the rook in the follow-up).
- **Better caption:** *"Don't capture yet — bring Qf6 first. 2 attackers vs 1 defender wins the knight."*
- **Missing fact:** `pile_on_opportunity` (we have an un-deployed attacker for the target square).
- **Pattern bucket:** **attackers-vs-defenders count**

### 2. Missed rook activation on open file

- **Game:** c25fea91 m12 — Black to move
- **FEN:** `r4rk1/p1p2ppp/2p1bq2/3n4/8/3P4/PPP2PPP/RNBQR1K1 b - - 2 12`
- **Played → best:** Qg6 → Rae8
- **Caption today:** *"Qg6 is a mistake. Rae8 was better."*
- **Chess theme:** The e-file just opened; Rae8 seizes it. Qg6 misses this strategic priority.
- **Better caption:** *"The e-file is open — your rook belongs there with Rae8. Activating a passive rook beats moving a developed queen."*
- **Missing fact:** `open_file_unoccupied + own_rook_could_seize`.
- **Pattern bucket:** **piece activation / open files**

### 3. Defended when attack was available

- **Game:** c25fea91 m19 — Black to move
- **FEN:** `4r1k1/p1p2ppp/2p3q1/8/5B2/2PP2P1/P1P1bPQP/R5K1 b - - 5 19`
- **Played → best:** Kf8 → Qf6
- **Caption today:** *"Kf8 is a mistake. Qf6 was better. Opponent's strongest reply: Be3."*
- **Chess theme:** Best move is an attacking queen move; played move is a passive king walk.
- **Better caption:** *"Don't shuffle the king — Qf6 attacks. When you have an active queen move, take it."*
- **Missing fact:** `played_is_passive_when_active_available` (best_move creates a threat / attacks a piece; played_move doesn't).
- **Pattern bucket:** **active vs passive move type**

### 4. Same family — missed active piece move

- **Game:** c25fea91 m20 — Black to move
- **FEN:** `4rk2/p1p2ppp/2p3q1/8/5B2/2PP2P1/P1P1bPQP/4R1K1 b - - 7 20`
- **Played → best:** Qe6 → Bg4
- **Caption today:** *"Qe6 is a serious mistake. Bg4 was better. Opponent's strongest reply: Be3."*
- **Chess theme:** Bg4 develops bishop with tempo. Qe6 is positional drift.
- **Pattern bucket:** **active vs passive move type** (same as #3)

### 5-9. Opening series — "Nf3 was better" repeats

- **Game:** 09125fda m5, m9, m10, m11, m13, m15
- **FENs (selected):**
  - m5: `r1b1kbnr/pppp1ppp/2n2q2/6N1/3pP3/8/PPP2PPP/RNBQKB1R w KQkq - 2 5` — White just played Bd3, should've played Nf3
  - m13: `r1b1k2r/pp2nppp/2p5/3pq1N1/3b4/2NQ3P/PP3PP1/R1B2RK1 w kq - 0 13` — Bd2 (major blunder, cp=472) — `wins material in the resulting line` fallback fired
  - m15: `2kr3r/pp2nppp/2p5/3pqbN1/3b4/2N2Q1P/PP1B1PP1/R4RK1 w - - 4 15` — Bf4 (major blunder, cp=424) — same fallback
- **Chess theme (m5-m11):** White's queenside knight (b1) is undeveloped through 11 moves while black's pieces coordinate. Repeated "Nf3 was better" reflects this — the engine wants the knight out.
- **Better caption (m5-m11):** *"Your knight on b1 hasn't moved — get it to f3 before doing anything else. Develop knights before bishops in the opening."*
- **Missing fact (opening):** `undeveloped_minor_piece_in_opening` (phase=opening, piece on starting square, move_number > 4).
- **Chess theme (m13, m15):** Big blunders losing material. Caption fires `R_PROMOTED_basic_mistake` "wins material in the resulting line" — generic engine-speak.
- **Better caption:** *"Bd2 leaves your knight on g5 hanging. Nxg5 wins a piece."* (position-specific — we know what's hanging from facts).
- **Missing fact:** existing `missed_tactic_detector` should fire here; need to investigate why it didn't (probably eval guard threshold or PV depth).
- **Pattern bucket:** **opening development + hanging piece detection**

### 10. Quick opening blunder

- **Game:** 2fb9b0cb m7 — Black to move
- **FEN:** `rn1qkbnr/pp4pp/2p1pp2/3pP3/3P1B2/2N2Q2/PPP2PPP/R3KB1R b KQkq - 1 7`
- **Played → best:** Bb4 → Nd7
- **Caption today:** *"Bb4 is a mistake. Nd7 was better."*
- **Chess theme:** Black still hasn't developed b8 knight; Nd7 develops it. Bb4 develops bishop but skips the knight.
- **Better caption:** *"Develop knights first. Your knight on b8 should move before the bishop wanders."*
- **Pattern bucket:** **opening development** (same as #5-#9)

### 11. Missed-tactic detection failure

- **Game:** daa51ba5 m15 — Black to move
- **FEN:** `2r3k1/1p1qrppp/p1n2p2/8/Q2P4/5N2/PPP2PPP/2KR3R b - - 5 15`
- **Played → best:** Qc7 → Re2 (cp=117)
- **Caption today:** *"Qc7 is a mistake. Re2 was better. Re2 wins material in the resulting line."*
- **Chess theme:** Re2 attacks white's loose pieces / infiltrates the 2nd rank. Black missed a strong invasion.
- **Better caption:** *"Re2 invades the 2nd rank — attacks your queen and creates threats."*
- **Missing fact:** missed_tactic should fire with `piece_capture` or richer (it's reporting "material" which is the eval-guard downgrade).
- **Pattern bucket:** **eval-guard downgrade is too aggressive** — see investigation note below.

### 12. Same family

- **Game:** daa51ba5 m23 — Black to move
- **FEN:** `2r1r1k1/2q2ppp/p7/1p1R2Q1/3Np3/5P2/PPP3PP/2K1R3 b - - 0 23`
- **Played → best:** Qc4 → e3 (cp=60)
- **Caption today:** *"Qc4 is a mistake. e3 was better."*
- **Chess theme:** Small cp_loss; pawn push e3 creates a passed pawn or attacks something.
- **Better caption:** Low-cp_loss positions are gray area — bare severity might be fine here.
- **Pattern bucket:** **small-cp blunders that don't need detail** — long tail, accept generic

### 13. Wrong capture choice in opening

- **Game:** 127a9ad9 m5 — Black to move
- **FEN:** `r1bqk1nr/pp1pppbp/2n3p1/2p5/2B1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq - 0 5`
- **Played → best:** Bxc3+ → d6 (cp=153)
- **Caption today:** *"Bxc3+ is a mistake. d6 was better."*
- **Chess theme:** Bxc3+ trades a fianchetto bishop for a knight + opens white's b-file for rook (good for white, bad for black). d6 keeps the bishop and supports e5.
- **Better caption:** *"Don't give up your fianchetto bishop without reason. d6 develops naturally."*
- **Missing fact:** `is_fianchetto_bishop_trade_without_compensation`.
- **Pattern bucket:** **bishop trade evaluation** — specialized opening principle, probably long tail at 1200 level.

### 14. Knight blunder

- **Game:** 127a9ad9 m15 — Black to move
- **FEN:** `1k1r2r1/pp1qp2p/2n1pnpB/2ppP1N1/8/2PP3P/P1P2PP1/1R1Q1RK1 b - - 0 15`
- **Played → best:** Nxe5 → Ne8 (cp=249)
- **Caption today:** *"Nxe5 is a mistake. Ne8 was better."*
- **Chess theme:** Nxe5 walks into a tactic (probably opens a file or loses material to opp reply). Ne8 retreats safely.
- **Better caption:** *"Nxe5 walks into a tactic. Look at opp's threats before capturing."*
- **Missing fact:** `played_creates_opponent_tactic` (after the move, opp has a winning continuation).
- **Pattern bucket:** **walked-into-tactic detection** — partially overlaps with existing `pv_after_played` analysis.

---

## Pattern buckets summary

| Bucket | Positions | Detector needed |
|---|---|---|
| **A: attackers-vs-defenders count** | #1 | Half-day geometric detector. Counts own attackers + opp defenders on opp pieces; flags "pile-on opportunity" when we have an extra attacker available. |
| **B: active vs passive move type** | #2, #3, #4 | Compare played_move and best_move: does one create a threat / attack while the other doesn't? Engine-derived. ~half day. |
| **C: opening development** | #5–#10 | Detect when a minor piece is still on its starting square in mid-opening AND the engine's best move develops it. Uses existing phase detection. ~quarter day. |
| **D: missed-tactic eval-guard tuning** | #9, #10, #11 | NOT a new detector — investigate why existing `missed_tactic_detector` falls back to `material` instead of `piece_capture`. Probably need to tune the eval threshold or look deeper in PV. ~half day. |
| **E: walked-into-tactic** | #14 | Look at `pv_after_played` for forcing opponent sequences. Partially exists; surface as a why-clause. ~half day. |
| **F: long tail (accept generic)** | #12, #13 | No detector. Small-cp blunders + specialized opening principles. Bare severity is fine. |

---

## Architecture proposal

**Stop building per-pattern detectors. Build a small set of FACT-PRODUCING utilities, each of which covers many positions.**

The pattern buckets above resolve to 4 reusable fact-producing detectors:

1. **`attackers_defenders_analyzer`** (Bucket A)
   Returns per-square: `(my_attackers, opp_defenders, my_potential_attackers_not_yet_committed)`.
   Surfaces: pile-on opportunity, undefended pieces, hanging captures.

2. **`move_activity_classifier`** (Bucket B)
   Returns for both played_move and best_move: `is_attacking | is_developing | is_retreating | is_passive`.
   Surfaces: passive-when-active-available why-clause.

3. **`development_state`** (Bucket C)
   Returns: list of own minor pieces still on starting squares + game phase.
   Surfaces: opening development why-clauses ("develop knights first", etc.).

4. **`played_opens_tactic` enhancement** (Bucket E)
   Already partially exists via `opp_reply_attacks_played_piece`. Extend to scan deeper plies in `pv_after_played` for forcing sequences.
   Surfaces: walked-into-tactic why-clause.

Plus **eval-guard tuning** for missed_tactic (Bucket D) — code investigation, not a new detector.

**Together these cover 13 of 15 positions** in the audit sample. Positions #12 (small cp_loss) and #13 (fianchetto bishop trade) are accepted as long tail.

**Estimated effort:** ~2-3 days for all four detectors + their JSON variants + R12 wiring.

**Result:** HIGH coverage projected to move from current 39.8% to ~60-70% based on the LOW buckets these detectors absorb.

---

## What NOT to do

- Don't build per-opening pattern detectors (Fried Liver, Légal's, Scandinavian, etc.) — covered by existing trap detection + opening_record.
- Don't build per-piece detectors (knight, bishop, etc.) — geometric helpers cover all pieces.
- Don't try to teach every chess principle — accept the long tail (~5-15% of captions stay generic).
- Don't add LLM-as-renderer until validator + facts infrastructure is in place (currently not).

---

## Open questions for Mohit

1. **Is "active vs passive" detection worth building?** Bucket B is the fuzziest — depends on heuristics. Could be high-leverage or noisy.
2. **Eval-guard threshold:** what's the right cutoff for `missed_tactic` to claim a piece capture vs downgrade to material? Currently +500cp from user POV. Lowering it to +300 might catch more, but risks overclaim.
3. **Phase detection accuracy:** the "opening development" detector relies on `phase=opening`. Does V5's phase detector currently fire at the right move number?
4. **Long tail tolerance:** are you comfortable with ~10-15% of captions staying generic, or do you want to push for 95%+ HIGH? The latter requires LLM phrasing (we discussed costs).
