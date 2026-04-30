/**
 * GuardianWarning - Pre-move guardian intervention modal
 * 
 * Shows a warning when the user is about to make a bad move,
 * allowing them to reconsider or proceed anyway.
 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  ShieldAlert, 
  AlertTriangle, 
  X, 
  Lightbulb 
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const GuardianWarning = ({ 
  intervention, 
  pendingMove, 
  onConfirm, 
  onCancel,
  remainingInterventions 
}) => {
  if (!intervention || !pendingMove) return null;
  
  const getRiskColor = (level) => {
    switch (level) {
      case "critical": return "text-red-500 bg-red-500/20";
      case "high": return "text-orange-500 bg-orange-500/20";
      case "medium": return "text-yellow-500 bg-yellow-500/20";
      default: return "text-blue-500 bg-blue-500/20";
    }
  };
  
  const getRiskIcon = (level) => {
    switch (level) {
      case "critical":
      case "high":
        return <ShieldAlert className="w-6 h-6" />;
      default:
        return <AlertTriangle className="w-6 h-6" />;
    }
  };
  
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
        onClick={onCancel}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <Card className="max-w-md border-2 border-red-500/50">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`p-2 rounded-lg ${getRiskColor(intervention.risk_level)}`}>
                    {getRiskIcon(intervention.risk_level)}
                  </div>
                  <CardTitle className="text-lg">
                    {intervention.risk_level === "critical" ? "Wait!" : "Hold on!"}
                  </CardTitle>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8"
                  onClick={onCancel}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            
            <CardContent className="space-y-4">
              {/* Warning Message */}
              <p className="text-sm text-muted-foreground">
                {intervention.message || `Playing ${pendingMove.move} might not be the best choice here.`}
              </p>
              
              {/* Explanation */}
              {intervention.explanation && (
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-sm">{intervention.explanation}</p>
                </div>
              )}
              
              {/* Alternative Moves */}
              {intervention.alternative_moves && intervention.alternative_moves.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Lightbulb className="w-4 h-4 text-yellow-500" />
                    <span>Better moves:</span>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {intervention.alternative_moves.map((move, idx) => (
                      <span 
                        key={idx}
                        className="px-2 py-1 rounded bg-green-500/20 text-green-400 text-sm font-mono"
                      >
                        {move}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <Button 
                  variant="outline" 
                  className="flex-1"
                  onClick={onCancel}
                >
                  Let me think...
                </Button>
                <Button 
                  variant="destructive" 
                  className="flex-1"
                  onClick={() => onConfirm(pendingMove, intervention.risk_level)}
                >
                  Play anyway
                </Button>
              </div>
              
              {/* Remaining interventions */}
              <p className="text-xs text-center text-muted-foreground">
                {remainingInterventions} warnings remaining this game
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default GuardianWarning;
