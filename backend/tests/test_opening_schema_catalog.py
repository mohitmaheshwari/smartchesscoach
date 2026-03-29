import sys

sys.path.insert(0, '/app/backend')

from coach_engine.opening_plans import (
    build_opening_coaching_context,
    get_opening_catalog_validation_report,
    get_opening_family_catalog,
)
from services.move_by_move_coach import get_variation_teaching


def test_catalog_contains_critical_families():
    catalog = get_opening_family_catalog()

    assert 'ruy_lopez' in catalog
    assert 'queens_gambit' in catalog
    assert 'sicilian' in catalog


def test_ruy_lopez_family_has_typed_variations_and_coverage():
    catalog = get_opening_family_catalog()
    ruy = catalog['ruy_lopez']

    assert ruy['coverage']['variation_count'] >= 2
    variation_names = {variation['variation_name'] for variation in ruy['variations']}
    assert 'Ruy Lopez — Steinitz Exchange Queenless Line' in variation_names
    assert 'Ruy Lopez — Berlin Defense' in variation_names


def test_ruy_steinitz_exchange_line_gets_variation_teaching():
    moves = ["e4", "e5", "Nf3", "Nc6", "Bb5", "d6", "d4", "a6", "Bxc6+", "bxc6", "dxe5", "dxe5", "Qxd8+", "Kxd8", "Nxe5"]
    context = build_opening_coaching_context(moves)
    teaching = get_variation_teaching(moves, context, 'white')

    assert context is not None
    assert teaching is not None
    assert teaching['variation_name'] == 'Ruy Lopez — Steinitz Exchange Queenless Line'
    assert 'queenless middlegame' in teaching['teaching'].lower() or 'centralizes the knight' in teaching['teaching'].lower()


def test_catalog_validation_report_has_no_current_issues_for_ruy_or_qg():
    report = get_opening_catalog_validation_report()

    assert 'ruy_lopez' not in report
    assert 'queens_gambit' not in report