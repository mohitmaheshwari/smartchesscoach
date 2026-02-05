import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { API } from "@/App";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  BookOpen, 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle,
  CheckCircle,
  Target,
  Loader2,
  ChevronDown,
  ChevronUp
} from "lucide-react";

const OpeningRepertoire = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedWhite, setExpandedWhite] = useState(false);
  const [expandedBlack, setExpandedBlack] = useState(false);

  useEffect(() => {
    fetchRepertoire();
  }, []);

  const fetchRepertoire = async () => {
    try {
      const res = await fetch(`${API}/openings/repertoire`, { credentials: "include" });
      if (res.ok) {
        setData(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch opening repertoire:", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="border-border/50">
        <CardContent className="py-12 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.has_data) {
    return (
      <Card className="border-border/50">
        <CardContent className="py-8 text-center">
          <BookOpen className="w-10 h-10 mx-auto mb-3 text-muted-foreground/50" />
          <p className="text-muted-foreground">Import and analyze games to see your opening repertoire</p>
        </CardContent>
      </Card>
    );
  }

  const getWinRateColor = (rate) => {
    if (rate >= 60) return "text-green-500";
    if (rate >= 40) return "text-amber-500";
    return "text-red-500";
  };

  const getWinRateBg = (rate) => {
    if (rate >= 60) return "bg-green-500/10";
    if (rate >= 40) return "bg-amber-500/10";
    return "bg-red-500/10";
  };

  const OpeningCard = ({ opening, color }) => (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-3 rounded-lg bg-card border border-border/50 hover:border-border transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${color === 'white' ? 'bg-zinc-100' : 'bg-zinc-800 border border-zinc-600'}`} />
            <h4 className="font-medium text-sm truncate">{opening.name}</h4>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
            <span>{opening.games_played} games</span>
            <span className="text-green-500">{opening.wins}W</span>
            <span className="text-red-500">{opening.losses}L</span>
            {opening.draws > 0 && <span className="text-zinc-500">{opening.draws}D</span>}
          </div>
        </div>
        
        <div className="text-right">
          <div className={`text-lg font-bold ${getWinRateColor(opening.win_rate)}`}>
            {opening.win_rate}%
          </div>
          <div className="text-[10px] text-muted-foreground">win rate</div>
        </div>
      </div>
      
      {opening.mistakes_per_game > 0 && (
        <div className="mt-2 pt-2 border-t border-border/50">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Mistakes/game</span>
            <span className={opening.mistakes_per_game > 2 ? "text-red-500 font-medium" : "text-muted-foreground"}>
              {opening.mistakes_per_game}
            </span>
          </div>
          
          {opening.common_mistakes?.length > 0 && opening.common_mistakes[0].examples?.length > 0 && (
            <div className="mt-1.5 text-[10px] text-amber-500/80">
              Common: {opening.common_mistakes[0].examples[0]?.lesson?.substring(0, 60) || opening.common_mistakes[0].type}...
            </div>
          )}
        </div>
      )}
    </motion.div>
  );

  return (
    <div className="space-y-6">
      {/* Coaching Focus Banner */}
      {data.coaching_focus && data.coaching_focus.area !== "maintain" && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 rounded-xl bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20"
        >
          <div className="flex items-start gap-3">
            <Target className="w-5 h-5 text-amber-500 mt-0.5" />
            <div>
              <h3 className="font-semibold text-sm text-amber-500">Coach's Focus Area</h3>
              <p className="text-sm text-foreground/80 mt-1">{data.coaching_focus.message}</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Problem Openings */}
      {data.problem_openings?.length > 0 && (
        <Card className="border-red-500/20 bg-red-500/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-500" />
              Problem Openings
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-2">
              {data.problem_openings.map((problem, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 rounded bg-background/50">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${problem.color === 'white' ? 'bg-zinc-100' : 'bg-zinc-800 border border-zinc-600'}`} />
                    <span className="text-sm font-medium">{problem.name}</span>
                  </div>
                  <span className="text-xs text-red-500">{problem.message}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recommendations */}
      {data.recommendations?.length > 0 && (
        <Card className="border-border/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-primary" />
              Personalized Recommendations
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-3">
              {data.recommendations.map((rec, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-muted/30 border border-border/50">
                  <div className="flex items-start gap-2">
                    <Badge 
                      variant={rec.priority === "high" ? "destructive" : rec.priority === "medium" ? "secondary" : "outline"}
                      className="text-[10px] px-1.5 py-0"
                    >
                      {rec.priority}
                    </Badge>
                    <div className="flex-1">
                      <p className="text-sm">{rec.message}</p>
                      {rec.suggestion && (
                        <p className="text-xs text-muted-foreground mt-1.5">
                          💡 {rec.suggestion}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-lg bg-card border border-border/50 text-center">
          <div className="text-2xl font-bold">{data.total_games}</div>
          <div className="text-xs text-muted-foreground">Total Games</div>
        </div>
        <div className="p-3 rounded-lg bg-card border border-border/50 text-center">
          <div className="text-2xl font-bold">{data.games_as_white}</div>
          <div className="text-xs text-muted-foreground">As White</div>
        </div>
        <div className="p-3 rounded-lg bg-card border border-border/50 text-center">
          <div className="text-2xl font-bold">{data.games_as_black}</div>
          <div className="text-xs text-muted-foreground">As Black</div>
        </div>
      </div>

      {/* White Repertoire */}
      <Card className="border-border/50">
        <CardHeader 
          className="pb-3 cursor-pointer"
          onClick={() => setExpandedWhite(!expandedWhite)}
        >
          <CardTitle className="text-base flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-zinc-100 border border-zinc-300" />
              White Repertoire
              <Badge variant="outline" className="text-xs ml-2">
                {data.white_repertoire?.length || 0} openings
              </Badge>
            </div>
            {expandedWhite ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </CardTitle>
        </CardHeader>
        {expandedWhite && (
          <CardContent className="pt-0">
            <div className="space-y-2">
              {data.white_repertoire?.map((opening, idx) => (
                <OpeningCard key={idx} opening={opening} color="white" />
              ))}
            </div>
          </CardContent>
        )}
      </Card>

      {/* Black Repertoire */}
      <Card className="border-border/50">
        <CardHeader 
          className="pb-3 cursor-pointer"
          onClick={() => setExpandedBlack(!expandedBlack)}
        >
          <CardTitle className="text-base flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-zinc-800 border border-zinc-600" />
              Black Repertoire
              <Badge variant="outline" className="text-xs ml-2">
                {data.black_repertoire?.length || 0} openings
              </Badge>
            </div>
            {expandedBlack ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </CardTitle>
        </CardHeader>
        {expandedBlack && (
          <CardContent className="pt-0">
            <div className="space-y-2">
              {data.black_repertoire?.map((opening, idx) => (
                <OpeningCard key={idx} opening={opening} color="black" />
              ))}
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
};

export default OpeningRepertoire;
