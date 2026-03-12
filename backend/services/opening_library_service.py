"""
Opening Library Service
========================

Provides opening data, main lines, traps, and teaching content
for the Opening Training Lab.

Features:
- Opening database with main lines and explanations
- Trap library for each opening
- User progress tracking
- Personalized recommendations based on playing style
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# Opening database with teaching content
OPENING_DATABASE = {
    "italian-game": {
        "name": "Italian Game",
        "eco": "C50-C54",
        "description": "A classic opening focusing on quick development and central control. Great for tactical players who like open games.",
        "color": "white",
        "first_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
        "main_line": [
            {"move": "e4", "explanation": "Control the center and open lines for your bishop and queen."},
            {"move": "e5", "explanation": "Black mirrors, fighting for the center."},
            {"move": "Nf3", "explanation": "Develop with tempo, attacking the e5 pawn."},
            {"move": "Nc6", "explanation": "Black defends the pawn and develops."},
            {"move": "Bc4", "explanation": "The Italian! Targeting the weak f7 square."},
            {"move": "Bc5", "explanation": "The Giuoco Piano - Black develops actively."},
            {"move": "c3", "explanation": "Preparing d4 to build a strong center."},
            {"move": "Nf6", "explanation": "Black develops and attacks e4."},
            {"move": "d4", "explanation": "Strike in the center! This is the key move."},
            {"move": "exd4", "explanation": "Black captures, opening the position."},
            {"move": "cxd4", "explanation": "Recapture, maintaining the center."},
            {"move": "Bb4+", "explanation": "Black checks, disrupting your development."},
            {"move": "Bd2", "explanation": "Block and develop. You're ready to castle."}
        ],
        "key_ideas": [
            "Control the center with pawns on e4 and d4",
            "Target the f7 square - it's only defended by the king",
            "Develop all pieces before attacking",
            "Castle early for king safety"
        ],
        "common_mistakes": [
            {"move": "d3", "instead_of": "c3", "explanation": "d3 is passive. c3 prepares the strong d4 push."},
            {"move": "Ng5", "instead_of": "c3", "explanation": "Too early! Ng5 can be met with d5, and you lose time."}
        ],
        "traps": [
            {
                "name": "Fried Liver Attack",
                "description": "A deadly knight sacrifice on f7 that wins material and exposes Black's king.",
                "setup_moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"],
                "trap_line": [
                    {"move": "d5", "explanation": "Black tries to block, but it's too late..."},
                    {"move": "exd5", "explanation": "White captures the pawn."},
                    {"move": "Nxd5", "explanation": "Black recaptures, but the knight is vulnerable."},
                    {"move": "Nxf7", "explanation": "The Fried Liver sacrifice! Knight takes on f7."},
                    {"move": "Kxf7", "explanation": "Black must capture."},
                    {"move": "Qf3+", "explanation": "Check! Double attack on king and knight on d5."},
                    {"move": "Ke6", "explanation": "The king is forced forward into danger."},
                    {"move": "Nc3", "explanation": "Develop with tempo. White wins the knight and has a crushing attack."}
                ],
                "success_message": "The Fried Liver Attack! Black's king is exposed and you win material."
            },
            {
                "name": "Legal's Mate Trap",
                "description": "A beautiful queen sacrifice leading to checkmate.",
                "setup_moves": ["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "g6"],
                "trap_line": [
                    {"move": "Nxe5", "explanation": "Sacrifice! Offering the queen to set up checkmate."},
                    {"move": "Bxd1", "explanation": "Black takes the queen, falling into the trap!"},
                    {"move": "Bxf7+", "explanation": "Check! The king must move."},
                    {"move": "Ke7", "explanation": "Forced - the only legal move."},
                    {"move": "Nd5#", "explanation": "Checkmate! The Legal's Mate - a queen sacrifice for mate."}
                ],
                "success_message": "Legal's Mate! A beautiful queen sacrifice leading to checkmate."
            }
        ],
        "what_if": [
            {
                "deviation": "Nf6 instead of Bc5",
                "name": "Two Knights Defense",
                "response": "After Bc5 Nf6, you can play Ng5 for the Fried Liver or d3 for a quieter game.",
                "recommendation": "Ng5 is aggressive and good for tactical players!"
            },
            {
                "deviation": "d6 instead of Bc5", 
                "name": "Hungarian Defense",
                "response": "Black plays passively. Simply play d4 and you get a great center.",
                "recommendation": "d4 immediately, then Nc3. You'll have a nice advantage."
            }
        ]
    },
    "sicilian-defense": {
        "name": "Sicilian Defense",
        "eco": "B20-B99",
        "description": "The most popular response to e4. Black fights for counterplay from move one. Sharp and complex.",
        "color": "black",
        "first_moves": ["e4", "c5"],
        "main_line": [
            {"move": "e4", "explanation": "White takes the center."},
            {"move": "c5", "explanation": "The Sicilian! Fighting for d4 control without mirroring."},
            {"move": "Nf3", "explanation": "White develops, preparing d4."},
            {"move": "d6", "explanation": "Solid. Preparing ...Nf6 and ...e5 or ...e6."},
            {"move": "d4", "explanation": "White opens the position."},
            {"move": "cxd4", "explanation": "Exchange, creating an open c-file for your rook."},
            {"move": "Nxd4", "explanation": "White recaptures with the knight."},
            {"move": "Nf6", "explanation": "Develop and attack e4."},
            {"move": "Nc3", "explanation": "White defends e4 and develops."},
            {"move": "a6", "explanation": "The Najdorf! Preparing ...b5 and controlling b5."}
        ],
        "key_ideas": [
            "Use the half-open c-file for your rook",
            "Play ...d5 break when ready to free your position",
            "Your queenside pawn majority can become dangerous in endgames",
            "Don't rush - Black's position is solid but needs careful play"
        ],
        "common_mistakes": [
            {"move": "e5", "instead_of": "d6", "explanation": "e5 weakens d5 and d6 squares. The position becomes hard to play."},
            {"move": "Nc6", "instead_of": "d6", "explanation": "Nc6 early allows Bb5, and after d4 you may face an awkward pin."}
        ],
        "traps": [
            {
                "name": "Siberian Trap",
                "description": "A deadly trap where Black wins White's queen with a bishop check!",
                "setup_moves": ["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "Bb4"],
                "trap_line": [
                    {"move": "e5", "explanation": "White attacks the knight - a common but losing move!"},
                    {"move": "Qa5", "explanation": "Black threatens Bxc3+ winning the queen."},
                    {"move": "exf6", "explanation": "White captures, but falls into the trap..."},
                    {"move": "Bxc3+", "explanation": "Check! The bishop takes the knight with check."},
                    {"move": "Bd2", "explanation": "White blocks the check."},
                    {"move": "Bxd2+", "explanation": "Take the bishop with another check!"},
                    {"move": "Qxd2", "explanation": "White must take with the queen."},
                    {"move": "Qxd2+", "explanation": "The Siberian Trap! Black wins White's queen."}
                ],
                "success_message": "The Siberian Trap! Black wins White's queen for just a knight."
            }
        ],
        "what_if": [
            {
                "deviation": "Bc4 instead of d4",
                "name": "Sicilian with Bc4",
                "response": "Play e6 to block the bishop, then d5 when ready.",
                "recommendation": "Don't fear it. e6 followed by d5 gives you a good game."
            }
        ]
    },
    "queens-gambit": {
        "name": "Queen's Gambit",
        "eco": "D00-D69",
        "description": "A solid, strategic opening. White offers a pawn to gain central control. Not a real gambit - the pawn can be recovered.",
        "color": "white",
        "first_moves": ["d4", "d5", "c4"],
        "main_line": [
            {"move": "d4", "explanation": "Control the center with your d-pawn."},
            {"move": "d5", "explanation": "Black stakes a claim in the center too."},
            {"move": "c4", "explanation": "The Queen's Gambit! Attack Black's center."},
            {"move": "e6", "explanation": "Queen's Gambit Declined - Black holds the center."},
            {"move": "Nc3", "explanation": "Develop and add pressure on d5."},
            {"move": "Nf6", "explanation": "Black develops, defending d5."},
            {"move": "Bg5", "explanation": "Pin the knight! Adding pressure."},
            {"move": "Be7", "explanation": "Black breaks the pin."},
            {"move": "e3", "explanation": "Solid. Preparing Bd3 and O-O."},
            {"move": "O-O", "explanation": "Black castles to safety."},
            {"move": "Nf3", "explanation": "Complete development, ready to castle."}
        ],
        "key_ideas": [
            "Control the center with pawns on d4 and eventually e4",
            "The c4 pawn attacks d5 - don't worry about losing it temporarily",
            "Develop pieces to active squares, then look for e4 break",
            "Minority attack on the queenside (a4-b5) is a common plan"
        ],
        "common_mistakes": [
            {"move": "e4", "instead_of": "Nc3", "explanation": "e4 too early weakens d4. Develop first!"},
            {"move": "Bd3", "instead_of": "Nc3", "explanation": "Bd3 blocks your d-pawn. Nc3 is more flexible."}
        ],
        "traps": [
            {
                "name": "Elephant Trap",
                "description": "Black wins a piece with a beautiful intermezzo check!",
                "setup_moves": ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5"],
                "trap_line": [
                    {"move": "Nxd5", "explanation": "Black recaptures the pawn."},
                    {"move": "Bxd8", "explanation": "White thinks they win the queen! But..."},
                    {"move": "Bb4+", "explanation": "Intermezzo! Check with the bishop."},
                    {"move": "Qd2", "explanation": "White blocks with the queen."},
                    {"move": "Bxd2+", "explanation": "Take the queen with check!"},
                    {"move": "Kxd2", "explanation": "White must recapture."},
                    {"move": "Kxd8", "explanation": "Now Black takes back the bishop. You're up a full piece!"}
                ],
                "success_message": "The Elephant Trap! The intermezzo check wins a piece."
            }
        ],
        "what_if": [
            {
                "deviation": "dxc4 (Queen's Gambit Accepted)",
                "name": "Queen's Gambit Accepted",
                "response": "Play e3 or e4 and Bxc4. You'll easily regain the pawn with a great position.",
                "recommendation": "Don't worry about the pawn. e3 followed by Bxc4 is simple and strong."
            }
        ]
    },
    "london-system": {
        "name": "London System",
        "eco": "D00",
        "description": "A solid, easy-to-learn system. Same setup against almost anything Black plays. Great for beginners and club players.",
        "color": "white",
        "first_moves": ["d4", "Bf4"],
        "main_line": [
            {"move": "d4", "explanation": "Claim the center."},
            {"move": "d5", "explanation": "Black responds symmetrically."},
            {"move": "Bf4", "explanation": "The London! Develop the bishop before e3."},
            {"move": "Nf6", "explanation": "Black develops naturally."},
            {"move": "e3", "explanation": "Solid. Support d4 and prepare Bd3."},
            {"move": "c5", "explanation": "Black challenges your center."},
            {"move": "c3", "explanation": "Reinforce d4. Your structure is rock solid."},
            {"move": "Nc6", "explanation": "Black continues developing."},
            {"move": "Nd2", "explanation": "The knight goes here in the London, not c3."},
            {"move": "e6", "explanation": "Black solidifies."},
            {"move": "Ngf3", "explanation": "Complete development."},
            {"move": "Bd6", "explanation": "Black challenges your bishop."},
            {"move": "Bg3", "explanation": "Keep the bishop! It's valuable."}
        ],
        "key_ideas": [
            "Always play Bf4 before e3 - don't trap your bishop!",
            "The setup is Bf4, e3, Bd3, Nf3, Nbd2, c3 - same against everything",
            "Don't trade your dark-squared bishop easily - it's your best piece",
            "Play for a kingside attack with h4-h5 or central e4 break"
        ],
        "common_mistakes": [
            {"move": "e3", "instead_of": "Bf4", "explanation": "e3 first traps your bishop on c1. Always Bf4 first!"},
            {"move": "Bxd6", "instead_of": "Bg3", "explanation": "Don't trade! Your bishop is better than Black's."}
        ],
        "traps": [
            {
                "name": "Englund Gambit Trap",
                "description": "Refute the dubious Englund Gambit and trap Black's queen!",
                "setup_moves": ["d4", "e5", "dxe5", "Nc6", "Nf3", "Qe7", "Bf4", "Qb4+"],
                "trap_line": [
                    {"move": "Bd2", "explanation": "Block the check with the bishop."},
                    {"move": "Qxb2", "explanation": "Black grabs the pawn greedily, but..."},
                    {"move": "Bc3", "explanation": "The queen is trapped! No safe squares."},
                    {"move": "Qb4", "explanation": "Black tries to escape, but..."},
                    {"move": "Bxb4", "explanation": "Take the queen! She has nowhere to run."}
                ],
                "success_message": "The Englund Gambit refuted! Black's greed costs them the queen."
            }
        ],
        "what_if": [
            {
                "deviation": "Nf6 before d5",
                "name": "Indian Defense Setup",
                "response": "Continue with Bf4, e3, Nf3. Your system works against everything!",
                "recommendation": "Stick to your setup. The London works against all defenses."
            }
        ]
    },
    "caro-kann": {
        "name": "Caro-Kann Defense",
        "eco": "B10-B19",
        "description": "A solid, reliable defense against e4. Black aims for a sound pawn structure and long-term play.",
        "color": "black",
        "first_moves": ["e4", "c6"],
        "main_line": [
            {"move": "e4", "explanation": "White takes the center."},
            {"move": "c6", "explanation": "The Caro-Kann! Preparing d5 with support."},
            {"move": "d4", "explanation": "White builds a big center."},
            {"move": "d5", "explanation": "Challenge the center immediately."},
            {"move": "Nc3", "explanation": "White defends e4."},
            {"move": "dxe4", "explanation": "Exchange, leading to the main lines."},
            {"move": "Nxe4", "explanation": "White recaptures with the knight."},
            {"move": "Bf5", "explanation": "Develop the bishop BEFORE e6. This is key!"},
            {"move": "Ng3", "explanation": "White attacks the bishop."},
            {"move": "Bg6", "explanation": "Retreat but stay active on the diagonal."},
            {"move": "h4", "explanation": "White gains space, threatening h5."},
            {"move": "h6", "explanation": "Stop h5, keep your bishop safe."}
        ],
        "key_ideas": [
            "Develop your light-squared bishop BEFORE playing e6",
            "Your pawn structure is solid - no weaknesses",
            "Play for ...c5 break to challenge White's center",
            "Endgames often favor Black due to better pawn structure"
        ],
        "common_mistakes": [
            {"move": "e6", "instead_of": "Bf5", "explanation": "e6 traps your bishop on c8. Always Bf5 first!"},
            {"move": "Nf6", "instead_of": "Bf5", "explanation": "Nf6 allows Nxf6+ ruining your structure. Bf5 first!"}
        ],
        "traps": [],
        "what_if": [
            {
                "deviation": "e5 (Advance Variation)",
                "name": "Advance Variation",
                "response": "Play Bf5 (before e6!), then e6, c5. Attack the d4 pawn.",
                "recommendation": "Bf5, e6, c5. Your position is solid and you'll attack d4."
            },
            {
                "deviation": "Nf3 (Two Knights)",
                "name": "Two Knights Variation",
                "response": "Play dxe4, then Nxe4 Nf6 or Bf5. Solid and equal.",
                "recommendation": "After dxe4 Nxe4, play Nf6 to trade knights for an easy game."
            }
        ]
    },
    "kings-indian-defense": {
        "name": "King's Indian Defense",
        "eco": "E60-E99",
        "description": "An aggressive, counterattacking defense. Black lets White build a center, then attacks it. For fighters!",
        "color": "black",
        "first_moves": ["d4", "Nf6", "c4", "g6"],
        "main_line": [
            {"move": "d4", "explanation": "White takes the center."},
            {"move": "Nf6", "explanation": "Flexible. See what White plays."},
            {"move": "c4", "explanation": "White expands."},
            {"move": "g6", "explanation": "The King's Indian! Fianchetto coming."},
            {"move": "Nc3", "explanation": "White develops."},
            {"move": "Bg7", "explanation": "The fianchetto. Your bishop eyes the center."},
            {"move": "e4", "explanation": "White builds a big center. Let them!"},
            {"move": "d6", "explanation": "Prepare ...e5 or ...c5 counterplay."},
            {"move": "Nf3", "explanation": "White completes development."},
            {"move": "O-O", "explanation": "Castle and prepare your attack!"},
            {"move": "Be2", "explanation": "White develops calmly."},
            {"move": "e5", "explanation": "Strike! Challenge the center."}
        ],
        "key_ideas": [
            "Let White build a big center - you'll attack it later",
            "Kingside attack with f5-f4 is your main plan",
            "Your dark-squared bishop on g7 is a monster - don't trade it",
            "Play ...e5 then ...f5 to start your attack"
        ],
        "common_mistakes": [
            {"move": "d5", "instead_of": "d6", "explanation": "d5 blocks your bishop. d6 keeps options open."},
            {"move": "e6", "instead_of": "d6", "explanation": "e6 is passive and blocks your f-pawn. d6 is correct."}
        ],
        "traps": [],
        "what_if": [
            {
                "deviation": "Bg5 (Averbakh)",
                "name": "Averbakh Variation",
                "response": "Play h6 to ask the bishop what it wants. Then continue normally.",
                "recommendation": "h6 is simple. After Bh4, play g5 Bg3 Nh5 for active play."
            }
        ]
    },
    "scandinavian-defense": {
        "name": "Scandinavian Defense",
        "eco": "B01",
        "description": "An aggressive defense where Black immediately challenges White's e4 pawn. Simple but solid.",
        "color": "black",
        "first_moves": ["e4", "d5"],
        "main_line": [
            {"move": "e4", "explanation": "White takes the center."},
            {"move": "d5", "explanation": "The Scandinavian! Immediate counterattack."},
            {"move": "exd5", "explanation": "White takes. Now you have a choice..."},
            {"move": "Qxd5", "explanation": "Main line - recapture with the queen."},
            {"move": "Nc3", "explanation": "White attacks your queen, gaining time."},
            {"move": "Qa5", "explanation": "Safe square. The queen stays active."},
            {"move": "d4", "explanation": "White builds a center."},
            {"move": "Nf6", "explanation": "Develop and eye the d5 square."},
            {"move": "Nf3", "explanation": "White develops."},
            {"move": "Bf5", "explanation": "Develop your bishop actively!"},
            {"move": "Bc4", "explanation": "White develops aggressively."},
            {"move": "e6", "explanation": "Solid. Block the bishop's diagonal."}
        ],
        "key_ideas": [
            "Your queen comes out early but finds a safe square on a5",
            "Develop your light bishop to f5 before playing e6",
            "Your structure is solid - no weaknesses",
            "Play ...c6 and ...Nbd7 for a solid setup"
        ],
        "common_mistakes": [
            {"move": "Qd8", "instead_of": "Qa5", "explanation": "Qd8 wastes time. Qa5 is active and safe."},
            {"move": "e6", "instead_of": "Bf5", "explanation": "e6 traps your bishop. Always Bf5 first!"}
        ],
        "traps": [],
        "what_if": [
            {
                "deviation": "d4 instead of Nc3",
                "name": "d4 Line",
                "response": "Play Qd8 or Qa5. Both are fine. Then develop normally.",
                "recommendation": "Qa5 keeps the queen active. Then Nf6, Bf5, e6."
            }
        ]
    },
    "nimzowitsch-defense": {
        "name": "Nimzowitsch Defense",
        "eco": "B00",
        "description": "An unusual defense where Black plays Nc6 against e4. Flexible and surprising.",
        "color": "black",
        "first_moves": ["e4", "Nc6"],
        "main_line": [
            {"move": "e4", "explanation": "White takes the center."},
            {"move": "Nc6", "explanation": "The Nimzowitsch! Unusual but solid."},
            {"move": "d4", "explanation": "White expands."},
            {"move": "d5", "explanation": "Counter in the center!"},
            {"move": "e5", "explanation": "White advances, gaining space."},
            {"move": "Bf5", "explanation": "Develop the bishop actively."},
            {"move": "Nf3", "explanation": "White develops."},
            {"move": "e6", "explanation": "Solid. Support your d5 pawn."},
            {"move": "Be2", "explanation": "White prepares to castle."},
            {"move": "Nge7", "explanation": "The knight goes to e7 to support d5 and f5."}
        ],
        "key_ideas": [
            "Fight for d5 - it's your key central square",
            "Develop the light bishop before e6",
            "Your knight structure (Nc6-Nge7) is flexible",
            "Look for ...f6 to challenge White's e5 pawn"
        ],
        "common_mistakes": [
            {"move": "e5", "instead_of": "d5", "explanation": "e5 is met by d5! attacking your knight with no good square."},
            {"move": "e6", "instead_of": "Bf5", "explanation": "Always develop the bishop before e6!"}
        ],
        "traps": [],
        "what_if": [
            {
                "deviation": "Nf3 instead of d4",
                "name": "Quiet Line",
                "response": "Play e5 grabbing central space, then d6 and normal development.",
                "recommendation": "e5 is strong here since White can't play d4 immediately."
            }
        ]
    },
    
    "ruy-lopez": {
        "name": "Ruy Lopez",
        "eco": "C60-C99",
        "description": "The Spanish Game - one of the oldest and most classic openings. Rich in strategy and tactics.",
        "color": "white",
        "first_moves": ["e4", "e5", "Nf3", "Nc6", "Bb5"],
        "main_line": [
            {"move": "e4", "explanation": "Control the center."},
            {"move": "e5", "explanation": "Black fights for the center."},
            {"move": "Nf3", "explanation": "Attack the e5 pawn."},
            {"move": "Nc6", "explanation": "Defend the pawn."},
            {"move": "Bb5", "explanation": "The Ruy Lopez! Pinning the knight indirectly."},
            {"move": "a6", "explanation": "The Morphy Defense - challenging the bishop."},
            {"move": "Ba4", "explanation": "Maintain the pin."},
            {"move": "Nf6", "explanation": "Develop and attack e4."},
            {"move": "O-O", "explanation": "Castle for king safety."},
            {"move": "Be7", "explanation": "Prepare to castle."},
            {"move": "Re1", "explanation": "Support the e4 pawn."},
            {"move": "b5", "explanation": "Chase the bishop."},
            {"move": "Bb3", "explanation": "The bishop retreats to a strong diagonal."}
        ],
        "key_ideas": [
            "The bishop on b5 indirectly pressures the e5 pawn through the knight",
            "White aims for a slow strategic squeeze",
            "Central control with pawns on e4 and d4 is the goal",
            "The Marshall Attack is a dangerous gambit Black can play"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "philidor-defense": {
        "name": "Philidor Defense",
        "eco": "C41",
        "description": "A solid but passive defense where Black plays d6 instead of Nc6. Can transpose to many setups.",
        "color": "black",
        "first_moves": ["e4", "e5", "Nf3", "d6"],
        "main_line": [
            {"move": "e4", "explanation": "White opens with the king's pawn."},
            {"move": "e5", "explanation": "Black mirrors."},
            {"move": "Nf3", "explanation": "Attacking the e5 pawn."},
            {"move": "d6", "explanation": "The Philidor! Defending solidly."},
            {"move": "d4", "explanation": "White strikes in the center."},
            {"move": "Nf6", "explanation": "Develop and attack e4."},
            {"move": "Nc3", "explanation": "Develop the knight."},
            {"move": "Nbd7", "explanation": "Black develops."},
            {"move": "Bc4", "explanation": "Targeting f7."},
            {"move": "Be7", "explanation": "Prepare to castle."},
            {"move": "O-O", "explanation": "Castle for safety."},
            {"move": "O-O", "explanation": "Black also castles."}
        ],
        "key_ideas": [
            "Black's setup is solid but passive",
            "Watch out for the Legal's Mate trap!",
            "Black often aims for ...c6 and ...d5 counter-strike",
            "Piece activity can be limited if not careful"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "petrov-defense": {
        "name": "Petrov Defense",
        "eco": "C42-C43",
        "description": "A symmetrical defense known for its solidity. Black mirrors White's play.",
        "color": "black",
        "first_moves": ["e4", "e5", "Nf3", "Nf6"],
        "main_line": [
            {"move": "e4", "explanation": "White opens."},
            {"move": "e5", "explanation": "Black mirrors."},
            {"move": "Nf3", "explanation": "Attacking e5."},
            {"move": "Nf6", "explanation": "The Petrov! Counter-attacking e4."},
            {"move": "Nxe5", "explanation": "White takes the pawn."},
            {"move": "d6", "explanation": "Attacking the knight."},
            {"move": "Nf3", "explanation": "Knight retreats."},
            {"move": "Nxe4", "explanation": "Black wins the pawn back."},
            {"move": "d4", "explanation": "White builds the center."},
            {"move": "d5", "explanation": "Black holds the center."},
            {"move": "Bd3", "explanation": "Develop and attack the knight."},
            {"move": "Nc6", "explanation": "Develop the knight."}
        ],
        "key_ideas": [
            "Very solid and drawish opening",
            "Don't take on e5 too early - develop first!",
            "The Stafford Gambit (Nc6 instead of d6) is risky but trappy",
            "Often leads to equal, symmetrical positions"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "budapest-gambit": {
        "name": "Budapest Gambit",
        "eco": "A51-A52",
        "description": "A sharp gambit where Black sacrifices a pawn for active piece play. Full of traps!",
        "color": "black",
        "first_moves": ["d4", "Nf6", "c4", "e5"],
        "main_line": [
            {"move": "d4", "explanation": "White plays the queen's pawn."},
            {"move": "Nf6", "explanation": "Develop the knight."},
            {"move": "c4", "explanation": "The English Attack."},
            {"move": "e5", "explanation": "The Budapest Gambit! A pawn sacrifice."},
            {"move": "dxe5", "explanation": "White takes the pawn."},
            {"move": "Ng4", "explanation": "Attack the e5 pawn."},
            {"move": "Bf4", "explanation": "Defend the pawn."},
            {"move": "Nc6", "explanation": "Develop and attack e5."},
            {"move": "Nf3", "explanation": "Defend and develop."},
            {"move": "Bb4+", "explanation": "Check! Creating threats."},
            {"move": "Nbd2", "explanation": "Block the check."},
            {"move": "Qe7", "explanation": "Pressure on e5."}
        ],
        "key_ideas": [
            "Black sacrifices a pawn for active piece play",
            "Many tactical traps exist, especially the Kieninger Trap",
            "If White is careless, Black can get a crushing attack",
            "White must know the theory or risk getting trapped"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "dutch-defense": {
        "name": "Dutch Defense",
        "eco": "A80-A99",
        "description": "An aggressive defense where Black plays f5, fighting for control of e4.",
        "color": "black",
        "first_moves": ["d4", "f5"],
        "main_line": [
            {"move": "d4", "explanation": "White opens."},
            {"move": "f5", "explanation": "The Dutch! Fighting for e4."},
            {"move": "g3", "explanation": "Fianchetto setup."},
            {"move": "Nf6", "explanation": "Develop the knight."},
            {"move": "Bg2", "explanation": "Fianchetto the bishop."},
            {"move": "e6", "explanation": "Support d5 and the f5 pawn."},
            {"move": "Nf3", "explanation": "Develop."},
            {"move": "Be7", "explanation": "Develop the bishop."},
            {"move": "O-O", "explanation": "Castle for safety."},
            {"move": "O-O", "explanation": "Black castles."},
            {"move": "c4", "explanation": "Control the center."},
            {"move": "d6", "explanation": "Solid setup."}
        ],
        "key_ideas": [
            "f5 controls the e4 square",
            "The Leningrad Variation (g6, Bg7) is very popular",
            "Watch out for early Bg5 pins!",
            "Can lead to sharp kingside attacks"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "french-defense": {
        "name": "French Defense",
        "eco": "C00-C19",
        "description": "A solid defense where Black locks the center with e6. Leads to strategic battles.",
        "color": "black",
        "first_moves": ["e4", "e6"],
        "main_line": [
            {"move": "e4", "explanation": "White opens."},
            {"move": "e6", "explanation": "The French Defense! Preparing d5."},
            {"move": "d4", "explanation": "White builds the center."},
            {"move": "d5", "explanation": "Challenge the center!"},
            {"move": "Nc3", "explanation": "Develop and defend."},
            {"move": "Nf6", "explanation": "Attack e4."},
            {"move": "Bg5", "explanation": "Pin the knight."},
            {"move": "Be7", "explanation": "Break the pin."},
            {"move": "e5", "explanation": "The Advance Variation."},
            {"move": "Nfd7", "explanation": "Knight retreats."},
            {"move": "Bxe7", "explanation": "Trade bishops."},
            {"move": "Qxe7", "explanation": "Recapture."}
        ],
        "key_ideas": [
            "Black's light-squared bishop can be passive",
            "The c5 break is crucial for counterplay",
            "The Winawer (Bb4) is the sharpest line",
            "Black often attacks on the queenside"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "slav-defense": {
        "name": "Slav Defense",
        "eco": "D10-D19",
        "description": "A solid response to the Queen's Gambit. Black keeps the light-squared bishop active.",
        "color": "black",
        "first_moves": ["d4", "d5", "c4", "c6"],
        "main_line": [
            {"move": "d4", "explanation": "White opens."},
            {"move": "d5", "explanation": "Black mirrors."},
            {"move": "c4", "explanation": "The Queen's Gambit."},
            {"move": "c6", "explanation": "The Slav! Supporting d5 without blocking the bishop."},
            {"move": "Nf3", "explanation": "Develop."},
            {"move": "Nf6", "explanation": "Develop."},
            {"move": "Nc3", "explanation": "Develop."},
            {"move": "dxc4", "explanation": "Accept the gambit."},
            {"move": "a4", "explanation": "Prevent b5."},
            {"move": "Bf5", "explanation": "The key idea - develop the bishop before e6!"},
            {"move": "e3", "explanation": "Prepare to recapture."},
            {"move": "e6", "explanation": "Now e6 is fine."}
        ],
        "key_ideas": [
            "Develop the light-squared bishop before playing e6!",
            "The Semi-Slav (e6 before Bf5) is a different system",
            "c6 supports d5 without blocking pieces",
            "Very solid and reliable"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "nimzo-indian": {
        "name": "Nimzo-Indian Defense",
        "eco": "E20-E59",
        "description": "One of Black's best responses to 1.d4. Black pins the knight and fights for control.",
        "color": "black",
        "first_moves": ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"],
        "main_line": [
            {"move": "d4", "explanation": "White opens."},
            {"move": "Nf6", "explanation": "Develop."},
            {"move": "c4", "explanation": "Expand."},
            {"move": "e6", "explanation": "Prepare Bb4."},
            {"move": "Nc3", "explanation": "Develop."},
            {"move": "Bb4", "explanation": "The Nimzo-Indian! Pin the knight."},
            {"move": "Qc2", "explanation": "The Classical variation."},
            {"move": "O-O", "explanation": "Castle for safety."},
            {"move": "a3", "explanation": "Challenge the bishop."},
            {"move": "Bxc3+", "explanation": "Trade."},
            {"move": "Qxc3", "explanation": "Recapture."},
            {"move": "d5", "explanation": "Strike in the center!"}
        ],
        "key_ideas": [
            "Bb4 pins the knight and doubles White's pawns if traded",
            "Black often gives up the bishop pair for structural advantage",
            "e5 is often a key break for Black",
            "Very solid and strategically rich"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "vienna-game": {
        "name": "Vienna Game",
        "eco": "C25-C29",
        "description": "A romantic opening where White delays Nf3 to play f4 quickly.",
        "color": "white",
        "first_moves": ["e4", "e5", "Nc3"],
        "main_line": [
            {"move": "e4", "explanation": "Open with the king's pawn."},
            {"move": "e5", "explanation": "Black mirrors."},
            {"move": "Nc3", "explanation": "The Vienna! Delaying Nf3."},
            {"move": "Nf6", "explanation": "Black develops."},
            {"move": "f4", "explanation": "The Vienna Gambit!"},
            {"move": "d5", "explanation": "Black strikes in the center."},
            {"move": "fxe5", "explanation": "Take the pawn."},
            {"move": "Nxe4", "explanation": "Black wins it back."},
            {"move": "Nf3", "explanation": "Develop."},
            {"move": "Bg4", "explanation": "Pin the knight."},
            {"move": "Qe2", "explanation": "Defend and prepare."}
        ],
        "key_ideas": [
            "f4 is the main idea - Vienna Gambit",
            "Can transpose to King's Gambit lines",
            "Bc4 is also possible for quieter play",
            "Sharp and tactical"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "queens-indian": {
        "name": "Queen's Indian Defense",
        "eco": "E12-E19",
        "description": "A flexible defense where Black fianchettoes the queen's bishop.",
        "color": "black",
        "first_moves": ["d4", "Nf6", "c4", "e6", "Nf3", "b6"],
        "main_line": [
            {"move": "d4", "explanation": "White opens."},
            {"move": "Nf6", "explanation": "Develop."},
            {"move": "c4", "explanation": "Expand."},
            {"move": "e6", "explanation": "Flexible."},
            {"move": "Nf3", "explanation": "Develop."},
            {"move": "b6", "explanation": "The Queen's Indian! Prepare Bb7."},
            {"move": "g3", "explanation": "Fianchetto."},
            {"move": "Bb7", "explanation": "Develop the bishop."},
            {"move": "Bg2", "explanation": "Complete the fianchetto."},
            {"move": "Be7", "explanation": "Develop."},
            {"move": "O-O", "explanation": "Castle."},
            {"move": "O-O", "explanation": "Black castles too."}
        ],
        "key_ideas": [
            "Bb7 controls the long diagonal",
            "Very flexible - can transpose to other systems",
            "Black often plays d5 or c5",
            "Strategic and positional"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "grunfeld-defense": {
        "name": "Grunfeld Defense",
        "eco": "D70-D99",
        "description": "A hypermodern defense where Black lets White build a center to attack it later.",
        "color": "black",
        "first_moves": ["d4", "Nf6", "c4", "g6", "Nc3", "d5"],
        "main_line": [
            {"move": "d4", "explanation": "White opens."},
            {"move": "Nf6", "explanation": "Develop."},
            {"move": "c4", "explanation": "Expand."},
            {"move": "g6", "explanation": "Prepare fianchetto."},
            {"move": "Nc3", "explanation": "Develop."},
            {"move": "d5", "explanation": "The Grunfeld! Strike at the center."},
            {"move": "cxd5", "explanation": "Exchange Variation."},
            {"move": "Nxd5", "explanation": "Recapture."},
            {"move": "e4", "explanation": "Build a big center."},
            {"move": "Nxc3", "explanation": "Trade."},
            {"move": "bxc3", "explanation": "Recapture."},
            {"move": "Bg7", "explanation": "Fianchetto - attacking the center!"}
        ],
        "key_ideas": [
            "Black allows White a big center to attack it",
            "The Bg7 is a monster piece",
            "c5 and e5 breaks are key",
            "Requires precise play from both sides"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    },
    
    "benoni-defense": {
        "name": "Benoni Defense",
        "eco": "A60-A79",
        "description": "A sharp defense where Black creates an asymmetrical pawn structure.",
        "color": "black",
        "first_moves": ["d4", "Nf6", "c4", "c5", "d5"],
        "main_line": [
            {"move": "d4", "explanation": "White opens."},
            {"move": "Nf6", "explanation": "Develop."},
            {"move": "c4", "explanation": "Expand."},
            {"move": "c5", "explanation": "Challenge d4!"},
            {"move": "d5", "explanation": "White advances."},
            {"move": "e6", "explanation": "Attack d5."},
            {"move": "Nc3", "explanation": "Develop."},
            {"move": "exd5", "explanation": "Open the e-file."},
            {"move": "cxd5", "explanation": "Recapture."},
            {"move": "d6", "explanation": "Solid structure."},
            {"move": "e4", "explanation": "Build the center."},
            {"move": "g6", "explanation": "Fianchetto setup."}
        ],
        "key_ideas": [
            "Black has a queenside pawn majority",
            "The e5 break is critical for White",
            "Black aims for b5 counterplay",
            "Sharp and double-edged"
        ],
        "common_mistakes": [],
        "traps": [],
        "what_if": []
    }
}


@dataclass
class OpeningProgress:
    """Tracks user's progress on a specific opening."""
    opening_key: str
    user_id: str
    main_line_progress: int = 0  # How many moves they know
    traps_learned: List[str] = field(default_factory=list)
    times_practiced: int = 0
    last_practiced: Optional[datetime] = None
    mastery_level: str = "unknown"  # unknown, learning, practiced, comfortable, mastered


