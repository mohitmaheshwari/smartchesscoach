/**
 * coachFlow/types.js — Shared types and constants for the coaching interaction system.
 *
 * States, pending move model, coaching moment model, clock states.
 */

// ─── Interaction States ─────────────────────────────────────────

export const INTERACTION_STATES = {
  IDLE: "idle",
  PENDING_USER_MOVE: "pending_user_move",
  THINKING_HOLD: "thinking_hold",
  CRITICAL_HOLD: "critical_hold",
  AWAITING_CLOCK_COMMIT: "awaiting_clock_commit",
  COMMITTING_MOVE: "committing_move",
  COACH_TURN: "coach_turn",
  GAME_OVER: "game_over",
};

// ─── Clock Visual States ────────────────────────────────────────

export const CLOCK_STATES = {
  NORMAL: "normal",
  HOLD_LOCKED: "hold_locked",
  HOLD_READY: "hold_ready",
  DISABLED: "disabled",
};

// ─── Severity Levels ────────────────────────────────────────────

export const SEVERITY = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
};

// ─── Message Types ──────────────────────────────────────────────

export const MESSAGE_TYPES = {
  CRITICAL_INTERRUPT: "critical_interrupt",
  PATTERN_REPEAT: "pattern_repeat",
  TURNING_POINT: "turning_point",
  REINFORCEMENT: "reinforcement",
  OPENING_PRINCIPLE: "opening_principle",
  CONSEQUENCE_WARNING: "consequence_warning",
  COACH_MOVE_EXPLANATION: "coach_move_explanation",
  ENDGAME_CONVERSION: "endgame_conversion",
};

// ─── Eval Window ────────────────────────────────────────────────

export const EVAL_WINDOW_MS = 400;

// ─── Factory functions ──────────────────────────────────────────

export function createPendingMove({ san, uci, from, to, promotion, fenBefore, fenAfterPreview }) {
  return {
    san,
    uci,
    from,
    to,
    promotion: promotion || null,
    fenBefore,
    fenAfterPreview,
    createdAt: Date.now(),
  };
}

export function createTimelineItem({ moveIndex, moveSan, messageType, severity, text, conceptKey }) {
  return {
    id: `tl_${moveIndex}_${Date.now()}`,
    moveIndex,
    moveSan,
    messageType,
    severity,
    text,
    conceptKey,
    timestamp: Date.now(),
  };
}
