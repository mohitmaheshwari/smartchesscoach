/**
 * LAB — Player Profile + Weakness Groups
 *
 * 1. Player profile — strengths + top 3 weaknesses
 * 2. Weakness tabs — selectable
 * 3. Games grouped under selected weakness — clickable to review
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  Import, ChevronRight, Check, Zap, Trophy, Shield
} from "lucide-react";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedWeakness, setSelectedWeakness] = useState(null);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        setData(d);
        // Auto-select first weakness
        const problems = d.coaching?.top_problems;
        if (problems?.length > 0 && !selectedWeakness) {
          setSelectedWeakness(problems[0].category);
        }
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const markReviewed = async (gameId) => {
    try {
      await fetch(`${API}/lab-mark-reviewed/${gameId}`, { method: "POST", credentials: "include" });
      fetchData();
    } catch (e) {}
  };

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const coaching = data?.coaching;
  const games = data?.games || [];

  if (games.length === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-20 text-center" data-testid="lab-page">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 border border-border flex items-center justify-center mx-auto mb-6">
            <Import className="w-7 h-7 text-muted-foreground/40" strokeWidth={1.5} />
          </div>
          <h2 className="text-xl font-heading font-semibold text-foreground mb-2">No games yet</h2>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-8">Import your games. Your coach will analyze them.</p>
          <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm font-semibold rounded-lg gradient-gold text-black shadow-lg shadow-amber-500/20 hover:opacity-90 transition-all" data-testid="lab-empty-import-btn">
            Import your games
          </button>
        </div>
      </Layout>
    );
  }

  const topProblems = coaching?.top_problems || [];
  const groupedGames = coaching?.grouped_games || {};
  const strengths = coaching?.strengths || [];

  // Get games for selected weakness
  const selectedGroup = selectedWeakness ? groupedGames[selectedWeakness] : null;
  const selectedGames = selectedGroup?.games || [];

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-8" data-testid="lab-page">

        {/* ═══ 1. PLAYER PROFILE ═══ */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-8">

          {/* Strengths */}
          {strengths.length > 0 && (
            <div className="mb-5">
              <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-emerald-500/70 mb-2.5">What you do well</p>
              <div className="space-y-2">
                {strengths.map((s, i) => (
                  <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-emerald-500/[0.04] border border-emerald-500/10">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                      {s.category === "brilliant_play" ? <Zap className="w-3 h-3 text-emerald-500" strokeWidth={2.5} /> :
                       s.category === "tactical_win" ? <Zap className="w-3 h-3 text-emerald-500" strokeWidth={2.5} /> :
                       s.category === "endgame_conversion" ? <Trophy className="w-3 h-3 text-emerald-500" strokeWidth={2} /> :
                       <Shield className="w-3 h-3 text-emerald-500" strokeWidth={2} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground">{s.description}</p>
                    </div>
                    <span className="text-xs font-mono text-emerald-500/60">{s.count} games</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Weaknesses header */}
          {topProblems.length > 0 && (
            <p className="text-[10px] tracking-[0.15em] uppercase font-bold text-red-400/70 mb-2.5">What's holding you back</p>
          )}

          {/* Weakness tabs */}
          {topProblems.length > 0 && (
            <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
              {topProblems.map((tp) => {
                const isActive = selectedWeakness === tp.category;
                return (
                  <button
                    key={tp.category}
                    onClick={() => setSelectedWeakness(tp.category)}
                    className={`flex-shrink-0 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                      isActive
                        ? "bg-red-500/10 text-red-500 border border-red-500/20"
                        : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-foreground/10"
                    }`}
                  >
                    {tp.label}
                    <span className={`ml-2 text-xs font-mono ${isActive ? "text-red-400/60" : "text-muted-foreground/40"}`}>
                      {tp.count}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </motion.div>

        {/* ═══ 2. GAMES FOR SELECTED WEAKNESS ═══ */}
        {selectedGroup && (
          <motion.div
            key={selectedWeakness}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            {/* Description */}
            {selectedGroup.description && (
              <p className="text-sm text-muted-foreground mb-4">
                {selectedGroup.description}
              </p>
            )}

            {/* Games list */}
            {selectedGames.length > 0 ? (
              <div className="space-y-2">
                {selectedGames.map((g) => (
                  <div
                    key={g.game_id}
                    className={`bg-card border rounded-xl cursor-pointer transition-all hover:border-primary/20 group ${
                      g.reviewed ? "opacity-50 border-border" : g.is_new ? "border-primary/30 ring-1 ring-primary/10" : "border-border"
                    }`}
                    onClick={() => navigate(`/game/${g.game_id}`)}
                  >
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          g.result === "L" ? "bg-red-400" : g.result === "D" ? "bg-muted-foreground/40" : "bg-emerald-500"
                        }`} />
                        <span className="text-sm font-medium text-foreground">vs {g.opponent}</span>
                        <span className={`text-[9px] px-1.5 py-0 font-bold rounded border ${
                          g.result === "L" ? "bg-red-500/15 text-red-400 border-red-500/25"
                          : g.result === "D" ? "bg-muted text-muted-foreground border-border"
                          : "bg-emerald-500/15 text-emerald-500 border-emerald-500/25"
                        }`}>{g.result}</span>
                        {g.is_new && !g.reviewed && (
                          <span className="text-[9px] px-1.5 py-0 font-bold rounded bg-primary/15 text-primary border border-primary/25">New</span>
                        )}
                        {g.opening && <span className="text-[10px] text-muted-foreground/40 ml-auto">{g.opening}</span>}
                      </div>

                      {/* Behavioral story — the main content */}
                      {(g.behavior || g.sub_cause) && (
                        <p className="text-xs text-muted-foreground leading-relaxed mb-2">
                          {g.behavior || g.sub_cause}
                        </p>
                      )}

                      {/* Footer */}
                      <div className="flex items-center justify-between">
                        {g.reviewed ? (
                          <div className="flex items-center gap-1 text-emerald-500/40">
                            <Check className="w-3 h-3" strokeWidth={2} />
                            <span className="text-[10px]">Reviewed</span>
                          </div>
                        ) : (
                          <button
                            onClick={(e) => { e.stopPropagation(); markReviewed(g.game_id); }}
                            className="flex items-center gap-1 text-muted-foreground/30 hover:text-emerald-500 transition-colors text-[10px]"
                          >
                            <Check className="w-3 h-3" strokeWidth={1.5} />
                            Mark reviewed
                          </button>
                        )}
                        <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/20 group-hover:text-primary transition-colors" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-8 text-center">No games found for this weakness.</p>
            )}
          </motion.div>
        )}

        {/* No coaching data fallback */}
        {topProblems.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground mb-4">Your coach is still analyzing your games.</p>
            <button onClick={() => navigate("/import")} className="text-sm text-primary hover:text-primary/80 transition-colors">
              Import more games
            </button>
          </div>
        )}

        {/* Import more */}
        <div className="text-center pt-6">
          <button onClick={() => navigate("/import")} className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors">
            Import more games
          </button>
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;
