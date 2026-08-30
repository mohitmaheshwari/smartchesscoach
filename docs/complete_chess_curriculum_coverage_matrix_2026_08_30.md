# Complete Chess Curriculum — Coverage Matrix

Date: 2026-08-30
Audience: practical chess below 2000, with product delivery optimized for
600–1500.
Status: implementation map; invited-coach review remains a final publication
gate.

## How to read this matrix

This document counts a topic only when the player can learn and prove it. A
detector, caption, opening label, article paragraph, or visible card is not by
itself a lesson.

Coverage labels:

- READY: verified canonical lesson with a working player route.
- PARTIAL: useful content or practice exists, but the complete teaching and
  evidence sequence does not.
- REFERENCE: sound knowledge exists for coaching, but not as a complete lesson.
- DETECTOR: the product can often notice the idea, but cannot yet teach and
  prove it.
- MISSING: no trustworthy end-to-end lesson.

Priority labels:

- CORE: essential for the 600–1500 player and belongs in the first complete
  map.
- GROWTH: practical 1200–1999 knowledge; available when prerequisites and
  player evidence justify it.
- DEFER: specialist theory primarily above 2000 or too rare to displace a more
  useful lesson.

The skill tree stores IDs, prerequisites, ranges, capabilities, and canonical
references. It does not repeat the lesson explanation.

## 1. Board vision and geometry

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Board coordinates, legal movement, check, capture, promotion, castling | CORE | PARTIAL across board services and onboarding | phase_principles.json foundation records plus existing deterministic board logic | Build a diagnostic route; do not force known basics on established players |
| Attacked, defended, loose, and hanging pieces | CORE | PARTIAL; piece-safety focus, detectors, and one PIC lesson exist | Tactical theory: undefended_piece plus the Personal Curriculum lesson contract | Generalize the verified piece-safety workspace |
| Count attackers and defenders before a capture | CORE | PARTIAL in coaching prompts | Tactical theory attached to piece safety | Teach the exact squares, then test on an unlabeled exchange |
| Rays, blockers, pins, x-rays, files, ranks, and diagonals | CORE | PARTIAL detectors; no complete geometry progression | Tactical theory with stable geometry prerequisites | Add line-of-sight lessons before naming advanced motifs |
| Knight jump geometry and fork squares | CORE | PARTIAL through knight_fork | Tactical theory: knight_fork | Add boundary cases where the landing square is unsafe |
| Pawn attack direction, chains, breaks, and promotion races | CORE | PARTIAL across tactics, structures, and endgames | Pawn canon plus endgame canon, referenced by shared prerequisite IDs | Separate movement geometry from strategic structure plans |
| King legal squares, danger squares, and escape squares | CORE | PARTIAL; escape-squares quiz exists | Tactical geometry plus mating lessons | Reuse the quiz as Diagnose/Recall, then add transfer |
| Captures, recaptures, exchanges, and intermediate moves | CORE | PARTIAL; zwischenzug exists but exchange literacy is fragmented | Tactical theory and practical-decision routines | Teach the full capture sequence, not only the first move |

Decision: this family becomes the prerequisite spine. A player with strong
game evidence can test out through a short answer-hidden diagnostic.

## 2. Piece safety and tactical patterns

The tactical canon currently has 17 records: undefended piece, pin to king,
pin to queen, knight fork, pawn fork, back-rank weakness, discovered attack,
discovered check, skewer, overloaded piece, deflection, decoy, trapped piece,
double attack, interference, zwischenzug, and removing the defender.

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Loose and trapped pieces | CORE | PARTIAL | tactical_patterns.json | Complete explanation, counterexample, help, recall, and transfer |
| Forks and double attacks | CORE | PARTIAL | tactical_patterns.json | Unify knight/pawn/general fork prerequisites without losing detector IDs |
| Pins, skewers, and x-rays | CORE | PARTIAL | tactical_patterns.json | Teach line geometry and when the pinned piece can legally or safely move |
| Discovered attacks and discovered checks | CORE | PARTIAL | tactical_patterns.json | Add blocker-removal geometry and defensive recognition |
| Removing and overloading defenders | CORE | PARTIAL | tactical_patterns.json | Teach exploit and defense; require recapture verification |
| Deflection, decoy, interference, and zwischenzug | GROWTH | PARTIAL | tactical_patterns.json | Keep separate IDs but share prerequisites and mixed practice |
| Clearance, attraction, and line opening | GROWTH | MISSING as stable lesson identities | tactical_patterns.json after detector and content verification | Add only when the board claim and grader are deterministic |
| Tactical combinations using more than one motif | GROWTH | DETECTOR/PUZZLE fragments | Derived mixed drills; no duplicate combination taxonomy | Grade one primary skill and record secondary evidence cautiously |

