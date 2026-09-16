"""Rollout contract for the Personalized Opening Coach V1.

Correctness fixes (honest copy, color alignment, canonical evidence reads)
remain active for everyone. New engine acceptance, branch evidence writes and
personalized recurring-decision recommendations are default-off until staging
and a bounded cohort are explicitly enabled.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional


FEATURE_FLAG = "PERSONALIZED_OPENING_COACH_V1_ENABLED"
SCHEMA_VERSION = "personalized_opening_coach.v1"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def personalized_opening_coach_enabled(
    env: Optional[Mapping[str, str]] = None,
) -> bool:
    source = os.environ if env is None else env
    return str(source.get(FEATURE_FLAG, "false")).strip().lower() in _TRUE_VALUES
