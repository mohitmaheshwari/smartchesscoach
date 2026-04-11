/**
 * PostGameReflection — The coaching loop's feedback moment
 *
 * After a game, the coach checks: did you repeat the active pattern?
 *
 * Case A: FAILED — "Again, you stopped thinking too early."
 * Case B: PARTIAL — "Better. You missed it once under pressure."
 * Case C: SUCCESS — "This time, no mistakes. This is real progress."
 *
 * The CTA always feeds back into the loop:
 * Failed → Training
 * Partial → Lab
 * Success → Play Again
 */

import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Trophy, AlertTriangle, Target, ChevronRight, Swords,
  Minus, Brain, CheckCircle2, XCircle
} from "lucide-react";

const PostGameReflection = ({ data, onPlayAgain, onGoTrain }) => {
  const navigate = useNavigate();

  if (!data || !data.has_data) return null;

  const isWin = data.result === "win" || data.result === "W" || data.result === "1-0" || data.result === "0-1";
  const isLoss = data.result === "loss" || data.result === "L";
  const pv = data.pattern_verdict;

  return (
    <div className="space-y-5">
      {/* ── RESULT HEADER (minimal) ── */}
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

      {/* ── PATTERN VERDICT (the main event) ── */}
      {pv && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {pv.case === "failed" && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/[0.03] p-5">
              <div className="flex items-center gap-2 mb-3">
                <XCircle className="w-4 h-4 text-red-400" strokeWidth={2} />
                <p className="text-xs font-bold uppercase tracking-wider text-red-400">Same mistake</p>
              </div>
              <p className="text-base font-heading text-foreground leading-snug mb-2">{pv.message}</p>
              {pv.detail && <p className="text-sm text-muted-foreground mb-3">{pv.detail}</p>}
              {pv.rule && (
                <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/15 mb-4">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">{pv.rule_name || "Rule"}</p>
                  <p className="text-sm text-foreground">{pv.rule}</p>
                </div>
              )}
              <button
                onClick={() => navigate(pv.cta_href || `/training?focus=${pv.pattern}`)}
                className="w-full py-3 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all flex items-center justify-center gap-2"
              >
                <Target className="w-4 h-4" strokeWidth={2} />
                {pv.cta_label || "Fix This Again"}
                <ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </div>
          )}

          {pv.case === "partial" && (
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.03] p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-amber-500" strokeWidth={2} />
                <p className="text-xs font-bold uppercase tracking-wider text-amber-500">Getting there</p>
              </div>
              <p className="text-base font-heading text-foreground leading-snug mb-2">{pv.message}</p>
              <p className="text-sm text-muted-foreground mb-3">{pv.detail}</p>
              {pv.rule && (
                <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/15 mb-4">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">{pv.rule_name || "Rule"}</p>
                  <p className="text-sm text-foreground">{pv.rule}</p>
                </div>
              )}
              <button
                onClick={() => navigate(pv.cta_href || "/lab")}
                className="w-full py-3 text-sm font-semibold rounded-xl border border-border text-foreground hover:bg-card transition-all flex items-center justify-center gap-2"
              >
                <Brain className="w-4 h-4" strokeWidth={1.5} />
                {pv.cta_label || "Review Game"}
                <ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </div>
          )}

          {pv.case === "success" && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-5">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                <p className="text-xs font-bold uppercase tracking-wider text-emerald-500">Progress</p>
              </div>
              <p className="text-base font-heading text-foreground leading-snug mb-2">{pv.message}</p>
              <p className="text-sm text-muted-foreground mb-4">{pv.detail}</p>
              <button
                onClick={onPlayAgain || (() => navigate(pv.cta_href || "/play-with-coach"))}
                className="w-full py-3 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all flex items-center justify-center gap-2"
              >
                <Swords className="w-4 h-4" strokeWidth={2} />
                {pv.cta_label || "Play Again"}
                <ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </div>
          )}
        </motion.div>
      )}

      {/* ── COACH SUMMARY (only if no pattern verdict) ── */}
      {!pv && (
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
      )}

      {/* ── KEY MOMENTS (compact, below verdict) ── */}
      {data.key_moments && data.key_moments.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/70 mb-2">
            {data.key_moments.length === 1 ? "The Moment" : "Key Moments"}
          </p>
          <div className="space-y-2">
            {data.key_moments.map((m, i) => (
              <div key={i} className="bg-card border border-border rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono text-muted-foreground">Move {m.move_number}</span>
                  <span className="text-xs font-mono text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">{m.user_move}</span>
                  <span className="text-muted-foreground/30">&rarr;</span>
                  <span className="text-xs font-mono text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">{m.best_move}</span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{m.explanation}</p>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── PHASE-BY-PHASE BREAKDOWN ── */}
      {data.phase_analysis && Object.keys(data.phase_analysis).length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-muted-foreground/70 mb-2">
            Game Phases
          </p>
          <div className="space-y-2">
            {["opening", "middlegame", "endgame"].filter(k => data.phase_analysis[k]).map((key) => {
              const phase = data.phase_analysis[key];
              const acc = phase.accuracy;
              const accColor = acc == null ? "text-muted-foreground"
                : acc >= 90 ? "text-emerald-500"
                : acc >= 70 ? "text-amber-500"
                : "text-red-400";
              return (
                <div key={key} className="bg-card border border-border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-foreground">{phase.name}</span>
                      {phase.opening_name && (
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {phase.opening_name}{phase.variation ? ` · ${phase.variation}` : ""}
                        </span>
                      )}
                    </div>
                    {acc != null && (
                      <span className={`text-sm font-bold font-mono ${accColor}`}>{acc}%</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground leading-snug">{phase.verdict}</p>
                  {phase.key_moments?.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {phase.key_moments.map((m, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[11px]">
                          <span className="font-mono text-muted-foreground/60">m{m.move}</span>
                          <span className="font-mono text-red-400">{m.played}</span>
                          <span className="text-muted-foreground/30">→</span>
                          <span className="font-mono text-emerald-500">{m.better || "?"}</span>
                          <span className="text-muted-foreground/50 truncate max-w-[120px]">{m.explanation}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* ── FALLBACK ACTIONS (only if no pattern verdict) ── */}
      {!pv && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="flex gap-3"
        >
          <button
            onClick={onPlayAgain}
            className="flex-1 px-4 py-3 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-md shadow-amber-500/15 flex items-center justify-center gap-2"
          >
            <Swords className="w-4 h-4" strokeWidth={2} />
            Play Again
          </button>
          <button
            onClick={onGoTrain}
            className="flex-1 px-4 py-3 text-sm font-medium rounded-xl border border-border text-foreground hover:bg-card transition-all flex items-center justify-center gap-2"
          >
            <Target className="w-4 h-4" strokeWidth={1.5} />
            Train
          </button>
        </motion.div>
      )}

      {/* ── GAMES TOGETHER ── */}
      {data.games_together > 1 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }} className="text-center">
          <p className="text-[10px] text-muted-foreground/40 font-mono">Game #{data.games_together} together</p>
        </motion.div>
      )}
    </div>
  );
};

export default PostGameReflection;
