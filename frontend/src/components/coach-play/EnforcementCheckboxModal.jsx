/**
 * EnforcementCheckboxModal.jsx - Level 3 Enforcement
 * 
 * THE MOST IMPORTANT UI IN THE PRODUCT
 * 
 * This modal:
 * - Blocks board interaction completely
 * - Cannot be dismissed without acknowledgment
 * - Forces user to pause and reflect
 * - Creates the "point of no escape"
 * 
 * "Until the user is forced to pause and reflect, nothing changes."
 */

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ShieldAlert } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

const EnforcementCheckboxModal = ({ 
  isOpen,
  riskType,
  repeatCount,
  onConfirm
}) => {
  const [isChecked, setIsChecked] = useState(false);
  const [canProceed, setCanProceed] = useState(false);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setIsChecked(false);
      setCanProceed(false);
    }
  }, [isOpen]);

  // Add delay after checking to prevent spam clicking
  useEffect(() => {
    if (isChecked) {
      const timer = setTimeout(() => {
        setCanProceed(true);
      }, 400); // 400ms delay
      return () => clearTimeout(timer);
    } else {
      setCanProceed(false);
    }
  }, [isChecked]);

  if (!isOpen) return null;

  // Get checkbox text based on risk type
  const getCheckboxText = () => {
    switch (riskType) {
      case "IGNORE_THREAT":
      case "ignore_threat":
        return "I checked what my opponent is threatening";
      case "HANGING_PIECE":
      case "hanging_piece":
        return "I verified my piece is safe after this move";
      case "MATERIAL_LOSS":
      case "material_loss":
        return "I understand the material I am giving up";
      case "BLUNDER_INTO_TACTIC":
      case "tactical_blunder":
        return "I have looked for tactics in this position";
      case "KING_SAFETY":
      case "king_danger":
        return "I have verified my king is safe";
      default:
        return "I have carefully checked my move";
    }
  };

  const handleConfirm = () => {
    if (canProceed) {
      onConfirm();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 bg-black/90 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      // No onClick to close - this is unavoidable
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", duration: 0.4 }}
      >
        <Card className="max-w-md w-full bg-red-950/80 border-red-500/50 shadow-2xl shadow-red-500/20">
          <CardContent className="p-6">
            {/* Icon */}
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center">
                <ShieldAlert className="w-8 h-8 text-red-400" />
              </div>
            </div>

            {/* Warning Header */}
            <div className="text-center mb-6">
              <h2 className="text-xl font-bold text-red-400 mb-2">
                You are repeating your mistake
              </h2>
              <p className="text-zinc-300 text-sm">
                Slow down.
              </p>
              {repeatCount >= 3 && (
                <p className="text-red-400/70 text-xs mt-2">
                  This is the {repeatCount}rd time this game.
                </p>
              )}
            </div>

            {/* Checkbox - THE KEY ELEMENT */}
            <div className="bg-zinc-900/50 rounded-lg p-4 mb-6 border border-zinc-800">
              <div className="flex items-start gap-3">
                <Checkbox
                  id="enforcement-check"
                  checked={isChecked}
                  onCheckedChange={setIsChecked}
                  className="mt-0.5 border-red-500/50 data-[state=checked]:bg-red-600 data-[state=checked]:border-red-600"
                  data-testid="enforcement-checkbox"
                />
                <label 
                  htmlFor="enforcement-check"
                  className="text-white text-sm cursor-pointer select-none leading-relaxed"
                >
                  {getCheckboxText()}
                </label>
              </div>
            </div>

            {/* Continue Button - Disabled until checked + delay */}
            <Button
              onClick={handleConfirm}
              disabled={!canProceed}
              className={`w-full h-12 text-lg transition-all duration-300 ${
                canProceed 
                  ? "bg-red-600 hover:bg-red-700" 
                  : "bg-zinc-700 cursor-not-allowed opacity-50"
              }`}
              data-testid="enforcement-continue-btn"
            >
              {!isChecked ? "Check the box above" : 
               !canProceed ? "Wait..." : "Continue"}
            </Button>

            {/* No skip, no close, no escape */}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
};

export default EnforcementCheckboxModal;
