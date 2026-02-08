import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress as ProgressBar } from "@/components/ui/progress";
import { 
  Loader2, 
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Zap,
  Clock,
  CheckCircle2,
  RefreshCw,
  AlertCircle,
  Trophy,
  BookOpen,
  Swords,
  Crown,
  ArrowRight,
  Sparkles,
  Calendar,
  BarChart3,
  Brain
} from "lucide-react";

// Trend indicator component
const TrendIndicator = ({ trend, size = "sm" }) => {
  const sizeClasses = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";
  
  if (trend === "improving") {
    return (
      <span className={`inline-flex items-center gap-1 text-emerald-500 bg-emerald-500/10 rounded ${sizeClasses}`}>
        <TrendingUp className="w-3 h-3" /> Improving
      </span>
    );
  }
  if (trend === "declining") {
    return (
      <span className={`inline-flex items-center gap-1 text-amber-500 bg-amber-500/10 rounded ${sizeClasses}`}>
        <TrendingDown className="w-3 h-3" /> Needs Attention
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1 text-muted-foreground bg-muted rounded ${sizeClasses}`}>
      <Minus className="w-3 h-3" /> Stable
    </span>
  );
};

// Phase mastery bar component - renamed to Game Discipline
const PhaseMasteryBar = ({ phase, data }) => {
  const phaseIcons = {
    opening: BookOpen,
    middlegame: Swords,
    endgame: Crown
  };
  const Icon = phaseIcons[phase] || BookOpen;
  const displayName = phase.charAt(0).toUpperCase() + phase.slice(1);
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-muted-foreground" />
          <span className="font-medium">{displayName}</span>
        </div>
        <div className="flex items-center gap-2">
          <TrendIndicator trend={data.trend} />
        </div>
      </div>
      <ProgressBar value={data.mastery_pct} className="h-2" />
      <p className="text-xs text-muted-foreground">
        {data.blunders_per_game > 1 ? `${data.blunders_per_game} discipline breaks/game` : 
         data.blunders_per_game > 0 ? "Occasional slip" : "Discipline holding"} • {data.games_analyzed} games
      </p>
    </div>
  );
};

// Metric comparison component (then vs now) - SIMPLIFIED
const MetricComparison = ({ label, then, now, improved }) => {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border/50 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground line-through">{then}</span>
        <ArrowRight className="w-4 h-4 text-muted-foreground" />
        <span className="font-mono font-medium">{now}</span>
        <TrendIndicator trend={improved ? "improving" : "declining"} />
      </div>
    </div>
  );
};

// Opening row component
const OpeningRow = ({ opening }) => {
  const winRateColor = opening.win_rate >= 60 ? 'text-emerald-500' : 
                       opening.win_rate >= 45 ? 'text-yellow-500' : 'text-red-500';
  
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex-1">
        <p className="font-medium text-sm">{opening.name}</p>
        <p className="text-xs text-muted-foreground">
          {opening.games} games • {opening.wins}W-{opening.losses}L-{opening.draws}D
        </p>
      </div>
      <div className="flex items-center gap-2">
        <ProgressBar value={opening.win_rate} className="w-20 h-2" />
        <span className={`font-mono text-sm ${winRateColor}`}>{opening.win_rate}%</span>
      </div>
    </div>
  );
};

// Habit item component
const HabitItem = ({ habit, status }) => {
  const statusColors = {
    conquered: "bg-emerald-500/10 border-emerald-500/30 text-emerald-500",
    in_progress: "bg-blue-500/10 border-blue-500/30 text-blue-500",
    needs_attention: "bg-amber-500/10 border-amber-500/30 text-amber-500"
  };
  
  return (
    <div className={`p-3 rounded-lg border ${statusColors[status]}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium text-sm">{habit.display_name}</span>
        {status === "in_progress" && (
          <span className="text-xs">{habit.mastery_pct}% corrected</span>
        )}
        {status === "needs_attention" && habit.recent_occurrences > 0 && (
          <span className="text-xs">Still leaking rating</span>
        )}
      </div>
      {status === "in_progress" && (
        <ProgressBar value={habit.mastery_pct} className="h-1.5" />
      )}
      {status === "conquered" && (
        <p className="text-xs opacity-75">Fixed — no longer a rating leak</p>
      )}
    </div>
  );
};

const ChessJourney = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [journey, setJourney] = useState(null);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    fetchJourney();
  }, []);

  const fetchJourney = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/journey/comprehensive`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setJourney(data);
      }
    } catch (e) {
      console.error("Failed to fetch journey:", e);
    } finally {
      setLoading(false);
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      await fetch(`${API}/journey/sync-now`, {
        method: "POST",
        credentials: "include"
      });
      setTimeout(fetchJourney, 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  // Destructure journey data
  const {
    member_since,
    total_games_analyzed = 0,
    rating_progression = {},
    phase_mastery = {},
    improvement_metrics = {},
    habit_journey = {},
    opening_repertoire = {},
    weekly_summary = {},
    insights = []
  } = journey || {};

  // Format member since date
  const memberSinceDate = member_since ? new Date(member_since).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }) : 'Recently';

  const daysSinceJoined = member_since ? 
    Math.floor((Date.now() - new Date(member_since).getTime()) / (1000 * 60 * 60 * 24)) : 0;

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto space-y-6 pb-12">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/coach")}>
              <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </Button>
          </div>
          <Button variant="outline" size="sm" onClick={syncNow} disabled={syncing}>
            <RefreshCw className={`w-4 h-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing...' : 'Sync Games'}
          </Button>
        </div>

        {/* Journey Title Card */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="bg-gradient-to-br from-primary/10 via-background to-background border-primary/20">
            <CardContent className="pt-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="w-14 h-14 rounded-full bg-primary/20 flex items-center justify-center">
                  <Trophy className="w-7 h-7 text-primary" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold">Your Chess Journey</h1>
                  <p className="text-muted-foreground">
                    Member since {memberSinceDate} ({daysSinceJoined} days) • {total_games_analyzed} games analyzed
                  </p>
                </div>
              </div>
              
              {/* Quick Stats */}
              {weekly_summary.games_this_week > 0 && (
                <div className="p-3 rounded-lg bg-muted/50 mt-4">
                  <p className="text-sm">{weekly_summary.message}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Rating Progression */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-primary" />
                  Rating Progression
                </CardTitle>
                <TrendIndicator trend={rating_progression.trend} size="md" />
              </div>
            </CardHeader>
            <CardContent>
              {/* Rating Stats */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center p-3 rounded-lg bg-muted/50">
                  <p className="text-2xl font-bold">{rating_progression.started_at || '—'}</p>
                  <p className="text-xs text-muted-foreground">Started</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-primary/10 border border-primary/20">
                  <p className="text-2xl font-bold text-primary">{rating_progression.current || '—'}</p>
                  <p className="text-xs text-muted-foreground">Current</p>
                </div>
                <div className="text-center p-3 rounded-lg bg-muted/50">
                  <p className="text-2xl font-bold">{rating_progression.peak || '—'}</p>
                  <p className="text-xs text-muted-foreground">Peak</p>
                </div>
              </div>
              
              {/* Change indicator */}
              {rating_progression.change !== undefined && (
                <div className="text-center">
                  <span className={`text-lg font-medium ${rating_progression.change >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                    {rating_progression.change >= 0 ? '+' : ''}{rating_progression.change} points
                  </span>
                  <span className="text-muted-foreground ml-2">since you joined</span>
                </div>
              )}
              
              {/* Mini chart placeholder - could add sparkline here */}
              {rating_progression.history && rating_progression.history.length > 0 && (
                <div className="mt-4 p-3 rounded bg-muted/30">
                  <p className="text-xs text-muted-foreground mb-2">Rating History</p>
                  <div className="flex items-end gap-1 h-12">
                    {rating_progression.history.map((point, i) => {
                      const maxRating = Math.max(...rating_progression.history.map(p => p.rating || 0));
                      const minRating = Math.min(...rating_progression.history.map(p => p.rating || 0));
                      const range = maxRating - minRating || 1;
                      const height = ((point.rating - minRating) / range) * 100;
                      return (
                        <div 
                          key={i}
                          className="flex-1 bg-primary/60 rounded-t"
                          style={{ height: `${Math.max(height, 10)}%` }}
                          title={`${point.week}: ${point.rating}`}
                        />
                      );
                    })}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Phase Mastery - Renamed to Game Discipline */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Target className="w-5 h-5 text-primary" />
                Game Discipline
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {phase_mastery.opening && (
                <PhaseMasteryBar phase="opening" data={phase_mastery.opening} />
              )}
              {phase_mastery.middlegame && (
                <PhaseMasteryBar phase="middlegame" data={phase_mastery.middlegame} />
              )}
              {phase_mastery.endgame && (
                <PhaseMasteryBar phase="endgame" data={phase_mastery.endgame} />
              )}
              
              {!phase_mastery.opening && !phase_mastery.middlegame && !phase_mastery.endgame && (
                <p className="text-center text-muted-foreground py-4">
                  Analyze more games to see phase mastery breakdown
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Improvement Metrics - Then vs Now */}
        {improvement_metrics.has_data && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  Then vs Now
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  What used to go wrong vs What is improving now
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  <MetricComparison 
                    label="Accuracy"
                    then={`${improvement_metrics.accuracy?.then || 0}%`}
                    now={`${improvement_metrics.accuracy?.now || 0}%`}
                    improved={improvement_metrics.accuracy?.improved}
                  />
                  <MetricComparison 
                    label="Blunders/Game"
                    then={improvement_metrics.blunders_per_game?.then || 0}
                    now={improvement_metrics.blunders_per_game?.now || 0}
                    improved={improvement_metrics.blunders_per_game?.improved}
                  />
                  <MetricComparison 
                    label="Mistakes/Game"
                    then={improvement_metrics.mistakes_per_game?.then || 0}
                    now={improvement_metrics.mistakes_per_game?.now || 0}
                    improved={improvement_metrics.mistakes_per_game?.improved}
                  />
                  <MetricComparison 
                    label="Best Moves/Game"
                    then={improvement_metrics.best_moves_per_game?.then || 0}
                    now={improvement_metrics.best_moves_per_game?.now || 0}
                    improved={improvement_metrics.best_moves_per_game?.improved}
                  />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Habit Journey */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                Habit Journey
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {habit_journey.total_mastered || 0} of {habit_journey.total_cards || 0} positions mastered
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              
              {/* Conquered Habits */}
              {habit_journey.conquered && habit_journey.conquered.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-emerald-500 mb-2 flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Conquered
                  </p>
                  <div className="grid gap-2">
                    {habit_journey.conquered.map((habit, i) => (
                      <HabitItem key={i} habit={habit} status="conquered" />
                    ))}
                  </div>
                </div>
              )}
              
              {/* In Progress */}
              {habit_journey.in_progress && habit_journey.in_progress.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-blue-500 mb-2 flex items-center gap-1">
                    <RefreshCw className="w-4 h-4" /> In Progress
                  </p>
                  <div className="grid gap-2">
                    {habit_journey.in_progress.map((habit, i) => (
                      <HabitItem key={i} habit={habit} status="in_progress" />
                    ))}
                  </div>
                </div>
              )}
              
              {/* Needs Attention */}
              {habit_journey.needs_attention && habit_journey.needs_attention.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-amber-500 mb-2 flex items-center gap-1">
                    <AlertCircle className="w-4 h-4" /> Needs Attention
                  </p>
                  <div className="grid gap-2">
                    {habit_journey.needs_attention.map((habit, i) => (
                      <HabitItem key={i} habit={habit} status="needs_attention" />
                    ))}
                  </div>
                </div>
              )}
              
              {(!habit_journey.conquered?.length && !habit_journey.in_progress?.length && !habit_journey.needs_attention?.length) && (
                <p className="text-center text-muted-foreground py-4">
                  Complete more training sessions to track habit progress
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Opening Repertoire */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-primary" />
                Opening Repertoire
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-6">
                {/* As White */}
                <div>
                  <p className="font-medium mb-2 flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-white border border-border" />
                    As White ({opening_repertoire.as_white?.total_games || 0} games)
                  </p>
                  {opening_repertoire.as_white?.openings?.length > 0 ? (
                    <div className="space-y-1">
                      {opening_repertoire.as_white.openings.map((opening, i) => (
                        <OpeningRow key={i} opening={opening} />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No data yet</p>
                  )}
                </div>
                
                {/* As Black */}
                <div>
                  <p className="font-medium mb-2 flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-zinc-800 border border-border" />
                    As Black ({opening_repertoire.as_black?.total_games || 0} games)
                  </p>
                  {opening_repertoire.as_black?.openings?.length > 0 ? (
                    <div className="space-y-1">
                      {opening_repertoire.as_black.openings.map((opening, i) => (
                        <OpeningRow key={i} opening={opening} />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No data yet</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Insights */}
        {insights && insights.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Zap className="w-5 h-5 text-primary" />
                  Insights
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {insights.map((insight, i) => (
                  <div 
                    key={i}
                    className={`p-3 rounded-lg border ${
                      insight.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/30' :
                      insight.type === 'warning' ? 'bg-amber-500/10 border-amber-500/30' :
                      'bg-muted/50 border-border'
                    }`}
                  >
                    <p className="font-medium text-sm">{insight.title}</p>
                    <p className="text-sm text-muted-foreground">{insight.message}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </motion.div>
        )}

      </div>
    </Layout>
  );
};

export default ChessJourney;
