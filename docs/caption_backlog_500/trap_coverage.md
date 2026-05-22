# Trap-coverage audit — 500-game corpus

Scanned 500 games (v53+).

`traps.json` currently covers **25 opening families** with **41 total trap entries**.

Corpus contained **334 distinct opening labels** (normalized to **136 families**).

## 1. Opening families in corpus with NO trap entries

These are the corpus-frequent families that have zero `traps.json` coverage. High-frequency entries here are the most likely candidates for adding traps.

| Family (normalized) | Games in corpus | Raw labels seen |
|---|---:|---|
| `kings-pawn-opening-kings-knight-variation` | 9 | `Kings Pawn Opening Kings Knight Variation` |
| `unknown` | 7 | `Unknown` |
| `kings-pawn-opening-1...e5` | 6 | `Kings Pawn Opening 1...e5` |
| `van-t-kruijs-opening` | 5 | `Van t Kruijs Opening` |
| `englund-gambit-2.dxe5` | 4 | `Englund Gambit 2.dxe5` |
| `modern-defense-with-1-e4-2.d4-bg7-3.nf3` | 4 | `Modern Defense with 1 e4 2.d4 Bg7 3.Nf3` |
| `undefined` | 4 | `Undefined` |
| `bishops-opening` | 4 | `Bishops Opening` |
| `nimzowitsch-defense` | 3 | `Nimzowitsch Defense` |
| `englund-gambit` | 3 | `Englund Gambit` |
| `owens-defense` | 3 | `Owens Defense` |
| `reti-opening-queenside-fianchetto-variation-2.d4-bb7-3.c4` | 3 | `Reti Opening Queenside Fianchetto Variation 2.d4 Bb7 3.c4` |
| `queens-pawn-opening-1...c6-2.c4` | 2 | `Queens Pawn Opening 1...c6 2.c4` |
| `kings-pawn-opening-kings-knight-gunderam-defense-3.bc4` | 2 | `Kings Pawn Opening Kings Knight Gunderam Defense 3.Bc4` |
| `indian-game-2.e3-g6-3.bd3-bg7` | 2 | `Indian Game 2.e3 g6 3.Bd3 Bg7` |
| `reti-opening-kingside-fianchetto-variation-2.e4-bg7` | 2 | `Reti Opening Kingside Fianchetto Variation 2.e4 Bg7` |
| `owens-defense-2.d4-bb7-3.nc3-e6-4.bd3` | 2 | `Owens Defense 2.d4 Bb7 3.Nc3 e6 4.Bd3` |
| `owens-defense...3.nc3-e6-4.nf3-bb4` | 2 | `Owens Defense...3.Nc3 e6 4.Nf3 Bb4` |
| `indian-game-east-indian-przepiorka-variation-3...bg7-4.bg2-o-o` | 1 | `Indian Game East Indian Przepiorka Variation 3...Bg7 4.Bg2 O O` |
| `indian-game` | 1 | `Indian Game` |
| `alekhines-defense-normal-variation-3.bc4` | 1 | `Alekhines Defense Normal Variation 3.Bc4` |
| `modern-defense-with-1-e4-2.d4-bg7-3.be3` | 1 | `Modern Defense with 1 e4 2.d4 Bg7 3.Be3` |
| `three-knights-opening-3...d6` | 1 | `Three Knights Opening 3...d6` |
| `queens-pawn-opening-pseudo-catalan-variation-3...bf5-4.bg2-e6-5.o-o` | 1 | `Queens Pawn Opening Pseudo Catalan Variation 3...Bf5 4.Bg2 e6 5.O O` |
| `van-geet-opening-1...c5-2.nf3` | 1 | `Van Geet Opening 1...c5 2.Nf3` |

## 2. Existing trap fire rate in 500-game corpus

Which existing traps in `traps.json` are actually firing in real games?

| Trap name | Fires in 500 games |
|---|---:|
| **Fried Liver Attack** (italian-game) | 9 |
| **Legal's Mate** (italian-game) | 0 |
| **Blackburne Shilling Gambit** (italian-game) | 0 |
| **Scholar's Mate Defense Trap** (italian-game) | 0 |
| **Traxler Counterattack** (italian-game) | 2 |
| **Lolli Variation** (italian-game) | 0 |
| **Siberian Trap** (sicilian-defense) | 0 |
| **Magnus Smith Trap** (sicilian-defense) | 0 |
| **Wing Gambit** (sicilian-defense) | 0 |
| **Elephant Trap** (queens-gambit) | 0 |
| **Lasker Trap** (queens-gambit) | 0 |
| **Rubinstein Trap** (queens-gambit) | 0 |
| **Cambridge Springs Trap** (queens-gambit) | 0 |
| **Englund Gambit Trap** (london-system) | 1 |
| **Caro-Kann Smothered Mate** (caro-kann) | 0 |
| **King's Indian Bayonet Trap** (kings-indian-defense) | 0 |
| **Portuguese Gambit Trap** (scandinavian-defense) | 0 |
| **Noah's Ark Trap** (ruy-lopez) | 0 |
| **Mortimer Trap** (ruy-lopez) | 0 |
| **Tarrasch Trap (Open Lopez)** (ruy-lopez) | 0 |
| **Philidor's Legal Mate** (philidor-defense) | 0 |
| **Damiano Defense Punishment** (philidor-defense) | 5 |
| **Stafford Gambit Trap** (petrov-defense) | 0 |
| **Petroff Marshall Trap** (petrov-defense) | 4 |
| **Cochrane Gambit** (petrov-defense) | 0 |
| **Kieninger Trap** (budapest-gambit) | 0 |
| **Dutch Defense Mate** (dutch-defense) | 0 |
| **Opera Game Finale** (opera-game) | 0 |
| **French Winawer Poisoned Pawn** (french-defense) | 0 |
| **French Advance Milner-Barry Gambit** (french-defense) | 0 |
| **Slav Main Line Trap** (slav-defense) | 0 |
| **Nimzo-Indian Hubner Trap** (nimzo-indian) | 0 |
| **Frankenstein-Dracula Variation** (vienna-game) | 0 |
| **Queen's Indian Bishop Trap** (queens-indian) | 0 |
| **Grunfeld Exchange Trap** (grunfeld-defense) | 0 |
| **Benoni Snake Trap** (benoni-defense) | 0 |
| **Halosar Trap** (blackmar-diemer-gambit) | 1 |
| **Tennison Gambit Trap** (tennison-gambit) | 0 |
| **Monticelli Trap** (bogo-indian) | 0 |
| **Kieseritzky Gambit Attack** (kings-gambit) | 0 |
| **Mieses Variation** (scotch) | 0 |

## 3. Honest assessment

- The pattern-clustering analysis (`find_trap_candidates.py`) found only 4 multi-game clusters across 1066 early blunders. On inspection most are either single-position calculation errors or false-positive groupings of different blunders. The existing 39 traps appear to cover the recurring named-trap patterns in this 500-game corpus.
- Coverage gaps (Section 1 above) are the more actionable list — opening families that appear in real games but have zero trap entries. Mohit to judge which deserve authoring.
- Low-fire traps (Section 2 with 0 fires) may still be valid — just rare in this particular corpus. Don't delete on small-sample evidence.
