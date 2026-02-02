import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import Layout from "@/components/Layout";
import { 
  Import, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle2, 
  ChevronRight,
  Gamepad2,
  Target
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
          <div className="animate-pulse text-muted-foreground">Loading dashboard...</div>
        </div>
      </Layout>
    );
  }

  const hasGames = stats && stats.total_games > 0;
  const topPatterns = stats && stats.top_patterns ? stats.top_patterns : [];
  const recentGames = stats && stats.recent_games ? stats.recent_games : [];
  const totalBlunders = stats && stats.stats ? stats.stats.total_blunders : 0;
  const totalBestMoves = stats && stats.stats ? stats.stats.total_best_moves : 0;
  const totalGames = stats ? stats.total_games : 0;
  const analyzedGames = stats ? stats.analyzed_games : 0;

  return (
    <Layout user={user}>
      <div className="space-y-8" data-testid="dashboard-page">
        {/* Welcome Section */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">
            Welcome back, {user && user.name ? user.name.split(' ')[0] : 'Player'}
          </h1>
          <p className="text-muted-foreground">
            {hasGames 
              ? "Here's your chess performance overview"
              : "Let's get started by importing your games"}
          </p>
        </div>

        {!hasGames ? (
          /* Empty State */
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16 space-y-6">
              <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
                <Import className="w-10 h-10 text-primary" />
              </div>
              <div className="text-center space-y-2">
                <h3 className="text-xl font-semibold">No games imported yet</h3>
                <p className="text-muted-foreground max-w-md">
                  Connect your Chess.com or Lichess account to import your games 
                  and start receiving personalized coaching.
                </p>
              </div>
              <Button 
                size="lg" 
                onClick={() => navigate('/import')}
                data-testid="import-games-cta"
              >
                <Import className="w-5 h-5 mr-2" />
                Import Your Games
              </Button>
            </CardContent>
          </Card>
        ) : (
          /* Dashboard with Stats */
          <>
            {/* Stats Grid - Bento Style */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card data-testid="stat-total-games">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Total Games</p>
                      <p className="text-3xl font-bold">{totalGames}</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Gamepad2 className="w-6 h-6 text-primary" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card data-testid="stat-analyzed-games">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Analyzed</p>
                      <p className="text-3xl font-bold">{analyzedGames}</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                      <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                    </div>
                  </div>
                  <Progress 
                    value={totalGames > 0 ? (analyzedGames / totalGames) * 100 : 0} 
                    className="mt-4 h-2"
                  />
                </CardContent>
              </Card>

              <Card data-testid="stat-blunders">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Total Blunders</p>
                      <p className="text-3xl font-bold text-red-500">{totalBlunders}</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-red-500/10 flex items-center justify-center">
                      <AlertTriangle className="w-6 h-6 text-red-500" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card data-testid="stat-best-moves">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Best Moves</p>
                      <p className="text-3xl font-bold text-emerald-500">{totalBestMoves}</p>
                    </div>
                    <div className="w-12 h-12 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                      <Target className="w-6 h-6 text-emerald-500" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Two Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Games */}
              <Card data-testid="recent-games-card">
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">Recent Games</CardTitle>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => navigate('/import')}
                  >
                    View All
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </CardHeader>
                <CardContent className="space-y-3">
                  {recentGames.length > 0 ? (
                    recentGames.map((game) => (
                      <div 
                        key={game.game_id}
                        className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors cursor-pointer"
                        onClick={() => navigate(`/game/${game.game_id}`)}
                        data-testid={`game-item-${game.game_id}`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${game.is_analyzed ? 'bg-emerald-500' : 'bg-muted-foreground'}`} />
                          <div>
                            <p className="font-medium text-sm">
                              {game.white_player} vs {game.black_player}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {game.platform} • {game.result}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs px-2 py-1 rounded ${game.user_color === 'white' ? 'bg-white text-black border' : 'bg-black text-white'}`}>
                            {game.user_color}
                          </span>
                          <ChevronRight className="w-4 h-4 text-muted-foreground" />
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted-foreground text-sm text-center py-4">
                      No recent games
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Top Weaknesses */}
              <Card data-testid="weaknesses-card">
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg">Top Weaknesses</CardTitle>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => navigate('/weaknesses')}
                  >
                    View All
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </CardHeader>
                <CardContent className="space-y-3">
                  {topPatterns.length > 0 ? (
                    topPatterns.map((pattern, index) => (
                      <div 
                        key={pattern.pattern_id}
                        className="p-3 rounded-lg bg-muted/50"
                        data-testid={`weakness-item-${index}`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-sm capitalize">
                            {pattern.subcategory.replace(/_/g, ' ')}
                          </span>
                          <span className="text-xs text-red-500 font-medium">
                            {pattern.occurrences} times
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {pattern.description}
                        </p>
                        <div className="mt-2">
                          <Progress 
                            value={Math.min(pattern.occurrences * 10, 100)} 
                            className="h-1"
                          />
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-4">
                      <p className="text-muted-foreground text-sm">
                        Analyze games to discover patterns
                      </p>
                      <Button 
                        variant="link" 
                        size="sm"
                        onClick={() => navigate('/import')}
                        className="mt-2"
                      >
                        Import Games
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Button 
                variant="outline" 
                className="h-auto py-6 flex flex-col items-center gap-2"
                onClick={() => navigate('/import')}
                data-testid="quick-import-btn"
              >
                <Import className="w-6 h-6" />
                <span>Import More Games</span>
              </Button>
              <Button 
                variant="outline" 
                className="h-auto py-6 flex flex-col items-center gap-2"
                onClick={() => navigate('/weaknesses')}
                data-testid="quick-weaknesses-btn"
              >
                <TrendingUp className="w-6 h-6" />
                <span>View Weaknesses</span>
              </Button>
              <Button 
                variant="outline" 
                className="h-auto py-6 flex flex-col items-center gap-2"
                onClick={() => navigate('/training')}
                data-testid="quick-training-btn"
              >
                <Target className="w-6 h-6" />
                <span>Get Training Plan</span>
              </Button>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
