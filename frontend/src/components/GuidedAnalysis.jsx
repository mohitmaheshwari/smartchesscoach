/**
 * GuidedAnalysis Component
 * 
 * Provides a step-by-step, coach-led analysis experience.
 * Instead of showing all information at once, it guides the user
 * through critical moments one at a time.
 * 
 * This is what elevates the Lab page from 7/10 to 9.5/10.
 */

import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { 
  ChevronRight, 
  ChevronLeft, 
  Brain, 
  Target, 
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  ArrowRight,
  Eye,
  SkipForward,
  Trophy,
  TrendingUp,
  MessageSquare,
  ThumbsDown,
  Sparkles,
  Clock,
  Shield,
  BookOpen,
  Tag
} from "lucide-react";
import InlineFeedbackButton from "@/components/InlineFeedbackButton";

// Coach phrases - More varied and contextual
const COACH_INTROS = [
  "Alright, let's break this game down together.",
  "I've spotted some key moments. Let's discuss them one by one.",
  "Ready? I'll walk you through the critical positions.",
  "There's a lot to learn here. Let's go step by step.",
  "Let me show you what I noticed in this game."
];

const COACH_TRANSITION = [
  "Good. Moving on to the next one.",
  "Got it? Let's look at another position.",
  "Okay, here's the next moment to consider.",
  "Next up - pay attention to this one.",
  "Alright, let's see what happened here."
];

const COACH_BLUNDER = [
  "This move changed the whole game. Here's why:",
  "This is where things started going downhill.",
  "The critical mistake - let's understand it.",
  "This one's important. Take a moment to look at the position.",
  "Here's the key turning point."
];

const COACH_MISTAKE = [
  "Not the best move here. Let me explain.",
  "This could have been better. See why?",
  "A small slip - but patterns like this add up.",
  "This move wasn't ideal. Here's what you missed.",
  "Let's look at what was better here."
];

const COACH_ENCOURAGEMENT = [
  "Don't worry - recognizing the mistake is the first step.",
  "Every strong player has made this exact mistake before.",
  "This is exactly why we review games - to learn.",
  "Good that you're studying this. That's how you improve.",
  "One game at a time. You're doing the right thing by reviewing."
];

const COACH_CONCLUSION = [
  "That covers the main moments. Take a few seconds to think about what we discussed.",
  "Remember these patterns - you'll see them again.",
  "Good session. Keep these lessons in mind for your next game.",
  "That's it for this game. The key is to not repeat these mistakes.",
  "Nice work reviewing. Reflection is how you get better."
];

// Pattern-specific tips
const PATTERN_TIPS = {
  "TACTICAL_MISS": "Look for forcing moves: checks, captures, and threats.",
  "PIECE_SAFETY": "Before moving, always check: is anything hanging?",
  "CALCULATION": "Try calculating one move deeper next time.",
  "TIME_PRESSURE": "Time trouble? Develop a pre-move routine.",
  "POSITIONAL": "Think about piece activity and king safety first.",
  "ENDGAME": "In endgames, activate your king early.",
  "OPENING": "Stick to your opening principles until you're comfortable.",
  "default": "Stay focused and take your time on critical moves."
};

// Helper to pick random phrase
const randomPhrase = (phrases) => phrases[Math.floor(Math.random() * phrases.length)];

