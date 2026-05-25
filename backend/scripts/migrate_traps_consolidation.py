"""
migrate_traps_consolidation.py — one-shot migration to make
data/traps.json the single source of truth for trap detection.

Background: trap data lives in two parallel files
  - data/traps.json (43 traps, kebab-case opening keys, consumed by
    services/trap_recognition)
  - data/coaching/opening_theory_tree.json (each opening has a `traps`
    array, 22 traps total). Not consumed by trap_recognition — pure
    drift hazard.

Of the 22 traps in theory_tree:
  - 11 are duplicates of traps.json entries (potential drift)
  - 11 are ORPHANS — detection-ready data sitting unused

This migration:
  1. For each orphan, builds a traps.json-shaped dict by mapping
       theory_tree fields → traps.json fields:
       name              → name
       explanation       → description (with `refutation` appended)
       setup_moves       → setup_moves (verbatim)
       full_line[len(setup_moves):] → trap_line steps
                                       (per-step explanation = '')
       trap_for          → trap_color
       difficulty        → difficulty
       category          → result_type ("trap" → 'mate' or 'wins_material'
                          based on explanation text; "warning" → 'wins_material')
       success_message: synthesised from name + 'punishment lands'
     and appends it to traps.json under the kebab-case opening key.

  2. Strips all `traps` arrays from opening_theory_tree.json (removes
     both the 11 orphans now migrated AND the 11 duplicates).

Idempotent: re-running checks both files; only adds traps that are
missing from traps.json.
"""
import json
from pathlib import Path
from typing import Any, Dict, List


# Manual mapping: theory_tree opening_key → traps.json opening_key
# (theory_tree uses snake_case, traps.json uses kebab-case).
_OPENING_KEY_MAP = {
    "italian_game":         "italian-game",
    "sicilian_defense":     "sicilian-defense",
    "queens_gambit":        "queens-gambit",
    "london_system":        "london-system",
    "caro_kann":            "caro-kann",
    "ruy_lopez":            "ruy-lopez",
    "philidor_defense":     "philidor-defense",
    "petrov_defense":       "petrov-defense",
    "scandinavian_defense": "scandinavian-defense",
    "qgd":                  "queens-gambit",         # QGD → queens-gambit bucket
    "budapest_gambit":      "budapest-gambit",
    "dutch_defense":        "dutch-defense",
    "french_defense":       "french-defense",
    "slav_defense":         "slav-defense",
    "vienna_game":          "vienna-game",
    "kings_indian_defense": "kings-indian-defense",
    "grunfeld_defense":     "grunfeld-defense",
    "nimzo_indian":         "nimzo-indian",
    "queens_indian":        "queens-indian",
    "benoni_defense":       "benoni-defense",
    "scotch_game":          "scotch",
    "four_knights":         "four-knights",
}


def _result_type_from_category(category: str, explanation: str) -> str:
    """Map theory_tree category → traps.json result_type. theory_tree
    uses 'trap' / 'warning' / 'gambit'; traps.json uses 'wins_material'
    / 'mate' / 'attack' / 'positional_edge'. Use explanation text to
    detect mate-ending traps."""
    expl = (explanation or "").lower()
    if any(t in expl for t in ("mate", "checkmate", "#")):
        return "mate"
    if category == "warning":
        return "wins_material"
    return "wins_material"


def _build_trap_line(setup_moves: List[str], full_line: List[str]) -> List[Dict[str, str]]:
    """trap_line = full_line minus the setup_moves prefix, each step
    wrapped in {move, explanation: ''}. theory_tree only has one
    explanation per trap — leave per-step empty."""
    if not full_line or not setup_moves:
        return []
    if full_line[:len(setup_moves)] != setup_moves:
        # Defensive: if full_line doesn't start with setup_moves verbatim,
        # treat the whole full_line as trap_line. This shouldn't happen
        # for our 11 orphans but is safer than failing silently.
        return [{"move": m, "explanation": ""} for m in full_line]
    return [{"move": m, "explanation": ""} for m in full_line[len(setup_moves):]]