def get_opening_data(opening_key: str) -> Optional[Dict]:
    """Get full opening data by key, including traps from the trap library."""
    from services.trap_library import get_traps_for_opening
    
    opening = OPENING_DATABASE.get(opening_key)
    if not opening:
        return None
    
    # Get traps from the comprehensive trap library
    traps = get_traps_for_opening(opening_key)
    
    # Return opening with traps from the library
    return {
        **opening,
        "traps": traps if traps else opening.get("traps", [])
    }


def get_all_openings() -> List[Dict]:
    """Get list of all openings with basic info."""
    from services.trap_library import get_traps_for_opening
    
    result = []
    for key, data in OPENING_DATABASE.items():
        # Get trap count from trap library
        traps = get_traps_for_opening(key)
        trap_count = len(traps) if traps else len(data.get("traps", []))
        
        result.append({
            "key": key,
            "name": data["name"],
            "eco": data["eco"],
            "color": data["color"],
            "description": data["description"],
            "trap_count": trap_count
        })
    return result


def get_openings_for_color(color: str) -> List[Dict]:
    """Get openings for a specific color."""
    from services.trap_library import get_traps_for_opening
    
    result = []
    for key, data in OPENING_DATABASE.items():
        if data["color"] == color:
            traps = get_traps_for_opening(key)
            trap_count = len(traps) if traps else len(data.get("traps", []))
            
            result.append({
                "key": key,
                "name": data["name"],
                "eco": data["eco"],
                "description": data["description"],
                "trap_count": trap_count
            })
    return result


