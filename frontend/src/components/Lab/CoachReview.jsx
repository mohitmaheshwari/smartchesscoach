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
    <div className="flex items-center justify-center w-7 h-7 border border-primary/30 text-primary">
      <span className="text-[10px] font-mono tracking-widest">{number}</span>
    </div>
    <Icon className="w-4 h-4 text-primary/70" strokeWidth={1.5} />
    <span className="text-[10px] font-mono tracking-[0.2em] uppercase text-muted-foreground">
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
      className="pb-8 mb-8 border-b border-border"
      data-testid="coach-review-story"
    >
      <SectionHeader icon={BookOpen} label="What Happened" number="01" />
      
      {narrative ? (
        <p className="text-base text-foreground leading-relaxed">
          {narrative}
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-foreground leading-relaxed">
            {story.opening}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {story.tension}
          </p>
          <p className="text-sm text-foreground leading-relaxed">
            {story.climax}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed italic">
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
      className="pb-8 mb-8 border-b border-border"
      data-testid="coach-review-mirror"
    >
      <SectionHeader icon={Eye} label="About You" number="02" />

      <div className="relative pl-4 border-l-2 border-primary/40">
        <p className="text-base text-foreground leading-relaxed">
          {narrative || mirror.observation}
        </p>
      </div>

      {mirror.pattern_insight && (
        <div className="mt-4 flex items-start gap-2">
          <Repeat className="w-3.5 h-3.5 text-primary/60 mt-0.5 shrink-0" strokeWidth={1.5} />
          <p className="text-xs text-primary/80 font-mono">
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
    minor: "border-border bg-muted/30",
  }[severity];

  return (
    <motion.div
      custom={2 + index * 0.3}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className={`p-4 border ${severityColor} mb-3 cursor-pointer group transition-all duration-200 hover:border-primary/30`}
      onClick={() => onNavigate?.(moment.move_number, moment.move_uci, moment.best_move_uci)}
      data-testid={`coach-review-moment-${index}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono tracking-widest text-muted-foreground uppercase">
            Move {moment.move_number}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground/50">
            {moment.phase}
          </span>
        </div>
        <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-primary transition-colors" strokeWidth={1.5} />
      </div>

      <p className="text-sm text-foreground leading-relaxed mb-2">
        {llmInsight || te.description || "A critical decision point."}
      </p>

      <div className="flex items-center gap-2">
        <Brain className="w-3 h-3 text-destructive/70" strokeWidth={1.5} />
        <span className="text-[11px] text-destructive/90 font-medium">
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
      className="pb-8 mb-8 border-b border-border"
      data-testid="coach-review-moments"
    >
      <SectionHeader icon={Target} label="Behavior Insight" number="03" />
      
      {moments.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No big mistakes. Clean game.
        </p>
      ) : (
        <div>
          <p className="text-xs text-muted-foreground mb-4">
            {moments.length === 1 
              ? "This move decided the game. Tap to see it."
              : `These ${moments.length} moves decided the game. Tap to see them.`
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
      className="pb-8 mb-8 border-b border-border"
      data-testid="coach-review-takeaway"
    >
      <SectionHeader icon={Lightbulb} label="Remember This" number="04" />
      
      <div className="relative bg-primary/[0.06] border border-primary/20 p-5">
        <Quote className="w-5 h-5 text-primary/30 absolute top-3 left-3" strokeWidth={1} />
        <p 
          className="text-lg text-foreground leading-relaxed text-center px-6 font-heading italic font-normal"
        >
          {mantra}
        </p>
      </div>

      {takeaway.focus_area && (
        <p className="text-[10px] font-mono tracking-widest text-muted-foreground/50 mt-3 text-center uppercase">
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
        <SectionHeader icon={TrendingUp} label="Your Progress" number="05" />
        <p className="text-sm text-muted-foreground">
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
      <SectionHeader icon={TrendingUp} label="Your Progress" number="05" />
      
      <p className="text-sm text-muted-foreground mb-4">
        {encouragement || proof.message}
      </p>

      {proof.improvements.length > 0 && (
        <div className="space-y-2 mb-3">
          {proof.improvements.map((imp, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/70 mt-1.5 shrink-0" />
              <div>
                <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">{imp.area}</span>
                <p className="text-xs text-muted-foreground mt-0.5">{imp.detail}</p>
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
                <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">{item.area}</span>
                <p className="text-xs text-muted-foreground mt-0.5">{item.detail}</p>
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
        <Loader2 className="w-6 h-6 animate-spin text-primary mb-4" />
        <span className="text-xs text-muted-foreground font-mono tracking-widest uppercase">
          Coach is thinking...
        </span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-16" data-testid="coach-review-error">
        <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-destructive/50" strokeWidth={1.5} />
        <p className="text-sm text-muted-foreground">{error || "No data available"}</p>
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
        className="mb-8 pb-6 border-b border-border"
      >
        <h2 
          className="text-2xl text-foreground tracking-tight font-heading"
        >
          Your Coach Says
        </h2>
        <p className="text-xs text-muted-foreground mt-1 font-mono tracking-widest uppercase">
          {story?.arc_type === "dominant" ? "Solid game" : 
           story?.arc_type === "thrown" ? "Tough lesson" :
           story?.arc_type === "outplayed" ? "Room to grow" :
           "Game review"}
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