// Format tag label for display
const formatTagLabel = (tagId) => {
  if (!tagId) return "";
  return tagId
    .replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

// Get badge color for tag category
const getTagColor = (tags) => {
  if (!tags?.phase) return "bg-muted";
  switch(tags.phase) {
    case "opening": return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    case "middlegame": return "bg-purple-500/20 text-purple-400 border-purple-500/30";
    case "endgame": return "bg-amber-500/20 text-amber-400 border-amber-500/30";
    default: return "bg-muted text-muted-foreground";
  }
};

// Get pattern category from classification
const getPatternCategory = (classification_v2) => {
  if (!classification_v2) return "default";
  const gap = classification_v2.primary_gap || "";
  if (gap.includes("TACTIC") || gap.includes("FORK") || gap.includes("PIN")) return "TACTICAL_MISS";
  if (gap.includes("SAFETY") || gap.includes("HANGING")) return "PIECE_SAFETY";
  if (gap.includes("CALCULATION")) return "CALCULATION";
  if (gap.includes("TIME")) return "TIME_PRESSURE";
  if (gap.includes("POSITION")) return "POSITIONAL";
  if (gap.includes("ENDGAME")) return "ENDGAME";
  if (gap.includes("OPENING")) return "OPENING";
  return "default";
};

export default function GuidedAnalysis({
  criticalMoments = [],
  currentMoveIndex,
  onNavigateToMove,
  onComplete,
  userColor,
  gameId,
  onFeedback,
  onOpenTheory // New: callback to open theory module
}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [showExplanation, setShowExplanation] = useState(false);
  const [seenMoments, setSeenMoments] = useState(new Set());
  const [coachPhrase, setCoachPhrase] = useState("");
  const [showTip, setShowTip] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(false);
  
  // Filter to only show significant moments
  const moments = useMemo(() => 
    criticalMoments.filter(m => 
      m.category === "blunder" || 
      m.category === "mistake" || 
      (m.cp_loss && Math.abs(m.cp_loss) > 50)
    ), [criticalMoments]);
  
  const currentMoment = moments[currentStep];
  const progress = moments.length > 0 ? ((currentStep + 1) / moments.length) * 100 : 0;
  const isLastStep = currentStep >= moments.length - 1;
  
  // Get contextual tip for current pattern
  const currentTip = useMemo(() => {
    if (!currentMoment) return PATTERN_TIPS.default;
    const category = getPatternCategory(currentMoment.classification_v2);
    return PATTERN_TIPS[category] || PATTERN_TIPS.default;
  }, [currentMoment]);
  
  useEffect(() => {
    setCoachPhrase(randomPhrase(COACH_INTROS));
  }, []);
  
  useEffect(() => {
    if (currentMoment && onNavigateToMove) {
      onNavigateToMove(currentMoment.move_number - 1);
    }
  }, [currentStep, currentMoment, onNavigateToMove]);
  
  const handleNext = () => {
    setSeenMoments(prev => new Set([...prev, currentStep]));
    setShowExplanation(false);
    setShowTip(false);
    
    if (isLastStep) {
      setCoachPhrase(randomPhrase(COACH_CONCLUSION));
      setSessionComplete(true);
    } else {
      setCurrentStep(prev => prev + 1);
      setCoachPhrase(randomPhrase(COACH_TRANSITION));
    }
  };
  
  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
      setShowExplanation(false);
      setShowTip(false);
    }
  };
  
  const handleShowExplanation = () => {
    setShowExplanation(true);
    // Show coach encouragement after revealing explanation
    setTimeout(() => {
      setCoachPhrase(randomPhrase(COACH_ENCOURAGEMENT));
    }, 500);
  };
  
  const handleShowTip = () => {
    setShowTip(true);
  };

  // Session complete view
  if (sessionComplete) {
    return (
      <div className="space-y-4" data-testid="guided-analysis-complete">
        <Card className="bg-gradient-to-br from-green-900/30 to-emerald-900/20 border-green-700/30">
          <CardContent className="p-6 text-center">
            <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
              <Trophy className="w-8 h-8 text-green-400" />
            </div>
            <h3 className="text-xl font-bold text-green-400 mb-2">Session Complete!</h3>
            <p className="text-sm text-muted-foreground mb-4">{coachPhrase}</p>
            
            <div className="flex items-center justify-center gap-4 text-sm mb-6">
              <div className="flex items-center gap-1">
                <Target className="w-4 h-4 text-primary" />
                <span>{moments.length} moments reviewed</span>
              </div>
              <div className="flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span>{seenMoments.size} understood</span>
              </div>
            </div>
            
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                onClick={() => {
                  setCurrentStep(0);
                  setSessionComplete(false);
                  setSeenMoments(new Set());
                  setCoachPhrase(randomPhrase(COACH_INTROS));
                }}
                className="flex-1"
              >
                <ArrowRight className="w-4 h-4 mr-1 rotate-180" />
                Review Again
              </Button>
              <Button 
                onClick={onComplete}
                className="flex-1"
              >
                <Sparkles className="w-4 h-4 mr-1" />
                See Full Analysis
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  // Clean game view
  if (moments.length === 0) {
    return (
      <Card className="bg-gradient-to-br from-green-900/20 to-emerald-900/10 border-green-800/30">
        <CardContent className="p-6 text-center">
          <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-3">
            <CheckCircle2 className="w-6 h-6 text-green-500" />
          </div>
          <h3 className="text-lg font-bold text-green-400 mb-1">Clean game!</h3>
          <p className="text-sm text-muted-foreground">
            No major mistakes to review. Well played!
          </p>
        </CardContent>
      </Card>
    );
  }
  
  return (
    <div className="space-y-4" data-testid="guided-analysis">
      {/* Progress Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center">
            <Brain className="w-3 h-3 text-primary" />
          </div>
          <span className="text-sm font-medium">
            Moment {currentStep + 1} of {moments.length}
          </span>
        </div>
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={onComplete}
          className="text-xs text-muted-foreground hover:text-foreground"
          data-testid="exit-guide-btn"
        >
          <SkipForward className="w-3 h-3 mr-1" />
          Full Analysis
        </Button>
      </div>
      
      <Progress value={progress} className="h-1.5 bg-muted/50" />
      
      {/* Coach Message Card */}
      <Card className="bg-gradient-to-r from-primary/5 to-primary/10 border-primary/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
              <MessageSquare className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-xs font-medium text-primary/80 mb-0.5">Your Coach</p>
              <p className="text-sm">{coachPhrase}</p>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Current Moment Card */}
      {currentMoment && (
        <Card className={`border-l-4 transition-all ${
          currentMoment.category === "blunder" 
            ? "border-l-red-500 bg-red-900/10" 
            : currentMoment.category === "mistake"
            ? "border-l-orange-500 bg-orange-900/10"
            : "border-l-yellow-500 bg-yellow-900/10"
        }`}>
          <CardContent className="p-4">
            {/* Move Info Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Badge 
                  variant={currentMoment.category === "blunder" ? "destructive" : "secondary"}
                  className="font-normal"
                >
                  {currentMoment.category === "blunder" ? (
                    <AlertTriangle className="w-3 h-3 mr-1" />
                  ) : (
                    <Clock className="w-3 h-3 mr-1" />
                  )}
                  Move {currentMoment.move_number}
                </Badge>
                <span className="font-mono text-lg font-bold">
                  {currentMoment.move_san}
                </span>
              </div>
              {currentMoment.cp_loss && (
                <Badge variant="outline" className="text-xs font-mono">
                  {currentMoment.cp_loss > 0 ? '-' : '+'}{Math.abs(currentMoment.cp_loss)} cp
                </Badge>
              )}
            </div>
            
            {/* Question/Prompt - Before explanation is shown */}
            {!showExplanation && (
              <div className="space-y-4">
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-sm font-medium flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-primary" />
                    Think about this position:
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {currentMoment.category === "blunder" 
                      ? randomPhrase(COACH_BLUNDER)
                      : randomPhrase(COACH_MISTAKE)
                    }
                  </p>
                </div>
                
                <Button 
                  onClick={handleShowExplanation}
                  className="w-full"
                  data-testid="show-explanation-btn"
                >
                  <Eye className="w-4 h-4 mr-2" />
                  Reveal What Happened
                </Button>
              </div>
            )}
            
            {/* Explanation - After button is clicked */}
            {showExplanation && (
              <div className="space-y-4">
                {/* Tags Section - Show pattern tags when available */}
                {currentMoment.tags && currentMoment.tags.primary_tag && (
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge 
                      variant="outline" 
                      className={`text-xs ${getTagColor(currentMoment.tags)}`}
                    >
                      <Tag className="w-3 h-3 mr-1" />
                      {formatTagLabel(currentMoment.tags.primary_tag)}
                    </Badge>
                    {currentMoment.tags.phase && (
                      <Badge variant="outline" className="text-xs bg-muted/50">
                        {currentMoment.tags.phase}
                      </Badge>
                    )}
                  </div>
                )}
                
                {/* Main Explanation */}
                <div className="p-4 bg-background/60 rounded-lg border border-border/50">
                  <div className="flex items-start gap-3">
                    <Lightbulb className="w-5 h-5 text-yellow-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      {currentMoment.classification_v2?.primary_gap && (
                        <p className="font-medium text-primary text-sm mb-2">
                          {currentMoment.classification_v2.primary_gap.replace(/_/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase())}
                        </p>
                      )}
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {currentMoment.classification_v2?.coaching_focus || 
                         currentMoment.coach_explanation ||
                         currentMoment.explanation ||
                         currentMoment.insight?.what_best_move_achieves ||
                         "This move allowed your opponent to gain a significant advantage."}
                      </p>
                      
                      {currentMoment.best_move && (
                        <div className="mt-3 pt-3 border-t border-border/50">
                          <p className="text-sm flex items-center gap-2">
                            <Shield className="w-4 h-4 text-green-500" />
                            <span className="text-muted-foreground">Better was:</span>
                            <span className="font-mono font-bold text-green-400">{currentMoment.best_move}</span>
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                
                {/* Theory Link - Learn More */}
                {currentMoment.recommended_theory?.primary_theory && (
                  <div 
                    className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20 cursor-pointer hover:bg-blue-500/15 transition-colors"
                    onClick={() => onOpenTheory?.(currentMoment.recommended_theory.primary_theory)}
                    data-testid="theory-link"
                  >
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-blue-400" />
                      <div className="flex-1">
                        <p className="text-xs font-medium text-blue-400">Learn about this pattern</p>
                        <p className="text-sm font-medium text-blue-300">
                          {currentMoment.recommended_theory.primary_theory.name}
                        </p>
                        <p className="text-xs text-blue-400/70 mt-0.5">
                          {currentMoment.recommended_theory.primary_theory.key_insight}
                        </p>
                      </div>
                      <ArrowRight className="w-4 h-4 text-blue-400" />
                    </div>
                  </div>
                )}
                
                {/* Quick Tip - Collapsible */}
                {!showTip ? (
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={handleShowTip}
                    className="w-full text-xs text-muted-foreground hover:text-foreground"
                  >
                    <TrendingUp className="w-3 h-3 mr-1" />
                    Show improvement tip
                  </Button>
                ) : (
                  <div className="p-3 bg-primary/5 rounded-lg border border-primary/20">
                    <p className="text-xs font-medium text-primary/80 mb-1 flex items-center gap-1">
                      <TrendingUp className="w-3 h-3" />
                      Quick Tip
                    </p>
                    <p className="text-sm text-muted-foreground">{currentTip}</p>
                  </div>
                )}
                
                {/* Feedback Button */}
                {onFeedback && (
                  <div className="flex justify-end">
                    <InlineFeedbackButton
                      context={{
                        explanation: currentMoment.classification_v2?.coaching_focus || currentMoment.explanation || "",
                        positionFen: currentMoment.fen_before || "",
                        movePlayed: currentMoment.move_san || currentMoment.move || "",
                        bestMove: currentMoment.best_move || "",
                        classification: currentMoment.classification_v2?.primary_gap || "unknown",
                        evalBefore: currentMoment.eval_before || 0,
                        evalAfter: currentMoment.eval_after || 0,
                        gameId: gameId,
                        moveNumber: currentMoment.move_number
                      }}
                      onClick={onFeedback}
                    />
                  </div>
                )}
                
                {/* Navigation Buttons */}
                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    onClick={handlePrevious}
                    disabled={currentStep === 0}
                    className="flex-1"
                    data-testid="prev-moment-btn"
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    Previous
                  </Button>
                  <Button
                    onClick={handleNext}
                    className="flex-1"
                    data-testid="next-moment-btn"
                  >
                    {isLastStep ? "Finish" : "Next"}
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
      
      {/* Quick Jump - More compact */}
      <div className="flex flex-wrap gap-1.5">
        {moments.map((moment, idx) => (
          <button
            key={idx}
            onClick={() => {
              setCurrentStep(idx);
              setShowExplanation(false);
              setShowTip(false);
            }}
            className={`w-7 h-7 rounded-md text-xs font-medium transition-all ${
              idx === currentStep
                ? "bg-primary text-primary-foreground ring-2 ring-primary/30"
                : seenMoments.has(idx)
                ? "bg-green-500/20 text-green-400 border border-green-500/30"
                : "bg-muted/50 hover:bg-muted text-muted-foreground"
            }`}
            title={`Move ${moment.move_number}: ${moment.move_san}`}
            data-testid={`jump-moment-${idx}`}
          >
            {moment.move_number}
          </button>
        ))}
      </div>
    </div>
  );
}
