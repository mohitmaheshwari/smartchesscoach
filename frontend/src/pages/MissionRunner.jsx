import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
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
  Eye,
  Lightbulb,
  Brain,
  Dumbbell,
  Flag,
} from "lucide-react";
import { ProgressRing } from "@/components/ui/premium";

/**
 * MissionRunner - The page where users execute their daily missions.
 * Part of the Dopamine Engine Phase 2D.
 * 
 * Flow:
 * 1. Reflect Phase - Protocol briefing  
 * 2. Train Phase - Drill positions
 * 3. Wrap-up Phase - Results and next steps
 */

// Mission Stepper Component - Shows Reflect → Train → Wrap-up progress
const MissionStepper = ({ currentPhase }) => {
  const steps = [
    { id: "briefing", label: "Reflect", icon: Brain, description: "Review protocol" },
    { id: "drill", label: "Train", icon: Dumbbell, description: "Solve positions" },
    { id: "complete", label: "Wrap-up", icon: Flag, description: "See results" },
  ];
  
  const currentIndex = steps.findIndex(s => s.id === currentPhase);
  
  return (
    <div className="flex items-center justify-center gap-2 mb-6" data-testid="mission-stepper">
      {steps.map((step, idx) => {
        const StepIcon = step.icon;
        const isActive = step.id === currentPhase;
        const isComplete = idx < currentIndex;
        
        return (
          <div key={step.id} className="flex items-center">
            {/* Step */}
            <div className="flex flex-col items-center">
              <div 
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isActive 
                    ? "bg-primary text-primary-foreground scale-110" 
                    : isComplete 
                      ? "bg-emerald-500/20 text-emerald-500" 
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {isComplete ? (
                  <Check className="w-5 h-5" />
                ) : (
                  <StepIcon className="w-5 h-5" />
                )}
              </div>
              <span className={`text-xs mt-1 font-medium ${
                isActive ? "text-primary" : isComplete ? "text-emerald-500" : "text-muted-foreground"
              }`}>
                {step.label}
              </span>
            </div>
            
            {/* Connector */}
            {idx < steps.length - 1 && (
              <div className={`w-12 h-0.5 mx-2 transition-colors ${
                idx < currentIndex ? "bg-emerald-500" : "bg-muted"
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );
};

const MissionRunner = ({ user }) => {
  const { missionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  // State from navigation or fetched
  const [mission, setMission] = useState(location.state?.mission || null);
  const [sessionId, setSessionId] = useState(location.state?.session_id || null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Drill positions
  const [positions, setPositions] = useState([]);
  const [positionsLoading, setPositionsLoading] = useState(false);
  
  // Mission progress state
  const [phase, setPhase] = useState("briefing"); // briefing | drill | complete
  const [currentStep, setCurrentStep] = useState(0);
  const [score, setScore] = useState({ attempted: 0, correct: 0, process_points: 0 });
  const [completionResult, setCompletionResult] = useState(null);
  
  // Drill interaction state
  const [showHint, setShowHint] = useState(false);
  const [showAnswer, setShowAnswer] = useState(false);
  const [selectedMove, setSelectedMove] = useState(null);
  const [feedback, setFeedback] = useState(null); // "correct" | "incorrect" | null
  
  // Timer
  const [startTime, setStartTime] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    fetchMissionData();
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

  const fetchMissionData = async () => {
    try {
      setLoading(true);
      
      // Fetch mission if not provided
      let missionData = mission;
      if (!missionData) {
        const res = await fetch(`${API}/missions/today`, {
          credentials: "include",
        });
        if (res.ok) {
          missionData = await res.json();
          setMission(missionData);
        }
      }
      
      // Fetch drill positions for this mission
      if (missionData?.mission_id) {
        setPositionsLoading(true);
        const posRes = await fetch(`${API}/missions/${missionData.mission_id}/positions`, {
          credentials: "include",
        });
        if (posRes.ok) {
          const posData = await posRes.json();
          setPositions(posData.positions || []);
        }
        setPositionsLoading(false);
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
    setShowHint(false);
    setShowAnswer(false);
    setFeedback(null);
  };

  const handleMoveSelect = (move) => {
    if (feedback) return; // Already answered
    
    const currentPosition = positions[currentStep];
    if (!currentPosition) return;
    
    const isCorrect = move === currentPosition.best_move;
    setSelectedMove(move);
    
    // Update score
    const newScore = {
      ...score,
      attempted: score.attempted + 1,
      correct: score.correct + (isCorrect ? 1 : 0),
    };
    setScore(newScore);
    
    // Record step to backend
    recordStep(isCorrect);
    
    // Delay setting feedback to allow board animation to complete
    setTimeout(() => {
      setFeedback(isCorrect ? "correct" : "incorrect");
    }, 300);
  };

  const handleShowAnswer = () => {
    setShowAnswer(true);
    // Count as incorrect if they needed to see answer
    if (!feedback) {
      setFeedback("incorrect");
      setScore({
        ...score,
        attempted: score.attempted + 1,
      });
      recordStep(false);
    }
  };

  const recordStep = async (correct) => {
    try {
      await fetch(`${API}/missions/${missionId}/step`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          step_type: "drill_result",
          payload: {
            step_index: currentStep,
            is_correct: correct,
            time_taken_ms: Date.now() - startTime,
            position_id: positions[currentStep]?.position_id,
            used_hint: showHint,
          },
        }),
      });
    } catch (err) {
      console.error("Failed to record step:", err);
    }
  };

  const handleNextPosition = () => {
    const totalSteps = positions.length || mission?.goal?.target || 5;
    
    if (currentStep + 1 >= totalSteps) {
      handleComplete(score);
    } else {
      setCurrentStep(currentStep + 1);
      setShowHint(false);
      setShowAnswer(false);
      setFeedback(null);
      setSelectedMove(null);
    }
  };

  const handleComplete = async (finalScore) => {
    setPhase("complete");
    
    try {
      const res = await fetch(`${API}/missions/${missionId}/complete`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score: finalScore }),
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

  // Get arrows for the current position
  const getArrows = () => {
    if (!positions[currentStep]) return [];
    const pos = positions[currentStep];
    const arrows = [];
    
    // Show user's wrong move in red if answered incorrectly
    if (feedback === "incorrect" && selectedMove) {
      const userArrow = sanToArrow(selectedMove, pos.fen, "red");
      if (userArrow) arrows.push(userArrow);
    }
    
    // Show best move in green if showing answer or correct
    if (showAnswer || feedback === "correct") {
      const bestArrow = sanToArrow(pos.best_move, pos.fen, "green");
      if (bestArrow) arrows.push(bestArrow);
    }
    
    return arrows;
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

  // Get legal moves for current position
  const getLegalMoves = () => {
    const pos = positions[currentStep];
    if (!pos?.fen) return [];
    try {
      const chess = new Chess(pos.fen);
      return chess.moves();
    } catch (e) {
      return [];
    }
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
          <Button onClick={() => navigate("/home")}>
            <Home className="w-4 h-4 mr-2" />
            Back to Home
          </Button>
        </div>
      </Layout>
    );
  }

  const protocolSteps = mission.micro_protocol || [];
  const totalSteps = positions.length || mission.goal?.target || 5;
  const threshold = mission.goal?.success_threshold || Math.ceil(totalSteps * 0.8);
  const passed = score.correct >= threshold;
  const currentPosition = positions[currentStep];

  return (
    <Layout user={user}>
      <div className="max-w-3xl mx-auto" data-testid="mission-runner-page">
        {/* Mission Stepper - Shows Reflect → Train → Wrap-up */}
        <MissionStepper currentPhase={phase} />
        
        {/* Progress Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => navigate("/home")}
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
                disabled={positionsLoading || positions.length === 0}
                size="lg"
                className="w-full"
                data-testid="start-drill-btn"
              >
                {positionsLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin mr-2" />
                    Loading positions...
                  </>
                ) : positions.length === 0 ? (
                  "No positions available"
                ) : (
                  <>
                    Start Mission
                    <ChevronRight className="w-5 h-5 ml-2" />
                  </>
                )}
              </Button>
            </motion.div>
          )}

          {/* ========== DRILL PHASE ========== */}
          {phase === "drill" && currentPosition && (
            <motion.div
              key={`drill-${currentStep}`}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="space-y-4"
            >
              {/* Position info */}
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Position {currentStep + 1}</h2>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  currentPosition.type === "blunder" 
                    ? "bg-red-500/20 text-red-500" 
                    : "bg-amber-500/20 text-amber-500"
                }`}>
                  {currentPosition.type === "blunder" ? "Blunder" : "Mistake"}
                </span>
              </div>
              
              {/* Chess Board */}
              <Card className="surface overflow-hidden">
                <div className="aspect-square max-w-[480px] mx-auto">
                  <CoachBoard
                    position={currentPosition.fen}
                    userColor={currentPosition.fen?.includes(" w ") ? "white" : "black"}
                    interactive={!feedback}
                    expectedMoves={[]}
                    onUserMove={(moveData) => handleMoveSelect(moveData.san)}
                    customArrows={getArrows()}
                  />
                </div>
              </Card>
              
              {/* Protocol reminder */}
              <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
                <p className="text-xs text-primary font-medium mb-1">Remember:</p>
                <p className="text-sm text-muted-foreground">
                  {protocolSteps[currentStep % protocolSteps.length] || "Find the best move"}
                </p>
              </div>
              
              {/* Feedback */}
              <AnimatePresence>
                {feedback && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`p-4 rounded-lg ${
                      feedback === "correct" 
                        ? "bg-emerald-500/10 border border-emerald-500/30" 
                        : "bg-red-500/10 border border-red-500/30"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {feedback === "correct" ? (
                        <Check className="w-6 h-6 text-emerald-500" />
                      ) : (
                        <X className="w-6 h-6 text-red-500" />
                      )}
                      <div>
                        <p className={`font-semibold ${
                          feedback === "correct" ? "text-emerald-500" : "text-red-500"
                        }`}>
                          {feedback === "correct" ? "Correct!" : "Not quite"}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Best move: <span className="font-mono font-bold">{currentPosition.best_move}</span>
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
              
              {/* Action buttons */}
              <div className="flex gap-3">
                {!feedback ? (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowHint(!showHint)}
                      className="flex-1"
                    >
                      <Lightbulb className="w-4 h-4 mr-2" />
                      {showHint ? "Hide Hint" : "Show Hint"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleShowAnswer}
                      className="flex-1"
                    >
                      <Eye className="w-4 h-4 mr-2" />
                      Show Answer
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={handleNextPosition}
                    className="w-full"
                    data-testid="next-position-btn"
                  >
                    {currentStep + 1 >= totalSteps ? "Finish" : "Next Position"}
                    <ChevronRight className="w-5 h-5 ml-2" />
                  </Button>
                )}
              </div>
              
              {/* Hint display */}
              {showHint && !feedback && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30"
                >
                  <p className="text-sm text-amber-600">
                    <Lightbulb className="w-4 h-4 inline mr-1" />
                    {currentPosition.explanation || "Look for forcing moves: checks, captures, threats."}
                  </p>
                </motion.div>
              )}
              
              {/* Current score */}
              <div className="flex justify-center gap-8 text-sm pt-2">
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
                  onClick={() => navigate("/home")}
                  data-testid="back-to-home"
                >
                  <Home className="w-4 h-4 mr-2" />
                  Home
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
