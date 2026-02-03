import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import { 
  StatCard,
  ProgressRing,
  SectionHeader,
  AnimatedList,
  AnimatedItem
} from "@/components/ui/premium";
import { 
  Import, 
  ChevronRight,
  Gamepad2,
  Target,
  TrendingUp,
  AlertTriangle,
  Zap,
  Loader2
} from "lucide-react";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch(`${API}/dashboard-stats`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          setStats(data);
        }
      } catch (error) {
        console.error('Error fetching stats:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  const hasGames = stats && stats.total_games > 0;
  const topWeaknesses = stats?.top_weaknesses || [];
  const recentGames = stats?.recent_games || [];
  const totalBlunders = stats?.stats?.total_blunders || 0;
  const totalBestMoves = stats?.stats?.total_best_moves || 0;
  const totalGames = stats?.total_games || 0;
  const analyzedGames = stats?.analyzed_games || 0;
  const analysisProgress = totalGames > 0 ? Math.round((analyzedGames / totalGames) * 100) : 0;

  const firstName = user?.name?.split(' ')[0] || 'Player';

  return (
    <Layout user={user}>
      <div className="space-y-8 max-w-5xl" data-testid="dashboard-page">
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-end justify-between"
        >
          <div>
            <p className="label-caps mb-2">Dashboard</p>
            <h1 className="text-3xl font-heading font-bold tracking-tight">
              Welcome back, {firstName}
            </h1>
          </div>
          {hasGames && (
            <Button 
              onClick={() => navigate('/journey')}
              variant="outline"
              className="btn-scale"
            >
              View Journey
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          )}
        </motion.div>

        {!hasGames ? (
          /* Empty State */
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="border-dashed border-2 border-muted-foreground/20">
              <CardContent className="flex flex-col items-center justify-center py-16">
                <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mb-6">
                  <Import className="w-9 h-9 text-muted-foreground" />
                </div>
                <h3 className="font-heading font-semibold text-xl mb-2">No games imported yet</h3>
                <p className="text-muted-foreground max-w-md text-center mb-6">
                  Connect your Chess.com or Lichess account to import games 
                  and start receiving personalized coaching.
                </p>
                <Button 
                  size="lg" 
                  onClick={() => navigate('/import')}
                  className="btn-scale"
                  data-testid="import-games-cta"
                >
                  <Import className="w-5 h-5 mr-2" />
                  Import Your Games
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ) : (
          <AnimatedList className="space-y-6">
            {/* Stats Row */}
            <AnimatedItem>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard 
                  label="Games" 
                  value={totalGames}
                  icon={Gamepad2}
                />
                <Card className="surface p-4 card-hover">
                  <div className="flex items-center gap-4">
                    <ProgressRing 
                      progress={analysisProgress} 
                      size={56} 
                      strokeWidth={5}
                      color="stroke-emerald-500"
                    />
                    <div>
                      <p className="label-caps mb-1">Analyzed</p>
                      <p className="text-xl font-heading font-semibold">{analyzedGames}</p>
                    </div>
                  </div>
                </Card>
                <StatCard 
                  label="Blunders" 
                  value={totalBlunders}
                  icon={AlertTriangle}
                />
                <StatCard 
                  label="Best Moves" 
                  value={totalBestMoves}
                  icon={Zap}
                />
              </div>
            </AnimatedItem>

            {/* Two Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Games */}
              <AnimatedItem>
                <Card className="surface h-full">
                  <CardContent className="py-6">
                    <SectionHeader 
                      label="Recent Games" 
                      action={
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => navigate('/import')}
                          className="text-muted-foreground hover:text-foreground -mr-2"
                        >
                          All
                          <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      }
                    />
                    <div className="space-y-2">
                      {recentGames.length > 0 ? (
                        recentGames.slice(0, 5).map((game) => (
                          <motion.div 
                            key={game.game_id}
                            whileHover={{ x: 4 }}
                            className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted/80 transition-colors cursor-pointer"
                            onClick={() => navigate(`/game/${game.game_id}`)}
                            data-testid={`game-item-${game.game_id}`}
                          >
                            <div className="flex items-center gap-3">
                              <span className={`w-2 h-2 rounded-full ${game.is_analyzed ? 'bg-emerald-500' : 'bg-muted-foreground'}`} />
                              <div>
                                <p className="font-medium text-sm">
                                  {game.white_player} vs {game.black_player}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {game.platform} · {game.result}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={`text-xs px-2 py-0.5 rounded font-mono ${game.user_color === 'white' ? 'bg-white text-black border border-border' : 'bg-zinc-800 text-white'}`}>
                                {game.user_color === 'white' ? 'W' : 'B'}
                              </span>
                              <ChevronRight className="w-4 h-4 text-muted-foreground" />
                            </div>
                          </motion.div>
                        ))
                      ) : (
                        <p className="text-muted-foreground text-sm text-center py-8">
                          No games yet
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </AnimatedItem>

              {/* Top Weaknesses */}
              <AnimatedItem>
                <Card className="surface h-full">
                  <CardContent className="py-6">
                    <SectionHeader 
                      label="Focus Areas" 
                      action={
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => navigate('/journey')}
                          className="text-muted-foreground hover:text-foreground -mr-2"
                        >
                          Journey
                          <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      }
                    />
                    <div className="space-y-2">
                      {topWeaknesses.length > 0 ? (
                        topWeaknesses.slice(0, 4).map((weakness, index) => (
                          <div 
                            key={index}
                            className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                            data-testid={`weakness-item-${index}`}
                          >
                            <div>
                              <p className="font-medium text-sm capitalize">
                                {(weakness.subcategory || weakness.name || '').replace(/_/g, ' ')}
                              </p>
                              <p className="text-xs text-muted-foreground capitalize">
                                {weakness.category}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-muted-foreground">
                                {weakness.occurrences || weakness.decayed_score?.toFixed(1) || '—'}
                              </span>
                              <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                                <div 
                                  className="h-full bg-amber-500 rounded-full"
                                  style={{ width: `${Math.min((weakness.occurrences || weakness.decayed_score || 0) * 10, 100)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-8">
                          <p className="text-muted-foreground text-sm mb-3">
                            Analyze games to discover patterns
                          </p>
                          <Button 
                            variant="outline" 
                            size="sm"
                            onClick={() => navigate('/import')}
                            className="btn-scale"
                          >
                            Import Games
                          </Button>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </AnimatedItem>
            </div>

            {/* Quick Actions */}
            <AnimatedItem>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                  <Button 
                    variant="outline" 
                    className="w-full h-auto py-5 flex flex-col items-center gap-2"
                    onClick={() => navigate('/import')}
                    data-testid="quick-import-btn"
                  >
                    <Import className="w-5 h-5" />
                    <span className="text-sm">Import Games</span>
                  </Button>
                </motion.div>
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                  <Button 
                    variant="outline" 
                    className="w-full h-auto py-5 flex flex-col items-center gap-2"
                    onClick={() => navigate('/journey')}
                    data-testid="quick-journey-btn"
                  >
                    <TrendingUp className="w-5 h-5" />
                    <span className="text-sm">View Journey</span>
                  </Button>
                </motion.div>
                <motion.div whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                  <Button 
                    variant="outline" 
                    className="w-full h-auto py-5 flex flex-col items-center gap-2"
                    onClick={() => navigate('/challenge')}
                    data-testid="quick-challenge-btn"
                  >
                    <Target className="w-5 h-5" />
                    <span className="text-sm">Practice</span>
                  </Button>
                </motion.div>
              </div>
            </AnimatedItem>
          </AnimatedList>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
