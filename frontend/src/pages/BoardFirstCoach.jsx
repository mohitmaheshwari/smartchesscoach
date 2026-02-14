import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CoachBoard from "@/components/CoachBoard";
import KeyMomentCard from "@/components/KeyMomentCard";
import DrillCard, { HabitCard } from "@/components/DrillCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { 
  Loader2, 
  Target,
  ClipboardCheck,
  BookOpen,
  Dumbbell,
  Brain,
  Trophy,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  Play,
  Flame,
  Lightbulb
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

/**
 * BoardFirstCoach - The "Show Me, Don't Tell Me" Coach Page
 * 
 * Layout:
 * - LEFT: Sticky interactive chessboard (always visible)
 * - RIGHT: Three tabs - Audit, Plan, Openings + Mission
 */
const BoardFirstCoach = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);
  
  // Loading states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Data states
  const [auditData, setAuditData] = useState(null);
  const [planData, setPlanData] = useState(null);
  const [focusData, setFocusData] = useState(null);
  const [keyMoments, setKeyMoments] = useState([]);
  const [drills, setDrills] = useState([]);
  const [openings, setOpenings] = useState(null);
  
  // UI states
  const [activeTab, setActiveTab] = useState("audit");
  const [activeMoment, setActiveMoment] = useState(null);
  const [activeDrill, setActiveDrill] = useState(null);
  const [drillMode, setDrillMode] = useState(false);
  const [completedDrills, setCompletedDrills] = useState(new Set());
  const [openingLineIndex, setOpeningLineIndex] = useState(0);
  const [isPlayingLine, setIsPlayingLine] = useState(false);
  
  // Sync status
  const [syncStatus, setSyncStatus] = useState(null);
  
  // Board state
  const [currentFen, setCurrentFen] = useState(START_FEN);
  const [userColor, setUserColor] = useState("white");

  // Fetch all coaching data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch plan audit, round preparation, and focus data in parallel
        const [auditRes, prepRes, focusRes] = await Promise.all([
          fetch(`${API}/plan-audit`, { credentials: "include" }),
          fetch(`${API}/round-preparation`, { credentials: "include" }),
          fetch(`${API}/focus`, { credentials: "include" })
        ]);
        
        if (auditRes.ok) {
          const data = await auditRes.json();
          setAuditData(data);
          
          // Extract key moments from audit data
          if (data.key_moments) {
            setKeyMoments(data.key_moments);
          } else {
            const moments = deriveKeyMomentsFromAudit(data);
            setKeyMoments(moments);
          }
        }
        
        if (prepRes.ok) {
          const data = await prepRes.json();
          setPlanData(data);
          
          // Extract drills from plan data
          if (data.drills) {
            setDrills(data.drills);
          } else {
            const derivedDrills = deriveDrillsFromPlan(data);
            setDrills(derivedDrills);
          }
          
          // Extract openings
          if (data.opening_recommendation) {
            setOpenings(data.opening_recommendation);
          }
        }
        
        if (focusRes.ok) {
          const data = await focusRes.json();
          setFocusData(data);
        }
        
      } catch (err) {
        console.error("Failed to load coaching data:", err);
        setError("Failed to load coaching data");
        toast.error("Failed to load coaching data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Sync status polling
  useEffect(() => {
    const fetchSyncStatus = async () => {
      try {
        const response = await fetch(`${API}/sync-status`, { credentials: 'include' });
        if (response.ok) {
          const data = await response.json();
          setSyncStatus(data);
        }
      } catch (error) {
        console.error('Error fetching sync status:', error);
      }
    };
    
    fetchSyncStatus();
    const interval = setInterval(fetchSyncStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Derive key moments from audit data
  const deriveKeyMomentsFromAudit = (audit) => {
    if (!audit || !audit.cards) return [];
    
    const moments = [];
    
    for (const card of audit.cards) {
      if (card.audit?.status === 'missed' && card.audit?.evidence?.length > 0) {
        for (const ev of card.audit.evidence.slice(0, 2)) {
          moments.push({
            label: card.domain === 'tactics' ? 'Tactical Miss' : 
                   card.domain === 'middlegame' ? 'Lost Advantage' : 
                   'Key Moment',
            moveNumber: ev.move,
            move: ev.move_san || '',
            evalSwing: ev.delta ? ev.delta * -100 : -150,
            fen: ev.fen || START_FEN,
            category: card.domain === 'tactics' ? 'tactical_miss' : 
                     card.domain === 'middlegame' ? 'advantage_collapse' : 
                     'positional',
            description: card.audit.coach_note || card.goal,
            bestMove: ev.best_move,
            bestMoveExplanation: ev.best_note
          });
        }
      }
    }
    
    if (audit.focus_items) {
      for (const item of audit.focus_items.slice(0, 3)) {
        if (!moments.some(m => m.moveNumber === item.move_number)) {
          moments.push({
            label: item.pattern_name || 'Key Moment',
            moveNumber: item.move_number,
            move: item.move || '',
            evalSwing: item.cp_lost ? -item.cp_lost : -100,
            fen: item.fen || START_FEN,
            category: item.category || 'tactical_miss',
            description: item.goal || item.key_insight,
            bestMove: item.best_move,
            bestMoveExplanation: item.best_explanation
          });
        }
      }
    }
    
    moments.sort((a, b) => a.evalSwing - b.evalSwing);
    return moments.slice(0, 5);
  };

  // Derive drills from plan data
  const deriveDrillsFromPlan = (plan) => {
    if (!plan) return [];
    
    const drills = [];
    
    if (plan.focus_items) {
      for (const item of plan.focus_items.slice(0, 3)) {
        drills.push({
          id: `drill_${item.id || drills.length}`,
          fen: item.fen || START_FEN,
          targetWeakness: item.pattern || 'tactics',
          description: item.goal || 'Find the best move',
          difficulty: item.cp_lost > 200 ? 'hard' : item.cp_lost > 100 ? 'medium' : 'easy',
          correctMoves: item.correct_moves || [],
          gameId: item.game_id,
          moveNumber: item.move_number,
          hint: item.hint
        });
      }
    }
    
    return drills;
  };

  // Handle "View on Board" click for key moments
  const handleViewMoment = useCallback((moment) => {
    setActiveMoment(moment);
    setDrillMode(false);
    setActiveDrill(null);
    
    if (boardRef.current && moment.fen) {
      boardRef.current.jumpToFen(moment.fen, {
        highlight: moment.highlightSquares || []
      });
      setCurrentFen(moment.fen);
    }
  }, []);

  // Handle "Try Again" click for key moments - STAYS ON CURRENT TAB
  const handleTryAgainMoment = useCallback((moment) => {
    setActiveMoment(moment);
    setDrillMode(true);
    setActiveDrill({
      fen: moment.fen,
      correctMoves: moment.bestMove ? [moment.bestMove] : moment.correctMoves || [],
      description: `Find a better move than ${moment.move}`
    });
    
    if (boardRef.current && moment.fen) {
      boardRef.current.jumpToFen(moment.fen);
      boardRef.current.startDrill(moment.bestMove ? [moment.bestMove] : []);
      setCurrentFen(moment.fen);
    }
    // DO NOT change tab - stay on Audit
  }, []);

  // Handle starting a drill from Plan tab - STAYS ON PLAN TAB
  const handleStartDrill = useCallback((drill) => {
    setActiveDrill(drill);
    setDrillMode(true);
    setActiveMoment(null);
    // DO NOT change tab - stay on Plan
    
    if (boardRef.current && drill.fen) {
      boardRef.current.jumpToFen(drill.fen);
      boardRef.current.startDrill(drill.correctMoves || []);
      setCurrentFen(drill.fen);
    }
  }, []);

  // Handle Practice Line - plays the opening moves on the board
  const handlePracticeOpeningLine = useCallback(async () => {
    if (!planData?.opening_recommendation?.line?.length) {
      toast.info("No opening line available yet");
      return;
    }
    
    const moves = planData.opening_recommendation.line;
    setIsPlayingLine(true);
    
    // Reset to starting position first
    if (boardRef.current) {
      boardRef.current.reset();
      
      // Play through the moves with animation
      await boardRef.current.playMoveSequence(moves, 800);
      
      setIsPlayingLine(false);
      toast.success("Now it's your turn! Repeat the line.");
      
      // Start drill mode for user to repeat
      boardRef.current.reset();
      setDrillMode(true);
      setActiveDrill({
        type: 'opening_line',
        moves: moves,
        currentMoveIndex: 0,
        description: "Repeat the opening line you just saw"
      });
    }
  }, [planData]);

  // Handle drill result
  const handleDrillResult = useCallback(({ correct, playedMove }) => {
    if (correct && activeDrill) {
      setCompletedDrills(prev => new Set([...prev, activeDrill.id]));
      toast.success("Excellent! That's the move.");
      
      setTimeout(() => {
        setDrillMode(false);
        setActiveDrill(null);
        if (boardRef.current) {
          boardRef.current.stopDrill();
        }
      }, 1500);
    }
  }, [activeDrill]);

  // Exit drill mode
  const exitDrill = useCallback(() => {
    setDrillMode(false);
    setActiveDrill(null);
    setActiveMoment(null);
    if (boardRef.current) {
      boardRef.current.stopDrill();
      boardRef.current.reset();
    }
  }, []);

  // Format time for sync status
  const formatSyncTime = (seconds) => {
    if (!seconds || seconds <= 0) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Render loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  // Get stats for header
  const gamesAnalyzed = planData?.games_analyzed || auditData?.games_analyzed || focusData?.games_analyzed || 0;
  const needsMoreGames = gamesAnalyzed < 5;
  const mission = focusData?.mission;

  return (
    <Layout user={user}>
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }} 
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-6"
        >
          <div>
            <h1 className="text-2xl font-bold">Coach</h1>
            <p className="text-sm text-muted-foreground">
              Interactive training from your games
            </p>
          </div>
          
          {/* Sync Timer */}
          {syncStatus && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 border border-border/50">
              {syncStatus.is_syncing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 text-primary animate-spin" />
                  <span className="text-xs text-primary font-medium">Syncing...</span>
                </>
              ) : (
                <>
                  <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    Next sync: <span className="font-mono font-medium text-foreground">{formatSyncTime(syncStatus.next_sync_in_seconds)}</span>
                  </span>
                </>
              )}
            </div>
          )}
        </motion.div>

        {needsMoreGames ? (
          /* Not enough games state */
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-md mx-auto"
          >
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-12 text-center">
                <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-medium mb-2">Building Your Profile</h3>
                <p className="text-muted-foreground mb-6">
                  Analyze {5 - gamesAnalyzed} more games to unlock personalized coaching
                </p>
                <Progress value={(gamesAnalyzed / 5) * 100} className="w-48 mx-auto mb-4" />
                <p className="text-sm text-muted-foreground mb-4">
                  {gamesAnalyzed}/5 games analyzed
                </p>
                <Button onClick={() => navigate("/import")}>
                  Import Games
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ) : (
          /* Main Board-First Layout */
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* LEFT PANEL: Sticky Chessboard */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="lg:sticky lg:top-20 lg:self-start"
            >
              <Card className="border-2 border-border/50">
                <CardContent className="p-4">
                  <CoachBoard
                    ref={boardRef}
                    initialFen={currentFen}
                    userColor={userColor}
                    drillMode={drillMode}
                    expectedMoves={activeDrill?.correctMoves || []}
                    onDrillResult={handleDrillResult}
                    showControls={true}
                  />
                  
                  {/* Drill Mode Controls */}
                  {drillMode && (
                    <div className="mt-4 pt-4 border-t border-border/50">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-amber-400">
                          Drill Mode Active
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={exitDrill}
                          className="text-muted-foreground"
                        >
                          <XCircle className="w-4 h-4 mr-1" />
                          Exit
                        </Button>
                      </div>
                      {activeDrill?.description && (
                        <p className="text-sm text-muted-foreground">
                          {activeDrill.description}
                        </p>
                      )}
                    </div>
                  )}
                  
                  {/* Active Moment Info */}
                  {activeMoment && !drillMode && (
                    <div className="mt-4 pt-4 border-t border-border/50">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        <span className="text-sm font-medium">{activeMoment.label}</span>
                        <span className="text-xs text-muted-foreground">Move {activeMoment.moveNumber}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {activeMoment.description}
                      </p>
                      {activeMoment.bestMove && (
                        <div className="mt-2 p-2 bg-emerald-500/10 rounded">
                          <span className="text-xs font-medium text-emerald-400">
                            Better: {activeMoment.bestMove}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
              
              {/* Mission Card - Below Board */}
              {mission && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="mt-4"
                >
                  <Card className={`border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent ${
                    mission.status === 'completed' ? 'border-emerald-500/40 from-emerald-500/5' : ''
                  }`}>
                    <CardContent className="py-4">
                      {/* Mission Header */}
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Target className={`w-4 h-4 ${mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'}`} />
                          <span className={`text-xs font-bold uppercase tracking-wider ${
                            mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'
                          }`}>
                            {mission.status === 'completed' ? 'Mission Complete!' : 'Current Mission'}
                          </span>
                        </div>
                        
                        {/* Streak Counter */}
                        <div className="flex items-center gap-1">
                          <Flame className={`w-4 h-4 ${
                            mission.current_streak > 0 ? 'text-orange-500' : 'text-muted-foreground'
                          }`} />
                          <span className={`text-xl font-bold ${
                            mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'
                          }`}>
                            {mission.current_streak || mission.progress || 0}
                          </span>
                          <span className="text-muted-foreground text-sm">/ {mission.target || 3}</span>
                        </div>
                      </div>
                      
                      {/* Mission Name & Goal */}
                      <h3 className="text-base font-bold mb-1">{mission.name}</h3>
                      <p className="text-sm text-muted-foreground mb-3">{mission.goal}</p>
                      
                      {/* Streak Progress Bar */}
                      {mission.is_streak_based && (
                        <div className="flex items-center gap-1 mb-2">
                          {[...Array(mission.target || 3)].map((_, i) => (
                            <div
                              key={i}
                              className={`h-2 flex-1 rounded-full transition-all ${
                                i < (mission.current_streak || 0)
                                  ? 'bg-amber-500'
                                  : 'bg-muted/50'
                              }`}
                            />
                          ))}
                        </div>
                      )}
                      
                      {/* Streak Status */}
                      {mission.streak_broken_in_last_game && (
                        <div className="flex items-center gap-1.5 text-xs text-orange-400">
                          <XCircle className="w-3 h-3" />
                          <span>Streak reset - last game didn't meet the criteria</span>
                        </div>
                      )}
                      {mission.last_game_passed && mission.status !== 'completed' && (
                        <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Last game counted! Keep it up.</span>
                        </div>
                      )}
                      
                      {/* Longest Streak */}
                      {mission.longest_streak > 0 && (
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs text-muted-foreground">Personal best:</span>
                          <span className="text-xs font-bold text-amber-500 flex items-center gap-1">
                            <Flame className="w-3 h-3" />
                            {mission.longest_streak} game streak
                          </span>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </motion.div>

            {/* RIGHT PANEL: Three Tabs */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
            >
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="w-full grid grid-cols-3 mb-4">
                  <TabsTrigger value="audit" className="gap-1.5" data-testid="tab-audit">
                    <ClipboardCheck className="w-4 h-4" />
                    Audit
                  </TabsTrigger>
                  <TabsTrigger value="plan" className="gap-1.5" data-testid="tab-plan">
                    <Target className="w-4 h-4" />
                    Plan
                  </TabsTrigger>
                  <TabsTrigger value="openings" className="gap-1.5" data-testid="tab-openings">
                    <BookOpen className="w-4 h-4" />
                    Openings
                  </TabsTrigger>
                </TabsList>

                {/* AUDIT TAB: Key Moments from Last Game */}
                <TabsContent value="audit" className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">Key Moments</h3>
                    <span className="text-xs text-muted-foreground">
                      {keyMoments.length} moments from last game
                    </span>
                  </div>
                  
                  {/* Coach Intro */}
                  <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <Lightbulb className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-blue-200/80">
                      These are the critical moments where the game turned. Click <strong>View Position</strong> to see the board, 
                      or <strong>Try Again</strong> to practice finding the right move.
                    </p>
                  </div>
                  
                  {keyMoments.length === 0 ? (
                    <Card className="border-dashed">
                      <CardContent className="py-8 text-center">
                        <Trophy className="w-8 h-8 mx-auto mb-2 text-muted-foreground/50" />
                        <p className="text-sm text-muted-foreground">
                          No critical moments found - well played!
                        </p>
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="space-y-3">
                      {keyMoments.map((moment, i) => (
                        <KeyMomentCard
                          key={`moment-${i}`}
                          moment={moment}
                          onViewOnBoard={handleViewMoment}
                          onTryAgain={handleTryAgainMoment}
                          isActive={activeMoment === moment}
                        />
                      ))}
                    </div>
                  )}
                  
                  {/* Audit Summary */}
                  {auditData?.audit_summary && (
                    <Card className="bg-muted/30 border-border/30">
                      <CardContent className="py-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-xs text-muted-foreground">Last Game</span>
                            <div className="flex items-center gap-2">
                              <span className={`font-bold ${
                                auditData.audit_summary.game_result === 'win' ? 'text-emerald-400' :
                                auditData.audit_summary.game_result === 'loss' ? 'text-red-400' :
                                'text-amber-400'
                              }`}>
                                {auditData.audit_summary.game_result?.toUpperCase() || 'Draw'}
                              </span>
                              <span className="text-sm text-muted-foreground">
                                vs {auditData.audit_summary.opponent_name || 'Opponent'}
                              </span>
                            </div>
                          </div>
                          <div className="text-right">
                            <span className="text-xs text-muted-foreground">Plan Execution</span>
                            <div className="text-lg font-bold">
                              {auditData.audit_summary.score || '0/0'}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </TabsContent>

                {/* PLAN TAB: Next Game Plan */}
                <TabsContent value="plan" className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">Next Game Plan</h3>
                    {planData?.training_block && (
                      <span className="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400">
                        {planData.training_block.name} - L{planData.training_block.intensity}
                      </span>
                    )}
                  </div>

                  {/* Opening Line Section */}
                  <Card className="border-blue-500/30 bg-blue-500/5">
                    <CardContent className="py-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Play className="w-4 h-4 text-blue-400" />
                        <span className="text-sm font-medium text-blue-400">Opening Line</span>
                      </div>
                      
                      <h4 className="font-semibold mb-2">
                        {planData?.opening_recommendation?.as_white || 
                         focusData?.opening_to_play?.white?.name || 
                         "Your Recommended Opening"}
                      </h4>
                      
                      {/* Show the moves if available */}
                      {planData?.opening_recommendation?.line?.length > 0 && (
                        <div className="text-sm font-mono text-muted-foreground mb-3">
                          {planData.opening_recommendation.line.slice(0, 8).map((m, i) => (
                            <span key={i}>
                              {i % 2 === 0 && <span className="text-muted-foreground/50">{Math.floor(i/2) + 1}.</span>}
                              {m}{' '}
                            </span>
                          ))}
                          {planData.opening_recommendation.line.length > 8 && <span>...</span>}
                        </div>
                      )}
                      
                      <Button
                        variant="default"
                        size="sm"
                        className="w-full bg-blue-500 hover:bg-blue-600"
                        onClick={handlePracticeOpeningLine}
                        disabled={isPlayingLine}
                      >
                        {isPlayingLine ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                            Playing...
                          </>
                        ) : (
                          <>
                            <Play className="w-3.5 h-3.5 mr-1.5" />
                            Practice Line on Board
                          </>
                        )}
                      </Button>
                    </CardContent>
                  </Card>

                  {/* Focus Habits (Max 2) */}
                  {planData?.cards && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium text-muted-foreground">Focus Habits</h4>
                      {planData.cards
                        .filter(c => c.priority === 'primary' || c.priority === 'secondary')
                        .slice(0, 2)
                        .map((card, i) => (
                          <HabitCard
                            key={card.domain}
                            habit={{
                              name: card.goal,
                              description: card.rules?.[0] || '',
                              isActive: card.escalation?.is_escalated
                            }}
                            index={i}
                          />
                        ))
                      }
                    </div>
                  )}

                  {/* Practice Drills */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">Practice Drills</h4>
                    {drills.length === 0 ? (
                      <Card className="border-dashed">
                        <CardContent className="py-6 text-center">
                          <Dumbbell className="w-6 h-6 mx-auto mb-2 text-muted-foreground/50" />
                          <p className="text-sm text-muted-foreground">
                            Drills will appear after your next game
                          </p>
                        </CardContent>
                      </Card>
                    ) : (
                      <div className="grid gap-3">
                        {drills.slice(0, 3).map((drill, i) => (
                          <DrillCard
                            key={drill.id}
                            drill={drill}
                            index={i}
                            onStartDrill={handleStartDrill}
                            isCompleted={completedDrills.has(drill.id)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </TabsContent>

                {/* OPENINGS TAB: Your Repertoire */}
                <TabsContent value="openings" className="space-y-4">
                  <h3 className="text-lg font-semibold">Your Repertoire</h3>
                  
                  {/* Coach Intro */}
                  <div className="flex items-start gap-3 p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                    <BookOpen className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-purple-200/80">
                      Based on your games, here are your most successful openings. 
                      Stick to what works until you master it.
                    </p>
                  </div>
                  
                  {/* As White */}
                  <Card>
                    <CardContent className="py-4">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-4 h-4 rounded-full bg-white border border-border" />
                        <span className="font-medium">As White</span>
                      </div>
                      
                      {(openings?.as_white || focusData?.opening_to_play?.white?.name) ? (
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            <span className="text-sm font-medium">
                              {openings?.as_white || focusData?.opening_to_play?.white?.name}
                            </span>
                          </div>
                          {(openings?.as_white_avoid || focusData?.opening_to_avoid?.white) && (
                            <div className="flex items-center gap-2 text-muted-foreground">
                              <XCircle className="w-4 h-4 text-amber-400" />
                              <span className="text-sm">
                                Avoid: {openings?.as_white_avoid || focusData?.opening_to_avoid?.white}
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">Play more games to build your profile</p>
                      )}
                    </CardContent>
                  </Card>

                  {/* As Black */}
                  <Card>
                    <CardContent className="py-4">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-4 h-4 rounded-full bg-slate-800 border border-border" />
                        <span className="font-medium">As Black</span>
                      </div>
                      
                      {(openings?.as_black || focusData?.opening_to_play?.black?.name) ? (
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            <span className="text-sm font-medium">
                              {openings?.as_black || focusData?.opening_to_play?.black?.name}
                            </span>
                          </div>
                          {(openings?.as_black_avoid || focusData?.opening_to_avoid?.black) && (
                            <div className="flex items-center gap-2 text-muted-foreground">
                              <XCircle className="w-4 h-4 text-amber-400" />
                              <span className="text-sm">
                                Avoid: {openings?.as_black_avoid || focusData?.opening_to_avoid?.black}
                              </span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">Play more games to build your profile</p>
                      )}
                    </CardContent>
                  </Card>

                  {/* Win Rate Stats */}
                  {focusData?.opening_stats && (
                    <Card className="bg-muted/30">
                      <CardContent className="py-4">
                        <h4 className="text-sm font-medium mb-3">Your Opening Performance</h4>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">Best as White:</span>
                            <div className="font-medium">
                              {focusData.opening_stats.best_white?.name || 'N/A'}
                              {focusData.opening_stats.best_white?.win_rate && (
                                <span className="text-emerald-400 ml-2">
                                  {Math.round(focusData.opening_stats.best_white.win_rate * 100)}%
                                </span>
                              )}
                            </div>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Best as Black:</span>
                            <div className="font-medium">
                              {focusData.opening_stats.best_black?.name || 'N/A'}
                              {focusData.opening_stats.best_black?.win_rate && (
                                <span className="text-emerald-400 ml-2">
                                  {Math.round(focusData.opening_stats.best_black.win_rate * 100)}%
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </TabsContent>
              </Tabs>
            </motion.div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default BoardFirstCoach;
