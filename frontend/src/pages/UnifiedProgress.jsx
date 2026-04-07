/**
 * PROGRESS — "Am I improving?"
 *
 * No charts. No accuracy. No numbers.
 * Only: what you're working on + is it getting better + next action.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, Target, Brain, Swords } from "lucide-react";

// Same mapping as Home — human language for each mistake
const MISTAKE_LABELS = {
  tactical_miss:      "Missing simple tactics",
  one_move_blunder:   "Leaving pieces hanging",
  calculation_error:  "Stopping your thinking too early",
  positional:         "Being outplayed positionally",
  endgame_collapse:   "Failing to convert endgames",
  opening_disaster:   "Making opening mistakes",
  time_collapse:      "Collapsing under time pressure",
  threw_winning:      "Throwing winning positions",
  piece_safety:       "Leaving pieces unprotected",
  ignore_threat:      "Not checking opponent threats",
  calculation_depth:  "Stopping your thinking too early",
  missed_tactic:      "Missing winning chances",
  king_safety:        "Leaving your king exposed",
  conversion:         "Giving back advantages",
};

const MISTAKE_DESCRIPTIONS = {
  tactical_miss:      "You play your move without scanning for captures, checks, and threats.",
  one_move_blunder:   "You move without checking if your piece is safe.",
  calculation_error:  "You decide your move but don't check what your opponent will do next.",
  positional:         "You move pieces without a plan. Your opponent outmaneuvers you.",
  endgame_collapse:   "You reach winning endgames but don't know the technique.",
  opening_disaster:   "You deviate from sound play in the first 10 moves.",
  time_collapse:      "You spend time on easy moves, then panic on hard ones.",
  threw_winning:      "You stop checking your opponent once you're ahead.",
  piece_safety:       "You don't check if your pieces are protected before moving.",
  ignore_threat:      "You play your move without checking what your opponent is attacking.",
  calculation_depth:  "You decide your move but don't check what your opponent will do next.",
  missed_tactic:      "The winning move is there. You're not looking for it.",
  king_safety:        "You attack before your king is safe.",
  conversion:         "When you're ahead, you get creative instead of simple.",
};

const UnifiedProgress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [coaching, setCoaching] = useState(null);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [reportRes, labRes] = await Promise.all([
          fetch(`${API}/progress/coaching-report`, { credentials: "include" }),
          fetch(`${API}/lab-coach-pick`, { credentials: "include" }),
        ]);

        if (reportRes.ok) {
          const r = await reportRes.json();
          if (r.has_data) setHasData(true);
        }

        if (labRes.ok) {
          const labData = await labRes.json();
          setCoaching(labData.coaching);
          if (labData.total_count > 0) setHasData(true);
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  if (!hasData) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-16 text-center" data-testid="progress-page">
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-3">Progress</h1>
          <p className="text-sm text-muted-foreground mb-6">Play and analyze a few games to track your improvement.</p>
          <button onClick={() => navigate("/import")} className="px-5 py-2.5 text-sm bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity">Import Games</button>
        </div>
      </Layout>
    );
  }

  const root = coaching?.root_problem;
  const topProblem = coaching?.top_problems?.[0];
  const lock = coaching?.training_lock;

  const mistakeKey = topProblem?.category || root?.pattern || "calculation_depth";
  const label = MISTAKE_LABELS[mistakeKey] || MISTAKE_LABELS.calculation_depth;
  const description = MISTAKE_DESCRIPTIONS[mistakeKey] || MISTAKE_DESCRIPTIONS.calculation_depth;

  // Simple improvement signal — no numbers, just direction
  const recentCount = root?.games_affected || 0;
  const isImproving = recentCount < 5;
  const isRepeating = recentCount >= 5;

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-10" data-testid="progress-page">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>

          {/* What you're working on */}
          <p className="text-sm text-muted-foreground/60 mb-2">You are working on:</p>

          <h1 className="text-xl sm:text-2xl font-heading text-foreground tracking-tight leading-snug mb-3">
            {label}
          </h1>

          <p className="text-[15px] text-muted-foreground leading-[1.7] mb-6">
            {description}
          </p>

          {/* Status — behavioral, not numerical */}
          <div className="rounded-xl border border-border bg-card p-5 mb-6">
            <p className="text-sm text-muted-foreground mb-2">Recent games:</p>
            {isRepeating ? (
              <p className="text-sm text-foreground">
                You repeated this mistake in your recent games.
              </p>
            ) : (
              <p className="text-sm text-foreground">
                This is showing up less. Keep going.
              </p>
            )}
          </div>

          {/* Action */}
          <button
            onClick={() => {
              if (lock && !lock.unlocked) navigate(`/training?focus=${lock.pattern || mistakeKey}`);
              else navigate("/play-with-coach");
            }}
            className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
          >
            {lock && !lock.unlocked ? (
              <><Target className="w-4 h-4" strokeWidth={2} />Continue Training</>
            ) : (
              <><Swords className="w-4 h-4" strokeWidth={2} />Apply It In a Game</>
            )}
            <ChevronRight className="w-4 h-4 opacity-60" />
          </button>

        </motion.div>
      </div>
    </Layout>
  );
};

export default UnifiedProgress;
