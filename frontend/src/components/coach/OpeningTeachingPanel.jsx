/**
 * OpeningTeachingPanel.jsx - Interactive Opening Lesson UI
 * 
 * Displays when coach detects an opening and offers to teach.
 * Handles the interactive lesson flow where user plays along.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { API } from "@/App";
import {
  BookOpen,
  Target,
  Swords,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Sparkles,
  RotateCcw,
  Play,
  Lightbulb,
  ExternalLink
} from "lucide-react";

/**
 * Teaching Offer - Shown when opening is detected
 */
export const OpeningTeachingOffer = ({ 
  offer, 
  sessionId, 
  onStartLesson, 
  onSkip 
}) => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Safety check - if offer is invalid, don't render
  if (!offer || !offer.opening_name) {
    return null;
  }

  // Options for the user
  const options = [
    { 
      id: "go_to_lesson", 
      label: "Learn this opening", 
      description: "Open the full opening lesson page",
      icon: BookOpen,
      primary: true
    },
    { 
      id: "learn_trap", 
      label: "Quick trap lesson", 
      description: "Learn a trap in this opening (stay in game)",
      icon: Target,
      primary: false,
      hidden: !offer.trap_name
    },
    { 
      id: "just_play", 
      label: "Just play", 
      description: "Continue without lesson",
      icon: Play,
      primary: false
    }
  ].filter(opt => !opt.hidden);

  const handleOption = async (optionId) => {
    setLoading(true);
    
    if (optionId === "go_to_lesson" && offer.opening_key) {
      // Navigate to the opening lesson page
      navigate(`/openings/${offer.opening_key}`);
      return;
    }
    
    if (optionId === "just_play") {
      // Skip the offer
      try {
        await fetch(`${API}/coach/play/teaching/skip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ session_id: sessionId })
        });
        onSkip();
      } catch (error) {
        console.error("Error skipping offer:", error);
      }
    } else if (optionId === "learn_trap") {
      // Start a quick trap lesson in-game
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
        
        if (response.ok) {
          const data = await response.json();
          onStartLesson(data);
        }
      } catch (error) {
        console.error("Error starting lesson:", error);
      }
    }
    
    setLoading(false);
  };

  // Use enriched options from backend if available, otherwise fall back to defaults
  const displayOptions = offer.options && offer.options.length > 0
    ? offer.options
    : options;

  return (
    <Card className="border-2 border-primary/30 bg-card overflow-hidden">
      {/* Coach message — conversational header */}
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
            <BookOpen className="w-4 h-4 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground">{offer.opening_name}</p>
            <p className="text-sm text-muted-foreground leading-relaxed mt-1">
              {offer.message}
            </p>
          </div>
        </div>

        {/* Position explanation — what's happening on the board */}
        {offer.position_explanation && (
          <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
            <p className="text-xs text-foreground leading-relaxed">{offer.position_explanation}</p>
          </div>
        )}

        {/* Options — enriched from backend */}
        <div className="space-y-2">
          {displayOptions.map((option) => {
            const optId = option.id;
            const isJustPlay = optId === "just_play";
            const isAggressive = option.style === "aggressive";
            const lessonType = option.lesson_type || optId;
            const Icon = isJustPlay ? Play : isAggressive ? Swords : option.icon || BookOpen;

            return (
              <button
                key={optId}
                onClick={() => handleOption(lessonType === "learn_trap" || lessonType === "learn_main_line" ? lessonType : optId)}
                disabled={loading}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  isJustPlay
                    ? "border-border hover:border-muted-foreground/30 hover:bg-muted/20"
                    : "border-primary/20 hover:border-primary/40 hover:bg-primary/5"
                }`}
                data-testid={`teaching-option-${optId}`}
              >
                <div className="flex items-center gap-2.5">
                  {typeof Icon === 'function' ? (
                    <Icon className={`w-4 h-4 flex-shrink-0 ${isJustPlay ? "text-muted-foreground" : "text-primary"}`} strokeWidth={1.5} />
                  ) : (
                    <Swords className={`w-4 h-4 flex-shrink-0 ${isJustPlay ? "text-muted-foreground" : "text-primary"}`} strokeWidth={1.5} />
                  )}
                  <div className="flex-1 min-w-0">
                    <span className={`text-sm font-medium ${isJustPlay ? "text-muted-foreground" : "text-foreground"}`}>
                      {option.label}
                    </span>
                    {option.description && (
                      <p className="text-xs text-muted-foreground mt-0.5">{option.description}</p>
                    )}
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/30 flex-shrink-0" />
                </div>
              </button>
            );
          })}
        </div>

        {/* Fun fact — adds personality */}
        {offer.fun_fact && (
          <div className="flex items-start gap-2 pt-1">
            <Lightbulb className="w-3 h-3 text-primary/50 mt-0.5 flex-shrink-0" />
            <p className="text-[11px] text-muted-foreground/60 italic leading-relaxed">{offer.fun_fact}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

/**
 * Active Lesson Panel - Shown during interactive teaching
 */
export const ActiveLessonPanel = ({
  lesson,
  sessionId,
  currentInstruction,
  onMoveValidated,
  onLessonComplete,
  onExitLesson
}) => {
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(false);

  // Handle when user makes a move during lesson
  const validateMove = async (move) => {
    setLoading(true);
    setFeedback(null);
    
    try {
      const response = await fetch(`${API}/coach/play/teaching/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          move: move
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.complete) {
          onLessonComplete(data);
        } else if (data.correct) {
          setFeedback({ type: "correct", message: data.message });
          onMoveValidated(data);
        } else {
          setFeedback({ 
            type: "incorrect", 
            message: data.message,
            hint: data.hint,
            expected: data.expected_move
          });
        }
      }
    } catch (error) {
      console.error("Error validating move:", error);
    }
    
    setLoading(false);
  };

  // Expose validateMove to parent
  useEffect(() => {
    window.validateTeachingMove = validateMove;
    return () => { delete window.validateTeachingMove; };
  }, [sessionId]);

  return (
    <Card className="border-2 border-amber-500/50 bg-amber-500/5">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-500" />
            <CardTitle className="text-base">
              Learning: {lesson.lesson_name}
            </CardTitle>
          </div>
          <Badge variant="outline">
            {currentInstruction?.progress || "0/0"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current instruction */}
        {currentInstruction && !currentInstruction.complete && (
          <div className="p-3 rounded-lg bg-background border">
            <p className="text-sm font-medium mb-2">
              {currentInstruction.message}
            </p>
            {currentInstruction.should_user_play && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <ChevronRight className="w-4 h-4 text-primary" />
                <span>Your turn - play <strong>{currentInstruction.move}</strong></span>
              </div>
            )}
          </div>
        )}
        
        {/* Feedback */}
        {feedback && (
          <div className={`p-3 rounded-lg ${
            feedback.type === "correct" 
              ? "bg-green-500/10 border border-green-500/30" 
              : "bg-red-500/10 border border-red-500/30"
          }`}>
            <div className="flex items-start gap-2">
              {feedback.type === "correct" ? (
                <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500 mt-0.5" />
              )}
              <div className="text-sm">
                <p>{feedback.message}</p>
                {feedback.hint && (
                  <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                    <Lightbulb className="w-3 h-3" />
                    {feedback.hint}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
        
        {/* Key ideas */}
        {lesson.key_ideas && lesson.key_ideas.length > 0 && (
          <div className="text-xs text-muted-foreground">
            <p className="font-medium mb-1">Key Ideas:</p>
            <ul className="list-disc list-inside space-y-0.5">
              {lesson.key_ideas.slice(0, 3).map((idea, i) => (
                <li key={i}>{idea}</li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Exit button */}
        <Button 
          variant="ghost" 
          size="sm" 
          className="w-full"
          onClick={() => onExitLesson("continue_game")}
        >
          <XCircle className="w-4 h-4 mr-1" />
          Exit Lesson
        </Button>
      </CardContent>
    </Card>
  );
};

/**
 * Lesson Complete Panel - Shown after finishing a lesson
 */
export const LessonCompletePanel = ({
  completion,
  sessionId,
  onChoice
}) => {
  const [loading, setLoading] = useState(false);

  const handleChoice = async (choice) => {
    setLoading(true);
    
    try {
      const response = await fetch(`${API}/coach/play/teaching/exit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          choice: choice
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        onChoice(choice, data);
      }
    } catch (error) {
      console.error("Error exiting lesson:", error);
    }
    
    setLoading(false);
  };

  return (
    <Card className="border-2 border-green-500/50 bg-green-500/5">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-green-500" />
          <CardTitle className="text-base">Lesson Complete!</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm">{completion.message}</p>
        
        {completion.summary && (
          <div className="p-3 rounded-lg bg-background border text-sm">
            {completion.summary}
          </div>
        )}
        
        {completion.key_ideas && completion.key_ideas.length > 0 && (
          <div className="text-xs">
            <p className="font-medium mb-1">Remember:</p>
            <ul className="list-disc list-inside text-muted-foreground space-y-0.5">
              {completion.key_ideas.map((idea, i) => (
                <li key={i}>{idea}</li>
              ))}
            </ul>
          </div>
        )}
        
        <div className="space-y-2 pt-2">
          {completion.options?.map((option) => (
            <Button
              key={option.id}
              variant={option.id === "continue_game" ? "default" : "outline"}
              className="w-full justify-start text-left h-auto py-3"
              onClick={() => handleChoice(option.id)}
              disabled={loading}
            >
              <div className="flex flex-col items-start">
                <span className="font-medium">{option.label}</span>
                <span className="text-xs text-muted-foreground mt-0.5">
                  {option.description}
                </span>
              </div>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export default { OpeningTeachingOffer, ActiveLessonPanel, LessonCompletePanel };