def match_opening_to_library(opening_name: str, eco: str = None) -> Optional[str]:
    """
    Match a game's opening name to our library.
    Returns the opening key if found.
    
    Uses multiple matching strategies:
    1. Direct name match
    2. ECO code range match
    3. Variation/alias match
    """
    if not opening_name and not eco:
        return None
    
    normalized = (opening_name or "").lower().replace("-", " ").replace("_", " ")
    eco_code = (eco or "").upper()
    
    # Opening aliases - map common variations to library keys
    OPENING_ALIASES = {
        # Italian Game variations
        "giuoco piano": "italian-game",
        "giuoco pianissimo": "italian-game",
        "italian": "italian-game",
        "two knights": "italian-game",
        "fried liver": "italian-game",
        "evans gambit": "italian-game",
        
        # Sicilian variations
        "sicilian": "sicilian-defense",
        "najdorf": "sicilian-defense",
        "dragon": "sicilian-defense",
        "scheveningen": "sicilian-defense",
        "sveshnikov": "sicilian-defense",
        "kan": "sicilian-defense",
        "taimanov": "sicilian-defense",
        "accelerated dragon": "sicilian-defense",
        
        # Queen's Gambit variations
        "queen's gambit": "queens-gambit",
        "queens gambit": "queens-gambit",
        "qgd": "queens-gambit",
        "qga": "queens-gambit",
        "slav": "queens-gambit",
        "semi slav": "queens-gambit",
        "tarrasch": "queens-gambit",
        
        # London System
        "london": "london-system",
        
        # Caro-Kann variations
        "caro kann": "caro-kann",
        "caro-kann": "caro-kann",
        
        # King's Indian variations
        "king's indian": "kings-indian-defense",
        "kings indian": "kings-indian-defense",
        "kid": "kings-indian-defense",
        
        # Scandinavian
        "scandinavian": "scandinavian-defense",
        "center counter": "scandinavian-defense",
        
        # Nimzowitsch
        "nimzowitsch": "nimzowitsch-defense",
        "nimzo": "nimzowitsch-defense",
    }
    
    # ECO code to opening mapping
    ECO_MAPPING = {
        # Italian Game: C50-C54
        "C50": "italian-game", "C51": "italian-game", "C52": "italian-game",
        "C53": "italian-game", "C54": "italian-game",
        # Also C55-C59 is Two Knights (Italian family)
        "C55": "italian-game", "C56": "italian-game", "C57": "italian-game",
        "C58": "italian-game", "C59": "italian-game",
        
        # Sicilian: B20-B99
        "B20": "sicilian-defense", "B21": "sicilian-defense", "B22": "sicilian-defense",
        "B23": "sicilian-defense", "B24": "sicilian-defense", "B25": "sicilian-defense",
        "B26": "sicilian-defense", "B27": "sicilian-defense", "B28": "sicilian-defense",
        "B29": "sicilian-defense", "B30": "sicilian-defense", "B31": "sicilian-defense",
        "B32": "sicilian-defense", "B33": "sicilian-defense", "B34": "sicilian-defense",
        "B35": "sicilian-defense", "B36": "sicilian-defense", "B37": "sicilian-defense",
        "B38": "sicilian-defense", "B39": "sicilian-defense", "B40": "sicilian-defense",
        "B41": "sicilian-defense", "B42": "sicilian-defense", "B43": "sicilian-defense",
        "B44": "sicilian-defense", "B45": "sicilian-defense", "B46": "sicilian-defense",
        "B47": "sicilian-defense", "B48": "sicilian-defense", "B49": "sicilian-defense",
        "B50": "sicilian-defense", "B51": "sicilian-defense", "B52": "sicilian-defense",
        "B53": "sicilian-defense", "B54": "sicilian-defense", "B55": "sicilian-defense",
        "B56": "sicilian-defense", "B57": "sicilian-defense", "B58": "sicilian-defense",
        "B59": "sicilian-defense", "B60": "sicilian-defense",
        
        # Queen's Gambit: D00-D69
        "D00": "queens-gambit", "D01": "queens-gambit", "D02": "queens-gambit",
        "D03": "queens-gambit", "D04": "queens-gambit", "D05": "queens-gambit",
        "D06": "queens-gambit", "D07": "queens-gambit", "D08": "queens-gambit",
        "D09": "queens-gambit", "D10": "queens-gambit", "D11": "queens-gambit",
        "D12": "queens-gambit", "D13": "queens-gambit", "D14": "queens-gambit",
        "D15": "queens-gambit", "D16": "queens-gambit", "D17": "queens-gambit",
        "D30": "queens-gambit", "D31": "queens-gambit", "D32": "queens-gambit",
        "D33": "queens-gambit", "D34": "queens-gambit", "D35": "queens-gambit",
        "D36": "queens-gambit", "D37": "queens-gambit", "D38": "queens-gambit",
        "D39": "queens-gambit", "D40": "queens-gambit", "D41": "queens-gambit",
        "D42": "queens-gambit", "D43": "queens-gambit", "D44": "queens-gambit",
        "D45": "queens-gambit", "D46": "queens-gambit", "D47": "queens-gambit",
        
        # Caro-Kann: B10-B19
        "B10": "caro-kann", "B11": "caro-kann", "B12": "caro-kann",
        "B13": "caro-kann", "B14": "caro-kann", "B15": "caro-kann",
        "B16": "caro-kann", "B17": "caro-kann", "B18": "caro-kann", "B19": "caro-kann",
        
        # King's Indian: E60-E99
        "E60": "kings-indian-defense", "E61": "kings-indian-defense",
        "E62": "kings-indian-defense", "E63": "kings-indian-defense",
        "E64": "kings-indian-defense", "E65": "kings-indian-defense",
        "E66": "kings-indian-defense", "E67": "kings-indian-defense",
        "E68": "kings-indian-defense", "E69": "kings-indian-defense",
        "E70": "kings-indian-defense", "E71": "kings-indian-defense",
        "E72": "kings-indian-defense", "E73": "kings-indian-defense",
        "E74": "kings-indian-defense", "E75": "kings-indian-defense",
        "E76": "kings-indian-defense", "E77": "kings-indian-defense",
        "E78": "kings-indian-defense", "E79": "kings-indian-defense",
        "E80": "kings-indian-defense", "E81": "kings-indian-defense",
        "E82": "kings-indian-defense", "E83": "kings-indian-defense",
        "E84": "kings-indian-defense", "E85": "kings-indian-defense",
        "E86": "kings-indian-defense", "E87": "kings-indian-defense",
        "E88": "kings-indian-defense", "E89": "kings-indian-defense",
        "E90": "kings-indian-defense", "E91": "kings-indian-defense",
        "E92": "kings-indian-defense", "E93": "kings-indian-defense",
        "E94": "kings-indian-defense", "E95": "kings-indian-defense",
        "E96": "kings-indian-defense", "E97": "kings-indian-defense",
        "E98": "kings-indian-defense", "E99": "kings-indian-defense",
        
        # Scandinavian: B01
        "B01": "scandinavian-defense",
        
        # Nimzowitsch: B00
        "B00": "nimzowitsch-defense",
    }
    
    # 1. Try ECO code first (most reliable)
    if eco_code and eco_code in ECO_MAPPING:
        return ECO_MAPPING[eco_code]
    
    # 2. Try alias matching
    for alias, key in OPENING_ALIASES.items():
        if alias in normalized:
            return key
    
    # 3. Try direct name match with library
    for key, data in OPENING_DATABASE.items():
        lib_name = data["name"].lower()
        if lib_name in normalized or normalized in lib_name:
            return key
    
    return None


