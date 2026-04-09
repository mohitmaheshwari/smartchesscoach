/**
 * LiveChecklist — Fundamentals + Weaknesses + Player Profile
 *
 * Three sections:
 *   1. Fundamentals — checked every move (pass/fail/neutral + game-wide score)
 *   2. Your Weaknesses — from analyzed games, tracked live
 *   3. Player Profile — strengths & domains from game history
 */

import { motion, AnimatePresence } from "framer-motion";
import { Check, X as XIcon, Minus, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";

const FUNDAMENTALS = [
  { key: "opponent_threats", label: "Checked opponent threats", icon: "👁" },
  { key: "piece_safety", label: "All pieces defended", icon: "🛡" },
  { key: "king_safety", label: "King is safe", icon: "♔" },
  { key: "development", label: "Pieces developed", icon: "♞" },
  { key: "center_control", label: "Center controlled", icon: "⊞" },
  { key: "has_plan", label: "Move has a purpose", icon: "🎯" },
];

const DOMAIN_LABELS = {
  tactical_vision: "Tactical Vision",
  calculation_depth: "Calculation",
  positional_sense: "Positional Sense",
  endgame_technique: "Endgame",
  opening_knowledge: "Opening Knowledge",
};

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

const LiveChecklist = ({ checklist, checklistHistory = {}, weaknesses, playerProfile, gamePhase, coachNote }) => {
  return (
    <div className="space-y-4">
      {/* Phase header */}
      {gamePhase && (
        <p className="text-[9px] uppercase tracking-widest font-bold text-muted-foreground/40">
          {gamePhase}
        </p>
      )}

      {/* Coach note — when coaching is active */}
      <AnimatePresence>
        {coachNote && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="rounded-lg px-3 py-2.5 border bg-muted/40 border-border/40"
          >
            <p className="text-sm text-foreground leading-snug">{coachNote}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Fundamentals Checklist */}
      {checklist && (
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
                <ChecklistRow
                  key={item.key}
                  icon={<Icon className={`w-3.5 h-3.5 ${style.iconColor} flex-shrink-0`} strokeWidth={2.5} />}
                  label={item.label}
                  emoji={item.icon}
                  status={status}
                  style={style}
                  history={history}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Player Weaknesses — from analyzed games */}
      {weaknesses && weaknesses.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50 mb-2">
            Focus areas
          </p>
          <div className="space-y-0.5">
            {weaknesses.map(w => {
              const status = checklist?.[w.signal] || "neutral";
              const style = STATUS_STYLES[status];
              const Icon = style.icon;
              const history = checklistHistory?.[w.signal];

              return (
                <ChecklistRow
                  key={w.signal}
                  icon={<Icon className={`w-3.5 h-3.5 ${style.iconColor} flex-shrink-0`} strokeWidth={2.5} />}
                  label={w.label}
                  status={status}
                  style={style}
                  history={history}
                  badge={w.severity === "high" ? (
                    <AlertTriangle className="w-3 h-3 text-amber-400 flex-shrink-0" strokeWidth={2} />
                  ) : null}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Player Profile — strengths & weaknesses from game history */}
      {playerProfile && (
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50 mb-2">
            Your chess profile
          </p>

          {/* Strongest & Weakest */}
          <div className="flex gap-2 mb-2">
            {playerProfile.strongest && (
              <div className="flex-1 rounded-lg bg-emerald-500/5 border border-emerald-500/10 px-2.5 py-1.5">
                <p className="text-[9px] uppercase tracking-wider text-emerald-600 font-bold mb-0.5">Strength</p>
                <p className="text-xs text-foreground">{DOMAIN_LABELS[playerProfile.strongest] || playerProfile.strongest}</p>
              </div>
            )}
            {playerProfile.weakest && (
              <div className="flex-1 rounded-lg bg-red-500/5 border border-red-500/10 px-2.5 py-1.5">
                <p className="text-[9px] uppercase tracking-wider text-red-500 font-bold mb-0.5">Weakness</p>
                <p className="text-xs text-foreground">{DOMAIN_LABELS[playerProfile.weakest] || playerProfile.weakest}</p>
              </div>
            )}
          </div>

          {/* Domain scores */}
          {playerProfile.domains && Object.keys(playerProfile.domains).length > 0 && (
            <div className="space-y-1">
              {Object.entries(playerProfile.domains).map(([key, domain]) => {
                const score = domain.score || 0;
                const isStrong = key === playerProfile.strongest;
                const isWeak = key === playerProfile.weakest;
                return (
                  <div key={key} className="flex items-center gap-2">
                    <span className={`text-[11px] w-24 truncate ${
                      isStrong ? "text-emerald-600 font-medium" :
                      isWeak ? "text-red-400 font-medium" :
                      "text-muted-foreground"
                    }`}>
                      {DOMAIN_LABELS[key] || key}
                    </span>
                    <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          isStrong ? "bg-emerald-500" :
                          isWeak ? "bg-red-400" :
                          "bg-muted-foreground/30"
                        }`}
                        style={{ width: `${Math.min(100, score)}%` }}
                      />
                    </div>
                    <span className="text-[9px] font-mono text-muted-foreground/50 w-6 text-right">
                      {Math.round(score)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Reusable row component
const ChecklistRow = ({ icon, label, emoji, status, style, history, badge }) => (
  <div className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg border ${style.bg} ${style.border} transition-all duration-200`}>
    {icon}
    <span className={`text-xs ${style.text} flex-1`}>{label}</span>
    {history && (history.passed > 0 || history.failed > 0) && (
      <span className="text-[9px] font-mono text-muted-foreground/40">
        <span className="text-emerald-500/60">{history.passed}</span>
        <span className="text-muted-foreground/20">/</span>
        <span className="text-red-400/60">{history.failed}</span>
      </span>
    )}
    {badge}
    {emoji && <span className="text-[10px] opacity-30">{emoji}</span>}
  </div>
);

export default LiveChecklist;
