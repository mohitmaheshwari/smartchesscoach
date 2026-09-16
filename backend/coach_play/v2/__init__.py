"""Default-off Play with Coach V2 contracts and shadow policy tools."""

from .contracts import (
    CandidateFocus,
    CandidateNovelty,
    CandidateTiming,
    CandidateUrgency,
    CoachingCandidate,
)
from .shadow_conductor import (
    SHADOW_POLICIES,
    SHADOW_POLICY_VERSION,
    SHADOW_SCHEMA_VERSION,
    UNIFIED_V1_ADAPTER_VERSION,
    build_shadow_packet,
    build_shadow_packet_from_unified_response,
    candidate_from_unified_decision,
)

__all__ = [
    "CandidateFocus",
    "CandidateNovelty",
    "CandidateTiming",
    "CandidateUrgency",
    "CoachingCandidate",
    "SHADOW_POLICIES",
    "SHADOW_POLICY_VERSION",
    "SHADOW_SCHEMA_VERSION",
    "UNIFIED_V1_ADAPTER_VERSION",
    "build_shadow_packet",
    "build_shadow_packet_from_unified_response",
    "candidate_from_unified_decision",
]
