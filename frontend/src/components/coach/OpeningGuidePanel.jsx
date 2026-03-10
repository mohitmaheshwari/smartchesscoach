/**
 * OpeningGuidePanel.jsx - Displays opening guidance during game
 * 
 * Extracted from CoachPlay.jsx for better code organization.
 * Shows suggested moves, trap options, and completion status.
 */

import { Button } from "@/components/ui/button";
import { BookOpen, Target, Sparkles, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { API } from "@/App";

/**
 * OpeningGuidePanel - Shows opening teaching guidance
 * 
 * Props:
 * - openingGuidance: Object with teaching_active, guidance, suggested_trap
 * - activeLesson: Current lesson state (if any)
 * - sessionId: Current game session ID
 * - onStartLesson: Callback when user clicks "Learn Trap"
 * - onSkipTrap: Callback when user clicks "Skip"
 */
export const OpeningGuidePanel = ({ 
  openingGuidance, 
  activeLesson, 
  sessionId, 
  onStartLesson,
  onSkipTrap
}) => {
  // Don't render if no active teaching
  if (!openingGuidance?.teaching_active || !openingGuidance.guidance) {
    return null;
  }

  const { guidance, suggested_trap } = openingGuidance;

  // Handle Learn Trap click
  const handleLearnTrap = async () => {
    try {
      const response = await fetch(`${API}/coach/play/teaching/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ 
          session_id: sessionId,
          lesson_type: "learn_trap"
        })
      });
      const data = await response.json();
      if (data.success && onStartLesson) {
        onStartLesson(data);
      }
    } catch (error) {
      console.error("Error starting trap lesson:", error);
      toast.error("Failed to start trap lesson");
    }
  };

  // Handle Skip click
  const handleSkip = async () => {
    try {
      await fetch(`${API}/coach/play/teaching/skip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId })
      });
      if (onSkipTrap) {
        onSkipTrap();
      }
      toast.info("No problem! Let's continue playing.");
    } catch (error) {
      console.error("Error skipping trap:", error);
    }
  };

  // Show completion message
  if (guidance.complete) {
    return (
      <div className="mt-4 p-3 rounded-lg bg-green-500/10 border border-green-500/30" data-testid="opening-complete">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-500" />
          <span className="text-sm text-green-500">{guidance.message}</span>
        </div>
      </div>
    );
  }

  // Show active guidance
  return (
    <div className="mt-4 p-3 rounded-lg bg-primary/10 border border-primary/30" data-testid="opening-guidance">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <BookOpen className="w-4 h-4 text-primary" />
        <span className="text-sm font-medium text-primary">Opening Guide</span>
      </div>

      {/* Move guidance */}
      {guidance.your_turn ? (
        <div className="space-y-1">
          <p className="text-sm">{guidance.message}</p>
          <p className="text-xs text-primary font-medium">
            Suggested: {guidance.suggested_move}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{guidance.message}</p>
      )}

      {/* Trap Learning Option */}
      {suggested_trap && !activeLesson && (
        <div className="mt-3 pt-3 border-t border-primary/20">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-amber-500" />
            <span className="text-xs font-medium text-amber-500">
              Trap: {suggested_trap.name}
            </span>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="flex-1 h-8 text-xs bg-amber-500/10 border-amber-500/30 hover:bg-amber-500/20"
              onClick={handleLearnTrap}
              data-testid="learn-trap-btn"
            >
              <Sparkles className="w-3 h-3 mr-1" />
              Learn Trap
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="flex-1 h-8 text-xs"
              onClick={handleSkip}
              data-testid="skip-trap-btn"
            >
              Skip
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default OpeningGuidePanel;
