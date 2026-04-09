/**
 * coachFlow/adaptiveTiming.js — Hold duration logic.
 *
 * Computes how long the player must wait before clock commit.
 * Based on severity, message type, pattern repeats, user behavior.
 */

import { MESSAGE_TYPES } from "./types";

/**
 * Get the minimum hold duration in milliseconds.
 *
 * @param {Object} input
 * @param {string} input.messageType - e.g. "critical_interrupt"
 * @param {string} input.severity - "low" | "medium" | "high"
 * @param {number} input.conceptRepeatCount - how many times this concept shown this session
 * @param {boolean} input.repeatedRecently - same concept in last 10 moves
 * @returns {number} milliseconds
 */
export function getAdaptiveHoldMs({
  messageType,
  severity,
  conceptRepeatCount = 0,
  repeatedRecently = false,
}) {
  if (severity === "low") return 1500;

  if (messageType === MESSAGE_TYPES.CRITICAL_INTERRUPT) {
    if (conceptRepeatCount >= 3) return 6500;
    if (repeatedRecently) return 5000;
    return 4000;
  }

  if (messageType === MESSAGE_TYPES.PATTERN_REPEAT) {
    return 5000;
  }

  if (severity === "medium") {
    return 2500;
  }

  return 2000;
}

/**
 * Get the presentation config for a coaching moment.
 *
 * @param {string} messageType
 * @param {string} severity
 * @returns {{ visualPriority: string, requiresClockCommit: boolean, canReviseMove: boolean }}
 */
export function getCoachingPresentation(messageType, severity) {
  if (messageType === MESSAGE_TYPES.CRITICAL_INTERRUPT) {
    return { visualPriority: "high", requiresClockCommit: true, canReviseMove: true };
  }

  if (messageType === MESSAGE_TYPES.PATTERN_REPEAT) {
    return { visualPriority: "high", requiresClockCommit: true, canReviseMove: true };
  }

  if (severity === "medium") {
    return { visualPriority: "medium", requiresClockCommit: true, canReviseMove: true };
  }

  return { visualPriority: "low", requiresClockCommit: true, canReviseMove: true };
}
