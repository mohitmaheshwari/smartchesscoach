/**
 * InstantDNA — The "wow moment" reveal component
 *
 * Shows a full Chess DNA report computed in <3 seconds from PGN data.
 * This is the first personalized thing a new user sees.
 * It needs to feel like the coach already knows them.
 */

import { motion } from "framer-motion";
import { Zap, Shield, Crown, Target, BookOpen, Swords, ChevronRight } from "lucide-react";

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
  const style = data.playing_style || {};
  const safety = data.king_safety || {};
  const openings = data.opening_repertoire || {};
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
        <p className="cg-eyebrow">My first impression</p>
        <h1 className="text-2xl sm:text-3xl font-heading font-bold text-foreground tracking-tight mb-2">
          You play like {String(arch.label || "a thoughtful chess player").toLowerCase()}.
        </h1>
        <p className="text-sm text-muted-foreground max-w-sm mx-auto">
          {arch.description}
        </p>
      </motion.div>

      {/* ── BEST OPENING ── */}
      {openings.best_opening && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="cg-panel !p-4 mb-4"
        >
          <p className="cg-eyebrow !mb-2">An opening that already feels like yours</p>
          <p className="text-base font-semibold text-foreground">{openings.best_opening.name}</p>
          <p className="text-xs text-muted-foreground mt-1">You seem comfortable reaching this kind of position as {openings.best_opening.color}.</p>
        </motion.div>
      )}

      {/* Translate stored signals into coaching language; the numbers remain evidence. */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6"
      >
        {/* Game length */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Swords className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold">Avg Game</p>
          </div>
          <p className="text-base font-semibold text-foreground">{style.style_label || "Your own"} style</p>
          <p className="text-xs text-muted-foreground mt-1">We’ll keep the plan recognisable to the way you like to play.</p>
        </div>

        {/* Castling */}
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Shield className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.5} />
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-bold">King Safety</p>
          </div>
          <p className="text-base font-semibold text-foreground">
            {safety.castle_rate >= 80 ? "You usually give your king a home" : safety.castle_rate >= 50 ? "Your king safety changes from game to game" : "Your king often waits too long"}
          </p>
          <p className="text-xs text-muted-foreground mt-1">I’ll watch what happens just before you commit to a plan.</p>
        </div>
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
            I’m still reading the deeper moments. I’ll bring them into your plan when they are ready.
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
          {ctaLabel || "Start with your coach"}
          <ChevronRight className="w-4 h-4" />
        </button>
      </motion.div>
    </div>
  );
};


export default InstantDNA;
