/**
 * LAB PAGE → Understanding
 * "Which game should I review?"
 * 
 * Guide the user, don't make them think.
 * 
 * - Group: "Start here" vs "Worth reviewing" vs "Clean games"
 * - Show: SPECIFIC mistake type from V5 analysis
 * - Highlight: Most educational game
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Loader2,
  ChevronRight,
  Import,
  AlertTriangle,
  CheckCircle2,
  Target,
  Zap,
  Clock,
  TrendingDown,
  Swords,
  Crown,
  Shield,
  RefreshCw,
} from "lucide-react";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showClean, setShowClean] = useState(false);
  const [migrating, setMigrating] = useState(false);

  useEffect(() => {
    fetchGames();
  }, []);

  const fetchGames = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/dashboard-stats`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGames(data.analyzed_list || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // Migrate existing games to get rich summaries
  const handleMigrate = async () => {
    setMigrating(true);
    try {
      const res = await fetch(`${API}/migrate-game-summaries`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        // Refresh the list
        await fetchGames();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setMigrating(false);
    }
  };

  // Determine result
  const getResult = (game) => {
    const result = game.result;
    const userColor = game.user_color;
    const isWhiteWin = result === "1-0";
    const isBlackWin = result === "0-1";
    const userWon = (userColor === "white" && isWhiteWin) || (userColor === "black" && isBlackWin);
    const userLost = (userColor === "white" && isBlackWin) || (userColor === "black" && isWhiteWin);
    if (userWon) return { label: "Won", color: "text-emerald-400", bg: "bg-emerald-500" };
    if (userLost) return { label: "Lost", color: "text-red-400", bg: "bg-red-500" };
    return { label: "Draw", color: "text-amber-400", bg: "bg-amber-500" };
  };

  // Get icon for mistake type
  const getMistakeIcon = (game) => {
    const tags = game.tags || [];
    const phase = game.problem_phase;
    
    // Tactical icons
    if (tags.some(t => t.includes("fork"))) return Swords;
    if (tags.some(t => t.includes("back_rank"))) return Shield;
    if (tags.some(t => t.includes("pin"))) return Target;
    
    // Phase icons
    if (phase === "opening") return Crown;
    if (phase === "endgame") return Clock;
    
    // Severity icons
    const blunders = game.blunders || 0;
    if (blunders >= 2) return Zap;
    if (blunders === 1) return AlertTriangle;
    
    return Target;
  };

  // Get the display info for a game
  const getGameDisplay = (game) => {
    const summary = game.summary || {};
    const keyMistakes = game.key_mistakes || [];
    const blunders = game.blunders || 0;
    const mistakes = game.mistakes || 0;
    const result = getResult(game);
    
    // If we have rich summary data, use it
    if (summary.headline && summary.headline !== "Clean game") {
      return {
        headline: summary.headline,
        subtext: summary.subtext,
        color: blunders > 0 ? "text-red-400" : "text-amber-400",
        icon: getMistakeIcon(game),
        learningValue: "high",
        priority: blunders * 3 + mistakes,
      };
    }
    
    // Fallback to basic stats (for games without V5 summaries)
    if (blunders >= 2) {
      return {
        headline: `${blunders} blunders`,
        subtext: keyMistakes[0]?.short_description || null,
        color: "text-red-400",
        icon: Zap,
        learningValue: "high",
        priority: 1,
      };
    }
    if (blunders === 1) {
      return {
        headline: keyMistakes[0]?.short_description || "Critical blunder",
        subtext: keyMistakes[1]?.short_description || null,
        color: "text-amber-400",
        icon: AlertTriangle,
        learningValue: "high",
        priority: 2,
      };
    }
    if (result.label === "Lost" && mistakes > 0) {
      return {
        headline: keyMistakes[0]?.short_description || "Mistakes cost the game",
        subtext: null,
        color: "text-red-400",
        icon: TrendingDown,
        learningValue: "medium",
        priority: 3,
      };
    }
    if (mistakes >= 2) {
      return {
        headline: keyMistakes[0]?.short_description || `${mistakes} mistakes`,
        subtext: keyMistakes[1]?.short_description || null,
        color: "text-amber-400",
        icon: Target,
        learningValue: "medium",
        priority: 4,
      };
    }
    if (mistakes === 1) {
      return {
        headline: keyMistakes[0]?.short_description || "Minor mistake",
        subtext: null,
        color: "text-zinc-400",
        icon: Clock,
        learningValue: "low",
        priority: 5,
      };
    }
    
    return {
      headline: "Clean game",
      subtext: null,
      color: "text-emerald-400",
      icon: CheckCircle2,
      learningValue: "none",
      priority: 10,
    };
  };

  // Split games into groups
  const categorizedGames = games.map(g => ({
    ...g,
    display: getGameDisplay(g),
  }));

  const worthReviewing = categorizedGames
    .filter(g => g.display.learningValue !== "none")
    .sort((a, b) => a.display.priority - b.display.priority);
  
  const cleanGames = categorizedGames.filter(g => g.display.learningValue === "none");

  // Check if any games need migration (have blunders but no summary)
  const needsMigration = games.some(g => 
    (g.blunders > 0 || g.mistakes > 0) && !g.summary?.headline
  );

  // Get the #1 game to review
  const topGame = worthReviewing[0];

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-xl mx-auto py-8 px-4 space-y-6" data-testid="lab-page">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Review</h1>
            <p className="text-sm text-zinc-500">{games.length} games analyzed</p>
          </div>
          <div className="flex items-center gap-2">
            {needsMigration && (
              <Button
                size="sm"
                variant="ghost"
                onClick={handleMigrate}
                disabled={migrating}
                className="text-xs text-zinc-400 hover:text-white"
                title="Load detailed insights for older games"
              >
                {migrating ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <RefreshCw className="w-3 h-3" />
                )}
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => navigate("/import")}
              className="text-xs border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            >
              <Import className="w-3 h-3 mr-1.5" />
              Import
            </Button>
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════
            TOP PICK: Start here
        ═══════════════════════════════════════════════════════════════ */}
        {topGame && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card 
              className="border-amber-500/30 bg-amber-500/5 cursor-pointer hover:bg-amber-500/10 transition-colors"
              onClick={() => navigate(`/game/${topGame.game_id}`)}
              data-testid="top-game-card"
            >
              <CardContent className="p-4">
                <p className="text-xs text-amber-500 font-medium uppercase tracking-wide mb-2">
                  Start here
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">
                      vs {topGame.opponent || topGame.white_player || topGame.black_player}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-sm ${getResult(topGame).color}`}>
                        {getResult(topGame).label}
                      </span>
                      <span className="text-zinc-600">·</span>
                      <span className={`text-sm ${topGame.display.color}`}>
                        {topGame.display.headline}
                      </span>
                    </div>
                    {topGame.display.subtext && (
                      <p className="text-xs text-zinc-500 mt-1 truncate">
                        Also: {topGame.display.subtext}
                      </p>
                    )}
                  </div>
                  <ChevronRight className="w-5 h-5 text-amber-500 flex-shrink-0 ml-2" />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            WORTH REVIEWING
        ═══════════════════════════════════════════════════════════════ */}
        {worthReviewing.length > 1 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
          >
            <p className="text-xs text-zinc-500 uppercase tracking-wide mb-3">
              Worth reviewing ({worthReviewing.length - 1} more)
            </p>
            
            <div className="space-y-2">
              {worthReviewing.slice(1, 8).map((game, i) => {
                const result = getResult(game);
                const display = game.display;
                const MistakeIcon = display.icon;
                
                return (
                  <motion.div
                    key={game.game_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + i * 0.03 }}
                  >
                    <Card 
                      className="bg-zinc-900/50 border-zinc-800 cursor-pointer hover:bg-zinc-900 hover:border-zinc-700 transition-all"
                      onClick={() => navigate(`/game/${game.game_id}`)}
                    >
                      <CardContent className="p-3 flex items-center gap-3">
                        {/* Result indicator */}
                        <div className={`w-1 h-12 rounded-full ${result.bg}`} />
                        
                        {/* Game info */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white truncate">
                            vs {game.opponent || game.white_player || game.black_player}
                          </p>
                          <div className="flex items-center gap-2 text-xs mt-0.5">
                            <span className={result.color}>{result.label}</span>
                            <span className="text-zinc-600">·</span>
                            <span className={`${display.color} truncate`}>{display.headline}</span>
                          </div>
                          {display.subtext && (
                            <p className="text-xs text-zinc-600 mt-0.5 truncate">
                              + {display.subtext}
                            </p>
                          )}
                        </div>
                        
                        {/* Mistake icon */}
                        <MistakeIcon className={`w-4 h-4 ${display.color} flex-shrink-0`} />
                        
                        <ChevronRight className="w-4 h-4 text-zinc-600 flex-shrink-0" />
                      </CardContent>
                    </Card>
                  </motion.div>
                );
              })}
              
              {worthReviewing.length > 8 && (
                <p className="text-xs text-zinc-600 text-center pt-2">
                  +{worthReviewing.length - 8} more games
                </p>
              )}
            </div>
          </motion.div>
        )}

        {/* ═══════════════════════════════════════════════════════════════
            CLEAN GAMES (Collapsed)
        ═══════════════════════════════════════════════════════════════ */}
        {cleanGames.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <button
              onClick={() => setShowClean(!showClean)}
              className="w-full text-left"
            >
              <div className="flex items-center justify-between py-2 text-zinc-500 hover:text-zinc-400 transition-colors">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <span className="text-xs uppercase tracking-wide">
                    Clean games ({cleanGames.length})
                  </span>
                </div>
                <span className="text-xs">{showClean ? "Hide" : "Show"}</span>
              </div>
            </button>
            
            {showClean && (
              <div className="space-y-2 mt-2">
                {cleanGames.map((game) => {
                  const result = getResult(game);
                  return (
                    <Card 
                      key={game.game_id}
                      className="bg-zinc-900/30 border-zinc-800/50 cursor-pointer hover:bg-zinc-900/50 transition-all"
                      onClick={() => navigate(`/game/${game.game_id}`)}
                    >
                      <CardContent className="p-3 flex items-center gap-3">
                        <div className={`w-1 h-8 rounded-full ${result.bg} opacity-50`} />
                        <div className="flex-1">
                          <p className="text-sm text-zinc-400 truncate">
                            vs {game.opponent || game.white_player || game.black_player}
                          </p>
                        </div>
                        <span className={`text-xs ${result.color}`}>{result.label}</span>
                        <CheckCircle2 className="w-4 h-4 text-emerald-500/50" />
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </motion.div>
        )}

        {/* Empty state */}
        {games.length === 0 && (
          <div className="text-center py-12">
            <p className="text-zinc-500 mb-4">No games analyzed yet</p>
            <Button onClick={() => navigate("/import")}>
              <Import className="w-4 h-4 mr-2" />
              Import Games
            </Button>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
