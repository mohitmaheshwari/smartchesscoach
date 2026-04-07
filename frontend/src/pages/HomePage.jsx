/**
 * HOME — "Face the problem"
 *
 * Headline (pain) → Proof (trust) → Insight (sharp) → Action (fix)
 * Nothing else.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, Swords, Import, Target, Brain, Flame } from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [coaching, setCoaching] = useState(null);
  const [streak, setStreak] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pageState, setPageState] = useState("loading"); // loading | empty | analyzing | ready

  useEffect(() => {
    (async () => {
      try {
        const [labRes, dashRes] = await Promise.all([
          fetch(`${API}/lab-coach-pick`, { credentials: "include" }),
          fetch(`${API}/home/dashboard-v2`, { credentials: "include" }),
        ]);

        if (labRes.ok) {
          const labData = await labRes.json();
          setCoaching(labData.coaching);
          if (labData.total_count === 0) setPageState("empty");
          else setPageState("ready");
        } else {
          setPageState("empty");
        }

        if (dashRes.ok) {
          const d = await dashRes.json();
          setStreak(d.streak);
          if (d.games_analyzed === 0 && d.games_imported > 0) setPageState("analyzing");
          if (d.games_analyzed === 0 && d.games_imported === 0) setPageState("empty");
        }
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

  // ── Empty ──
  if (pageState === "empty") {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-4 py-24 text-center" data-testid="home-page">
          <div className="w-14 h-14 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-6 shadow-lg shadow-amber-500/20">
            <Brain className="w-6 h-6 text-black" strokeWidth={2} />
          </div>
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-3">Your coach is waiting.</h1>
          <p className="text-muted-foreground mb-8 text-sm">Import your games. Your coach will tell you exactly what's holding you back.</p>
          <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20" data-testid="import-cta">
            <Import className="w-4 h-4 inline mr-2" strokeWidth={2} />Import Games
          </button>
        </div>
      </Layout>
    );
  }

  // ── Analyzing ──
  if (pageState === "analyzing") {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-4 py-24 text-center" data-testid="home-page">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
            <div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">Your coach is studying your games.</h1>
          <p className="text-muted-foreground text-sm mb-8">This takes a few minutes.</p>
          <button onClick={() => navigate("/play-with-coach")} className="px-6 py-3 text-sm gradient-gold text-black rounded-lg hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20">
            <Swords className="w-4 h-4 inline mr-2" strokeWidth={2} />Play with Coach
          </button>
        </div>
      </Layout>
    );
  }

  // ── MAIN ──
  const root = coaching?.root_problem;
  const diag = coaching?.diagnosis;
  const rule = coaching?.rule;
  const lock = coaching?.training_lock;
  const topProblem = coaching?.top_problems?.[0];

  // Build the content
  const headline = topProblem?.label || diag?.short || "Your coach found something to fix.";

  let proof = "";
  if (root) {
    const n = root.games_affected || 0;
    if (root.thrown_games > 0) {
      proof = `You threw ${root.thrown_games} winning position${root.thrown_games > 1 ? "s" : ""}. This happened in ${n} of your recent games.`;
    } else if (n >= 15) {
      proof = "This is happening in almost every game you play.";
    } else if (n >= 5) {
      proof = `Happened in ${n} of your recent games.`;
    } else if (n > 0) {
      proof = `This showed up in ${n} game${n > 1 ? "s" : ""} recently.`;
    }
  }

  const insight = topProblem?.description || diag?.detail || "";

  const isLocked = lock && !lock.unlocked;
  const actionLabel = isLocked ? "Start Fixing This" : "Open Lab";
  const actionHref = isLocked ? `/training?focus=${root?.pattern || ""}` : "/lab";

  // Streak override
  const isWinStreak = streak?.type === "W" && streak?.count >= 3;
  const isLossStreak = streak?.type === "L" && streak?.count >= 3;

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-4 py-12" data-testid="home-page">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>

          {/* Win streak override */}
          {isWinStreak && (
            <div className="text-center mb-8">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center mx-auto mb-3">
                <Flame className="w-5 h-5 text-emerald-500" />
              </div>
              <h1 className="text-xl font-heading text-foreground mb-1">You're playing great chess.</h1>
              <p className="text-sm text-muted-foreground mb-6">{streak.count} wins in a row. Don't change anything.</p>
              <button onClick={() => navigate("/play-with-coach")} className="w-full py-3.5 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/15 flex items-center justify-center gap-2">
                <Swords className="w-4 h-4" strokeWidth={2} />Play Another<ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </div>
          )}

          {/* Loss streak override */}
          {isLossStreak && !isWinStreak && (
            <div className="text-center mb-8">
              <h1 className="text-xl font-heading text-foreground mb-1">Stop. You're repeating the same mistake.</h1>
              <p className="text-sm text-muted-foreground mb-6">Review one game before you play again.</p>
              <button onClick={() => navigate("/lab")} className="w-full py-3.5 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/15 flex items-center justify-center gap-2">
                <Brain className="w-4 h-4" strokeWidth={2} />Open Lab<ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </div>
          )}

          {/* Normal: coaching data */}
          {!isWinStreak && !isLossStreak && (
            <>
              {/* Headline — pain */}
              <h1 className="text-2xl font-heading text-foreground tracking-tight leading-snug mb-3">
                {headline}
              </h1>

              {/* Proof — trust */}
              {proof && (
                <p className="text-sm text-muted-foreground leading-relaxed mb-4">{proof}</p>
              )}

              {/* Insight — sharp */}
              {insight && (
                <p className="text-sm text-foreground/70 leading-relaxed mb-5">{insight}</p>
              )}

              {/* Rule */}
              {rule && (
                <div className="p-3.5 rounded-xl bg-amber-500/5 border border-amber-500/15 mb-6">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400 mb-1">{rule.name}</p>
                  <p className="text-sm text-foreground">{rule.rule}</p>
                </div>
              )}

              {/* ONE action */}
              <button
                onClick={() => navigate(actionHref)}
                className="w-full py-3.5 text-sm font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/15 flex items-center justify-center gap-2"
                data-testid="coach-cta"
              >
                <Target className="w-4 h-4" strokeWidth={2} />
                {actionLabel}
                <ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </>
          )}

          {/* Streak — micro signal */}
          {streak?.count >= 2 && !isWinStreak && !isLossStreak && (
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

export default HomePage;
