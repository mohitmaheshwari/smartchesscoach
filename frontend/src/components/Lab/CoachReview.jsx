/**
 * CoachReview.jsx — "Human Coach" Game Review
 * 
 * Five sections, like sitting with a coach after the game:
 * 1. THE STORY — What happened (narrative, no notation)
 * 2. THE MIRROR — What this reveals about you
 * 3. THE MOMENT — The 2-3 decisions that defined the game
 * 4. THE TAKEAWAY — One sentence to carry forward
 * 5. THE PROOF — What's improving
 */

import { useState, useEffect } from "react";
import { API } from "@/App";
import { motion } from "framer-motion";
import { 
  Loader2, BookOpen, Eye, Target, 
  Lightbulb, TrendingUp, ChevronRight,
  ArrowRight, AlertTriangle, Quote,
  Repeat, Zap, Brain
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (i) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  }),
};

// ─── Section Header ──────────────────────────────────────────────

const SectionHeader = ({ icon: Icon, label, number }) => (
  <div className="flex items-center gap-3 mb-4">
    <div className="flex items-center justify-center w-7 h-7 border border-[#CBA135]/30 text-[#CBA135]">
      <span className="text-[10px] font-mono tracking-widest">{number}</span>
    </div>
    <Icon className="w-4 h-4 text-[#CBA135]/70" strokeWidth={1.5} />
    <span className="text-[10px] font-mono tracking-[0.2em] uppercase text-[#A1A1AA]">
      {label}
    </span>
  </div>
);

// ─── 1. THE STORY ────────────────────────────────────────────────

const StorySection = ({ story, llmNarrative }) => {
  const narrative = llmNarrative?.story_narrative;

  return (
    <motion.div
      custom={0}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="pb-8 mb-8 border-b border-white/5"
      data-testid="coach-review-story"
    >
      <SectionHeader icon={BookOpen} label="The Story" number="01" />
      
      {narrative ? (
        <p className="text-base text-white/90 leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
          {narrative}
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-white/80 leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {story.opening}
          </p>
          <p className="text-sm text-white/70 leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {story.tension}
          </p>
          <p className="text-sm text-white/80 leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {story.climax}
          </p>
          <p className="text-sm text-white/60 leading-relaxed italic" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {story.resolution}
          </p>
        </div>
      )}
    </motion.div>
  );
};

// ─── 2. THE MIRROR ──────────────────────────────────────────────

const MirrorSection = ({ mirror, llmNarrative }) => {
  const narrative = llmNarrative?.mirror_narrative;

  return (
    <motion.div
      custom={1}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="pb-8 mb-8 border-b border-white/5"
      data-testid="coach-review-mirror"
    >
      <SectionHeader icon={Eye} label="The Mirror" number="02" />

      <div className="relative pl-4 border-l-2 border-[#722F37]/60">
        <p className="text-base text-white/90 leading-relaxed" style={{ fontFamily: "'Outfit', sans-serif" }}>
          {narrative || mirror.observation}
        </p>
      </div>

      {mirror.pattern_insight && (
        <div className="mt-4 flex items-start gap-2">
          <Repeat className="w-3.5 h-3.5 text-[#CBA135]/60 mt-0.5 shrink-0" strokeWidth={1.5} />
          <p className="text-xs text-[#CBA135]/80" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {mirror.pattern_insight}
          </p>
        </div>
      )}
    </motion.div>
  );
};

// ─── 3. THE MOMENT ──────────────────────────────────────────────

