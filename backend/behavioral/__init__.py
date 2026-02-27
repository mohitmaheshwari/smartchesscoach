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
- advice_engine: Coach advice rule evaluation
- learning_velocity: Learning speed calculation
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

from .advice_engine import (
    AdviceRule,
    AdviceResult,
    AdviceEngine,
    ADVICE_RULES,
    ADVICE_TEMPLATES,
    LEAK_TO_RULE,
)

from .learning_velocity import (
    LearningVelocityResult,
    compute_learning_velocity,
    compute_compliance_score,
    check_advice_resolution,
    resolve_advice,
    get_consecutive_follows,
    get_active_advice_count,
    archive_lowest_severity_resolved,
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
    
    # Advice Engine
    "AdviceRule",
    "AdviceResult",
    "AdviceEngine",
    "ADVICE_RULES",
    "ADVICE_TEMPLATES",
    "LEAK_TO_RULE",
    
    # Learning Velocity
    "LearningVelocityResult",
    "compute_learning_velocity",
    "compute_compliance_score",
    "check_advice_resolution",
    "resolve_advice",
    "get_consecutive_follows",
    "get_active_advice_count",
    "archive_lowest_severity_resolved",
]
