import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Layout from "@/components/Layout";
import StatsDetailModal from "@/components/StatsDetailModal";
import { toast } from "sonner";
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
  ChevronDown,
  Trophy,
  Star,
  Flame,
  Award,
  X,
  RefreshCw,
  Clock,
  CheckCircle2,
  FileQuestion,
  Play
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// Milestone celebration banner component
const MilestoneBanner = ({ milestone, onDismiss }) => {
  const iconMap = {
    trophy: <Trophy className="w-6 h-6" />,
    fire: <Flame className="w-6 h-6" />,
    star: <Star className="w-6 h-6" />,
    chart: <Award className="w-6 h-6" />
  };
  
  const rarityColors = {
    common: "from-green-500/20 to-emerald-500/20 border-green-500/30",
    rare: "from-blue-500/20 to-indigo-500/20 border-blue-500/30",
    epic: "from-purple-500/20 to-pink-500/20 border-purple-500/30"
  };
  
  const textColors = {
    common: "text-green-400",
    rare: "text-blue-400",
    epic: "text-purple-400"
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.95 }}
      className={`relative p-4 rounded-xl bg-gradient-to-r ${rarityColors[milestone.rarity]} border mb-6 overflow-hidden`}
      data-testid="milestone-banner"
    >
      {/* Animated background particles */}
      <div className="absolute inset-0 overflow-hidden">
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className={`absolute w-1 h-1 rounded-full ${textColors[milestone.rarity]}`}
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0, 1, 0],
              y: [-20, -40],
              x: [0, (i % 2 === 0 ? 10 : -10)]
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              delay: i * 0.3
            }}
            style={{ left: `${15 + i * 15}%`, top: '80%' }}
          />
        ))}
      </div>
      
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className={`p-3 rounded-full bg-background/50 ${textColors[milestone.rarity]}`}>
            {iconMap[milestone.icon] || <Trophy className="w-6 h-6" />}
          </div>
          <div>
            <p className={`text-xs uppercase tracking-wide font-bold ${textColors[milestone.rarity]}`}>
              Milestone Unlocked!
            </p>
            <p className="font-bold text-lg">{milestone.name}</p>
            <p className="text-sm text-muted-foreground">{milestone.description}</p>
          </div>
        </div>
        <button 
          onClick={onDismiss}
          className="p-2 hover:bg-background/50 rounded-full transition-colors"
        >
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
    </motion.div>
  );
};

// Game list item component for analyzed games
const GameListItem = ({ game, userRating, onNavigate, onReanalyze, isReanalyzing }) => {
  const opponent = game.user_color === 'white' ? game.black_player : game.white_player;
  const opponentRating = game.user_color === 'white' ? game.black_rating : game.white_rating;
  
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
      whileHover={{ x: 4 }}
      className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted/80 transition-colors cursor-pointer group"
      onClick={onNavigate}
      data-testid={`game-item-${game.game_id}`}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
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
            {!game.opening && game.platform && (
              <span>{game.platform}</span>
            )}
            {game.accuracy && (
              <span className="text-emerald-500">{game.accuracy.toFixed(1)}%</span>
            )}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors" />
      </div>
    </motion.div>
  );
};