async def get_user_opening_repertoire(db, user_id: str) -> Dict:
    """
    Get user's opening repertoire with stats from their games.
    """
    from opening_trainer_service import get_user_opening_stats
    
    # Get user's actual game stats
    user_stats = await get_user_opening_stats(db, user_id)
    
    # Get user progress on library openings
    progress_records = await db.opening_learning_progress.find(
        {"user_id": user_id}
    ).to_list(100)
    progress_map = {p["opening_key"]: p for p in progress_records}
    
    # Build repertoire
    white_openings = []
    black_openings = []
    
    # Add openings from user's games
    for stat in user_stats:
        opening_name = stat.get("name", "")
        opening_key = match_opening_to_library(opening_name)
        
        entry = {
            "name": opening_name,
            "games_played": stat.get("games_played", 0),
            "win_rate": stat.get("win_rate", 0),
            "avg_accuracy": stat.get("avg_accuracy", 0),
            "in_library": opening_key is not None,
            "library_key": opening_key,
            "learning_progress": progress_map.get(opening_key, {}).get("main_line_progress", 0) if opening_key else 0,
            "traps_learned": progress_map.get(opening_key, {}).get("traps_learned", []) if opening_key else []
        }
        
        # Determine color based on library or guess
        if opening_key:
            color = OPENING_DATABASE[opening_key]["color"]
        else:
            # Guess based on common opening names
            color = "white" if any(w in opening_name.lower() for w in ["italian", "london", "queen's gambit", "ruy lopez", "scotch"]) else "black"
        
        if color == "white":
            white_openings.append(entry)
        else:
            black_openings.append(entry)
    
    # Add recommended openings not yet played
    recommended_white = []
    recommended_black = []
    
    played_keys = {match_opening_to_library(s.get("name", "")) for s in user_stats}
    
    for key, data in OPENING_DATABASE.items():
        if key not in played_keys:
            rec = {
                "key": key,
                "name": data["name"],
                "description": data["description"],
                "reason": "Popular and instructive opening"
            }
            if data["color"] == "white":
                recommended_white.append(rec)
            else:
                recommended_black.append(rec)
    
    return {
        "white_repertoire": sorted(white_openings, key=lambda x: -x["games_played"]),
        "black_repertoire": sorted(black_openings, key=lambda x: -x["games_played"]),
        "recommended_white": recommended_white[:3],
        "recommended_black": recommended_black[:3],
        "total_openings_played": len(user_stats),
        "library_openings_available": len(OPENING_DATABASE)
    }


