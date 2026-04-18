/**
 * ALL GAMES — browse every game (imported + with Coach), tabbed.
 * Not a coaching page — just a list. Click to review.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, ChevronLeft, Swords, Import } from "lucide-react";

const resultWord = (g) => {
  const r = String(g.result || "").toLowerCase().trim();
  if (r === "win" || r === "w") return "Won";
  if (r === "loss" || r === "l") return "Lost";
  if (r === "draw" || r === "d" || r === "1/2-1/2" || r === "½-½") return "Drew";
  const color = String(g.user_color || "").toLowerCase();
  if (r === "1-0") return color === "white" ? "Won" : "Lost";
  if (r === "0-1") return color === "black" ? "Won" : "Lost";
  return r ? r.charAt(0).toUpperCase() + r.slice(1) : "—";
};

const fmtDate = (g) => {
  const d = g.analyzed_at || g.created_at || g.date;
  if (!d) return "";
  const ts = new Date(d);
  const diffH = (Date.now() - ts.getTime()) / 3600000;
  if (diffH < 1) return `${Math.floor(diffH * 60)}m ago`;
  if (diffH < 24) return `${Math.floor(diffH)}h ago`;
  const days = Math.floor(diffH / 24);
  if (days < 7) return `${days}d ago`;
  return ts.toLocaleDateString();
};

const AllGames = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("imported");
  const [expandedGameId, setExpandedGameId] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const coaching = data?.coaching;
  const groupedGames = coaching?.grouped_games || {};
  const allGamesRaw = coaching?.all_games?.length
    ? coaching.all_games
    : Object.values(groupedGames).flatMap(g => g.games || []);

  const seen = new Set();
  const uniqueGames = allGamesRaw.filter(g => {
    if (seen.has(g.game_id)) return false;
    seen.add(g.game_id);
    return true;
  });

  const sortByDate = (a, b) => {
    const da = new Date(a.analyzed_at || a.created_at || a.date || 0).getTime();
    const db = new Date(b.analyzed_at || b.created_at || b.date || 0).getTime();
    return db - da;
  };

  const coachGames = uniqueGames
    .filter(g => g.platform === "coach" || g.opponent === "Coach")
    .sort(sortByDate);
  const importedGames = uniqueGames
    .filter(g => g.platform !== "coach" && g.opponent !== "Coach")
    .sort(sortByDate);

  const activeGames = tab === "coach" ? coachGames : importedGames;

  const GameRow = ({ g }) => {
    const isExpanded = expandedGameId === g.game_id;
    return (
      <div className="rounded-xl overflow-hidden border border-border/40">
        <div
          onClick={() => setExpandedGameId(isExpanded ? null : g.game_id)}
          className="flex items-center justify-between p-3 hover:bg-muted/40 cursor-pointer transition-all group"
        >
          <div className="flex items-center gap-3 min-w-0">
            <Swords className="w-3.5 h-3.5 flex-shrink-0 text-muted-foreground/60" strokeWidth={2} />
            <div className="min-w-0 flex-1">
              <div className="text-sm text-foreground truncate">
                {resultWord(g)}
                {g.platform === "coach"
                  ? " vs Coach"
                  : g.opponent && g.opponent !== "Opponent"
                  ? ` vs ${g.opponent}`
                  : ""}
                {g.opening ? (
                  <span className="text-[10px] text-muted-foreground/40 ml-2">{g.opening}</span>
                ) : null}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-[10px] text-muted-foreground/50">{fmtDate(g)}</span>
            <ChevronRight className={`w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-primary transition-all ${isExpanded ? "rotate-90" : ""}`} />
          </div>
        </div>

        {isExpanded && (
          <div className="px-3 pb-3 pt-1 bg-muted/20 border-t border-muted/30">
            {g.coach_take && (
              <p className="text-xs text-foreground/80 italic mb-2">{g.coach_take}</p>
            )}
            {g.critical_move && (
              <p className="text-[11px] text-muted-foreground/60 mb-2">
                Critical moment: move {g.critical_move}
                {g.critical_best ? ` — best was ${g.critical_best}` : ""}
              </p>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); navigate(`/game/${g.game_id}`); }}
              className="text-xs font-medium px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition"
            >
              Review game
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <Layout user={user}>
      <div className="max-w-lg mx-auto px-4 py-8" data-testid="all-games-page">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate("/lab")}
              className="p-1.5 rounded-lg hover:bg-muted/50 transition"
              aria-label="Back to Lab"
            >
              <ChevronLeft className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
            </button>
            <h1 className="text-lg font-heading font-semibold text-foreground">All games</h1>
          </div>

          <div className="flex items-center gap-1 p-1 rounded-xl bg-muted/30 border border-border/40">
            <button
              onClick={() => { setTab("imported"); setExpandedGameId(null); }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                tab === "imported" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Your games {importedGames.length > 0 && <span className="text-muted-foreground/60">· {importedGames.length}</span>}
            </button>
            <button
              onClick={() => { setTab("coach"); setExpandedGameId(null); }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                tab === "coach" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              With Coach {coachGames.length > 0 && <span className="text-muted-foreground/60">· {coachGames.length}</span>}
            </button>
          </div>

          {activeGames.length === 0 ? (
            <div className="text-center py-10">
              <p className="text-sm text-muted-foreground/70 mb-4">
                {tab === "coach" ? "No games with Coach yet." : "No imported games yet."}
              </p>
              <button
                onClick={() => navigate(tab === "coach" ? "/play-with-coach" : "/import")}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg border border-border bg-card hover:bg-muted/40 transition"
              >
                {tab === "coach" ? <><Swords className="w-3.5 h-3.5" />Play with Coach</> : <><Import className="w-3.5 h-3.5" />Import games</>}
              </button>
            </div>
          ) : (
            <div className="space-y-1.5">
              {activeGames.map(g => <GameRow key={g.game_id} g={g} />)}
            </div>
          )}

        </motion.div>
      </div>
    </Layout>
  );
};

export default AllGames;
