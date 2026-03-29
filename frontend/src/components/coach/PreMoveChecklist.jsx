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
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-3"
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => setExpanded(true)}
          className="w-full justify-between bg-purple-50 border-purple-200 hover:bg-purple-100 text-purple-700"
          data-testid="pre-move-checklist-expand"
        >
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4" />
            <span className="text-xs">Pre-Move Checklist</span>
            {checks.some(c => c.priority === "high") && (
              <Badge variant="outline" className="text-[10px] px-1 py-0 border-amber-500 text-amber-400">
                !
              </Badge>
            )}
          </div>
          <ChevronDown className="w-4 h-4" />
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
        className="mb-3"
      >
        <Card className="border-purple-200 bg-purple-50" data-testid="pre-move-checklist">
          <CardContent className="p-3">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-purple-700">Before You Move</span>
              </div>
              <div className="flex items-center gap-1">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-6 w-6 p-0"
                  onClick={() => setExpanded(false)}
                >
                  <ChevronUp className="w-3 h-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                  onClick={handleDismiss}
                >
                  <X className="w-3 h-3" />
                </Button>
              </div>
            </div>
            
            {/* Checklist Items */}
            <div className="space-y-2">
              {checks.map((check) => (
                <motion.div
                  key={check.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                    checkedItems.has(check.id) 
                      ? 'bg-green-500/10 border border-green-500/30' 
                      : check.priority === 'high'
                        ? 'bg-amber-500/10 border border-amber-500/30'
                        : 'bg-background/50 border border-border/50'
                  }`}
                  onClick={() => handleCheck(check.id)}
                  data-testid={`checklist-item-${check.id}`}
                >
                  {/* Checkbox */}
                  <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 ${
                    checkedItems.has(check.id)
                      ? 'border-green-500 bg-green-500'
                      : 'border-muted-foreground'
                  }`}>
                    {checkedItems.has(check.id) && (
                      <CheckCircle2 className="w-3 h-3 text-white" />
                    )}
                  </div>
                  
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-base">{check.icon}</span>
                      <p className={`text-sm font-medium ${
                        checkedItems.has(check.id) ? 'text-green-400 line-through' : ''
                      }`}>
                        {check.question}
                      </p>
                    </div>
                    {check.reason && (
                      <p className="text-xs text-amber-400 mt-0.5 flex items-center gap-1">
                        <Lightbulb className="w-3 h-3" />
                        {check.reason}
                      </p>
                    )}
                  </div>
                  
                  {/* Priority Badge */}
                  {check.priority === 'high' && !checkedItems.has(check.id) && (
                    <Badge variant="outline" className="text-[10px] border-amber-500 text-amber-400 flex-shrink-0">
                      Focus
                    </Badge>
                  )}
                </motion.div>
              ))}
            </div>
            
            {/* All checked message */}
            {allChecked && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-2 p-2 rounded bg-green-500/10 border border-green-500/30"
              >
                <p className="text-xs text-green-400 flex items-center gap-2">
                  <CheckCircle2 className="w-3 h-3" />
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
