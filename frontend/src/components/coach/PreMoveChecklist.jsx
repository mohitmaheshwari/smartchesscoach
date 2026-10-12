/**
 * PreMoveChecklist - Reinforces opening thinking habits
 * 
 * Shows contextual prompts before the player moves based on:
 * - Current opening principles that need attention
 * - Player's historical weak points
 * - Position-specific considerations
 */

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Brain, 
  CheckCircle2, 
  ChevronDown, 
  ChevronUp,
  Shield,
  Target,
  Lightbulb,
  X
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// Opening principles with their thinking prompts
const OPENING_PRINCIPLES = {
  castle_check: {
    question: "Can I castle this move?",
    explanation: "Castling keeps your king safe and connects your rooks",
    icon: "♚",
    phase: "opening",
    minMove: 4,
    maxMove: 12
  },
  development_check: {
    question: "Is there a piece I haven't developed yet?",
    explanation: "Develop all your minor pieces before starting an attack",
    icon: "♞",
    phase: "opening",
    minMove: 2,
    maxMove: 12
  },
  center_check: {
    question: "Am I fighting for the center?",
    explanation: "Control of central squares (e4, d4, e5, d5) gives your pieces more power",
    icon: "⊕",
    phase: "opening",
    minMove: 1,
    maxMove: 6
  },
  threat_check: {
    question: "What is my opponent threatening?",
    explanation: "Always look for your opponent's ideas before making your move",
    icon: "⚠️",
    phase: "all",
    minMove: 3,
    maxMove: 100
  },
  queen_safety: {
    question: "Is my queen safe? Can it be chased?",
    explanation: "Don't bring your queen out too early where it can be attacked",
    icon: "♛",
    phase: "opening",
    minMove: 1,
    maxMove: 8
  },
  king_safety: {
    question: "Is my king safe?",
    explanation: "Before any aggressive move, make sure your king isn't vulnerable",
    icon: "🛡️",
    phase: "all",
    minMove: 6,
    maxMove: 100
  }
};

// Map behavioral patterns to relevant checks
const WEAKNESS_TO_CHECK = {
  hope_chess: {
    id: "response_check",
    question: "What will my opponent do after this move?",
    explanation: "You tend to play moves without considering opponent responses",
    icon: "🔮",
    priority: "high",
    personal: true
  },
  impulsive_play: {
    id: "verify_check",
    question: "STOP - Have I double-checked this move?",
    explanation: "You sometimes move too quickly. Take a moment to verify.",
    icon: "⏸️",
    priority: "high",
    personal: true
  },
  tunnel_vision: {
    id: "whole_board_check",
    question: "Have I scanned the WHOLE board?",
    explanation: "You sometimes miss threats on the other side of the board",
    icon: "👁️",
    priority: "high",
    personal: true
  },
  hanging_pieces: {
    id: "blunder_check",
    question: "Does this leave anything undefended?",
    explanation: "Always verify no pieces become hanging after your move",
    icon: "🎯",
    priority: "high",
    personal: true
  },
  missed_tactics: {
    id: "tactics_check",
    question: "Are there any checks, captures, or threats?",
    explanation: "Look for forcing moves before playing quiet moves",
    icon: "⚡",
    priority: "high",
    personal: true
  },
  passive_play: {
    id: "activity_check",
    question: "Can I improve a piece or create a threat?",
    explanation: "Look for active moves, not just defensive ones",
    icon: "🚀",
    priority: "medium",
    personal: true
  },
  defensive_lapse: {
    id: "safety_check",
    question: "Is my position safe after this move?",
    explanation: "Check that your position remains solid after moving",
    icon: "🛡️",
    priority: "high",
    personal: true
  }
};

// Get relevant checks based on move number and game phase
const getRelevantChecks = (moveNumber, hasCastled, developedPieces, playerWeaknesses = []) => {
  const checks = [];
  
  // Priority 0: Player's specific behavioral weaknesses
  for (const weakness of playerWeaknesses) {
    const personalCheck = WEAKNESS_TO_CHECK[weakness];
    if (personalCheck && !checks.find(c => c.id === personalCheck.id)) {
      checks.push({
        ...personalCheck,
        reason: personalCheck.explanation
      });
    }
  }
  
  // Priority 1: Opening-specific weaknesses from player history
  if (playerWeaknesses.includes("castle_early") && !hasCastled && moveNumber >= 4 && moveNumber <= 12) {
    if (!checks.find(c => c.id === "castle_check")) {
      checks.push({
        id: "castle_check",
        ...OPENING_PRINCIPLES.castle_check,
        priority: "high",
        reason: "You often delay castling - this is a good habit to build!"
      });
    }
  }
  
  if (playerWeaknesses.includes("queen_out_early") && moveNumber <= 6) {
    checks.push({
      id: "queen_safety",
      ...OPENING_PRINCIPLES.queen_safety,
      priority: "high",
      reason: "Be careful with early queen moves - they can be punished"
    });
  }
  
  // Priority 2: Phase-appropriate checks
  if (moveNumber <= 10 && !hasCastled && moveNumber >= 5) {
    if (!checks.find(c => c.id === "castle_check")) {
      checks.push({
        id: "castle_check",
        ...OPENING_PRINCIPLES.castle_check,
        priority: "medium"
      });
    }
  }
  
  if (moveNumber <= 8 && developedPieces < 3) {
    checks.push({
      id: "development_check",
      ...OPENING_PRINCIPLES.development_check,
      priority: "medium"
    });
  }
  
  if (moveNumber <= 5) {
    checks.push({
      id: "center_check",
      ...OPENING_PRINCIPLES.center_check,
      priority: "low"
    });
  }
  
  // Always include threat check (but at lower priority)
  if (moveNumber >= 3) {
    checks.push({
      id: "threat_check",
      ...OPENING_PRINCIPLES.threat_check,
      priority: "low"
    });
  }
  
  // Limit to top 2-3 most relevant
  return checks.slice(0, 3);
};

