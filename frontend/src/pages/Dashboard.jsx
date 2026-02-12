import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Layout from "@/components/Layout";
import StatsDetailModal from "@/components/StatsDetailModal";
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
  Loader2,
  Filter,
  ChevronDown
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState(null);
  const [opponentFilter, setOpponentFilter] = useState("all"); // all, stronger, equal, weaker

  const openStatsModal = (type) => {
    setModalType(type);
    setModalOpen(true);
  };

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

  // User's estimated rating from profile
  const userRating = stats?.profile_summary?.estimated_elo || 1200;

  // Filter games based on opponent strength
  const filteredGames = recentGames.filter(game => {
    if (opponentFilter === "all") return true;
    
    const opponentRating = game.user_color === 'white' 
      ? game.black_rating 
      : game.white_rating;
    
    if (!opponentRating) return opponentFilter === "all";
    
    const ratingDiff = opponentRating - userRating;
    
    if (opponentFilter === "stronger") return ratingDiff > 50;
    if (opponentFilter === "weaker") return ratingDiff < -50;
    if (opponentFilter === "equal") return Math.abs(ratingDiff) <= 50;
    
    return true;
  });

  // Get opponent strength label
  const getOpponentStrengthLabel = (opponentRating) => {
    if (!opponentRating) return null;
    const diff = opponentRating - userRating;
    if (diff > 100) return { label: "Higher", color: "text-red-400" };
    if (diff > 50) return { label: "Higher", color: "text-orange-400" };
    if (diff < -100) return { label: "Lower", color: "text-green-400" };
    if (diff < -50) return { label: "Lower", color: "text-green-400" };
    return { label: "Equal", color: "text-muted-foreground" };
  };

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
            {/* Stats Row - Clickable */}
            <AnimatedItem>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard 
                  label="Games" 
                  value={totalGames}
                  icon={Gamepad2}
                />
                <Card 
                  className="surface p-4 card-hover cursor-pointer hover:ring-1 hover:ring-primary/50 transition-all"
                  onClick={() => openStatsModal("analyzed")}
                  data-testid="analyzed-stat-card"
                >
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
                <Card 
                  className="surface p-4 card-hover cursor-pointer hover:ring-1 hover:ring-red-500/50 transition-all"
                  onClick={() => openStatsModal("blunders")}
                  data-testid="blunders-stat-card"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center">
                      <AlertTriangle className="w-5 h-5 text-red-500" />
                    </div>
                    <div>
                      <p className="label-caps mb-1">Blunders</p>
                      <p className="text-xl font-heading font-semibold">{totalBlunders}</p>
                    </div>
                  </div>
                </Card>
                <Card 
                  className="surface p-4 card-hover cursor-pointer hover:ring-1 hover:ring-amber-500/50 transition-all"
                  onClick={() => openStatsModal("best-moves")}
                  data-testid="best-moves-stat-card"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                      <Zap className="w-5 h-5 text-amber-500" />
                    </div>
                    <div>
                      <p className="label-caps mb-1">Best Moves</p>
                      <p className="text-xl font-heading font-semibold">{totalBestMoves}</p>
                    </div>
                  </div>
                </Card>
              </div>
            </AnimatedItem>

            {/* Two Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Games - Enhanced */}
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
                        recentGames.slice(0, 5).map((game) => {
                          const opponent = game.user_color === 'white' 
                            ? game.black_player 
                            : game.white_player;
                          const opponentRating = game.user_color === 'white'
                            ? game.black_rating
                            : game.white_rating;
                          const resultText = game.result === '1-0' 
                            ? (game.user_color === 'white' ? 'Won' : 'Lost')
                            : game.result === '0-1'
                            ? (game.user_color === 'black' ? 'Won' : 'Lost')
                            : 'Draw';
                          const resultColor = resultText === 'Won' 
                            ? 'text-emerald-500' 
                            : resultText === 'Lost' 
                            ? 'text-red-500' 
                            : 'text-yellow-500';
                          
                          return (
                            <motion.div 
                              key={game.game_id}
                              whileHover={{ x: 4 }}
                              className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted/80 transition-colors cursor-pointer group"
                              onClick={() => navigate(`/game/${game.game_id}`)}
                              data-testid={`game-item-${game.game_id}`}
                            >
                              <div className="flex items-center gap-3 flex-1 min-w-0">
                                {/* Color indicator */}
                                <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold ${
                                  game.user_color === 'white' 
                                    ? 'bg-white text-black border border-border' 
                                    : 'bg-zinc-800 text-white'
                                }`}>
                                  {game.user_color === 'white' ? 'W' : 'B'}
                                </span>
                                
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2">
                                    <p className="font-medium text-sm truncate">
                                      vs {opponent || 'Opponent'}
                                    </p>
                                    {opponentRating && (
                                      <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                                        {opponentRating}
                                      </span>
                                    )}
                                    <span className={`text-xs font-semibold ${resultColor}`}>
                                      {resultText}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                    {game.opening && (
                                      <span className="truncate max-w-[120px]">{game.opening}</span>
                                    )}
                                    {!game.opening && (
                                      <span>{game.platform}</span>
                                    )}
                                    {game.is_analyzed && game.accuracy && (
                                      <span className="text-emerald-500">{game.accuracy}%</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-2">
                                {!game.is_analyzed && (
                                  <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-500">
                                    Not analyzed
                                  </span>
                                )}
                                <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                              </div>
                            </motion.div>
                          );
                        })
                      ) : (
                        <p className="text-muted-foreground text-sm text-center py-8">
                          No games yet
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </AnimatedItem>

              {/* Focus Areas - Enhanced */}
              <AnimatedItem>
                <Card className="surface h-full">
                  <CardContent className="py-6">
                    <SectionHeader 
                      label="Focus Areas" 
                      action={
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => navigate('/progress')}
                          className="text-muted-foreground hover:text-foreground -mr-2"
                        >
                          Journey
                          <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      }
                    />
                    <div className="space-y-3">
                      {topWeaknesses.length > 0 ? (
                        <>
                          {/* Primary Focus - Highlighted */}
                          <div 
                            className="p-4 rounded-lg bg-gradient-to-r from-red-500/10 to-orange-500/10 border border-red-500/20 cursor-pointer hover:border-red-500/40 transition-colors"
                            onClick={() => navigate('/coach')}
                          >
                            <div className="flex items-center gap-2 mb-2">
                              <Target className="w-4 h-4 text-red-500" />
                              <span className="text-xs text-red-400 uppercase tracking-wide font-semibold">
                                #1 Priority
                              </span>
                            </div>
                            <p className="font-semibold capitalize">
                              {(topWeaknesses[0]?.subcategory || topWeaknesses[0]?.name || '').replace(/_/g, ' ')}
                            </p>
                            <p className="text-sm text-muted-foreground mt-1">
                              {topWeaknesses[0]?.occurrences || Math.round(topWeaknesses[0]?.decayed_score || 0)} occurrences · 
                              <span className="text-red-400"> Fix this first</span>
                            </p>
                          </div>
                          
                          {/* Other focus areas */}
                          {topWeaknesses.slice(1, 4).map((weakness, index) => (
                            <div 
                              key={index}
                              className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted/80 transition-colors cursor-pointer"
                              onClick={() => navigate('/progress')}
                              data-testid={`weakness-item-${index}`}
                            >
                              <div className="flex items-center gap-3">
                                <span className="text-xs text-muted-foreground font-mono">
                                  #{index + 2}
                                </span>
                                <div>
                                  <p className="font-medium text-sm capitalize">
                                    {(weakness.subcategory || weakness.name || '').replace(/_/g, ' ')}
                                  </p>
                                  <p className="text-xs text-muted-foreground capitalize">
                                    {weakness.category}
                                  </p>
                                </div>
                              </div>
                              <span className="text-xs font-mono text-muted-foreground">
                                {weakness.occurrences || Math.round(weakness.decayed_score || 0)}×
                              </span>
                            </div>
                          ))}
                        </>
                      ) : (
                        <div className="text-center py-8">
                          <Target className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                          <p className="text-muted-foreground text-sm mb-3">
                            Analyze games to discover your weaknesses
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

            {/* Quick Actions - More Specific */}
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
                    onClick={() => navigate('/progress')}
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
                    onClick={() => navigate('/coach')}
                    data-testid="quick-focus-btn"
                  >
                    <Target className="w-5 h-5" />
                    <span className="text-sm">Today's Focus</span>
                  </Button>
                </motion.div>
              </div>
            </AnimatedItem>
          </AnimatedList>
        )}
      </div>

      {/* Stats Detail Modal */}
      <StatsDetailModal 
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        type={modalType}
      />
    </Layout>
  );
};

export default Dashboard;
