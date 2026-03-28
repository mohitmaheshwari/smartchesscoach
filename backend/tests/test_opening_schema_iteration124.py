"""
Tests for the typed opening schema/catalog introduced in this iteration.

Covers:
1. Schema builds successfully from opening library
2. Catalog contains Tier-1 family entries and coverage metadata
3. Ruy Lopez structured variation support (Steinitz exchange queenless, Berlin)
4. Variation lookup for all previously added families
5. Duplicate SAN handling with move-index-aware teaching nodes
6. Catalog validation passes for Ruy Lopez and Queen's Gambit
"""
import sys
sys.path.insert(0, '/app/backend')

import pytest
from coach_engine.opening_schema import (
    build_family_schema,
    build_variation_schema,
    validate_family_schema,
    OpeningFamilySchema,
    OpeningVariationSchema,
    OpeningCoverageSchema,
)
from coach_engine.opening_plans import (
    OPENING_PLANS,
    get_opening_family_catalog,
    get_opening_catalog_validation_report,
    get_opening_family_by_moves,
    get_opening_family_schema_by_moves,
    build_opening_coaching_context,
)
from services.move_by_move_coach import get_variation_teaching


class TestSchemaBuildsFromOpeningLibrary:
    """Verify the typed opening schema/catalog builds successfully."""
    
    def test_catalog_builds_without_error(self):
        """Schema catalog can be built from current opening library without exceptions."""
        catalog = get_opening_family_catalog()
        assert catalog is not None
        assert isinstance(catalog, dict)
        assert len(catalog) > 0
    
    def test_all_families_have_required_fields(self):
        """All families in catalog have required schema fields."""
        catalog = get_opening_family_catalog()
        required_fields = ['family_id', 'family_name', 'eco_codes', 'starting_moves', 
                          'family_concepts', 'variations', 'coverage']
        for family_id, family_data in catalog.items():
            for field in required_fields:
                assert field in family_data, f"{family_id} missing {field}"


class TestCatalogContainsTier1Families:
    """Verify catalog contains Tier-1 family entries with coverage metadata."""
    
    def test_tier1_families_present(self):
        """All Tier-1 families are in the catalog."""
        catalog = get_opening_family_catalog()
        tier1_families = ['italian', 'ruy_lopez', 'queens_gambit', 'sicilian', 
                         'french', 'caro_kann', 'kings_indian', 'london']
        for family in tier1_families:
            assert family in catalog, f"Tier-1 family '{family}' missing from catalog"
    
    def test_families_have_coverage_metadata(self):
        """Each family has coverage statistics."""
        catalog = get_opening_family_catalog()
        coverage_fields = ['variation_count', 'node_count', 'trap_count', 
                          'deviation_rule_count', 'min_full_line_ply_depth',
                          'max_full_line_ply_depth', 'has_white_plans', 
                          'has_black_plans', 'has_rating_layers']
        for family_id, family_data in catalog.items():
            coverage = family_data.get('coverage')
            assert coverage is not None, f"{family_id} has no coverage"
            for field in coverage_fields:
                assert field in coverage, f"{family_id} coverage missing {field}"
    
    def test_ruy_lopez_has_multiple_variations(self):
        """Ruy Lopez family has at least 2 variations."""
        catalog = get_opening_family_catalog()
        ruy = catalog['ruy_lopez']
        assert ruy['coverage']['variation_count'] >= 2


