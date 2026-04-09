/**
 * ActiveCoachStrip — Ambient and advisory coaching display.
 *
 * State-driven, NOT timer-driven.
 * Message stays until:
 *   - Replaced by next message
 *   - OR fades slowly after delay if nothing new arrives
 *   - User interaction (hover) extends life
 *
 * One message at a time. No stacking. No scrolling.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

const LAYER_CONFIG = {
  ambient: {
    bg: "bg-muted/60",
    border: "border-border/40",
    text: "text-foreground/70",
    fadeDelay: 5000,
  },
  advisory: {
    bg: "bg-amber-50",
    border: "border-amber-200/60",
    text: "text-amber-900",
    fadeDelay: 8000,
  },
};

const ActiveCoachStrip = ({ coaching }) => {
  const [visible, setVisible] = useState(false);
  const [displayData, setDisplayData] = useState(null);
  const fadeTimerRef = useRef(null);
  const isHoveredRef = useRef(false);

  const startFadeTimer = useCallback((delay) => {
    if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current);
    fadeTimerRef.current = setTimeout(() => {
      if (!isHoveredRef.current) {
        setVisible(false);
      } else {
        // User is hovering — retry fade after another interval
        startFadeTimer(3000);
      }
    }, delay);
  }, []);

  useEffect(() => {
    if (!coaching || !coaching.text) {
      // No new message — let current one fade naturally (timer already running)
      return;
    }

    // New message arrived — replace immediately
    const layer = coaching.layer || "ambient";
    const config = LAYER_CONFIG[layer] || LAYER_CONFIG.ambient;

    setDisplayData({ ...coaching, layer });
    setVisible(true);

    // Start fade timer
    startFadeTimer(config.fadeDelay);

    return () => {
      if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current);
    };
  }, [coaching?.text, coaching?.layer, startFadeTimer]);

  const handleMouseEnter = () => {
    isHoveredRef.current = true;
    // Extend visibility while hovering
    if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current);
  };

  const handleMouseLeave = () => {
    isHoveredRef.current = false;
    // Resume fade after hover ends
    startFadeTimer(2000);
  };

  if (!displayData) return null;

  const config = LAYER_CONFIG[displayData.layer] || LAYER_CONFIG.ambient;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25 }}
          className={`rounded-lg border ${config.bg} ${config.border} px-4 py-3 cursor-default`}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          {/* Game phase indicator */}
          {displayData.gamePhase && (
            <p className="text-[9px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-1.5">
              {displayData.gamePhase}
            </p>
          )}
          <p className={`text-sm ${config.text} leading-snug`}>
            {displayData.text}
          </p>
          {displayData.question?.prompt && (
            <p className={`text-xs ${config.text} opacity-60 mt-1.5 italic`}>
              {displayData.question.prompt}
            </p>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ActiveCoachStrip;
