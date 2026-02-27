"""
Behavioral Analysis Package

Modular architecture for behavioral coaching intelligence.

Modules:
- feature_extractor: Raw feature extraction from game data
- context_enricher: Contextual pattern intelligence
- narrative_engine: Deterministic headline/insight generation
- mission_picker: Root cause matched missions
- stagnation_detector: Stuck-in-loop detection
- scoring_engine: Feature to score conversion
"""

from .feature_extractor import (
    BehaviorFeatures,
    extract_behavior_features,
    detect_phase,
    NEGATIVE_LEAK_TAGS,
    POSITIVE_LEAK_TAGS,
)

from .context_enricher import (
    enrich_pattern_context,
    get_root_cause_description,
    get_root_cause_label,
)

from .narrative_engine import (
    build_behavioral_narrative,
)

from .mission_picker import (
    Mission,
    choose_mission,
)

from .scoring_engine import (
    ScoreItem,
    score_behavior,
    labelize,
)

from .stagnation_detector import (
    detect_stagnation,
    store_behavioral_report,
)

__all__ = [
    # Feature extraction
    "BehaviorFeatures",
    "extract_behavior_features",
    "detect_phase",
    "NEGATIVE_LEAK_TAGS",
    "POSITIVE_LEAK_TAGS",
    
    # Context enrichment
    "enrich_pattern_context",
    "get_root_cause_description",
    "get_root_cause_label",
    
    # Narrative
    "build_behavioral_narrative",
    
    # Mission
    "Mission",
    "choose_mission",
    
    # Scoring
    "ScoreItem",
    "score_behavior",
    "labelize",
    
    # Stagnation
    "detect_stagnation",
    "store_behavioral_report",
]
