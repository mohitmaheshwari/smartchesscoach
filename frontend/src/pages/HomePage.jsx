import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import Layout from "@/components/Layout";
import {
  Play,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Loader2,
  Swords,
  Flame,
  Trophy,
  ChevronRight,
} from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API}/dashboard-stats`, { credentials: "include" });
        if (res.ok) setDashboardData(await res.json());
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const weakness = getTopWeakness(dashboardData);
  const progress = getProgress(dashboardData);
  const lastGame = getLastGame(dashboardData);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-lg mx-auto py-10 px-4 space-y-6">

        {/* 1. Play with Coach — primary CTA */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <button
            onClick={() => navigate("/play-with-coach")}
            className="w-full group relative overflow-hidden rounded-2xl bg-gradient-to-br from-amber-600 to-orange-700 p-6 text-left transition-transform active:scale-[0.98]"
            data-testid="play-with-coach-cta"
          >
            <div className="absolute inset-0 bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-amber-200/70 text-xs font-medium uppercase tracking-wider mb-1">
                  Ready?
                </p>
                <h1 className="text-2xl font-bold text-white">
                  Play with Coach
                </h1>
                <p className="text-amber-100/60 text-sm mt-1">
                  Real-time coaching on every move
                </p>
              </div>
              <div className="w-14 h-14 rounded-xl bg-white/10 flex items-center justify-center">
                <Swords className="w-7 h-7 text-white" />
              </div>
            </div>
          </button>
        </motion.div>

        {/* 2. Your Biggest Problem — 1 insight + fix */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
        >
          <div
            className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5"
            data-testid="biggest-problem-card"
          >
            {weakness ? (
              <>
                <p className="text-[11px] text-zinc-500 uppercase tracking-wider mb-2">
                  Your biggest problem
                </p>
                <h2 className="text-lg font-semibold text-white">
                  {weakness.name}
                </h2>
                <p className="text-sm text-zinc-400 mt-1 leading-relaxed">
                  {weakness.insight}
                </p>
                <Button
                  size="sm"
                  onClick={() => navigate(weakness.fixRoute)}
                  className="mt-4 bg-zinc-800 hover:bg-zinc-700 text-white"
                  data-testid="fix-weakness-btn"
                >
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                  {weakness.fixLabel}
                </Button>
              </>
            ) : (
              <>
                <p className="text-[11px] text-zinc-500 uppercase tracking-wider mb-2">
                  Your biggest problem
                </p>
                <h2 className="text-lg font-semibold text-white">
                  Not enough data yet
                </h2>
                <p className="text-sm text-zinc-400 mt-1">
                  Import a few games so we can find your patterns.
                </p>
                <Button
                  size="sm"
                  onClick={() => navigate("/import")}
                  className="mt-4 bg-zinc-800 hover:bg-zinc-700 text-white"
                  data-testid="import-games-btn"
                >
                  Import Games
                </Button>
              </>
            )}
          </div>
        </motion.div>

        {/* 3. Progress — 2-3 metrics only */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.16 }}
        >
          <div
            className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5"
            data-testid="progress-card"
          >
            <p className="text-[11px] text-zinc-500 uppercase tracking-wider mb-4">
              Progress
            </p>
            <div className="flex items-center justify-between gap-4">
              <Metric
                icon={<Trophy className="w-4 h-4 text-amber-500" />}
                label="Games"
                value={progress.gamesAnalyzed}
              />
              <div className="w-px h-8 bg-zinc-800" />
              <Metric
                icon={<Flame className="w-4 h-4 text-orange-500" />}
                label="Avg errors"
                value={progress.avgErrors}
              />
              <div className="w-px h-8 bg-zinc-800" />
              <Metric
                icon={
                  progress.trending === "up" ? (
                    <TrendingUp className="w-4 h-4 text-emerald-500" />
                  ) : progress.trending === "down" ? (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  ) : (
                    <TrendingUp className="w-4 h-4 text-zinc-500" />
                  )
                }
                label="Trend"
                value={progress.trendLabel}
              />
            </div>
          </div>
        </motion.div>

        {/* Small "Review last game" link */}
        {lastGame && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.22 }}
          >
            <button
              onClick={() => navigate(`/game/${lastGame.gameId}`)}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl bg-zinc-900/40 border border-zinc-800/50 hover:border-zinc-700 transition-colors group"
              data-testid="review-last-game-link"
            >
              <span className="text-sm text-zinc-400 group-hover:text-zinc-300 transition-colors">
                Review last game vs <span className="text-zinc-200 font-medium">{lastGame.opponent}</span>
              </span>
              <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
            </button>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

/* --- helpers --- */

function Metric({ icon, label, value }) {
  return (
    <div className="flex-1 flex flex-col items-center text-center gap-1">
      {icon}
      <span className="text-base font-semibold text-white">{value}</span>
      <span className="text-[11px] text-zinc-500">{label}</span>
    </div>
  );
}

function getTopWeakness(data) {
  const w = data?.top_weaknesses?.[0];
  if (!w) return null;

  const type = w.pattern_type || w.type || w.category || "tactical_error";
  const count = w.occurrences || w.count || 0;

  const MAP = {
    tactical_error: { name: "Tactical Errors", insight: `${count} missed tactics in recent games. One check of "what can my opponent do?" before each move fixes most of these.`, fixLabel: "Train Tactics", fixRoute: `/training?focus=${type}` },
    missed_threat: { name: "Threat Awareness", insight: `You missed ${count} opponent threats recently. Scanning all their pieces before deciding your move will cut this in half.`, fixLabel: "Train Threats", fixRoute: `/training?focus=${type}` },
    hanging_piece: { name: "Piece Safety", insight: `${count} pieces left unprotected. After every move, ask: "Is everything I have still safe?"`, fixLabel: "Train Safety", fixRoute: `/training?focus=${type}` },
    missed_tactic: { name: "Tactical Vision", insight: `${count} winning moves missed. Practice checks-captures-threats in that order.`, fixLabel: "Train Vision", fixRoute: `/training?focus=${type}` },
    time_trouble: { name: "Time Management", insight: `${count} mistakes under time pressure. Spending more time in the opening saves you in the endgame.`, fixLabel: "Practice Speed", fixRoute: `/training?focus=${type}` },
    blunder_after_blunder: { name: "Emotional Control", insight: `${count} tilt mistakes — errors right after errors. Pause and breathe after a mistake.`, fixLabel: "Train Recovery", fixRoute: `/training?focus=${type}` },
    endgame_technique: { name: "Endgame Technique", insight: `${count} endgame errors. King activity matters more than pawns here.`, fixLabel: "Train Endgames", fixRoute: `/training?focus=${type}` },
  };

  const info = MAP[type] || {
    name: type.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
    insight: `${count} occurrences in recent games. Focused practice will fix this.`,
    fixLabel: "Start Training",
    fixRoute: `/training?focus=${type}`,
  };

  return info;
}

function getLastGame(data) {
  const games = data?.analyzed_list || [];
  if (!games.length) return null;
  const g = games[0];
  const userColor = g.user_color || "white";
  const opponent = userColor === "white" ? (g.black_player || "Opponent") : (g.white_player || "Opponent");
  return { gameId: g.game_id, opponent };
}

function getProgress(data) {
  const games = data?.analyzed_list || [];
  const gamesAnalyzed = data?.total_analyzed || games.length || 0;

  if (games.length < 2) {
    return { gamesAnalyzed, avgErrors: "—", trending: "neutral", trendLabel: "—" };
  }

  const recent = games.slice(0, 3);
  const older = games.slice(3, 6);

  const avg = (arr) =>
    arr.length
      ? Math.round((arr.reduce((s, g) => s + (g.blunders || 0) + (g.mistakes || 0), 0) / arr.length) * 10) / 10
      : 0;

  const recentAvg = avg(recent);
  const olderAvg = older.length ? avg(older) : null;

  let trending = "neutral";
  let trendLabel = "Steady";
  if (olderAvg !== null && olderAvg > 0) {
    const pct = Math.round(((olderAvg - recentAvg) / olderAvg) * 100);
    if (pct > 5) { trending = "up"; trendLabel = `+${pct}%`; }
    else if (pct < -5) { trending = "down"; trendLabel = `${pct}%`; }
  }

  return { gamesAnalyzed, avgErrors: recentAvg, trending, trendLabel };
}

export default HomePage;
