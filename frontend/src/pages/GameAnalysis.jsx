import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Layout from "@/components/Layout";
import ChessBoardViewer from "@/components/ChessBoardViewer";
import { toast } from "sonner";
import { 
  ArrowLeft, 
  Loader2, 
  Brain,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Star,
  Sparkles
} from "lucide-react";

const GameAnalysis = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMoveNumber, setCurrentMoveNumber] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const gameUrl = API + "/games/" + gameId;
        const gameResponse = await fetch(gameUrl, { credentials: "include" });
        if (!gameResponse.ok) throw new Error("Game not found");
        const gameData = await gameResponse.json();
        setGame(gameData);

        const analysisUrl = API + "/analysis/" + gameId;
        const analysisResponse = await fetch(analysisUrl, { credentials: "include" });
        if (analysisResponse.ok) {
          const analysisData = await analysisResponse.json();
          setAnalysis(analysisData);
        }
      } catch (error) {
        toast.error("Failed to load game");
        navigate("/import");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [gameId, navigate]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const url = API + "/analyze-game";
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ game_id: gameId })
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Analysis failed");
      }
      const data = await response.json();
      setAnalysis(data);
      toast.success("Analysis complete!");
    } catch (error) {
      toast.error(error.message || "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  // Safe data extraction
  const pgn = game ? game.pgn : "";
  const userColor = game ? game.user_color : "white";
  const whitePlayer = game ? game.white_player : "White";
  const blackPlayer = game ? game.black_player : "Black";
  const platform = game ? game.platform : "";
  const result = game ? game.result : "";
  
  const commentary = analysis ? analysis.commentary : [];
  const blunders = analysis ? analysis.blunders : 0;
  const mistakes = analysis ? analysis.mistakes : 0;
  const inaccuracies = analysis ? analysis.inaccuracies : 0;
  const bestMoves = analysis ? analysis.best_moves : 0;
  const summary = analysis ? analysis.overall_summary : "";
  const keyLesson = analysis ? analysis.key_lesson : "";
  
  // Get weaknesses - new format
  let weaknesses = [];
  if (analysis && analysis.weaknesses) {
    weaknesses = analysis.weaknesses;
  }
  
  // Get patterns - old format fallback  
  let patterns = [];
  if (analysis && analysis.identified_patterns) {
    patterns = analysis.identified_patterns;
  }

  const renderWeaknessBadge = (w, i) => {
    let name = "Pattern #" + (i + 1);
    if (w.display_name) {
      name = w.display_name;
    } else if (w.subcategory) {
      name = w.subcategory.split("_").join(" ");
    }
    return (
      <Badge key={i} variant="outline" className="text-xs capitalize">
        {name}
      </Badge>
    );
  };

  const renderPatternBadge = (p, i) => {
    return (
      <Badge key={i} variant="outline" className="text-xs">
        Pattern #{i + 1}
      </Badge>
    );
  };

  const renderWeaknessDetail = (w, i) => {
    let name = w.subcategory ? w.subcategory.split("_").join(" ") : "";
    if (w.display_name) name = w.display_name;
    return (
      <div key={i} className="p-2 rounded bg-muted/50 text-sm">
        <span className="font-medium capitalize">{name}</span>
        {w.description && (
          <p className="text-muted-foreground text-xs mt-1">{w.description}</p>
        )}
        {w.advice && (
          <p className="text-blue-600 dark:text-blue-400 text-xs mt-1">{w.advice}</p>
        )}
      </div>
    );
  };

  const getEvalColor = (ev) => {
    if (ev === "blunder") return "border-l-red-500 bg-red-500/5";
    if (ev === "mistake") return "border-l-orange-500 bg-orange-500/5";
    if (ev === "inaccuracy") return "border-l-yellow-500 bg-yellow-500/5";
    if (ev === "good") return "border-l-blue-500 bg-blue-500/5";
    if (ev === "excellent") return "border-l-emerald-500 bg-emerald-500/5";
    if (ev === "brilliant") return "border-l-cyan-500 bg-cyan-500/5";
    return "border-l-muted-foreground";
  };

  const getEvalIcon = (ev) => {
    if (ev === "blunder") return <AlertTriangle className="w-4 h-4 text-red-500" />;
    if (ev === "mistake") return <AlertCircle className="w-4 h-4 text-orange-500" />;
    if (ev === "inaccuracy") return <AlertCircle className="w-4 h-4 text-yellow-500" />;
    if (ev === "good") return <CheckCircle2 className="w-4 h-4 text-blue-500" />;
    if (ev === "excellent") return <Star className="w-4 h-4 text-emerald-500" />;
    if (ev === "brilliant") return <Sparkles className="w-4 h-4 text-cyan-500" />;
    return null;
  };

  const renderMoveComment = (item, index) => {
    const colorClass = getEvalColor(item.evaluation);
    const icon = getEvalIcon(item.evaluation);
    const isActive = currentMoveNumber === item.move_number;
    
    return (
      <div 
        key={index}
        className={"p-3 rounded-lg border-l-4 " + colorClass + " " + (isActive ? "ring-2 ring-primary" : "")}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-medium">
              {item.move_number}. {item.move}
            </span>
            {icon}
          </div>
          {item.evaluation && item.evaluation !== "neutral" && (
            <Badge variant="outline" className="text-xs capitalize">
              {item.evaluation}
            </Badge>
          )}
        </div>
        
        {item.player_intention && (
          <p className="text-sm text-blue-600 dark:text-blue-400 italic mb-2">
            &ldquo;{item.player_intention}&rdquo;
          </p>
        )}
        
        {item.coach_response && (
          <p className="text-sm text-muted-foreground mb-2">{item.coach_response}</p>
        )}
        
        {!item.coach_response && item.comment && (
          <p className="text-sm text-muted-foreground mb-2">{item.comment}</p>
        )}
        
        {item.better_move && (
          <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium mb-2">
            Better: {item.better_move}
          </p>
        )}
        
        {item.explanation && (
          <div className="mt-2 pt-2 border-t border-muted space-y-1">
            {item.explanation.thinking_error && (
              <p className="text-xs">
                <span className="font-medium text-red-500">Thinking:</span>{" "}
                <span className="text-muted-foreground">{item.explanation.thinking_error}</span>
              </p>
            )}
            {item.explanation.one_repeatable_rule && (
              <p className="text-xs">
                <span className="font-medium text-emerald-500">Rule:</span>{" "}
                <span className="text-muted-foreground">{item.explanation.one_repeatable_rule}</span>
              </p>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <Layout user={user}>
      <div className="space-y-6" data-testid="game-analysis-page">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                {whitePlayer} vs {blackPlayer}
              </h1>
              <p className="text-sm text-muted-foreground">
                {platform} • {result} • You played {userColor}
              </p>
            </div>
          </div>
          {!analysis && (
            <Button onClick={handleAnalyze} disabled={analyzing} className="glow-primary">
              {analyzing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Brain className="w-4 h-4 mr-2" />
                  Analyze with AI
                </>
              )}
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <span className="w-6 h-6 rounded bg-primary/10 flex items-center justify-center text-xs font-bold">♟</span>
                Interactive Board
              </CardTitle>
            </CardHeader>
            <CardContent>
              {analyzing ? (
                <div className="flex flex-col items-center justify-center py-16 space-y-4">
                  <div className="relative">
                    <div className="w-16 h-16 rounded-full border-4 border-primary border-t-transparent animate-spin" />
                    <Brain className="w-8 h-8 text-primary absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
                  </div>
                  <p className="font-medium">Analyzing your game...</p>
                </div>
              ) : (
                <ChessBoardViewer
                  pgn={pgn}
                  userColor={userColor}
                  onMoveChange={setCurrentMoveNumber}
                  commentary={commentary}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                AI Coach Commentary
              </CardTitle>
            </CardHeader>
            <CardContent>
              {analysis ? (
                <Tabs defaultValue="summary" className="w-full">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="summary">Summary</TabsTrigger>
                    <TabsTrigger value="moves">Move Analysis</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="summary" className="space-y-4 mt-4">
                    <div className="grid grid-cols-4 gap-3">
                      <div className="text-center p-3 rounded-lg bg-red-500/10">
                        <p className="text-2xl font-bold text-red-500">{blunders}</p>
                        <p className="text-xs text-muted-foreground">Blunders</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-orange-500/10">
                        <p className="text-2xl font-bold text-orange-500">{mistakes}</p>
                        <p className="text-xs text-muted-foreground">Mistakes</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-yellow-500/10">
                        <p className="text-2xl font-bold text-yellow-500">{inaccuracies}</p>
                        <p className="text-xs text-muted-foreground">Inaccuracies</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-emerald-500/10">
                        <p className="text-2xl font-bold text-emerald-500">{bestMoves}</p>
                        <p className="text-xs text-muted-foreground">Best Moves</p>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                          <Brain className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-sm mb-1">Coach&apos;s Summary</p>
                          <p className="text-sm text-muted-foreground">{summary}</p>
                        </div>
                      </div>
                    </div>

                    {keyLesson && (
                      <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                        <p className="text-sm font-medium text-amber-600 dark:text-amber-400 flex items-center gap-2">
                          <Sparkles className="w-4 h-4" />
                          Key Lesson
                        </p>
                        <p className="text-sm mt-1">{keyLesson}</p>
                      </div>
                    )}

                    {(weaknesses.length > 0 || patterns.length > 0) && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium">Patterns Identified</p>
                        <div className="flex flex-wrap gap-2">
                          {weaknesses.length > 0 
                            ? weaknesses.map(renderWeaknessBadge)
                            : patterns.map(renderPatternBadge)
                          }
                        </div>
                        {weaknesses.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {weaknesses.map(renderWeaknessDetail)}
                          </div>
                        )}
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="moves" className="mt-4">
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-3">
                        {commentary.map(renderMoveComment)}
                      </div>
                    </ScrollArea>
                  </TabsContent>
                </Tabs>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 space-y-4">
                  <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                    <Brain className="w-8 h-8 text-primary" />
                  </div>
                  <p className="font-medium">Ready for Analysis</p>
                  <p className="text-sm text-muted-foreground">
                    Click &ldquo;Analyze with AI&rdquo; to get personalized coaching
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </Layout>
  );
};

export default GameAnalysis;