All 17 existing patterns stay visible only after they pass the extended lesson
gate. The expansion adds missing geometry and teaching evidence before adding
famous motif names.

## 3. Mating geometry and attack

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Queen and king mate | CORE | READY | endgame theory: queen_checkmate | Add to the unified progression and evidence path |
| Rook and king mate | CORE | READY | endgame theory: rook_checkmate | Add to the unified progression and evidence path |
| Ladder mate and shrinking the king's box | CORE | PARTIAL inside mate material | Endgame/mating canon | Expose the geometry as a reusable prerequisite |
| Back-rank mate and making an escape square | CORE | PARTIAL | tactical_patterns.json: back_rank_weakness | Complete both attack and prevention |
| Queen-and-bishop battery on f7/f2 or h7/h2 | CORE | PARTIAL through trap/opening content | Canonical mating-pattern record referenced by traps | Teach geometry without requiring one opening move order |
| Rook-and-knight edge-of-board net | GROWTH | MISSING | Mating-pattern canon | Teach the squares before introducing the conventional name |
| Smothered king and blocked flight squares | GROWTH | MISSING | Mating-pattern canon | Require a distinct non-sacrificial counterexample |
| Building and verifying a mating net | GROWTH | PARTIAL through escape-squares logic | Mating-pattern canon plus mixed practice | Count every legal defense before claiming mate |

Named historical labels are optional vocabulary. The transferable board shape
is the skill.

## 4. Calculation and move selection

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Threat scan: what changed after the opponent's move | CORE | PARTIAL in prompts and reviews | phase_principles.json | Turn the prompt into a measured routine |
| Checks, captures, and direct threats as candidate moves | CORE | PARTIAL in many duplicate messages | phase_principles.json | One canonical routine; delivery services reference it |
| Opponent's strongest reply | CORE | PARTIAL in coaching services | phase_principles.json | Require one reply before independent proof |
| Two-move safety scan before committing | CORE | PARTIAL | phase_principles.json | Connect it to the player's actual recurring cutoff |
| Candidate generation and comparison | GROWTH | PARTIAL via engine candidates | phase_principles.json | Player proposes candidates before engine comparison |
| Move order and intermediate moves | GROWTH | PARTIAL | tactical_patterns.json: zwischenzug plus calculation routine | Test whether order changes the opponent's defense |
| Visualization without moving pieces | GROWTH | MISSING systematic progression | phase_principles.json | Increase depth only after board-state accuracy is proven |
| Evaluate the resulting position and know when to stop | GROWTH | MISSING | phase_principles.json | Prefer concrete material, king safety, and activity checks over engine numbers |

Today these ideas are slogans scattered through services. They need one
referenced routine with observable behavior, not another caption table.

## 5. Defense and resilience

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Identify the opponent's immediate threat | CORE | PARTIAL | opponent-threat and practical-routine canon | Diagnose before suggesting a defense |
| Move the target, add a defender, remove the attacker, block, or counterattack | CORE | PARTIAL | phase_principles.json defensive-response records | Compare resources on the same board |
| Create king escape squares and avoid back-rank danger | CORE | PARTIAL | tactical/mating canon | Reuse escape-squares evidence |
| Defend common opening traps | CORE | READY for 23 verified traps | traps.json | Keep defense-first and answer-hidden |
| Simplify an attack by trading the right attacker | CORE | PARTIAL | Strategic canon with tactical verification | Teach which attacker matters, not “trade pieces” generically |
| Find perpetual check, stalemate, fortress, or active counterplay | GROWTH | PARTIAL stalemate; others missing | Endgame/defense canon | Add only with exact or coach-reviewed evidence |
| Continue accurately after a blunder or in a worse position | CORE | MISSING as a lesson | Practical-play canon | Teach the next decision; never use shame or fake optimism |

## 6. Positional play and piece improvement

