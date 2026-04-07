/**
 * HOME PAGE — THE TRIGGER
 *
 * A coach stopped you and said something important.
 * That's it. Nothing else.
 *
 * 1. Truth (1-2 lines)
 * 2. Evidence (1 line)
 * 3. Rule (short)
 * 4. ONE CTA
 *
 * No game list. No stats. No multiple buttons. No scrolling.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ChevronRight, Swords, Import,
  Brain, Target, Trophy, AlertTriangle, Flame
} from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [coaching, setCoaching] = useState(null);
  const [streak, setStreak] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hasGames, setHasGames] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [gamesImported, setGamesImported] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        // Single source of truth: lab-coach-pick
        const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setCoaching(data.coaching);
          setStreak(null); // Will get from dashboard

          if (data.total_count === 0) {
            setHasGames(false);
          }
        } else {
          setHasGames(false);
        }

        // Get streak + basic state from dashboard
        const dashRes = await fetch(`${API}/home/dashboard-v2`, { credentials: "include" });
        if (dashRes.ok) {
          const dashData = await dashRes.json();
          setStreak(dashData.streak);
          if (dashData.games_analyzed === 0 && dashData.games_imported > 0) {
            setAnalyzing(true);
            setGamesImported(dashData.games_imported);
          }
          if (dashData.games_analyzed === 0 && dashData.games_imported === 0) {
            setHasGames(false);
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  // ── No games ──
  if (!hasGames && !analyzing) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-4 py-24 text-center" data-testid="home-page">
          <div className="w-14 h-14 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-6 shadow-lg shadow-amber-500/20">
            <Brain className="w-6 h-6 text-black" strokeWidth={2} />
          </div>
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-3">Your coach is waiting.</h1>
          <p className="text-muted-foreground mb-8 text-sm leading-relaxed">
            Import your games. Your coach will study them and tell you exactly what's holding you back.
          </p>
          <button onClick={() => navigate("/import")}
            className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20"
            data-testid="import-cta">
            <Import className="w-4 h-4 inline mr-2" strokeWidth={2} />Import Games
          </button>
        </div>
      </Layout>
    );
  }

  // ── Analyzing ──
  if (analyzing) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-4 py-24 text-center" data-testid="home-page">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">Your coach is studying your games.</h1>
          <p className="text-muted-foreground text-sm mb-8">Analyzing {gamesImported} games. This takes a few minutes.</p>
          <button onClick={() => navigate("/play-with-coach")}
            className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20">
            <Swords className="w-4 h-4 inline mr-2" strokeWidth={2} />Play with Coach
          </button>
          <div className="mt-6">
            <button onClick={() => window.location.reload()} className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors">
              Check if ready
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  // ── MAIN: The trigger ──
  const c = buildTrigger(coaching, streak);

  return (
    <Layout user={user}>
      <div className="max-w-lg mx-auto px-4 py-10" data-testid="home-page">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>

          {/* Coach avatar */}
          <div className="flex items-center gap-3 mb-6">
            <div className="relative">
              <div className="w-11 h-11 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/10 flex items-center justify-center">
                <Brain className="w-5 h-5 text-amber-500" />
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-background" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">Coach says</p>
              {c.badge && <p className={`text-[10px] font-semibold ${c.badgeColor}`}>{c.badge}</p>}
            </div>
          </div>

          {/* The truth */}
          <h1 className="text-xl sm:text-2xl font-heading text-foreground tracking-tight leading-snug mb-3">
            {c.truth}
          </h1>

          {/* Evidence */}
          {c.evidence && (
            <p className="text-sm text-muted-foreground leading-relaxed mb-5">{c.evidence}</p>
          )}

          {/* Rule */}
          {c.rule && (
            <div className="p-3.5 rounded-xl bg-amber-500/5 border border-amber-500/15 mb-6">
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">{c.ruleName}</p>
              <p className="text-sm text-foreground">{c.rule}</p>
            </div>
          )}

          {/* ONE CTA */}
          <button
            onClick={() => navigate(c.actionHref)}
            className="w-full py-3.5 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/15 flex items-center justify-center gap-2"
            data-testid="coach-cta"
          >
            <c.actionIcon className="w-4 h-4" strokeWidth={2} />
            {c.actionLabel}
            <ChevronRight className="w-3.5 h-3.5 opacity-60" />
          </button>

          {/* Streak — tiny, at the bottom */}
          {streak?.count >= 2 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <Flame className={`w-3.5 h-3.5 ${streak.type === "W" ? "text-emerald-500" : "text-red-400"}`} />
              <span className={`text-xs font-semibold ${streak.type === "W" ? "text-emerald-500" : "text-red-400"}`}>
                {streak.count}-game {streak.type === "W" ? "win" : "loss"} streak
              </span>
            </div>
          )}

        </motion.div>
      </div>
    </Layout>
  );
};