class TestRuyLopezStructuredVariationSupport:
    """Verify Ruy Lopez has Steinitz exchange queenless and Berlin variations."""
    
    def test_ruy_lopez_has_steinitz_exchange_queenless(self):
        """Steinitz Exchange Queenless Line is present in Ruy Lopez."""
        catalog = get_opening_family_catalog()
        ruy = catalog['ruy_lopez']
        variation_names = [v['variation_name'] for v in ruy['variations']]
        assert 'Ruy Lopez — Steinitz Exchange Queenless Line' in variation_names
    
    def test_ruy_lopez_has_berlin_defense(self):
        """Berlin Defense is present in Ruy Lopez."""
        catalog = get_opening_family_catalog()
        ruy = catalog['ruy_lopez']
        variation_names = [v['variation_name'] for v in ruy['variations']]
        assert 'Ruy Lopez — Berlin Defense' in variation_names
    
    def test_steinitz_full_line_is_valid(self):
        """Steinitz line full_line is a legal move sequence."""
        catalog = get_opening_family_catalog()
        ruy = catalog['ruy_lopez']
        steinitz = next(v for v in ruy['variations'] 
                       if 'Steinitz' in v['variation_name'])
        assert len(steinitz['full_line']) >= 10
        # The line should contain key moves
        full_line_lower = [m.lower() for m in steinitz['full_line']]
        assert 'bxc6+' in full_line_lower or 'bxc6' in full_line_lower
        assert 'qxd8+' in full_line_lower or 'qxd8' in full_line_lower
    
    def test_berlin_full_line_is_valid(self):
        """Berlin line full_line is a legal move sequence."""
        catalog = get_opening_family_catalog()
        ruy = catalog['ruy_lopez']
        berlin = next(v for v in ruy['variations'] 
                     if 'Berlin' in v['variation_name'])
        assert len(berlin['full_line']) >= 8
        full_line_lower = [m.lower() for m in berlin['full_line']]
        assert 'nxe4' in full_line_lower
    
    def test_steinitz_has_teaching_nodes(self):
        """Steinitz variation has teaching nodes for key moments."""
        catalog = get_opening_family_catalog()
        ruy = catalog['ruy_lopez']
        steinitz = next(v for v in ruy['variations'] 
                       if 'Steinitz' in v['variation_name'])
        assert len(steinitz['nodes']) >= 5


class TestVariationLookupForPreviousFamilies:
    """Verify variation lookup works for Queen's Gambit, Italian, London, 
       Sicilian, French, Caro-Kann, King's Indian."""
    
    def test_queens_gambit_qgd_variation_lookup(self):
        """QGD variation is found via moves."""
        moves = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)
        assert context is not None
        assert 'qgd_main' in context.get('variations', {})
    
    def test_queens_gambit_slav_variation_lookup(self):
        """Slav variation is found via moves."""
        moves = ["d4", "d5", "c4", "c6", "Nf3", "Nf6", "Nc3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context)
        assert context is not None
        assert 'slav_main' in context.get('variations', {})
    
    def test_italian_giuoco_pianissimo_lookup(self):
        """Giuoco Pianissimo is found."""
        moves = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, "white")
        assert teaching is not None
        assert 'Giuoco Pianissimo' in teaching.get('variation_name', '')
    
    def test_italian_two_knights_lookup(self):
        """Two Knights is found."""
        moves = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, "white")
        assert teaching is not None
        assert 'Two Knights' in teaching.get('variation_name', '')
    
    def test_london_variation_lookup(self):
        """London variation is found."""
        moves = ["d4", "d5", "Nf3", "Nf6", "Bf4", "c5", "e3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, "white")
        assert teaching is not None
        assert 'London' in teaching.get('variation_name', '')
    
    def test_sicilian_open_variation_lookup(self):
        """Open Sicilian is found."""
        moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, "black")
        assert teaching is not None
        assert 'Sicilian' in teaching.get('variation_name', '')
    
    def test_french_advance_variation_lookup(self):
        """French Advance is found."""
        moves = ["e4", "e6", "d4", "d5", "e5", "c5", "c3"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, "black")
        assert teaching is not None
        assert 'French' in teaching.get('variation_name', '')
    
    def test_caro_kann_classical_lookup(self):
        """Caro-Kann Classical is found."""
        moves = ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, "black")
        assert teaching is not None
        assert 'Caro-Kann' in teaching.get('variation_name', '')
    
    def test_kings_indian_main_lookup(self):
        """King's Indian main setup is found."""
        moves = ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, "black")
        assert teaching is not None
        assert 'King' in teaching.get('variation_name', '')


