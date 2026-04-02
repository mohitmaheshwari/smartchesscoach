/**
 * useGuardian — Pre-move guardian system
 *
 * Evaluates moves before execution. If a move is risky (blunder/mistake),
 * shows an intervention modal. The user can cancel or confirm the move.
 *
 * confirmRiskyMove stays in CoachPlay because it interacts with session,
 * coaching, and polling state. This hook manages the guardian-specific state
 * and the evaluate + cancel flows.
 */

import { useState, useCallback } from "react";
import { API } from "@/App";
import { toast } from "sonner";

const useGuardian = ({ session, onCancelRestore }) => {
  const [guardianIntervention, setGuardianIntervention] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const [showEnforcementCheckbox, setShowEnforcementCheckbox] = useState(false);
  const [remainingInterventions, setRemainingInterventions] = useState(3);

  const evaluateMove = useCallback(
    async (moveSan) => {
      try {
        const response = await fetch(`${API}/coach/play/evaluate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            session_id: session.session_id,
            move: moveSan,
          }),
        });

        if (response.ok) {
          const result = await response.json();

          if (result.tactical_awareness) {
            toast.success(
              result.tactical_message || "Good tactical awareness!"
            );
          }

          return result;
        }
      } catch (error) {
        console.error("Guardian evaluation error:", error);
      }
      return null;
    },
    [session?.session_id]
  );

  const cancelRiskyMove = useCallback(() => {
    if (pendingMove?.originalFen && onCancelRestore) {
      onCancelRestore(pendingMove.originalFen);
    }
    setGuardianIntervention(null);
    setPendingMove(null);
    toast.info("Move cancelled. Choose a different move.");
  }, [pendingMove, onCancelRestore]);

  const setIntervention = useCallback((result, moveData) => {
    setGuardianIntervention(result);
    setPendingMove(moveData);
  }, []);

  const clearIntervention = useCallback(() => {
    setGuardianIntervention(null);
    setPendingMove(null);
  }, []);

  const resetGuardian = useCallback(() => {
    setGuardianIntervention(null);
    setPendingMove(null);
    setRemainingInterventions(3);
  }, []);

  return {
    guardianIntervention,
    setGuardianIntervention,
    pendingMove,
    setPendingMove,
    showEnforcementCheckbox,
    setShowEnforcementCheckbox,
    remainingInterventions,
    setRemainingInterventions,
    evaluateMove,
    cancelRiskyMove,
    setIntervention,
    clearIntervention,
    resetGuardian,
  };
};

export default useGuardian;