async def get_opening_lesson(db, user_id: str, opening_key: str) -> Optional[Dict]:
    """
    Get a full opening lesson with user's specific mistakes.
    """
    opening = get_opening_data(opening_key)
    if not opening:
        return None
    
    # Get user's stats in this opening
    from opening_trainer_service import get_user_opening_stats
    user_stats = await get_user_opening_stats(db, user_id)
    
    user_opening_stats = None
    for stat in user_stats:
        if match_opening_to_library(stat.get("name", "")) == opening_key:
            user_opening_stats = stat
            break
    
    # Get user's mistakes in this opening from their games
    user_mistakes = []
    if user_opening_stats:
        # Find games with this opening
        games = await db.games.find({
            "user_id": user_id,
            "$or": [
                {"opening": {"$regex": opening["name"], "$options": "i"}},
                {"opening_name": {"$regex": opening["name"], "$options": "i"}}
            ]
        }, {"_id": 0, "game_id": 1}).limit(10).to_list(10)
        
        game_ids = [g["game_id"] for g in games]
        
        # Get mistakes from these games
        for game_id in game_ids[:5]:
            analysis = await db.games_analysis.find_one(
                {"game_id": game_id},
                {"_id": 0, "stockfish_analysis": 1}
            )
            if analysis:
                moves = analysis.get("stockfish_analysis", {}).get("move_evaluations", [])
                for m in moves[:15]:  # Opening moves only
                    if abs(m.get("cp_loss", 0)) >= 50:
                        user_mistakes.append({
                            "game_id": game_id,
                            "move_number": m.get("move_number"),
                            "your_move": m.get("move"),
                            "best_move": m.get("best_move"),
                            "cp_loss": m.get("cp_loss")
                        })
    
    # Get learning progress
    progress = await db.opening_learning_progress.find_one(
        {"user_id": user_id, "opening_key": opening_key}
    )
    
    return {
        "opening": opening,
        "user_stats": user_opening_stats,
        "user_mistakes": user_mistakes[:5],
        "learning_progress": {
            "main_line_progress": progress.get("main_line_progress", 0) if progress else 0,
            "traps_learned": progress.get("traps_learned", []) if progress else [],
            "times_practiced": progress.get("times_practiced", 0) if progress else 0,
            "mastery_level": progress.get("mastery_level", "unknown") if progress else "unknown"
        }
    }


