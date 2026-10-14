import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Trophy, AlertTriangle, Minus, RotateCcw, ArrowRight, Sparkles, X, Brain } from "lucide-react";
import { useNavigate } from "react-router-dom";

/**
 * GameResultModal — Celebratory / reflective post-game result card.
 * Shown when game ends in Victory, Defeat, or Draw.
 * Supports both Light and Dark modes with rich micro-animations.
 */
export default function GameResultModal({
  isOpen,
  result, // "win" | "loss" | "draw" | "1-0" | "0-1" | "1/2-1/2"
  userColor = "white",
  moveCount = 0,
  summary,
  onPlayAgain,
  onReviewGame,
  onClose,
}) {
  const navigate = useNavigate();

  if (!isOpen) return null;

  // Normalize result
  const normalizedResult = (() => {
    if (!result) return "draw";
    const r = String(result).toLowerCase();
    if (r === "win" || r === "victory") return "win";
    if (r === "loss" || r === "defeat") return "loss";
    if (r === "draw") return "draw";
    if (r === "1-0") return userColor === "white" ? "win" : "loss";
    if (r === "0-1") return userColor === "black" ? "win" : "loss";
    if (r === "1/2-1/2") return "draw";
    return "draw";
  })();

  const isWin = normalizedResult === "win";
  const isLoss = normalizedResult === "loss";
  const isDraw = normalizedResult === "draw";

  const config = isWin
    ? {
        badge: "VICTORY",
        title: "Checkmate! Brilliant Victory",
        subtitle: "You outplayed Coach Jessica and converted your advantage cleanly.",
        badgeCls: "bg-emerald-500/15 border-emerald-500/40 text-emerald-700 dark:text-emerald-300",
        iconBg: "bg-gradient-to-br from-emerald-400 to-teal-500 shadow-emerald-500/30",
        borderCls: "border-emerald-500/30 dark:border-emerald-500/40",
        glowCls: "bg-emerald-500/15",
        ctaBtn: "bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 shadow-emerald-500/30",
        icon: Trophy,
      }
    : isLoss
    ? {
        badge: "HARD-FOUGHT MATCH",
        title: "Defeat — Great Learning Moment",
        subtitle: "Every loss contains the exact lesson you need for your next plateau jump.",
        badgeCls: "bg-rose-500/15 border-rose-500/40 text-rose-700 dark:text-rose-300",
        iconBg: "bg-gradient-to-br from-rose-500 to-amber-600 shadow-rose-500/30",
        borderCls: "border-rose-500/30 dark:border-rose-500/40",
        glowCls: "bg-rose-500/15",
        ctaBtn: "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 shadow-cyan-500/30",
        icon: AlertTriangle,
      }
    : {
        badge: "DRAW",
        title: "A Resilient Draw",
        subtitle: "Solid balance across the board. Neither player yielded an opening.",
        badgeCls: "bg-amber-500/15 border-amber-500/40 text-amber-700 dark:text-amber-300",
        iconBg: "bg-gradient-to-br from-amber-400 to-orange-500 shadow-amber-500/30",
        borderCls: "border-amber-500/30 dark:border-amber-500/40",
        glowCls: "bg-amber-500/15",
        ctaBtn: "bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-slate-950 shadow-amber-500/30",
        icon: Minus,
      };

  const Icon = config.icon;

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-8 bg-black/60 dark:bg-black/85 backdrop-blur-md animate-in fade-in duration-200"
        onClick={onClose}
        data-testid="game-result-modal"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.92, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 15 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          onClick={(e) => e.stopPropagation()}
          className={`relative w-full max-w-lg sm:max-w-xl rounded-3xl border ${config.borderCls} bg-card dark:bg-gradient-to-b dark:from-[#1b2633] dark:via-[#131d27] dark:to-[#0b1118] text-foreground dark:text-white shadow-2xl dark:shadow-[0_25px_70px_rgba(0,0,0,0.85)] p-6 sm:p-8 md:p-10 backdrop-blur-2xl overflow-hidden`}
        >
          {/* Subtle Glow Orb behind card */}
          <div
            className={`absolute top-0 right-0 w-64 h-64 ${config.glowCls} rounded-full blur-3xl pointer-events-none`}
          />

          {/* Close button */}
          {onClose && (
            <button
              onClick={onClose}
              className="absolute top-5 right-5 p-2 text-muted-foreground hover:text-foreground dark:text-slate-400 dark:hover:text-white hover:bg-muted dark:hover:bg-white/10 rounded-full transition-colors cursor-pointer z-10"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          )}

          {/* Icon & Badge Header */}
          <div className="flex flex-col items-center text-center mb-6 relative z-10">
            <div
              className={`w-20 h-20 sm:w-24 sm:h-24 rounded-3xl flex items-center justify-center text-slate-950 mb-4 shadow-xl ${config.iconBg} transform hover:rotate-6 transition-transform`}
            >
              <Icon className="w-10 h-10 sm:w-12 sm:h-12 text-slate-950" strokeWidth={2.2} />
            </div>

            <div
              className={`inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full border text-xs font-mono font-bold uppercase tracking-wider mb-2.5 shadow-sm ${config.badgeCls}`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{config.badge}</span>
            </div>

            <h3 className="font-heading font-extrabold text-2xl sm:text-3xl text-foreground dark:text-white tracking-tight">
              {config.title}
            </h3>

            <p className="text-xs sm:text-sm text-muted-foreground dark:text-slate-300 mt-1.5 max-w-md leading-relaxed font-medium">
              {config.subtitle}
            </p>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-3 gap-2.5 sm:gap-3 p-3.5 sm:p-4 rounded-2xl bg-muted/50 dark:bg-white/[0.04] border border-border dark:border-white/10 mb-6 relative z-10">
            <div className="text-center">
              <span className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground dark:text-slate-400 font-semibold">
                Your Color
              </span>
              <span className="text-xs sm:text-sm font-bold text-foreground dark:text-white capitalize mt-0.5 inline-block">
                {userColor}
              </span>
            </div>
            <div className="text-center border-x border-border dark:border-white/10">
              <span className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground dark:text-slate-400 font-semibold">
                Moves Played
              </span>
              <span className="text-xs sm:text-sm font-bold text-foreground dark:text-white mt-0.5 inline-block font-mono">
                {moveCount}
              </span>
            </div>
            <div className="text-center">
              <span className="block text-[10px] font-mono uppercase tracking-wider text-muted-foreground dark:text-slate-400 font-semibold">
                Coach
              </span>
              <span className="text-xs sm:text-sm font-bold text-cyan-700 dark:text-cyan-300 mt-0.5 inline-block">
                Jessica
              </span>
            </div>
          </div>

          {/* Coach Insight Summary Snippet if available */}
          {summary?.key_takeaway && (
            <div className="mb-6 p-4 rounded-2xl bg-cyan-500/10 dark:bg-cyan-950/40 border border-cyan-500/30 text-left relative z-10">
              <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-wider text-cyan-700 dark:text-cyan-300 mb-1">
                <Brain className="w-3.5 h-3.5" />
                <span>Coach Takeaway</span>
              </div>
              <p className="text-xs sm:text-sm text-foreground/90 dark:text-slate-200 leading-relaxed font-medium">
                {summary.key_takeaway}
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 relative z-10">
            <button
              type="button"
              onClick={onPlayAgain}
              className={`flex-1 py-3.5 px-5 rounded-2xl font-heading font-extrabold text-xs uppercase tracking-wider transition-all inline-flex items-center justify-center gap-2 cursor-pointer shadow-md hover:shadow-lg ${config.ctaBtn}`}
            >
              <RotateCcw className="w-4 h-4" />
              <span>Play Again</span>
            </button>

            <button
              type="button"
              onClick={() => {
                if (onReviewGame) {
                  onReviewGame();
                } else if (summary?.game_id) {
                  navigate(`/lab/game/${summary.game_id}`);
                } else {
                  navigate("/lab");
                }
              }}
              className="py-3.5 px-5 rounded-2xl bg-muted hover:bg-muted/80 dark:bg-white/10 dark:hover:bg-white/20 border border-border dark:border-white/20 text-foreground dark:text-white font-heading font-bold text-xs uppercase tracking-wider transition-all cursor-pointer whitespace-nowrap inline-flex items-center justify-center gap-2"
            >
              <span>Review in Lab</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
