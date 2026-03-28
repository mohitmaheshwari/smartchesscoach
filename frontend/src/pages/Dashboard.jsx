/**
 * LAB PAGE — Coach's Review Queue
 * 
 * Not a list. A queue fed by the coach.
 * "Review this one because..." → review → mark done → next surfaces.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Loader2, Import, ChevronRight, Check, RefreshCw } from "lucide-react";

const WINE = "#722F37";
const GOLD_TEXT = "#8B6F1F";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Error:", err);
    } finally {
      setLoading(false);
    }
  };

  const markReviewed = async (gameId) => {
    try {
      await fetch(`${API}/lab-mark-reviewed/${gameId}`, { method: "POST", credentials: "include" });
      fetchData(); // Refresh — next game surfaces
    } catch (e) {}
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-5 h-5 border border-border border-t-foreground/50 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  const pick = data?.pick;
  const pickReason = data?.pick_reason;
  const verdict = data?.verdict;
  const games = data?.games || [];
  const reviewedCount = data?.reviewed_count || 0;
  const totalCount = data?.total_count || 0;
  const unreviewedGames = games.filter(g => !g.reviewed);
  const reviewedGames = games.filter(g => g.reviewed);

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto py-8 px-4" data-testid="lab-page">
        
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl text-foreground tracking-tight font-heading">Lab</h1>
            <p className="text-xs text-muted-foreground mt-1 font-mono">
              {reviewedCount}/{totalCount} reviewed
            </p>
          </div>
          <button
            onClick={() => navigate("/import")}
            className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border text-foreground hover:bg-muted/50 transition-colors rounded-sm"
            data-testid="lab-import-btn"
          >
            <Import className="w-3.5 h-3.5" strokeWidth={1.5} />
            Import
          </button>
        </div>

        {/* ── VERDICT STRIP ── */}
        {verdict && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
            <div className="bg-card border border-border rounded-sm p-5">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-lg text-emerald-600 font-mono">{verdict.wins}W</span>
                <span className="text-lg font-mono" style={{ color: WINE }}>{verdict.losses}L</span>
                <span className="text-xs text-muted-foreground font-mono">last {verdict.total} games</span>
              </div>
              <p className="text-sm text-muted-foreground font-light">{verdict.insight}</p>
            </div>
          </motion.div>
        )}

        {/* ── COACH'S PICK ── */}
        {pick && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-8">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-2 font-mono" style={{ color: GOLD_TEXT }}>
              Coach's Pick
            </p>
            <div
              className="bg-card border border-border rounded-sm cursor-pointer transition-all duration-200 hover:shadow-sm"
              style={{ borderLeft: `3px solid ${GOLD_TEXT}` }}
              onClick={() => navigate(`/game/${pick.game_id}`)}
              data-testid="coach-pick-card"
            >
              <div className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-base text-foreground font-heading">vs {pick.opponent}</span>
                    <ResultBadge result={pick.result} />
                    {pick.accuracy > 0 && (
                      <span className="text-xs text-muted-foreground font-mono">{pick.accuracy}%</span>
                    )}
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground/40" strokeWidth={1.5} />
                </div>
                {/* The reason — this is the coach talking */}
                <p className="text-sm font-light" style={{ color: WINE }}>{pickReason}</p>
                {pick.summary_headline && (
                  <p className="text-xs text-muted-foreground mt-2 font-light">{pick.summary_headline}</p>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── UNREVIEWED GAMES ── */}
        {unreviewedGames.length > 1 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <p className="text-[10px] tracking-[0.2em] uppercase mb-2 font-mono" style={{ color: GOLD_TEXT }}>
              To Review ({unreviewedGames.length - (pick ? 1 : 0)} more)
            </p>
            <div className="bg-card border border-border rounded-sm divide-y divide-border">
              {unreviewedGames.filter(g => g.game_id !== pick?.game_id).map((game) => (
                <div
                  key={game.game_id}
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors hover:bg-muted/30"
                  onClick={() => navigate(`/game/${game.game_id}`)}
                >
                  <div className="w-1 h-8 flex-shrink-0 rounded-full" style={{
                    background: game.result === "W" ? "#16a34a" : game.result === "L" ? WINE : "#ddd"
                  }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground font-light truncate">vs {game.opponent}</p>
                    <div className="flex items-center gap-2 text-xs mt-0.5">
                      <ResultBadge result={game.result} small />
                      {game.opening && (
                        <>
                          <span className="text-muted-foreground/40">·</span>
                          <span className="text-muted-foreground truncate font-light">{game.opening}</span>
                        </>
                      )}
                      {game.blunders > 0 && (
                        <>
                          <span className="text-muted-foreground/40">·</span>
                          <span className="text-muted-foreground font-mono">{game.blunders}B</span>
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); markReviewed(game.game_id); }}
                    className="p-1.5 text-muted-foreground/30 hover:text-emerald-600 transition-colors"
                    title="Mark as reviewed"
                  >
                    <Check className="w-4 h-4" strokeWidth={1.5} />
                  </button>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* ── REVIEWED GAMES ── */}
        {reviewedGames.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-6">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-2 font-mono text-muted-foreground/50">
              Reviewed ({reviewedGames.length})
            </p>
            <div className="divide-y divide-border/50">
              {reviewedGames.map((game) => (
                <div
                  key={game.game_id}
                  className="flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors hover:bg-muted/20 opacity-50"
                  onClick={() => navigate(`/game/${game.game_id}`)}
                >
                  <Check className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" strokeWidth={1.5} />
                  <span className="text-sm text-muted-foreground font-light truncate">vs {game.opponent}</span>
                  <ResultBadge result={game.result} small />
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Empty state */}
        {games.length === 0 && (
          <div className="text-center py-20">
            <p className="text-muted-foreground mb-4 font-light">No games analyzed yet</p>
            <button
              onClick={() => navigate("/import")}
              className="px-6 py-3 text-sm text-white rounded-sm"
              style={{ background: WINE }}
            >
              Import your games
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
};

const ResultBadge = ({ result, small }) => {
  const base = small ? "text-[9px] px-1 py-0" : "text-[10px] px-1.5 py-0.5";
  return (
    <span className={`${base} font-mono rounded-sm`} style={{
      background: result === "W" ? "rgba(22,163,74,0.1)" : result === "L" ? `${WINE}15` : "rgba(0,0,0,0.05)",
      color: result === "W" ? "#16a34a" : result === "L" ? WINE : "#888",
    }}>
      {result === "W" ? "WON" : result === "L" ? "LOST" : "DRAW"}
    </span>
  );
};

export default Dashboard;
