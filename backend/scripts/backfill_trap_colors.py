"""
backfill_trap_colors.py — one-shot script that fills the `trap_color`
field for every trap in data/traps.json that's missing it.

Why: services/trap_recognition treats trap_color as the SETTER's color
(the one who wins material / mates / punishes). The v88 audit found
that 36 of 41 traps left this blank, which blocks the
victim-side-warning caption (we can't tell who the victim is without
knowing the setter).

The mapping below was derived by reading each trap's `description`
+ `success_message` to identify which color executes the trap. Each
entry is annotated with the phrase that anchored the call.

Idempotent: re-running won't overwrite existing trap_color values.
Only fills entries where trap_color is missing or empty.
"""
import json
from pathlib import Path


TRAP_COLORS = {
    # name → trap_color (the SETTER's color)
    # White punishes / wins / mates
    "Fried Liver Attack":                  ("white", "wins material and exposes Black's king"),
    "Legal's Mate":                        ("white", "Legal's Mate (white delivers mate via queen sac)"),
    "Lolli Variation":                     ("white", "White crashes through with d4"),
    "Wing Gambit":                         ("white", "White sacrifices a flank pawn"),
    "Rubinstein Trap":                     ("white", "white win[s] a pawn via the h7 pin"),
    "Englund Gambit Trap":                 ("white", "Refute the dubious Englund Gambit and trap Black's queen"),
    "Caro-Kann Smothered Mate":            ("white", "Nd6# delivered by white"),
    "King's Indian Bayonet Trap":          ("white", "White has a powerful passed pawn"),
    "Tarrasch Trap (Open Lopez)":          ("white", "White exploits the knight on c5...black loses a piece"),
    "Philidor's Legal Mate":               ("white", "Legal's Mate in the Philidor — white delivers"),
    "Damiano Defense Punishment":          ("white", "White recovers material"),
    "Petroff Marshall Trap":               ("white", "discovered-check queen grab by white"),
    "Cochrane Gambit":                     ("white", "White sacrifices the knight on f7"),
    "Dutch Defense Mate":                  ("white", "Black is too aggressive — white delivers mate"),
    "Opera Game Finale":                   ("white", "Morphy's masterpiece (white)"),
    "French Winawer Poisoned Pawn":        ("white", "White wins material"),
    "French Advance Milner-Barry Gambit":  ("white", "White sacrifices pawns for a strong attack"),
    "Frankenstein-Dracula Variation":      ("white", "white's Qd5 attack in the Vienna"),
    "Grunfeld Exchange Trap":              ("white", "White has a strong passed pawn"),
    "Benoni Snake Trap":                   ("white", "lines for White's pieces"),
    "Halosar Trap":                        ("white", "greed for a pawn costs black the queen"),
    "Tennison Gambit Trap":                ("white", "Bg6+ queen snatch by white"),
    "Monticelli Trap":                     ("white", "white plays Ng5 unleashing tactics"),
    "Kieseritzky Gambit Attack":           ("white", "White sacs a pawn for huge central control"),
    "Mieses Variation":                    ("white", "Scotch line where central pawn power dominates"),
    "Owen's Defense Greek-Gift Trap":      ("white", "White punishes with the Greek-gift sacrifice"),

    # Black punishes / wins / mates
    "Traxler Counterattack":               ("black", "Black's daring counter-trap — king-hunt"),
    "Lasker Trap":                         ("black", "Albin Counter-Gambit underpromotion (black)"),
    "Cambridge Springs Trap":              ("black", "Black wins a piece via the discovered check"),
    "Portuguese Gambit Trap":              ("black", "active piece play for Black"),
    "Noah's Ark Trap":                     ("black", "wins White's light-squared bishop"),
    "Mortimer Trap":                       ("black", "smothered mate delivered by black"),
    "Stafford Gambit Trap":                ("black", "Black sacrifices a pawn for a mating attack"),
    "Kieninger Trap":                      ("black", "Budapest smothered mate by black"),
    "Slav Main Line Trap":                 ("black", "Black wins material with a discovered attack"),
    "Nimzo-Indian Hubner Trap":            ("black", "Hubner — black wins the queen on white's king"),
    "Queen's Indian Bishop Trap":          ("black", "Black wins the light-squared bishop"),
}


def main() -> None:
    path = Path(__file__).parent.parent / "data" / "traps.json"
    with open(path, encoding="utf-8") as f:
        tree = json.load(f)

    filled = 0
    skipped_existing = 0
    not_found_in_map: list = []
    for opening, traps in tree.items():
        if not isinstance(traps, list):
            continue
        for trap in traps:
            name = trap.get("name")
            if not name:
                continue
            if trap.get("trap_color"):
                skipped_existing += 1
                continue
            entry = TRAP_COLORS.get(name)
            if not entry:
                not_found_in_map.append((opening, name))
                continue
            color, why = entry
            trap["trap_color"] = color
            filled += 1
            print(f"  {color:5s} <- {name} ({opening})  // {why}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print()
    print(f"Filled: {filled} traps")
    print(f"Skipped (already had trap_color): {skipped_existing}")
    if not_found_in_map:
        print(f"NOT FOUND IN MAP (manual fix needed):")
        for opening, name in not_found_in_map:
            print(f"  {opening}: {name}")


if __name__ == "__main__":
    main()
