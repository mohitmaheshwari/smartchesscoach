/**
 * LiveChecklist — Fundamentals + Weaknesses tracker
 *
 * Runs EVERY move like a pilot's pre-flight checklist.
 * Shows:
 *   - Current move status (pass/fail/neutral) for each fundamental
 *   - Game-wide score (3/5 passed across the game)
 *   - Player's known weaknesses with game-wide tracking
 *   - Coach note when something fails
 */

import { motion, AnimatePresence } from "framer-motion";
import { Check, X as XIcon, Minus, AlertTriangle } from "lucide-react";

const FUNDAMENTALS = [
  { key: "opponent_threats", label: "Checked opponent threats", icon: "👁" },
  { key: "piece_safety", label: "All pieces defended", icon: "🛡" },
  { key: "king_safety", label: "King is safe", icon: "♔" },
  { key: "development", label: "Pieces developed", icon: "♞" },
  { key: "center_control", label: "Center controlled", icon: "⊞" },
  { key: "has_plan", label: "Move has a purpose", icon: "🎯" },
];

const STATUS_STYLES = {
  passed: {
    icon: Check,
    bg: "bg-emerald-500/8",
    border: "border-emerald-500/15",
    text: "text-foreground",
    iconColor: "text-emerald-500",
  },
  failed: {
    icon: XIcon,
    bg: "bg-red-500/8",
    border: "border-red-500/15",
    text: "text-foreground",
    iconColor: "text-red-500",
  },
  neutral: {
    icon: Minus,
    bg: "bg-transparent",
    border: "border-transparent",
    text: "text-muted-foreground/40",
    iconColor: "text-muted-foreground/25",
  },
};

const LiveChecklist = ({ checklist, checklistHistory = {}, weaknesses, gamePhase, coachNote }) => {
  if (!checklist) return null;

  return (
    <div className="space-y-3">
      {/* Phase header */}
      {gamePhase && (
        <p className="text-[9px] uppercase tracking-widest font-bold text-muted-foreground/40">
          {gamePhase}
        </p>
      )}

      {/* Fundamentals */}
      <div>
        <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50 mb-2">
          Fundamentals
        </p>
        <div className="space-y-0.5">
          {FUNDAMENTALS.map(item => {
            const status = checklist[item.key] || "neutral";
            const style = STATUS_STYLES[status];
            const Icon = style.icon;
            const history = checklistHistory[item.key];

            return (
              <div
                key={item.key}
                className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg border ${style.bg} ${style.border} transition-all duration-200`}
              >
                <Icon className={`w-3.5 h-3.5 ${style.iconColor} flex-shrink-0`} strokeWidth={2.5} />
                <span className={`text-xs ${style.text} flex-1`}>
                  {item.label}
                </span>
                {/* Game-wide score */}
                {history && (history.passed > 0 || history.failed > 0) && (
                  <span className="text-[9px] font-mono text-muted-foreground/40">
                    <span className="text-emerald-500/60">{history.passed}</span>
                    /
                    <span className="text-red-400/60">{history.failed}</span>
                  </span>
                )}
                <span className="text-[10px] opacity-30">{item.icon}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Player Weaknesses */}
      {weaknesses && weaknesses.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50 mb-2">
            Your focus areas
          </p>
          <div className="space-y-0.5">
            {weaknesses.map(w => {
              const status = checklist[w.signal] || "neutral";
              const style = STATUS_STYLES[status];
              const Icon = style.icon;
              const history = checklistHistory[w.signal];

              return (
                <div
                  key={w.signal}
                  className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg border ${style.bg} ${style.border} transition-all duration-200`}
                >
                  <Icon className={`w-3.5 h-3.5 ${style.iconColor} flex-shrink-0`} strokeWidth={2.5} />
                  <span className={`text-xs ${style.text} flex-1`}>{w.label}</span>
                  {history && (history.passed > 0 || history.failed > 0) && (
                    <span className="text-[9px] font-mono text-muted-foreground/40">
                      <span className="text-emerald-500/60">{history.passed}</span>
                      /
                      <span className="text-red-400/60">{history.failed}</span>
                    </span>
                  )}
                  {w.severity === "high" && (
                    <AlertTriangle className="w-3 h-3 text-amber-400 flex-shrink-0" strokeWidth={2} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Coach note */}
      <AnimatePresence>
        {coachNote && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="rounded-lg px-3 py-2.5 border bg-muted/30 border-border/30"
          >
            <p className="text-xs text-muted-foreground leading-snug">{coachNote}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default LiveChecklist;
