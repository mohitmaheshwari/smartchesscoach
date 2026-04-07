/**
 * HOME — "A coach stopping you before your next mistake."
 *
 * LOCKED: pain → behavior → tension → action (NO rule, NO answer)
 * UNLOCKED: pain → proof → last game memory → rule → directive → action
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, Swords, Import, Target, Brain } from "lucide-react";

// Mistake → confrontation headline (always leads with pain)
const HEADLINES = {
  tactical_miss:      "You are missing tactics that are right in front of you.",
  one_move_blunder:   "You are leaving pieces where they can be taken for free.",
  calculation_error:  "You are throwing games because you stop thinking too early.",
  positional:         "You are being outplayed. Your pieces have no plan.",
  endgame_collapse:   "You reach endgames you should win. You don't finish them.",
  opening_disaster:   "Your games are lost before they start.",
  time_collapse:      "You are losing on the clock, not on the board.",
  threw_winning:      "You are throwing winning positions.",
  piece_safety:       "You are giving away pieces for free.",
  ignore_threat:      "You are not looking at what your opponent is doing.",
  calculation_depth:  "You are throwing games because you stop thinking too early.",
  missed_tactic:      "You are missing simple winning chances.",
  king_safety:        "You are leaving your king exposed and getting punished.",
  conversion:         "You get the advantage. Then you give it back.",
};

// Mistake → behavior (LOCKED: what they do wrong. Sharp, no filler.)
const BEHAVIORS = {
  tactical_miss:      "You play your move without scanning the board.\nThat's where your games collapse.",
  one_move_blunder:   "You move without checking if your piece is protected.\nThat's where your games collapse.",
  calculation_error:  "You stop checking your opponent after you decide your move.\nThat's where your games collapse.",
  positional:         "You move pieces without a plan.\nYour opponent outmaneuvers you every time.",
  endgame_collapse:   "You reach winning endgames but don't know the technique.\nSo you draw — or worse.",
  opening_disaster:   "You make unsound moves in the first 10.\nBy the middlegame, you're already lost.",
  time_collapse:      "You spend time on easy moves.\nThen you panic on the ones that matter.",
  threw_winning:      "You stop checking your opponent once you're ahead.\nThat's where your games collapse.",
  piece_safety:       "You move without checking if your pieces are safe.\nThat's where your games collapse.",
  ignore_threat:      "You play your move without checking what your opponent is attacking.\nThat's where your games collapse.",
  calculation_depth:  "You stop checking your opponent after you decide your move.\nThat's where your games collapse.",
  missed_tactic:      "You don't scan for captures, checks, and threats.\nThe winning move is there. You're not looking.",
  king_safety:        "You attack before your king is safe.\nYour opponent punishes it every time.",
  conversion:         "You stop checking your opponent once you're ahead.\nThat's where your games collapse.",
};

// Mistake → behavior-specific rule (only shown in UNLOCKED state)
const RULES = {
  tactical_miss:      "Before you move — check for captures, checks, and threats.",
  one_move_blunder:   "Before you move — is anything I own under attack?",
  calculation_error:  "Before you move — check their best reply.",
  positional:         "Before you move — what is my worst piece doing?",
  endgame_collapse:   "In the endgame — activate your king first.",
  opening_disaster:   "First 10 moves — develop, control center, castle.",
  time_collapse:      "Under 2 minutes — play the simplest move.",
  threw_winning:      "Stay alert even when you're winning.",
  piece_safety:       "Before you move — is anything I own under attack?",
  ignore_threat:      "Before you move — what is my opponent attacking?",
  calculation_depth:  "Before you move — check their best reply.",
  missed_tactic:      "Before you move — is there a tactic here?",
  king_safety:        "Before you attack — is my king safe?",
  conversion:         "When ahead — simplify. Don't get creative.",
};

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [coaching, setCoaching] = useState(null);
  const [lastGameHook, setLastGameHook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pageState, setPageState] = useState("loading");

  useEffect(() => {
    (async () => {
      try {
        const [labRes, dashRes] = await Promise.all([
          fetch(`${API}/lab-coach-pick`, { credentials: "include" }),
          fetch(`${API}/home/dashboard-v2`, { credentials: "include" }),
        ]);

        let hasGames = false;
        let isAnalyzing = false;

        if (dashRes.ok) {
          const d = await dashRes.json();
          if (d.games_analyzed > 0) hasGames = true;
          else if (d.games_imported > 0) isAnalyzing = true;

          // Last game hook for UNLOCKED state
          if (d.last_battle?.behavior) {
            setLastGameHook(d.last_battle.behavior);
          }
        }

        if (labRes.ok) {
          const labData = await labRes.json();
          if (labData.total_count > 0) hasGames = true;
          setCoaching(labData.coaching);
        }

        if (!hasGames && !isAnalyzing) setPageState("empty");
        else if (isAnalyzing && !hasGames) setPageState("analyzing");
        else setPageState("ready");

      } catch (e) {
        setPageState("empty");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  if (pageState === "empty") {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-24 text-center" data-testid="home-page">
          <div className="w-14 h-14 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-6 shadow-lg shadow-amber-500/20">
            <Brain className="w-6 h-6 text-black" strokeWidth={2} />
          </div>
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-3">Your coach is waiting.</h1>
          <p className="text-muted-foreground mb-8 text-sm">Import your games. Your coach will tell you what's holding you back.</p>
          <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20" data-testid="import-cta">
            <Import className="w-4 h-4 inline mr-2" strokeWidth={2} />Import Games
          </button>
        </div>
      </Layout>
    );
  }

  if (pageState === "analyzing") {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-24 text-center" data-testid="home-page">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">Your coach is watching your games.</h1>
          <p className="text-muted-foreground text-sm mb-8">This takes a few minutes.</p>
          <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20">
            <Swords className="w-4 h-4 inline mr-2" strokeWidth={2} />Play with Coach
          </button>
        </div>
      </Layout>
    );
  }

  // ═══════════════════════════════════════════
  // MAIN — THE CONFRONTATION
  // ═══════════════════════════════════════════

  const root = coaching?.root_problem;
  const topProblem = coaching?.top_problems?.[0];
  const lock = coaching?.training_lock;
  const isUnlocked = lock?.unlocked;
  const pg = coaching?.priority_game;

  const mistakeKey = topProblem?.category || root?.pattern || "calculation_depth";
  const baseHeadline = HEADLINES[mistakeKey] || HEADLINES.calculation_depth;
  const behavior = BEHAVIORS[mistakeKey] || BEHAVIORS.calculation_depth;
  const rule = RULES[mistakeKey] || RULES.calculation_depth;

  // Anger escalation — prefix changes when problem returns after being resolved
  const lifecycle = coaching?.lifecycle;
  const angerPrefix = lifecycle?.anger_config?.prefix || "";
  const headline = angerPrefix + baseHeadline;

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-10" data-testid="home-page">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >

          {/* ═══ HEADLINE — visually dominant ═══ */}
          <h1 className="text-2xl sm:text-[28px] font-heading text-foreground tracking-tight leading-[1.2] mb-6">
            {headline}
          </h1>

          {/* ═══ LOCKED: behavior + tension. No answers. ═══ */}
          {!isUnlocked && (
            <div className="space-y-6">
              <p className="text-[15px] text-muted-foreground leading-[1.7] whitespace-pre-line">
                {behavior}
              </p>

              <div className="space-y-1">
                <p className="text-sm text-foreground/50">Next time you play, this will happen again.</p>
                <p className="text-sm text-foreground/80 font-medium">Unless you fix it.</p>
              </div>
            </div>
          )}

          {/* ═══ UNLOCKED: behavior + rule + directive. No stats. ═══ */}
          {isUnlocked && (
            <div className="space-y-5">
              {/* Behavior */}
              <p className="text-[15px] text-muted-foreground leading-[1.7] whitespace-pre-line">
                {behavior}
              </p>

              {/* Rule — separate coaching moment */}
              <div className="py-4 px-4 -mx-4 rounded-lg bg-amber-500/[0.04] border-y border-amber-500/10">
                <p className="text-[15px] text-foreground font-medium">{rule}</p>
              </div>

              {/* Directive */}
              <p className="text-sm text-foreground/60 font-medium">
                Next game — don't repeat this.
              </p>
            </div>
          )}

          {/* ═══ ACTIONS — clear hierarchy ═══ */}
          <div className="mt-8 space-y-3">
            <button
              onClick={() => navigate("/play-with-coach")}
              className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
              data-testid="coach-cta"
            >
              <Swords className="w-4.5 h-4.5" strokeWidth={2} />
              Play with Coach
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>

            <button
              onClick={() => navigate(root?.pattern ? `/training?focus=${root.pattern}` : "/lab")}
              className="w-full py-3 text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center gap-1.5"
            >
              <Target className="w-3.5 h-3.5" strokeWidth={1.5} />
              Fix this before you play (3 min)
            </button>
          </div>

        </motion.div>
      </div>
    </Layout>
  );
};

export default HomePage;
