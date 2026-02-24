import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import {
  AlertTriangle,
  Clock,
  ChevronRight,
  X,
  Wrench,
  Target,
  Loader2,
} from "lucide-react";

/**
 * PostLossRecoveryCard - Triggered after a game loss to offer a "fix-it" mission.
 * Part of the Dopamine Engine - promotes immediate learning from losses.
 * 
 * Props:
 * - gameId: The game that was lost (required to fetch the fix-it mission)
 * - onDismiss: Callback when user dismisses the card
 * - autoShow: Whether to auto-display on mount
 */
const PostLossRecoveryCard = ({ gameId, onDismiss, autoShow = true }) => {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(autoShow);
  const [mission, setMission] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [recoveryMessage, setRecoveryMessage] = useState(null);

  useEffect(() => {
    if (gameId && visible) {
      fetchPostLossMission();
    }
  }, [gameId, visible]);

  const fetchPostLossMission = async () => {
    try {
      setLoading(true);
      
      // First fetch the post-loss message
      const msgRes = await fetch(`${API}/rewards/post-loss-message?game_id=${gameId}`, {
        credentials: "include",
      });
      
      if (msgRes.ok) {
        const msgData = await msgRes.json();
        setRecoveryMessage(msgData);
      }
      
      // Then fetch/generate today's mission (which may be a post-loss one)
      const missionRes = await fetch(`${API}/missions/today`, {
        credentials: "include",
      });
      
      if (missionRes.ok) {
        const missionData = await missionRes.json();
        // Only show if it's a post_loss mission
        if (missionData?.trigger_type === "post_loss") {
          setMission(missionData);
        } else {
          // If no post-loss mission, still show but use daily mission
          setMission(missionData);
        }
      }
    } catch (err) {
      console.error("Error fetching post-loss data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleStartMission = async () => {
    if (!mission?.mission_id) return;
    
    setStarting(true);
    try {
      const res = await fetch(`${API}/missions/${mission.mission_id}/start`, {
        method: "POST",
        credentials: "include",
      });
      
      if (res.ok) {
        const data = await res.json();
        navigate(`/mission/${mission.mission_id}`, { 
          state: { session_id: data.session_id, mission } 
        });
      }
    } catch (err) {
      console.error("Error starting mission:", err);
    } finally {
      setStarting(false);
    }
  };

  const handleDismiss = () => {
    setVisible(false);
    if (onDismiss) {
      onDismiss();
    }
  };

  if (!visible) return null;

  // Loading state
  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
      >
        <Card 
          className="border-amber-500/30 bg-gradient-to-r from-amber-500/10 to-orange-500/5"
          data-testid="post-loss-card-loading"
        >
          <CardContent className="py-6">
            <div className="flex items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">Finding something to fix...</span>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    );
  }

  // No mission available
  if (!mission) {
    return null;
  }

  const headline = recoveryMessage?.headline || "Tough game. Don't waste it.";
  const subtext = recoveryMessage?.subtext || "We found one pattern worth fixing today.";
  const ctaText = recoveryMessage?.cta_text || `Start ${mission.estimated_minutes || 5}-minute fix`;
  const minutes = recoveryMessage?.minutes || mission.estimated_minutes || 5;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -20, scale: 0.98 }}
        transition={{ type: "spring", duration: 0.5 }}
      >
        <Card 
          className="relative overflow-hidden border-amber-500/40 bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent"
          data-testid="post-loss-recovery-card"
        >
          {/* Subtle animated background */}
          <div className="absolute inset-0 overflow-hidden">
            <motion.div
              className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-amber-500/5"
              animate={{
                scale: [1, 1.2, 1],
                opacity: [0.3, 0.5, 0.3],
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          </div>
          
          {/* Dismiss button */}
          <button
            onClick={handleDismiss}
            className="absolute top-3 right-3 p-1.5 rounded-full hover:bg-background/50 transition-colors z-10"
            data-testid="dismiss-post-loss-btn"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
          
          <CardContent className="py-6 relative">
            <div className="flex items-start gap-4">
              {/* Icon */}
              <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                <Wrench className="w-6 h-6 text-amber-500" />
              </div>
              
              {/* Content */}
              <div className="flex-1 min-w-0 pr-6">
                {/* Badge */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-amber-500 uppercase tracking-wide flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    After Loss
                  </span>
                </div>
                
                {/* Headline */}
                <h3 className="font-bold text-lg mb-1">
                  {headline}
                </h3>
                
                {/* Subtext */}
                <p className="text-sm text-muted-foreground mb-4">
                  {subtext}
                </p>
                
                {/* Focus area */}
                {mission.focus_label && (
                  <div className="flex items-center gap-2 mb-4 p-2 rounded-lg bg-background/50">
                    <Target className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium">{mission.focus_label}</span>
                  </div>
                )}
                
                {/* CTA Row */}
                <div className="flex items-center gap-4">
                  <Button
                    onClick={handleStartMission}
                    disabled={starting}
                    className="bg-amber-500 hover:bg-amber-600 text-black font-semibold"
                    data-testid="start-fix-mission-btn"
                  >
                    {starting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        {ctaText}
                        <ChevronRight className="w-4 h-4 ml-1" />
                      </>
                    )}
                  </Button>
                  
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{minutes} min</span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
};

export default PostLossRecoveryCard;
