"""
Opening Plans Database - 20 Common Openings

Each opening has:
- Name and ECO code
- Key moves to identify it
- Main PLANS (not just moves)
- Teaching points for 800-1800 players
- Simple explanations without jargon
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class OpeningPlan:
    """A complete opening plan for teaching"""
    name: str
    eco_codes: List[str]  # ECO codes this covers
    identifying_moves: List[str]  # Move sequence to identify
    main_ideas: List[str]  # 2-3 main plans in plain language
    key_squares: List[str]  # Important squares to highlight
    typical_mistakes: List[str]  # Common errors at club level
    simple_explanation: str  # One-liner for beginners
    teaching_moments: Dict[str, str]  # move -> what to teach
    variations: Dict[str, Dict] = field(default_factory=dict)  # Deep variation trees


# ==================== WHITE OPENINGS ====================

ITALIAN_GAME = OpeningPlan(
    name="Italian Game",
    eco_codes=["C50", "C51", "C52", "C53", "C54"],
    identifying_moves=["e4", "e5", "Nf3", "Nc6", "Bc4"],
    main_ideas=[
        "Put your bishop on c4 pointing at f7 - their weak spot",
        "Castle quickly to keep your king safe",
        "Control the center, then attack the kingside"
    ],
    key_squares=["c4", "f7", "d4", "f4"],
    typical_mistakes=[
        "Attacking f7 too early before castling",
        "Forgetting to develop the other pieces",
        "Moving the same piece twice in opening"
    ],
    simple_explanation="Your bishop aims at f7 (only the king guards it). Develop, castle, then attack.",
    teaching_moments={
        "e5": "Fighting for the center! This creates an open game with lots of tactics. Ready for some action?",
        "Nf6": "Good development! The knight attacks e4. Can you see what square it's aiming for?",
        "Nc6": "Natural move - the knight develops and defends e5. How many pieces protect that pawn now?",
        "Bc5": "Mirror image! Your bishop also eyes f2 - white's weak pawn. Now it's a real battle!",
        "Be7": "Solid choice - preparing to castle. Sometimes safe is better than aggressive.",
        "Bc4": "This is the Italian Game! The bishop stares at f7 - the weakest point. Only the king guards it.",
        "O-O": "Castle! King safety first, attack second. This is how grandmasters play.",
        "d3": "Supporting the center and opening a path for the bishop. Good technique!",
        "c3": "Preparing d4 - the big center push. Can you see the plan coming together?",
        "d6": "Solid - defending e5 and preparing development. What should develop next?",
    },
    variations={
        "giuoco_pianissimo": {
            "name": "Italian Game — Giuoco Pianissimo",
            "trigger_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],
            "full_line": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d3", "d6", "O-O", "O-O", "Re1", "a6"],
            "move_teaching": {
                "c3": {"teach": "Prepare the central break with d4. This quiet pawn move is the real backbone of the Italian — you improve your center before throwing punches.", "idea": "Support d4 before opening the game"},
                "Nf6": {"teach": "Black develops and eyes e4. Good Italian players always notice that this knight is both a defender and an attacker.", "idea": "Respect Black's pressure on e4"},
                "d3": {"teach": "This is the Pianissimo spirit — calm development first, then the center later. You keep flexibility while stopping cheap counterplay.", "idea": "Stay solid before expanding"},
                "d6": {"teach": "Black mirrors the plan and keeps e5 protected. Nobody is rushing — both sides are building a platform for the middlegame.", "idea": "Complete the shell before the break"},
                "O-O": {"teach": "Castle before you open the center. In the Italian, king safety and rook activation come before the d4 break.", "idea": "King safety before central action"},
                "Re1": {"teach": "Excellent placement. The rook supports e4, reinforces the center, and prepares d4 under better conditions.", "idea": "Coordinate the center before breaking"},
                "a6": {"teach": "Black takes away b5 and asks your bishop to make a long-term choice. This is a patient, strategic Italian battle now.", "idea": "Slow queenside improvement"}
            },
            "key_plans": [
                "White: build with c3, d3, O-O, then strike with d4 when you're fully ready",
                "White: reroute a knight via d2-f1-g3 to aim at the kingside",
                "Black: keep White's d4 break under control and improve pieces before counterplay"
            ],
            "plans_for_white": [
                "Prepare d4 carefully, not impulsively",
                "Use Re1 and Nbd2-f1-g3 to build kingside pressure",
                "Keep the bishop active while the center stays closed"
            ],
            "plans_for_black": [
                "Control White's d4 break before opening the center",
                "Use ...a6 and ...Ba7 or ...Be6 to improve the dark-squared bishop",
                "Counter in the center only after development is complete"
            ],
            "traps": [
                {"move": "Bxf7+", "warning": "Greek Gift temptation: Bxf7+ usually backfires in quiet Italian positions if White is not fully developed. Finish your setup before sacrificing."}
            ]
        },
        "two_knights_defense": {
            "name": "Italian Game — Two Knights / Fried Liver Ideas",
            "trigger_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],
            "full_line": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5", "Nxf7", "Kxf7", "Qf3+"],
            "move_teaching": {
                "Ng5": {"teach": "Now the position turns sharp. White jumps on f7 ideas immediately — this is where the Fried Liver style starts to appear.", "idea": "Attack f7 before Black finishes development"},
                "d5": {"teach": "Black's best practical answer — hit the bishop line and fight back in the center immediately. In open games, counterplay matters more than passive defense.", "idea": "Meet the attack with central counterplay"},
                "exd5": {"teach": "White opens lines and keeps the attack alive. Once you go for Ng5, you have to calculate, not just hope.", "idea": "Open lines before Black consolidates"},
                "Nxd5": {"teach": "Black develops while grabbing central control. The defender is trying to survive the initiative without falling apart.", "idea": "Develop while solving tactical problems"},
                "Nxf7": {"teach": "This is the famous Fried Liver leap. White wins material and drags the king out — but only if the follow-up is accurate.", "idea": "Rip open the king before Black untangles"},
                "Kxf7": {"teach": "Black accepts the challenge. Now the position is all about calculation and king safety — one careless move changes everything.", "idea": "Survive the storm, then consolidate"},
                "Qf3+": {"teach": "Strong follow-up: White keeps the king exposed and brings another piece into the attack. Initiative is worth gold here.", "idea": "Keep adding attackers with tempo"}
            },
            "key_plans": [
                "White: if you attack f7, calculate the full sequence — don't stop after the first flashy move",
                "Black: meet the attack with ...d5 and active defense, not fear",
                "Both sides: development and tempo are more important than material counting"
            ],
            "plans_for_white": [
                "Keep the black king exposed with checks and active pieces",
                "Bring the queen and bishop together before grabbing more material",
                "If the attack fades, regroup and castle rather than forcing more sacrifices"
            ],
            "plans_for_black": [
                "Use ...d5 immediately to fight the attack in the center",
                "Return material if needed to finish development and cover the king",
                "Swap attacking pieces whenever possible once the king is safe enough"
            ],
            "traps": [
                {"move": "Ng5", "warning": "Fried Liver alert! If Ng5 is on the board, White wants f7. Black should know ...d5; White should know the follow-up before jumping in."}
            ]
        }
    }
)

RUY_LOPEZ = OpeningPlan(
    name="Ruy Lopez (Spanish Game)",
    eco_codes=["C60", "C61", "C62", "C63", "C64", "C65", "C66", "C67", "C68", "C69", "C70", "C71", "C72", "C73", "C74", "C75", "C76", "C77", "C78", "C79", "C80", "C81", "C82", "C83", "C84", "C85", "C86", "C87", "C88", "C89", "C90", "C91", "C92", "C93", "C94", "C95", "C96", "C97", "C98", "C99"],
    identifying_moves=["e4", "e5", "Nf3", "Nc6", "Bb5"],
    main_ideas=[
        "Put pressure on their knight that defends e5",
        "Build a strong center with d4 later",
        "Slow, strategic game - be patient"
    ],
    key_squares=["b5", "c6", "d4", "e5"],
    typical_mistakes=[
        "Taking the knight too early (Bxc6) without a plan",
        "Rushing the attack before completing development",
        "Forgetting that your bishop can retreat to a4 or c2"
    ],
    simple_explanation="Your bishop puts pressure on the knight guarding e5. It's a slow, strong opening.",
    teaching_moments={
        "Bb5": "This pins their knight to the king's defense of e5. They have to worry about it.",
        "O-O": "Castle first, attack later. The Ruy Lopez is a patient opening.",
        "Re1": "Your rook now supports the e4 pawn. Solid.",
        "c3": "Preparing d4. This is the main plan in the Ruy Lopez.",
    }
)

LONDON_SYSTEM = OpeningPlan(
    name="London System",
    eco_codes=["D00", "A46", "A48"],
    identifying_moves=["d4", "Nf3", "Bf4"],
    main_ideas=[
        "Develop bishop to f4 BEFORE playing e3",
        "Build a solid pyramid: pawns on d4, e3, c3",
        "Simple and safe - hard for opponent to attack"
    ],
    key_squares=["f4", "d4", "e3", "c3"],
    typical_mistakes=[
        "Playing e3 before Bf4 (bishop gets trapped)",
        "Being too passive - you still need to make a plan",
        "Forgetting to castle"
    ],
    simple_explanation="Put bishop on f4 first, then build a solid wall. Safe and easy to play.",
    teaching_moments={
        "Bf4": "Get this bishop out BEFORE e3, otherwise it's stuck forever.",
        "e3": "Now your pawn structure is solid. The bishop is already out.",
        "Bd3": "Your bishops are developed. Looking good!",
        "O-O": "Perfect. Safe king, developed pieces. Now look for a plan.",
        "c3": "Supporting d4 and giving your queen a square on c2.",
    },
    variations={
        "main_london_c5": {
            "name": "London System — ...c5 Challenge",
            "trigger_moves": ["d4", "d5", "Nf3", "Nf6", "Bf4", "c5"],
            "full_line": ["d4", "d5", "Nf3", "Nf6", "Bf4", "c5", "e3", "Nc6", "c3", "Qb6", "Nbd2"],
            "move_teaching": {
                "e3": {"teach": "Now e3 makes sense because the bishop is already outside the pawn chain. The London is about clean move order, not random setup moves.", "idea": "Lock the center only after the bishop escapes"},
                "Nc6": {"teach": "Black adds more pressure to d4 and keeps ...Qb6 ideas alive. The London player must stay solid without drifting passive.", "idea": "Increase pressure on the center"},
                "c3": {"teach": "This is the classic London shell: d4, e3, c3. You hold the center and prepare to meet queenside pressure calmly.", "idea": "Complete the London pyramid"},
                "Qb6": {"teach": "Black immediately tests b2 and d4. London players must remember that a solid setup still needs tactical attention.", "idea": "Pressure weak dark squares and b2"},
                "Nbd2": {"teach": "Good practical move. You cover b3, reinforce e4 ideas, and keep the whole structure coordinated.", "idea": "Support the center without loosening the shape"}
            },
            "key_plans": [
                "White: finish the London shell first, then look for Ne5 or Bd3 and a kingside plan",
                "Black: challenge the center with ...c5 and ...Qb6 instead of letting White coast",
                "Both sides: the London is strategic, but tactical details around b2 and e4 still matter"
            ],
            "plans_for_white": [
                "Build c3-e3 before launching piece activity",
                "Use Ne5 or Bd3 to shift from setup mode into pressure",
                "Keep b2 and the queenside dark squares under control"
            ],
            "plans_for_black": [
                "Use ...c5 and ...Qb6 to question the London structure early",
                "Avoid letting White complete the setup without pressure",
                "Trade one of White's active bishops if it helps reduce kingside pressure"
            ],
            "traps": [
                {"move": "Qb3", "warning": "Don't auto-pilot with Qb3 if Black is already active — always check whether b2, d4, or your bishop becomes loose first."}
            ]
        }
    }
)

QUEENS_GAMBIT = OpeningPlan(
    name="Queen's Gambit",
    eco_codes=["D06", "D07", "D08", "D09", "D10", "D11", "D12", "D13", "D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D27", "D28", "D29", "D30", "D31", "D32", "D33", "D34", "D35", "D36", "D37", "D38", "D39", "D40", "D41", "D42", "D43", "D44", "D45", "D46", "D47", "D48", "D49"],
    identifying_moves=["d4", "d5", "c4"],
    main_ideas=[
        "Offer the c4 pawn to open the center — this is a gambit, not a sacrifice",
        "If they take on c4, you reclaim the center with e4. Two central pawns = domination",
        "Develop knights to c3 and f3, bishop to g5 or f4, then castle and attack"
    ],
    key_squares=["c4", "d4", "d5", "e4"],
    typical_mistakes=[
        "Trying to hold the gambit pawn with b5 (wastes time and weakens king)",
        "Forgetting to develop pieces while fighting for the center",
        "Moving the queen out too early — let the minor pieces do the work first"
    ],
    simple_explanation="Offer a pawn to control the center. If they take, you play e4 and dominate.",
    teaching_moments={
        "d4": "Great start! d4 fights for the center. Now we'll build the Queen's Gambit.",
        "c4": "This is the Queen's Gambit! You're offering a pawn to open the center. If Black takes, you'll play e4 and get two pawns in the middle.",
        "e4": "Two pawns in the center — this is the ideal setup! You're controlling key squares and opening lines for your pieces.",
        "Nc3": "Developing the knight AND supporting d5 and e4. This piece does double duty.",
        "Nf3": "Knights before bishops — classic development. The knight also defends d4 and eyes e5.",
        "Bg5": "Pinning the knight to the queen! This is a key idea in the Queen's Gambit. It puts real pressure on Black's defense of d5.",
        "Bf4": "The bishop is active outside the pawn chain. Good development — don't lock it behind your own pawns!",
        "e3": "Solid — supporting d4 and opening the diagonal for your bishop. Sometimes safe moves are the strongest.",
        "Bd3": "The bishop develops to a great diagonal. It can support a future e4 push or eye the kingside.",
        "O-O": "Castle! King safety first, attack second. This is how strong players approach the opening.",
        "dxc4": "They took the gambit pawn! Don't panic. Play e3 or e4 and the pawn falls. You'll get a beautiful center.",
        "e6": "The Queen's Gambit Declined. Black says 'No thanks' and keeps the center solid. Respect — this is a tough defense to crack.",
        "c6": "This is the Slav Defense — very solid. Black defends d5 with a pawn instead of blocking the light-squared bishop.",
    },
    variations={
        # ======= QUEEN'S GAMBIT DECLINED (1.d4 d5 2.c4 e6) =======
        "qgd_main": {
            "name": "Queen's Gambit Declined — Classical",
            "trigger_moves": ["d4", "d5", "c4", "e6"],
            "full_line": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O", "Nf3", "Nbd7", "Bd3", "c6"],
            "move_teaching": {
                "Nc3": {"teach": "Develop the knight to c3 — it supports e4 and puts pressure on d5. This is the most natural and strongest move in the QGD.", "idea": "Control the center and pressure d5"},
                "Nf6": {"teach": "Black develops the knight and defends d5. Now you need to increase the pressure. How? By pinning this defender!", "idea": "Target the d5 defender"},
                "Bg5": {"teach": "Pin the knight! This is the CLASSICAL approach. The knight on f6 defends d5 — by pinning it to the queen, you threaten to win the d5 pawn. This is one of the most important ideas in the QGD.", "idea": "Pressure d5 through the pin"},
                "Be7": {"teach": "Black breaks the pin. Solid defense — the bishop covers e7 and prepares castling. Your plan now: complete development with e3 and Nf3.", "idea": "King safety first"},
                "e3": {"teach": "Support d4 and unlock the light-squared bishop. The bishop will go to d3 — a powerful post aiming at Black's kingside. This quiet move is actually very strong.", "idea": "Prepare Bd3 and kingside pressure"},
                "O-O": {"teach": "Black castles. Good defensive technique. Now the real battle begins. Your plan: Bd3, Nf3, then push for e4 or play a queenside minority attack.", "idea": "Middlegame planning begins"},
                "Nf3": {"teach": "Complete development — knights before the queen. Your army is nearly ready. After Bd3, you'll have a powerful setup.", "idea": "Finish development"},
                "Nbd7": {"teach": "Black reroutes the knight, possibly to f8-g6 for kingside defense. Deep positional maneuvering.", "idea": "Piece improvement"},
                "Bd3": {"teach": "The bishop lands on the PERFECT diagonal! It eyes h7 and supports an eventual e4 push. This is the dream setup in the Queen's Gambit Declined.", "idea": "Attacking setup complete"},
                "c6": {"teach": "Black reinforces d5 with a pawn chain. Your two big plans from here: 1) Central break with e4 to blast open the position, or 2) Minority attack with a4-b5 to create weak pawns on Black's queenside.", "idea": "Choose your plan: e4 or minority attack"},
            },
            "key_plans": [
                "Minority attack: push a4-b5 to create weak pawns on Black's queenside",
                "Central break: push e4 when the time is right to open lines for your pieces",
                "Kingside attack: Bd3 + potential Bxh7 sacrifice if Black is careless"
            ],
            "plans_for_white": [
                "Complete development, then choose between e4 or the minority attack",
                "Use the Bg5 pin to increase pressure on d5",
                "Place the bishop on d3 before shifting toward a kingside attack"
            ],
            "plans_for_black": [
                "Finish development and look for ...c5 or ...e5 to free the position",
                "Break White's pressure on d5 before launching counterplay",
                "Use ...Nbd7 and ...c6 to stay solid, then challenge the center"
            ],
            "traps": [
                {"move": "Nxd5", "warning": "Elephant Trap alert! After cxd5 Nxd5 Bxe7?? Bb4! — the pin wins White's knight. Always check for ...Bb4!"},
            ]
        },
        # ======= QUEEN'S GAMBIT ACCEPTED (1.d4 d5 2.c4 dxc4) =======
        "qga_main": {
            "name": "Queen's Gambit Accepted",
            "trigger_moves": ["d4", "d5", "c4", "dxc4"],
            "full_line": ["d4", "d5", "c4", "dxc4", "e4", "e5", "Nf3", "exd4", "Bxc4", "Nc6", "O-O", "Nf6"],
            "move_teaching": {
                "e4": {"teach": "Don't chase the c4 pawn! Instead, play e4 and grab TWO central pawns. This is why the gambit works — you sacrifice a wing pawn for massive center control.", "idea": "Two pawns in the center beats one on the side"},
                "e3": {"teach": "This also works to recover the pawn, but e4 is much more ambitious. You're playing for a big center!", "idea": "Recover the gambit pawn"},
                "Nf3": {"teach": "Develop and attack! The knight pressures e5 and d4. You're building up fast while Black is still figuring out what to do with that extra pawn.", "idea": "Develop with initiative"},
                "Bxc4": {"teach": "Recover your pawn! The bishop lands on a beautiful diagonal targeting f7 — the weakest point in Black's position. This is a dream development.", "idea": "Bishop targets f7"},
                "O-O": {"teach": "Castle immediately! You have a massive development lead — pieces are out, king is safe, rooks are connected. Black is still behind.", "idea": "Press the development advantage"},
                "Nc3": {"teach": "Another piece in the game! You're way ahead in development. The plan: open the center and punish Black for grabbing that pawn.", "idea": "Development advantage"},
                "Re1": {"teach": "Rook to the open file! This puts direct pressure on e5 or the e-file. Very natural and strong.", "idea": "Activate the rook"},
            },
            "key_plans": [
                "Rapid development: get all your pieces out before Black can catch up",
                "Control the center with d4+e4 — the whole point of the gambit",
                "Target f7 with the bishop on c4 — it's Black's weakest square"
            ],
            "plans_for_white": [
                "Use the development lead before Black untangles",
                "Control the center first, then punish the extra pawn",
                "Aim active pieces toward f7 and the open files"
            ],
            "plans_for_black": [
                "Give the pawn back if needed to finish development safely",
                "Challenge White's center with ...e5 or ...c5 at the right moment",
                "Avoid greed that leaves the king and pieces undeveloped"
            ],
            "traps": [
                {"move": "b5", "warning": "If Black plays ...b5 trying to hold the pawn, play a4! This undermines the defense and opens devastating lines."},
            ]
        },
        # ======= SLAV DEFENSE (1.d4 d5 2.c4 c6) =======
        "slav_main": {
            "name": "Slav Defense",
            "trigger_moves": ["d4", "d5", "c4", "c6"],
            "full_line": ["d4", "d5", "c4", "c6", "Nf3", "Nf6", "Nc3", "dxc4", "a4", "Bf5", "e3", "e6", "Bxc4", "Bb4"],
            "move_teaching": {
                "Nf3": {"teach": "Develop naturally. The Slav is one of the most solid defenses in chess — don't rush. Build up piece by piece. Knights before bishops!", "idea": "Patient, solid development"},
                "Nc3": {"teach": "Add more pressure to d5 and prepare e4. You're slowly building a strong center. This is how grandmasters play the Slav.", "idea": "Increase central pressure"},
                "a4": {"teach": "Critical move! Stop Black from playing ...b5 to hold the extra pawn. Without a4, Black keeps the c4 pawn forever. This is a MUST-KNOW idea in the Slav.", "idea": "Prevent ...b5 — essential"},
                "e3": {"teach": "Support d4 and prepare to recapture on c4 with the bishop. Solid and logical.", "idea": "Prepare Bxc4"},
                "Bxc4": {"teach": "Recover your pawn with a well-placed bishop. You have good development and central presence. The position is roughly equal but rich with ideas.", "idea": "Balanced position with chances"},
                "dxc4": {"teach": "They took! This is the main line Slav. Black's plan: develop the light-squared bishop to f5 BEFORE playing ...e6. In the QGD, this bishop gets trapped — the Slav avoids that problem.", "idea": "The Slav's secret: free the light bishop"},
                "Bf5": {"teach": "There it is! The bishop escapes to f5 BEFORE ...e6 blocks it in. This is THE reason players choose the Slav over the QGD. Respect this idea.", "idea": "The Slav's signature move"},
                "e6": {"teach": "NOW Black plays e6 — the bishop is already free! Compare this to the QGD where the bishop is permanently stuck behind the pawns.", "idea": "Compare to QGD: bishop is free here"},
            },
            "key_plans": [
                "Play a4 early to prevent ...b5 — this is essential",
                "Recapture on c4 with the bishop for active development",
                "Push e4 when ready to open the center and create chances"
            ],
            "plans_for_white": [
                "Stop ...b5 first, then recover the c4 pawn with development",
                "Use a4 and Bxc4 to make the queenside healthy before pushing e4",
                "Keep the center compact while Black develops the light bishop"
            ],
            "plans_for_black": [
                "Develop the light-squared bishop before ...e6 whenever possible",
                "Only hold the c4 pawn if it does not cost too much time",
                "Counter White's center once your development is complete"
            ],
            "traps": [
                {"move": "b5", "warning": "If you forget a4 and Black plays ...b5, they keep the extra pawn for free. Always play a4 in the Slav!"},
            ]
        },
    }
)

SCOTCH_GAME = OpeningPlan(
    name="Scotch Game",
    eco_codes=["C44", "C45"],
    identifying_moves=["e4", "e5", "Nf3", "Nc6", "d4"],
    main_ideas=[
        "Open the center immediately",
        "Get active piece play quickly",
        "Don't worry about giving up the d4 pawn"
    ],
    key_squares=["d4", "e5", "c3"],
    typical_mistakes=[
        "Taking back with the queen too early (Qxd4 gets attacked)",
        "Not developing pieces fast enough",
        "Forgetting to castle"
    ],
    simple_explanation="Open the center right away. Fast, attacking chess. Don't be passive!",
    teaching_moments={
        "d4": "Opening the center immediately. This is the Scotch Game - aggressive!",
        "Nxd4": "Good recapture with the knight. Keeps developing.",
        "Bc4": "Now your bishop is active, pointing at f7.",
    }
)

VIENNA_GAME = OpeningPlan(
    name="Vienna Game",
    eco_codes=["C25", "C26", "C27", "C28", "C29"],
    identifying_moves=["e4", "e5", "Nc3"],
    main_ideas=[
        "Prepare f4 to attack the center",
        "Can transpose into sharp or quiet positions",
        "Flexible - keep your options open"
    ],
    key_squares=["c3", "f4", "d5"],
    typical_mistakes=[
        "Playing f4 too early without preparation",
        "Not knowing what plan to follow",
        "Being passive"
    ],
    simple_explanation="Knight to c3 prepares f4. Flexible opening - you choose if it's sharp or calm.",
    teaching_moments={
        "Nc3": "This is the Vienna Game. You're preparing f4 or Bc4 - flexible!",
        "f4": "Now it's sharp! You're attacking their e5 pawn.",
        "Bc4": "Good development, similar ideas to the Italian.",
    }
)


# ==================== BLACK RESPONSES ====================

SICILIAN_DEFENSE = OpeningPlan(
    name="Sicilian Defense",
    eco_codes=["B20", "B21", "B22", "B23", "B24", "B25", "B26", "B27", "B28", "B29", "B30", "B31", "B32", "B33", "B34", "B35", "B36", "B37", "B38", "B39", "B40", "B41", "B42", "B43", "B44", "B45", "B46", "B47", "B48", "B49", "B50", "B51", "B52", "B53", "B54", "B55", "B56", "B57", "B58", "B59", "B60", "B61", "B62", "B63", "B64", "B65", "B66", "B67", "B68", "B69", "B70", "B71", "B72", "B73", "B74", "B75", "B76", "B77", "B78", "B79", "B80", "B81", "B82", "B83", "B84", "B85", "B86", "B87", "B88", "B89", "B90", "B91", "B92", "B93", "B94", "B95", "B96", "B97", "B98", "B99"],
    identifying_moves=["e4", "c5"],
    main_ideas=[
        "Fight for the center from the side with c5",
        "After d4 exchange, you get the open c-file for your rook",
        "Counter-attack on the queenside while white attacks kingside"
    ],
    key_squares=["c5", "d4", "c-file"],
    typical_mistakes=[
        "Playing too passively - the Sicilian needs active play",
        "Forgetting to develop the queenside pieces",
        "Castling kingside when white has a strong attack there"
    ],
    simple_explanation="c5 fights for the center sideways. When pawns trade on d4, your rook uses the c-file.",
    teaching_moments={
        "c5": "The Sicilian Defense! Notice how c5 fights for the d4 square from the side? This is chess's most combative response to e4.",
        "d6": "Solid setup - this is often the start of the Dragon or Najdorf. Can you guess why we delay developing the knight?",
        "d5": "Direct challenge! We're not waiting around. This grabs space immediately. What do you think happens if white takes?",
        "Nf6": "See how this knight attacks e4? In the Sicilian, we constantly pressure white's center. What would happen if they ignore it?",
        "Nc6": "The knight develops toward d4 - our dream square. Every piece should aim for the center. Where should your knight go?",
        "e6": "The Scheveningen - very solid. We're preparing to play d5 when the time is right. Patience is key here.",
        "a6": "The Najdorf! A small move with big ideas - it prevents Bb5 pins and prepares b5-b4 expansion. One of the richest openings in chess!",
        "g6": "The Dragon setup! The bishop on g7 will be a monster on that diagonal. What diagonal is it aiming at?",
    },
    variations={
        "open_sicilian_classical": {
            "name": "Sicilian Defense — Open Sicilian",
            "trigger_moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3"],
            "full_line": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Be3", "e6", "f3", "Be7", "Qd2", "O-O"],
            "move_teaching": {
                "d4": {"teach": "White opens the center immediately. In the Sicilian, White wants activity before Black's queenside play gets rolling.", "idea": "Open the game while Black is still developing"},
                "cxd4": {"teach": "This exchange is the Sicilian's heartbeat. Black gives White a central pawn but wins dynamic play on the c-file.", "idea": "Trade central symmetry for active files"},
                "Nxd4": {"teach": "White recaptures with a piece to stay active. Development matters more than grabbing space with pawns alone.", "idea": "Recapture while improving a piece"},
                "Nf6": {"teach": "Black immediately questions e4. Sicilian players attack the center move by move instead of admiring it.", "idea": "Pressure e4 before White settles"},
                "Nc3": {"teach": "White reinforces e4 and controls d5. This is the standard Open Sicilian setup — flexible, active, and ready for sharp play.", "idea": "Support e4 and claim d5"},
                "a6": {"teach": "This is the Najdorf-style hook: stop Bb5+, prepare ...b5, and ask White what kind of fight they want.", "idea": "Prepare queenside expansion"},
                "Be3": {"teach": "White develops with purpose: support queenside castling ideas and keep pressure on key dark squares.", "idea": "Coordinate for long-term kingside pressure"},
                "e6": {"teach": "Black solidifies d5 control and prepares ...Be7 or ...Qc7. The Sicilian often looks quiet just before it explodes.", "idea": "Keep d5 under control before counterplay"},
                "f3": {"teach": "White supports e4 and makes room for Qd2 with long castling ideas. This is a serious attacking setup.", "idea": "Support the center and prepare the kingside race"},
                "Be7": {"teach": "Black develops calmly and gets ready to castle. Good Sicilian defense means not panicking when White points pieces at your king.", "idea": "Finish development before the race begins"},
                "Qd2": {"teach": "Now White connects the pieces and hints at long castling. The board is telling you that opposite-side attacks may be coming.", "idea": "Connect the attack before castling"},
                "O-O": {"teach": "Black castles short and accepts the race. From here, calculation and timing decide everything.", "idea": "King safety first, then counterattack"}
            },
            "key_plans": [
                "White: use Be3, Qd2, and long castling to race against Black's queenside play",
                "Black: hit the center and queenside with ...a6, ...b5, and the c-file",
                "Both sides: whoever strikes first usually dictates the middlegame"
            ],
            "plans_for_white": [
                "Reinforce e4, then build a kingside attack with Be3-Qd2-f3",
                "Use central control to slow Black's queenside expansion",
                "Decide early whether you're castling long or keeping the king flexible"
            ],
            "plans_for_black": [
                "Pressure d4 and e4 before White starts the attack",
                "Use ...a6 and the c-file to create queenside counterplay",
                "Keep the d5 break in mind as the long-term equalizer"
            ],
            "traps": [
                {"move": "Nxe4", "warning": "Don't grab on e4 too casually in the Sicilian — tactical shots like Bb5+ or Qa4+ can punish loose coordination."}
            ]
        }
    }
)

FRENCH_DEFENSE = OpeningPlan(
    name="French Defense",
    eco_codes=["C00", "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17", "C18", "C19"],
    identifying_moves=["e4", "e6"],
    main_ideas=[
        "Solid structure - let white overextend",
        "Your light bishop is blocked but your position is solid",
        "Attack white's center with c5 and f6 later"
    ],
    key_squares=["e6", "d5", "c5"],
    typical_mistakes=[
        "Not playing c5 to challenge the center",
        "Leaving the light bishop stuck forever",
        "Being too passive"
    ],
    simple_explanation="e6 is solid. You'll play d5 next and challenge white's center with c5 later.",
    teaching_moments={
        "e6": "The French Defense - very solid! The plan is to play d5 next and create a strong center. Ready?",
        "d5": "Perfect timing! Now we're fighting for the center. What happens to the pawns if white captures?",
        "c5": "This is THE key move in the French! We're attacking d4 - white's center is under pressure. See the idea?",
        "Nc6": "Knight to c6 adds more pressure to d4. Count the attackers - how many pieces target that square now?",
        "Bb4": "Pinning the knight! This is the Winawer variation. If the knight moves, what happens to d4?",
    },
    variations={
        "advance_french": {
            "name": "French Defense — Advance Variation",
            "trigger_moves": ["e4", "e6", "d4", "d5", "e5"],
            "full_line": ["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6"],
            "move_teaching": {
                "e5": {"teach": "White grabs space and locks the center. That means both sides must think in plans, not just immediate tactics.", "idea": "Close the center and gain space"},
                "c5": {"teach": "Black's main French reaction: attack the base of the pawn chain. If d4 falls, White's whole center wobbles.", "idea": "Attack the pawn chain at its base"},
                "c3": {"teach": "White reinforces d4 and keeps the space advantage. In the Advance French, this move is almost part of the identity of the structure.", "idea": "Hold the center before expanding"},
                "Nc6": {"teach": "Black piles more pressure onto d4. French players win by making White defend the center again and again.", "idea": "Increase pressure on d4"},
                "Nf3": {"teach": "White develops without weakening the center. The challenge is to attack while the pawn chain still holds.", "idea": "Develop without loosening d4"},
                "Qb6": {"teach": "Strong French move. Black hits d4 and b2 at once, forcing White to solve real problems instead of free development.", "idea": "Create double pressure on d4 and b2"}
            },
            "key_plans": [
                "White: keep the space advantage while preparing kingside activity",
                "Black: attack d4 relentlessly and break the center with ...cxd4 or ...f6 later",
                "Both sides: the locked center means pawn breaks decide the middlegame"
            ],
            "plans_for_white": [
                "Hold d4 securely before thinking about kingside play",
                "Use Bd3, O-O, and Re1 to support a future attack",
                "Watch b2 whenever Black's queen reaches b6"
            ],
            "plans_for_black": [
                "Attack d4 until White spends time defending it",
                "Look for ...Qb6 and ...Bd7 to coordinate pressure",
                "Prepare ...f6 as the long-term break against White's center"
            ],
            "traps": [
                {"move": "Qb6", "warning": "French pressure alert: once ...Qb6 appears, White must remember that b2 and d4 are both under fire."}
            ]
        }
    }
)

CARO_KANN = OpeningPlan(
    name="Caro-Kann Defense",
    eco_codes=["B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18", "B19"],
    identifying_moves=["e4", "c6"],
    main_ideas=[
        "Prepare d5 with c6 supporting it",
        "Solid structure like the French, but bishop isn't trapped",
        "Exchange pawns in center, then develop freely"
    ],
    key_squares=["c6", "d5", "c8"],
    typical_mistakes=[
        "Not playing d5 after c6",
        "Being too passive in the middlegame",
        "Forgetting to develop the kingside"
    ],
    simple_explanation="c6 prepares d5 with support. Unlike the French, your bishop stays free.",
    teaching_moments={
        "c6": "The Caro-Kann! Preparing d5 with pawn support.",
        "d5": "Good! Now you're fighting for the center with your pawn supported.",
        "Bf5": "See? Your bishop is free, unlike in the French Defense.",
        "e6": "Solid. Supporting d5 and preparing development.",
    },
    variations={
        "classical_caro_kann": {
            "name": "Caro-Kann Defense — Classical Development",
            "trigger_moves": ["e4", "c6", "d4", "d5", "Nc3"],
            "full_line": ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Nf3", "e6", "Bd3", "Bxd3"],
            "move_teaching": {
                "Nc3": {"teach": "White supports e4 and keeps central control. Now Black has to decide whether to keep tension or simplify with purpose.", "idea": "Reinforce the center before Black frees up"},
                "dxe4": {"teach": "Black clarifies the center and aims for clean development. The Caro-Kann often trades central tension for reliable structure.", "idea": "Simplify the center, keep the structure healthy"},
                "Nxe4": {"teach": "White recaptures with a piece and stays active. Central recaptures with a knight are a recurring classical theme.", "idea": "Recapture while developing"},
                "Bf5": {"teach": "Here is the Caro-Kann's signature: the bishop develops before ...e6 closes it in. This is why many players trust the opening.", "idea": "Develop the bishop before locking the center"},
                "Nf3": {"teach": "White keeps improving pieces and pressures e5 and d4 squares. No rush — just healthy development.", "idea": "Finish development before choosing a plan"},
                "e6": {"teach": "Now Black closes the chain safely because the bishop is already outside. This is the French structure without the bad bishop problem.", "idea": "Lock in the structure after freeing the bishop"},
                "Bd3": {"teach": "White immediately questions the active bishop. In Caro-Kann structures, that bishop is one of Black's proudest pieces.", "idea": "Challenge Black's best minor piece"},
                "Bxd3": {"teach": "Black usually gives up the bishop rather than retreat into passivity. The Caro-Kann is solid, but it still needs active decisions.", "idea": "Trade activity for a stable structure"}
            },
            "key_plans": [
                "White: complete development and use the space edge without overpushing",
                "Black: get the bishop out before ...e6, then rely on the healthy structure",
                "Both sides: Caro-Kann battles are often decided by who activates pieces faster after the early trades"
            ],
            "plans_for_white": [
                "Challenge Black's light-squared bishop early",
                "Use Bd3, Nf3, and O-O to keep the initiative without overextending",
                "Avoid slow development just because the position looks quiet"
            ],
            "plans_for_black": [
                "Free the bishop first, then lock the structure with ...e6",
                "Trade central tension only when it helps your development",
                "Stay active after the early exchanges — don't drift into passivity"
            ],
            "traps": [
                {"move": "Bxd3", "warning": "Remember why the Caro-Kann works: get the bishop out before closing the chain. If Black forgets that sequence, the whole opening loses its point."}
            ]
        }
    }
)

KINGS_INDIAN = OpeningPlan(
    name="King's Indian Defense",
    eco_codes=["E60", "E61", "E62", "E63", "E64", "E65", "E66", "E67", "E68", "E69", "E70", "E71", "E72", "E73", "E74", "E75", "E76", "E77", "E78", "E79", "E80", "E81", "E82", "E83", "E84", "E85", "E86", "E87", "E88", "E89", "E90", "E91", "E92", "E93", "E94", "E95", "E96", "E97", "E98", "E99"],
    identifying_moves=["d4", "Nf6", "c4", "g6", "Nc3", "Bg7"],
    main_ideas=[
        "Let white build a big center, then attack it",
        "Fianchetto your bishop to g7 - it's a monster on the diagonal",
        "Play e5 and attack on the kingside"
    ],
    key_squares=["g7", "e5", "f4", "h5"],
    typical_mistakes=[
        "Playing too passively and letting white crush you",
        "Not playing e5 to challenge the center",
        "Forgetting the kingside attack with f5"
    ],
    simple_explanation="Let white build up, then explode on the kingside with e5 and f5. Your g7 bishop is powerful.",
    teaching_moments={
        "Nf6": "Good start. Flexible - can go to many openings.",
        "g6": "Fianchetto! Your bishop will be strong on g7.",
        "Bg7": "Beautiful. This bishop controls the whole diagonal.",
        "O-O": "King is safe. Now prepare e5 and the kingside attack!",
        "e5": "The key break! Now you have counterplay.",
    },
    variations={
        "main_kings_indian": {
            "name": "King's Indian Defense — Main Setup",
            "trigger_moves": ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7"],
            "full_line": ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5"],
            "move_teaching": {
                "e4": {"teach": "White grabs space and claims the center. King's Indian players actually invite this — they want a target.", "idea": "Build a center Black can later attack"},
                "d6": {"teach": "Black supports ...e5 and keeps the dark-squared bishop flexible. The King's Indian is patient before it becomes violent.", "idea": "Prepare the central break safely"},
                "Nf3": {"teach": "White develops naturally and prepares to castle. Big centers need piece support or they collapse under pressure.", "idea": "Support the center before expanding further"},
                "O-O": {"teach": "Black castles and says: now the middlegame can begin. Counterplay comes only after king safety is solved.", "idea": "Finish development before counterplay"},
                "Be2": {"teach": "White keeps things flexible and avoids tactical pin ideas. This is a main-line King's Indian decision.", "idea": "Stay flexible before Black breaks"},
                "e5": {"teach": "Now Black strikes the center. This is the King's Indian promise — let White build, then hit back with energy.", "idea": "Challenge the center and start counterplay"}
            },
            "key_plans": [
                "White: use the space edge to stay active before Black's kingside attack starts",
                "Black: prepare ...e5 and then kingside play with ...f5",
                "Both sides: this opening is about timing — whoever lands the first successful pawn break gets the initiative"
            ],
            "plans_for_white": [
                "Use the center and queenside space before Black's kingside attack grows",
                "Complete development quickly so the center is actually stable",
                "Watch for ...e5 and ...f5 before deciding where your pieces belong"
            ],
            "plans_for_black": [
                "Prepare ...e5, then look for kingside counterplay with ...f5",
                "Use the g7 bishop and knight pressure to undermine White's center",
                "Don't start the attack before king safety and development are finished"
            ],
            "traps": [
                {"move": "f5", "warning": "King's Indian warning: ...f5 is powerful only after Black is fully coordinated. Don't launch the pawn storm before the pieces are ready."}
            ]
        }
    }
)

NIMZO_INDIAN = OpeningPlan(
    name="Nimzo-Indian Defense",
    eco_codes=["E20", "E21", "E22", "E23", "E24", "E25", "E26", "E27", "E28", "E29", "E30", "E31", "E32", "E33", "E34", "E35", "E36", "E37", "E38", "E39", "E40", "E41", "E42", "E43", "E44", "E45", "E46", "E47", "E48", "E49", "E50", "E51", "E52", "E53", "E54", "E55", "E56", "E57", "E58", "E59"],
    identifying_moves=["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"],
    main_ideas=[
        "Pin the knight on c3 with your bishop",
        "Control e4 - don't let white play e4 easily",
        "If they play a3, trade bishop for knight and double their pawns"
    ],
    key_squares=["b4", "c3", "e4"],
    typical_mistakes=[
        "Trading the bishop too early without a plan",
        "Not fighting for e4 control",
        "Being too passive after the opening"
    ],
    simple_explanation="Pin their knight with Bb4. If they kick your bishop, trade it and give them doubled pawns.",
    teaching_moments={
        "Bb4": "The Nimzo-Indian! You're pinning their knight and controlling e4.",
        "O-O": "Good. Castle first, make plans later.",
        "c5": "Attacking d4. Good counterplay!",
        "Bxc3": "Now they have doubled pawns on c3. That's a weakness.",
    }
)

QUEENS_GAMBIT_DECLINED = OpeningPlan(
    name="Queen's Gambit Declined",
    eco_codes=["D30", "D31", "D32", "D33", "D34", "D35", "D36", "D37", "D38", "D39", "D40", "D41", "D42", "D43", "D44", "D45", "D46", "D47", "D48", "D49"],
    identifying_moves=["d4", "d5", "c4", "e6"],
    main_ideas=[
        "Don't take the pawn - defend d5 solidly",
        "Develop pieces behind your pawn wall",
        "Wait for the right moment to free your position with c5 or e5"
    ],
    key_squares=["d5", "e6", "c5"],
    typical_mistakes=[
        "Never playing c5 or e5 to free your pieces",
        "Leaving your light bishop trapped",
        "Being too passive"
    ],
    simple_explanation="Defend d5 with e6. Solid, but you must play c5 eventually to free your pieces.",
    teaching_moments={
        "e6": "The Queen's Gambit Declined. Solid! You keep your d5 pawn.",
        "Nf6": "Good development, attacking their e4 square.",
        "Be7": "Developing and preparing to castle.",
        "O-O": "Safe king. Now look for c5 to free your position.",
        "c5": "The key break! Now your pieces have room.",
    }
)

SLAV_DEFENSE = OpeningPlan(
    name="Slav Defense",
    eco_codes=["D10", "D11", "D12", "D13", "D14", "D15", "D16", "D17", "D18", "D19"],
    identifying_moves=["d4", "d5", "c4", "c6"],
    main_ideas=[
        "Defend d5 with c6 (not e6) so your bishop is free",
        "Your light bishop can go to f5 or g4",
        "Solid structure with active pieces"
    ],
    key_squares=["c6", "d5", "f5", "g4"],
    typical_mistakes=[
        "Playing e6 and blocking your bishop anyway",
        "Being too passive",
        "Not developing the light bishop early"
    ],
    simple_explanation="Defend d5 with c6 so your bishop can go to f5. Best of both worlds!",
    teaching_moments={
        "c6": "The Slav! You defend d5 AND keep your bishop free.",
        "Bf5": "See? Your bishop is out and active. That's the point of the Slav.",
        "e6": "Now solid. But make sure you got your bishop out first!",
        "Nf6": "Good development.",
    }
)

SCANDINAVIAN = OpeningPlan(
    name="Scandinavian Defense",
    eco_codes=["B01"],
    identifying_moves=["e4", "d5"],
    main_ideas=[
        "Immediately challenge e4",
        "After exd5 Qxd5, queen comes out early but it's okay",
        "Simple development, solid position"
    ],
    key_squares=["d5", "e4", "a5", "d6"],
    typical_mistakes=[
        "Keeping the queen in the center too long",
        "Not developing pieces quickly",
        "Forgetting to castle"
    ],
    simple_explanation="Immediately attack e4. Your queen comes out early but finds a safe square on a5.",
    teaching_moments={
        "d5": "The Scandinavian! Direct attack on e4.",
        "Qxd5": "Your queen is out early but it's okay here.",
        "Qa5": "Good square. Your queen is safe and active.",
        "Nf6": "Developing with tempo if white's queen is on d1.",
    }
)

PHILIDOR_DEFENSE = OpeningPlan(
    name="Philidor Defense",
    eco_codes=["C41"],
    identifying_moves=["e4", "e5", "Nf3", "d6"],
    main_ideas=[
        "Very solid - protect e5 with d6",
        "You can play f5 later for counterplay",
        "Patient, waiting for white to overextend"
    ],
    key_squares=["d6", "e5", "f5"],
    typical_mistakes=[
        "Being too passive",
        "Never playing f5 for counterplay",
        "Letting white dominate the center"
    ],
    simple_explanation="d6 is very solid. Protect e5 first, then look for f5 to counter-attack.",
    teaching_moments={
        "d6": "The Philidor Defense. Very solid! You protect e5 first.",
        "Nf6": "Developing and attacking e4.",
        "Be7": "Preparing to castle. Solid.",
        "O-O": "Good. Now you can think about f5 for counterplay.",
    }
)

PETROV_DEFENSE = OpeningPlan(
    name="Petrov Defense (Russian Game)",
    eco_codes=["C42", "C43"],
    identifying_moves=["e4", "e5", "Nf3", "Nf6"],
    main_ideas=[
        "Counter-attack e4 instead of defending e5",
        "Leads to equal, solid positions",
        "If white takes e5, don't take back immediately - play d6 first"
    ],
    key_squares=["e4", "e5", "d6"],
    typical_mistakes=[
        "Taking back on e5 immediately (Nxe4 is a trap!)",
        "Not knowing the theory",
        "Being passive"
    ],
    simple_explanation="Attack e4 right back! If they take your e5, play d6 first, then take back safely.",
    teaching_moments={
        "Nf6": "The Petrov! You attack e4 right back instead of defending e5.",
        "d6": "Important! This protects your knight on f6 and controls the center.",
        "Nxe4": "Now you can take back safely.",
    }
)


# ==================== OPENING DATABASE ====================

OPENING_PLANS: Dict[str, OpeningPlan] = {
    # White openings
    "italian": ITALIAN_GAME,
    "ruy_lopez": RUY_LOPEZ,
    "spanish": RUY_LOPEZ,
    "london": LONDON_SYSTEM,
    "queens_gambit": QUEENS_GAMBIT,
    "scotch": SCOTCH_GAME,
    "vienna": VIENNA_GAME,
    
    # Black responses
    "sicilian": SICILIAN_DEFENSE,
    "french": FRENCH_DEFENSE,
    "caro_kann": CARO_KANN,
    "kings_indian": KINGS_INDIAN,
    "nimzo_indian": NIMZO_INDIAN,
    "qgd": QUEENS_GAMBIT_DECLINED,
    "slav": SLAV_DEFENSE,
    "scandinavian": SCANDINAVIAN,
    "philidor": PHILIDOR_DEFENSE,
    "petrov": PETROV_DEFENSE,
}


def _normalize_san(move: str) -> str:
    """Normalize SAN for lightweight matching."""
    return (
        (move or "")
        .replace("+", "")
        .replace("#", "")
        .replace("!", "")
        .replace("?", "")
        .strip()
        .lower()
    )


def _opening_key(name: str) -> str:
    return (name or "").lower().replace(" ", "_").replace("'", "")


def _iter_unique_opening_plans() -> List[OpeningPlan]:
    unique_plans: List[OpeningPlan] = []
    seen_names = set()
    for plan in OPENING_PLANS.values():
        if plan.name in seen_names:
            continue
        seen_names.add(plan.name)
        unique_plans.append(plan)
    return unique_plans


def get_opening_family_by_moves(moves: List[str]) -> Optional[OpeningPlan]:
    """
    Find the deepest opening family that carries variation trees.

    This lets child openings like QGD/Slav inherit the richer family
    teaching data from the broader Queen's Gambit tree.
    """
    clean_moves = [_normalize_san(move) for move in moves if move]
    if not clean_moves:
        return None

    best_match = None
    best_depth = 0

    for plan in _iter_unique_opening_plans():
        if not plan.variations:
            continue

        identifying = [_normalize_san(move) for move in plan.identifying_moves]
        if len(clean_moves) < len(identifying):
            continue

        if clean_moves[: len(identifying)] == identifying and len(identifying) > best_depth:
            best_match = plan
            best_depth = len(identifying)

    return best_match


def build_opening_coaching_context(moves: List[str]) -> Optional[Dict]:
    """
    Build the opening payload used by the live coach.

    The direct opening keeps the visible name/ideas, while a broader family
    opening can contribute deeper variation trees, trap libraries, and
    extra teaching moments.
    """
    direct_opening = get_opening_by_moves(moves)
    family_opening = get_opening_family_by_moves(moves)

    if not direct_opening and not family_opening:
        return None

    primary_opening = direct_opening or family_opening

    teaching_moments: Dict[str, str] = {}
    main_ideas: List[str] = []
    typical_mistakes: List[str] = []
    variations: Dict[str, Dict] = {}

    if family_opening:
        teaching_moments.update(getattr(family_opening, "teaching_moments", {}) or {})
        main_ideas.extend(getattr(family_opening, "main_ideas", []) or [])
        typical_mistakes.extend(getattr(family_opening, "typical_mistakes", []) or [])
        variations.update(getattr(family_opening, "variations", {}) or {})

    if primary_opening:
        teaching_moments.update(getattr(primary_opening, "teaching_moments", {}) or {})
        main_ideas = (getattr(primary_opening, "main_ideas", []) or []) + main_ideas
        typical_mistakes = (getattr(primary_opening, "typical_mistakes", []) or []) + typical_mistakes
        variations.update(getattr(primary_opening, "variations", {}) or {})

    deduped_main_ideas = list(dict.fromkeys(main_ideas))
    deduped_mistakes = list(dict.fromkeys(typical_mistakes))

    family_key = _opening_key(getattr(family_opening, "name", "")) if family_opening else None
    primary_key = _opening_key(getattr(primary_opening, "name", "")) if primary_opening else None

    return {
        "name": getattr(primary_opening, "name", ""),
        "family_name": getattr(family_opening, "name", None) if family_opening else None,
        "key": primary_key,
        "family_key": family_key if family_key != primary_key else None,
        "identifying_moves": getattr(primary_opening, "identifying_moves", []),
        "teaching_moments": teaching_moments,
        "main_ideas": deduped_main_ideas,
        "typical_mistakes": deduped_mistakes,
        "variations": variations,
    }


def get_opening_by_moves(moves: List[str]) -> Optional[OpeningPlan]:
    """
    Try to identify opening from move list.
    Returns the best matching opening plan.
    """
    move_str = " ".join(moves[:6]).lower()
    
    # Italian: e4 e5 Nf3 Nc6 Bc4
    if "e4" in move_str and "e5" in move_str and "bc4" in move_str:
        return ITALIAN_GAME
    
    # Ruy Lopez: e4 e5 Nf3 Nc6 Bb5
    if "e4" in move_str and "e5" in move_str and "bb5" in move_str:
        return RUY_LOPEZ
    
    # Sicilian: e4 c5
    if move_str.startswith("e4") and "c5" in move_str[:8]:
        return SICILIAN_DEFENSE
    
    # French: e4 e6
    if "e4" in move_str and "e6" in move_str[:8]:
        return FRENCH_DEFENSE
    
    # Caro-Kann: e4 c6
    if "e4" in move_str and "c6" in move_str[:8]:
        return CARO_KANN
    
    # London: d4 Nf3 Bf4
    if "d4" in move_str and "bf4" in move_str:
        return LONDON_SYSTEM
    
    # Queen's Gambit: d4 d5 c4
    if "d4" in move_str and "d5" in move_str and "c4" in move_str:
        # Check if declined
        if "e6" in move_str:
            return QUEENS_GAMBIT_DECLINED
        if "c6" in move_str:
            return SLAV_DEFENSE
        return QUEENS_GAMBIT
    
    # King's Indian: d4 Nf6 c4 g6
    if "d4" in move_str and "g6" in move_str:
        return KINGS_INDIAN
    
    # Scandinavian: e4 d5
    if "e4" in move_str and "d5" in move_str[:8]:
        return SCANDINAVIAN
    
    # Petrov: e4 e5 Nf3 Nf6
    if "e4" in move_str and "e5" in move_str and move_str.count("nf") >= 2:
        return PETROV_DEFENSE
    
    return None


def get_teaching_for_move(opening: OpeningPlan, move_san: str) -> Optional[str]:
    """Get teaching moment for a specific move in an opening"""
    # Normalize move (remove + and # symbols)
    clean_move = move_san.replace("+", "").replace("#", "")
    return opening.teaching_moments.get(clean_move)


def get_all_openings() -> List[OpeningPlan]:
    """Get all opening plans"""
    return list(set(OPENING_PLANS.values()))