const MomentCard = ({ moment, index, onNavigate, llmInsight }) => {
  const te = moment.thinking_error || {};
  const severity = moment.cp_loss >= 200 ? "critical" : moment.cp_loss >= 100 ? "significant" : "minor";
  const severityColor = {
    critical: "border-red-500/30 bg-red-500/5",
    significant: "border-amber-500/20 bg-amber-500/5",
    minor: "border-white/10 bg-white/[0.02]",
  }[severity];

  return (
    <motion.div
      custom={2 + index * 0.3}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className={`p-4 border ${severityColor} mb-3 cursor-pointer group transition-all duration-200 hover:border-[#CBA135]/30`}
      onClick={() => onNavigate?.(moment.move_number, moment.move_uci, moment.best_move_uci)}
      data-testid={`coach-review-moment-${index}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono tracking-widest text-[#A1A1AA] uppercase">
            Move {moment.move_number}
          </span>
          <span className="text-[10px] font-mono text-white/30">
            {moment.phase}
          </span>
        </div>
        <ChevronRight className="w-3.5 h-3.5 text-white/20 group-hover:text-[#CBA135] transition-colors" strokeWidth={1.5} />
      </div>

      <p className="text-sm text-white/90 leading-relaxed mb-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
        {llmInsight || te.description || "A critical decision point."}
      </p>

      <div className="flex items-center gap-2">
        <Brain className="w-3 h-3 text-[#722F37]/70" strokeWidth={1.5} />
        <span className="text-[11px] text-[#722F37]/90 font-medium">
          {te.label || "Thinking error"}
        </span>
      </div>
    </motion.div>
  );
};

const MomentSection = ({ moments, llmNarrative, onNavigate }) => {
  const insights = llmNarrative?.moment_insights || [];

  return (
    <motion.div
      custom={2}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="pb-8 mb-8 border-b border-white/5"
      data-testid="coach-review-moments"
    >
      <SectionHeader icon={Target} label="The Moment" number="03" />
      
      {moments.length === 0 ? (
        <p className="text-sm text-white/50" style={{ fontFamily: "'Outfit', sans-serif" }}>
          No critical mistakes in this game. Clean play.
        </p>
      ) : (
        <div>
          <p className="text-xs text-white/40 mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>
            {moments.length === 1 
              ? "One decision defined this game. Click to see the position."
              : `${moments.length} decisions defined this game. Click to see the positions.`
            }
          </p>
          {moments.map((m, i) => (
            <MomentCard 
              key={i} 
              moment={m} 
              index={i} 
              onNavigate={onNavigate}
              llmInsight={insights[i]}
            />
          ))}
        </div>
      )}
    </motion.div>
  );
};

// ─── 4. THE TAKEAWAY ────────────────────────────────────────────

const TakeawaySection = ({ takeaway, llmNarrative }) => {
  const mantra = llmNarrative?.takeaway_refined || takeaway.mantra;

  return (
    <motion.div
      custom={3}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="pb-8 mb-8 border-b border-white/5"
      data-testid="coach-review-takeaway"
    >
      <SectionHeader icon={Lightbulb} label="The Takeaway" number="04" />
      
      <div className="relative bg-[#CBA135]/[0.04] border border-[#CBA135]/20 p-5">
        <Quote className="w-5 h-5 text-[#CBA135]/30 absolute top-3 left-3" strokeWidth={1} />
        <p 
          className="text-lg text-white/95 leading-relaxed text-center px-6"
          style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 400, fontStyle: "italic" }}
        >
          {mantra}
        </p>
      </div>

      {takeaway.focus_area && (
        <p className="text-[10px] font-mono tracking-widest text-white/30 mt-3 text-center uppercase">
          Focus area: {takeaway.focus_area.replace(/_/g, " ")}
        </p>
      )}
    </motion.div>
  );
};

// ─── 5. THE PROOF ───────────────────────────────────────────────

const ProofSection = ({ proof, llmNarrative }) => {
  const encouragement = llmNarrative?.encouragement;

  if (!proof.has_enough_data) {
    return (
      <motion.div
        custom={4}
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        className="pb-4"
        data-testid="coach-review-proof"
      >
        <SectionHeader icon={TrendingUp} label="The Proof" number="05" />
        <p className="text-sm text-white/40" style={{ fontFamily: "'Outfit', sans-serif" }}>
          {proof.message}
        </p>
      </motion.div>
    );
  }

  return (
    <motion.div
      custom={4}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="pb-4"
      data-testid="coach-review-proof"
    >
      <SectionHeader icon={TrendingUp} label="The Proof" number="05" />
      
      <p className="text-sm text-white/70 mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>
        {encouragement || proof.message}
      </p>

      {proof.improvements.length > 0 && (
        <div className="space-y-2 mb-3">
          {proof.improvements.map((imp, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/70 mt-1.5 shrink-0" />
              <div>
                <span className="text-xs text-emerald-400/90 font-medium">{imp.area}</span>
                <p className="text-xs text-white/50 mt-0.5">{imp.detail}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {proof.still_working_on.length > 0 && (
        <div className="space-y-2">
          {proof.still_working_on.map((item, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-500/60 mt-1.5 shrink-0" />
              <div>
                <span className="text-xs text-amber-400/80 font-medium">{item.area}</span>
                <p className="text-xs text-white/50 mt-0.5">{item.detail}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
};

// ─── MAIN COMPONENT ─────────────────────────────────────────────

const CoachReview = ({ gameId, onMoveClick }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!gameId) return;
    
    const fetchReview = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API}/lab/${gameId}/coach-review`, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to load coach review");
        const json = await res.json();
        setData(json);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchReview();
  }, [gameId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20" data-testid="coach-review-loading">
        <Loader2 className="w-6 h-6 animate-spin text-[#CBA135] mb-4" />
        <span className="text-xs text-white/40 font-mono tracking-widest uppercase">
          Your coach is reviewing...
        </span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-16" data-testid="coach-review-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-[#722F37]/50" strokeWidth={1.5} />
        <p className="text-sm text-white/40">{error || "No data available"}</p>
      </div>
    );
  }

  const { story, mirror, moments, takeaway, proof, llm_narrative } = data;

  return (
    <div className="px-2" data-testid="coach-review-panel">
      {/* Title */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        className="mb-8 pb-6 border-b border-white/5"
      >
        <h2 
          className="text-2xl text-white/90 tracking-tight"
          style={{ fontFamily: "'Cormorant Garamond', serif" }}
        >
          Coach Review
        </h2>
        <p className="text-xs text-white/30 mt-1 font-mono tracking-widest uppercase">
          {story?.arc_type === "dominant" ? "Clean performance" : 
           story?.arc_type === "thrown" ? "Lessons to learn" :
           story?.arc_type === "outplayed" ? "Growth opportunity" :
           "Game breakdown"}
        </p>
      </motion.div>

      {/* 5 Sections */}
      <StorySection story={story} llmNarrative={llm_narrative} />
      <MirrorSection mirror={mirror} llmNarrative={llm_narrative} />
      <MomentSection 
        moments={moments} 
        llmNarrative={llm_narrative} 
        onNavigate={(moveNum, moveUci, bestUci) => onMoveClick?.(moveNum, moveUci, bestUci)}
      />
      <TakeawaySection takeaway={takeaway} llmNarrative={llm_narrative} />
      <ProofSection proof={proof} llmNarrative={llm_narrative} />
    </div>
  );
};

export default CoachReview;
