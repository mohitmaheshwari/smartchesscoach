import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chessboard } from "react-chessboard";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  X,
  ChevronRight,
  AlertTriangle,
  TrendingUp,
  Target,
  TrendingDown,
  Play,
  Eye
} from "lucide-react";

/**
 * EvidenceModal - Shows specific game positions where a pattern occurred
 * 
 * Props:
 * - isOpen: boolean
 * - onClose: () => void
 * - title: string (e.g., "Relaxes when winning")
 * - evidence: Array of position objects with game_id, move_number, fen_before, etc.
 * - type: "pattern" | "state" - determines styling
 * - state: "winning" | "equal" | "losing" (optional, for win-state analysis)
 */
const EvidenceModal = ({ 
  isOpen, 
  onClose, 
  title, 
  subtitle,
  evidence = [], 
  type = "pattern",
  state = null 
}) => {
  const navigate = useNavigate();
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [previewIndex, setPreviewIndex] = useState(0);

  // Get color based on type/state
  const getAccentColor = () => {
    if (type === "state") {
      if (state === "winning") return "text-green-500";
      if (state === "equal") return "text-yellow-500";
      if (state === "losing") return "text-orange-500";
    }
    return "text-red-500"; // Default for pattern (rating killer)
  };

  const getStateIcon = () => {
    if (state === "winning") return <TrendingUp className="w-4 h-4" />;
    if (state === "equal") return <Target className="w-4 h-4" />;
    if (state === "losing") return <TrendingDown className="w-4 h-4" />;
    return <AlertTriangle className="w-4 h-4" />;
  };

  // Navigate to game at specific move
  const goToGame = (item) => {
    navigate(`/games/dashboard/${item.game_id}?move=${item.move_number}`);
    onClose();
  };

  // Format eval for display
  const formatEval = (evalBefore) => {
    if (evalBefore === undefined || evalBefore === null) return "";
    const sign = evalBefore >= 0 ? "+" : "";
    return `${sign}${evalBefore.toFixed(1)}`;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] p-0 overflow-hidden" data-testid="evidence-modal" aria-describedby="evidence-modal-description">
        <DialogHeader className="p-4 pb-2 border-b border-border/50">
          <DialogTitle className="flex items-center gap-2">
            <span className={getAccentColor()}>{getStateIcon()}</span>
            {title}
          </DialogTitle>
          {subtitle && (
            <p id="evidence-modal-description" className="text-sm text-muted-foreground">{subtitle}</p>
          )}
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 h-[500px]">
          {/* Left: Position List */}
          <ScrollArea className="h-full border-r border-border/50">
            <div className="p-3 space-y-2">
              <p className="text-xs text-muted-foreground mb-3">
                {evidence.length} position{evidence.length !== 1 ? 's' : ''} found
              </p>
              
              {evidence.map((item, idx) => (
                <motion.div
                  key={`${item.game_id}-${item.move_number}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className={`p-3 rounded-lg border cursor-pointer transition-all
                    ${previewIndex === idx 
                      ? 'border-primary bg-primary/10' 
                      : 'border-border/50 hover:border-primary/50 hover:bg-muted/50'
                    }`}
                  onClick={() => setPreviewIndex(idx)}
                  data-testid={`evidence-item-${idx}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">
                      vs {item.opponent}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Move {item.move_number}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2 text-xs">
                    {/* Eval before */}
                    <span className={`font-mono ${
                      item.eval_before > 1 ? 'text-green-500' :
                      item.eval_before < -1 ? 'text-red-500' :
                      'text-yellow-500'
                    }`}>
                      {formatEval(item.eval_before)}
                    </span>
                    
                    {/* Arrow showing what happened */}
                    <span className="text-muted-foreground">→</span>
                    
                    {/* Your move (the mistake) */}
                    <span className="font-mono text-red-400">
                      {item.move_played}
                    </span>
                    
                    {/* CP loss */}
                    <span className="text-red-500/70 ml-auto">
                      -{item.cp_loss} cp
                    </span>
                  </div>
                  
                  {/* Best move hint */}
                  {item.best_move && (
                    <p className="text-xs text-emerald-500 mt-1">
                      Better: {item.best_move}
                    </p>
                  )}
                </motion.div>
              ))}
              
              {evidence.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  <p className="text-sm">No positions found</p>
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Right: Board Preview */}
          <div className="p-4 flex flex-col">
            {evidence[previewIndex] ? (
              <>
                <div className="flex-1 flex items-center justify-center">
                  <div className="w-full max-w-[280px]">
                    <Chessboard
                      position={evidence[previewIndex].fen_before || "start"}
                      boardWidth={280}
                      arePiecesDraggable={false}
                      customBoardStyle={{
                        borderRadius: '4px',
                        boxShadow: '0 2px 10px rgba(0,0,0,0.3)'
                      }}
                    />
                  </div>
                </div>
                
                {/* Position details */}
                <div className="mt-4 space-y-3">
                  <div className="text-center">
                    <p className="text-sm text-muted-foreground">
                      You had <span className={`font-bold ${
                        evidence[previewIndex].eval_before > 1 ? 'text-green-500' :
                        evidence[previewIndex].eval_before < -1 ? 'text-red-500' :
                        'text-yellow-500'
                      }`}>
                        {formatEval(evidence[previewIndex].eval_before)}
                      </span>
                    </p>
                    <p className="text-sm mt-1">
                      You played <span className="font-mono text-red-400">{evidence[previewIndex].move_played}</span>
                    </p>
                    {evidence[previewIndex].best_move && (
                      <p className="text-sm text-emerald-500 mt-1">
                        Better was <span className="font-mono">{evidence[previewIndex].best_move}</span>
                      </p>
                    )}
                  </div>
                  
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="flex-1 gap-1"
                      onClick={() => goToGame(evidence[previewIndex])}
                      data-testid="view-full-game-btn"
                    >
                      <Eye className="w-4 h-4" />
                      Full Game
                    </Button>
                    <Button 
                      size="sm" 
                      className="flex-1 gap-1"
                      onClick={() => goToGame(evidence[previewIndex])}
                      data-testid="analyze-btn"
                    >
                      <Play className="w-4 h-4" />
                      Analyze
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <p className="text-sm">Select a position to preview</p>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EvidenceModal;
