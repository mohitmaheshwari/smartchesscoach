import React, { useState } from "react";
import ActiveRecallRanking from "./ActiveRecallRanking";
import ActiveRecallConcept from "./ActiveRecallConcept";
import "./ActiveRecallContainer.css";

/**
 * ACTIVE RECALL CONTAINER
 *
 * Orchestrates ranking + concept questions after a coaching mistake.
 * - Shows both questions sequentially
 * - Records responses to backend
 * - Shows feedback: "mastered" / "partial" / "not_learned"
 * - Gracefully skips if no active_recall data (coaching text still shows)
 */
export default function ActiveRecallContainer({
  sessionId,
  moveIndex,
  activeRecall,
  cognitiveGap,
  onComplete
}) {
  const [stage, setStage] = useState("ranking"); // "ranking", "concept", "feedback"
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [responses, setResponses] = useState({
    ranking: null,
    concept: null
  });
  const [feedback, setFeedback] = useState(null);

  if (!activeRecall?.ranking || !activeRecall?.concept) {
    return null; // Skip silently if no active recall data
  }

  const handleRankingAnswer = async (answer) => {
    setResponses(r => ({ ...r, ranking: answer }));
    setStage("concept");
  };

  const handleConceptAnswer = async (answer) => {
    setIsSubmitting(true);
    try {
      const combinedResponse = {
        session_id: sessionId,
        move_index: moveIndex,
        cognitive_gap: cognitiveGap,
        ranking_response: responses.ranking,
        concept_response: answer
      };

      const response = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/coach/play/active-recall-response`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(combinedResponse)
        }
      );

      if (!response.ok) throw new Error("Failed to record response");

      const data = await response.json();
      setFeedback(data.score); // "mastered", "partial", "not_learned"
      setResponses(r => ({ ...r, concept: answer }));
      setStage("feedback");

      // Auto-dismiss after 2s if mastered
      if (data.score === "mastered") {
        setTimeout(onComplete, 2000);
      }
    } catch (error) {
      console.error("[AR] Response recording failed:", error);
      setStage("feedback");
      setFeedback("error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="active-recall-container">
      {stage === "ranking" && (
        <ActiveRecallRanking
          ranking={activeRecall.ranking}
          onAnswer={handleRankingAnswer}
          isLoading={isSubmitting}
        />
      )}

      {stage === "concept" && (
        <ActiveRecallConcept
          concept={activeRecall.concept}
          onAnswer={handleConceptAnswer}
          isLoading={isSubmitting}
        />
      )}

      {stage === "feedback" && (
        <div className="ar-feedback">
          {feedback === "mastered" && (
            <div className="ar-feedback-mastered">
              <span className="ar-feedback-icon">✓</span>
              <h3>Perfect!</h3>
              <p>You've got this pattern down.</p>
            </div>
          )}

          {feedback === "partial" && (
            <div className="ar-feedback-partial">
              <span className="ar-feedback-icon">~</span>
              <h3>Good start!</h3>
              <p>You got one part right. Keep practicing.</p>
            </div>
          )}

          {feedback === "not_learned" && (
            <div className="ar-feedback-not_learned">
              <span className="ar-feedback-icon">!</span>
              <h3>Keep learning</h3>
              <p>This pattern will show up again soon.</p>
            </div>
          )}

          {feedback === "error" && (
            <div className="ar-feedback-error">
              <p>Couldn't save your response. Try again.</p>
            </div>
          )}

          <button
            onClick={onComplete}
            className="ar-feedback-dismiss"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
