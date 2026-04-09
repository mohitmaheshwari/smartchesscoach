/**
 * ActiveCoachStrip — Ambient and advisory coaching display.
 *
 * Shows ONE short coaching message near the board.
 * Not a sidebar item. Not a modal. Just a clean strip.
 *
 * Ambient: subtle, fades after 3-4 seconds
 * Advisory: slightly stronger, stays 4-6 seconds
 *
 * Replaces previous message when new one arrives.
 * No stacking. No scrolling. One line at a time.
 */

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

const LAYER_STYLES = {
  ambient: {
    bg: "bg-muted/60",
    border: "border-border/40",
    text: "text-foreground/70",
    duration: 4000,
  },
  advisory: {
    bg: "bg-amber-50",
    border: "border-amber-200/60",
    text: "text-amber-900",
    duration: 6000,
  },
};

const ActiveCoachStrip = ({ coaching }) => {
  const [visible, setVisible] = useState(false);
  const [currentText, setCurrentText] = useState("");
  const [currentLayer, setCurrentLayer] = useState("ambient");
  const timerRef = useRef(null);

  useEffect(() => {
    if (!coaching || !coaching.text) {
      setVisible(false);
      return;
    }

    const layer = coaching.layer || "ambient";
    const style = LAYER_STYLES[layer] || LAYER_STYLES.ambient;

    // Show new message
    setCurrentText(coaching.text);
    setCurrentLayer(layer);
    setVisible(true);

    // Auto-hide after duration
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setVisible(false);
    }, style.duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [coaching?.text, coaching?.layer]);

  const style = LAYER_STYLES[currentLayer] || LAYER_STYLES.ambient;

  return (
    <AnimatePresence>
      {visible && currentText && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.2 }}
          className={`rounded-lg border ${style.bg} ${style.border} px-4 py-2.5`}
        >
          <p className={`text-sm ${style.text} leading-snug`}>
            {currentText}
          </p>
          {coaching?.question?.prompt && (
            <p className={`text-xs ${style.text} opacity-60 mt-1 italic`}>
              {coaching.question.prompt}
            </p>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ActiveCoachStrip;
