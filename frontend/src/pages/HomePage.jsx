/**
 * HOME — "Opening a text from your coach."
 *
 * Personal, specific, forward-looking.
 * 1. Greeting with relationship context
 * 2. Last session recap (what happened)
 * 3. Current problem (what's holding you back)
 * 4. Today's plan (what to do next)
 * 5. One clear CTA
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  ChevronRight, Swords, Target, Brain, Import,
  TrendingUp, Trophy, XCircle, Minus, BookOpen, Zap, Flame,
} from "lucide-react";
import LichessBoard from "@/components/LichessBoard";

const PROBLEM_HEADLINES = {
  tactical_miss: "You are missing tactics that are right in front of you.",
  one_move_blunder: "You are giving away pieces for free.",
  calculation_error: "You are losing games because you stop thinking too early.",
  calculation_depth: "You are losing games because you stop thinking too early.",
  positional: "You are being outplayed. Your pieces have no plan.",
  endgame_collapse: "You reach endgames you should win. You don't finish them.",
  opening_disaster: "Your games are lost before they start.",
  time_collapse: "You are losing on the clock, not on the board.",
  threw_winning: "You are throwing winning positions.",
  piece_safety: "You are giving away pieces for free.",
  ignore_threat: "You are not looking at what your opponent is doing.",
  missed_tactic: "You are missing simple winning chances.",
  king_safety: "You are leaving your king exposed.",
  conversion: "You get the advantage. Then you give it back.",
};

const PROBLEM_RULES = {
  tactical_miss: "Before every move — check captures, checks, and threats.",
  one_move_blunder: "Before every move — is anything I own under attack?",
  calculation_error: "Before every move — what will they do next?",
  calculation_depth: "Before every move — what will they do next?",
  positional: "Before every move — which piece is doing the least?",
  endgame_collapse: "In the endgame — activate your king first.",
  opening_disaster: "First 10 moves — develop, control center, castle.",
  time_collapse: "Under 2 minutes — play the simplest move.",
  threw_winning: "When ahead — trade pieces, not pawns.",
  piece_safety: "Before every move — is anything I own under attack?",
  ignore_threat: "Before every move — what is my opponent attacking?",
  missed_tactic: "Before every move — is there a tactic here?",
  king_safety: "Before you attack — is my king safe?",
  conversion: "When ahead — simplify. Don't get creative.",
};

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hasGames, setHasGames] = useState(false);
  const [proof, setProof] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [homeRes, dashRes, proofRes] = await Promise.all([
          fetch(`${API}/home/coach-home`, { credentials: "include" }),
          fetch(`${API}/home/dashboard-v2`, { credentials: "include" }),
          fetch(`${API}/progress/improvement-proof`, { credentials: "include" }),
        ]);
        if (homeRes.ok) setData(await homeRes.json());
        if (dashRes.ok) {
          const d = await dashRes.json();
          if (d.games_analyzed > 0 || d.games_imported > 0) setHasGames(true);
        }
        if (proofRes.ok) {
          const proofData = await proofRes.json();
          console.log("[Home] Improvement proof:", proofData?.has_data, "primary:", proofData?.primary_pattern?.label, "reduction:", proofData?.primary_pattern?.reduction_pct);
          setProof(proofData);
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
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

  // Empty state — no games yet
  if (!hasGames && !data?.last_session) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-24 text-center" data-testid="home-page">
          <div className="w-14 h-14 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-6 shadow-lg shadow-amber-500/20">
            <Brain className="w-6 h-6 text-black" strokeWidth={2} />
          </div>
          <h1 className="text-2xl font-heading text-foreground tracking-tight mb-3">Your coach is waiting.</h1>
          <p className="text-muted-foreground mb-8 text-sm">Import your games or play with the coach to get started.</p>
          <div className="space-y-3">
            <button onClick={() => navigate("/play-with-coach")}
              className="w-full px-6 py-3 text-sm gradient-gold text-black rounded-xl hover:opacity-90 transition-all font-semibold shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
            >
              <Swords className="w-4 h-4" strokeWidth={2} />Play with Coach
            </button>
            <button onClick={() => navigate("/import")}
              className="w-full px-6 py-3 text-sm border border-border text-foreground rounded-xl hover:bg-muted/50 transition-all font-medium flex items-center justify-center gap-2"
            >
              <Import className="w-4 h-4" strokeWidth={2} />Import Games
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  const greeting = data?.greeting || {};
  const lastSession = data?.last_session;
  const problem = data?.problem;
  const plan = data?.todays_plan || {};
  const warmup = data?.warmup;

  // Extract a reasonable display name from email
  const rawName = user?.display_name || user?.name || user?.email?.split("@")[0] || "";
  // Split on dots, underscores, or camelCase boundaries to get first name
  const nameParts = rawName.split(/[._-]/).filter(Boolean);
  const firstName = nameParts[0] || "";
  const displayName = firstName.length <= 12
    ? firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase()
    : "";

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-8" data-testid="home-page">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="space-y-6"
        >

          {/* ─── GREETING ─── */}
          <div>
            <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">
              {displayName ? `Hey ${displayName}.` : "Welcome back."}
            </h1>
            {greeting.games_together > 0 && (
              <p className="text-sm text-muted-foreground">
                {greeting.games_together > 1
                  ? `You've played ${greeting.games_together} games with me.`
                  : "We've played 1 game together."
                }
                {greeting.improving && greeting.acc_old && greeting.acc_new
                  ? ` Your accuracy went from ${greeting.acc_old}% to ${greeting.acc_new}%. That's real improvement.`
                  : greeting.avg_accuracy
                    ? ` ${greeting.avg_accuracy}% average accuracy.`
                    : ""
                }
              </p>
            )}
          </div>

          {/* ─── IMPROVEMENT PROOF ─── */}
          {proof?.has_data && (proof?.primary_pattern?.reduction_pct > 0 || proof?.streaks?.no_blunder_games >= 3 || proof?.streaks?.no_big_mistake_games >= 3 || proof?.streaks?.no_threat_miss_games >= 3 || proof?.accuracy?.delta >= 2) && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 }}
              className="rounded-2xl border-2 border-emerald-500/20 bg-emerald-500/[0.03] p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                <span className="text-sm font-semibold text-foreground">
                  {proof.primary_pattern?.reduction_pct > 0
                    ? `${proof.primary_pattern.reduction_pct}% fewer ${proof.primary_pattern.label.toLowerCase()} mistakes`
                    : proof.accuracy?.delta >= 2
                      ? `Accuracy up ${proof.accuracy.delta}% recently`
                      : "You're staying consistent"
                  }
                </span>
              </div>

              {proof.streaks?.no_blunder_games >= 2 && (
                <p className="text-xs text-emerald-500/70 mb-2">
                  <Flame className="w-3 h-3 inline mr-1" />{proof.streaks.no_blunder_games} games in a row with no blunders
                </p>
              )}

              {proof.streaks?.no_big_mistake_games >= 3 && (
                <p className="text-xs text-emerald-500/70 mb-2">
                  <Flame className="w-3 h-3 inline mr-1" />{proof.streaks.no_big_mistake_games} games without a major mistake
                </p>
              )}

              {proof.streaks?.no_threat_miss_games >= 3 && (
                <p className="text-xs text-emerald-500/70 mb-2">
                  <Flame className="w-3 h-3 inline mr-1" />{proof.streaks.no_threat_miss_games} games without missing a threat
                </p>
              )}

              {/* Before/After — show first example only on home */}
              {proof.before_after?.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-muted-foreground mb-2">{proof.before_after[0].message}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-[9px] uppercase tracking-widest font-bold text-red-400/60 mb-1">Before</p>
                      <div className="rounded-lg overflow-hidden border border-red-500/20">
                        <LichessBoard fen={proof.before_after[0].old_fen} viewOnly={true} width={150} />
                      </div>
                    </div>
                    <div>
                      <p className="text-[9px] uppercase tracking-widest font-bold text-emerald-400/60 mb-1">Now</p>
                      <div className="rounded-lg overflow-hidden border border-emerald-500/20">
                        <LichessBoard fen={proof.before_after[0].new_fen} viewOnly={true} width={150} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {proof.primary_pattern?.reduction_pct > 0 && (
                <p className="text-xs text-foreground/60 mt-3">
                  This used to happen every game. Now it doesn't.
                </p>
              )}
            </motion.div>
          )}

          {/* ─── LAST SESSION RECAP ─── */}
          {lastSession && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="rounded-2xl border border-border bg-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                {lastSession.result === "win" ? (
                  <Trophy className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                ) : lastSession.result === "loss" ? (
                  <XCircle className="w-4 h-4 text-red-400" strokeWidth={2} />
                ) : (
                  <Minus className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
                )}
                <span className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/50">
                  Last session
                </span>
              </div>
              <p className="text-sm text-foreground leading-relaxed">
                {lastSession.story}
              </p>
              {lastSession.accuracy > 0 && (
                <p className="text-xs text-muted-foreground mt-1.5">
                  {lastSession.total_moves} moves · {lastSession.accuracy}% accuracy
                </p>
              )}
            </motion.div>
          )}

          {/* ─── WHAT'S HOLDING YOU BACK ─── */}
          {problem?.category && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
            >
              <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground/40 mb-2">
                The thing that's still holding you back
              </p>
              <p className="text-[15px] text-foreground font-medium leading-snug mb-3">
                {PROBLEM_HEADLINES[problem.category] || `Your ${problem.category.replace(/_/g, " ")} needs work.`}
              </p>

              {/* Evidence + trend */}
              {problem.count >= 2 && (
                <p className="text-sm text-muted-foreground mb-3">
                  {problem.trending_better
                    ? `This happened in ${problem.count} games. But it's getting less frequent — you're improving.`
                    : problem.count >= 7
                      ? "This is happening in almost every game."
                      : `This happened in ${problem.count} of your recent games.`
                  }
                </p>
              )}

              {/* The rule */}
              <div className="py-3 px-4 rounded-xl bg-amber-500/[0.04] border border-amber-500/10">
                <p className="text-sm text-foreground font-medium">
                  {PROBLEM_RULES[problem.category] || "Think before you move."}
                </p>
              </div>
            </motion.div>
          )}

          {/* ─── TODAY'S PLAN ─── */}
          {plan.opening && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="rounded-2xl border-2 border-primary/20 bg-primary/[0.03] p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <BookOpen className="w-4 h-4 text-primary" strokeWidth={2} />
                <span className="text-[10px] uppercase tracking-widest font-bold text-primary">
                  Today's session
                </span>
              </div>
              <p className="text-sm text-foreground leading-relaxed mb-1">
                Play the <span className="font-semibold">{plan.opening}</span>
                {plan.branch && <> — <span className="font-semibold">{plan.branch}</span></>}
                .
              </p>
              {plan.reason && (
                <p className="text-xs text-muted-foreground">{plan.reason}</p>
              )}
            </motion.div>
          )}

          {/* ─── MAIN CTA ─── */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="space-y-3"
          >
            <button
              onClick={() => {
                const opening = plan.opening || "";
                navigate(`/play-with-coach${opening ? `?opening=${encodeURIComponent(opening)}` : ""}`);
              }}
              className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
              data-testid="coach-cta"
            >
              <Swords className="w-4 h-4" strokeWidth={2} />
              {plan.opening
                ? `Play ${plan.opening}${plan.branch ? ` — ${plan.branch}` : ""}`
                : "Play with Coach"
              }
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>

            {/* Warmup puzzles */}
            {warmup?.available && (
              <button
                onClick={() => navigate(`/training/pattern/${warmup.pattern}`)}
                className="w-full py-3 text-sm text-muted-foreground hover:text-foreground border border-border rounded-xl hover:bg-muted/50 transition-all flex items-center justify-center gap-2"
              >
                <Zap className="w-3.5 h-3.5" strokeWidth={2} />
                Quick warmup — {warmup.label} puzzles
                <span className="text-[10px] text-muted-foreground/40">3 min</span>
              </button>
            )}

            {/* Progress link */}
            <button
              onClick={() => navigate("/progress")}
              className="w-full py-2.5 text-xs text-muted-foreground/50 hover:text-muted-foreground transition-colors flex items-center justify-center gap-1"
            >
              <TrendingUp className="w-3 h-3" />
              See your full progress
            </button>
          </motion.div>

        </motion.div>
      </div>
    </Layout>
  );
};

export default HomePage;
