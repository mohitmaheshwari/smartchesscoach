/**
 * FeedbackModal - Reusable feedback modal for pattern learning
 * 
 * Used in: Lab, Reflect, CoachPlay
 * Purpose: Let users correct wrong AI explanations to improve the system
 * 
 * When user says an explanation is "wrong", they can:
 * 1. Select the correct pattern (fork, pin, etc.)
 * 2. Add a comment explaining what actually happened
 * 3. Submit to the pattern-learning API
 */

import { useState } from "react";
import { X, ThumbsDown, Send, Loader2, CheckCircle2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;

// Pattern correction options - same as in pattern_learning
const PATTERN_OPTIONS = [
  { value: "WALKED_INTO_FORK", label: "I walked into a fork" },
  { value: "WALKED_INTO_PIN", label: "I walked into a pin" },
  { value: "WALKED_INTO_SKEWER", label: "I walked into a skewer" },
  { value: "HANGING_PIECE", label: "I left a piece hanging" },
  { value: "MISSED_FORK", label: "I missed a fork opportunity" },
  { value: "MISSED_PIN", label: "I missed a pin opportunity" },
  { value: "MISSED_THREAT", label: "I missed opponent's threat" },
  { value: "MISSED_CHECKMATE", label: "I missed checkmate (or allowed it)" },
  { value: "MISSED_WINNING_TACTIC", label: "I missed a winning tactic" },
  { value: "BLUNDER_WHEN_AHEAD", label: "I blundered when ahead" },
  { value: "IGNORED_THREAT", label: "I ignored opponent's threat" },
  { value: "POSITIONAL_DRIFT", label: "Small positional mistake" },
  { value: "OTHER", label: "Something else" },
];

// Feedback type options
const FEEDBACK_TYPES = [
  { value: "confusing", label: "Confusing / Hard to understand" },
  { value: "wrong", label: "Wrong / Incorrect explanation" },
  { value: "obvious", label: "Too obvious / I knew this" },
  { value: "not_relevant", label: "Not relevant to my situation" },
];

export default function FeedbackModal({
  isOpen,
  onClose,
  // Context for the feedback
  explanation,       // The explanation that was shown
  positionFen,       // FEN of the position
  movePlayed,        // The move user played (UCI or SAN)
  moveSan,           // SAN notation
  bestMove,          // The best move
  classification,    // System's classification (e.g., "threat_blindness")
  evalBefore,        // Eval before move
  evalAfter,         // Eval after move
  pvAfterPlayed,     // Principal variation after played move
  gameId,            // Game ID
  moveNumber,        // Move number
  userColor,         // User's color
  source = "lab",    // Which page this is from: "lab", "reflect", "coach_play"
}) {
  const [feedbackType, setFeedbackType] = useState("");
  const [correctPattern, setCorrectPattern] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!feedbackType) return;
    if (feedbackType === "wrong" && !correctPattern) return;

    setSubmitting(true);

    try {
      // Submit to pattern learning API
      const response = await fetch(`${API}/api/coach/pattern-learning/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          position_fen: positionFen || "",
          move_played: movePlayed || "",
          move_san: moveSan || movePlayed || "",
          system_classification: classification || "UNKNOWN",
          system_explanation: explanation || "",
          correct_classification: feedbackType === "wrong" ? correctPattern : feedbackType,
          user_explanation: comment,
          eval_before: evalBefore || 0,
          eval_after: evalAfter || 0,
          best_move: bestMove || "",
          pv_after_played: pvAfterPlayed || [],
          game_id: gameId || "",
          move_number: moveNumber || 0,
          user_color: userColor || "white",
          source: source,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setSubmitted(true);
        
        if (feedbackType === "wrong" && result.corrected_explanation) {
          toast.success("Thanks! The coach will learn from this.", {
            description: result.corrected_explanation.substring(0, 100) + "...",
          });
        } else {
          toast.success("Thanks for your feedback! This helps improve coaching for everyone.");
        }
        
        // Auto-close after 1.5s
        setTimeout(() => {
          onClose();
          setFeedbackType("");
          setCorrectPattern("");
          setComment("");
          setSubmitted(false);
        }, 1500);
      } else {
        toast.error("Failed to submit feedback. Please try again.");
      }
    } catch (error) {
      console.error("Error submitting feedback:", error);
      toast.error("Failed to submit feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md" data-testid="feedback-modal">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <ThumbsDown className="w-4 h-4" />
              What was wrong?
            </CardTitle>
            <button
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground"
              data-testid="close-feedback-modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Show the explanation being reported */}
          {explanation && (
            <div className="p-2 bg-muted/50 rounded text-xs text-muted-foreground line-clamp-3">
              "{explanation}"
            </div>
          )}

          {/* Success state */}
          {submitted ? (
            <div className="flex flex-col items-center gap-3 py-4">
              <CheckCircle2 className="w-12 h-12 text-green-500" />
              <p className="text-sm font-medium text-green-600 dark:text-green-400">
                Thanks! Your feedback helps the coach learn.
              </p>
            </div>
          ) : (
            <>
              {/* Feedback type selection */}
              <div className="space-y-2">
                {FEEDBACK_TYPES.map((option) => (
                  <label
                    key={option.value}
                    className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                      feedbackType === option.value
                        ? "bg-primary/10 border border-primary/30"
                        : "hover:bg-muted/50 border border-transparent"
                    }`}
                  >
                    <input
                      type="radio"
                      name="feedback"
                      value={option.value}
                      checked={feedbackType === option.value}
                      onChange={(e) => setFeedbackType(e.target.value)}
                      className="sr-only"
                    />
                    <div
                      className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        feedbackType === option.value
                          ? "border-primary bg-primary"
                          : "border-muted-foreground"
                      }`}
                    >
                      {feedbackType === option.value && (
                        <div className="w-2 h-2 rounded-full bg-background" />
                      )}
                    </div>
                    <span className="text-sm">{option.label}</span>
                  </label>
                ))}
              </div>

              {/* Pattern correction - shown when "wrong" is selected */}
              {feedbackType === "wrong" && (
                <div className="space-y-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                  <p className="text-xs font-medium text-amber-600 dark:text-amber-400">
                    Help us learn! What was it actually?
                  </p>
                  <select
                    value={correctPattern}
                    onChange={(e) => setCorrectPattern(e.target.value)}
                    className="w-full p-2 text-sm rounded border bg-background"
                    data-testid="pattern-correction-select"
                  >
                    <option value="">Select the correct pattern...</option>
                    {PATTERN_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Comment textarea */}
              <Textarea
                placeholder={
                  feedbackType === "wrong"
                    ? "Explain what the mistake actually was (e.g., 'The pawn forks my knight and bishop')..."
                    : "Tell us more (optional)..."
                }
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="h-20 text-sm"
              />

              {/* Submit button */}
              <Button
                onClick={handleSubmit}
                disabled={
                  !feedbackType ||
                  (feedbackType === "wrong" && !correctPattern) ||
                  submitting
                }
                className="w-full"
                data-testid="submit-feedback-btn"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4 mr-2" />
                    Submit Feedback
                  </>
                )}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
