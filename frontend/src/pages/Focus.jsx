import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { 
  Loader2, 
  Target,
  AlertTriangle,
  AlertCircle,
  Lightbulb,
  Flame,
  ChevronRight,
  Brain,
  Eye,
  Dumbbell,
  BookOpen,
  CheckCircle2,
  TrendingUp,
  TrendingDown,
  XCircle,
  Shield,
  Crosshair,
  Activity,
  Clock,
  RefreshCw,
  Sword,
  Crown,
  Zap,
  Timer,
  FileText
} from "lucide-react";
import MistakeMastery from "@/components/MistakeMastery";
import EvidenceModal from "@/components/EvidenceModal";
import DrillMode from "@/components/DrillMode";

/**
 * FOCUS PAGE - GM Coach Style Coaching Loop
 * 
 * GOLD FEATURE: Plan → Play → Audit → Adjust
 * 
 * Structure:
 * - ROUND PREPARATION: Plan for next game (5 domains)
 * - PLAN AUDIT: Evaluation of last game against previous plan
 * - RATING KILLER: One dominant weakness
 * - MISSION: Streak-based improvement goal
 * - OPENING GUIDANCE: What to play/avoid
 * 
 * Feels like: "I gave you a plan. I watched your game. You followed/didn't follow. Here's the adjusted plan."
 */