The strategic canon already contains 10 reference concepts: good bishop,
bishop pair, knight outpost, weak squares, space advantage, development lead,
open file, two weaknesses, king activity, and material imbalance. These are
substantial references, not yet complete mastery lessons.

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Development, center, king safety, and connected rooks | CORE | PARTIAL | Phase principles plus verified opening-fundamental facts | Build transferable positions outside a named opening |
| Improve the worst piece | CORE | REFERENCE/prompts | strategic_imbalances.py | Add board-specific before/after comparisons |
| Open and semi-open files; rook entry squares | CORE | REFERENCE/DETECTOR | strategic_imbalances.py: open_file | Test whether the file has a real target or entry |
| Outposts and squares pawns cannot challenge | CORE | REFERENCE/DETECTOR | strategic_imbalances.py: knight_outpost and weak_squares | Teach the supporting pawn and exchange decision |
| Good bishop, bad bishop, and bishop pair | GROWTH | REFERENCE; related endgames READY | strategic_imbalances.py plus endgame references | Share fact IDs; do not copy explanations |
| Space and pawn breaks | GROWTH | REFERENCE | strategic_imbalances.py plus pawn canon | Counterexample: overextension without support |
| Two weaknesses and switching sides | GROWTH | REFERENCE | strategic_imbalances.py: two_weaknesses | Require plan choice, not one engine move |
| Material imbalances and exchange decisions | GROWTH | REFERENCE | strategic_imbalances.py: material_imbalance | Compare piece activity, king safety, and pawn structure |
| Prophylaxis: stop the opponent's useful plan | GROWTH | PARTIAL detector/prompts | Strategic canon after source consolidation | Ask for the opponent's plan before naming the term |
| Color complexes and control after a bishop trade | GROWTH | PARTIAL under weak_squares | strategic_imbalances.py: weak_squares | Keep as a subskill unless corpus evidence proves a separate need |

structure_plan_database.py is not a second canon. Its reachable content will be
mapped to these strategic records, pawn structures, openings, or endgames
through a parity-tested adapter.

## 7. Pawn structures and plans

The pawn canon already contains 10 reference structures: isolated queen pawn,
hanging pawns, doubled pawns, kingside majority, queenside majority, Carlsbad,
French Advance, Open Sicilian, symmetrical structure, and closed center.

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Passed pawn, protected passer, and outside passer | CORE | READY/PARTIAL in endgames | Endgame canon with pawn prerequisite IDs | Reuse, then test in a middlegame transfer |
| Isolated and doubled pawns | CORE | REFERENCE | pawn_structures.py | Teach both weakness and activity compensation |
| Backward pawns and the square in front | GROWTH | DETECTOR, no canonical lesson | pawn_structures.py | Add after a quality-audited detector link |
| Hanging pawns | GROWTH | REFERENCE | pawn_structures.py: hanging_pawns | Teach mobility versus fixed targets |
| Pawn chains, base, head, and breaks | CORE | REFERENCE/opening fragments | pawn_structures.py | Teach outside a French-only move order |
| Majorities and creating a passer | CORE | REFERENCE/READY fragments | pawn_structures.py plus endgame canon | Connect plan to an actual pawn race |
| Carlsbad and minority attack | GROWTH | REFERENCE | pawn_structures.py: carlsbad | Teach the target created on c6, not jargon alone |
| Open Sicilian, French, closed-center, and symmetrical plans | GROWTH | REFERENCE | pawn_structures.py | Route only when position/repertoire evidence makes them relevant |
| Pawn islands, lever recognition, and reserve tempi | GROWTH | MISSING as complete lessons | pawn_structures.py or endgame canon according to use | Add with board-verifiable definitions |

## 8. Openings and traps

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Universal opening habits and exceptions | CORE | PARTIAL; 28 opening-mistake records | opening_mistakes.json | Teach why the move failed in this position, not “never do X” |
| Personal White repertoire | CORE | 37 verified lessons across catalog | opening_curriculum.json | Select by connected repertoire and actual games |
| Personal responses to 1.e4 and 1.d4 | CORE | 37 verified lessons across catalog | opening_curriculum.json | Avoid forcing every player into the same repertoire |
| Plans and pawn structures after the memorized moves | CORE/GROWTH | PARTIAL in authored openings | opening_curriculum.json referencing pawn canon | Make plans transferable and avoid duplicated structure prose |
| Recognition labels and aliases | SUPPORT | 42 records without distinct lessons | opening alias mapping | Route aliases to a verified family; do not create duplicate cards |
| Truly distinct missing opening families | GROWTH | Audit required among the 42 records | opening_curriculum.json | Author only when the label represents a different player decision |
| Trap defense | CORE | 23 READY, defense-first | traps.json | Publish verified lines only |
| Remaining trap records | SUPPORT/GROWTH | 32 fail truth/content/evidence | traps.json backlog | Repair rather than hide; no public lesson until verified |

Opening mastery is not line recall alone. Proof requires recognizing the
position, choosing a sound move without the answer, explaining the plan when
needed, and later navigating a real game opportunity.

## 9. Endgames and conversion

