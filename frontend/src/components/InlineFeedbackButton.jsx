/**
 * InlineFeedbackButton - Small feedback button for AI-generated text
 * 
 * Purpose: Allow users to flag any AI-generated commentary as unhelpful
 * Used in: Lab page (strategy insights, coach explanations)
 * 
 * When clicked, captures full context for the self-learning system:
 * - The text that was shown
 * - The position (FEN)
 * - Game ID, move number
 * - Section type (what_you_missed, why_wrong, etc.)
 */

import { ThumbsDown } from "lucide-react";

export default function InlineFeedbackButton({ onClick, className = "" }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`inline-flex items-center gap-1 text-xs text-muted-foreground/60 hover:text-red-400 transition-colors opacity-60 hover:opacity-100 ${className}`}
      title="Report incorrect or unhelpful content"
      data-testid="inline-feedback-btn"
    >
      <ThumbsDown className="w-3 h-3" />
      <span>Not helpful</span>
    </button>
  );
}