def _convert_orphan(tree_trap: Dict[str, Any], opening_key: str) -> Dict[str, Any]:
    """Convert a theory_tree trap dict → traps.json schema."""
    name = (tree_trap.get("name") or "").strip()
    expl = (tree_trap.get("explanation") or "").strip()
    refutation = (tree_trap.get("refutation") or "").strip()
    description = expl
    if refutation:
        description = f"{expl} {refutation}".strip()
    setup_moves = list(tree_trap.get("setup_moves") or [])
    full_line = list(tree_trap.get("full_line") or [])
    trap_line = _build_trap_line(setup_moves, full_line)
    trap_color = (tree_trap.get("trap_for") or "").lower() or None
    result_type = _result_type_from_category(
        tree_trap.get("category") or "trap",
        expl,
    )
    difficulty = tree_trap.get("difficulty") or "intermediate"
    success_message = (
        f"{name} — the punishment lands. {expl[:80]}..." if expl else f"{name} succeeds."
    )
    return {
        "name": name,
        "description": description,
        "setup_moves": setup_moves,
        "trap_line": trap_line,
        "success_message": success_message,
        "result_type": result_type,
        "difficulty": difficulty,
        "trap_color": trap_color,
    }


def main() -> None:
    repo = Path(__file__).parent.parent
    traps_path = repo / "data" / "traps.json"
    tree_path = repo / "data" / "coaching" / "opening_theory_tree.json"

    with open(traps_path, encoding="utf-8") as f:
        traps_data = json.load(f)
    with open(tree_path, encoding="utf-8") as f:
        tree_data = json.load(f)

    # Names already in traps.json (lowercase for case-insensitive match)
    existing_names = set()
    for op_key, op_traps in traps_data.items():
        if isinstance(op_traps, list):
            for t in op_traps:
                if (t.get("name") or "").strip():
                    existing_names.add(t["name"].strip().lower())

    # Collect orphans from theory_tree
    added = 0
    skipped_dup = 0
    skipped_no_mapping = []
    skipped_no_trapline = []
    for tree_op_key, tree_op in tree_data.items():
        if tree_op_key == "_meta":
            continue
        if not isinstance(tree_op, dict):
            continue
        for tree_trap in (tree_op.get("traps") or []):
            tname = (tree_trap.get("name") or "").strip()
            if not tname:
                continue
            if tname.lower() in existing_names:
                skipped_dup += 1
                continue
            target_op = _OPENING_KEY_MAP.get(tree_op_key)
            if not target_op:
                skipped_no_mapping.append((tree_op_key, tname))
                continue
            converted = _convert_orphan(tree_trap, target_op)
            if not converted["trap_line"]:
                skipped_no_trapline.append((tree_op_key, tname))
                continue
            traps_data.setdefault(target_op, []).append(converted)
            existing_names.add(tname.lower())
            added += 1
            print(f"  + {target_op}: {tname} (trap_color={converted['trap_color']}, "
                  f"{len(converted['setup_moves'])} setup + {len(converted['trap_line'])} trap-line steps)")

    # Strip traps[] arrays from theory_tree (both duplicates and now-migrated orphans)
    removed_arrays = 0
    for tree_op_key, tree_op in tree_data.items():
        if isinstance(tree_op, dict) and "traps" in tree_op:
            tree_op.pop("traps")
            removed_arrays += 1

    # Write both files
    with open(traps_path, "w", encoding="utf-8") as f:
        json.dump(traps_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print()
    print(f"Added to traps.json    : {added}")
    print(f"Skipped (already there): {skipped_dup}")
    print(f"Skipped (no mapping)   : {len(skipped_no_mapping)}")
    for op, n in skipped_no_mapping:
        print(f"    {op}: {n}")
    print(f"Skipped (empty trap_line): {len(skipped_no_trapline)}")
    for op, n in skipped_no_trapline:
        print(f"    {op}: {n}")
    print(f"Stripped traps[] arrays from theory_tree openings: {removed_arrays}")


if __name__ == "__main__":
    main()