const PreMoveChecklist = ({ 
  moveNumber, 
  hasCastled, 
  developedPieces = 0,
  playerWeaknesses = [],
  isPlayerTurn,
  onDismiss,
  compact = true  // Start minimized by default
}) => {
  const [expanded, setExpanded] = useState(!compact);
  const [checkedItems, setCheckedItems] = useState(new Set());
  const [dismissed, setDismissed] = useState(false);
  
  // Get relevant checks
  const checks = getRelevantChecks(moveNumber, hasCastled, developedPieces, playerWeaknesses);
  
  // Reset checked items when move changes
  useEffect(() => {
    setCheckedItems(new Set());
  }, [moveNumber]);
  
  // Don't show if not player's turn, no checks, or after opening
  if (!isPlayerTurn || checks.length === 0 || moveNumber > 15 || dismissed) {
    return null;
  }
  
  const handleCheck = (checkId) => {
    const newChecked = new Set(checkedItems);
    if (newChecked.has(checkId)) {
      newChecked.delete(checkId);
    } else {
      newChecked.add(checkId);
    }
    setCheckedItems(newChecked);
  };
  
  const handleDismiss = () => {
    setDismissed(true);
    if (onDismiss) onDismiss();
  };
  
  const allChecked = checks.every(c => checkedItems.has(c.id));
  
  // Minimized view
  if (!expanded) {
    return (
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-1 flex justify-center w-full"
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => setExpanded(true)}
          className="h-6 px-3 py-0 rounded-full bg-[#16202c]/90 border border-purple-500/30 hover:border-purple-400/50 hover:bg-purple-500/15 text-purple-300 text-[11px] font-mono font-medium flex items-center gap-1.5 shadow-sm transition-all cursor-pointer"
          data-testid="pre-move-checklist-expand"
        >
          <Brain className="w-3 h-3 text-purple-400" />
          <span>Before You Move</span>
          {checks.some(c => c.priority === "high") && (
            <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-500/60 text-amber-300 bg-amber-500/10">
              !
            </Badge>
          )}
          <ChevronDown className="w-3 h-3 text-purple-400" />
        </Button>
      </motion.div>
    );
  }
  
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: "auto" }}
        exit={{ opacity: 0, height: 0 }}
        className="mb-1 max-w-md mx-auto w-full"
      >
        <Card className="rounded-xl border border-purple-500/30 bg-[#16202c]/95 shadow-xl backdrop-blur-md text-slate-200" data-testid="pre-move-checklist">
          <CardContent className="p-2 sm:p-2.5">
            {/* Header */}
            <div className="flex items-center justify-between mb-1.5 px-0.5">
              <div className="flex items-center gap-1.5">
                <Brain className="w-3.5 h-3.5 text-purple-400" />
                <span className="text-xs font-semibold text-purple-300 font-mono tracking-wide">Before You Move</span>
              </div>
              <div className="flex items-center gap-0.5">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-5 w-5 p-0 text-slate-400 hover:text-white hover:bg-white/10 rounded cursor-pointer"
                  onClick={() => setExpanded(false)}
                  title="Collapse"
                >
                  <ChevronUp className="w-3 h-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-5 w-5 p-0 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded cursor-pointer"
                  onClick={handleDismiss}
                  title="Dismiss"
                >
                  <X className="w-3 h-3" />
                </Button>
              </div>
            </div>
            
            {/* Checklist Items */}
            <div className="space-y-1">
              {checks.map((check) => (
                <motion.div
                  key={check.id}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`flex items-center gap-2 p-1.5 px-2 rounded-lg cursor-pointer transition-colors ${
                    checkedItems.has(check.id) 
                      ? 'bg-emerald-500/15 border border-emerald-500/30' 
                      : check.priority === 'high'
                        ? 'bg-amber-500/15 border border-amber-500/30'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                  onClick={() => handleCheck(check.id)}
                  data-testid={`checklist-item-${check.id}`}
                >
                  {/* Checkbox */}
                  <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                    checkedItems.has(check.id)
                      ? 'border-emerald-500 bg-emerald-500'
                      : 'border-slate-500 bg-slate-900/50'
                  }`}>
                    {checkedItems.has(check.id) && (
                      <CheckCircle2 className="w-2.5 h-2.5 text-slate-950 font-bold" />
                    )}
                  </div>
                  
                  {/* Content */}
                  <div className="flex-1 min-w-0 flex items-center justify-between gap-1">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="text-sm shrink-0">{check.icon}</span>
                      <p className={`text-xs font-medium truncate ${
                        checkedItems.has(check.id) ? 'text-emerald-400 line-through opacity-80' : 'text-slate-200'
                      }`}>
                        {check.question}
                      </p>
                    </div>
                    {check.priority === 'high' && !checkedItems.has(check.id) && (
                      <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-500/50 text-amber-300 bg-amber-500/10 shrink-0">
                        Focus
                      </Badge>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
            
            {/* All checked message */}
            {allChecked && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-1.5 p-1 px-2 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                <p className="text-[11px] text-emerald-300 font-medium">
                  Good thinking! Now make your move.
                </p>
              </motion.div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
};

export default PreMoveChecklist;
