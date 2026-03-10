/**
 * Deep Coaching Session Modal
 * 
 * 6-step guided coaching flow:
 * 1. Pattern Summary (Authority)
 * 2. Guided Reflection (Discovery)
 * 3. Mirror Back Thinking
 * 4. Structured Teaching (A Mode)
 * 5. Assignment (Trainer Mode)
 * 6. Commitment Anchor
 * 
 * Tone: Calm authority, slight firmness. Indian coaching rhythm.
 * Duration: 3-4 minutes max.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import LichessBoard from "@/components/LichessBoard";
import {
  X,
  ChevronRight,
  Brain,
  Target,
  Lightbulb,
  Dumbbell,
  CheckCircle2,
  TrendingUp,
  TrendingDown,
  Loader2,
  AlertTriangle
} from "lucide-react";

const STEP_ICONS = {
  1: Brain,
  2: Target,
  3: Lightbulb,
  4: Brain,
  5: Dumbbell,
  6: CheckCircle2
};

const STEP_TITLES = {
  1: "Pattern Summary",
  2: "Reflection",
  3: "Understanding",
  4: "Key Principle",
  5: "Assignment",
  6: "Commitment"
};

const DeepSessionModal = ({ isOpen, onClose, onComplete }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [sessionId, setSessionId] = useState(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [content, setContent] = useState(null);
  const [selectedOption, setSelectedOption] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      startSession();
    }
  }, [isOpen]);

  const startSession = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/coach/deep-session/start`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trigger: "manual" })
      });

      if (res.ok) {
        const data = await res.json();
        setSessionId(data.session_id);
        setCurrentStep(data.current_step);
        setContent(data.content);
      }
    } catch (err) {
      console.error("Error starting deep session:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAdvance = async () => {
    if (!sessionId) return;
    
    try {
      setSubmitting(true);
      
      // Special handling for step 2 (reflection)
      if (currentStep === 2 && selectedOption) {
        const res = await fetch(`${API}/coach/deep-session/${sessionId}/reflection`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer: selectedOption })
        });
        
        if (res.ok) {
          const data = await res.json();
          setCurrentStep(data.current_step);
          setContent(data.content);
          setSelectedOption(null);
        }
      }
      // Step 6 - complete session
      else if (currentStep === 6) {
        const res = await fetch(`${API}/coach/deep-session/${sessionId}/complete`, {
          method: "POST",
          credentials: "include"
        });
        
        if (res.ok) {
          onComplete?.();
          onClose();
        }
      }
      // Normal advance
      else {
        const res = await fetch(`${API}/coach/deep-session/${sessionId}/advance`, {
          method: "POST",
          credentials: "include"
        });
        
        if (res.ok) {
          const data = await res.json();
          setCurrentStep(data.current_step);
          setContent(data.content);
        }
      }
    } catch (err) {
      console.error("Error advancing session:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const renderStepContent = () => {
    if (!content) return null;

    switch (currentStep) {
      case 1:
        return <SummaryStep content={content} />;
      case 2:
        return (
          <ReflectionStep 
            content={content} 
            selectedOption={selectedOption}
            onSelect={setSelectedOption}
          />
        );
      case 3:
        return <MirrorStep content={content} />;
      case 4:
        return <TeachingStep content={content} />;
      case 5:
        return <AssignmentStep content={content} />;
      case 6:
        return <CommitmentStep content={content} />;
      default:
        return null;
    }
  };

  const canAdvance = () => {
    if (currentStep === 2) {
      return selectedOption !== null;
    }
    return true;
  };

  if (!isOpen) return null;

  const StepIcon = STEP_ICONS[currentStep] || Brain;
  const progress = (currentStep / 6) * 100;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="relative w-full max-w-lg mx-4 bg-card rounded-2xl border border-border shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <StepIcon className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">
                Step {currentStep} of 6
              </p>
              <h3 className="font-medium">{STEP_TITLES[currentStep]}</h3>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Progress bar */}
        <div className="px-4 pt-2">
          <Progress value={progress} className="h-1" />
        </div>

        {/* Content */}
        <div className="p-6 min-h-[300px]">
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                {renderStepContent()}
              </motion.div>
            </AnimatePresence>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border">
          <Button 
            onClick={handleAdvance}
            disabled={!canAdvance() || submitting}
            className="w-full gap-2"
          >
            {submitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : currentStep === 6 ? (
              <>
                <CheckCircle2 className="w-4 h-4" />
                I'm Ready
              </>
            ) : (
              <>
                {content?.cta || "Continue"}
                <ChevronRight className="w-4 h-4" />
              </>
            )}
          </Button>
        </div>
      </motion.div>
    </div>
  );
};

