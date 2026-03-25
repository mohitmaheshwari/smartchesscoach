/**
 * LAB PAGE → Understanding
 * "Which game should I review?"
 * 
 * Guide the user, don't make them think.
 * 
 * - Group: "Worth reviewing" vs "Clean games"
 * - Show: Type of mistake, not just count
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
} from "lucide-react";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showClean, setShowClean] = useState(false);

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

  // Categorize mistake type based on blunders/mistakes/accuracy
  const getMistakeType = (game) => {
    const blunders = game.blunders || 0;
    const mistakes = game.mistakes || 0;
    const accuracy = game.accuracy || 0;
    const result = getResult(game);
    
    if (blunders >= 2) {
      return { 
        type: "Multiple blunders", 
        icon: Zap, 
        color: "text-red-400",
        priority: 1,
        learningValue: "high"
      };
    }
    if (blunders === 1) {
      return { 
        type: "Critical blunder", 
        icon: AlertTriangle, 
        color: "text-amber-400",
        priority: 2,
        learningValue: "high"
      };
    }
    if (result.label === "Lost" && mistakes > 0) {
      return { 
        type: "Mistakes cost the game", 
        icon: TrendingDown, 
        color: "text-red-400",
        priority: 3,
        learningValue: "medium"
      };
    }
    if (mistakes >= 2) {
      return { 
        type: "Several mistakes", 
        icon: Target, 
        color: "text-amber-400",
        priority: 4,
        learningValue: "medium"
      };
    }
    if (mistakes === 1) {
      return { 
        type: "Minor mistake", 
        icon: Clock, 
        color: "text-zinc-400",
        priority: 5,
        learningValue: "low"
      };
    }
    if (accuracy < 60) {
      return { 
        type: "Low accuracy", 
        icon: Target, 
        color: "text-amber-400",
        priority: 4,
        learningValue: "medium"
      };
    }
    return { 
      type: "Clean game", 
      icon: CheckCircle2, 
      color: "text-emerald-400",
      priority: 10,
      learningValue: "none"
    };
  };

  // Split games into groups
  const worthReviewing = games
    .filter(g => getMistakeType(g).learningValue !== "none")
    .sort((a, b) => getMistakeType(a).priority - getMistakeType(b).priority);
  
  const cleanGames = games.filter(g => getMistakeType(g).learningValue === "none");

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
                  <div>
                    <p className="text-white font-medium">
                      vs {topGame.opponent || topGame.white_player || topGame.black_player}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-sm ${getResult(topGame).color}`}>
                        {getResult(topGame).label}
                      </span>
                      <span className="text-zinc-600">·</span>
                      <span className={`text-sm ${getMistakeType(topGame).color}`}>
                        {getMistakeType(topGame).type}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-amber-500" />
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
                const mistake = getMistakeType(game);
                const MistakeIcon = mistake.icon;
                
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
                        <div className={`w-1 h-10 rounded-full ${result.bg}`} />
                        
                        {/* Game info */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white truncate">
                            vs {game.opponent || game.white_player || game.black_player}
                          </p>
                          <div className="flex items-center gap-2 text-xs">
                            <span className={result.color}>{result.label}</span>
                            <span className="text-zinc-600">·</span>
                            <span className={mistake.color}>{mistake.type}</span>
                          </div>
                        </div>
                        
                        {/* Mistake icon */}
                        <MistakeIcon className={`w-4 h-4 ${mistake.color}`} />
                        
                        <ChevronRight className="w-4 h-4 text-zinc-600" />
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