// ═══ TRIGGER ENGINE ═══
// Outputs: truth, evidence, rule, ONE action.

function buildTrigger(coaching, streak) {
  const defaults = {
    badge: null, badgeColor: "text-muted-foreground",
    truth: "Your coach is ready. Let's play.",
    evidence: null,
    rule: null, ruleName: null,
    actionLabel: "Play with Coach",
    actionHref: "/play-with-coach",
    actionIcon: Swords,
  };

  // ── Win streak — celebrate, keep going ──
  if (streak?.type === "W" && streak.count >= 3) {
    return { ...defaults,
      badge: `${streak.count} wins in a row`, badgeColor: "text-emerald-500",
      truth: "You're playing the best chess I've seen from you.",
      evidence: "Don't change anything. Just play.",
      actionLabel: "Play Another", actionIcon: Swords,
    };
  }

  // ── Loss streak — stop and fix ──
  if (streak?.type === "L" && streak.count >= 3) {
    return { ...defaults,
      badge: `${streak.count} losses in a row`, badgeColor: "text-red-400",
      truth: "Stop. You're repeating the same mistake.",
      evidence: "Review one game before you play again.",
      actionLabel: "Open Lab",
      actionHref: "/lab",
      actionIcon: Brain,
    };
  }

  // ── Has coaching data ──
  if (coaching?.root_problem && coaching?.diagnosis) {
    const diag = coaching.diagnosis;
    const root = coaching.root_problem;
    const rule = coaching.rule;
    const lock = coaching.training_lock;
    const pg = coaching.priority_game;

    // Impact line
    let evidence = "This is costing you games.";
    const totalGames = root.games_affected || 0;
    if (totalGames >= 15) {
      evidence = "This is happening in almost every game you play.";
    } else if (totalGames >= 5) {
      evidence = "This is where your games are breaking.";
    }

    // Pain hook — only if strong signal from priority game
    if (pg?.was_winning && pg?.result === "L") {
      evidence += " You lost a winning game because of this.";
    } else if (root.thrown_games > 0) {
      evidence += ` You threw ${root.thrown_games} winning position${root.thrown_games > 1 ? "s" : ""}.`;
    }

    // CTA: locked → Fix This Now. Unlocked → Open Lab.
    let actionLabel = "Fix This Now";
    let actionHref = `/training?focus=${root.pattern}`;
    let actionIcon = Target;

    if (lock?.unlocked) {
      actionLabel = "Open Lab";
      actionHref = "/lab";
      actionIcon = Brain;
    }

    // Use the #1 aggregated problem as the truth, fall back to diagnosis
    const topProblem = coaching.top_problems?.[0];
    const truthText = topProblem
      ? topProblem.label  // "Missed a simple tactic" — from game reason aggregation
      : diag.short;       // "You miss winning chances" — from pattern diagnosis

    return {
      badge: "active focus", badgeColor: "text-amber-500",
      truth: truthText,
      evidence: evidence,
      rule: rule?.rule || null,
      ruleName: rule?.name || null,
      actionLabel,
      actionHref,
      actionIcon,
    };
  }

  // ── Has coaching but no root problem (edge case: improving) ──
  if (coaching && !coaching.root_problem) {
    return { ...defaults,
      truth: "No major patterns right now. Keep playing.",
      evidence: "Your coach is watching. Play a game.",
    };
  }

  return defaults;
}

export default HomePage;