// ============================================================================
// STEP COMPONENTS
// ============================================================================

const SummaryStep = ({ content }) => {
  const TrendIcon = content.trend === "improving" ? TrendingUp : 
                    content.trend === "declining" ? TrendingDown : Target;
  const trendColor = content.trend === "improving" ? "text-green-400" :
                     content.trend === "declining" ? "text-red-400" : "text-amber-400";

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{content.title}</h2>
      
      {/* Theme badge */}
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="border-primary/50 text-primary">
          {content.theme}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {content.games_analyzed} games analyzed
        </span>
      </div>

      {/* Observations */}
      <div className="space-y-3 py-2">
        {content.observations?.map((obs, idx) => (
          <p key={idx} className="text-sm text-foreground leading-relaxed">
            {obs}
          </p>
        ))}
      </div>

      {/* Trend indicator */}
      <div className={`flex items-center gap-2 p-3 rounded-lg bg-muted/50`}>
        <TrendIcon className={`w-4 h-4 ${trendColor}`} />
        <span className="text-sm capitalize">{content.trend}</span>
      </div>
    </div>
  );
};

const ReflectionStep = ({ content, selectedOption, onSelect }) => {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{content.title}</h2>
      <p className="text-foreground">{content.question}</p>
      <p className="text-xs text-muted-foreground">{content.instruction}</p>
      
      <div className="space-y-2 pt-2">
        {content.options?.map((option) => (
          <button
            key={option.id}
            onClick={() => onSelect(option.id)}
            className={`w-full p-3 text-left rounded-lg border transition-colors ${
              selectedOption === option.id
                ? "border-primary bg-primary/10 text-foreground"
                : "border-border hover:border-primary/50 text-muted-foreground hover:text-foreground"
            }`}
          >
            <span className="text-sm">{option.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

const MirrorStep = ({ content }) => {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{content.title}</h2>
      <div className="p-4 rounded-xl bg-primary/5 border border-primary/20">
        <p className="text-foreground leading-relaxed">
          {content.response}
        </p>
      </div>
    </div>
  );
};

const TeachingStep = ({ content }) => {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{content.title}</h2>
      
      {/* Principle */}
      <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
        <p className="text-sm font-medium text-amber-300 mb-1">Principle</p>
        <p className="text-foreground">{content.principle}</p>
      </div>

      {/* Rule */}
      <div className="p-4 rounded-xl bg-primary/10 border border-primary/30">
        <p className="text-sm font-medium text-primary mb-1">Your Rule</p>
        <p className="text-foreground font-medium">{content.rule}</p>
      </div>

      {/* Position if available */}
      {content.position?.fen && (
        <div className="mt-4">
          <p className="text-xs text-muted-foreground mb-2">
            {content.position.label || "Critical moment"}
          </p>
          <div className="w-48 h-48 mx-auto">
            <LichessBoard 
              fen={content.position.fen}
              viewOnly={true}
              interactive={false}
            />
          </div>
        </div>
      )}

      {/* Explanation */}
      <p className="text-sm text-muted-foreground">
        {content.explanation}
      </p>
    </div>
  );
};

const AssignmentStep = ({ content }) => {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{content.title}</h2>
      
      <div className="p-6 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 border border-primary/30 text-center">
        <Dumbbell className="w-10 h-10 text-primary mx-auto mb-3" />
        <p className="font-medium text-lg">{content.assignment_text}</p>
        <p className="text-sm text-muted-foreground mt-2">
          Duration: {content.duration}
        </p>
      </div>
    </div>
  );
};

const CommitmentStep = ({ content }) => {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{content.title}</h2>
      
      <div className="p-6 rounded-xl bg-gradient-to-br from-green-500/10 to-green-500/5 border border-green-500/30">
        <CheckCircle2 className="w-10 h-10 text-green-400 mx-auto mb-3" />
        <p className="text-center text-lg font-medium">
          {content.message}
        </p>
      </div>

      <div className="p-4 rounded-lg bg-muted/50 mt-4">
        <p className="text-xs text-muted-foreground mb-1">Your focus rule:</p>
        <p className="font-medium text-primary">"{content.micro_rule}"</p>
      </div>
    </div>
  );
};

export default DeepSessionModal;
