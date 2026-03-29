/**
 * InlineTrapLesson - Compact trap lesson panel for in-game teaching
 * 
 * Shows trap sequence without redirecting user away from their game.
 * Lets them try the trap right there on the board.
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Target, 
  ChevronDown, 
  ChevronUp,
  Play,
  Eye,
  RotateCcw,
  X,
  Zap
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

const InlineTrapLesson = ({ 
  trap,
  onShowTrapMoves,
  onTryTrap,
  onDismiss
}) => {
  const [expanded, setExpanded] = useState(true);
  const [showingMoves, setShowingMoves] = useState(false);
  
  if (!trap) return null;
  
  const {
    name,
    description,
    moves = [],
    trigger_move,
    victim_falls_for
  } = trap;
  
  const handleShowMoves = () => {
    setShowingMoves(true);
    if (onShowTrapMoves) {
      onShowTrapMoves(moves);
    }
  };
  
  const handleTryTrap = () => {
    if (onTryTrap) {
      onTryTrap(trap);
    }
    toast.success("Let's practice this trap!");
  };
  
  // Format moves for display
  const formatMoves = (moves) => {
    if (!moves || moves.length === 0) return [];
    
    const formatted = [];
    for (let i = 0; i < moves.length; i += 2) {
      const moveNum = Math.floor(i / 2) + 1;
      const white = moves[i] || "";
      const black = moves[i + 1] || "";
      formatted.push(`${moveNum}.${white}${black ? ` ${black}` : ""}`);
    }
    return formatted;
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: -10, height: 0 }}
      animate={{ opacity: 1, y: 0, height: "auto" }}
      exit={{ opacity: 0, y: -10, height: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Card className="border-amber-500/50 bg-gradient-to-r from-amber-500/5 to-orange-500/10 overflow-hidden">
        <CardContent className="p-3">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div 
              className="flex items-center gap-2 cursor-pointer flex-1"
              onClick={() => setExpanded(!expanded)}
            >
              <Target className="w-4 h-4 text-amber-500" />
              <span className="font-semibold text-sm">{name}</span>
              <Badge variant="outline" className="text-xs bg-amber-500/10 text-amber-500 border-amber-500/30">
                <Zap className="w-3 h-3 mr-1" />
                Trap available
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
                {/* Description */}
                {description && (
                  <p className="text-sm text-muted-foreground">
                    {description}
                  </p>
                )}
                
                {/* Trap sequence */}
                <div className="space-y-2">
                  <span className="text-xs text-muted-foreground font-medium">
                    Trap sequence:
                  </span>
                  <div className="flex items-center gap-1 flex-wrap">
                    {formatMoves(moves).slice(0, 4).map((move, idx) => (
                      <span 
                        key={idx}
                        className={`px-2 py-0.5 rounded text-xs font-mono ${
                          idx === formatMoves(moves).length - 1 
                            ? "bg-amber-500/20 text-amber-500 font-bold" 
                            : "bg-muted"
                        }`}
                      >
                        {move}
                      </span>
                    ))}
                    {moves.length > 8 && (
                      <span className="text-xs text-muted-foreground">...</span>
                    )}
                  </div>
                </div>
                
                {/* Key info */}
                {trigger_move && (
                  <div className="text-xs text-muted-foreground">
                    <span className="text-amber-500 font-medium">Key move:</span>{" "}
                    {trigger_move}
                    {victim_falls_for && (
                      <span> — opponent might play {victim_falls_for}</span>
                    )}
                  </div>
                )}
                
                {/* Action buttons */}
                <div className="flex gap-2 flex-wrap">
                  <Button 
                    size="sm" 
                    variant="outline"
                    className="h-8 text-xs border-amber-500/30 hover:bg-amber-500/10"
                    onClick={handleShowMoves}
                    disabled={showingMoves}
                    data-testid="show-trap-moves-btn"
                  >
                    <Eye className="w-3 h-3 mr-1" />
                    {showingMoves ? "Showing..." : "Show moves"}
                  </Button>
                  
                  <Button 
                    size="sm" 
                    className="h-8 text-xs bg-amber-500 hover:bg-amber-600 text-black"
                    onClick={handleTryTrap}
                    data-testid="try-trap-btn"
                  >
                    <Play className="w-3 h-3 mr-1" />
                    Try it now
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

export default InlineTrapLesson;
