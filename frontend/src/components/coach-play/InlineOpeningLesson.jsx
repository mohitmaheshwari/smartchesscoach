/**
 * InlineOpeningLesson - Compact opening lesson panel for in-game teaching
 * 
 * Shows key information without redirecting user away from their game.
 * Appears when coach detects an opening.
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  BookOpen, 
  ChevronDown, 
  ChevronUp,
  Eye,
  Bookmark,
  ExternalLink,
  Sparkles,
  X
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

const InlineOpeningLesson = ({ 
  opening,
  onShowOnBoard,
  onDismiss,
  onSaveForLater
}) => {
  const [expanded, setExpanded] = useState(true);
  const navigate = useNavigate();
  
  if (!opening) return null;
  
  const {
    name,
    key,
    main_idea,
    key_moves = [],
    key_squares = [],
    simple_explanation
  } = opening;
  
  const handleShowOnBoard = () => {
    if (onShowOnBoard) {
      onShowOnBoard(key_moves, key_squares);
    }
  };
  
  const handleSaveForLater = async () => {
    if (onSaveForLater) {
      await onSaveForLater(key);
    }
    toast.success("Added to your practice queue!");
  };
  
  const handleFullLesson = () => {
    // Open in new tab to not lose game
    window.open(`/openings/${key}`, '_blank');
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: -10, height: 0 }}
      animate={{ opacity: 1, y: 0, height: "auto" }}
      exit={{ opacity: 0, y: -10, height: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Card className="border-primary/50 bg-gradient-to-r from-primary/5 to-primary/10 overflow-hidden">
        <CardContent className="p-3">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div 
              className="flex items-center gap-2 cursor-pointer flex-1"
              onClick={() => setExpanded(!expanded)}
            >
              <BookOpen className="w-4 h-4 text-primary" />
              <span className="font-semibold text-sm">{name}</span>
              <Badge variant="outline" className="text-xs bg-primary/10">
                <Sparkles className="w-3 h-3 mr-1" />
                Opening detected
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
                {/* Key idea */}
                <p className="text-sm text-muted-foreground">
                  {simple_explanation || main_idea || "A solid opening choice."}
                </p>
                
                {/* Main moves */}
                {key_moves.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-muted-foreground">Main line:</span>
                    {key_moves.slice(0, 6).map((move, idx) => (
                      <span 
                        key={idx}
                        className="px-2 py-0.5 rounded bg-muted text-xs font-mono"
                      >
                        {move}
                      </span>
                    ))}
                  </div>
                )}
                
                {/* Action buttons */}
                <div className="flex gap-2 flex-wrap">
                  <Button 
                    size="sm" 
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={handleShowOnBoard}
                    data-testid="show-on-board-btn"
                  >
                    <Eye className="w-3 h-3 mr-1" />
                    Show on board
                  </Button>
                  
                  <Button 
                    size="sm" 
                    variant="outline"
                    className="h-8 text-xs"
                    onClick={handleSaveForLater}
                    data-testid="save-for-later-btn"
                  >
                    <Bookmark className="w-3 h-3 mr-1" />
                    Practice later
                  </Button>
                  
                  <Button 
                    size="sm" 
                    variant="ghost"
                    className="h-8 text-xs text-primary"
                    onClick={handleFullLesson}
                    data-testid="full-lesson-btn"
                  >
                    <ExternalLink className="w-3 h-3 mr-1" />
                    Full lesson
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

export default InlineOpeningLesson;