async def update_learning_progress(
    db, 
    user_id: str, 
    opening_key: str, 
    main_line_progress: int = None,
    trap_learned: str = None,
    practiced: bool = False
) -> Dict:
    """Update user's learning progress on an opening."""
    
    update = {"$set": {"last_practiced": datetime.now(timezone.utc)}}
    
    if main_line_progress is not None:
        update["$set"]["main_line_progress"] = main_line_progress
    
    if practiced:
        update["$inc"] = {"times_practiced": 1}
    
    if trap_learned:
        update["$addToSet"] = {"traps_learned": trap_learned}
    
    await db.opening_learning_progress.update_one(
        {"user_id": user_id, "opening_key": opening_key},
        {
            **update,
            "$setOnInsert": {
                "user_id": user_id,
                "opening_key": opening_key,
                "created_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )
    
    # Recalculate mastery level
    progress = await db.opening_learning_progress.find_one(
        {"user_id": user_id, "opening_key": opening_key}
    )
    
    opening = get_opening_data(opening_key)
    total_moves = len(opening["main_line"]) if opening else 10
    
    moves_known = progress.get("main_line_progress", 0)
    times_practiced = progress.get("times_practiced", 0)
    
    if moves_known >= total_moves and times_practiced >= 5:
        mastery = "mastered"
    elif moves_known >= total_moves * 0.7 and times_practiced >= 3:
        mastery = "comfortable"
    elif moves_known >= total_moves * 0.5 or times_practiced >= 2:
        mastery = "practiced"
    elif moves_known > 0 or times_practiced > 0:
        mastery = "learning"
    else:
        mastery = "unknown"
    
    await db.opening_learning_progress.update_one(
        {"user_id": user_id, "opening_key": opening_key},
        {"$set": {"mastery_level": mastery}}
    )
    
    return {"mastery_level": mastery}
