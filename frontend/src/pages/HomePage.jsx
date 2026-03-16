/**
 * HomePage - Focused Coaching Dashboard
 * 
 * Four sections only:
 * 1. Biggest Weakness (top priority)
 * 2. Improvement Tracker (last 3 games)
 * 3. Today's Training Task (single action)
 * 4. Games to Reflect
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  Eye,
  CheckCircle2,
  XCircle,
  Minus
} from "lucide-react";

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState(null);
  const [reflectionGames, setReflectionGames] = useState([]);
  const [focusLock, setFocusLock] = useState(null);
  
  // Fetch all required data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Fetch dashboard stats (includes weaknesses, recent games)
        const [statsRes, reflectRes, focusRes] = await Promise.all([
          fetch(`${API}/dashboard-stats`, { credentials: 'include' }),
          fetch(`${API}/reflect/pending`, { credentials: 'include' }),
          fetch(`${API}/coach/focus-lock`, { credentials: 'include' })
        ]);
        
        if (statsRes.ok) {
          const stats = await statsRes.json();
          setDashboardData(stats);
        }
        
        if (reflectRes.ok) {
          const reflect = await reflectRes.json();
          setReflectionGames(reflect.games || []);
        }
        
        if (focusRes.ok) {
          const focus = await focusRes.json();
          setFocusLock(focus);
        }
      } catch (error) {
        console.error('Error fetching homepage data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);
  
  // Get biggest weakness from dashboard data
  const getBiggestWeakness = () => {
    if (!dashboardData?.top_weaknesses?.length) {
      return null;
    }
    
    const weakness = dashboardData.top_weaknesses[0];
    
    // Map pattern types to friendly names and descriptions
    const weaknessInfo = {
      'missed_threat': {
        name: 'Threat Awareness',
        description: 'You missed opponent threats in your recent games.',
        impact: 'This is often why positions collapse quickly.'
      },
      'hanging_piece': {
        name: 'Piece Safety',
        description: 'You left pieces undefended that got captured.',
        impact: 'Free material for your opponent.'
      },
      'missed_tactic': {
        name: 'Tactical Vision',
        description: 'You missed winning tactics in your games.',
        impact: 'Opportunities slipped away.'
      },
      'time_trouble': {
        name: 'Time Management',
        description: 'You made mistakes when low on time.',
        impact: 'Rushing leads to errors.'
      },
      'blunder_after_blunder': {
        name: 'Emotional Control',
        description: 'One mistake led to more mistakes.',
        impact: 'Staying calm is key.'
      },
      'opening_inaccuracy': {
        name: 'Opening Preparation',
        description: 'Early mistakes in the opening phase.',
        impact: 'Starting with a disadvantage.'
      },
      'endgame_technique': {
        name: 'Endgame Technique',
        description: 'Errors converting winning positions.',
        impact: 'Wins slipping to draws.'
      }
    };
    
    const patternType = weakness.pattern_type || weakness.type || 'missed_threat';
    const info = weaknessInfo[patternType] || {
      name: patternType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      description: `This pattern appeared ${weakness.occurrences || weakness.count || 'multiple'} times.`,
      impact: 'Focus on this to improve.'
    };
    
    return {
      ...info,
      count: weakness.occurrences || weakness.count || 0,
      pattern_type: patternType
    };
  };
  
  // Get improvement data from last 3 games
  const getImprovementTracker = () => {
    if (!dashboardData?.analyzed_games?.length) {
      return null;
    }
    
    // Get last 3 analyzed games
    const recentGames = dashboardData.analyzed_games.slice(0, 3);
    
    if (recentGames.length < 2) {
      return null;
    }
    
    // Track blunders/mistakes across games
    const gameStats = recentGames.map((game, index) => ({
      opponent: game.opponent || game.white_player || game.black_player || 'Opponent',
      blunders: game.blunders || 0,
      mistakes: game.mistakes || 0,
      accuracy: game.accuracy || 0,
      result: game.result,
      index: index + 1
    }));
    
    // Calculate trend
    const firstGame = gameStats[gameStats.length - 1];
    const lastGame = gameStats[0];
    const errorFirst = (firstGame?.blunders || 0) + (firstGame?.mistakes || 0);
    const errorLast = (lastGame?.blunders || 0) + (lastGame?.mistakes || 0);
    
    let trend = 'neutral';
    let message = 'Keep focusing on clean play.';
    
    if (errorLast < errorFirst) {
      trend = 'improving';
      message = 'Nice progress! Your recent games show fewer errors.';
    } else if (errorLast > errorFirst) {
      trend = 'declining';
      message = 'Still working on consistency. One game at a time.';
    }
    
    return {
      games: gameStats,
      trend,
      message
    };
  };
  
  // Get today's training task
  const getTrainingTask = () => {
    const weakness = getBiggestWeakness();
    
    // Map weakness to training type
    const trainingMap = {
      'missed_threat': {
        title: 'Threat Detection Practice',
        description: 'Solve 5 positions where your opponent has hidden threats.',
        action: 'Start Training',
        route: '/training?focus=threats'
      },
      'hanging_piece': {
        title: 'Piece Safety Drill',
        description: 'Practice positions where you must protect your pieces.',
        action: 'Start Training',
        route: '/training?focus=safety'
      },
      'missed_tactic': {
        title: 'Tactical Puzzles',
        description: 'Find the winning moves in tactical positions.',
        action: 'Start Training',
        route: '/training'
      },
      'time_trouble': {
        title: 'Speed Decision Training',
        description: 'Practice making quick, accurate decisions.',
        action: 'Start Training',
        route: '/training'
      },
      'endgame_technique': {
        title: 'Endgame Practice',
        description: 'Master the technique to convert your advantages.',
        action: 'Start Training',
        route: '/training?focus=endgame'
      }
    };
    
    if (weakness && trainingMap[weakness.pattern_type]) {
      return trainingMap[weakness.pattern_type];
    }
    
    // Default training
    return {
      title: 'Daily Puzzle Practice',
      description: 'Solve tactical puzzles to sharpen your vision.',
      action: 'Start Training',
      route: '/training'
    };
  };
  
  const biggestWeakness = getBiggestWeakness();
  const improvement = getImprovementTracker();
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
      <div className="max-w-2xl mx-auto py-6 px-4 space-y-6">
        
        {/* Section 1: Biggest Weakness */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0 }}
        >
          <Card className="bg-gradient-to-br from-red-500/10 to-orange-500/5 border-red-500/20" data-testid="biggest-weakness-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                Your biggest weakness
              </CardTitle>
            </CardHeader>
            <CardContent>
              {biggestWeakness ? (
                <div className="space-y-2">
                  <h2 className="text-2xl font-bold text-foreground">
                    {biggestWeakness.name}
                  </h2>
                  <p className="text-muted-foreground">
                    {biggestWeakness.description}
                  </p>
                  <p className="text-sm text-orange-400">
                    {biggestWeakness.impact}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-foreground">
                    No patterns detected yet
                  </h2>
                  <p className="text-muted-foreground">
                    Play more games to discover your weaknesses.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
        
        {/* Section 2: Improvement Tracker */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="bg-card/50" data-testid="improvement-tracker-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                {improvement?.trend === 'improving' ? (
                  <TrendingUp className="w-4 h-4 text-green-400" />
                ) : improvement?.trend === 'declining' ? (
                  <TrendingDown className="w-4 h-4 text-yellow-400" />
                ) : (
                  <Minus className="w-4 h-4 text-muted-foreground" />
                )}
                Progress Check
              </CardTitle>
            </CardHeader>
            <CardContent>
              {improvement ? (
                <div className="space-y-4">
                  <p className={`text-sm ${
                    improvement.trend === 'improving' ? 'text-green-400' : 'text-muted-foreground'
                  }`}>
                    {improvement.message}
                  </p>
                  
                  <div className="space-y-2">
                    {improvement.games.map((game, i) => (
                      <div 
                        key={i}
                        className="flex items-center justify-between p-2 bg-muted/30 rounded-lg"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground w-16">
                            Game {game.index}
                          </span>
                          <span className="text-sm truncate max-w-[120px]">
                            vs {game.opponent}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-1">
                            <XCircle className="w-3 h-3 text-red-400" />
                            <span className="text-xs">{game.blunders}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3 text-yellow-400" />
                            <span className="text-xs">{game.mistakes}</span>
                          </div>
                          {game.accuracy > 0 && (
                            <span className="text-xs text-muted-foreground">
                              {game.accuracy.toFixed(0)}%
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Analyze more games to track your progress.
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
        
        {/* Section 3: Today's Training Task */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20" data-testid="training-task-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <Target className="w-4 h-4 text-primary" />
                Today's Training
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-foreground">
                    {trainingTask.title}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {trainingTask.description}
                  </p>
                </div>
                
                <Button 
                  onClick={() => navigate(trainingTask.route)}
                  className="w-full gap-2"
                  data-testid="start-training-btn"
                >
                  <Play className="w-4 h-4" />
                  {trainingTask.action}
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
        
        {/* Section 4: Games to Reflect */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card className="bg-card/50" data-testid="reflection-games-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <Eye className="w-4 h-4 text-blue-400" />
                Games to Reflect
              </CardTitle>
            </CardHeader>
            <CardContent>
              {reflectionGames.length > 0 ? (
                <div className="space-y-2">
                  {reflectionGames.slice(0, 3).map((game, i) => (
                    <button
                      key={game.game_id || i}
                      onClick={() => navigate(`/game/${game.game_id}`)}
                      className="w-full flex items-center justify-between p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors text-left"
                      data-testid={`reflection-game-${i}`}
                    >
                      <div>
                        <p className="text-sm font-medium">
                          vs {game.opponent || game.white_player || game.black_player || 'Opponent'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {game.blunders_count || game.blunders || 0} blunders to understand
                        </p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              ) : dashboardData?.analyzed_games?.length > 0 ? (
                <div className="space-y-2">
                  {dashboardData.analyzed_games.slice(0, 3).map((game, i) => (
                    <button
                      key={game.game_id || i}
                      onClick={() => navigate(`/game/${game.game_id}`)}
                      className="w-full flex items-center justify-between p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors text-left"
                      data-testid={`analyzed-game-${i}`}
                    >
                      <div>
                        <p className="text-sm font-medium">
                          vs {game.opponent || 'Opponent'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {(game.blunders || 0) + (game.mistakes || 0)} moments to review
                        </p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No games ready for reflection yet.
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
        
        {/* Quick Links Footer */}
        <div className="flex justify-center gap-4 pt-4">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate('/journey')}
            className="text-xs text-muted-foreground"
          >
            View Full Journey
          </Button>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate('/openings')}
            className="text-xs text-muted-foreground"
          >
            Opening Repertoire
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default HomePage;
