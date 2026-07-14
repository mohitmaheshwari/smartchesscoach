"""Drift guard: every opening the review-caption book names must map into the
curriculum (Q3, 2026-07-14).

The repo has TWO opening recognizers by design — decryption_voice/opening_book
(66 curated lines with authored captions, fires often, used by review
captions) and opening_lookup (curriculum setup_order matching, strict gate,
used by PWC teaching/progress). Measured on 60 real games they never produce
CONFLICTING names (the curriculum gate rarely fires where the book does), but
nothing stopped the book's names drifting away from curriculum keys. This
test pins the mapping: every book name must resolve to a curriculum key by
exact match, prefix (book names may be finer-grained sub-variations), or the
explicit alias table. Book-only openings the curriculum genuinely lacks are
listed in STANDALONE — consciously, so a new unmapped name fails loudly.

Run: python backend/tests/test_opening_name_alignment.py   (or pytest)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Book sub-variation name -> curriculum key. Only for names where the prefix
# rule can't see the parent (spelling differs).
ALIASES = {
    "sicilian": "sicilian_defense",
    "sicilian_open": "sicilian_defense",
    "sicilian_bowdler": "sicilian_defense_bowdler_attac",
    "closed_sicilian": "sicilian_defense",
    "alapin_sicilian": "sicilian_defense",
    "sicilian_najdorf_or_classical": "sicilian_najdorf",
    "caro_kann_advance": "caro_kann_defense_advance_vari",
    "caro_kann_exchange": "caro_kann_defense_exchange_var",
    "caro_kann_main": "caro_kann_defense",
    "caro_kann_classical_main": "caro_kann_defense",
    "french_main": "french_defense",
    "french_advance": "french_defense",
    "french_classical": "french_defense",
    "french_exchange": "french_defense",
    "scandinavian": "scandinavian_defense",
    "scandinavian_main": "scandinavian_defense",
    "scandinavian_modern": "scandinavian_defense",
    "scandinavian_ilundain": "scandinavian_defense",
    "scandinavian_bronstein_larsen": "scandinavian_defense",
    "scandinavian_mieses_kotroc": "scandinavian_defense_mieses_ko",
    "scandinavian_mieses_kotroc_c6": "scandinavian_defense_mieses_ko",
    "scandinavian_mieses_kotroc_d4": "scandinavian_defense_mieses_ko",
    "scandinavian_mieses_kotroc_nf3": "scandinavian_defense_mieses_ko",
    "italian_giuoco_piano": "italian_game",
    "italian_two_knights": "italian_game",
    "petrov_main": "petrov_defense",
    "kings_indian": "kings_indian_defense",
    "kings_indian_main": "kings_indian_defense",
    "queens_gambit_declined": "queens_gambit",
    "queens_gambit_accepted": "queens_gambit_accepted_3_nf3",
    "slav_main_dxc4": "slav_defense",
    "centre_game": "center_game",
}

# Book-only openings the curriculum does not teach yet. Additions here are a
# CONSCIOUS decision (the review caption will name an opening the teaching
# system can't follow up on) — prefer extending the curriculum instead.
STANDALONE = {
    "catalan",
    "evans_gambit",
    "indian_defenses",
    "kings_fianchetto_opening",
    "larsens_opening",
    "pirc_or_modern_setup",
    "queens_pawn",
    "reti",
}


def _load():
    from services.decryption_voice.opening_book import _OPENINGS
    cur_path = os.path.join(os.path.dirname(__file__), "..", "data", "opening_curriculum.json")
    cur = json.load(open(cur_path, encoding="utf-8"))
    return _OPENINGS, set(cur.keys())


def _resolve(name, curkeys):
    if name in curkeys:
        return name
    for k in curkeys:  # book name is a finer-grained child of a curriculum key
        if name.startswith(k):
            return k
    if name in ALIASES:
        return ALIASES[name]
    if name in STANDALONE:
        return "__standalone__"
    return None


def test_every_book_name_maps_into_curriculum():
    openings, curkeys = _load()
    unmapped = sorted({e["name"] for e in openings} - {None}
                      ) and [n for n in sorted({e["name"] for e in openings})
                             if _resolve(n, curkeys) is None]
    assert not unmapped, (
        f"Book opening names with NO curriculum mapping: {unmapped}. "
        "Extend the curriculum, add an ALIAS, or consciously add to STANDALONE.")


def test_alias_targets_exist():
    _, curkeys = _load()
    bad = sorted(v for v in ALIASES.values() if v not in curkeys)
    assert not bad, f"ALIASES point at nonexistent curriculum keys: {bad}"


def test_standalone_not_secretly_mapped():
    """If the curriculum gains one of these, remove it from STANDALONE so the
    mapping becomes real instead of silently ignored."""
    _, curkeys = _load()
    now_mappable = sorted(n for n in STANDALONE
                          if n in curkeys or any(n.startswith(k) for k in curkeys))
    assert not now_mappable, (
        f"STANDALONE entries now have curriculum homes: {now_mappable} — "
        "remove them from STANDALONE.")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