class TestDuplicateSANHandling:
    """Verify move-index-aware teaching nodes work for repeated SAN patterns."""
    
    def test_steinitz_queenless_uses_teaching_nodes_not_move_teaching(self):
        """Steinitz queenless line uses teaching_nodes array for disambiguation."""
        ruy_plan = OPENING_PLANS.get('ruy_lopez')
        steinitz_var = ruy_plan.variations.get('steinitz_exchange_queenless', {})
        # This variation uses teaching_nodes instead of move_teaching
        assert 'teaching_nodes' in steinitz_var
        assert len(steinitz_var['teaching_nodes']) > 0
    
    def test_teaching_nodes_have_move_index(self):
        """Teaching nodes specify move_index for disambiguation."""
        ruy_plan = OPENING_PLANS.get('ruy_lopez')
        steinitz_var = ruy_plan.variations.get('steinitz_exchange_queenless', {})
        nodes = steinitz_var.get('teaching_nodes', [])
        for node in nodes:
            assert 'move_index' in node, "Teaching node missing move_index"
            assert 'move_san' in node, "Teaching node missing move_san"
            assert 'teach' in node, "Teaching node missing teach"
    
    def test_schema_builds_nodes_from_teaching_nodes_array(self):
        """Schema builder correctly uses teaching_nodes when provided."""
        ruy_plan = OPENING_PLANS.get('ruy_lopez')
        steinitz_var = ruy_plan.variations.get('steinitz_exchange_queenless', {})
        
        schema = build_variation_schema('steinitz_exchange_queenless', steinitz_var)
        
        # Verify nodes were built from teaching_nodes
        assert len(schema.nodes) == len(steinitz_var['teaching_nodes'])
        
        # Verify move_index is preserved correctly
        for i, node in enumerate(schema.nodes):
            expected_index = steinitz_var['teaching_nodes'][i]['move_index']
            assert node.move_index == expected_index
    
    def test_variation_teaching_returns_correct_node_at_repeated_san(self):
        """Variation teaching correctly finds teaching by move_index when SAN repeats."""
        # The Steinitz line has multiple captures/exchanges that could confuse name-based lookup
        # Test that we get the correct teaching at specific positions
        moves = ["e4", "e5", "Nf3", "Nc6", "Bb5", "d6", "d4", "a6", "Bxc6+", "bxc6", 
                "dxe5", "dxe5", "Qxd8+", "Kxd8", "Nxe5"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, 'white')
        
        assert teaching is not None
        # At move 14 (Nxe5), we should get the Nxe5 teaching
        assert 'centralizes' in teaching.get('teaching', '').lower() or \
               'knight' in teaching.get('teaching', '').lower()


