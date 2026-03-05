/**
 * PROGRESS PAGE - Human Coach Style
 * 
 * Not a dashboard. A coaching session.
 * Shows your journey with celebration, trends, and specific examples.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress as ProgressBar } from "@/components/ui/progress";
import { 
  Loader2, 
  TrendingUp,
  TrendingDown,
  Target,
  Zap,
  CheckCircle2,
  RefreshCw,
  Flame,
  Trophy,
  ArrowRight,
  Sparkles,
  Brain,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Eye
} from "lucide-react";

const Progress = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [homeData, setHomeData] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [expandedSection, setExpandedSection] = useState(null);

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [progressRes, homeRes] = await Promise.all([
        fetch(`${API}/progress`, { credentials: "include" }),
        fetch(`${API}/coach/home-intelligence`, { credentials: "include" })
      ]);
      if (progressRes.ok) setData(await progressRes.json());
      if (homeRes.ok) setHomeData(await homeRes.json());
    } catch (e) {
      console.error("Failed to fetch:", e);
    } finally {
      setLoading(false);
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      await fetch(`${API}/journey/sync-now`, { method: "POST", credentials: "include" });
      setTimeout(fetchAll, 3000);
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

  const patterns = homeData?.specific_patterns;
  const dominantPattern = patterns?.dominant_pattern;
  const patternCount = patterns?.pattern_count || 0;
  const accuracy = data?.accuracy || {};
  const habits = data?.habits || [];
  const gamesAnalyzed = data?.valid_analysis_count || 0;

  // Calculate improvement percentage
  const accuracyImproved = accuracy.current > accuracy.previous;
  const accuracyDelta = accuracy.current - (accuracy.previous || accuracy.current);

  // Get greeting based on performance
  const getCoachGreeting = () => {
    if (accuracyDelta >= 5) return { text: "You're on fire!", icon: Flame, color: "text-orange-500" };
    if (accuracyDelta >= 2) return { text: "Nice progress this week", icon: TrendingUp, color: "text-emerald-500" };
    if (accuracyDelta <= -3) return { text: "Let's get back on track", icon: Target, color: "text-amber-500" };
    return { text: "Steady progress", icon: Sparkles, color: "text-primary" };
  };

  const greeting = getCoachGreeting();
  const GreetingIcon = greeting.icon;

  return (
    <Layout user={user}>
      <div className="max-w-2xl mx-auto space-y-6" data-testid="progress-page">
        
        {/* Coach Greeting - Human touch */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center py-6"
        >
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full bg-muted/50 mb-4`}>
            <GreetingIcon className={`w-5 h-5 ${greeting.color}`} />
            <span className="font-medium">{greeting.text}</span>
          </div>
          <h1 className="text-3xl font-heading font-bold mb-2">Your Progress</h1>
          <p className="text-muted-foreground">Based on {gamesAnalyzed} games analyzed</p>
        </motion.div>

        {/* Main Metric - Accuracy with trend */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="overflow-hidden">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Move Accuracy</p>
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-bold">{accuracy.current?.toFixed(1)}%</span>
                    {accuracyDelta !== 0 && (
                      <span className={`flex items-center text-sm ${accuracyImproved ? 'text-emerald-500' : 'text-red-500'}`}>
                        {accuracyImproved ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
                        {accuracyDelta > 0 ? '+' : ''}{accuracyDelta.toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">Last week</p>
                  <p className="text-lg text-muted-foreground">{accuracy.previous?.toFixed(1) || '--'}%</p>
                </div>
              </div>
              
              {/* Visual progress bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Beginner</span>
                  <span>Expert</span>
                </div>
                <ProgressBar value={accuracy.current || 0} className="h-3" />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>40%</span>
                  <span>60%</span>
                  <span>80%</span>
                  <span>95%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Your Main Weakness - With action */}
        {dominantPattern && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent">
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-6 h-6 text-amber-500" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold mb-1">Your Main Leak</h3>
                    <p className="text-2xl font-bold text-amber-500 mb-1">
                      {patternCount}x {dominantPattern.replace(/_/g, " ")}
                    </p>
                    <p className="text-sm text-muted-foreground mb-3">
                      This is costing you the most rating points. Fix this first.
                    </p>
                    <Button 
                      onClick={() => navigate(`/training/prescribed?weakness=${dominantPattern}`)}
                      className="bg-amber-500 hover:bg-amber-600 text-black"
                      data-testid="train-weakness-btn"
                    >
                      <Target className="w-4 h-4 mr-2" />
                      Train This Now
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Blunder Stats - Coach perspective */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Zap className="w-4 h-4 text-red-500" />
                  Blunder Control
                </h3>
                <span className={`text-xs px-2 py-1 rounded ${
                  data?.blunders?.trend === 'improving' 
                    ? 'bg-emerald-500/10 text-emerald-500' 
                    : data?.blunders?.trend === 'worsening'
                    ? 'bg-red-500/10 text-red-500'
                    : 'bg-muted text-muted-foreground'
                }`}>
                  {data?.blunders?.trend === 'improving' ? 'Improving' : 
                   data?.blunders?.trend === 'worsening' ? 'Needs work' : 'Stable'}
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-muted/30">
                  <p className="text-3xl font-bold">{data?.blunders?.avg_per_game?.toFixed(1) || '--'}</p>
                  <p className="text-sm text-muted-foreground">blunders per game</p>
                </div>
                <div className="p-4 rounded-lg bg-muted/30">
                  <p className="text-3xl font-bold">{data?.blunders?.total || 0}</p>
                  <p className="text-sm text-muted-foreground">total this week</p>
                </div>
              </div>
              
              <p className="mt-4 text-sm text-muted-foreground">
                {data?.blunders?.avg_per_game <= 1 
                  ? "Excellent control! You're keeping blunders rare."
                  : data?.blunders?.avg_per_game <= 2
                  ? "Good. Most games have 1-2 critical moments to fix."
                  : "Focus on slowing down. Check for threats before each move."}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        {/* Active Habits - What you're working on */}
        {habits.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Card>
              <CardContent className="p-5">
                <h3 className="font-semibold flex items-center gap-2 mb-4">
                  <Brain className="w-4 h-4 text-purple-500" />
                  Habits You're Building
                </h3>
                
                <div className="space-y-3">
                  {habits.filter(h => h.is_active).slice(0, 3).map((habit, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                          habit.trend === 'improving' ? 'bg-emerald-500/20' : 'bg-muted'
                        }`}>
                          {habit.trend === 'improving' 
                            ? <TrendingUp className="w-4 h-4 text-emerald-500" />
                            : <Target className="w-4 h-4 text-muted-foreground" />
                          }
                        </div>
                        <div>
                          <p className="font-medium text-sm">{habit.name}</p>
                          <p className="text-xs text-muted-foreground capitalize">{habit.category}</p>
                        </div>
                      </div>
                      <span className={`text-xs ${
                        habit.trend === 'improving' ? 'text-emerald-500' : 'text-muted-foreground'
                      }`}>
                        {habit.occurrences_recent} this week
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="grid grid-cols-2 gap-3"
        >
          <Button 
            variant="outline" 
            className="h-auto py-4 flex-col gap-2"
            onClick={() => navigate('/reflect')}
          >
            <Eye className="w-5 h-5" />
            <span className="text-xs">Reflect on Games</span>
          </Button>
          <Button 
            variant="outline" 
            className="h-auto py-4 flex-col gap-2"
            onClick={() => navigate('/journey')}
          >
            <TrendingUp className="w-5 h-5" />
            <span className="text-xs">Full Journey</span>
          </Button>
        </motion.div>

        {/* Sync footer */}
        <div className="flex justify-center pt-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={syncNow}
            disabled={syncing}
            className="text-muted-foreground"
          >
            {syncing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Sync latest games
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default Progress;
