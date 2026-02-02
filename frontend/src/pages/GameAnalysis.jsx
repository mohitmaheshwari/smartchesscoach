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
        const gameResponse = await fetch(`${API}/games/${gameId}`, {
          credentials: 'include'
        });
        if (!gameResponse.ok) {
          throw new Error('Game not found');
        }
        const gameData = await gameResponse.json();
        setGame(gameData);

        try {
          const analysisResponse = await fetch(`${API}/analysis/${gameId}`, {
            credentials: 'include'
          });
          if (analysisResponse.ok) {
            const analysisData = await analysisResponse.json();
            setAnalysis(analysisData);
          }
        } catch {
          // No existing analysis
        }
      } catch (error) {
        console.error('Error fetching game:', error);
        toast.error('Failed to load game');
        navigate('/import');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [gameId, navigate]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const response = await fetch(`${API}/analyze-game`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ game_id: gameId })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Analysis failed');
      }

      const data = await response.json();
      setAnalysis(data);
      toast.success('Analysis complete!');
    } catch (error) {
      toast.error(error.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleMoveChange = (moveNumber, move) => {
    setCurrentMoveNumber(moveNumber);
  };

  const getEvalIcon = (evaluation) => {
    switch (evaluation) {
      case 'blunder': return <AlertTriangle className="w-4 h-4 text-red-500" />;
      case 'mistake': return <AlertCircle className="w-4 h-4 text-orange-500" />;
      case 'inaccuracy': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case 'good': return <CheckCircle2 className="w-4 h-4 text-blue-500" />;
      case 'excellent': return <Star className="w-4 h-4 text-emerald-500" />;
      case 'brilliant': return <Sparkles className="w-4 h-4 text-cyan-500" />;
      default: return null;
    }
  };

  const getEvalClass = (evaluation) => {
    switch (evaluation) {
      case 'blunder': return 'border-l-red-500 bg-red-500/5';
      case 'mistake': return 'border-l-orange-500 bg-orange-500/5';
      case 'inaccuracy': return 'border-l-yellow-500 bg-yellow-500/5';
      case 'good': return 'border-l-blue-500 bg-blue-500/5';
      case 'excellent': return 'border-l-emerald-500 bg-emerald-500/5';
      case 'brilliant': return 'border-l-cyan-500 bg-cyan-500/5';
      default: return 'border-l-muted-foreground';
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

  return (
    <Layout user={user}>
      <div className="space-y-6" data-testid="game-analysis-page">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <Button 
              variant="ghost" 
              size="icon"
              onClick={() => navigate(-1)}
              data-testid="back-button"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                {game?.white_player} vs {game?.black_player}
              </h1>
              <p className="text-sm text-muted-foreground">
                {game?.platform} • {game?.result} • You played {game?.user_color}
              </p>
            </div>
          </div>
          {!analysis && (
            <Button 
              onClick={handleAnalyze}
              disabled={analyzing}
              data-testid="analyze-button"
              className="glow-primary"
            >
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

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Chess Board */}
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
                  <div className="text-center">
                    <p className="font-medium">Analyzing your game...</p>
                    <p className="text-sm text-muted-foreground">
                      Using RAG to find similar patterns from your history
                    </p>
                  </div>
                </div>
              ) : (
                <ChessBoardViewer
                  pgn={game?.pgn || ""}
                  userColor={game?.user_color || "white"}
                  onMoveChange={handleMoveChange}
                  commentary={analysis?.commentary || []}
                />
              )}
            </CardContent>
          </Card>

          {/* Right: Analysis/Commentary */}
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
                    {/* Summary Stats */}
                    <div className="grid grid-cols-4 gap-3">
                      <div className="text-center p-3 rounded-lg bg-red-500/10">
                        <p className="text-2xl font-bold text-red-500">{analysis.blunders}</p>
                        <p className="text-xs text-muted-foreground">Blunders</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-orange-500/10">
                        <p className="text-2xl font-bold text-orange-500">{analysis.mistakes}</p>
                        <p className="text-xs text-muted-foreground">Mistakes</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-yellow-500/10">
                        <p className="text-2xl font-bold text-yellow-500">{analysis.inaccuracies}</p>
                        <p className="text-xs text-muted-foreground">Inaccuracies</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-emerald-500/10">
                        <p className="text-2xl font-bold text-emerald-500">{analysis.best_moves}</p>
                        <p className="text-xs text-muted-foreground">Best Moves</p>
                      </div>
                    </div>

                    {/* Overall Summary */}
                    <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                          <Brain className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-sm mb-1">Coach's Summary</p>
                          <p className="text-sm text-muted-foreground">
                            {analysis.overall_summary}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Identified Patterns */}
                    {analysis.identified_patterns && analysis.identified_patterns.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium">Patterns Identified</p>
                        <div className="flex flex-wrap gap-2">
                          {analysis.identified_patterns.map((patternId, idx) => (
                            <Badge key={idx} variant="outline">
                              Pattern #{idx + 1}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="moves" className="mt-4">
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-2">
                        {analysis.commentary?.map((item, index) => (
                          <div 
                            key={index}
                            className={`p-3 rounded-lg border-l-4 ${getEvalClass(item.evaluation)} cursor-pointer transition-all hover:scale-[1.01] ${
                              currentMoveNumber === item.move_number ? 'ring-2 ring-primary' : ''
                            }`}
                            data-testid={`move-comment-${index}`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm font-medium">
                                  {item.move_number}. {item.move}
                                </span>
                                {getEvalIcon(item.evaluation)}
                              </div>
                              {item.evaluation && item.evaluation !== 'neutral' && (
                                <Badge variant="outline" className="text-xs capitalize">
                                  {item.evaluation}
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {item.comment}
                            </p>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </TabsContent>
                </Tabs>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 space-y-4">
                  <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                    <Brain className="w-8 h-8 text-primary" />
                  </div>
                  <div className="text-center">
                    <p className="font-medium">Ready for Analysis</p>
                    <p className="text-sm text-muted-foreground">
                      Click "Analyze with AI" to get personalized coaching feedback
                    </p>
                  </div>
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
