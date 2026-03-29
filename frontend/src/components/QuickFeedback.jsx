/**
 * Simple Quick Feedback Component
 * =================================
 * 
 * Extends EXISTING pattern learning feedback system with simple thumbs up/down.
 * Uses YOUR existing /coach/pattern-learning/quick-rating endpoint.
 * 
 * NO duplication - just adds quick rating UI to existing system.
 */

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Check } from "lucide-react";
import { API } from "@/App";
import { toast } from "sonner";

export const QuickFeedback = ({ 
  explanation,
  templateId,
  generationMethod, 
  gameId,
  moveNumber
}) => {
  const [rated, setRated] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const submitRating = async (isHelpful) => {
    setSubmitting(true);
    try {
      const response = await fetch(`${API}/coach/pattern-learning/quick-rating`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          template_id: templateId,
          generation_method: generationMethod || "unknown",
          is_helpful: isHelpful,
          game_id: gameId,
          move_number: moveNumber,
          explanation_text: explanation
        })
      });

      if (response.ok) {
        setRated(true);
        toast.success("Thanks for your feedback!");
      }
    } catch (err) {
      toast.error("Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  };

  if (rated) {
    return (
      <div className="flex items-center gap-1 text-xs text-muted-foreground mt-2">
        <Check className="w-3 h-3" />
        <span>Thanks!</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/30">
      <span className="text-xs text-muted-foreground">Helpful?</span>
      <button
        onClick={() => submitRating(true)}
        disabled={submitting}
        className="p-1 hover:bg-green-500/10 rounded transition-colors disabled:opacity-50"
        title="This explanation was helpful"
      >
        <ThumbsUp className="w-3.5 h-3.5 text-green-600 dark:text-green-400" />
      </button>
      <button
        onClick={() => submitRating(false)}
        disabled={submitting}
        className="p-1 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50"
        title="This explanation was not helpful"
      >
        <ThumbsDown className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
      </button>
    </div>
  );
};

export default QuickFeedback;
