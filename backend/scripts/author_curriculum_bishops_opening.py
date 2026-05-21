"""Add bishops_opening entry to curriculum (Mohit overnight 2026-05-21).

Bishop's Opening (1.e4 e5 2.Bc4) appeared in 4 of 500 audited games.
Italian-family cousin: aims at f7 immediately, often transposes to
the Italian or Vienna. We teach the canonical setup as white.

Run once:
    docker exec chess-coach-backend python /app/backend/scripts/author_curriculum_bishops_opening.py
"""
import json
import os
import sys

bishops_opening_entry = {
    "name": "Bishop's Opening",
    "color": "white",
    "summary": "1.e4 e5 2.Bc4. Italian-family opening — aim the bishop at f7 immediately. Often transposes to the Italian Game after 3.Nf3. Modern lines also include the Vienna-Anti-Petroff with 2...Nf6 3.d3 or 3.d4.",
    "difficulty": "beginner",
    "setup_order": ["e4", "Bc4", "Nf3", "d3", "Nc3", "O-O"],
    "golden_rules": [
        "Bc4 first, then choose: Nf3 (transposes to Italian) or d3 (Modern Bishop's Opening, slow positional).",
        "Against ...Nf6, d3 (Modern) is solid; 2.Nf3 first transposes to standard Italian Two Knights.",
        "Castle kingside, develop knights to f3 and d2 (or c3) — quiet positional play.",
        "Don't push d4 too early without c3 support."
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea": "Take the center.",
            "next": "Bc4",
            "responses": {
                "e5": {
                    "name": "Open Game",
                    "idea_opponent": "Black mirrors.",
                    "next": "Bc4",
                    "hint": "Aim the bishop at f7 right away.",
                    "right_feedback": "Bc4 — Bishop's Opening. Eyes f7 immediately, before developing the knight.",
                    "wrong_feedback": "In the Bishop's Opening, Bc4 is the defining move — bishop aims at f7 before knights come out. Nf3 first leads to standard Italian (also fine, just different order). Bc4 first leaves you the flexibility of d3 (Modern Bishop's) or Nc3 (Vienna-style).",
                    "responses": {
                        "Nf6": {
                            "name": "Bishop's Opening — Berlin / Modern",
                            "idea_opponent": "Black attacks e4 immediately.",
                            "next": "d3",
                            "hint": "Defend e4 with a pawn — Modern Bishop's Opening setup.",
                            "right_feedback": "d3 — Modern Bishop's Opening. Solid positional play; Nf3 + O-O + Nbd2 next.",
                            "wrong_feedback": "Against 2...Nf6 in the Bishop's Opening, d3 is the modern positional choice — defends e4 and prepares slow development. Nf3 transposes to the Two Knights Defense (Fried Liver territory, sharper). Both sound; d3 if you prefer quiet positional games.",
                            "responses": {}
                        },
                        "Bc5": {
                            "name": "Bishop's Opening → Italian transposition",
                            "idea_opponent": "Black mirrors with Bc5 — typically transposes to Italian.",
                            "next": "Nf3",
                            "right_feedback": "Nf3 — develops, transposes to Italian Giuoco Piano.",
                            "responses": {}
                        }
                    }
                }
            }
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "Slow positional play. Bc4 + d3 + Nf3 + O-O + Nbd2 + Re1. Eventually push c3 + d4 if Black allows.",
            "ideas": [
                "Don't push d4 without c3 support.",
                "Keep the bishop on c4 (or b3 if attacked by ...Na5).",
                "Plan f4 or g4 expansion if Black castles short."
            ]
        },
        "when_ahead": {
            "plan": "Open the center with d4 once supported. Trade pieces if your structure is better.",
            "ideas": ["Push d4 + e5 with c3 support.", "Trade queens if endgame favors you."]
        },
        "when_behind": {
            "plan": "Keep the position closed. The Bishop's Opening is rarely won by Black quickly.",
            "ideas": ["Don't trade the bishop on c4 for the knight.", "Wait for Black to overcommit."]
        }
    },
    "endgame_tips": [
        "The bishop pair (if you keep both) gives an endgame edge — preserve them.",
        "Pawn structures from Bishop's Opening transpositions usually resemble Italian endgames."
    ]
}


def main():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'opening_curriculum.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['bishops_opening'] = bishops_opening_entry
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'Added bishops_opening. Total openings: {len(data)}')


if __name__ == '__main__':
    sys.exit(main())
