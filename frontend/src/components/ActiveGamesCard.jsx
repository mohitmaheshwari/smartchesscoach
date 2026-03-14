import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Play, 
  Clock, 
  ChevronRight, 
  Loader2,
  X,
  Swords
} from "lucide-react";

const ActiveGamesCard = () => {
  const navigate = useNavigate();
  const [activeSessions, setActiveSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    fetchActiveSessions();
  }, []);

  const fetchActiveSessions = async () => {
    try {
      const response = await fetch(`${API}/coach/play/active`, {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setActiveSessions(data.active_sessions || []);
      }
    } catch (error) {
      console.error("Error fetching active sessions:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatTimeAgo = (dateString) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return "Just now";
  };

  const getMoveCount = (session) => {
    return session.move_history?.length || 0;
  };

  const getLastMove = (session) => {
    const history = session.move_history || [];
    if (history.length === 0) return null;
    return history[history.length - 1]?.move;
  };

  const handleResume = (sessionId) => {
    // Navigate to coach play with session id - will auto-resume
    navigate("/coach");
  };

  const handleDismiss = () => {
    setDismissed(true);
  };

  // Don't render if no active sessions, loading, or dismissed
  if (loading) return null;
  if (dismissed) return null;
  if (activeSessions.length === 0) return null;

  // Show only the most recent active session
  const mostRecentSession = activeSessions[0];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.3 }}
      >
        <Card 
          className="bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-amber-500/10 border-amber-500/30 hover:border-amber-500/50 transition-all overflow-hidden relative"
          data-testid="active-games-card"
        >
          {/* Dismiss button */}
          <button
            onClick={handleDismiss}
            className="absolute top-2 right-2 p-1 rounded-full hover:bg-white/10 transition-colors z-10"
            data-testid="dismiss-active-games"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>

          <CardContent className="p-4">
            <div className="flex items-center justify-between gap-4">
              {/* Left side - Game info */}
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div className="p-2.5 rounded-xl bg-amber-500/20 shrink-0">
                  <Swords className="w-5 h-5 text-amber-400" />
                </div>
                
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-sm">Continue where you left off</h3>
                    <Badge 
                      variant="outline" 
                      className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-[10px] px-1.5 py-0"
                    >
                      Active Game
                    </Badge>
                  </div>
                  
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimeAgo(mostRecentSession.created_at)}
                    </span>
                    <span>
                      {getMoveCount(mostRecentSession)} moves
                    </span>
                    {mostRecentSession.user_color && (
                      <span>
                        Playing as {mostRecentSession.user_color}
                      </span>
                    )}
                    {getLastMove(mostRecentSession) && (
                      <span className="text-foreground/70">
                        Last: {getLastMove(mostRecentSession)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right side - Resume button */}
              <Button
                onClick={() => handleResume(mostRecentSession.session_id)}
                className="bg-amber-500 hover:bg-amber-600 text-black font-medium shrink-0"
                data-testid="resume-game-btn"
              >
                <Play className="w-4 h-4 mr-1.5" />
                Resume
              </Button>
            </div>

            {/* Show if there are more active games */}
            {activeSessions.length > 1 && (
              <div className="mt-3 pt-3 border-t border-amber-500/20">
                <p className="text-xs text-muted-foreground">
                  +{activeSessions.length - 1} more active {activeSessions.length - 1 === 1 ? 'game' : 'games'}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
};

export default ActiveGamesCard;
