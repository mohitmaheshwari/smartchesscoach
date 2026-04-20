/**
 * HOME — "Opening a text from your coach."
 *
 * One landing page. The hero is TodayHero (the coach's single prescription).
 * Below it, lightweight secondary anchors: a brief last-game line, a link
 * to all games, a link to progress. No competing cards, no menu.
 *
 * New users (no games yet) see a warm welcome + connect/play CTAs instead.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import TodayHero from "@/components/TodayHero";
import {
  ChevronRight, Swords, Brain, Import, TrendingUp, History,
} from "lucide-react";


const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [lastSession, setLastSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hasGames, setHasGames] = useState(false);
  const [coachGamesPlayed, setCoachGamesPlayed] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const [homeRes, dashRes] = await Promise.all([
          fetch(`${API}/home/coach-home`, { credentials: "include" }),
          fetch(`${API}/home/dashboard-v2`, { credentials: "include" }),
        ]);
        if (homeRes.ok) {
          const d = await homeRes.json();
          setLastSession(d?.last_session || null);
          setCoachGamesPlayed(d?.greeting?.games_together || 0);
        }
        if (dashRes.ok) {
          const d = await dashRes.json();
          if (d.games_analyzed > 0 || d.games_imported > 0) setHasGames(true);
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

  // ─── New user — no games yet ───────────────────────────────────
  if (!hasGames && !lastSession) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-10" data-testid="home-page">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

            <div className="text-center">
              <div className="w-14 h-14 rounded-2xl gradient-gold flex items-center justify-center mx-auto mb-4 shadow-lg shadow-amber-500/20">
                <Brain className="w-6 h-6 text-black" strokeWidth={2} />
              </div>
              <h1 className="text-2xl font-heading text-foreground tracking-tight mb-2">
                Welcome to ChessGuru
              </h1>
              <p className="text-sm text-muted-foreground">
                I'm your personal chess coach. Let's find out how you play.
              </p>
            </div>

            <div className="flex items-center justify-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${coachGamesPlayed >= 1 ? "bg-emerald-500" : "bg-primary"}`} />
              <div className={`w-2.5 h-2.5 rounded-full ${coachGamesPlayed >= 2 ? "bg-emerald-500" : "bg-muted"}`} />
              <div className={`w-2.5 h-2.5 rounded-full ${coachGamesPlayed >= 3 ? "bg-emerald-500" : "bg-muted"}`} />
              <span className="text-xs text-muted-foreground ml-2">
                {coachGamesPlayed === 0 ? "Play your first game" :
                 coachGamesPlayed < 3 ? `${coachGamesPlayed}/3 games — ${3 - coachGamesPlayed} more to build your profile` :
                 "Profile ready!"}
              </span>
            </div>

            <div className="rounded-2xl border-2 border-primary/20 bg-primary/[0.03] p-5">
              <h2 className="text-base font-semibold text-foreground mb-2">
                {coachGamesPlayed === 0
                  ? "Play a game with me"
                  : coachGamesPlayed < 3
                    ? "Keep going — I'm learning how you think"
                    : "I know your game now"}
              </h2>
              <p className="text-sm text-muted-foreground mb-4">
                {coachGamesPlayed === 0
                  ? "I'll watch how you play and tell you what I see. No preparation needed — just play your natural game."
                  : coachGamesPlayed < 3
                    ? `After ${3 - coachGamesPlayed} more game${3 - coachGamesPlayed > 1 ? "s" : ""}, I'll have your full profile.`
                    : "Your profile is ready. Let's keep improving."}
              </p>
              <button onClick={() => navigate("/play-with-coach")}
                className="w-full py-4 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
              >
                <Swords className="w-4 h-4" strokeWidth={2} />
                {coachGamesPlayed === 0 ? "Play my first game" : "Play another game"}
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>
            </div>

            <div className="rounded-2xl border border-border bg-card p-4">
              <p className="text-sm text-foreground mb-3">Already play on Chess.com or Lichess?</p>
              <p className="text-xs text-muted-foreground mb-3">
                Connect your account and I'll analyze your existing games. Instant profile.
              </p>
              <button onClick={() => navigate("/import")}
                className="w-full py-2.5 text-sm border border-border text-foreground rounded-xl hover:bg-muted/50 transition-all flex items-center justify-center gap-2"
              >
                <Import className="w-4 h-4" strokeWidth={2} />
                Connect Chess.com or Lichess
              </button>
            </div>

          </motion.div>
        </div>
      </Layout>
    );
  }

  // ─── Returning user — TodayHero + lightweight anchors ─────────────
  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-10" data-testid="home-page">
        {/* Hero — the one prescription */}
        <TodayHero />

        {/* Divider */}
        <div className="border-t border-border/50 mt-10 pt-6 space-y-4">

          {/* Last session — small, quiet */}
          {lastSession?.story && (
            <div className="text-[12px] text-muted-foreground leading-relaxed">
              <span className="uppercase tracking-widest text-muted-foreground/50 text-[10px] font-bold">
                Last session ·
              </span>{" "}
              {lastSession.story}
            </div>
          )}

          {/* Quiet text links — no competing cards */}
          <div className="flex flex-col gap-1 pt-2">
            <button
              onClick={() => navigate("/games")}
              className="text-left text-[12px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 py-1"
            >
              <History className="w-3 h-3" />
              See all your games
              <ChevronRight className="w-3 h-3 ml-auto opacity-40" />
            </button>

            <button
              onClick={() => navigate("/progress")}
              className="text-left text-[12px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 py-1"
            >
              <TrendingUp className="w-3 h-3" />
              See your progress over time
              <ChevronRight className="w-3 h-3 ml-auto opacity-40" />
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default HomePage;
