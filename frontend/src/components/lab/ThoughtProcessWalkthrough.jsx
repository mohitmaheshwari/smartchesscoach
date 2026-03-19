/**
 * ThoughtProcessWalkthrough - Shows HOW to think through a position
 * 
 * Integrates with the Thinking Coach service to display:
 * - Step-by-step thinking phases
 * - Questions to ask yourself
 * - What to observe at each step
 * - The conclusion and key takeaway
 */

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import {
  Brain,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Shield,
  Target,
  Zap,
  Eye,
  Lightbulb,
  Loader2,
  HelpCircle
} from "lucide-react";

const PHASE_ICONS = {
  assess_threats: Target,
  check_king_safety: Shield,
  identify_targets: Zap,
  calculate_tactics: Zap,
  evaluate_structure: Brain,
  choose_plan: Lightbulb,
  verify_move: CheckCircle2
};

const PHASE_LABELS = {
  assess_threats: "Check Threats",
  check_king_safety: "King Safety",
  identify_targets: "Find Targets",
  calculate_tactics: "Calculate",
  evaluate_structure: "Pawn Structure",
  choose_plan: "Choose Plan",
  verify_move: "Verify Move"
};

const ThoughtProcessWalkthrough = ({
  fen,
  bestMove,
  playedMove = null,
  compact = false,
  autoFetch = true
}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(!compact);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (autoFetch && fen && bestMove) {
      fetchWalkthrough();
    }
  }, [fen, bestMove, autoFetch]);

  const fetchWalkthrough = async () => {
    if (!fen || !bestMove) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/thinking-coach/walkthrough`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen,
          best_move: bestMove,
          played_move: playedMove
        })
      });
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (e) {
      console.error("Failed to fetch thought process:", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
        <p className="text-sm">Generating thought process...</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { walkthrough, conclusion, key_takeaway, phase, focus } = data;

  // Minimized view
  if (compact && !expanded) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setExpanded(true)}
        className="w-full justify-between bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/20 text-blue-300"
        data-testid="thought-process-expand"
      >
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4" />
          <span className="text-xs">How to Think Here</span>
        </div>
        <ChevronDown className="w-4 h-4" />
      </Button>
    );
  }

  return (
    <Card className="border-blue-500/30 bg-blue-500/5" data-testid="thought-process-walkthrough">
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-blue-300">How Strong Players Think</span>
            <Badge variant="outline" className="text-[10px] border-blue-500/50 text-blue-400">
              {phase}
            </Badge>
          </div>
          {compact && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={() => setExpanded(false)}
            >
              <ChevronUp className="w-3 h-3" />
            </Button>
          )}
        </div>

        {/* Focus area */}
        <p className="text-xs text-muted-foreground mb-4">
          Focus on: <span className="text-blue-300">{focus}</span>
        </p>

        {/* Thinking Steps */}
        <div className="space-y-3 mb-4">
          {walkthrough.map((step, idx) => {
            const PhaseIcon = PHASE_ICONS[step.phase] || HelpCircle;
            const isActive = idx === currentStep;
            const isCompleted = idx < currentStep;

            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.1 }}
                className={`p-3 rounded-lg border transition-colors cursor-pointer ${
                  isActive 
                    ? 'bg-blue-500/20 border-blue-500/50' 
                    : isCompleted 
                      ? 'bg-green-500/10 border-green-500/30' 
                      : 'bg-background/50 border-border/50'
                }`}
                onClick={() => setCurrentStep(idx)}
                data-testid={`thinking-step-${idx}`}
              >
                {/* Step Header */}
                <div className="flex items-center gap-2 mb-2">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                    isActive ? 'bg-blue-500' : isCompleted ? 'bg-green-500' : 'bg-slate-700'
                  }`}>
                    {isCompleted ? (
                      <CheckCircle2 className="w-3 h-3 text-white" />
                    ) : (
                      <PhaseIcon className="w-3 h-3 text-white" />
                    )}
                  </div>
                  <span className={`text-sm font-medium ${
                    isActive ? 'text-blue-300' : isCompleted ? 'text-green-300' : 'text-muted-foreground'
                  }`}>
                    {PHASE_LABELS[step.phase] || step.phase}
                  </span>
                </div>

                {/* Question */}
                <p className="text-sm font-medium mb-1 text-foreground">
                  "{step.question}"
                </p>

                {/* Observation (shown when active or completed) */}
                {(isActive || isCompleted) && step.observation && (
                  <p className="text-xs text-muted-foreground mt-2 pl-8">
                    💭 {step.observation}
                  </p>
                )}

                {/* Follow-up (shown when active) */}
                {isActive && step.follow_up && (
                  <p className="text-xs text-blue-300 mt-2 pl-8 italic">
                    → {step.follow_up}
                  </p>
                )}
              </motion.div>
            );
          })}
        </div>

        {/* Navigation */}
        <div className="flex gap-2 mb-4">
          <Button
            variant="outline"
            size="sm"
            disabled={currentStep === 0}
            onClick={() => setCurrentStep(prev => prev - 1)}
            className="flex-1"
          >
            Previous
          </Button>
          <Button
            size="sm"
            disabled={currentStep === walkthrough.length - 1}
            onClick={() => setCurrentStep(prev => prev + 1)}
            className="flex-1"
          >
            Next Step
          </Button>
        </div>

        {/* Conclusion */}
        {conclusion && (
          <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/30 mb-3">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              <span className="text-xs font-medium text-green-400">Conclusion</span>
            </div>
            <p className="text-sm text-green-200">{conclusion}</p>
          </div>
        )}

        {/* Key Takeaway */}
        {key_takeaway && (
          <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30">
            <div className="flex items-center gap-2 mb-1">
              <Lightbulb className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-medium text-purple-400">Key Takeaway</span>
            </div>
            <p className="text-sm text-purple-200">{key_takeaway}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ThoughtProcessWalkthrough;
