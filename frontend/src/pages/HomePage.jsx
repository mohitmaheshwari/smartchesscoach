/**
 * HomePage - Coaching Progress Dashboard
 * 
 * Designed to feel like a coach, not a dashboard.
 * 
 * Flow:
 * 1. See biggest weakness with improvement progress
 * 2. Coach insight (personality)
 * 3. Clear training action
 * 4. Games to reflect with specific context
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import { 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown,
  Target,
  Play,
  ChevronRight,
  Loader2,
  Zap,
  MessageSquare,
  Sparkles,
  Eye,
  Shield
} from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState(null);
  const [reflectionGames, setReflectionGames] = useState([]);
  const [weeklyProgress, setWeeklyProgress] = useState(null);
  const [blindSpots, setBlindSpots] = useState([]);
  
  // Fetch all required data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [statsRes, reflectRes, progressRes, blindSpotsRes] = await Promise.all([
          fetch(`${API}/dashboard-stats`, { credentials: 'include' }),
          fetch(`${API}/reflect/pending`, { credentials: 'include' }),
          fetch(`${API}/coach/analytics/summary`, { credentials: 'include' }).catch(() => null),
          fetch(`${API}/blind-spots`, { credentials: 'include' }).catch(() => null)
        ]);
        
        if (statsRes.ok) {
          const stats = await statsRes.json();
          setDashboardData(stats);
        }
        
        if (reflectRes.ok) {
          const reflect = await reflectRes.json();
          setReflectionGames(reflect.games || []);
        }
        
        if (blindSpotsRes?.ok) {
          const spots = await blindSpotsRes.json();
          setBlindSpots(spots.blind_spots || []);
        }
        
        // Try to get weekly progress data
        if (progressRes?.ok) {
          const progress = await progressRes.json();
          setWeeklyProgress(progress);
        }
      } catch (error) {
        console.error('Error fetching homepage data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);
  
  // Get biggest weakness with details
  const getWeaknessData = () => {
    if (!dashboardData?.top_weaknesses?.length) {
      return null;
    }
    
    const weakness = dashboardData.top_weaknesses[0];
    const patternType = weakness.pattern_type || weakness.type || weakness.category || 'tactical_error';
    const occurrences = weakness.occurrences || weakness.count || weakness.occurrence_count || 0;
    
    // Weakness info with coaching language
    const weaknessInfo = {
      'tactical_error': {
        name: 'Tactical Errors',
        metric: 'missed tactics',
        coachTip: 'Before every move, ask: "What is my opponent threatening?"',
        trainingType: 'tactical puzzles',
        potentialGain: 150
      },
      'missed_threat': {
        name: 'Threat Awareness',
        metric: 'missed threats',
        coachTip: 'Scan all opponent pieces before deciding your move.',
        trainingType: 'threat detection drills',
        potentialGain: 120
      },
      'hanging_piece': {
        name: 'Piece Safety',
        metric: 'pieces left hanging',
        coachTip: 'After each move, check: "Is everything protected?"',
        trainingType: 'piece safety puzzles',
        potentialGain: 100
      },
      'missed_tactic': {
        name: 'Tactical Vision',
        metric: 'winning moves missed',
        coachTip: 'Look for checks, captures, and threats in that order.',
        trainingType: 'tactical patterns',
        potentialGain: 180
      },
      'time_trouble': {
        name: 'Time Management',
        metric: 'time pressure mistakes',
        coachTip: 'Spend more time in the opening to avoid rushing later.',
        trainingType: 'speed decision training',
        potentialGain: 80
      },
      'blunder_after_blunder': {
        name: 'Emotional Control',
        metric: 'tilt mistakes',
        coachTip: 'After a mistake, pause and reset before your next move.',
        trainingType: 'recovery training',
        potentialGain: 100
      },
      'endgame_technique': {
        name: 'Endgame Technique',
        metric: 'endgame errors',
        coachTip: 'In endgames, king activity is worth more than pawns.',
        trainingType: 'endgame drills',
        potentialGain: 130
      }
    };
    
    const info = weaknessInfo[patternType] || {
      name: patternType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      metric: 'mistakes',
      coachTip: 'Focus on one improvement at a time.',
      trainingType: 'targeted practice',
      potentialGain: 100
    };
    
    return {
      ...info,
      count: occurrences,
      pattern_type: patternType
    };
  };
  
  // Calculate improvement from analyzed games
  const getImprovementData = () => {
    const analyzedGames = dashboardData?.analyzed_list || [];
    if (analyzedGames.length < 4) return null;
    
    // Split into recent (first 3) and older (rest)
    const recentGames = analyzedGames.slice(0, 3);
    const olderGames = analyzedGames.slice(3, 6);
    
    if (olderGames.length === 0) return null;
    
    // Calculate average mistakes
    const recentMistakes = recentGames.reduce((sum, g) => sum + (g.blunders || 0) + (g.mistakes || 0), 0) / recentGames.length;
    const olderMistakes = olderGames.reduce((sum, g) => sum + (g.blunders || 0) + (g.mistakes || 0), 0) / olderGames.length;
    
    const improvement = olderMistakes > 0 
      ? Math.round(((olderMistakes - recentMistakes) / olderMistakes) * 100)
      : 0;
    
    return {
      recentAvg: Math.round(recentMistakes * 10) / 10,
      olderAvg: Math.round(olderMistakes * 10) / 10,
      improvement,
      isImproving: improvement > 0
    };
  };
  
  // Get training task based on weakness
  const getTrainingTask = () => {
    const weakness = getWeaknessData();
    if (!weakness) {
      return {
        title: 'Start Your Journey',
        subtitle: 'Import games to discover your patterns',
        action: 'Import Games',
        route: '/import',
        count: null
      };
    }
    
    return {
      title: `${weakness.trainingType.charAt(0).toUpperCase() + weakness.trainingType.slice(1)}`,
      subtitle: `You had ${weakness.count} ${weakness.metric} recently`,
      action: 'Start Training',
      route: `/training?focus=${weakness.pattern_type}`,
      count: Math.min(weakness.count, 5) // Suggest solving up to 5
    };
  };
  
  const weaknessData = getWeaknessData();
  const improvementData = getImprovementData();
  const trainingTask = getTrainingTask();
  
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </Layout>
    );
  }
  
  return (
    <Layout user={user}>
      <div className="max-w-xl mx-auto py-8 px-4 space-y-6">
        
        {/* Section 1: Weakness + Progress Combined */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="bg-gradient-to-br from-red-500/10 to-orange-500/5 border-red-500/20 overflow-hidden" data-testid="weakness-progress-card">
            <CardContent className="pt-6">
              {weaknessData ? (
                <div className="space-y-5">
                  {/* Weakness Header */}
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                      Your biggest weakness
                    </p>
                    <h2 className="text-2xl font-bold text-foreground">
                      {weaknessData.name}
                    </h2>
                  </div>
                  
                  {/* Progress Stats */}
                  {improvementData ? (
                    <div className="bg-background/50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-sm text-muted-foreground">Your progress</span>
                        {improvementData.isImproving ? (
                          <span className="flex items-center gap-1 text-green-400 text-sm font-medium">
                            <TrendingUp className="w-4 h-4" />
                            +{improvementData.improvement}%
                          </span>
                        ) : improvementData.improvement < 0 ? (
                          <span className="flex items-center gap-1 text-yellow-400 text-sm font-medium">
                            <TrendingDown className="w-4 h-4" />
                            {improvementData.improvement}%
                          </span>
                        ) : (
                          <span className="text-muted-foreground text-sm">Steady</span>
                        )}
                      </div>
                      
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Previous games</p>
                          <p className="text-lg font-semibold">{improvementData.olderAvg} <span className="text-sm font-normal text-muted-foreground">errors/game</span></p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Recent games</p>
                          <p className="text-lg font-semibold">{improvementData.recentAvg} <span className="text-sm font-normal text-muted-foreground">errors/game</span></p>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-orange-400">
                      {weaknessData.count} {weaknessData.metric} in recent games. Let's fix that.
                    </p>
                  )}
                  
                  {/* Potential Rating Gain */}
                  <div className="flex items-center gap-2 text-sm">
                    <Sparkles className="w-4 h-4 text-yellow-400" />
                    <span className="text-muted-foreground">
                      Fixing this could gain you <span className="text-foreground font-medium">+{weaknessData.potentialGain} rating points</span>
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4">
                  <AlertTriangle className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
                  <h2 className="text-xl font-semibold mb-2">No patterns detected yet</h2>
                  <p className="text-sm text-muted-foreground">
                    Import and analyze games to discover your weaknesses.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
        
        {/* Section 2: Coach Insight */}
        {weaknessData && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="bg-card/50 border-primary/20" data-testid="coach-insight-card">
              <CardContent className="pt-5 pb-5">
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                    <MessageSquare className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-xs text-primary font-medium mb-1">Coach Tip</p>
                    <p className="text-sm text-foreground leading-relaxed">
                      {weaknessData.coachTip}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
        
        {/* Section 2.5: Blind Spots - Turning Point Patterns */}
        {blindSpots.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12 }}
          >
            <Card className="bg-card/50 border-amber-500/20" data-testid="blind-spots-card">
              <CardContent className="pt-5 pb-5">
                <div className="flex items-center gap-2 mb-4">
                  <Eye className="w-4 h-4 text-amber-400" />
                  <span className="text-xs text-muted-foreground uppercase tracking-wide">
                    Your Blind Spots
                  </span>
                </div>
                
                <div className="space-y-3">
                  {blindSpots.slice(0, 3).map((spot, i) => (
                    <div 
                      key={spot.category}
                      className="flex items-center justify-between p-2 bg-muted/30 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${
                          spot.severity === 'high' ? 'bg-red-400' : 
                          spot.severity === 'medium' ? 'bg-amber-400' : 'bg-slate-400'
                        }`} />
                        <div>
                          <p className="text-sm font-medium">{spot.label}</p>
                          <p className="text-xs text-muted-foreground">
                            {spot.count} of {spot.total_games} games ({spot.percentage}%)
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs text-amber-400 hover:text-amber-300 p-0 h-auto"
                        onClick={() => navigate(`/training?focus=${spot.training_focus}`)}
                      >
                        Train
                        <ChevronRight className="w-3 h-3 ml-0.5" />
                      </Button>
                    </div>
                  ))}
                </div>
                
                {blindSpots.length > 0 && blindSpots[0].patterns?.length > 0 && (
                  <p className="text-xs text-muted-foreground mt-3">
                    Common patterns: {blindSpots[0].patterns.slice(0, 2).join(", ")}
                  </p>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
        
        {/* Section 3: Today's Training */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20" data-testid="training-task-card">
            <CardContent className="pt-5 pb-5">
              <div className="flex items-center gap-2 mb-3">
                <Target className="w-4 h-4 text-primary" />
                <span className="text-xs text-muted-foreground uppercase tracking-wide">Today's Training</span>
              </div>
              
              <h3 className="text-lg font-semibold mb-1">{trainingTask.title}</h3>
              <p className="text-sm text-muted-foreground mb-4">{trainingTask.subtitle}</p>
              
              {trainingTask.count && (
                <p className="text-sm text-primary mb-4">
                  Solve {trainingTask.count} positions from your games
                </p>
              )}
              
              <Button 
                onClick={() => navigate(trainingTask.route)}
                className="w-full gap-2"
                data-testid="start-training-btn"
              >
                <Play className="w-4 h-4" />
                {trainingTask.action}
              </Button>
            </CardContent>
          </Card>
        </motion.div>
        
        {/* Section 4: Games to Reflect */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="bg-card/50" data-testid="reflection-games-card">
            <CardContent className="pt-5 pb-5">
              <div className="flex items-center gap-2 mb-4">
                <Zap className="w-4 h-4 text-yellow-400" />
                <span className="text-xs text-muted-foreground uppercase tracking-wide">Games to Reflect</span>
              </div>
              
              {reflectionGames.length > 0 ? (
                <div className="space-y-3">
                  {reflectionGames.slice(0, 2).map((game, i) => (
                    <button
                      key={game.game_id || i}
                      onClick={() => navigate(`/game/${game.game_id}`)}
                      className="w-full text-left p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors group"
                      data-testid={`reflection-game-${i}`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium mb-1">
                            Game vs {game.opponent_name || game.opponent || 'Opponent'}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {game.blunders || 0} blunders to understand
                          </p>
                        </div>
                        <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                      </div>
                    </button>
                  ))}
                </div>
              ) : dashboardData?.analyzed_list?.length > 0 ? (
                <div className="space-y-3">
                  {dashboardData.analyzed_list.slice(0, 2).map((game, i) => {
                    const userColor = game.user_color || 'white';
                    const opponent = userColor === 'white' 
                      ? (game.black_player || 'Opponent')
                      : (game.white_player || 'Opponent');
                    
                    return (
                      <button
                        key={game.game_id || i}
                        onClick={() => navigate(`/game/${game.game_id}`)}
                        className="w-full text-left p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors group"
                        data-testid={`analyzed-game-${i}`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium mb-1">
                              Game vs {opponent}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {(game.blunders || 0) + (game.mistakes || 0)} moments to review
                            </p>
                          </div>
                          <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-2">
                  No games ready for reflection yet.
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
        
        {/* Quick Links */}
        <div className="flex justify-center gap-4 pt-2">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate('/journey')}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Full Journey
          </Button>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate('/openings')}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Openings
          </Button>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate('/play-with-coach')}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Play
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default HomePage;
