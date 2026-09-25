# ChessGuru Opening Reference Catalog

**Status:** Research ledger, 2026-09-04. This is not a new runtime data source. It maps every current `opening_curriculum.json` entry to external evidence that can be used when authoring and verifying the canonical curriculum.

## Reference policy

Use the references in this order:

1. **Identity and position:** [lichess-org/chess-openings](https://github.com/lichess-org/chess-openings) is the primary opening-name source. Its CC0 dataset provides ECO, canonical English name, PGN, UCI, and EPD. Match by resulting position, not only by a label or one move order.
2. **What players actually choose:** [Lichess Opening Explorer](https://lichess.org/analysis#explorer) provides move frequency and results from master games and rating-filtered Lichess games. Query the position reached by the canonical line and use the production player's rating band.
3. **Opening family and human-browsable branches:** [Lichess Opening Tree](https://lichess.org/opening/tree) is the reference index for families and named variations. The links below point to its family page or a search for the exact variation.
4. **Move and claim verification:** [Stockfish](https://github.com/official-stockfish/Stockfish) verifies candidate moves, acceptable alternatives, tactical punishments, and claims that a move loses. It does not supply teaching prose.
5. **ChessGuru player evidence:** production games decide which reply, mistake, trap, and plan should be taught first. Global popularity must not override what this player repeatedly reaches.

Do not copy prose from random articles, videos, or community studies into the curriculum. We author the explanation in ChessGuru's voice from verified board facts. A Lichess page with no written description is still a valid identity, line, continuation, and example-game reference.

## Complete mapping of the current system catalog

Every one of the 79 current keys is listed below. Several are duplicate labels or game-derived variation snapshots, not independent opening families. They should reference their parent curriculum entry instead of becoming separate shallow lessons.

| Canonical family | Current ChessGuru keys covered | Primary Lichess reference | Curriculum treatment |
|---|---|---|---|
| London System | `london_system`, `queens_pawn_opening_accelerate` | [London System](https://lichess.org/opening/London_System) | One family lesson; Accelerated London is a reply/order branch. |
| Italian Game | `italian_game`, `italian_game_black`, `four_knights_game_italian_vari`, `giuoco_piano_game_four_knights`, `italian_game_knight_attack_nor`, `italian_game_knight_attack` | [Italian Game](https://lichess.org/opening/Italian_Game) | One family with side-aware plans and Giuoco Piano, Two Knights/Knight Attack, and Four Knights transposition branches. |
| Sicilian Defense | `sicilian_defense`, `sicilian_defense_bowdler_attac`, `sicilian_defense_old_sicilian_`, `sicilian_dragon`, `sicilian_najdorf` | [Sicilian Defense](https://lichess.org/opening/Sicilian_Defense) | Parent lesson plus Bowdler, Old Sicilian, Dragon, and Najdorf branches. Dragon/Najdorf may become advanced child lessons after the shared decisions are understood. |
| Caro-Kann Defense | `caro_kann`, `caro_kann_defense`, `caro_kann_defense_exchange_var`, `caro_kann_defense_2_nf3_d5_3_e`, `caro_kann_defense_2_nf3_d5`, `caro_kann_defense_2_f4_d5_3_e5`, `caro_kann_defense_2_nc3_d5`, `caro_kann_defense_advance_botv`, `caro_kann_defense_advance_vari`, `caro_kann_defense_2_d4_d5_3_nc` | [Caro-Kann Defense](https://lichess.org/opening/Caro-Kann_Defense) | One family with Advance, Exchange, Two Knights, Classical, and Botvinnik-Carls decision branches; remove the duplicate family shell. |
| French Defense | `french_defense`, `french_defense_knight_variatio`, `french_defense_normal_variatio` | [French Defense](https://lichess.org/opening/French_Defense) | One family; Knight/Normal labels become 2.Nf3 and 2.d4 d5 3.Nc3 reply branches. |
| Queen's Gambit | `queens_gambit`, `queens_gambit_accepted_3_nf3`, `qgd` | [Queen's Gambit](https://lichess.org/opening/Queens_Gambit) | One parent lesson with Accepted and Declined branches; do not teach “gambit” as a forced pawn sacrifice. |
| Scandinavian Defense | `scandinavian_defense`, `scandinavian_defense_2_e5`, `scandinavian_defense_mieses_ko` | [Scandinavian Defense](https://lichess.org/opening/Scandinavian_Defense) | One family with 2.exd5 main decision, 2.e5 sideline, and Mieses-Kotroc branch. Correct the current truncated spelling. |
| Ruy Lopez | `ruy_lopez` | [Ruy Lopez](https://lichess.org/opening/Ruy_Lopez) | Family lesson organized around pressure on c6/e5, Black's main replies, and resulting plans rather than a long memorized line. |
| Scotch Game | `scotch_game`, `scotch_game_3_exd4`, `scotch_game_3_d6`, `scotch_game_3_exd4_4_nxd4_nxd4` | [Scotch Game](https://lichess.org/opening/Scotch_Game) | One family with ...exd4, ...d6, and early exchange branches. |
| Petrov's Defense | `petrov_defense`, `petrovs_defense_classical_vari`, `petrovs_defense`, `petrovs_defense_three_knights_` | [Petrov's Defense search](https://lichess.org/opening?q=Petrov%27s%20Defense) | Normalize Petrov/Petroff/Petrov's identity, then teach Classical and Three Knights branches. |
| King's Indian Defense | `kings_indian_defense` | [King's Indian Defense](https://lichess.org/opening/Kings_Indian_Defense) | One family; first teach the center-versus-kingside plan before named theory. |
| Nimzo-Indian Defense | `nimzo_indian_defense`, `nimzo_indian` | [Nimzo-Indian Defense](https://lichess.org/opening/Nimzo-Indian_Defense) | Merge duplicate keys into one family. Keep Nimzowitsch Defense separate. |
| Slav Defense | `slav_defense` | [Slav Defense](https://lichess.org/opening/Slav_Defense) | One family lesson centered on supporting d5 while freeing the light bishop. |
| English Opening | `english_opening` | [English Opening](https://lichess.org/opening/English_Opening) | One family with structure/transposition decisions; avoid pretending one fixed line defines the opening. |
| Modern Defense | `modern_defense` | [Modern Defense](https://lichess.org/opening/Modern_Defense) | One family lesson on allowing the center, attacking it later, and the cost of delaying development. |
| Philidor Defense | `philidor_defense`, `philidor_defense_3_bc4`, `philidor_defense_3_d4` | [Philidor Defense](https://lichess.org/opening/Philidor_Defense) | One family with 3.d4 and 3.Bc4 branches, including verified Legal-pattern danger without claiming every pin loses. |
| Bishop's Opening | `bishops_opening`, `bishops_opening_berlin_defense`, `bishops_opening_2_nc6` | [Bishop's Opening](https://lichess.org/opening/Bishops_Opening) | First complete reference implementation. Add Berlin, ...Nc6, ...Bc5, ...c6/...d5, Calabrese, Urusov, and Boden-Kieseritzky decisions only after line and engine verification. |
| Vienna Game | `vienna_game` | [Vienna Game](https://lichess.org/opening/Vienna_Game) | One family with quiet development, Vienna Gambit, and ...Nf6/...Nc6 reply decisions. |
| Englund Gambit | `englund_gambit_response`, `englund_gambit`, `englund_gambit_2_dxe5` | [Englund Gambit](https://lichess.org/opening/Englund_Gambit) | One family. Teach White's safe response first; label Black's practical tricks as opponent-error-dependent. |
| King's Gambit | `kings_gambit`, `kings_gambit_declined_queens_k` | [King's Gambit](https://lichess.org/opening/Kings_Gambit) | One family with Accepted and Declined branches; Queen's Knight Defense is a reply branch. |
| Four Knights Game | `four_knights_game`, `four_knights` | [Four Knights Game](https://lichess.org/opening/Four_Knights_Game) | Merge duplicate keys; Italian transpositions remain linked to the Italian family. |
| Pirc Defense | `pirc_defense` | [Pirc Defense](https://lichess.org/opening/Pirc_Defense) | One family; contrast it clearly with Modern Defense through the committed ...Nf6 move and center pressure. |
| Alekhine Defense | `alekhine_defense` | [Alekhine Defense](https://lichess.org/opening/Alekhine_Defense) | One family lesson on inviting the pawn advance and attacking the extended center. |
| King's Pawn Game | `kings_pawn_opening_1_e5`, `kings_pawn_opening_kings_knigh`, `kings_pawn_opening`, `kings_pawn_opening_leonardis_v` | [King's Pawn Game](https://lichess.org/opening/Kings_Pawn_Game) | Foundational parent/reference entry. King's Knight and Leonardis are branches; do not compete with Italian, Ruy, Scotch, Vienna, or Bishop's Opening lessons after those positions are reached. |
| Van't Kruijs Opening | `van_t_kruijs_opening_1_e5`, `van_t_kruijs_opening` | [Van't Kruijs Opening](https://lichess.org/opening/Vant_Kruijs_Opening) | Merge duplicate keys; likely reference-first unless production use justifies a full lesson. |
| Center Game | `center_game_accepted_normal_va`, `center_game` | [Center Game](https://lichess.org/opening/Center_Game) | One family with Accepted/Normal branch and early-queen-development trade-off. |
| Nimzowitsch Defense | `nimzowitsch_defense` | [Nimzowitsch Defense](https://lichess.org/opening/Nimzowitsch_Defense) | Separate family. The current ChessGuru normalizer incorrectly groups this under Nimzo-Indian and must be corrected. |
| Queen's Pawn Game | `queens_pawn_opening_chigorin_v` | [Queen's Pawn Game search](https://lichess.org/opening?q=Queen%27s%20Pawn%20Game%20Chigorin%20Variation) | Parent/reference branch. Do not confuse it with the Chigorin Defense to the Queen's Gambit. |
| Grünfeld Defense | `grunfeld_defense` | [Grünfeld Defense search](https://lichess.org/opening?q=Gr%C3%BCnfeld%20Defense) | One family. Normalize Grunfeld/Gruenfeld/Grünfeld aliases to the same ID. |
| Queen's Indian Defense | `queens_indian` | [Queen's Indian Defense](https://lichess.org/opening/Queens_Indian_Defense) | One family lesson on controlling e4 and developing through ...b6/...Bb7. |
| Benoni Defense | `benoni_defense` | [Benoni Defense search](https://lichess.org/opening?q=Benoni%20Defense) | One family; separate Old Benoni and Modern Benoni branches only when player evidence calls for them. |
| Budapest Gambit | `budapest_gambit` | [Budapest Gambit search](https://lichess.org/opening?q=Budapest%20Gambit) | One family; teach White's safe development and Black's tactical pressure, not only traps. |
| Dutch Defense | `dutch_defense` | [Dutch Defense](https://lichess.org/opening/Dutch_Defense) | One family with Stonewall, Leningrad, and Classical structures introduced by player need. |
| Albin Countergambit | `albin_counter_gambit` | [Albin Countergambit search](https://lichess.org/opening?q=Queen%27s%20Gambit%20Declined%20Albin%20Countergambit) | One family; teach the advanced d4 pawn, safe defence, and traps as conditional consequences. |

## Immediate catalog corrections revealed by the mapping

- `nimzowitsch_defense` is currently normalized as Nimzo-Indian even though they are different openings.
- Petrov/Petroff naming is inconsistent across four keys.
- Bishop's, King's, Queen's, and Van't Kruijs apostrophes are missing from several displayed names.
- Caro-Kann, Grünfeld, Mieses-Kotroc, and Albin Countergambit spelling/hyphenation need canonical normalization.
- Several snapshot keys are truncated (`...vari`, `...attac`, `...ko`) and must never become player-facing IDs.
- `italian_game_black` is a side-specific view, not a separate opening identity.
- `caro_kann` and `caro_kann_defense`, `four_knights_game` and `four_knights`, and `nimzo_indian_defense` and `nimzo_indian` are duplicate family identities.

## Trap-to-opening linkage audit

**Verdict: the current trap links are not complete or reliable enough to ship as personalized opening teaching.** The canonical file contains 54 trap records, but runtime association is based on exact strings rather than a stable opening identity. Position-matching every setup and legal continuation against the official Lichess openings dataset exposed mis-parented records, four family-key mismatches, overlapping records, and three illegal lines.

This table is the reviewed destination ledger. It does not duplicate trap moves or prose; names refer to records that remain canonical in `backend/data/traps.json`.

| Canonical opening family | Canonical trap records that should appear with the opening | Required correction |
|---|---|---|
| London System | None currently verified | Move `Englund Gambit Trap` to Englund Gambit; its position is not a London System position. |
| Italian Game | `Fried Liver Attack`; `Blackburne Shilling Gambit`; `Traxler Counterattack`; `Lolli Variation` | Move the two mis-parented records below. Block `Lolli Variation` until its illegal `Kxf7` step is repaired and reverified. |
| Sicilian Defense | `Siberian Trap`; `Magnus Smith Trap`; `Wing Gambit` | Keep linked; teach each only after the triggering opponent choice. |
| Caro-Kann Defense | `Caro-Kann Smothered Mate`; `Caro-Kann Classical Pin` | Keep linked; verify the recovery/refusal line before publication. |
| French Defense | `French Winawer Poisoned Pawn`; `French Advance Milner-Barry Gambit`; `Milner-Barry Gambit` | Review the two Milner-Barry records for overlap and teach one coherent decision path. |
| Queen's Gambit | `Elephant Trap`; `Lasker Trap`; `Rubinstein Trap`; `Cambridge Springs Trap`; `Marshall Trap`; `QGA Greedy ...b5 Trap (Qf3)` | Keep under Accepted/Declined child branches rather than showing all six at family entry. |
| Scandinavian Defense | `Portuguese Gambit Trap`; `Scandinavian Queen Danger` | Keep provisionally. Recheck the Portuguese label because the stored continuation reaches a Lasker Variation position. |
| Ruy Lopez | `Noah's Ark Trap`; `Mortimer Trap`; `Tarrasch Trap (Open Lopez)`; `Fishing Pole Trap` | Block `Tarrasch Trap (Open Lopez)` until its illegal `Nxe4` step is repaired and reverified. |
| Scotch Game | `Mieses Variation` | Replace the broken `scotch` → `scotch_game` exact-key dependency with the canonical opening ID. |
| Petrov's Defense | `Stafford Gambit Trap`; `Petroff Marshall Trap`; `Cochrane Gambit`; `Petrov Fork Trap`; `Stafford Gambit` | Review the two Stafford records for duplication or define their distinct teaching moments. |
| King's Indian Defense | `King's Indian Bayonet Trap` | Keep linked under the Bayonet branch, not the family introduction. |
| Nimzo-Indian Defense | `Nimzo-Indian Hubner Trap` | Replace the broken `nimzo_indian` → `nimzo_indian_defense` exact-key dependency. |
| Slav Defense | `Slav Main Line Trap` | Keep linked. |
| English Opening | None currently verified | Author only after a legal, engine-verified line is selected from player evidence. |
| Modern Defense | None currently verified | Same rule; absence is better than a generic or mislabelled trap. |
| Philidor Defense | `Legal's Mate`; `Philidor's Legal Mate`; `Philidor Legal's Mate`; `Opera Game Finale` | Re-parent `Legal's Mate` from Italian and `Opera Game Finale` from its standalone pseudo-family; deduplicate the three Legal-pattern records into distinct moments or one lesson. |
| Bishop's Opening | `Scholar's Mate Defense Trap` | Re-parent from Italian Game: its stored setup matches ECO C23 Bishop's Opening. This is the currently verified trap link; Calabrese, Urusov, and Boden-Kieseritzky ideas are candidates, not shipped records. |
| Vienna Game | `Frankenstein-Dracula Variation` | Keep linked. |
| Englund Gambit | `Englund Gambit Trap`; `Englund Gambit Mate Trap` | Re-parent the first from London and replace `englund_gambit` / `englund_gambit_response` string matching with the canonical opening ID. |
| King's Gambit | `Kieseritzky Gambit Attack` | Keep linked under the Accepted/Kieseritzky branch. |
| Four Knights Game | `Halloween Gambit` | Replace the broken `four_knights` → `four_knights_game` exact-key dependency. |
| Pirc Defense | None currently verified | Do not manufacture a trap merely to fill the page. |
| Alekhine Defense | None currently verified | Do not manufacture a trap merely to fill the page. |
| King's Pawn Game | `Damiano Defense Punishment` | Re-parent from Philidor Defense; the stored setup is the Damiano Defense in ECO C40. |
| Van't Kruijs Opening | None currently verified | Keep reference-only until player evidence and a verified line justify teaching. |
| Center Game | None currently verified | Keep reference-only until player evidence and a verified line justify teaching. |
| Nimzowitsch Defense | None currently verified | Do not borrow the Nimzo-Indian trap; these are different openings. |
| Queen's Pawn Game | None currently verified | Keep reference-only until player evidence and a verified line justify teaching. |
| Grünfeld Defense | `Grunfeld Exchange Trap` | Link through normalized `grunfeld_defense`; retain the player-facing Grünfeld spelling. |
| Queen's Indian Defense | `Queen's Indian Bishop Trap` | Keep linked. |
| Benoni Defense | `Benoni Snake Trap` | Keep linked. |
| Budapest Gambit | `Kieninger Trap`; `Budapest Smothered Mate` | Keep linked. |
| Dutch Defense | `Dutch Defense Mate` | Keep linked under the relevant ...f5/...g5 structure. |
| Albin Countergambit | None currently verified | Add only after its full legal line, defensive response, and recovery continuation are verified. |

Four canonical trap records currently belong to opening families absent from the 34-family curriculum: `Halosar Trap` (Blackmar-Diemer Gambit), `Tennison Gambit Trap`, `Monticelli Trap` (Bogo-Indian Defense), and `Owen's Defense Greek-Gift Trap`. They remain valid catalog candidates, but they must not be forced under an unrelated opening merely to make them visible. `Halosar Trap` is blocked until its illegal `Bxc3` step is repaired and reverified.

### Runtime linkage contract

1. `backend/data/traps.json` remains the one source of trap positions, moves, explanations, and metadata.
2. Give every trap a stable `trap_id` and a canonical `opening_id`; never join a trap to an opening by display name, filename spelling, or ad-hoc hyphen conversion.
3. Opening lessons reference trap IDs, or query canonical traps by `opening_id`. They must not copy trap lines into `opening_curriculum.json`.
4. A linked trap declares `trap_color`, the opponent move that permits it, the punishment, the best defence, the safe continuation when the opponent refuses, and the curriculum branch where it becomes relevant.
5. The UI reveals only stage-appropriate traps for the player's side and active focus. A trap is a conditional teaching moment, not the definition of the opening.
6. Publication requires a fully legal line, exact position match, engine verification of tactical claims, an independent board check, and plain-language voice review.
7. One validator must fail CI for an unknown `opening_id`, duplicate `trap_id`, illegal move, unreachable position, missing explanation, or copied/divergent trap content.

### Known quality blockers in the canonical trap file

- Three full lines are illegal as stored: `Lolli Variation` at `Kxf7`, `Tarrasch Trap (Open Lopez)` at `Nxe4`, and `Halosar Trap` at `Bxc3`.
- Ten trap records contain at least one line step without an explanation.
- The two Stafford records and the three Legal-pattern records need explicit deduplication or clearly different teaching purposes.
- Public opening guides currently use trap content embedded in `opening_curriculum.json`, while authenticated lessons use `traps.json`, and the in-game teaching catalog uses a separate hardcoded 18-trap library. These parallel paths violate the single-source contract and can teach different material for the same opening.

## How to turn each reference into a ChessGuru lesson

For every family above, the authoring pass must produce evidence rather than copy an encyclopedia entry:

1. Resolve the shortest canonical position and all relevant transpositions from the Lichess opening dataset.
2. Query Lichess Explorer for the replies actually common in the player's rating band, plus the master database as a correctness cross-check.
3. Query ChessGuru production games for the replies and mistakes this audience actually reaches.
4. Select a small set of decisions that cover the player's likely games; do not dump every named variation.
5. Use Stockfish to verify candidate moves, alternatives, tactical consequences, and recovery after deviations.
6. Link applicable traps from the canonical `traps.json`; verify the opponent error, punishment, defence, and refusal continuation.
7. Author plain-language teaching from the verified facts and run legal-move, exact-SAN, voice, route, and independent-checkpoint validators.
8. Publish only when the entry satisfies the Guided Chess Curriculum contract. Otherwise keep it as a reference entry, not a lesson.

## Source limitations

- Opening frequency is not the same as instructional importance. It informs prioritization but does not decide it alone.
- Win rate is affected by rating, colour, time control, and player selection. It must not be translated directly into “this move is best.”
- A named gambit or trap is not necessarily objectively sound.
- Opening pages sometimes lack explanatory prose; ChessGuru still needs independently authored teaching.
- Stockfish can verify chess consequences but cannot decide the clearest human explanation or whether a concept is timely for one student.
