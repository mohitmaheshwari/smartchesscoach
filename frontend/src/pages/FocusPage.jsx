import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import {
  Loader2,
  Target,
  Brain,
  Eye,
  Zap,
  Shield,
  Clock,
  Crown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Flame,
  Play,
  ArrowRight,
  Swords,
  BookOpen,
  Timer,
  TrendingUp,
  ChevronRight,
  Pause,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Lock,
  Info,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/**
 * FocusPage - Deterministic Personalized Coaching System
 * 
 * Layout:
 * A) Coach Note (personalized text from metrics)
 * B) This Week's Requirements (3 progress bars)
 * C) Your 2 Rules (from primary focus)
 * D) Your Opening Pack (personalized)
 * E) Start Mission (in-app runner with active time tracking)
 * F) Turning Point Replay
 * G) Bucket Breakdown (debug panel)
 */
const FocusPage = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);

  // Data states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [focusPlan, setFocusPlan] = useState(null);
  const [coachNote, setCoachNote] = useState("");
  const [streak, setStreak] = useState(0);

  // Bucket breakdown state
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [bucketBreakdown, setBucketBreakdown] = useState(null);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);

  // Board state
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [boardTitle, setBoardTitle] = useState("Interactive Board");

  // Mission state
  const [missionActive, setMissionActive] = useState(false);
  const [missionSession, setMissionSession] = useState(null);
  const [activeSeconds, setActiveSeconds] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [stepProgress, setStepProgress] = useState({});

  // Fetch data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        const res = await fetch(`${API}/focus-plan`, { credentials: "include" });

        if (res.ok) {
          const data = await res.json();
          if (data.plan) {
            setFocusPlan(data.plan);
            setCoachNote(data.coach_note || "");
            setStreak(data.streak || 0);
          } else if (data.needs_more_games) {
            setFocusPlan({ needs_more_games: true, ...data });
          } else {
            setError("Failed to load focus plan");
          }
        } else {
          setError("Failed to load focus plan");
        }
      } catch (err) {
        console.error("Failed to load focus plan:", err);
        setError("Failed to load focus plan");
        toast.error("Failed to load focus plan");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Handle viewing position on board
  const handleViewPosition = useCallback((fen, title) => {
    if (boardRef.current && fen) {
      boardRef.current.jumpToFen(fen);
      setCurrentFen(fen);
      setBoardTitle(title || "Position");
    }
  }, []);

  // Fetch bucket breakdown
  const fetchBucketBreakdown = async () => {
    if (bucketBreakdown) {
      setShowBreakdown(!showBreakdown);
      return;
    }
    
    setLoadingBreakdown(true);
    try {
      const res = await fetch(`${API}/focus-plan/bucket-breakdown`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setBucketBreakdown(data);
        setShowBreakdown(true);
      }
    } catch (err) {
      toast.error("Failed to load breakdown");
    } finally {
      setLoadingBreakdown(false);
    }
  };

  // Start mission
  const startMission = async () => {
    try {
      const res = await fetch(`${API}/focus-plan/mission/start`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        const session = await res.json();
        setMissionSession(session);
        setMissionActive(true);
        setActiveSeconds(0);
        setCurrentStep(0);
        setStepProgress({});
        toast.success("Mission started! 15 minutes to go.");
      }
    } catch (err) {
      toast.error("Failed to start mission");
    }
  };

  // Record interaction (heartbeat)
  const recordInteraction = useCallback(async (eventType, eventData = null) => {
    if (!missionSession?.session_id) return;
    
    try {
      const res = await fetch(`${API}/focus-plan/mission/interaction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: missionSession.session_id,
          event_type: eventType,
          event_data: eventData,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveSeconds(Math.round(data.active_seconds || 0));
      }
    } catch (err) {
      console.error("Failed to record interaction:", err);
    }
  }, [missionSession]);

  // Heartbeat while mission is active
  useEffect(() => {
    if (!missionActive || !missionSession) return;
    
    const interval = setInterval(() => {
      recordInteraction("heartbeat");
    }, 5000);
    
    return () => clearInterval(interval);
  }, [missionActive, missionSession, recordInteraction]);

  // Complete mission
  const completeMission = async () => {
    if (!missionSession?.session_id) return;
    
    try {
      const res = await fetch(`${API}/focus-plan/mission/complete?session_id=${missionSession.session_id}`, {
        method: "POST",
        credentials: "include",
      });
      if (res.ok) {
        setMissionActive(false);
        setMissionSession(null);
        toast.success("Mission complete! Great work!");
        // Refresh data
        window.location.reload();
      }
    } catch (err) {
      toast.error("Failed to complete mission");
    }
  };

  // Get bucket icon
  const getBucketIcon = (bucketCode) => {
    const icons = {
      PIECE_SAFETY: <Shield className="w-5 h-5" />,
      THREAT_AWARENESS: <Eye className="w-5 h-5" />,
      TACTICAL_EXECUTION: <Zap className="w-5 h-5" />,
      ADVANTAGE_DISCIPLINE: <Crown className="w-5 h-5" />,
      OPENING_STABILITY: <BookOpen className="w-5 h-5" />,
      TIME_DISCIPLINE: <Clock className="w-5 h-5" />,
      ENDGAME_FUNDAMENTALS: <Target className="w-5 h-5" />,
    };
    return icons[bucketCode] || <Target className="w-5 h-5" />;
  };

  // Format seconds to mm:ss
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  // Error state
  if (error) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto text-center py-12">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-amber-400" />
          <h3 className="text-lg font-medium mb-2">Error Loading Focus</h3>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </Layout>
    );
  }

  // Need more games state
  if (focusPlan?.needs_more_games) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto py-12">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-12 text-center">
                <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-medium mb-2">Building Your Profile</h3>
                <p className="text-muted-foreground mb-6">
                  Analyze {focusPlan.games_required - focusPlan.games_analyzed} more games to unlock personalized coaching
                </p>
                <Progress value={(focusPlan.games_analyzed / focusPlan.games_required) * 100} className="w-48 mx-auto mb-4" />
                <p className="text-sm text-muted-foreground mb-4">
                  {focusPlan.games_analyzed}/{focusPlan.games_required} games analyzed
                </p>
                <Button onClick={() => navigate("/import")}>Import Games</Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </Layout>
    );
  }

  const { primary_focus, secondary_focus, rules, openings, mission, weekly_requirements, turning_points, ratings } = focusPlan || {};
  const targetSeconds = mission?.active_seconds_target || 900;

  return (
    <Layout user={user}>
      <div className="max-w-6xl mx-auto px-4 py-6">
        
        {/* ============================================ */}
        {/* HEADER: Coach Note */}
        {/* ============================================ */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-2xl font-bold mb-2">Focus</h1>
              <p className="text-muted-foreground text-sm leading-relaxed">
                {coachNote || `You're rated ${ratings?.current || 1200}. Focus on ${primary_focus?.label || 'your weaknesses'} this week.`}
              </p>
            </div>
            
            {/* Streak Badge */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <Flame className={`w-5 h-5 ${streak > 0 ? 'text-orange-500' : 'text-muted-foreground'}`} />
              <span className="text-lg font-bold text-amber-500">{streak}</span>
              <span className="text-xs text-muted-foreground">day streak</span>
            </div>
          </div>
        </motion.div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* ============================================ */}
          {/* LEFT COLUMN: Rules + Openings */}
          {/* ============================================ */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* PRIMARY FOCUS + RULES */}
            <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
              <Card className="border-blue-500/20 overflow-hidden" data-testid="primary-focus-card">
                <CardContent className="p-5">
                  {/* Focus Badge */}
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400">
                      {getBucketIcon(primary_focus?.code)}
                    </div>
                    <div>
                      <div className="text-xs text-blue-400 font-medium uppercase tracking-wider">This Week's Focus</div>
                      <h2 className="text-lg font-bold">{primary_focus?.label || "Your Weakness"}</h2>
                    </div>
                    {primary_focus?.frequency_rate > 0 && (
                      <div className="ml-auto text-right">
                        <div className="text-2xl font-bold text-blue-400">{Math.round(primary_focus.frequency_rate * 100)}%</div>
                        <div className="text-xs text-muted-foreground">of games affected</div>
                      </div>
                    )}
                  </div>
                  
                  {/* Your 2 Rules */}
                  <div className="space-y-2">
                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Your 2 Rules</div>
                    {rules?.map((rule, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-3 rounded-lg bg-blue-500/5 border border-blue-500/10"
                      >
                        <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 text-sm font-bold flex-shrink-0">
                          {i + 1}
                        </div>
                        <p className="text-sm">{rule}</p>
                      </div>
                    ))}
                  </div>
                  
                  {/* Example Position */}
                  {primary_focus?.example_position && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="mt-4 text-blue-400"
                      onClick={() => handleViewPosition(
                        primary_focus.example_position.fen,
                        `${primary_focus.label} - Move ${primary_focus.example_position.move_number}`
                      )}
                    >
                      <Eye className="w-4 h-4 mr-2" />
                      See Example Position
                    </Button>
                  )}
                </CardContent>
              </Card>
            </motion.div>

            {/* OPENING PACK */}
            <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
              <Card className="border-emerald-500/20" data-testid="opening-pack-card">
                <CardContent className="p-5">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-400">
                      <BookOpen className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs text-emerald-400 font-medium uppercase tracking-wider">Opening Pack</div>
                      <h2 className="text-lg font-bold">Your Openings This Week</h2>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {/* White Opening */}
                    {openings?.white && (
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="w-4 h-4 rounded bg-white border border-border"></div>
                          <span className="text-xs text-muted-foreground">As White</span>
                        </div>
                        <div className="font-medium text-sm mb-1">{openings.white.name}</div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{openings.white.games} games</span>
                          <span>•</span>
                          <span>{openings.white.win_rate}% win</span>
                        </div>
                        {openings.white.avg_stability < 70 && (
                          <div className="mt-2 text-xs text-amber-400">
                            {openings.white.recommendation}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* Black vs e4 */}
                    {openings?.black_vs_e4 && (
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="w-4 h-4 rounded bg-zinc-800 border border-border"></div>
                          <span className="text-xs text-muted-foreground">vs 1.e4</span>
                        </div>
                        <div className="font-medium text-sm mb-1">{openings.black_vs_e4.name}</div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{openings.black_vs_e4.games} games</span>
                          <span>•</span>
                          <span>{openings.black_vs_e4.win_rate}% win</span>
                        </div>
                      </div>
                    )}
                    
                    {/* Black vs d4 */}
                    {openings?.black_vs_d4 && (
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="w-4 h-4 rounded bg-zinc-800 border border-border"></div>
                          <span className="text-xs text-muted-foreground">vs 1.d4</span>
                        </div>
                        <div className="font-medium text-sm mb-1">{openings.black_vs_d4.name}</div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{openings.black_vs_d4.games} games</span>
                          <span>•</span>
                          <span>{openings.black_vs_d4.win_rate}% win</span>
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* TURNING POINTS / GUIDED REPLAY */}
            {turning_points && turning_points.length > 0 && (
              <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
                <Card className="border-purple-500/20" data-testid="turning-points-card">
                  <CardContent className="p-5">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center text-purple-400">
                        <TrendingUp className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="text-xs text-purple-400 font-medium uppercase tracking-wider">Guided Replay</div>
                        <h2 className="text-lg font-bold">Your Biggest Turning Points</h2>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      {turning_points.slice(0, 3).map((tp, i) => (
                        <div
                          key={tp.turning_point_id}
                          className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border/50 cursor-pointer hover:border-purple-500/30 transition-colors"
                          onClick={() => handleViewPosition(tp.fen, `Turning Point - Move ${tp.move_number}`)}
                        >
                          <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 text-sm font-bold">
                            {i + 1}
                          </div>
                          <div className="flex-1">
                            <div className="text-sm font-medium">Move {tp.move_number} • {tp.phase}</div>
                            <div className="text-xs text-muted-foreground">
                              You played {tp.your_move}, best was {tp.best_move} ({tp.cp_loss}cp loss)
                            </div>
                          </div>
                          <Eye className="w-4 h-4 text-muted-foreground" />
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>

          {/* ============================================ */}
          {/* RIGHT COLUMN: Board + Mission */}
          {/* ============================================ */}
          <div className="space-y-6">
            
            {/* Interactive Board */}
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <Card className="border-2 border-border/50">
                <CardContent className="p-4">
                  <div className="text-sm text-muted-foreground mb-2">{boardTitle}</div>
                  <CoachBoard
                    ref={boardRef}
                    initialFen={currentFen}
                    userColor="white"
                    drillMode={false}
                    showControls={true}
                  />
                </CardContent>
              </Card>
            </motion.div>

            {/* Weekly Requirements */}
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
              <Card className="border-amber-500/20" data-testid="weekly-requirements-card">
                <CardContent className="p-4">
                  <div className="text-xs text-amber-400 font-medium uppercase tracking-wider mb-3">This Week</div>
                  
                  <div className="space-y-3">
                    {/* Games with openings */}
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Games with openings</span>
                        <span className="text-muted-foreground">
                          {weekly_requirements?.games_with_openings?.current || 0}/{weekly_requirements?.games_with_openings?.target || 10}
                        </span>
                      </div>
                      <Progress 
                        value={((weekly_requirements?.games_with_openings?.current || 0) / (weekly_requirements?.games_with_openings?.target || 10)) * 100} 
                        className="h-2"
                      />
                    </div>
                    
                    {/* Missions completed */}
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Missions completed</span>
                        <span className="text-muted-foreground">
                          {weekly_requirements?.missions_completed?.current || 0}/{weekly_requirements?.missions_completed?.target || 7}
                        </span>
                      </div>
                      <Progress 
                        value={((weekly_requirements?.missions_completed?.current || 0) / (weekly_requirements?.missions_completed?.target || 7)) * 100}
                        className="h-2"
                      />
                    </div>
                    
                    {/* Guided replays */}
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Guided replays</span>
                        <span className="text-muted-foreground">
                          {weekly_requirements?.guided_replays?.current || 0}/{weekly_requirements?.guided_replays?.target || 2}
                        </span>
                      </div>
                      <Progress 
                        value={((weekly_requirements?.guided_replays?.current || 0) / (weekly_requirements?.guided_replays?.target || 2)) * 100}
                        className="h-2"
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>

            {/* Mission Card */}
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              <Card className={`${missionActive ? 'border-green-500/40 bg-green-500/5' : 'border-amber-500/20'}`} data-testid="mission-card">
                <CardContent className="p-4">
                  {!missionActive ? (
                    // Mission Start State
                    <>
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-400">
                          <Timer className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="text-xs text-amber-400 font-medium uppercase tracking-wider">Daily Mission</div>
                          <h3 className="font-bold">15 Minute Focus</h3>
                        </div>
                      </div>
                      
                      <div className="space-y-2 mb-4">
                        {mission?.steps?.map((step, i) => (
                          <div key={i} className="flex items-center gap-2 text-sm">
                            <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs">
                              {i + 1}
                            </div>
                            <span className="text-muted-foreground">{step.label}</span>
                            <span className="ml-auto text-xs text-muted-foreground">
                              {step.required} {step.type === "GUIDED_REPLAY" ? "plies" : "positions"}
                            </span>
                          </div>
                        ))}
                      </div>
                      
                      <Button 
                        className="w-full bg-amber-500 hover:bg-amber-600 text-black"
                        onClick={startMission}
                      >
                        <Play className="w-4 h-4 mr-2" />
                        Start Mission
                      </Button>
                    </>
                  ) : (
                    // Mission Active State
                    <>
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse"></div>
                          <span className="text-green-400 font-medium text-sm">Mission Active</span>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-mono font-bold">{formatTime(activeSeconds)}</div>
                          <div className="text-xs text-muted-foreground">/ {formatTime(targetSeconds)}</div>
                        </div>
                      </div>
                      
                      <Progress value={(activeSeconds / targetSeconds) * 100} className="h-3 mb-4" />
                      
                      <div className="flex gap-2">
                        <Button 
                          variant="outline" 
                          className="flex-1"
                          onClick={() => setMissionActive(false)}
                        >
                          <Pause className="w-4 h-4 mr-2" />
                          Pause
                        </Button>
                        <Button 
                          className="flex-1 bg-green-500 hover:bg-green-600"
                          onClick={completeMission}
                          disabled={activeSeconds < targetSeconds * 0.8}
                        >
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                          Complete
                        </Button>
                      </div>
                      
                      {activeSeconds < targetSeconds * 0.8 && (
                        <p className="text-xs text-muted-foreground mt-2 text-center">
                          Complete at least 12 minutes to finish
                        </p>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </div>

        {/* ============================================ */}
        {/* BUCKET BREAKDOWN (Why This Focus?) */}
        {/* ============================================ */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ delay: 0.3 }}
          className="mt-8"
        >
          <button
            onClick={fetchBucketBreakdown}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mx-auto"
            data-testid="bucket-breakdown-toggle"
          >
            {loadingBreakdown ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <BarChart3 className="w-4 h-4" />
            )}
            <span>Why this focus?</span>
            {showBreakdown ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          <AnimatePresence>
            {showBreakdown && bucketBreakdown && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <Card className="mt-4 border-muted-foreground/20" data-testid="bucket-breakdown-panel">
                  <CardContent className="p-5">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center text-muted-foreground">
                        <BarChart3 className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-bold">Cost Score Breakdown</h3>
                        <p className="text-xs text-muted-foreground">
                          Rating: {bucketBreakdown.rating} ({bucketBreakdown.rating_band})
                        </p>
                      </div>
                    </div>

                    <div className="mb-4 p-3 rounded-lg bg-blue-500/5 border border-blue-500/10">
                      <div className="flex items-center gap-2 text-sm">
                        <Info className="w-4 h-4 text-blue-400" />
                        <span className="text-muted-foreground">
                          Your focus is the bucket with the <span className="text-blue-400 font-medium">highest cost score</span> that's available for your rating band.
                        </span>
                      </div>
                    </div>

                    <div className="space-y-3">
                      {Object.entries(bucketBreakdown.bucket_costs || {})
                        .sort((a, b) => b[1].score - a[1].score)
                        .map(([bucketId, data], i) => {
                          const isSelected = bucketId === primary_focus?.code;
                          const isLocked = !data.allowed_for_rating;
                          const maxScore = Math.max(...Object.values(bucketBreakdown.bucket_costs || {}).map(d => d.score));
                          const barWidth = maxScore > 0 ? (data.score / maxScore) * 100 : 0;

                          return (
                            <div
                              key={bucketId}
                              className={`relative p-3 rounded-lg border transition-colors ${
                                isSelected 
                                  ? 'bg-blue-500/10 border-blue-500/30' 
                                  : isLocked 
                                    ? 'bg-muted/20 border-muted/30 opacity-60' 
                                    : 'bg-muted/30 border-border/50'
                              }`}
                            >
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                                    isSelected ? 'bg-blue-500 text-white' : 'bg-muted text-muted-foreground'
                                  }`}>
                                    {i + 1}
                                  </div>
                                  <span className={`font-medium text-sm ${isSelected ? 'text-blue-400' : ''}`}>
                                    {getBucketLabel(bucketId)}
                                  </span>
                                  {isSelected && (
                                    <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">
                                      Selected
                                    </span>
                                  )}
                                  {isLocked && (
                                    <Lock className="w-3 h-3 text-muted-foreground" />
                                  )}
                                </div>
                                <div className="text-right">
                                  <div className={`font-bold ${isSelected ? 'text-blue-400' : 'text-foreground'}`}>
                                    {Math.round(data.score).toLocaleString()}
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    {data.games_affected} games affected
                                  </div>
                                </div>
                              </div>

                              {/* Score Bar */}
                              <div className="h-2 bg-muted/50 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    isSelected ? 'bg-blue-500' : isLocked ? 'bg-muted-foreground/30' : 'bg-muted-foreground/50'
                                  }`}
                                  style={{ width: `${barWidth}%` }}
                                />
                              </div>

                              {isLocked && (
                                <p className="text-xs text-muted-foreground mt-2">
                                  Locked for {bucketBreakdown.rating_band} players
                                </p>
                              )}
                            </div>
                          );
                        })}
                    </div>

                    <div className="mt-4 pt-4 border-t border-border/50">
                      <p className="text-xs text-muted-foreground">
                        <strong>How it works:</strong> Each bucket's cost score = Σ(EvalDrop × ContextWeight) + FrequencyBonus. 
                        Mistakes when winning cost 40% more. Your rating band ({bucketBreakdown.rating_band}) determines which buckets are available.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </Layout>
  );
};

// Helper function to convert bucket ID to label
const getBucketLabel = (bucketId) => {
  const labels = {
    PIECE_SAFETY: "Piece Safety",
    THREAT_AWARENESS: "Threat Awareness",
    TACTICAL_EXECUTION: "Tactical Execution",
    ADVANTAGE_DISCIPLINE: "Advantage Discipline",
    OPENING_STABILITY: "Opening Stability",
    TIME_DISCIPLINE: "Time Discipline",
    ENDGAME_FUNDAMENTALS: "Endgame Fundamentals",
  };
  return labels[bucketId] || bucketId;
};

export default FocusPage;
