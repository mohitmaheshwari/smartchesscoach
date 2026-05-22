# Trap Findings — 500-game corpus

## TL;DR

I ran two analyses against the same 500-game v53+ corpus the caption audit used:

1. **Pattern-clustering** ([find_trap_candidates.py](../../backend/scripts/find_trap_candidates.py)) — find recurring opening positions where multiple games hit the same early blunder.
2. **Coverage audit** ([audit_trap_coverage.py](../../backend/scripts/audit_trap_coverage.py)) — list opening families that appear in the corpus but have zero entries in `traps.json`.

**Headline:**

- **The existing 39 traps cover the named-pattern recurring blunders in this corpus.** Pattern-clustering found only 4 multi-game candidates across 1066 early blunders, and on inspection 3 of those are either false-positive groupings or one-off calculation errors — not real trap patterns.
- **The actionable gap is by-opening, not by-pattern.** Several opening families appear in real games but have no trap entries. The top candidates for new trap entries are listed below.
- **Fire rate in the 500-game corpus**: only 6 of 39 traps fired at all (Fried Liver 9, Damiano 5, Petroff Marshall 4, Traxler 2, Englund 1, Halosar 1). 33 traps had 0 fires — likely just rare in this corpus, not broken. **Don't delete on this evidence.**

I did **not** author new trap entries. Adding traps requires voice/content review to match the existing 39 in tone — same risk-of-drift reason I cited for deferring curriculum content. Recommendations below; your call on which to author.

---

## My recommendations (in order of confidence)

### High confidence — worth authoring

1. **Owen's Defense punishment** — 7 games in corpus across 3 raw labels (`Owens Defense`, `Owens Defense 2.d4 Bb7 3.Nc3 e6 4.Bd3`, `Owens Defense...3.Nc3 e6 4.Nf3 Bb4`), zero trap coverage. Owen's (1.e4 b6) has a well-known refutation: 2.d4 Bb7 3.Bd3 e6 4.Nf3 and Black gets cramped. Plus the **Owen's Trap** (4...Nf6?? 5.Bxh7+!). Could author 1 entry: "Owen's Defense 4...Nf6 Trap" — bishop-grab on h7.

2. **Bishop's Opening — Urusov Gambit / Boden-Kieseritzky** — 4 games of Bishop's Opening in corpus, zero trap coverage. We just added the *curriculum* entry for Bishop's, so authoring 1 trap (Urusov Gambit Trap: 2.Bc4 Nf6 3.d4! exd4 4.Nf3) to match the curriculum would close the loop.

3. **Englund Gambit Mate Trap** — 7 games combined (`Englund Gambit`, `Englund Gambit 2.dxe5`), only 1 fire of the existing "Englund Gambit Trap" in london-system. Either the existing trap is mis-labeled to london-system (it should arguably live under `englund-gambit` as a separate family) or the detector isn't matching. We documented the Mate Trap in the curriculum walker's `englund_gambit_response` entry; promoting it to a real `traps.json` entry would let it surface in the trap-fires pipeline too.

### Medium confidence — depends on user demographics

4. **Modern Defense — 1.e4 g6 anti-Modern setups** — 5 games. Common at ~1000-1400 level. No widely-known "trap" but the standard punishment (2.d4 Bg7 3.Nc3 d6 4.Be3 followed by Qd2/O-O-O) for premature ...c5 or ...Nc6 plays is teachable.

5. **Nimzowitsch Defense (1...Nc6)** — 3 games. Known issues but few clean traps. Could skip.

### Low confidence — skip

6. **Van 't Kruijs Opening (1.e3)** — 5 games. Quiet system with no real trap structure.
7. **Reti Opening sidelines** — 5 games total. Rarely trappy at sub-1500 level.
8. **`Unknown` / `Undefined` openings** — 11 games. Just unlabeled imports.

---

## Detail: pattern-clustering candidates (low signal)

Full report: [trap_candidates.md](trap_candidates.md). Summary:

| # | Cluster | Verdict |
|---|---|---|
| 1 | Caro-Kann after 1.e4 c6 2.Bc4 d5 — Qf3/Nf3 blunders | **Not a trap.** Different blunder moves grouped together (Qf3 ≠ Nf3). The teachable point is "exd5 is best", not a named trap. |
| 2 | Italian Game m12 Qd4 (open middlegame) | **Not a trap.** One-off calculation error in a tactical middlegame, not an opening pattern. |
| 3 | Scotch — 4.Ng5 h6 5.Nxf7 Kxf7 6.Bc4+ Ke8?? | **Borderline.** Real pattern (similar to Légal's Mate) but 4.Ng5 is a dubious sacrifice line, rare in serious play. 2 games. |
| 4 | "King's Pawn Opening" Bg5 blunders | **Not a trap.** T3-loose grouping matched 3 games at different move numbers — different positions, same SAN by coincidence. |

**Conclusion from clustering**: the corpus is large enough that if a new named trap were recurring, this analysis would find it. The absence of strong candidates suggests the existing 39 traps cover the corpus well.

## Detail: coverage gaps

Full report: [trap_coverage.md](trap_coverage.md). The top uncovered families (>= 3 games in corpus, normalized):

| Family | Games | Recommendation |
|---|---:|---|
| `kings-pawn-opening-kings-knight-variation` | 9 | These are 1.e4 e5 2.Nf3 lines — *already* covered by italian-game, philidor-defense, petrov-defense traps via transposition. Likely a labeling artifact, not a real gap. |
| `kings-pawn-opening-1...e5` | 6 | Same as above. |
| `van-t-kruijs-opening` | 5 | Skip — quiet system, no trap structure. |
| `englund-gambit-2.dxe5` | 4 | Author. |
| `modern-defense` | 4 + 1 | Author if going for breadth. |
| `bishops-opening` | 4 | Author (matches new curriculum entry). |
| `nimzowitsch-defense` | 3 | Optional. |
| `englund-gambit` | 3 | Author (combined 7 with above). |
| `owens-defense` | 3 | Author. |

## What I'd do if green-lit

If you want me to author the **3 high-confidence traps** (Owen's, Bishop's/Urusov, Englund Mate), I'd:

1. Write each entry to a draft MD first (FEN, setup_moves, trap_line, success_message, voice-matched explanations) — one MD per trap.
2. Wait for your review of voice/accuracy.
3. Merge approved entries into `backend/data/traps.json`.

Time: ~15 min per trap to author, plus engine verification of each line. Total ~45 min for the 3 high-confidence ones. Just say which (or all).

---

## Tools delivered

- [backend/scripts/find_trap_candidates.py](../../backend/scripts/find_trap_candidates.py) — pattern-clustering with 3-tier strictness (exact prefix → opening+blunder+move → opening+blunder)
- [backend/scripts/audit_trap_coverage.py](../../backend/scripts/audit_trap_coverage.py) — uncovered-family + fire-rate audit

Both runnable from `chess-coach-backend` container with `--out <md_path>` and `--max-games 500`.
