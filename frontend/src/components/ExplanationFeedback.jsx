/**
 * ExplanationFeedback Component
 * ==============================
 * 
 * Allows users to rate and improve chess explanations.
 * Beta testers and coaches can suggest better explanations.
 * 
 * Usage:
 * <ExplanationFeedback
 *   explanation={explanation}
 *   templateId={templateId}
 *   gameId={gameId}
 *   moveNumber={moveNumber}
 * />
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { API } from "@/App";
import { toast } from "sonner";
import { 
  ThumbsUp, 
  ThumbsDown, 
  Edit3,
  Check,
  X,
  Star,
  AlertTriangle
} from "lucide-react";

const ExplanationFeedback = ({ 
  explanation, 
  templateId, 
  gameId, 
  moveNumber,
  onFeedbackSubmitted 
}) => {
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [feedbackType, setFeedbackType] = useState(null); // "helpful" | "not_helpful" | "improve"
  const [rating, setRating] = useState(0);
  const [suggestionText, setSuggestionText] = useState("");
  const [isChessAccurate, setIsChessAccurate] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleQuickFeedback = async (helpful) => {
    setSubmitting(true);
    try {
      const response = await fetch(`${API}/explanation-feedback/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          game_id: gameId,
          move_number: moveNumber,
          explanation: explanation,
          template_id: templateId,
          feedback_type: "rating",
          is_helpful: helpful
        })
      });

      if (response.ok) {
        setSubmitted(true);
        toast.success("Thanks for your feedback!");
        if (onFeedbackSubmitted) onFeedbackSubmitted();
      }
    } catch (err) {
      toast.error("Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDetailedFeedback = async () => {
    if (feedbackType === "improve" && !suggestionText.trim()) {
      toast.error("Please provide your suggested improvement");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API}/explanation-feedback/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          game_id: gameId,
          move_number: moveNumber,
          explanation: explanation,
          template_id: templateId,
          feedback_type: feedbackType === "improve" ? "correction" : "rating",
          rating: rating > 0 ? rating : null,
          is_helpful: feedbackType === "helpful" ? true : feedbackType === "not_helpful" ? false : null,
          suggested_improvement: suggestionText.trim() || null,
          is_chess_accurate: isChessAccurate
        })
      });

      if (response.ok) {
        setSubmitted(true);
        setShowFeedbackForm(false);
        toast.success("Thanks for helping improve ChessGuru!");
        if (onFeedbackSubmitted) onFeedbackSubmitted();
      }
    } catch (err) {
      toast.error("Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400 mt-2">
        <Check className="w-4 h-4" />
        <span>Feedback submitted. Thank you!</span>
      </div>
    );
  }

  if (!showFeedbackForm) {
    return (
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50">
        <span className="text-xs text-muted-foreground">Was this helpful?</span>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2"
          onClick={() => handleQuickFeedback(true)}
          disabled={submitting}
        >
          <ThumbsUp className="w-3 h-3 mr-1" />
          Yes
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2"
          onClick={() => handleQuickFeedback(false)}
          disabled={submitting}
        >
          <ThumbsDown className="w-3 h-3 mr-1" />
          No
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2"
          onClick={() => {
            setShowFeedbackForm(true);
            setFeedbackType("improve");
          }}
        >
          <Edit3 className="w-3 h-3 mr-1" />
          Suggest Better
        </Button>
      </div>
    );
  }

  return (
    <Card className="mt-3 border-blue-500/30 bg-blue-500/5">
      <CardContent className="p-3 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Edit3 className="w-4 h-4 text-blue-500" />
            <span className="text-sm font-medium">Help Improve This Explanation</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 w-6 p-0"
            onClick={() => setShowFeedbackForm(false)}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Rating */}
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Rate this explanation:</label>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                onClick={() => setRating(star)}
                className="p-1 hover:scale-110 transition-transform"
              >
                <Star
                  className={`w-5 h-5 ${
                    star <= rating 
                      ? "fill-yellow-500 text-yellow-500" 
                      : "text-muted-foreground"
                  }`}
                />
              </button>
            ))}
          </div>
        </div>

        {/* Chess Accuracy Check */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="chess-accurate"
            checked={isChessAccurate}
            onChange={(e) => setIsChessAccurate(e.target.checked)}
            className="rounded"
          />
          <label htmlFor="chess-accurate" className="text-sm">
            The chess analysis is correct
          </label>
          {!isChessAccurate && (
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          )}
        </div>

        {/* Suggestion Text */}
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">
            Suggest a better explanation (optional):
          </label>
          <Textarea
            placeholder="How would you explain this better? (Your suggestion will be reviewed by coaches)"
            value={suggestionText}
            onChange={(e) => setSuggestionText(e.target.value)}
            className="min-h-[80px] text-sm"
          />
        </div>

        {/* Submit Buttons */}
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowFeedbackForm(false)}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleDetailedFeedback}
            disabled={submitting}
          >
            {submitting ? "Submitting..." : "Submit Feedback"}
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          🙏 Your feedback helps us improve explanations for all users!
        </p>
      </CardContent>
    </Card>
  );
};

export default ExplanationFeedback;
