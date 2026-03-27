/**
 * LAB PAGE — Reimagined as a Visual Timeline
 * 
 * Not a list. A story of your recent chess life.
 * Wins go UP, losses go DOWN. You SEE your form.
 */

import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Loader2, Import, ChevronRight, RefreshCw } from "lucide-react";

const WINE = "#722F37";
const GOLD = "#CBA135";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [migrating, setMigrating] = useState(false);

  useEffect(() => {
    fetchGames();
  }, []);

  const fetchGames = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/dashboard-stats`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGames(data.analyzed_list || []);
      }
    } catch (err) {
      console.error("Error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleMigrate = async () => {
    setMigrating(true);
    try {
      const res = await fetch(`${API}/migrate-game-summaries`, { method: "POST", credentials: "include" });
      if (res.ok) await fetchGames();
    } catch (e) {}
    finally { setMigrating(false); }
  };

  // Compute user result for each game
  const enrichedGames = useMemo(() => {
    return games.map(g => {
      const userWon = (g.result === "1-0" && g.user_color === "white") || (g.result === "0-1" && g.user_color === "black");
      const isDraw = (g.result || "").includes("1/2");
      return { ...g, userWon, isDraw, userLost: !userWon && !isDraw };
    });
  }, [games]);

  // Verdict strip
  const verdict = useMemo(() => {
    const recent = enrichedGames.slice(0, 15);
    if (recent.length === 0) return null;
    const wins = recent.filter(g => g.userWon).length;
    const losses = recent.filter(g => g.userLost).length;
    const draws = recent.filter(g => g.isDraw).length;
    const throws = recent.filter(g => g.userWon && (g.blunders || 0) >= 2).length;
    const lostToBlunder = recent.filter(g => g.userLost && (g.blunders || 0) >= 1).length;

    let insight = "";
    if (throws >= 3) insight = `You're winning but getting sloppy — ${throws} wins with 2+ blunders`;
    else if (lostToBlunder >= 3) insight = `${lostToBlunder} losses came from blunders, not being outplayed`;
    else if (wins > losses * 2) insight = "Strong form. Keep the momentum";
    else if (losses > wins) insight = "Rough stretch. Focus on reviewing, not playing more";
    else insight = "Steady form. Room to sharpen";

    return { wins, losses, draws, total: recent.length, insight };
  }, [enrichedGames]);

  // Featured game (first game with learning value)
  const featuredGame = useMemo(() => {
    return enrichedGames.find(g => g.userLost && (g.blunders || 0) >= 1) || enrichedGames[0];
  }, [enrichedGames]);

  // Needs migration?
  const needsMigration = games.some(g => (g.blunders > 0 || g.mistakes > 0) && !g.summary?.headline);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-5 h-5 border border-gray-700 border-t-white animate-spin" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto py-8 px-4" data-testid="lab-page">
        
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl text-white tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>Lab</h1>
            <p className="text-xs text-gray-600 mt-1" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{games.length} games analyzed</p>
          </div>
          <div className="flex items-center gap-2">
            {needsMigration && (
              <button onClick={handleMigrate} disabled={migrating} className="p-2 text-gray-600 hover:text-white transition-colors">
                {migrating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" strokeWidth={1.5} />}
              </button>
            )}
            <button
              onClick={() => navigate("/import")}
              className="flex items-center gap-1.5 px-4 py-2 text-sm transition-all"
              style={{ border: "1px solid rgba(255,255,255,0.1)", color: GOLD }}
              data-testid="lab-import-btn"
            >
              <Import className="w-3.5 h-3.5" strokeWidth={1.5} />
              Import
            </button>
          </div>
        </div>

        {/* ── VERDICT STRIP ── */}
        {verdict && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
            <div className="p-5" style={{ background: "#241A14", border: "1px solid rgba(255,255,255,0.05)" }}>
              <div className="flex items-center gap-4 mb-3">
                <div className="flex items-center gap-2" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  <span className="text-lg text-emerald-400">{verdict.wins}W</span>
                  <span className="text-lg text-red-400">{verdict.losses}L</span>
                  {verdict.draws > 0 && <span className="text-lg text-gray-500">{verdict.draws}D</span>}
                </div>
                <span className="text-xs text-gray-600" style={{ fontFamily: "'JetBrains Mono', monospace" }}>last {verdict.total} games</span>
              </div>
              <p className="text-sm text-gray-400 font-light">{verdict.insight}</p>
            </div>
          </motion.div>
        )}

        {/* ── TIMELINE ── */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mb-10">
          <p className="text-[10px] tracking-[0.2em] uppercase mb-4" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
            Your Form
          </p>
          <TimelineChart
            games={enrichedGames.slice(0, 20)}
            onGameClick={(g) => navigate(`/game/${g.game_id}`)}
            featuredId={featuredGame?.game_id}
          />
        </motion.div>

        {/* ── FEATURED GAME ── */}
        {featuredGame && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mb-8">
            <p className="text-[10px] tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Review This One
            </p>
            <div
              className="p-5 cursor-pointer transition-all duration-200 hover:border-white/10"
              style={{ background: "#0a0a0a", border: "1px solid rgba(203,161,53,0.2)", borderLeft: "3px solid #CBA135" }}
              onClick={() => navigate(`/game/${featuredGame.game_id}`)}
              data-testid="featured-game"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-base text-white font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                    vs {featuredGame.opponent || featuredGame.white_player || featuredGame.black_player}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs ${featuredGame.userWon ? 'text-emerald-400' : featuredGame.userLost ? 'text-red-400' : 'text-gray-500'}`}
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {featuredGame.userWon ? "WON" : featuredGame.userLost ? "LOST" : "DRAW"}
                    </span>
                    {featuredGame.summary?.headline && (
                      <>
                        <span className="text-gray-700">·</span>
                        <span className="text-sm text-gray-400 font-light">{featuredGame.summary.headline}</span>
                      </>
                    )}
                    {!featuredGame.summary?.headline && (featuredGame.blunders || 0) > 0 && (
                      <>
                        <span className="text-gray-700">·</span>
                        <span className="text-sm text-gray-400 font-light">{featuredGame.blunders} blunder{featuredGame.blunders > 1 ? 's' : ''}</span>
                      </>
                    )}
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-600" strokeWidth={1.5} />
              </div>
            </div>
          </motion.div>
        )}

        {/* ── ALL GAMES ── */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <p className="text-[10px] tracking-[0.2em] uppercase mb-4" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
            All Games
          </p>
          <div>
            {enrichedGames.map((game, i) => (
              <div
                key={game.game_id}
                className="flex items-center gap-3 py-3 cursor-pointer transition-all duration-200 hover:bg-white/[0.02]"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}
                onClick={() => navigate(`/game/${game.game_id}`)}
                data-testid={`game-row-${i}`}
              >
                <div className="w-1 h-8 flex-shrink-0" style={{
                  background: game.userWon ? "#276F4B" : game.userLost ? WINE : "rgba(255,255,255,0.1)"
                }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white font-light truncate">vs {game.opponent || game.white_player || game.black_player}</p>
                  <div className="flex items-center gap-2 text-xs mt-0.5">
                    <span className={game.userWon ? 'text-emerald-400' : game.userLost ? 'text-red-400' : 'text-gray-500'}
                      style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {game.userWon ? "W" : game.userLost ? "L" : "D"}
                    </span>
                    {game.opening && (
                      <>
                        <span className="text-gray-700">·</span>
                        <span className="text-gray-600 truncate font-light">{game.opening}</span>
                      </>
                    )}
                    {(game.blunders || 0) > 0 && (
                      <>
                        <span className="text-gray-700">·</span>
                        <span className="text-gray-600" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{game.blunders}B</span>
                      </>
                    )}
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-800 flex-shrink-0" strokeWidth={1.5} />
              </div>
            ))}
          </div>
        </motion.div>

        {games.length === 0 && (
          <div className="text-center py-20">
            <p className="text-gray-500 mb-4 font-light">No games analyzed yet</p>
            <button
              onClick={() => navigate("/import")}
              className="px-6 py-3 text-sm"
              style={{ background: WINE, color: "white" }}
            >
              Import your games
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
};


// ── TIMELINE CHART ──
const TimelineChart = ({ games, onGameClick, featuredId }) => {
  if (!games.length) return null;

  const HEIGHT = 140;
  const PADDING_Y = 30;
  const DOT_R = 6;
  const usableH = HEIGHT - PADDING_Y * 2;

  // Each game gets a Y position: wins go up, losses go down, draws middle
  // We track cumulative score: +1 for win, -1 for loss, 0 for draw
  const reversed = [...games].reverse(); // oldest first
  let cumScore = 0;
  const points = reversed.map((g, i) => {
    if (g.userWon) cumScore += 1;
    else if (g.userLost) cumScore -= 1;
    return { ...g, cumScore, index: i };
  });

  const maxScore = Math.max(...points.map(p => Math.abs(p.cumScore)), 1);
  const totalW = Math.max(points.length * 50, 400);

  const getX = (i) => 30 + (i / Math.max(points.length - 1, 1)) * (totalW - 60);
  const getY = (score) => PADDING_Y + (usableH / 2) - (score / maxScore) * (usableH / 2);

  // Build SVG path
  let pathD = "";
  points.forEach((p, i) => {
    const x = getX(i);
    const y = getY(p.cumScore);
    if (i === 0) pathD += `M ${x} ${y}`;
    else pathD += ` L ${x} ${y}`;
  });

  return (
    <div className="overflow-x-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.1) transparent" }}>
      <svg width={totalW} height={HEIGHT} className="block">
        {/* Zero line */}
        <line x1={20} y1={getY(0)} x2={totalW - 20} y2={getY(0)} stroke="rgba(255,255,255,0.05)" strokeWidth={1} />

        {/* Path line */}
        <path d={pathD} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth={1.5} />

        {/* Dots */}
        {points.map((p, i) => {
          const x = getX(i);
          const y = getY(p.cumScore);
          const fill = p.userWon ? "#276F4B" : p.userLost ? WINE : "#333";
          const isFeatured = p.game_id === featuredId;

          return (
            <g key={p.game_id} className="cursor-pointer" onClick={() => onGameClick(p)}>
              {isFeatured && (
                <circle cx={x} cy={y} r={DOT_R + 4} fill="none" stroke={GOLD} strokeWidth={1} opacity={0.6} />
              )}
              <circle cx={x} cy={y} r={DOT_R} fill={fill} stroke={isFeatured ? GOLD : "rgba(255,255,255,0.1)"} strokeWidth={1} />
              {/* Opponent name on hover — show for every 3rd game or featured */}
              {(i % 3 === 0 || isFeatured) && (
                <text x={x} y={y - 12} textAnchor="middle" fill="#555" fontSize={9} fontFamily="'JetBrains Mono', monospace">
                  {(p.opponent || p.white_player || "")?.slice(0, 8)}
                </text>
              )}
            </g>
          );
        })}

        {/* Win/Loss labels */}
        <text x={10} y={PADDING_Y - 5} fill="#276F4B" fontSize={9} fontFamily="'JetBrains Mono', monospace">W</text>
        <text x={10} y={HEIGHT - PADDING_Y + 12} fill={WINE} fontSize={9} fontFamily="'JetBrains Mono', monospace">L</text>
      </svg>
    </div>
  );
};


export default Dashboard;
