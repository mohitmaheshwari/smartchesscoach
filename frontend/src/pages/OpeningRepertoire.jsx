import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  BookOpen, 
  ChevronRight, 
  Trophy,
  Target,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Loader2,
  Crown,
  Swords,
  X
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API } from "@/App";

const OpeningCard = ({ opening, onClick }) => {
  const winRate = opening.win_rate || 0;
  const isGoodWinRate = winRate >= 50;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      className="cursor-pointer"
      onClick={onClick}
    >
      <Card className={`border-border/50 hover:border-primary/50 transition-all ${
        opening.in_library ? "bg-card" : "bg-card/50"
      }`}>
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1">
              <h3 className="font-semibold text-sm">{opening.name}</h3>
              <p className="text-xs text-muted-foreground mt-1">
                {opening.games_played} games played
              </p>
            </div>
            {opening.in_library && (
              <Badge variant="secondary" className="text-xs">
                <BookOpen className="w-3 h-3 mr-1" />
                In Library
              </Badge>
            )}
          </div>
          
          <div className="flex items-center gap-4 mt-3">
            <div className="flex items-center gap-1">
              {isGoodWinRate ? (
                <TrendingUp className="w-4 h-4 text-green-400" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-400" />
              )}
              <span className={`text-sm font-medium ${
                isGoodWinRate ? "text-green-400" : "text-red-400"
              }`}>
                {winRate.toFixed(0)}%
              </span>
            </div>
            
            {opening.learning_progress > 0 && (
              <div className="flex-1">
                <Progress 
                  value={opening.learning_progress * 10} 
                  className="h-1.5"
                />
              </div>
            )}
          </div>
          
          {opening.traps_learned?.length > 0 && (
            <div className="flex items-center gap-1 mt-2 text-xs text-amber-400">
              <Target className="w-3 h-3" />
              {opening.traps_learned.length} trap{opening.traps_learned.length > 1 ? 's' : ''} learned
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};

const RecommendedCard = ({ opening, onClick }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    whileHover={{ scale: 1.02 }}
    className="cursor-pointer"
    onClick={onClick}
  >
    <Card className="border-primary/30 bg-primary/5 hover:bg-primary/10 transition-all">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-primary/20">
            <Sparkles className="w-4 h-4 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-sm">{opening.name}</h3>
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
              {opening.description}
            </p>
            <p className="text-xs text-primary mt-2">
              {opening.reason}
            </p>
          </div>
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        </div>
      </CardContent>
    </Card>
  </motion.div>
);

const OpeningRepertoire = () => {
  const navigate = useNavigate();
  const [repertoire, setRepertoire] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("white");
  const [showAllOpenings, setShowAllOpenings] = useState(false);
  const [allOpenings, setAllOpenings] = useState([]);
  
  useEffect(() => {
    const fetchRepertoire = async () => {
      try {
        const res = await fetch(`${API}/openings/repertoire`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          setRepertoire(data);
        }
        
        // Also fetch all openings for the browse modal
        const libRes = await fetch(`${API}/openings/library`, {
          credentials: "include"
        });
        if (libRes.ok) {
          const libData = await libRes.json();
          setAllOpenings(libData.openings || []);
        }
      } catch (err) {
        console.error("Error fetching repertoire:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchRepertoire();
  }, []);
  
  const handleOpeningClick = (opening) => {
    if (opening.library_key || opening.key) {
      navigate(`/openings/${opening.library_key || opening.key}`);
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border/50 bg-card/50">
        <div className="max-w-6xl mx-auto px-4 py-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-primary/20">
              <BookOpen className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Opening Training Lab</h1>
              <p className="text-sm text-muted-foreground">
                Master your openings with personalized lessons
              </p>
            </div>
          </div>
          
          {/* Stats */}
          <div className="flex gap-4 mt-4">
            <div className="flex items-center gap-2 text-sm">
              <Trophy className="w-4 h-4 text-amber-400" />
              <span>{repertoire?.total_openings_played || 0} openings played</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <BookOpen className="w-4 h-4 text-primary" />
              <span>{repertoire?.library_openings_available || 0} lessons available</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="white" className="gap-2">
              <Crown className="w-4 h-4" />
              White Repertoire
            </TabsTrigger>
            <TabsTrigger value="black" className="gap-2">
              <Swords className="w-4 h-4" />
              Black Repertoire
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="white" className="space-y-6">
            {/* Recommended for White */}
            {repertoire?.recommended_white?.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  Recommended for You
                </h2>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {repertoire.recommended_white.map((opening, i) => (
                    <RecommendedCard 
                      key={i} 
                      opening={opening}
                      onClick={() => handleOpeningClick(opening)}
                    />
                  ))}
                </div>
              </div>
            )}
            
            {/* Your White Openings */}
            <div>
              <h2 className="text-lg font-semibold mb-3">Your White Openings</h2>
              {repertoire?.white_repertoire?.length > 0 ? (
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {repertoire.white_repertoire.map((opening, i) => (
                    <OpeningCard 
                      key={i} 
                      opening={opening}
                      onClick={() => handleOpeningClick(opening)}
                    />
                  ))}
                </div>
              ) : (
                <Card className="border-dashed">
                  <CardContent className="p-8 text-center">
                    <p className="text-muted-foreground">
                      Play some games as White to build your repertoire!
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
          
          <TabsContent value="black" className="space-y-6">
            {/* Recommended for Black */}
            {repertoire?.recommended_black?.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  Recommended for You
                </h2>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {repertoire.recommended_black.map((opening, i) => (
                    <RecommendedCard 
                      key={i} 
                      opening={opening}
                      onClick={() => handleOpeningClick(opening)}
                    />
                  ))}
                </div>
              </div>
            )}
            
            {/* Your Black Openings */}
            <div>
              <h2 className="text-lg font-semibold mb-3">Your Black Openings</h2>
              {repertoire?.black_repertoire?.length > 0 ? (
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {repertoire.black_repertoire.map((opening, i) => (
                    <OpeningCard 
                      key={i} 
                      opening={opening}
                      onClick={() => handleOpeningClick(opening)}
                    />
                  ))}
                </div>
              ) : (
                <Card className="border-dashed">
                  <CardContent className="p-8 text-center">
                    <p className="text-muted-foreground">
                      Play some games as Black to build your repertoire!
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>
        </Tabs>
        
        {/* Browse All Openings */}
        <div className="mt-8 pt-6 border-t border-border/50">
          <Button 
            variant="outline" 
            className="w-full"
            onClick={() => setShowAllOpenings(true)}
          >
            <BookOpen className="w-4 h-4 mr-2" />
            Browse All Opening Lessons
          </Button>
        </div>
        
        {/* All Openings Modal */}
        {showAllOpenings && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-background rounded-lg max-w-3xl w-full max-h-[80vh] overflow-hidden">
              <div className="p-4 border-b flex items-center justify-between">
                <h2 className="text-lg font-semibold">All Opening Lessons</h2>
                <Button variant="ghost" size="sm" onClick={() => setShowAllOpenings(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <div className="p-4 overflow-y-auto max-h-[60vh]">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {allOpenings.map((opening) => (
                    <Card 
                      key={opening.key}
                      className="cursor-pointer hover:bg-accent/50 transition-colors"
                      onClick={() => {
                        navigate(`/openings/${opening.key}`);
                        setShowAllOpenings(false);
                      }}
                    >
                      <CardContent className="p-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="font-medium text-sm">{opening.name}</h3>
                            <p className="text-xs text-muted-foreground">{opening.eco}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={opening.color === "white" ? "outline" : "secondary"}>
                              {opening.color}
                            </Badge>
                            {opening.trap_count > 0 && (
                              <Badge variant="destructive" className="text-xs">
                                {opening.trap_count} traps
                              </Badge>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default OpeningRepertoire;
