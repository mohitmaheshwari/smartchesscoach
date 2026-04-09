/**
 * CommentaryPanel — Position-specific board reading.
 *
 * Shows on the left side, between board and sidebar.
 * Uses existing read_board_like_a_coach() output.
 *
 * Displays:
 *   - Phase + summary
 *   - Current plan
 *   - Position observations (pins, forks, piece activity, structure)
 *
 * This teaches the GAME. The sidebar teaches the PROCESS.
 */

import { motion, AnimatePresence } from "framer-motion";
import { Eye, Target, Zap, Shield, Crown } from "lucide-react";

const CATEGORY_CONFIG = {
  tactics: { icon: Zap, color: "text-red-500", bg: "bg-red-500/5", border: "border-red-500/10" },
  king_safety: { icon: Shield, color: "text-amber-500", bg: "bg-amber-500/5", border: "border-amber-500/10" },
  piece_activity: { icon: Crown, color: "text-blue-500", bg: "bg-blue-500/5", border: "border-blue-500/10" },
  development: { icon: Target, color: "text-emerald-500", bg: "bg-emerald-500/5", border: "border-emerald-500/10" },
  center: { icon: Target, color: "text-purple-500", bg: "bg-purple-500/5", border: "border-purple-500/10" },
  pawn_structure: { icon: Eye, color: "text-orange-500", bg: "bg-orange-500/5", border: "border-orange-500/10" },
};

const CommentaryPanel = ({ commentary }) => {
  if (!commentary) return null;

  const { summary, phase, plan, observations, material } = commentary;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-border/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Eye className="w-3.5 h-3.5 text-muted-foreground/50" />
            <span className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50">
              Board Reading
            </span>
          </div>
          {phase && (
            <span className="text-[9px] uppercase tracking-widest text-muted-foreground/40">
              {phase}
            </span>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {/* Material */}
        {material && (
          <p className="text-[11px] text-muted-foreground font-medium">{material}</p>
        )}

        {/* Summary — main coaching insight */}
        {summary && (
          <p className="text-sm text-foreground leading-snug">{summary}</p>
        )}

        {/* Plan */}
        {plan && (
          <div className="rounded-lg bg-primary/5 border border-primary/10 px-3 py-2">
            <p className="text-[9px] uppercase tracking-widest text-primary/60 font-bold mb-1">Plan</p>
            <p className="text-xs text-foreground leading-snug">{plan}</p>
          </div>
        )}

        {/* Observations */}
        {observations && observations.length > 0 && (
          <div className="space-y-1.5">
            {observations.map((obs, i) => {
              const config = CATEGORY_CONFIG[obs.category] || CATEGORY_CONFIG.piece_activity;
              const Icon = config.icon;
              return (
                <div
                  key={i}
                  className={`rounded-lg ${config.bg} border ${config.border} px-2.5 py-2`}
                >
                  <div className="flex items-start gap-2">
                    <Icon className={`w-3 h-3 ${config.color} mt-0.5 flex-shrink-0`} strokeWidth={2} />
                    <div className="flex-1 min-w-0">
                      {obs.title && (
                        <p className={`text-[10px] font-semibold ${config.color} mb-0.5`}>{obs.title}</p>
                      )}
                      <p className="text-xs text-foreground/80 leading-snug">
                        {obs.description || obs.actionable || obs.title}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default CommentaryPanel;