const FocusPage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [focusData, setFocusData] = useState(null);
  const [coachData, setCoachData] = useState(null);
  const [planAudit, setPlanAudit] = useState(null);
  
  // Evidence modal state
  const [showEvidence, setShowEvidence] = useState(false);
  
  // Drill mode state
  const [showDrill, setShowDrill] = useState(false);
  
  // Sync status state
  const [syncStatus, setSyncStatus] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch focus data, coach data, and plan audit
        const [focusRes, coachRes, auditRes] = await Promise.all([
          fetch(`${API}/focus`, { credentials: "include" }),
          fetch(`${API}/coach/today`, { credentials: "include" }),
          fetch(`${API}/plan-audit`, { credentials: "include" })
        ]);
        
        if (focusRes.ok) {
          const data = await focusRes.json();
          setFocusData(data);
        }
        
        if (coachRes.ok) {
          const data = await coachRes.json();
          setCoachData(data);
        }
        
        if (auditRes.ok) {
          const data = await auditRes.json();
          setPlanAudit(data);
        }
      } catch (err) {
        console.error("Failed to load focus data:", err);
        toast.error("Failed to load focus data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Sync status timer
  useEffect(() => {
    const fetchSyncStatus = async () => {
      try {
        const response = await fetch(`${API}/sync-status`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          setSyncStatus(data);
        }
      } catch (error) {
        console.error('Error fetching sync status:', error);
      }
    };
    
    fetchSyncStatus();
    
    const countdownInterval = setInterval(() => {
      setSyncStatus(prev => {
        if (!prev || prev.is_syncing) return prev;
        const newSeconds = Math.max(0, prev.next_sync_in_seconds - 1);
        if (newSeconds === 0) fetchSyncStatus();
        return { ...prev, next_sync_in_seconds: newSeconds };
      });
    }, 1000);
    
    const refetchInterval = setInterval(fetchSyncStatus, 30000);
    
    return () => {
      clearInterval(countdownInterval);
      clearInterval(refetchInterval);
    };
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }

  const gamesAnalyzed = focusData?.games_analyzed || 0;
  const needsMoreGames = gamesAnalyzed < 5;
  
  // Extract evidence for the main focus
  const focusEvidence = focusData?.focus?.evidence || [];
  const focusOccurrences = focusData?.focus?.occurrences || 0;

  // Format seconds to MM:SS
  const formatSyncTime = (seconds) => {
    if (!seconds || seconds <= 0) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }} 
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-3xl font-bold mb-2">Today's Focus</h1>
          <p className="text-muted-foreground">
            One thing to remember in your next game
          </p>
          
          {/* Sync Timer */}
          {syncStatus && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 mt-4 rounded-full bg-muted/50 border border-border/50"
              data-testid="sync-timer"
            >
              {syncStatus.is_syncing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 text-primary animate-spin" />
                  <span className="text-xs text-primary font-medium">Syncing games...</span>
                </>
              ) : (
                <>
                  <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    Next sync: <span className="font-mono font-medium text-foreground">{formatSyncTime(syncStatus.next_sync_in_seconds)}</span>
                  </span>
                </>
              )}
            </motion.div>
          )}
        </motion.div>

        {needsMoreGames ? (
          /* Not enough data state */
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="border-2 border-dashed border-muted-foreground/20">
              <CardContent className="py-12 text-center">
                <Brain className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
                <h3 className="text-lg font-medium mb-2">Building Your Profile</h3>
                <p className="text-muted-foreground mb-6">
                  Analyze {5 - gamesAnalyzed} more games to unlock personalized coaching
                </p>
                <Progress value={(gamesAnalyzed / 5) * 100} className="w-48 mx-auto mb-4" />
                <p className="text-sm text-muted-foreground">
                  {gamesAnalyzed}/5 games analyzed
                </p>
                <Button 
                  className="mt-6" 
                  onClick={() => navigate("/import")}
                >
                  Import Games
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ) : showDrill ? (
          /* DRILL MODE */
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <DrillMode
              pattern={focusData?.focus?.pattern}
              patternLabel={focusData?.focus?.label || "this pattern"}
              onComplete={() => setShowDrill(false)}
              onClose={() => setShowDrill(false)}
            />
          </motion.div>
        ) : (
          <>
            {/* PLAN AUDIT - Phase-Based Execution Evaluation */}
            {planAudit?.has_data && planAudit?.audits?.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 }}
                data-testid="plan-audit"
              >
                <Card className="border-2 border-slate-500/30 bg-gradient-to-br from-slate-500/5 to-zinc-500/5">
                  <CardContent className="py-5">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Target className="w-4 h-4 text-slate-400" />
                          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                            Plan Audit – Last Game
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          vs {planAudit.opponent} · {planAudit.result?.toUpperCase()} · {planAudit.accuracy}% accuracy
                        </p>
                      </div>
                      
                      {/* Execution Score */}
                      <div className="text-right">
                        <span className={`text-2xl font-bold ${
                          planAudit.summary?.executed === planAudit.summary?.domains_shown ? 'text-emerald-500' :
                          planAudit.summary?.failed > 0 ? 'text-orange-500' :
                          'text-amber-500'
                        }`}>
                          {planAudit.summary?.executed || 0}/{planAudit.summary?.domains_shown || 0}
                        </span>
                        <p className="text-xs text-muted-foreground">domains executed</p>
                      </div>
                    </div>
                    
                    {/* Domain Audits */}
                    <div className="space-y-3">
                      {planAudit.audits.map((audit, idx) => (
                        <div 
                          key={audit.domain}
                          className={`p-3 rounded-lg border ${
                            audit.verdict_type === 'pass' 
                              ? 'bg-emerald-500/5 border-emerald-500/20' 
                              : audit.verdict_type === 'fail'
                              ? 'bg-orange-500/5 border-orange-500/20'
                              : 'bg-amber-500/5 border-amber-500/20'
                          }`}
                          data-testid={`audit-${audit.domain.toLowerCase()}`}
                        >
                          {/* Domain Header */}
                          <div className="flex items-center justify-between mb-2">
                            <span className={`text-xs font-bold uppercase tracking-wider ${
                              audit.verdict_type === 'pass' ? 'text-emerald-500' :
                              audit.verdict_type === 'fail' ? 'text-orange-500' :
                              'text-amber-500'
                            }`}>
                              {audit.domain}
                            </span>
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                              audit.verdict_type === 'pass' 
                                ? 'bg-emerald-500/20 text-emerald-400' 
                                : audit.verdict_type === 'fail'
                                ? 'bg-orange-500/20 text-orange-400'
                                : 'bg-amber-500/20 text-amber-400'
                            }`}>
                              {audit.verdict_type === 'pass' ? '✓' : audit.verdict_type === 'fail' ? '✗' : '~'}
                            </span>
                          </div>
                          
                          {/* Plan (if existed) */}
                          {audit.plan && (
                            <p className="text-xs text-muted-foreground mb-1.5">
                              <span className="font-medium">Plan:</span> {audit.plan}
                            </p>
                          )}
                          
                          {/* What Happened */}
                          <div className="space-y-0.5 mb-2">
                            {audit.what_happened?.map((item, i) => (
                              <p key={i} className="text-xs text-foreground/80">
                                • {item}
                              </p>
                            ))}
                          </div>
                          
                          {/* Data Snapshot */}
                          <div className="flex flex-wrap gap-2 mb-2">
                            {audit.data?.opening_accuracy && (
                              <span className="text-xs bg-background/50 px-1.5 py-0.5 rounded">
                                Accuracy: {audit.data.opening_accuracy}%
                              </span>
                            )}
                            {audit.data?.early_eval_stability && (
                              <span className="text-xs bg-background/50 px-1.5 py-0.5 rounded">
                                Stability: {audit.data.early_eval_stability}
                              </span>
                            )}
                            {audit.data?.max_advantage && (
                              <span className="text-xs bg-background/50 px-1.5 py-0.5 rounded">
                                Peak: {audit.data.max_advantage}
                              </span>
                            )}
                            {audit.data?.eval_swing && (
                              <span className="text-xs bg-background/50 px-1.5 py-0.5 rounded">
                                Swing: {audit.data.eval_swing}
                              </span>
                            )}
                            {audit.data?.blunders !== undefined && (
                              <span className="text-xs bg-background/50 px-1.5 py-0.5 rounded">
                                Blunders: {audit.data.blunders}
                              </span>
                            )}
                            {audit.data?.worst_drop && (
                              <span className="text-xs bg-background/50 px-1.5 py-0.5 rounded">
                                Worst: {audit.data.worst_drop}
                              </span>
                            )}
                            {audit.data?.conversion && (
                              <span className="text-xs bg-background/50 px-1.5 py-0.5 rounded">
                                Converted: {audit.data.conversion}
                              </span>
                            )}
                          </div>
                          
                          {/* Verdict */}
                          <p className={`text-xs font-semibold ${
                            audit.verdict_type === 'pass' ? 'text-emerald-400' :
                            audit.verdict_type === 'fail' ? 'text-orange-400' :
                            'text-amber-400'
                          }`}>
                            {audit.verdict}
                          </p>
                        </div>
                      ))}
                    </div>
                    
                    {/* Summary Footer */}
                    <div className="mt-4 pt-3 border-t border-border/30">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {/* Quick Score Icons */}
                          {planAudit.audits.map((audit) => (
                            <span 
                              key={audit.domain}
                              className={`text-xs font-medium ${
                                audit.verdict_type === 'pass' ? 'text-emerald-400' :
                                audit.verdict_type === 'fail' ? 'text-orange-400' :
                                'text-amber-400'
                              }`}
                              title={audit.domain}
                            >
                              {audit.domain.charAt(0)} {audit.verdict_type === 'pass' ? '✓' : audit.verdict_type === 'fail' ? '✗' : '~'}
                            </span>
                          ))}
                        </div>
                        
                        {/* Training Focus */}
                        {planAudit.summary?.training_focus && (
                          <span className="text-xs text-muted-foreground">
                            Focus: <span className="text-foreground font-medium">{planAudit.summary.training_focus}</span>
                          </span>
                        )}
                      </div>
                      
                      {/* View Game Link */}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="mt-2 text-slate-400 hover:text-slate-300 p-0 h-auto text-xs"
                        onClick={() => navigate(`/game/${planAudit.game_id}`)}
                        data-testid="audit-view-game"
                      >
                        <Eye className="w-3 h-3 mr-1" />
                        Full analysis
                        <ChevronRight className="w-3 h-3 ml-0.5" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* RATING KILLER - Only show when relevant */}
            {focusData?.focus?.pattern && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <Card 
                className="border-2 border-red-500/30 bg-gradient-to-br from-red-500/5 to-orange-500/5 cursor-pointer hover:border-red-500/50 transition-colors"
                onClick={() => focusEvidence.length > 0 && setShowEvidence(true)}
                data-testid="rating-killer-card"
              >
                <CardContent className="py-8">
                  <div className="flex items-start gap-4">
                    <div className="p-3 rounded-full bg-red-500/10">
                      <Flame className="w-8 h-8 text-red-500" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-red-500">
                          #1 Rating Killer
                        </span>
                        {focusOccurrences > 0 && (
                          <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            See {focusOccurrences} times this happened
                          </span>
                        )}
                      </div>
                      <h2 className="text-xl font-bold mb-3">
                        {focusData?.focus?.main_message || "Loading..."}
                      </h2>
                      {focusData?.focus?.impact && (
                        <p className="text-sm text-muted-foreground mb-4">
                          Cost you {focusData.focus.impact} in recent games
                        </p>
                      )}
                      
                      {/* The FIX */}
                      <div className="p-4 rounded-lg bg-background/50 border border-border/50 mb-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Lightbulb className="w-4 h-4 text-yellow-500" />
                          <span className="text-sm font-semibold">Before your next move:</span>
                        </div>
                        <p className="text-base">
                          {focusData?.focus?.fix || "Focus on piece safety."}
                        </p>
                      </div>
                      
                      {/* ACTION BUTTONS */}
                      {focusData?.focus?.pattern && (
                        <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="gap-1"
                            onClick={() => setShowEvidence(true)}
                            disabled={focusEvidence.length === 0}
                            data-testid="see-examples-btn"
                          >
                            <Eye className="w-4 h-4" />
                            See Examples
                          </Button>
                          <Button 
                            size="sm" 
                            className="gap-1 bg-red-500 hover:bg-red-600"
                            onClick={() => setShowDrill(true)}
                            data-testid="train-pattern-btn"
                          >
                            <Dumbbell className="w-4 h-4" />
                            Train This
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
            )}

            {/* MISSION - STREAK-BASED */}
            {focusData?.mission && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <Card className={`border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent ${
                  focusData.mission.status === 'completed' ? 'border-emerald-500/40 from-emerald-500/5' : ''
                }`}>
                  <CardContent className="py-5">
                    {/* Header with Rating Tier */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Target className={`w-4 h-4 ${focusData.mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'}`} />
                        <span className={`text-xs font-bold uppercase tracking-wider ${
                          focusData.mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'
                        }`}>
                          {focusData.mission.status === 'completed' ? 'Mission Complete!' : 'Current Mission'}
                        </span>
                      </div>
                      {focusData.mission.rating_tier && focusData.mission.rating_tier !== 'starter' && (
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          focusData.mission.rating_tier === 'beginner' ? 'bg-green-500/20 text-green-400' :
                          focusData.mission.rating_tier === 'intermediate' ? 'bg-yellow-500/20 text-yellow-400' :
                          focusData.mission.rating_tier === 'advanced' ? 'bg-blue-500/20 text-blue-400' :
                          'bg-purple-500/20 text-purple-400'
                        }`}>
                          {focusData.mission.rating_tier === 'beginner' ? '600-1000' :
                           focusData.mission.rating_tier === 'intermediate' ? '1000-1600' :
                           focusData.mission.rating_tier === 'advanced' ? '1600-2000' : '2000+'}
                        </span>
                      )}
                    </div>
                    
                    {/* Mission Name & Streak Progress */}
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-lg font-bold">{focusData.mission.name}</h3>
                      <div className="flex items-center gap-3">
                        {/* Current Streak */}
                        <div className="flex items-center gap-1">
                          <Flame className={`w-4 h-4 ${
                            focusData.mission.current_streak > 0 ? 'text-orange-500' : 'text-muted-foreground'
                          }`} />
                          <span className={`text-2xl font-bold ${
                            focusData.mission.status === 'completed' ? 'text-emerald-500' : 'text-amber-500'
                          }`}>
                            {focusData.mission.current_streak || focusData.mission.progress || 0}
                          </span>
                          <span className="text-muted-foreground text-sm">/ {focusData.mission.target || 3}</span>
                        </div>
                      </div>
                    </div>
                    
                    {/* Goal */}
                    <p className="text-sm font-medium mb-3">
                      {focusData.mission.goal}
                    </p>
                    
                    {/* Streak Indicator - Visual representation */}
                    {focusData.mission.is_streak_based && (
                      <div className="mb-4">
                        <div className="flex items-center gap-1 mb-2">
                          {[...Array(focusData.mission.target || 3)].map((_, i) => (
                            <div
                              key={i}
                              className={`h-2 flex-1 rounded-full transition-all ${
                                i < (focusData.mission.current_streak || 0)
                                  ? 'bg-amber-500'
                                  : 'bg-muted/50'
                              }`}
                            />
                          ))}
                        </div>
                        
                        {/* Streak Status Message */}
                        {focusData.mission.streak_broken_in_last_game && (
                          <div className="flex items-center gap-1.5 text-xs text-orange-400">
                            <XCircle className="w-3 h-3" />
                            <span>Streak reset - last game didn't meet the criteria</span>
                          </div>
                        )}
                        {focusData.mission.last_game_passed && focusData.mission.status !== 'completed' && (
                          <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Last game counted! Keep it up.</span>
                          </div>
                        )}
                        
                        {/* Longest Streak Badge */}
                        {focusData.mission.longest_streak > 0 && (
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-xs text-muted-foreground">
                              Personal best:
                            </span>
                            <span className="text-xs font-bold text-amber-500 flex items-center gap-1">
                              <Flame className="w-3 h-3" />
                              {focusData.mission.longest_streak} game streak
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* Progress Bar - Fallback for non-streak missions */}
                    {!focusData.mission.is_streak_based && (
                      <Progress 
                        value={((focusData.mission.progress || 0) / (focusData.mission.target || 3)) * 100} 
                        className="h-1.5 mb-4"
                      />
                    )}
                    
                    {/* Instruction Box */}
                    {focusData.mission.instruction && focusData.mission.status !== 'completed' && (
                      <div className="bg-muted/50 rounded-lg p-3 border border-border/50 mb-3">
                        <p className="text-xs uppercase font-semibold text-muted-foreground mb-1">How to do it</p>
                        <p className="text-sm">{focusData.mission.instruction}</p>
                      </div>
                    )}
                    
                    {/* Completed State - Next Mission Button */}
                    {focusData.mission.status === 'completed' && (
                      <div className="pt-3 border-t border-border/30">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                            <span className="text-sm font-medium text-emerald-400">
                              Mission accomplished! Great discipline.
                            </span>
                          </div>
                          <Button
                            size="sm"
                            className="gap-1.5 bg-amber-500 hover:bg-amber-600"
                            onClick={async () => {
                              try {
                                const response = await fetch(`${API}/focus/next-mission`, {
                                  method: 'POST',
                                  credentials: 'include'
                                });
                                if (response.ok) {
                                  window.location.reload();
                                }
                              } catch (err) {
                                console.error('Failed to get next mission:', err);
                              }
                            }}
                            data-testid="next-mission-btn"
                          >
                            <ChevronRight className="w-4 h-4" />
                            Next Mission
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* OPENING GUIDANCE - Direction, not labels */}
            {focusData?.opening_guidance?.ready && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <Card className="border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-indigo-500/5">
                  <CardContent className="py-5">
                    <div className="flex items-center gap-2 mb-4">
                      <BookOpen className="w-4 h-4 text-blue-500" />
                      <span className="text-xs font-bold uppercase tracking-wider text-blue-500">
                        Opening Guidance
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* As White */}
                      <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2">As White</p>
                        
                        {focusData.opening_guidance.as_white.working_well.length > 0 && (
                          <div className="mb-3">
                            <div className="flex items-center gap-1.5 mb-1">
                              <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                              <span className="text-xs font-medium text-emerald-500">Working Well</span>
                            </div>
                            {focusData.opening_guidance.as_white.working_well.map((op, i) => (
                              <div key={i} className="ml-4 mb-1.5">
                                <p className="text-sm font-medium">{op.name}</p>
                                <p className="text-xs text-muted-foreground">{op.reason}</p>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {focusData.opening_guidance.as_white.pause_for_now.length > 0 && (
                          <div>
                            <div className="flex items-center gap-1.5 mb-1">
                              <AlertCircle className="w-3 h-3 text-amber-500" />
                              <span className="text-xs font-medium text-amber-500">Pause For Now</span>
                            </div>
                            {focusData.opening_guidance.as_white.pause_for_now.map((op, i) => (
                              <div key={i} className="ml-4 mb-1.5">
                                <p className="text-sm font-medium">{op.name}</p>
                                <p className="text-xs text-muted-foreground">{op.reason}</p>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {focusData.opening_guidance.as_white.working_well.length === 0 && 
                         focusData.opening_guidance.as_white.pause_for_now.length === 0 && (
                          <p className="text-xs text-muted-foreground ml-4">More data needed</p>
                        )}
                      </div>
                      
                      {/* As Black */}
                      <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2">As Black</p>
                        
                        {focusData.opening_guidance.as_black.working_well.length > 0 && (
                          <div className="mb-3">
                            <div className="flex items-center gap-1.5 mb-1">
                              <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                              <span className="text-xs font-medium text-emerald-500">Working Well</span>
                            </div>
                            {focusData.opening_guidance.as_black.working_well.map((op, i) => (
                              <div key={i} className="ml-4 mb-1.5">
                                <p className="text-sm font-medium">{op.name}</p>
                                <p className="text-xs text-muted-foreground">{op.reason}</p>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {focusData.opening_guidance.as_black.pause_for_now.length > 0 && (
                          <div>
                            <div className="flex items-center gap-1.5 mb-1">
                              <AlertCircle className="w-3 h-3 text-amber-500" />
                              <span className="text-xs font-medium text-amber-500">Pause For Now</span>
                            </div>
                            {focusData.opening_guidance.as_black.pause_for_now.map((op, i) => (
                              <div key={i} className="ml-4 mb-1.5">
                                <p className="text-sm font-medium">{op.name}</p>
                                <p className="text-xs text-muted-foreground">{op.reason}</p>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {focusData.opening_guidance.as_black.working_well.length === 0 && 
                         focusData.opening_guidance.as_black.pause_for_now.length === 0 && (
                          <p className="text-xs text-muted-foreground ml-4">More data needed</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* RATING IMPACT - Motivational */}
            {focusData?.rating_impact?.potential_gain > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                <Card className="border-green-500/20 bg-gradient-to-br from-green-500/5 to-emerald-500/5">
                  <CardContent className="py-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-full bg-green-500/10">
                          <AlertTriangle className="w-5 h-5 text-green-500" />
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground">Potential Rating Gain</span>
                          <p className="text-sm">{focusData.rating_impact.message}</p>
                        </div>
                      </div>
                      <span className="text-2xl font-bold text-green-500">
                        +{focusData.rating_impact.potential_gain}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {/* PRACTICE PUZZLE - ONE interactive element */}
            {coachData?.mistake_mastery && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
              >
                <MistakeMastery 
                  data={coachData.mistake_mastery}
                  compact={true}
                />
              </motion.div>
            )}

            {/* CTA to see full analysis */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="text-center pt-4"
            >
              <Button 
                variant="outline" 
                onClick={() => navigate("/progress")}
                className="group"
              >
                View Full Journey
                <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
              </Button>
            </motion.div>
          </>
        )}
      </div>
      
      {/* Evidence Modal */}
      <EvidenceModal
        isOpen={showEvidence}
        onClose={() => setShowEvidence(false)}
        title={focusData?.focus?.label || "Rating Killer"}
        subtitle={focusData?.focus?.main_message}
        evidence={focusEvidence}
        type="pattern"
      />
    </Layout>
  );
};

export default FocusPage;
