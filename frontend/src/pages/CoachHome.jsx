/**
 * CoachHome - The Focused Home Page
 * 
 * UX Promise: "From loss to learning in under 90 seconds."
 * 
 * Answers in 5 seconds:
 * - What stage am I in?
 * - What am I working on?
 * - How did I do?
 * - What should I do next?
 * 
 * Layout (Priority Order):
 * 1. Development Phase Banner - Shows current stage
 * 2. Fresh Loss Card OR Active Mission Card (if exists)
 * 3. Active Advice Card - THE ONE thing to focus on
 * 4. Post-Game Review Card (only if new game analyzed)
 * 5. Recommended Drill Card
 * 6. Quick Actions
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  DevelopmentPhaseBanner,
  ActiveMissionCard,
  CoachGameReviewCard,
  RecommendedDrillCard,
  ActiveAdviceCard,
} from "@/components/Home";
import BehavioralInsightCard from "@/components/Home/BehavioralInsightCard";
import {
  AlertTriangle,
  ChevronRight,
  Clock,
  Wrench,
  Loader2,
  Import,
  TrendingUp,
  Brain,
  BookOpen,
  Sparkles,
  Gamepad2,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const CoachHome = ({ user }) => {
  const navigate = useNavigate();
  
  // State
  const [loading, setLoading] = useState(true);
  const [homeData, setHomeData] = useState(null);
  const [mission, setMission] = useState(null);
  const [freshLoss, setFreshLoss] = useState(null);
  const [starting, setStarting] = useState(false);
  const [reanalysisStatus, setReanalysisStatus] = useState(null);

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      
      // Fetch all data in parallel
      const [homeRes, missionRes, lossRes, reanalysisRes] = await Promise.all([
        fetch(`${API}/coach/home-intelligence`, { credentials: "include" }),
        fetch(`${API}/missions/today`, { credentials: "include" }),
        fetch(`${API}/coach/fresh-loss`, { credentials: "include" }).catch(() => null),
        fetch(`${API}/behavioral/reanalysis/status`, { credentials: "include" }).catch(() => null),
      ]);
      
      if (homeRes.ok) {
        setHomeData(await homeRes.json());
      }
      
      if (missionRes.ok) {
        setMission(await missionRes.json());
      }
      
      if (lossRes?.ok) {
        const lossData = await lossRes.json();
        if (lossData?.has_fresh_loss) {
          setFreshLoss(lossData);
        }
      }
      
      if (reanalysisRes?.ok) {
        const statusData = await reanalysisRes.json();
        if (statusData?.status === "RUNNING") {
          setReanalysisStatus(statusData);
        }
      }
    } catch (err) {
      console.error("Error fetching home data:", err);
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
      console.error("Failed to start mission:", err);
    } finally {
      setStarting(false);
    }
  };

  const handleStartRecovery = () => {
    if (freshLoss?.game_id) {
      navigate(`/recover/${freshLoss.game_id}`);
    }
  };

  // Greeting based on time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
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

  const hasFreshLoss = freshLoss?.has_fresh_loss;
  const userName = user?.name?.split(" ")[0] || "Player";
  const hasData = homeData?.has_data;
  const hasNewGame = homeData?.last_game?.is_new;

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto space-y-6" data-testid="coach-home">
        {/* Greeting */}
        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-sm text-muted-foreground"
        >
          {getGreeting()}, {userName}
        </motion.p>

        {/* P1.6: Reanalysis Progress Banner */}
        {reanalysisStatus && reanalysisStatus.status === "RUNNING" && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-2 py-2 px-4 rounded-lg bg-blue-500/10 border border-blue-500/30 text-sm"
            data-testid="reanalysis-banner"
          >
            <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
            <span className="text-blue-300">
              Updating your coaching history: {reanalysisStatus.processed_games}/{reanalysisStatus.total_games} games analyzed...
            </span>
          </motion.div>
        )}

        {/* Section 1: Development Phase Banner */}
        {hasData && (
          <DevelopmentPhaseBanner phase={homeData.development_phase} />
        )}

        {/* Section 2: Primary Action Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {hasFreshLoss ? (
            <PostLossRecoveryCard 
              loss={freshLoss} 
              onStart={handleStartRecovery}
            />
          ) : mission?.mission_id ? (
            <ActiveMissionCard 
              mission={mission}
              onStart={handleStartMission}
              starting={starting}
            />
          ) : (
            <NoMissionCard onImport={() => navigate("/import")} />
          )}
        </motion.div>

        {/* Section 3: Active Advice (THE KEY CARD) */}
        {hasData && homeData.active_advice && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <ActiveAdviceCard 
              advice={homeData.active_advice}
              focusCapacity={homeData.focus_capacity?.level}
            />
          </motion.div>
        )}

        {/* Section 4: Post-Game Review - BEHAVIORAL INSIGHTS (not just blunder count) */}
        {homeData?.last_game?.game_id && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <BehavioralInsightCard 
              gameId={homeData.last_game.game_id} 
              lastGame={homeData.last_game}
            />
          </motion.div>
        )}

        {/* Section 5: Recommended Drill */}
        {hasData && homeData.recommended_drill && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
          >
            <RecommendedDrillCard 
              drill={homeData.recommended_drill}
              advice={homeData.active_advice}
            />
          </motion.div>
        )}

        {/* Section 6: Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="flex gap-3"
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/import")}
            className="flex-1 text-muted-foreground"
            data-testid="quick-import"
          >
            <Import className="w-4 h-4 mr-2" />
            Import Games
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate("/progress")}
            className="flex-1 text-muted-foreground"
            data-testid="quick-progress"
          >
            <TrendingUp className="w-4 h-4 mr-2" />
            View Journey
          </Button>
        </motion.div>
      </div>
    </Layout>
  );
};

/* ========== SUB-COMPONENTS ========== */

/**
 * Post-Loss Recovery Card - High priority when fresh loss exists
 */
const PostLossRecoveryCard = ({ loss, onStart }) => {
  const minutes = loss?.estimated_minutes || 6;
  const focus = loss?.focus_label || "Critical moment";
  
  return (
    <div 
      className="relative overflow-hidden rounded-xl border-l-4 border-l-red-500 bg-card p-6"
      data-testid="post-loss-hero"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 via-transparent to-transparent pointer-events-none" />
      
      <div className="relative space-y-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-500" />
          <span className="text-xs font-semibold text-red-500 uppercase tracking-wide">
            Fresh Loss
          </span>
        </div>
        
        <h1 className="text-2xl font-bold tracking-tight">
          Tough game. Let's fix it.
        </h1>
        
        <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
          <Wrench className="w-5 h-5 text-muted-foreground" />
          <div>
            <p className="text-xs text-muted-foreground">Focus Area</p>
            <p className="text-sm font-medium">{focus}</p>
          </div>
        </div>
        
        <Button 
          onClick={onStart}
          size="lg"
          className="w-full bg-red-500 hover:bg-red-600 text-white font-semibold"
          data-testid="start-recovery-btn"
        >
          Fix this in {minutes} min
          <ChevronRight className="w-5 h-5 ml-2" />
        </Button>
      </div>
    </div>
  );
};

/**
 * No Mission Card - When user has no games/mission
 */
const NoMissionCard = ({ onImport }) => (
  <div 
    className="rounded-xl border border-dashed border-border bg-card/50 p-8 text-center"
    data-testid="no-mission-card"
  >
    <Gamepad2 className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
    <h2 className="text-lg font-semibold mb-2">No mission yet</h2>
    <p className="text-sm text-muted-foreground mb-4">
      Import a game to get your personalized coaching plan.
    </p>
    <Button onClick={onImport} data-testid="import-first-game">
      <Import className="w-4 h-4 mr-2" />
      Import Your First Game
    </Button>
  </div>
);

export default CoachHome;
