/**
 * OpeningTeachingPanel.jsx - Interactive Opening Lesson UI
 * 
 * Displays when coach detects an opening and offers to teach.
 * Handles the interactive lesson flow where user plays along.
 */

import { useState, useEffect } from "react";
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
  Lightbulb
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

  // Safety check - if offer is invalid, don't render
  if (!offer || !offer.opening_name) {
    return null;
  }

  // Default options if not provided
  const options = offer.options || [
    { id: "learn_trap", label: "Learn a trap", description: "Interactive trap lesson" },
    { id: "learn_main_line", label: "Learn the main line", description: "Step-by-step opening theory" },
    { id: "just_play", label: "Just play", description: "Continue without lesson" }
  ];

  const handleOption = async (optionId) => {
    setLoading(true);
    
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
    } else {
      // Start a lesson
      try {
        const response = await fetch(`${API}/coach/play/teaching/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ 
            session_id: sessionId,
            lesson_type: optionId 
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

  return (
    <Card className="border-2 border-primary/50 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-primary" />
          <CardTitle className="text-base">{offer.opening_name}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm">{offer.message}</p>
        
        {offer.trap_name && (
          <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/30">
            <Target className="w-3 h-3 mr-1" />
            Trap available: {offer.trap_name}
          </Badge>
        )}
        
        <div className="space-y-2">
          {options.map((option) => (
            <Button
              key={option.id}
              variant={option.id === "learn_trap" ? "default" : "outline"}
              className="w-full justify-start text-left h-auto py-3"
              onClick={() => handleOption(option.id)}
              disabled={loading}
              data-testid={`teaching-option-${option.id}`}
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
