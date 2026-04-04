/**
 * PostGameReflection — What happened and what to do next
 *
 * Shown after a Play with Coach game ends.
 * Not stats — a coaching conversation.
 */

import { motion } from "framer-motion";
import { Trophy, AlertTriangle, Target, ChevronRight, Swords, Minus } from "lucide-react";

const PostGameReflection = ({ data, onPlayAgain, onGoTrain }) => {
  if (!data || !data.has_data) return null;

  const isWin = data.result === "win" || data.result === "W";
  const isLoss = data.result === "loss" || data.result === "L";

  return (
    <div className="space-y-5">
      {/* ── RESULT HEADER ── */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center"
      >
        <div className={`w-12 h-12 rounded-xl mx-auto mb-3 flex items-center justify-center ${
          isWin ? "bg-emerald-500/15" : isLoss ? "bg-red-500/15" : "bg-muted"
        }`}>
          {isWin ? <Trophy className="w-6 h-6 text-emerald-500" strokeWidth={1.5} /> :
           isLoss ? <AlertTriangle className="w-6 h-6 text-red-400" strokeWidth={1.5} /> :
           <Minus className="w-6 h-6 text-muted-foreground" strokeWidth={1.5} />}
        </div>
        <h2 className="text-lg font-heading font-semibold text-foreground">
          {isWin ? "Victory" : isLoss ? "Defeat" : "Draw"}
        </h2>
      </motion.div>

      {/* ── COACH SUMMARY ── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-card border border-border rounded-xl p-4"
      >
        <p className="text-sm text-foreground leading-relaxed">{data.coach_summary}</p>
        {data.encouragement && (
          <p className="text-xs text-muted-foreground mt-2 italic">{data.encouragement}</p>
        )}
      </motion.div>

      {/* ── KEY MOMENTS ── */}
      {data.key_moments && data.key_moments.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/70 mb-2">
            {data.key_moments.length === 1 ? "The Moment That Mattered" : "Two Moments That Mattered"}
          </p>
          <div className="space-y-2">
            {data.key_moments.map((m, i) => (
              <div key={i} className="bg-card border border-border rounded-xl p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono text-muted-foreground">Move {m.move_number}</span>
                  <span className="text-xs font-mono text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">{m.user_move}</span>
                  <span className="text-muted-foreground/30">→</span>
                  <span className="text-xs font-mono text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">{m.best_move}</span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{m.explanation}</p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── PATTERN CHECK ── */}
      {data.memory_insights && data.memory_insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/70 mb-2">
            Pattern Check
          </p>
          <div className="space-y-1.5">
            {data.memory_insights.map((mi, i) => (
              <div key={i} className={`text-xs px-3 py-2 rounded-lg border ${
                mi.type === "improvement" ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-500" :
                mi.type === "recurring" ? "border-amber-500/20 bg-amber-500/5 text-amber-400" :
                "border-border bg-card text-muted-foreground"
              }`}>
                {mi.message}
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── WHAT TO DO NEXT ── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/70 mb-2">
          What To Do Next
        </p>
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-sm text-foreground font-medium mb-2">{data.priority_focus}</p>
          {data.training_suggestions && data.training_suggestions.length > 0 && (
            <div className="space-y-1 mt-2">
              {data.training_suggestions.map((s, i) => (
                <p key={i} className="text-xs text-muted-foreground flex items-start gap-2">
                  <span className="text-primary mt-0.5">•</span>
                  {s}
                </p>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* ── GAMES TOGETHER ── */}
      {data.games_together > 1 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.45 }}
          className="text-center"
        >
          <p className="text-[10px] text-muted-foreground/40 font-mono">
            Game #{data.games_together} together
          </p>
        </motion.div>
      )}

      {/* ── ACTIONS ── */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="flex gap-3"
      >
        <button
          onClick={onPlayAgain}
          className="flex-1 px-4 py-3 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-md shadow-amber-500/15 flex items-center justify-center gap-2"
        >
          <Swords className="w-4 h-4" strokeWidth={2} />
          Play Again
        </button>
        {data.priority_focus && (
          <button
            onClick={onGoTrain}
            className="flex-1 px-4 py-3 text-sm font-medium rounded-xl border border-border text-foreground hover:bg-card transition-all flex items-center justify-center gap-2"
          >
            <Target className="w-4 h-4" strokeWidth={1.5} />
            Train Weakness
          </button>
        )}
      </motion.div>
    </div>
  );
};

export default PostGameReflection;