All 20 current canonical endgames and their 60 positions are legally and
analytically verified. They cover queen mate, rook mate, opposition, key
squares, rule of the square, breakthrough, king centralization, Lucena,
Philidor, rook activity, stopping promotion, stalemate, good versus bad bishop,
opposite-color bishops, knight versus bishop, knight blockade, creating a
passed pawn, zugzwang, outside passer, and two pawns versus one.

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| Existing 20-lesson catalog | CORE/GROWTH | READY | endgame_theory_tree.json | Add every verified lesson to the unified progression |
| Converting an extra piece or healthy extra pawn | CORE | PARTIAL across lessons | Endgame/conversion canon | Teach simplification boundaries and opponent counterplay |
| Triangulation and reserve pawn moves | GROWTH | PARTIAL via zugzwang | endgame_theory_tree.json | Add only if distinct transfer evidence justifies a node |
| Cut off the king and check from a safe distance in rook endings | GROWTH | PARTIAL | endgame_theory_tree.json | Extend practical rook technique beyond named positions |
| Queen versus advanced pawn | GROWTH | MISSING | endgame_theory_tree.json | Add exact tablebase-backed examples |
| Wrong-color bishop pawn, fortress, and drawing resources | GROWTH | PARTIAL opposite bishops/stalemate | endgame_theory_tree.json | Add exact examples with clear prerequisites |
| Rare theoretical rook/queen endings and deep tablebase studies | DEFER | MISSING | None in V1 | Do not displace high-frequency practical knowledge |

“No completion backlog” for the existing catalog means its current 20 lessons
are finished. It does not mean chess has no other useful under-2000 endings.

## 10. Practical play, habits, and self-correction

| Skill family | Priority | Current coverage | Canonical destination | Completion decision |
| --- | --- | --- | --- | --- |
| A short pre-move routine adapted to the player's failure | CORE | PARTIAL across many services | phase_principles.json referenced by coaching surfaces | Teach one surviving instruction, then measure it |
| Clock use: when to slow down and when to move | CORE | DETECTOR/profile signals | phase_principles.json | Use time-control evidence; never infer when clocks are absent |
| Playing while ahead: reduce counterplay and convert | CORE | PARTIAL prompts | Conversion routine linked to position evidence | Avoid the false rule “always trade when ahead” |
| Playing while worse: activity, complications, and drawing chances | CORE/GROWTH | PARTIAL prompts | Defense/practical canon | Keep moves sound and language honest |
| Choosing exchanges | CORE | PARTIAL | Strategic/practical canon | Compare the position after the exchange |
| Recovering after a loss or blunder | CORE | PARTIAL coach tone, no measured lesson | phase_principles.json | Focus on the next decision and prevent emotional carryover |
| Postgame prediction, reflection, and one lesson extraction | CORE | PARTIAL existing reflection | Existing reflection owner | Feed one supported misconception into the teaching profile |
| Recognizing when a principle has an exception | CORE/GROWTH | MISSING systematic treatment | Every canonical lesson's counterexample field | This is a delivery contract, not a separate trivia course |

## 11. Alias and deferral rules

An item is an alias when it produces the same board decision, prerequisite,
grader, and transferable plan as an existing skill. Aliases route to the same
skill identity and may preserve their familiar name for recognition.

An item is distinct when at least one of those four things changes. A distinct
item receives a new stable skill ID only after the canonical lesson and
verification evidence exist.

Defer from V1:

- exhaustive opening variations and memorization beyond the player's
  repertoire;
- rare named traps with no corpus reach or verified defensive lesson;
- specialist compositions and theoretical endings primarily above 2000;
- separate nodes for every historical tactical or mating name when the tested
  board geometry is identical;
- strategic concepts whose only grader would be an unreviewed LLM opinion.

Nothing deferred is deleted from recognition or research data. It simply does
not appear as a finished player lesson.

## 12. Implementation waves

1. Foundation spine: geometry, piece safety, threat scan, opponent reply,
   escape squares, and existing basic mates/endgames.
2. Existing verified breadth: 17 tactical patterns, 23 traps, 37 openings, and
   all 20 endgames through the shared personalized workspace.
3. Strategic core: the 10 strategic imbalances and 10 pawn structures, after
   the positional evidence protocol and compatibility adapter pass.
4. Practical transfer: mixed practice, coached opportunities, organic
   application evidence, clock-aware routines, and retention.
5. Growth additions: missing mating nets, calculation depth, defensive
   resources, practical rook/queen endings, and genuinely distinct opening
   families.

Every wave stays hidden behind PERSONALIZED_TEACHING_ENABLED until the
canonical content, state contract, route, instrumentation, and tests are
complete. Mohit and the invited coaches review the full candidate before any
public rollout.

## Verdict

ChessGuru is not missing a giant pile of random chess topics. It is missing a
foundation spine, complete lesson treatment for concepts it already detects,
systematic calculation and defense training, practical transfer, and one
honest evidence loop across all subjects.

The correct expansion is therefore:

- finish and connect existing verified content;
- turn reference knowledge into complete lessons;
- add only the high-value gaps identified above;
- personalize delivery from auditable evidence;
- keep each chess fact in one canonical owner;
- publish nothing that cannot teach, test, transfer, and explain its evidence.
