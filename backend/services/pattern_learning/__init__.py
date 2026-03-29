"""
Self-Learning Pattern Recognition System

This module implements an AI-powered system that learns from user feedback
to improve chess mistake classification over time.

Components:
- FeedbackCollector: Collects and stores user feedback on coach explanations
- PatternLearner: AI that analyzes feedback and generates classification rules
- RuleValidator: Validates new rules against Stockfish before going live
- RuleExecutor: Runs learned rules against positions
- LearningDB: Database operations for the learned rules

The system ensures NO HALLUCINATION by:
1. Using Stockfish as the source of truth for chess facts
2. AI only interprets Stockfish data, never invents tactics
3. All learned rules are validated against engine analysis
4. Cross-user learning: fixes propagate to all users with similar patterns
"""

from .feedback_collector import FeedbackCollector, UserFeedback
from .pattern_learner import PatternLearner, LearnedRule
from .rule_validator import RuleValidator, ValidationResult
from .rule_executor import RuleExecutor, ClassificationResult
from .learning_db import LearningDB
from .auto_correction_service import AutoCorrectionService, get_auto_correction_service

__all__ = [
    'FeedbackCollector',
    'UserFeedback', 
    'PatternLearner',
    'LearnedRule',
    'RuleValidator',
    'ValidationResult',
    'RuleExecutor',
    'ClassificationResult',
    'LearningDB',
    'AutoCorrectionService',
    'get_auto_correction_service'
]
