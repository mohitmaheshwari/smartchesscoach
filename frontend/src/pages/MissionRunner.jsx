import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import Layout from "@/components/Layout";
import {
  Target,
  ChevronRight,
  ChevronLeft,
  Check,
  X,
  Clock,
  Loader2,
  Trophy,
  AlertTriangle,
  RotateCcw,
  Home,
} from "lucide-react";
import { ProgressRing } from "@/components/ui/premium";

/**
 * MissionRunner - The page where users execute their daily missions.
 * Part of the Dopamine Engine Phase 2D.
 * 
 * Flow:
 * 1. Show mission briefing (protocol steps)
 * 2. Present drill positions one by one
 * 3. Track score and process signals
 * 4. Show completion screen with reward message
 */
const MissionRunner = ({ user }) => {
  const { missionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  // State from navigation or fetched
  const [mission, setMission] = useState(location.state?.mission || null);
  const [sessionId, setSessionId] = useState(location.state?.session_id || null);
  const [loading, setLoading] = useState(!mission);
  const [error, setError] = useState(null);
  
  // Mission progress state
  const [phase, setPhase] = useState("briefing"); // briefing | drill | complete
  const [currentStep, setCurrentStep] = useState(0);
  const [score, setScore] = useState({ attempted: 0, correct: 0, process_points: 0 });
  const [completionResult, setCompletionResult] = useState(null);
  
  // Timer
  const [startTime, setStartTime] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!mission) {
      fetchMission();
    }
  }, [missionId]);
  
  // Timer effect
  useEffect(() => {
    if (phase === "drill" && startTime) {
      const interval = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [phase, startTime]);

  const fetchMission = async () => {
    try {
      const res = await fetch(`${API}/missions/today`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setMission(data);
        
        // Start mission if not already started
        if (data.status === "pending") {
          const startRes = await fetch(`${API}/missions/${data.mission_id}/start`, {
            method: "POST",
            credentials: "include",
          });
          if (startRes.ok) {
            const startData = await startRes.json();
            setSessionId(startData.session_id);
          }
        }
      }
    } catch (err) {
      setError("Could not load mission");
    } finally {
      setLoading(false);
    }
  };

  const handleStartDrill = () => {
    setPhase("drill");
    setStartTime(Date.now());
    setCurrentStep(0);
  };

  const handleDrillAnswer = async (correct) => {
    const newScore = {
      ...score,
      attempted: score.attempted + 1,
      correct: score.correct + (correct ? 1 : 0),
    };
    setScore(newScore);
    
    // Record step to backend
    try {
      await fetch(`${API}/missions/${missionId}/step`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          step_type: "drill_result",
          payload: {
            step_index: currentStep,
            correct,
            time_taken_ms: Date.now() - startTime,
          },
        }),
      });
    } catch (err) {
      console.error("Failed to record step:", err);
    }
    
    // Move to next step or complete
    const totalSteps = mission?.goal?.target || 5;
    if (currentStep + 1 >= totalSteps) {
      handleComplete(newScore);
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleComplete = async (finalScore) => {
    setPhase("complete");
    
    try {
      const res = await fetch(`${API}/missions/${missionId}/complete`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ final_score: finalScore }),
      });
      
      if (res.ok) {
        const data = await res.json();
        setCompletionResult(data);
      }
    } catch (err) {
      console.error("Failed to complete mission:", err);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
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

  if (error || !mission) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
          <AlertTriangle className="w-12 h-12 text-amber-500 mb-4" />
          <h2 className="text-xl font-semibold mb-2">Mission Not Found</h2>
          <p className="text-muted-foreground mb-4">{error || "No active mission available"}</p>
          <Button onClick={() => navigate("/dashboard")}>
            <Home className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </div>
      </Layout>
    );
  }

  const protocolSteps = mission.micro_protocol || [];
  const totalSteps = mission.goal?.target || 5;
  const threshold = mission.goal?.success_threshold || 4;
  const passed = score.correct >= threshold;

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto" data-testid="mission-runner-page">
        {/* Progress Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => navigate("/dashboard")}
              className="text-muted-foreground hover:text-foreground -ml-2"
            >
              <ChevronLeft className="w-4 h-4 mr-1" />
              Exit
            </Button>
            
            {phase === "drill" && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {formatTime(elapsedSeconds)}
                </span>
                <span className="text-sm font-medium">
                  {currentStep + 1} / {totalSteps}
                </span>
              </div>
            )}
          </div>
          
          {/* Progress bar */}
          {phase === "drill" && (
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-primary"
                initial={{ width: "0%" }}
                animate={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          )}
        </div>

        <AnimatePresence mode="wait">
          {/* ========== BRIEFING PHASE ========== */}
          {phase === "briefing" && (
            <motion.div
              key="briefing"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              <div className="text-center mb-8">
                <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <Target className="w-8 h-8 text-primary" />
                </div>
                <h1 className="text-2xl font-bold mb-2">{mission.focus_label}</h1>
                <p className="text-muted-foreground">
                  {mission.estimated_minutes} minute mission · {totalSteps} positions
                </p>
              </div>

              {/* Protocol Steps */}
              <Card className="surface">
                <CardContent className="py-6">
                  <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-xs text-primary font-bold">
                      !
                    </span>
                    Before Each Move
                  </h3>
                  <div className="space-y-3">
                    {protocolSteps.map((step, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"
                      >
                        <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium text-primary flex-shrink-0">
                          {idx + 1}
                        </span>
                        <p className="text-sm">{step}</p>
                      </motion.div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Goal */}
              <div className="text-center text-sm text-muted-foreground">
                Pass by getting <span className="text-foreground font-medium">{threshold}+ correct</span>
              </div>

              {/* Start Button */}
              <Button
                onClick={handleStartDrill}
                size="lg"
                className="w-full"
                data-testid="start-drill-btn"
              >
                Start Mission
                <ChevronRight className="w-5 h-5 ml-2" />
              </Button>
            </motion.div>
          )}

          {/* ========== DRILL PHASE ========== */}
          {phase === "drill" && (
            <motion.div
              key="drill"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Placeholder drill UI - To be replaced with actual chess position */}
              <Card className="surface">
                <CardContent className="py-8">
                  <div className="text-center">
                    <h2 className="text-lg font-semibold mb-4">Position {currentStep + 1}</h2>
                    
                    {/* Placeholder board */}
                    <div className="w-full aspect-square max-w-md mx-auto bg-muted/50 rounded-lg flex items-center justify-center mb-6 border-2 border-dashed border-border">
                      <div className="text-center text-muted-foreground">
                        <Target className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">Chess position will appear here</p>
                        <p className="text-xs mt-1">Find the best move</p>
                      </div>
                    </div>
                    
                    {/* Protocol reminder */}
                    <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 mb-6 text-left">
                      <p className="text-xs text-primary font-medium mb-1">Remember:</p>
                      <p className="text-sm text-muted-foreground">{protocolSteps[currentStep % protocolSteps.length]}</p>
                    </div>
                    
                    {/* Answer buttons (placeholder) */}
                    <div className="flex gap-4 justify-center">
                      <Button
                        variant="outline"
                        size="lg"
                        onClick={() => handleDrillAnswer(false)}
                        className="flex-1 max-w-[150px]"
                        data-testid="answer-wrong"
                      >
                        <X className="w-5 h-5 mr-2 text-red-500" />
                        Missed
                      </Button>
                      <Button
                        size="lg"
                        onClick={() => handleDrillAnswer(true)}
                        className="flex-1 max-w-[150px] bg-emerald-600 hover:bg-emerald-700"
                        data-testid="answer-correct"
                      >
                        <Check className="w-5 h-5 mr-2" />
                        Got it
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Current score */}
              <div className="flex justify-center gap-8 text-sm">
                <div className="text-center">
                  <p className="text-emerald-500 font-bold text-xl">{score.correct}</p>
                  <p className="text-muted-foreground">Correct</p>
                </div>
                <div className="text-center">
                  <p className="text-red-500 font-bold text-xl">{score.attempted - score.correct}</p>
                  <p className="text-muted-foreground">Missed</p>
                </div>
              </div>
            </motion.div>
          )}

          {/* ========== COMPLETION PHASE ========== */}
          {phase === "complete" && (
            <motion.div
              key="complete"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="space-y-6 text-center"
            >
              {/* Result icon */}
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", delay: 0.2 }}
                className={`w-20 h-20 rounded-full mx-auto flex items-center justify-center ${
                  passed ? "bg-emerald-500/20" : "bg-amber-500/20"
                }`}
              >
                {passed ? (
                  <Trophy className="w-10 h-10 text-emerald-500" />
                ) : (
                  <RotateCcw className="w-10 h-10 text-amber-500" />
                )}
              </motion.div>

              {/* Result message */}
              <div>
                <h1 className={`text-2xl font-bold mb-2 ${passed ? "text-emerald-500" : "text-amber-500"}`}>
                  {passed ? "Mission Complete!" : "Almost There"}
                </h1>
                <p className="text-muted-foreground">
                  {passed 
                    ? "You trained the exact pattern from your game."
                    : "This pattern needs more work. We'll try again tomorrow."}
                </p>
              </div>

              {/* Score display */}
              <Card className="surface">
                <CardContent className="py-6">
                  <div className="flex items-center justify-center gap-8">
                    <ProgressRing
                      progress={(score.correct / totalSteps) * 100}
                      size={80}
                      strokeWidth={8}
                      color={passed ? "stroke-emerald-500" : "stroke-amber-500"}
                      label={`${score.correct}/${totalSteps}`}
                    />
                    <div className="text-left">
                      <p className="text-sm text-muted-foreground">Focus</p>
                      <p className="font-semibold">{mission.focus_label}</p>
                      <p className="text-sm text-muted-foreground mt-2">Time</p>
                      <p className="font-semibold">{formatTime(elapsedSeconds)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Reward message */}
              {completionResult?.message && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                  className="p-4 rounded-lg bg-muted/50 text-sm"
                >
                  {completionResult.message.text}
                </motion.div>
              )}

              {/* Actions */}
              <div className="flex gap-4 justify-center pt-4">
                <Button
                  variant="outline"
                  onClick={() => navigate("/dashboard")}
                  data-testid="back-to-dashboard"
                >
                  <Home className="w-4 h-4 mr-2" />
                  Dashboard
                </Button>
                <Button
                  onClick={() => navigate("/training")}
                  data-testid="more-training"
                >
                  More Training
                  <ChevronRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Layout>
  );
};

export default MissionRunner;
