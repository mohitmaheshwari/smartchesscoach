/**
 * DailyMissionCard - Entry point for Dopamine Engine
 * Shows today's mission with focus area and CTA
 */
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import { 
  Target, 
  Clock, 
  Play, 
  Check, 
  ChevronRight,
  Zap,
  RefreshCw,
  AlertCircle
} from "lucide-react";

const DailyMissionCard = ({ onStartMission }) => {
  const navigate = useNavigate();
  const [mission, setMission] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    fetchMission();
  }, []);

  const fetchMission = async () => {
    try {
      const res = await fetch(`${API}/missions/today`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setMission(data);
      }
    } catch (err) {
      console.error("Failed to fetch mission:", err);
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
        // Navigate to training with mission context
        if (onStartMission) {
          onStartMission(mission);
        } else {
          navigate(`/training?mission=${mission.mission_id}`);
        }
      }
    } catch (err) {
      console.error("Failed to start mission:", err);
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <Card className="surface border-primary/20">
        <CardContent className="py-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-primary animate-spin" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Loading mission...</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!mission) {
    return (
      <Card className="surface border-muted">
        <CardContent className="py-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                Play some games to unlock daily missions
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Status-based rendering
  const isCompleted = mission.status === "completed";
  const isActive = mission.status === "active";
  const isExpired = mission.status === "expired";

  if (isCompleted) {
    return (
      <Card className="surface border-green-500/30 bg-green-500/5">
        <CardContent className="py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                <Check className="w-5 h-5 text-green-500" />
              </div>
              <div>
                <p className="font-medium text-green-400">Mission Complete</p>
                <p className="text-sm text-muted-foreground">{mission.focus_label}</p>
              </div>
            </div>
            <Button 
              variant="ghost" 
              size="sm"
              onClick={() => navigate('/training')}
              className="text-muted-foreground hover:text-foreground"
            >
              More practice <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isExpired) {
    return (
      <Card className="surface border-amber-500/30 bg-amber-500/5">
        <CardContent className="py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <Clock className="w-5 h-5 text-amber-500" />
              </div>
              <div>
                <p className="font-medium text-amber-400">Yesterday's mission expired</p>
                <p className="text-sm text-muted-foreground">Rust happens. Start fresh today.</p>
              </div>
            </div>
            <Button 
              onClick={fetchMission}
              size="sm"
              className="bg-amber-500 hover:bg-amber-600 text-black"
            >
              <RefreshCw className="w-4 h-4 mr-1" /> New Mission
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Default: pending or active
  return (
    <Card 
      className={`surface transition-all ${
        isActive 
          ? "border-primary ring-1 ring-primary/30" 
          : "border-primary/30 hover:border-primary/50"
      }`}
      data-testid="daily-mission-card"
    >
      <CardContent className="py-5">
        <div className="flex items-start justify-between gap-4">
          {/* Left: Mission info */}
          <div className="flex items-start gap-3 flex-1">
            <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Target className="w-6 h-6 text-primary" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <p className="font-semibold">Today's Mission</p>
                <span className="text-xs px-2 py-0.5 rounded-full bg-primary/20 text-primary font-medium">
                  {mission.estimated_minutes} min
                </span>
                {mission.trigger_type === "post_loss" && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-500 font-medium">
                    From your game
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground mb-2">
                Focus: <span className="text-foreground font-medium">{mission.focus_label}</span>
              </p>
              
              {/* Micro-protocol preview */}
              {mission.micro_protocol && mission.micro_protocol.length > 0 && (
                <div className="text-xs text-muted-foreground space-y-0.5">
                  {mission.micro_protocol.slice(0, 2).map((step, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <div className="w-1 h-1 rounded-full bg-primary/50" />
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          
          {/* Right: CTA */}
          <div className="shrink-0">
            {isActive ? (
              <Button 
                onClick={() => navigate(`/training?mission=${mission.mission_id}`)}
                className="bg-primary hover:bg-primary/90"
              >
                <Play className="w-4 h-4 mr-1" /> Continue
              </Button>
            ) : (
              <Button 
                onClick={handleStartMission}
                disabled={starting}
                className="bg-primary hover:bg-primary/90"
              >
                {starting ? (
                  <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Zap className="w-4 h-4 mr-1" />
                )}
                Start Mission
              </Button>
            )}
          </div>
        </div>
        
        {/* Goal indicator */}
        <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between text-xs">
          <span className="text-muted-foreground">
            Goal: Solve {mission.goal?.target || 5} positions
          </span>
          <span className="text-muted-foreground">
            Pass: {mission.goal?.success_threshold || 4}+ correct
          </span>
        </div>
      </CardContent>
    </Card>
  );
};

export default DailyMissionCard;
