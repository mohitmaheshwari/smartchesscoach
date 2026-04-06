/**
 * InstantDNA — The "wow moment" reveal component
 *
 * Shows a full Chess DNA report computed in <3 seconds from PGN data.
 * This is the first personalized thing a new user sees.
 * It needs to feel like the coach already knows them.
 */

import { motion } from "framer-motion";
import {
  Zap, Shield, Crown, Target, BookOpen, Swords,
  TrendingUp, TrendingDown, Minus, Clock, ChevronRight
} from "lucide-react";

const ARCHETYPE_ICONS = {
  tactical_attacker: Swords,
  positional_grinder: Shield,
  rapid_warrior: Zap,
  endgame_specialist: Crown,
  opening_theorist: BookOpen,
  all_rounder: Target,
  aggressive_gambler: Zap,
  solid_defender: Shield,
};

const InstantDNA = ({ data, onContinue, ctaLabel }) => {
  if (!data || !data.has_data) return null;

  const arch = data.archetype || {};
  const record = data.record || {};
  const style = data.playing_style || {};
  const safety = data.king_safety || {};
  const openings = data.opening_repertoire || {};
  const rating = data.rating || {};
  const time = data.time_management;
  const insights = data.insights || [];
  const ArchIcon = ARCHETYPE_ICONS[data.archetype_key] || Target;

  return (
    <div className="max-w-lg mx-auto px-4">
      {/* ── HEADER ── */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="text-center mb-8"
      >
        <div className="w-14 h-14 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-4 shadow-lg shadow-amber-500/20">
          <ArchIcon className="w-7 h-7 text-black" strokeWidth={2} />
        </div>
        <p className="text-xs font-mono text-primary mb-2">
          {data.games_analyzed} games analyzed in {(data.generation_time_ms / 1000).toFixed(1)}s
        </p>
        <h1 className="text-2xl sm:text-3xl font-heading font-bold text-foreground tracking-tight mb-1">
          {arch.label || "Chess Player"}
        </h1>
        <p className="text-sm text-muted-foreground max-w-sm mx-auto">
          {arch.description}
        </p>
      </motion.div>

      {/* ── WIN RATES ── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="grid grid-cols-3 gap-3 mb-6"
      >
        <StatBox value={`${record.win_rate || 0}%`} label="Win Rate"
          color={record.win_rate >= 55 ? "text-emerald-500" : record.win_rate >= 45 ? "text-foreground" : "text-red-400"} />
        <StatBox value={`${record.white_win_rate || 0}%`} label="As White"
          color={record.white_win_rate >= 55 ? "text-emerald-500" : "text-foreground"} />
        <StatBox value={`${record.black_win_rate || 0}%`} label="As Black"
          color={record.black_win_rate >= 55 ? "text-emerald-500" : "text-foreground"} />
      </motion.div>

      {/* ── BEST OPENING ── */}
      {openings.best_opening && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-card border border-border rounded-xl p-4 mb-4"
        >
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold mb-2">Strongest Opening</p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-base font-semibold text-foreground">{openings.best_opening.name}</p>
              <p className="text-xs text-muted-foreground">
                {openings.best_opening.games} games as {openings.best_opening.color}
              </p>
            </div>
            <span className="text-lg font-mono font-bold text-emerald-500">{openings.best_opening.win_rate}%</span>
          </div>
        </motion.div>
      )}

      {/* ── KEY NUMBERS ── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="grid grid-cols-2 gap-3 mb-6"
      >
        {/* Game length */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Swords className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold">Avg Game</p>
          </div>
          <p className="text-xl font-mono font-bold text-foreground">{style.avg_game_length || 0} moves</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">{style.style_label} style</p>
        </div>

        {/* Castling */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Shield className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold">King Safety</p>
          </div>
          <p className="text-xl font-mono font-bold text-foreground">
            {safety.avg_castle_move > 0 ? `Move ${safety.avg_castle_move}` : "Rare"}
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {safety.castle_rate >= 80 ? "Castles consistently" : safety.castle_rate >= 50 ? `${safety.castle_rate}% of games` : "Often skips castling"}
          </p>
        </div>

        {/* Rating */}
        {rating.current && (
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold">Rating</p>
            </div>
            <p className="text-xl font-mono font-bold text-foreground">{rating.current}</p>
            {rating.change !== null && rating.change !== undefined && (
              <p className={`text-[10px] mt-0.5 font-medium ${rating.change > 0 ? "text-emerald-500" : rating.change < 0 ? "text-red-400" : "text-muted-foreground"}`}>
                {rating.change > 0 ? "+" : ""}{rating.change} recent trend
              </p>
            )}
          </div>
        )}

        {/* Time management */}
        {time && time.avg_time_per_move && (
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold">Avg Move Time</p>
            </div>
            <p className="text-xl font-mono font-bold text-foreground">{time.avg_time_per_move}s</p>
            {time.rushed_move_pct > 20 && (
              <p className="text-[10px] text-amber-400 mt-0.5">{time.rushed_move_pct}% rushed</p>
            )}
          </div>
        )}
      </motion.div>

      {/* ── INSIGHTS ── */}
      {insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="mb-8"
        >
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold mb-2.5">Coach's First Impressions</p>
          <div className="space-y-2">
            {insights.map((insight, i) => (
              <div key={i} className="flex items-start gap-2.5 text-sm text-muted-foreground leading-relaxed">
                <span className="text-primary mt-0.5 flex-shrink-0">•</span>
                {insight}
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── BACKGROUND ANALYSIS NOTICE ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.55 }}
        className="mb-6"
      >
        <div className="bg-card border border-border/50 rounded-lg p-3 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse flex-shrink-0" />
          <p className="text-xs text-muted-foreground">
            Deep analysis running in background. Full insights will appear on your Progress page.
          </p>
        </div>
      </motion.div>

      {/* ── CTA ── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="text-center"
      >
        <button
          onClick={onContinue}
          className="w-full px-6 py-4 text-base font-semibold text-black rounded-xl gradient-gold hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
        >
          {ctaLabel || "Start Training"}
          <ChevronRight className="w-4 h-4" />
        </button>
      </motion.div>
    </div>
  );
};


const StatBox = ({ value, label, color = "text-foreground" }) => (
  <div className="bg-card border border-border rounded-xl p-3 text-center">
    <p className={`text-2xl font-mono font-bold ${color}`}>{value}</p>
    <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-0.5">{label}</p>
  </div>
);


export default InstantDNA;
