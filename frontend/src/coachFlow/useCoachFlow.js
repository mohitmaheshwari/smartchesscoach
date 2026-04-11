/**
 * coachFlow/useCoachFlow.js — Main hook for the coaching interaction system.
 *
 * Manages:
 *   - Pending move lifecycle
 *   - 400ms eval window (instant move → async eval → maybe interrupt)
 *   - Coaching hold states (thinking_hold, critical_hold, awaiting_clock_commit)
 *   - Clock commit gating
 *   - Move revision before commit
 *   - Session timeline (historical coaching moments)
 *   - Analytics logging
 */

import { useState, useRef, useCallback } from "react";
import { API } from "@/App";
import {
  INTERACTION_STATES,
  CLOCK_STATES,
  createPendingMove,
  createTimelineItem,
} from "./types";
import { getAdaptiveHoldMs, getCoachingPresentation } from "./adaptiveTiming";

export default function useCoachFlow({ session, userRating = 1200 }) {
  // ─── Core State ─────────────────────────────────────────────
  const [interactionState, setInteractionState] = useState(INTERACTION_STATES.IDLE);
  const [clockState, setClockState] = useState(CLOCK_STATES.NORMAL);
  const [pendingMove, setPendingMove] = useState(null);
  const [activeCoachingMoment, setActiveCoachingMoment] = useState(null);
  const [activeStripCoaching, setActiveStripCoaching] = useState(null); // ambient/advisory
  const [liveChecklist, setLiveChecklist] = useState(null); // {phase, fundamentals: [...]}
  const [playerWeaknessList, setPlayerWeaknessList] = useState([]); // from backend
  const [playerProfile, setPlayerProfile] = useState(null); // strengths/weaknesses/domains
  const [rootProblem, setRootProblem] = useState(null); // {primary, secondary, minor}
  const [commentary, setCommentary] = useState(null); // position-specific board reading
  const [openingGuidance, setOpeningGuidance] = useState(null); // move idea + arrow
  const [trapWarning, setTrapWarning] = useState(null); // approaching a known trap
  const [timeline, setTimeline] = useState([]);

  // ─── Internal Refs ──────────────────────────────────────────
  const holdTimerRef = useRef(null);
  const evalAbortRef = useRef(null);
  const sessionBehavior = useRef({
    repeatedConceptCounts: {},
    recentCriticalMoveIndices: [],
    fastCommitStreak: 0,
  });

  // ─── Cleanup ────────────────────────────────────────────────
  const _clearHoldTimer = useCallback(() => {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }
  }, []);

  const _clearState = useCallback(() => {
    _clearHoldTimer();
    setPendingMove(null);
    setActiveCoachingMoment(null);
    setActiveStripCoaching(null);
    setClockState(CLOCK_STATES.NORMAL);
  }, [_clearHoldTimer]);

  // ─── MAIN: Handle User Move ─────────────────────────────────
  /**
   * Called when user drops a piece on the board.
   * Board updates INSTANTLY. Async eval runs in background.
   * If coaching exists within 400ms → hold. Otherwise → auto-commit.
   *
   * @param {Object} moveData - { san, uci, from, to, promotion, fenBefore, fenAfterPreview }
   * @param {Function} commitFn - async (moveSan, timeSpent) => boolean — commits move to backend
   * @param {number} timeSpent - seconds
   * @returns {{ autoCommitted: boolean }} — if true, caller should proceed normally
   */
  const handleUserMove = useCallback(async (moveData, commitFn, timeSpent) => {
    const pending = createPendingMove(moveData);
    setPendingMove(pending);
    setInteractionState(INTERACTION_STATES.PENDING_USER_MOVE);
    setActiveCoachingMoment(null);
    _clearHoldTimer();

    // Async eval — race with 400ms window
    const sessionId = session?.session_id;
    if (!sessionId) {
      // No session, auto-commit
      await commitFn(pending.san, timeSpent);
      setInteractionState(INTERACTION_STATES.COACH_TURN);
      setPendingMove(null);
      return { autoCommitted: true };
    }

    try {
      // Create abort controller for timeout
      const controller = new AbortController();
      evalAbortRef.current = controller;

      // Race: eval vs 400ms timeout
      const evalPromise = fetch(`${API}/coach/play/evaluate-pending`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        signal: controller.signal,
        body: JSON.stringify({
          sessionId,
          fenBefore: pending.fenBefore,
          uci: pending.uci,
          moveIndexPreview: moveData.moveIndexPreview || 0,
          userRating,
        }),
      }).then(r => r.ok ? r.json() : null);

      // 3000ms window — Stockfish needs time, especially on cold start
      const EVAL_TIMEOUT_MS = 3000;
      const timeoutPromise = new Promise(resolve =>
        setTimeout(() => resolve("__timeout__"), EVAL_TIMEOUT_MS)
      );

      const raceResult = await Promise.race([evalPromise, timeoutPromise]);
      const timedOut = raceResult === "__timeout__";
      const result = timedOut ? null : raceResult;
      console.log("[CoachFlow] evaluate-pending result:", timedOut ? "timeout" : "received", result);

      // If timeout won → auto-commit, but still grab guidance when eval finishes
      if (timedOut) {
        // Fire-and-forget: when eval eventually resolves, apply guidance/checklist
        evalPromise.then(lateResult => {
          if (lateResult) {
            console.log("[CoachFlow] Late eval arrived, applying guidance:", Object.keys(lateResult));
            if (lateResult.checklist) setLiveChecklist(lateResult.checklist);
            if (lateResult.weaknesses) setPlayerWeaknessList(lateResult.weaknesses);
            if (lateResult.playerProfile) setPlayerProfile(prev => prev || lateResult.playerProfile);
            if (lateResult.commentary) setCommentary(lateResult.commentary);
            if (lateResult.rootProblem) setRootProblem(lateResult.rootProblem);
            setOpeningGuidance(lateResult.openingGuidance || null);
            setTrapWarning(lateResult.trapWarning || null);
          }
        }).catch(() => {});

        await commitFn(pending.san, timeSpent);
        setInteractionState(INTERACTION_STATES.COACH_TURN);
        setPendingMove(null);
        setClockState(CLOCK_STATES.DISABLED);
        return { autoCommitted: true };
      }

      // Eval failed
      if (!result) {
        await commitFn(pending.san, timeSpent);
        setInteractionState(INTERACTION_STATES.COACH_TURN);
        setPendingMove(null);
        setClockState(CLOCK_STATES.DISABLED);
        return { autoCommitted: true };
      }

      const decision = result.coachingDecision || {};
      const layer = decision.layer || "silent";

      // Update checklist (always, even on silent)
      if (result.checklist) {
        console.log("[CoachFlow] fundamentals:", result.checklist);
        setLiveChecklist(result.checklist);
      }
      if (result.weaknesses) {
        setPlayerWeaknessList(result.weaknesses);
      }
      if (result.playerProfile && !playerProfile) {
        setPlayerProfile(result.playerProfile);
      }
      if (result.commentary) {
        setCommentary(result.commentary);
      }
      if (result.rootProblem) {
        setRootProblem(result.rootProblem);
      }
      // Always update guidance — clear old if no new guidance
      console.log("[CoachFlow] openingGuidance:", result.openingGuidance ? JSON.stringify({arrow: result.openingGuidance.arrow, move: result.openingGuidance.expected_move, idea: result.openingGuidance.move_idea?.substring(0, 40)}) : "null");
      setOpeningGuidance(result.openingGuidance || null);
      setTrapWarning(result.trapWarning || null);
      console.log("[CoachFlow] debug.guidance:", result.debug?.guidance, "openingGuidance:", result.openingGuidance ? "present" : "null");

      // ─── AUTO-COMMIT (silent, ambient, advisory) ─────
      if (layer === "silent" || result.shouldAutoCommit) {
        // Show strip for ambient/advisory (but auto-commit continues)
        if ((layer === "ambient" || layer === "advisory") && decision.text) {
          setActiveStripCoaching({
            layer,
            text: decision.text,
            question: decision.question,
            category: decision.category,
            conceptKey: decision.conceptKey,
            gamePhase: decision.gamePhase,
          });
          // Timeline: ONLY advisory and above. Never ambient.
          if (layer === "advisory") {
            setTimeline(prev => [...prev, createTimelineItem({
              moveIndex: moveData.moveIndexPreview || 0,
              moveSan: pending.san,
              messageType: decision.category || layer,
              severity: decision.severity || "medium",
              text: decision.text,
              conceptKey: decision.conceptKey,
            })]);
          }
        }
        await commitFn(pending.san, timeSpent);
        setInteractionState(INTERACTION_STATES.COACH_TURN);
        setPendingMove(null);
        setClockState(CLOCK_STATES.DISABLED);
        return { autoCommitted: true };
      }

      // ─── CRITICAL: Enter hold ─────
      const moment = result.coachingMoment || decision;
      const holdMs = moment.minHoldMs || getAdaptiveHoldMs({
        messageType: "critical_interrupt",
        severity: decision.severity || "high",
        conceptRepeatCount: sessionBehavior.current.repeatedConceptCounts[decision.conceptKey] || 0,
        repeatedRecently: false,
      });

      const coachingMoment = {
        id: `cm_${Date.now()}`,
        messageType: decision.layer || "critical_interrupt",
        severity: decision.severity || "high",
        text: decision.text,
        question: decision.question || null,
        conceptKey: decision.conceptKey,
        moveIndex: moveData.moveIndexPreview || 0,
        requiresClockCommit: true,
        minHoldMs: holdMs,
        canReviseMove: true,
        shownAt: Date.now(),
        moveEvaluation: result.moveEvaluation,
      };

      setActiveCoachingMoment(coachingMoment);
      setActiveStripCoaching(null); // Clear strip during hold

      // Track concept repeat
      const counts = sessionBehavior.current.repeatedConceptCounts;
      counts[decision.conceptKey] = (counts[decision.conceptKey] || 0) + 1;

      setInteractionState(INTERACTION_STATES.CRITICAL_HOLD);
      setClockState(CLOCK_STATES.HOLD_LOCKED);

      // Start hold timer
      holdTimerRef.current = setTimeout(() => {
        setInteractionState(INTERACTION_STATES.AWAITING_CLOCK_COMMIT);
        setClockState(CLOCK_STATES.HOLD_READY);
      }, holdMs);

      return { autoCommitted: false };

    } catch (err) {
      // Eval failed — auto-commit silently
      console.warn("Coach eval failed, auto-committing:", err);
      await commitFn(pending.san, timeSpent);
      setInteractionState(INTERACTION_STATES.COACH_TURN);
      setPendingMove(null);
      return { autoCommitted: true };
    }
  }, [session, userRating, _clearHoldTimer]);

  // ─── Clock Tap (Commit) ─────────────────────────────────────
  const handleClockTap = useCallback(async (commitFn, timeSpent) => {
    if (interactionState !== INTERACTION_STATES.AWAITING_CLOCK_COMMIT) return false;
    if (!pendingMove) return false;

    setInteractionState(INTERACTION_STATES.COMMITTING_MOVE);
    setClockState(CLOCK_STATES.DISABLED);

    // Log analytics
    const latencyMs = activeCoachingMoment
      ? Date.now() - (activeCoachingMoment.shownAt + activeCoachingMoment.minHoldMs)
      : 0;

    if (latencyMs < 500) {
      sessionBehavior.current.fastCommitStreak += 1;
    } else {
      sessionBehavior.current.fastCommitStreak = 0;
    }

    // Append to timeline
    if (activeCoachingMoment) {
      setTimeline(prev => [...prev, createTimelineItem({
        moveIndex: activeCoachingMoment.moveIndex,
        moveSan: pendingMove.san,
        messageType: activeCoachingMoment.messageType,
        severity: activeCoachingMoment.severity,
        text: activeCoachingMoment.text,
        conceptKey: activeCoachingMoment.conceptKey,
      })]);
    }

    // Commit the move
    const success = await commitFn(pendingMove.san, timeSpent);

    // Clear state
    _clearState();

    if (success) {
      setInteractionState(INTERACTION_STATES.COACH_TURN);
    } else {
      setInteractionState(INTERACTION_STATES.IDLE);
    }

    return success;
  }, [interactionState, pendingMove, activeCoachingMoment, _clearState]);

  // ─── Move Revision ──────────────────────────────────────────
  const handleMoveRevision = useCallback((newMoveData) => {
    if (
      interactionState !== INTERACTION_STATES.THINKING_HOLD &&
      interactionState !== INTERACTION_STATES.CRITICAL_HOLD &&
      interactionState !== INTERACTION_STATES.AWAITING_CLOCK_COMMIT
    ) return false;

    // Clear current hold
    _clearHoldTimer();
    setActiveCoachingMoment(null);
    setClockState(CLOCK_STATES.NORMAL);

    // Set new pending move — the caller (CoachPlay) will re-run handleUserMove
    setPendingMove(createPendingMove(newMoveData));
    return true;
  }, [interactionState, _clearHoldTimer]);

  // ─── Cancel Pending Move ────────────────────────────────────
  const cancelPendingMove = useCallback(() => {
    _clearState();
    setInteractionState(INTERACTION_STATES.IDLE);
  }, [_clearState]);

  // ─── Game State Transitions ─────────────────────────────────
  const setCoachTurn = useCallback(() => {
    setInteractionState(INTERACTION_STATES.COACH_TURN);
    setClockState(CLOCK_STATES.DISABLED);
  }, []);

  const setPlayerTurn = useCallback(() => {
    setInteractionState(INTERACTION_STATES.IDLE);
    setClockState(CLOCK_STATES.NORMAL);
  }, []);

  const setGameOver = useCallback(() => {
    _clearState();
    setInteractionState(INTERACTION_STATES.GAME_OVER);
    setClockState(CLOCK_STATES.DISABLED);
  }, [_clearState]);

  const resetFlow = useCallback(() => {
    _clearState();
    setInteractionState(INTERACTION_STATES.IDLE);
    setLiveChecklist(null);
    setPlayerWeaknessList([]);
    setPlayerProfile(null);
    setRootProblem(null);
    setCommentary(null);
    setOpeningGuidance(null);
    setTrapWarning(null);
    setTimeline([]);
    sessionBehavior.current = {
      repeatedConceptCounts: {},
      recentCriticalMoveIndices: [],
      fastCommitStreak: 0,
    };
  }, [_clearState]);

  // ─── Derived State ──────────────────────────────────────────
  const isInHold = [
    INTERACTION_STATES.THINKING_HOLD,
    INTERACTION_STATES.CRITICAL_HOLD,
    INTERACTION_STATES.AWAITING_CLOCK_COMMIT,
  ].includes(interactionState);

  const canCommit = interactionState === INTERACTION_STATES.AWAITING_CLOCK_COMMIT;
  const canRevise = isInHold && activeCoachingMoment?.canReviseMove;
  const hasPendingMove = !!pendingMove;

  return {
    // State
    interactionState,
    clockState,
    pendingMove,
    activeCoachingMoment,
    activeStripCoaching,
    liveChecklist,
    playerWeaknessList,
    playerProfile,
    rootProblem,
    commentary,
    openingGuidance,
    setOpeningGuidance,
    trapWarning,
    timeline,

    // Derived
    isInHold,
    canCommit,
    canRevise,
    hasPendingMove,

    // Actions
    handleUserMove,
    handleClockTap,
    handleMoveRevision,
    cancelPendingMove,
    setCoachTurn,
    setPlayerTurn,
    setGameOver,
    resetFlow,
  };
}
