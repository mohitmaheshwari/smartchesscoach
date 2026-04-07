/**
 * HOME — "A coach stopping you before your next mistake."
 *
 * One flow. No locked/unlocked. Adapts to:
 * - anger level (first time / recurring / returned / chronic)
 * - last game (did they just repeat it?)
 * - game count (how many times)
 *
 * Structure:
 * 1. Headline (anger-aware)
 * 2. Behavior
 * 3. Last game hook (if relevant)
 * 4. Rule (always — earned or not, the coach speaks)
 * 5. Tension/directive
 * 6. Actions
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, Swords, Import, Target, Brain } from "lucide-react";

const HEADLINES = {
  tactical_miss:      "You are missing tactics that are right in front of you.",
  one_move_blunder:   "You are giving away pieces for free.",
  calculation_error:  "You are losing games because you stop thinking too early.",
  positional:         "You are being outplayed. Your pieces have no plan.",
  endgame_collapse:   "You reach endgames you should win. You don't finish them.",
  opening_disaster:   "Your games are lost before they start.",
  time_collapse:      "You are losing on the clock, not on the board.",
  threw_winning:      "You are throwing winning positions.",
  piece_safety:       "You are giving away pieces for free.",
  ignore_threat:      "You are not looking at what your opponent is doing.",
  calculation_depth:  "You are losing games because you stop thinking too early.",
  missed_tactic:      "You are missing simple winning chances.",
  king_safety:        "You are leaving your king exposed.",
  conversion:         "You get the advantage. Then you give it back.",
};

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

// Behavior variations based on anger + count
const BEHAVIOR_VARIANTS = {
  recurring: {
    threw_winning:      "You keep stopping your thinking once you're ahead.\nThis is not new. This has been happening.",
    calculation_depth:  "You keep deciding your move without checking the reply.\nYou've done this over and over.",
    tactical_miss:      "You keep missing tactics that are right there.\nThis pattern is repeating.",
  },
  returned: {
    threw_winning:      "You fixed this. Then you stopped applying the rule.\nNow it's back.",
    calculation_depth:  "This was resolved. You stopped doing the check.\nNow the same mistake is returning.",
    tactical_miss:      "You were getting better at this. Then you stopped scanning.\nNow you're missing tactics again.",
  },
  chronic: {
    threw_winning:      "We fixed this before. More than once.\nEvery time you stop paying attention, it comes back.\nThis is the pattern behind the pattern.",
    calculation_depth:  "This has been fixed and broken multiple times.\nThe issue is not chess. It's discipline.\nYou know the rule. You're not applying it.",
    tactical_miss:      "You've solved this in training. Multiple times.\nBut in games, you stop looking.\nThis is not a knowledge problem.",
  },
};

const RULES = {
  tactical_miss:      "Before every move — check captures, checks, and threats.",
  one_move_blunder:   "Before every move — is anything I own under attack?",
  calculation_error:  "Before every move — what will they do next?",
  positional:         "Before every move — which piece is doing the least?",
  endgame_collapse:   "In the endgame — activate your king first.",
  opening_disaster:   "First 10 moves — develop, control center, castle.",
  time_collapse:      "Under 2 minutes — play the simplest move.",
  threw_winning:      "Stay alert even when you're winning.",
  piece_safety:       "Before every move — is anything I own under attack?",
  ignore_threat:      "Before every move — what is my opponent attacking?",
  calculation_depth:  "Before every move — what will they do next?",
  missed_tactic:      "Before every move — is there a tactic here?",
  king_safety:        "Before you attack — is my king safe?",
  conversion:         "When ahead — simplify. Don't get creative.",
};

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [coaching, setCoaching] = useState(null);
  const [lastSession, setLastSession] = useState(null);
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

          // Check if last game/session matches active problem
          if (d.last_battle) {
            setLastSession({
              opponent: d.last_battle.opponent,
              result: d.last_battle.result,
              gameReason: d.last_battle.game_reason,
            });
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
  const lifecycle = coaching?.lifecycle;
  const anger = lifecycle?.anger || "first_time";

  const mistakeKey = topProblem?.category || root?.pattern || "calculation_depth";

  // Headline — anger-aware prefix
  const angerPrefix = lifecycle?.anger_config?.prefix || "";
  const headline = angerPrefix + (HEADLINES[mistakeKey] || HEADLINES.calculation_depth);

  // Behavior — varies with anger level
  const behaviorVariant = BEHAVIOR_VARIANTS[anger]?.[mistakeKey];
  const behavior = behaviorVariant || BEHAVIORS[mistakeKey] || BEHAVIORS.calculation_depth;

  // Rule
  const rule = RULES[mistakeKey] || RULES.calculation_depth;

  // Last game hook — did they just repeat this mistake?
  const lastGameMatchesProblem = lastSession?.gameReason?.category === (topProblem?.category || root?.pattern);
  const lastGameWasLoss = lastSession?.result && (
    lastSession.result.includes("0-1") || lastSession.result.includes("1-0") || lastSession.result === "L"
  );

  // Game count
  const gameCount = topProblem?.count || root?.games_affected || 0;

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-10" data-testid="home-page">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >

          {/* ═══ HEADLINE ═══ */}
          <h1 className="text-2xl sm:text-[28px] font-heading text-foreground tracking-tight leading-[1.2] mb-6">
            {headline}
          </h1>

          {/* ═══ BEHAVIOR ═══ */}
          <p className="text-[15px] text-muted-foreground leading-[1.7] whitespace-pre-line mb-5">
            {behavior}
          </p>

          {/* ═══ LAST GAME HOOK — "you just did it again" ═══ */}
          {lastGameMatchesProblem && lastGameWasLoss && (
            <p className="text-sm text-red-400/80 font-medium mb-5">
              You just did this in your last game.
            </p>
          )}

          {/* ═══ EVIDENCE — game count (subtle, not headline) ═══ */}
          {gameCount >= 3 && !lastGameMatchesProblem && (
            <p className="text-sm text-foreground/40 mb-5">
              {gameCount >= 10
                ? "This is happening in almost every game."
                : `This happened in ${gameCount} of your recent games.`
              }
            </p>
          )}

          {/* ═══ RULE ═══ */}
          <div className="py-4 px-4 -mx-4 rounded-lg bg-amber-500/[0.04] border-y border-amber-500/10 mb-5">
            <p className="text-[15px] text-foreground font-medium">{rule}</p>
          </div>

          {/* ═══ DIRECTIVE ═══ */}
          <p className="text-sm text-foreground/50 font-medium mb-0">
            {lastGameMatchesProblem
              ? "Try again. Apply the rule this time."
              : "Next game — don't repeat this."
            }
          </p>

          {/* ═══ ACTIONS ═══ */}
          <div className="mt-8 space-y-3">
            <button
              onClick={() => navigate("/play-with-coach")}
              className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
              data-testid="coach-cta"
            >
              <Swords className="w-4 h-4" strokeWidth={2} />
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