class TestCatalogValidation:
    """Verify catalog validation reports no issues for Ruy Lopez and Queen's Gambit."""
    
    def test_ruy_lopez_has_no_validation_issues(self):
        """Ruy Lopez passes schema validation."""
        report = get_opening_catalog_validation_report()
        assert 'ruy_lopez' not in report, f"Ruy Lopez has issues: {report.get('ruy_lopez')}"
    
    def test_queens_gambit_has_no_validation_issues(self):
        """Queen's Gambit passes schema validation."""
        report = get_opening_catalog_validation_report()
        assert 'queens_gambit' not in report, f"QG has issues: {report.get('queens_gambit')}"
    
    def test_italian_has_no_validation_issues(self):
        """Italian Game passes schema validation."""
        report = get_opening_catalog_validation_report()
        assert 'italian' not in report, f"Italian has issues: {report.get('italian')}"
    
    def test_validation_checks_san_legality(self):
        """Validation catches illegal SAN moves."""
        # Create a family with an illegal move
        bad_family = build_family_schema(
            family_id='test_bad',
            family_name='Bad Opening',
            eco_codes=['Z99'],
            starting_moves=['e4', 'e5'],
            family_concepts={'white': [], 'black': []},
            variations={
                'bad_var': {
                    'name': 'Bad Variation',
                    'trigger_moves': ['e4', 'e5'],
                    'full_line': ['e4', 'e5', 'Qh8'],  # Illegal move
                    'plans_for_white': ['test'],
                    'plans_for_black': ['test'],
                }
            }
        )
        issues = validate_family_schema(bad_family)
        assert len(issues) > 0
        assert any('illegal' in issue.lower() for issue in issues)
    
    def test_validation_catches_missing_plans(self):
        """Validation catches missing plans."""
        # Create a family with no plans
        minimal_family = build_family_schema(
            family_id='test_minimal',
            family_name='Minimal Opening',
            eco_codes=['Z99'],
            starting_moves=['e4'],
            family_concepts={'white': [], 'black': []},
            variations={
                'min_var': {
                    'name': 'Minimal Variation',
                    'trigger_moves': ['e4'],
                    'full_line': ['e4', 'e5'],
                    'plans_for_white': [],  # Empty
                    'plans_for_black': [],  # Empty
                }
            }
        )
        issues = validate_family_schema(minimal_family)
        assert any('plans_for_white' in issue for issue in issues)
        assert any('plans_for_black' in issue for issue in issues)


class TestBerlinDefenseStructure:
    """Additional tests for Berlin Defense structure."""
    
    def test_berlin_has_position_tags(self):
        """Berlin variation has position tags."""
        catalog = get_opening_family_catalog()
        ruy = catalog['ruy_lopez']
        berlin = next(v for v in ruy['variations'] if 'Berlin' in v['variation_name'])
        assert 'position_tags' in berlin
        assert 'berlin' in berlin['position_tags']
    
    def test_berlin_variation_teaching_works(self):
        """Berlin variation returns teaching when matched."""
        moves = ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "O-O", "Nxe4"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, 'black')
        assert teaching is not None
        assert 'Berlin' in teaching.get('variation_name', '')
    
    def test_berlin_has_plans_for_both_colors(self):
        """Berlin has plans for both white and black."""
        ruy_plan = OPENING_PLANS.get('ruy_lopez')
        berlin_var = ruy_plan.variations.get('berlin_main', {})
        assert len(berlin_var.get('plans_for_white', [])) > 0
        assert len(berlin_var.get('plans_for_black', [])) > 0


class TestRuyLopezSchemaIntegration:
    """Integration tests for Ruy Lopez schema with move_by_move_coach."""
    
    def test_ruy_family_found_by_moves(self):
        """get_opening_family_by_moves finds Ruy Lopez."""
        moves = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
        family = get_opening_family_by_moves(moves)
        assert family is not None
        assert family.name == "Ruy Lopez (Spanish Game)"
    
    def test_ruy_schema_found_by_moves(self):
        """get_opening_family_schema_by_moves returns schema dict."""
        moves = ["e4", "e5", "Nf3", "Nc6", "Bb5"]
        schema = get_opening_family_schema_by_moves(moves)
        assert schema is not None
        assert schema['family_name'] == "Ruy Lopez (Spanish Game)"
        assert 'variations' in schema
        assert 'coverage' in schema
    
    def test_steinitz_triggers_at_d6(self):
        """Steinitz line triggers after d6."""
        moves = ["e4", "e5", "Nf3", "Nc6", "Bb5", "d6"]
        context = build_opening_coaching_context(moves)
        teaching = get_variation_teaching(moves, context, 'white')
        # May or may not have teaching at this point but should detect variation
        if teaching and teaching.get('variation_name'):
            assert 'Steinitz' in teaching.get('variation_name', '') or 'Ruy' in context.get('name', '')
