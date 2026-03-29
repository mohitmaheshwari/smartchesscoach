import sys

sys.path.insert(0, '/app/backend')

from services.verified_opening_traps import (
    get_verified_trap_by_name,
    select_preferred_trap,
    validate_verified_trap_registry,
)


def test_verified_trap_registry_is_legal():
    issues = validate_verified_trap_registry()
    assert issues == [], issues


def test_siberian_trap_matches_exact_sicilian_setup_only():
    trap = select_preferred_trap(
        'sicilian_defense',
        ['e4', 'c5', 'Nf3', 'e6', 'd4', 'cxd4', 'Nxd4', 'Nf6', 'Nc3', 'Bb4']
    )

    assert trap is not None
    assert trap.name == 'Siberian Trap'
    assert trap.trap_move == 'Qa5'


def test_siberian_trap_not_offered_for_other_sicilian_branch():
    trap = select_preferred_trap(
        'sicilian_defense',
        ['e4', 'c5', 'Nf3', 'd6', 'd4', 'cxd4', 'Nxd4', 'Nf6', 'Nc3', 'a6']
    )

    assert trap is None


def test_elephant_trap_still_available_for_qgd_line():
    trap = select_preferred_trap(
        'queens_gambit',
        ['d4', 'd5', 'c4', 'e6', 'Nc3', 'Nf6', 'Bg5', 'Nbd7', 'cxd5', 'exd5', 'Nxd5', 'Nxd5', 'Bxd8']
    )

    assert trap is not None
    assert trap.name == 'Elephant Trap'


def test_verified_trap_lookup_by_name_prefers_canonical_siberian():
    trap = get_verified_trap_by_name('sicilian_defense', 'Siberian Trap')

    assert trap is not None
    assert trap.opening_name == 'Sicilian Defense'
    assert trap.variation_name == 'Open Sicilian ...Bb4 line'