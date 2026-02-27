import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  Wrench,
  ChevronRight,
  Clock,
  Loader2,
  FlaskConical,
  Target,
  Play,
} from "lucide-react";

/**
 * PostLossRecovery - The signature UX pattern
 * 
 * "Tough game. Don't waste it."
 * 
 * Layout:
 * - Board on left (60%)
 * - Recovery panel on right (40%)
 * 
 * Flow:
 * 1. Show the critical mistake from the game
 * 2. One insight (main issue)
 * 3. One CTA ("Fix this in X min")
 * 4. Secondary: "See full analysis"
 */
const PostLossRecovery = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  
  // State
  const [loading, setLoading] = useState(true);
  const [recoveryData, setRecoveryData] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  
  // Board state
  const [boardFen, setBoardFen] = useState("start");
  const [arrows, setArrows] = useState([]);

  useEffect(() => {
    if (gameId) {
      fetchRecoveryData();
    }
  }, [gameId]);

  const fetchRecoveryData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/reflect/v1/post-loss/${gameId}`, {
        credentials: "include",
      });
      
      if (res.ok) {
        const data = await res.json();
        setRecoveryData(data);
        
        // Set up the board with the critical moment
        if (data.critical_moment) {
          setBoardFen(data.critical_moment.fen || "start");
          
          // Show arrows for the mistake
          const userArrow = sanToArrow(data.critical_moment.user_move, data.critical_moment.fen, "red");
          const betterArrow = sanToArrow(data.critical_moment.best_move, data.critical_moment.fen, "green");
          const newArrows = [];
          if (userArrow) newArrows.push(userArrow);
          if (betterArrow) newArrows.push(betterArrow);
          setArrows(newArrows);
        }
      } else {
        setError("Could not load recovery data");
      }
    } catch (err) {
      console.error("Error fetching recovery data:", err);
      setError("Could not load recovery data");
    } finally {
      setLoading(false);
    }
  };

  const sanToArrow = (san, fen, color) => {
    if (!san || !fen) return null;
    try {
      const chess = new Chess(fen);
      const move = chess.move(san);
      if (move) {
        return [move.from, move.to, color];
      }
    } catch (e) {
      return null;
    }
    return null;
  };

  const handleStartRecovery = async () => {
    setStarting(true);
    
    // Generate or get the fix-it mission for this game
    try {
      const res = await fetch(`${API}/missions/generate-fix`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ game_id: gameId }),
      });
      
      if (res.ok) {
        const data = await res.json();
        // Start the mission
        const startRes = await fetch(`${API}/missions/${data.mission_id}/start`, {
          method: "POST",
          credentials: "include",
        });
        
        if (startRes.ok) {
          const startData = await startRes.json();
          navigate(`/mission/${data.mission_id}`, {
            state: { session_id: startData.session_id, mission: data }
          });
        }
      } else {
        // Fallback: Go to reflect page
        navigate(`/reflect?game=${gameId}`);
      }
    } catch (err) {
      // Fallback: Go to reflect page
      navigate(`/reflect?game=${gameId}`);
    } finally {
      setStarting(false);
    }
  };

  const handleFullAnalysis = () => {
    navigate(`/game/${gameId}`);
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  if (error || !recoveryData) {
    return (
      <Layout user={user}>
        <div className="max-w-2xl mx-auto py-12 text-center">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold mb-2">Could not load recovery</h1>
          <p className="text-muted-foreground mb-4">{error || "Game data not available"}</p>
          <Button onClick={() => navigate("/home")} variant="outline">
            Back to Home
          </Button>
        </div>
      </Layout>
    );
  }

  const { 
    headline, 
    main_issue, 
    estimated_minutes,
    critical_moment,
    opponent_name,
    user_color,
    recurring_pattern,  // Coach memory context
  } = recoveryData;

  return (
    <Layout user={user}>
      <div className="max-w-5xl mx-auto py-6" data-testid="post-loss-recovery-page">
        {/* Desktop: Side-by-side layout */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          
          {/* Left: Board (60%) */}
          <div className="lg:col-span-3">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
            >
              {/* Board Container */}
              <div className="rounded-xl overflow-hidden bg-card border border-border">
                <div className="aspect-square max-w-[500px] mx-auto">
                  <CoachBoard
                    fen={boardFen}
                    orientation={user_color || "white"}
                    interactive={false}
                    viewOnly={true}
                    customArrows={arrows}
                  />
                </div>
                
                {/* Move Info */}
                {critical_moment && (
                  <div className="p-4 border-t border-border">
                    <div className="flex items-center justify-center gap-6">
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground mb-1">You played</p>
                        <p className="font-mono font-bold text-[#EF4444] text-lg">
                          {critical_moment.user_move}
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-muted-foreground" />
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground mb-1">Better was</p>
                        <p className="font-mono font-bold text-[#10B981] text-lg">
                          {critical_moment.best_move}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          </div>

          {/* Right: Recovery Panel (40%) */}
          <div className="lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="space-y-6"
            >
              {/* Badge */}
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
                <span className="text-xs font-semibold text-[#EF4444] uppercase tracking-wide">
                  Post-Loss Recovery
                </span>
              </div>
              
              {/* Opponent context */}
              {opponent_name && (
                <p className="text-sm text-muted-foreground">
                  vs {opponent_name}
                </p>
              )}
              
              {/* Headline - Emotional, Direct */}
              <h1 className="text-3xl font-bold tracking-tight">
                {headline || "Let's fix this moment."}
              </h1>
              
              {/* COACH MEMORY: Recurring Pattern Alert */}
              {recurring_pattern?.coach_memory_line && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30"
                >
                  <div className="flex items-start gap-2">
                    <Brain className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-amber-200">
                      {recurring_pattern.coach_memory_line}
                    </p>
                  </div>
                  {recurring_pattern.trend === "worsening" && (
                    <p className="text-xs text-amber-500/70 mt-1 ml-6">
                      This needs focused attention.
                    </p>
                  )}
                </motion.div>
              )}
              
              {/* Main Issue Card */}
              <div className="p-4 rounded-xl bg-secondary/50 border border-border">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-lg bg-[#EF4444]/10 flex items-center justify-center flex-shrink-0">
                    <Target className="w-5 h-5 text-[#EF4444]" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                      Main Issue
                    </p>
                    <p className="font-medium">
                      {main_issue || "Critical position misjudgment"}
                    </p>
                  </div>
                </div>
              </div>
              
              {/* CTA Section */}
              <div className="space-y-3 pt-4">
                {/* Primary CTA */}
                <Button
                  onClick={handleStartRecovery}
                  disabled={starting}
                  size="lg"
                  className="w-full bg-[#EF4444] hover:bg-[#DC2626] text-white font-semibold h-14 text-base"
                  data-testid="fix-it-btn"
                >
                  {starting ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Wrench className="w-5 h-5 mr-2" />
                      Fix this in {estimated_minutes || 6} min
                      <ChevronRight className="w-5 h-5 ml-2" />
                    </>
                  )}
                </Button>
                
                {/* Time estimate */}
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  <span>{estimated_minutes || 6} minute focused drill</span>
                </div>
                
                {/* Secondary: Full analysis */}
                <button
                  onClick={handleFullAnalysis}
                  className="w-full text-center text-sm text-muted-foreground hover:text-foreground transition-colors py-2"
                  data-testid="see-analysis-btn"
                >
                  <FlaskConical className="w-4 h-4 inline mr-1" />
                  See full analysis instead →
                </button>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default PostLossRecovery;
