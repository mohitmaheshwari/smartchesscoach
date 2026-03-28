/**
 * TrapAlert - Temporary, dismissible alert for tactical dangers
 * 
 * NOT inside the coach card.
 * Appears as a separate floating notification when relevant.
 * 
 * Rules:
 * - Only appears if action-relevant within 1-2 moves
 * - Short and dismissible
 * - Optional "Show line" action
 * - Does NOT compete with normal coach explanation
 */

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { X, Eye, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const TrapAlert = ({ 
  trap,
  onShowLine,
  onDismiss,
  autoHideAfter = 10000 // Auto-hide after 10 seconds
}) => {
  const [visible, setVisible] = useState(true);
  
  // Auto-hide after timeout
  useEffect(() => {
    if (autoHideAfter > 0) {
      const timer = setTimeout(() => {
        setVisible(false);
        onDismiss?.();
      }, autoHideAfter);
      return () => clearTimeout(timer);
    }
  }, [autoHideAfter, onDismiss]);
  
  const handleDismiss = () => {
    setVisible(false);
    onDismiss?.();
  };
  
  if (!trap || !visible) return null;
  
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="mb-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30"
      >
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-amber-500">
              Trap Alert
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {trap.message || trap.name}
            </p>
          </div>
          <button 
            onClick={handleDismiss}
            className="text-muted-foreground hover:text-foreground p-1"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
        
        {/* Action buttons */}
        <div className="flex gap-2 mt-2 ml-6">
          {onShowLine && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-6 text-xs text-amber-500 hover:text-amber-400"
              onClick={() => {
                onShowLine(trap);
                handleDismiss();
              }}
            >
              <Eye className="w-3 h-3 mr-1" />
              Show line
            </Button>
          )}
          <Button 
            variant="ghost" 
            size="sm" 
            className="h-6 text-xs"
            onClick={handleDismiss}
          >
            Got it
          </Button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

export default TrapAlert;
