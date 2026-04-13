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
  const focusPlan = data?.focus_plan;

  // Determine the page mood — ONE message, not contradictory signals
  // 1. Last game clean + improving → celebrate
  // 2. Last game bad / focus violated → confront
  // 3. No recent data → neutral, just plan
  const lastGameWasGood = lastSession?.result === "win" || (lastSession?.accuracy >= 75 && lastSession?.total_moves >= 15);
  const hasImprovement = proof?.has_data && (proof?.primary_pattern?.reduction_pct > 15 || proof?.streaks?.no_big_mistake_games >= 3);
  const mood = lastGameWasGood && hasImprovement ? "celebrating"
    : lastGameWasGood ? "encouraging"
    : problem?.category ? "confronting"
    : "neutral";

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
            <h1 className="text-2xl font-heading text-foreground tracking-tight">
              {displayName ? `Hey ${displayName}.` : "Welcome back."}
            </h1>
          </div>

          {/* ═══ MOOD: CELEBRATING — last game good + improving ═══ */}
          {mood === "celebrating" && (
            <>
              {/* Improvement proof */}
              {proof?.primary_pattern?.reduction_pct > 0 && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
                  className="rounded-2xl border-2 border-emerald-500/20 bg-emerald-500/[0.03] p-4"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                    <span className="text-sm font-semibold text-foreground">
                      {proof.primary_pattern.reduction_pct}% fewer {proof.primary_pattern.label.toLowerCase()} mistakes
                    </span>
                  </div>
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
                  <p className="text-xs text-foreground/60 mt-3">This used to happen every game. Now it doesn't.</p>
                </motion.div>
              )}

              {/* Last session — brief, positive */}
              {lastSession && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}
                  className="rounded-2xl border border-emerald-500/15 bg-card p-4"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Trophy className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                    <span className="text-[10px] uppercase tracking-widest font-bold text-emerald-500/60">Last session</span>
                  </div>
                  <p className="text-sm text-foreground">{lastSession.story}</p>
                </motion.div>
              )}
            </>
          )}

          {/* ═══ MOOD: ENCOURAGING — last game good, no strong improvement data ═══ */}
          {mood === "encouraging" && lastSession && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
              className="rounded-2xl border border-emerald-500/15 bg-card p-4"
            >
              <div className="flex items-center gap-2 mb-1">
                <Trophy className="w-4 h-4 text-emerald-500" strokeWidth={2} />
                <span className="text-[10px] uppercase tracking-widest font-bold text-emerald-500/60">Last session</span>
              </div>
              <p className="text-sm text-foreground">{lastSession.story}</p>
              {lastSession.accuracy > 0 && lastSession.total_moves >= 15 && (
                <p className="text-xs text-muted-foreground mt-1.5">{lastSession.total_moves} moves · {lastSession.accuracy}% accuracy</p>
              )}
            </motion.div>
          )}

          {/* ═══ MOOD: CONFRONTING — last game bad, show the problem ═══ */}
          {mood === "confronting" && (
            <>
              {/* Last session — brief, not the focus */}
              {lastSession && (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
                  className="rounded-2xl border border-border bg-card p-3"
                >
                  <div className="flex items-center gap-2">
                    <XCircle className="w-3.5 h-3.5 text-red-400" strokeWidth={2} />
                    <p className="text-xs text-muted-foreground">{lastSession.story}</p>
                  </div>
                </motion.div>
              )}

              {/* The problem — the main event */}
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
                <p className="text-[15px] text-foreground font-medium leading-snug mb-3">
                  {PROBLEM_HEADLINES[problem.category] || `Your ${problem.category.replace(/_/g, " ")} needs work.`}
                </p>
                {problem.count >= 2 && (
                  <p className="text-sm text-muted-foreground mb-3">
                    {problem.trending_better
                      ? `This happened in ${problem.count} games. But it's getting less frequent.`
                      : problem.count >= 7
                        ? "This is happening in almost every game."
                        : `This happened in ${problem.count} of your recent games.`
                    }
                  </p>
                )}
                <div className="py-3 px-4 rounded-xl bg-amber-500/[0.04] border border-amber-500/10">
                  <p className="text-sm text-foreground font-medium">
                    {PROBLEM_RULES[problem.category] || focusPlan?.rule || "Think before you move."}
                  </p>
                </div>
              </motion.div>
            </>
          )}

          {/* ═══ MOOD: NEUTRAL — no strong signal ═══ */}
          {mood === "neutral" && lastSession && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
              className="rounded-2xl border border-border bg-card p-4"
            >
              <p className="text-sm text-foreground">{lastSession.story}</p>
            </motion.div>
          )}

          {/* ─── FOCUS PLAN (show only if games tracked, otherwise looks empty) ─── */}
          {focusPlan && focusPlan.games_played > 0 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }}
              className="rounded-2xl border border-border bg-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-4 h-4 text-primary" strokeWidth={2} />
                <span className="text-[10px] uppercase tracking-widest font-bold text-primary/60">Your focus</span>
              </div>
              <p className="text-sm font-medium text-foreground mb-1">{focusPlan.name}</p>
              <div className="flex items-center gap-3 mt-2">
                <div className="flex items-center gap-1.5">
                  {Array.from({ length: focusPlan.games_target }).map((_, i) => {
                    const r = focusPlan.game_results?.[i];
                    return (
                      <div key={i} className={`w-3 h-3 rounded-full border ${
                        !r ? "border-border" : r.clean ? "border-emerald-500 bg-emerald-500" : "border-red-400 bg-red-400"
                      }`} />
                    );
                  })}
                </div>
                <span className="text-xs text-muted-foreground">
                  {focusPlan.clean_count}/{focusPlan.clean_threshold} clean
                </span>
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

          {/* ─── MAIN CTA — after loss: train first. after win: play. ─── */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="space-y-3"
          >
            {/* After a loss: training is the PRIMARY action */}
            {mood === "confronting" && problem?.category && (
              <button
                onClick={() => {
                  const patternMap = {
                    threw_winning: "calculation_depth", tactical_miss: "tactical_oversight",
                    one_move_blunder: "piece_safety", calculation_error: "calculation_depth",
                    time_collapse: "calculation_depth", opening_disaster: "piece_safety",
                    endgame_collapse: "endgame_technique", positional: "calculation_depth",
                  };
                  navigate(`/training/prescribed?focus=${patternMap[problem.category] || problem.category}`);
                }}
                className="w-full py-4 text-[15px] font-semibold rounded-xl bg-foreground text-background hover:opacity-90 transition-all flex items-center justify-center gap-2"
                data-testid="train-cta"
              >
                <Target className="w-4 h-4" strokeWidth={2} />
                Fix this first — 3 min
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>
            )}

            {/* Play with Coach — primary after win, secondary after loss */}
            <button
              onClick={() => {
                const opening = plan.opening || "";
                navigate(`/play-with-coach${opening ? `?opening=${encodeURIComponent(opening)}` : ""}`);
              }}
              className={`w-full py-4 text-[15px] font-semibold rounded-xl flex items-center justify-center gap-2 ${
                mood === "confronting"
                  ? "border border-border text-foreground hover:bg-muted/50 transition-all"
                  : "gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20"
              }`}
              data-testid="coach-cta"
            >
              <Swords className="w-4 h-4" strokeWidth={2} />
              {plan.opening
                ? `Play ${plan.opening}${plan.branch ? ` — ${plan.branch}` : ""}`
                : "Play with Coach"
              }
              <ChevronRight className="w-4 h-4 opacity-60" />
            </button>

            {/* Warmup puzzles — only show when NOT in confronting mode (training CTA handles it) */}
            {mood !== "confronting" && warmup?.available && (
              <button
                onClick={() => navigate(`/training/prescribed?focus=${warmup.pattern}`)}
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