// Queued game item with progress indicator
const QueuedGameItem = ({ game, onNavigate }) => {
  const opponent = game.user_color === 'white' ? game.black_player : game.white_player;
  const isProcessing = game.analysis_status === 'processing';
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between p-3 rounded-lg bg-amber-500/5 border border-amber-500/20 cursor-pointer group hover:bg-amber-500/10 transition-colors"
      onClick={onNavigate}
      data-testid={`queued-game-${game.game_id}`}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <div className="relative">
          <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold ${
            game.user_color === 'white' 
              ? 'bg-white text-black border border-border' 
              : 'bg-zinc-800 text-white'
          }`}>
            {game.user_color === 'white' ? 'W' : 'B'}
          </span>
          {isProcessing && (
            <div className="absolute -top-1 -right-1">
              <Loader2 className="w-3 h-3 text-amber-500 animate-spin" />
            </div>
          )}
        </div>
        
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="font-medium text-sm truncate">
              vs {opponent || 'Opponent'}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className={isProcessing ? 'text-amber-400' : 'text-muted-foreground'}>
              {isProcessing ? 'Analyzing...' : 'Waiting in queue'}
            </span>
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-2">
        {isProcessing ? (
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-amber-500/10">
            <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span className="text-xs text-amber-500 font-medium">Processing</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-muted">
            <Clock className="w-3 h-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Queued</span>
          </div>
        )}
      </div>
    </motion.div>
  );
};

// Not Analyzed Game Item - for games that need analysis
const NotAnalyzedGameItem = ({ game, onQueue, isQueuing }) => {
  const opponent = game.user_color === 'white' ? game.black_player : game.white_player;
  const opponentRating = game.user_color === 'white' ? game.black_rating : game.white_rating;
  
  // Determine result display
  const getResultDisplay = () => {
    if (!game.result) return null;
    if (game.result === '1-0') {
      return game.user_color === 'white' ? 
        <span className="text-emerald-500 font-medium">Won</span> : 
        <span className="text-red-500 font-medium">Lost</span>;
    }
    if (game.result === '0-1') {
      return game.user_color === 'black' ? 
        <span className="text-emerald-500 font-medium">Won</span> : 
        <span className="text-red-500 font-medium">Lost</span>;
    }
    return <span className="text-muted-foreground">Draw</span>;
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
      data-testid={`not-analyzed-game-${game.game_id}`}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
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
              <span className="text-xs text-muted-foreground">({opponentRating})</span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {getResultDisplay()}
            <span className="text-muted-foreground">• Not analyzed</span>
          </div>
        </div>
      </div>
      
      <Button
        size="sm"
        variant="outline"
        onClick={(e) => onQueue(game.game_id, e)}
        disabled={isQueuing}
        className="gap-1.5"
      >
        {isQueuing ? (
          <>
            <Loader2 className="w-3 h-3 animate-spin" />
            Queuing
          </>
        ) : (
          <>
            <Play className="w-3 h-3" />
            Analyze
          </>
        )}
      </Button>
    </motion.div>
  );
};

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState(null);
  const [opponentFilter, setOpponentFilter] = useState("all"); // all, stronger, equal, weaker
  const [newMilestone, setNewMilestone] = useState(null);
  const [activeTab, setActiveTab] = useState("analyzed"); // analyzed, in_queue, not_analyzed
  const [reanalyzing, setReanalyzing] = useState({}); // Track which games are being reanalyzed
  const [queuingAll, setQueuingAll] = useState(false); // Track batch queue status
  const [syncStatus, setSyncStatus] = useState(null); // Sync timer status
  const [dismissedMilestones, setDismissedMilestones] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('dismissedMilestones') || '[]');
    } catch {
      return [];
    }
  });

  const openStatsModal = (type) => {
    setModalType(type);
    setModalOpen(true);
  };
  
  // Queue a single game for analysis
  const handleQueueGame = async (gameId, e) => {
    if (e) e.stopPropagation();
    setReanalyzing(prev => ({ ...prev, [gameId]: true }));
    
    try {
      const res = await fetch(`${API}/games/${gameId}/reanalyze`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (res.ok) {
        toast.success("Game queued for analysis!");
        // Refetch stats to update lists
        const statsRes = await fetch(`${API}/dashboard-stats`, { credentials: 'include' });
        if (statsRes.ok) {
          const data = await statsRes.json();
          setStats(data);
        }
      } else {
        const error = await res.json();
        toast.error(error.detail || "Failed to queue game");
      }
    } catch (err) {
      toast.error("Failed to queue game for analysis");
    } finally {
      setReanalyzing(prev => ({ ...prev, [gameId]: false }));
    }
  };
  
  // Reanalyze a game (same as queue but for already analyzed games)
  const handleReanalyze = async (gameId, e) => {
    handleQueueGame(gameId, e);
  };
  
  // Check for new milestones
  useEffect(() => {
    const checkMilestones = async () => {
      try {
        const res = await fetch(`${API}/milestones`, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          const achieved = data.achieved || [];
          // Find the first milestone not yet dismissed
          const unshown = achieved.find(m => !dismissedMilestones.includes(m.id));
          if (unshown) {
            setNewMilestone(unshown);
          }
        }
      } catch (err) {
        console.error("Failed to check milestones:", err);
      }
    };
    
    checkMilestones();
  }, [dismissedMilestones]);
  
  const dismissMilestone = (id) => {
    const updated = [...dismissedMilestones, id];
    setDismissedMilestones(updated);
    localStorage.setItem('dismissedMilestones', JSON.stringify(updated));
    setNewMilestone(null);
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

  // Real-time queue polling - auto-refresh when games are being analyzed
  useEffect(() => {
    // Only poll if there are games in queue
    const queuedCount = stats?.queued_games || 0;
    if (queuedCount === 0) return;
    
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API}/dashboard-stats`, {
          credentials: 'include'
        });
        if (response.ok) {
          const newData = await response.json();
          const newQueuedCount = newData?.queued_games || 0;
          const oldQueuedCount = stats?.queued_games || 0;
          
          // If queue count changed, update stats
          if (newQueuedCount !== oldQueuedCount) {
            setStats(newData);
            
            // If a game finished (queue count decreased), show toast
            if (newQueuedCount < oldQueuedCount) {
              const gamesFinished = oldQueuedCount - newQueuedCount;
              toast.success(`${gamesFinished} game${gamesFinished > 1 ? 's' : ''} analyzed!`);
            }
          }
        }
      } catch (error) {
        console.error('Poll error:', error);
      }
    }, 5000); // Poll every 5 seconds
    
    return () => clearInterval(pollInterval);
  }, [stats?.queued_games]);

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
  const ratingImpact = stats?.rating_impact;

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
        {/* Milestone Celebration Banner */}
        <AnimatePresence>
          {newMilestone && (
            <MilestoneBanner 
              milestone={newMilestone} 
              onDismiss={() => dismissMilestone(newMilestone.id)} 
            />
          )}
        </AnimatePresence>
        
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
              {/* Games Section - With Tabs */}
              <AnimatedItem>
                <Card className="surface h-full">
                  <CardContent className="py-6">
                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                      <div className="flex items-center justify-between mb-4">
                        <TabsList className="grid w-fit grid-cols-3">
                          <TabsTrigger value="analyzed" className="gap-1.5" data-testid="analyzed-tab">
                            <CheckCircle2 className="w-3 h-3" />
                            Analyzed
                            {stats?.analyzed_games > 0 && (
                              <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-500">
                                {stats.analyzed_games}
                              </span>
                            )}
                          </TabsTrigger>
                          <TabsTrigger value="in_queue" className="gap-1.5" data-testid="in-queue-tab">
                            <Clock className="w-3 h-3" />
                            In Queue
                            {stats?.queued_games > 0 && (
                              <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-500">
                                {stats.queued_games}
                              </span>
                            )}
                          </TabsTrigger>
                          <TabsTrigger value="not_analyzed" className="gap-1.5" data-testid="not-analyzed-tab">
                            <FileQuestion className="w-3 h-3" />
                            Not Analyzed
                            {stats?.not_analyzed_games > 0 && (
                              <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-zinc-500/20 text-zinc-400">
                                {stats.not_analyzed_games}
                              </span>
                            )}
                          </TabsTrigger>
                        </TabsList>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => navigate('/import')}
                          className="text-muted-foreground hover:text-foreground -mr-2"
                        >
                          Import
                          <Import className="w-4 h-4 ml-1" />
                        </Button>
                      </div>
                      
                      {/* Analyzed Games Tab */}
                      <TabsContent value="analyzed" className="mt-0">
                        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                          {(stats?.analyzed_list || []).length > 0 ? (
                            (stats?.analyzed_list || []).map((game) => (
                              <GameListItem
                                key={game.game_id}
                                game={game}
                                userRating={userRating}
                                onNavigate={() => navigate(`/game/${game.game_id}`)}
                              />
                            ))
                          ) : (
                            <div className="text-center py-8">
                              <CheckCircle2 className="w-10 h-10 mx-auto mb-3 text-muted-foreground/30" />
                              <p className="text-muted-foreground text-sm">No analyzed games yet</p>
                              <p className="text-xs text-muted-foreground mt-1">Import games and analyze them to see insights</p>
                            </div>
                          )}
                        </div>
                      </TabsContent>
                      
                      {/* In Queue Tab */}
                      <TabsContent value="in_queue" className="mt-0">
                        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                          {(stats?.in_queue_list || []).length > 0 ? (
                            (stats?.in_queue_list || []).map((game) => (
                              <QueuedGameItem
                                key={game.game_id}
                                game={game}
                                onNavigate={() => navigate(`/game/${game.game_id}`)}
                              />
                            ))
                          ) : (
                            <div className="text-center py-8">
                              <Clock className="w-10 h-10 mx-auto mb-3 text-muted-foreground/30" />
                              <p className="text-muted-foreground text-sm">No games in queue</p>
                              <p className="text-xs text-muted-foreground mt-1">Games being analyzed will appear here</p>
                            </div>
                          )}
                        </div>
                      </TabsContent>
                      
                      {/* Not Analyzed Tab - NEW */}
                      <TabsContent value="not_analyzed" className="mt-0">
                        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                          {(stats?.not_analyzed_list || []).length > 0 ? (
                            (stats?.not_analyzed_list || []).map((game) => (
                              <NotAnalyzedGameItem
                                key={game.game_id}
                                game={game}
                                onQueue={handleQueueGame}
                                isQueuing={reanalyzing[game.game_id]}
                              />
                            ))
                          ) : (
                            <div className="text-center py-8">
                              <CheckCircle2 className="w-10 h-10 mx-auto mb-3 text-emerald-500/30" />
                              <p className="text-muted-foreground text-sm">All games analyzed!</p>
                              <p className="text-xs text-muted-foreground mt-1">Great work, all your games have been analyzed</p>
                            </div>
                          )}
                        </div>
                      </TabsContent>
                    </Tabs>
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
                      {/* Rating Impact Banner */}
                      {ratingImpact?.potential_gain > 0 && (
                        <div 
                          className="p-3 rounded-lg bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/20 cursor-pointer hover:border-green-500/40 transition-colors"
                          onClick={() => navigate('/focus')}
                          data-testid="rating-impact-card"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <TrendingUp className="w-4 h-4 text-green-500" />
                                <span className="text-xs text-green-400 uppercase tracking-wide font-semibold">
                                  Potential Gain
                                </span>
                              </div>
                              <p className="text-sm text-muted-foreground">
                                {ratingImpact.message}
                              </p>
                            </div>
                            <span className="text-2xl font-bold text-green-500">
                              +{ratingImpact.potential_gain}
                            </span>
                          </div>
                        </div>
                      )}
                      
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
