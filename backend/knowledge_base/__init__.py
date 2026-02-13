"""
ChessGuru Canon - Knowledge Base

This module provides structured chess knowledge for RAG-powered coaching.
All knowledge is deterministic, structured, and designed for retrieval.

Components:
- pawn_structures.py - 10 core pawn structure patterns
- strategic_imbalances.py - 10 key middlegame imbalances
"""

from .pawn_structures import (
    PAWN_STRUCTURES,
    get_structure_by_id,
    get_all_structure_ids,
    match_structure_from_analysis
)

from .strategic_imbalances import (
    STRATEGIC_IMBALANCES,
    get_imbalance_by_id,
    get_all_imbalance_ids,
    detect_imbalances_from_themes
)

__all__ = [
    'PAWN_STRUCTURES',
    'STRATEGIC_IMBALANCES',
    'get_structure_by_id',
    'get_all_structure_ids',
    'match_structure_from_analysis',
    'get_imbalance_by_id',
    'get_all_imbalance_ids',
    'detect_imbalances_from_themes'
]
