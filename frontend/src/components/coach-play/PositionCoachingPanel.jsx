/**
 * PositionCoachingPanel - Shows position-based coaching suggestions
 * 
 * Displays strategic plans and tactical features based on the current
 * position's pawn structure and tactical patterns.
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Target, 
  ChevronDown, 
  ChevronUp,
  Lightbulb,
  AlertTriangle,
  Zap,
  X,
  BookOpen,
  Map
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const PositionCoachingPanel = ({ 
  coaching,
  onDismiss,
  onLearnPlan,
  onShowTactics,
  onCheckSafety
}) => {
  const [expanded, setExpanded] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState(null);
  
  if (!coaching) return null;
  
  const {
    structure_name,
    structure_type,
    game_phase,
    main_idea,
    key_characteristics = [],
    strategic_plans = [],
    tactical_features = {},
    tactical_insights = [],
    teaching_points = [],
    critical_squares = [],
    options = []
  } = coaching;
  
  const handleOptionClick = (option) => {
    switch (option.id) {
      case "learn_strategic_plan":
        if (onLearnPlan && strategic_plans.length > 0) {
          onLearnPlan(strategic_plans[0]);
        }
        break;
      case "see_tactical_themes":
        if (onShowTactics) {
          onShowTactics(tactical_insights);
        }
        break;
      case "check_piece_safety":
        if (onCheckSafety) {
          onCheckSafety(tactical_features);
        }
        break;
      case "just_play":
        if (onDismiss) {
          onDismiss();
        }
        break;
      default:
        // Handle insight options
        if (option.id.startsWith("insight_")) {
          const insight = tactical_insights.find(i => `insight_${i.type}` === option.id);
          if (insight) {
            setSelectedPlan({
              name: insight.type,
              description: insight.message,
              teaching_explanation: insight.message
            });
          }
        }
    }
  };
  
  const getPhaseIcon = () => {
    switch (game_phase) {
      case "opening": return "🎯";
      case "middlegame": return "⚔️";
      case "late_middlegame": return "🔄";
      case "endgame": return "♟️";
      default: return "📊";
    }
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: -10, height: 0 }}
      animate={{ opacity: 1, y: 0, height: "auto" }}
      exit={{ opacity: 0, y: -10, height: 0 }}
      transition={{ duration: 0.2 }}
      data-testid="position-coaching-panel"
    >
      <Card className="border-blue-500/50 bg-gradient-to-r from-blue-500/5 to-blue-500/10 overflow-hidden">
        <CardContent className="p-3">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div 
              className="flex items-center gap-2 cursor-pointer flex-1"
              onClick={() => setExpanded(!expanded)}
            >
              <Target className="w-4 h-4 text-blue-500" />
              <span className="font-semibold text-sm">{structure_name}</span>
              <Badge variant="outline" className="text-xs bg-blue-500/10">
                <span className="mr-1">{getPhaseIcon()}</span>
                {game_phase?.replace("_", " ") || "Analysis"}
              </Badge>
            </div>
            <div className="flex items-center gap-1">
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-6 w-6"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </Button>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-6 w-6"
                onClick={onDismiss}
                data-testid="dismiss-position-coaching"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>
          
          {/* Expandable content */}
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 space-y-3"
              >
                {/* Main idea */}
                <p className="text-sm text-muted-foreground">
                  <Lightbulb className="w-4 h-4 inline mr-1 text-yellow-500" />
                  {main_idea}
                </p>
                
                {/* Key characteristics */}
                {key_characteristics.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground font-medium">Key Features:</span>
                    <ul className="text-xs text-muted-foreground list-disc list-inside space-y-0.5">
                      {key_characteristics.slice(0, 3).map((char, idx) => (
                        <li key={idx}>{char}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Tactical features */}
                {(tactical_features.threats > 0 || tactical_features.undefended_pieces > 0) && (
                  <div className="flex gap-2 flex-wrap">
                    {tactical_features.threats > 0 && (
                      <Badge className="bg-green-500/20 text-green-500 border-green-500/30">
                        <Zap className="w-3 h-3 mr-1" />
                        {tactical_features.threats} opportunities
                      </Badge>
                    )}
                    {tactical_features.undefended_pieces > 0 && (
                      <Badge className="bg-yellow-500/20 text-yellow-500 border-yellow-500/30">
                        <AlertTriangle className="w-3 h-3 mr-1" />
                        {tactical_features.undefended_pieces} undefended
                      </Badge>
                    )}
                  </div>
                )}
                
                {/* Strategic plan preview */}
                {strategic_plans.length > 0 && !selectedPlan && (
                  <div className="p-2 rounded bg-muted/50 space-y-1">
                    <div className="flex items-center gap-1 text-sm font-medium">
                      <Map className="w-4 h-4 text-blue-500" />
                      {strategic_plans[0].name}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {strategic_plans[0].description}
                    </p>
                  </div>
                )}
                
                {/* Selected plan detail */}
                {selectedPlan && (
                  <div className="p-2 rounded bg-primary/10 border border-primary/30 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{selectedPlan.name}</span>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-5 w-5"
                        onClick={() => setSelectedPlan(null)}
                      >
                        <X className="w-3 h-3" />
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {selectedPlan.teaching_explanation}
                    </p>
                    {selectedPlan.key_moves && (
                      <div className="flex gap-1 flex-wrap">
                        {selectedPlan.key_moves.slice(0, 5).map((move, idx) => (
                          <span 
                            key={idx}
                            className="px-2 py-0.5 rounded bg-muted text-xs font-mono"
                          >
                            {move}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Critical squares */}
                {critical_squares.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-muted-foreground">Key squares:</span>
                    {critical_squares.map((sq, idx) => (
                      <span 
                        key={idx}
                        className="px-2 py-0.5 rounded bg-blue-500/20 text-xs font-mono text-blue-500"
                      >
                        {sq}
                      </span>
                    ))}
                  </div>
                )}
                
                {/* Action buttons from options */}
                <div className="flex gap-2 flex-wrap">
                  {options.filter(o => o.id !== "just_play").slice(0, 3).map((option, idx) => (
                    <Button 
                      key={idx}
                      size="sm" 
                      variant={idx === 0 ? "default" : "outline"}
                      className="h-8 text-xs"
                      onClick={() => handleOptionClick(option)}
                      data-testid={`position-coaching-${option.id}`}
                    >
                      {option.id === "learn_strategic_plan" && <BookOpen className="w-3 h-3 mr-1" />}
                      {option.id === "see_tactical_themes" && <Zap className="w-3 h-3 mr-1" />}
                      {option.id === "check_piece_safety" && <AlertTriangle className="w-3 h-3 mr-1" />}
                      {option.label.replace(/[📚⚡⚠️💡]/g, "").trim()}
                    </Button>
                  ))}
                  
                  <Button 
                    size="sm" 
                    variant="ghost"
                    className="h-8 text-xs"
                    onClick={onDismiss}
                    data-testid="position-coaching-dismiss"
                  >
                    Continue playing
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>
    </motion.div>
  );
};

export default PositionCoachingPanel;
