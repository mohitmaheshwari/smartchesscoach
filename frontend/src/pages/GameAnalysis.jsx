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
        } catch (err) {
          console.log('No analysis yet');
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

  const handleMoveChange = (moveNumber) => {
    setCurrentMoveNumber(moveNumber);
  };

  const getEvalIcon = (evaluation) => {
    if (evaluation === 'blunder') return <AlertTriangle className="w-4 h-4 text-red-500" />;
    if (evaluation === 'mistake') return <AlertCircle className="w-4 h-4 text-orange-500" />;
    if (evaluation === 'inaccuracy') return <AlertCircle className="w-4 h-4 text-yellow-500" />;
    if (evaluation === 'good') return <CheckCircle2 className="w-4 h-4 text-blue-500" />;
    if (evaluation === 'excellent') return <Star className="w-4 h-4 text-emerald-500" />;
    if (evaluation === 'brilliant') return <Sparkles className="w-4 h-4 text-cyan-500" />;
    return null;
  };

  const getEvalClass = (evaluation) => {
    if (evaluation === 'blunder') return 'border-l-red-500 bg-red-500/5';
    if (evaluation === 'mistake') return 'border-l-orange-500 bg-orange-500/5';
    if (evaluation === 'inaccuracy') return 'border-l-yellow-500 bg-yellow-500/5';
    if (evaluation === 'good') return 'border-l-blue-500 bg-blue-500/5';
    if (evaluation === 'excellent') return 'border-l-emerald-500 bg-emerald-500/5';
    if (evaluation === 'brilliant') return 'border-l-cyan-500 bg-cyan-500/5';
    return 'border-l-muted-foreground';
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

  const gamePgn = game ? game.pgn : "";
  const gameUserColor = game ? game.user_color : "white";
  const gameWhite = game ? game.white_player : "White";
  const gameBlack = game ? game.black_player : "Black";
  const gamePlatform = game ? game.platform : "";
  const gameResult = game ? game.result : "";
  
  const analysisCommentary = analysis ? analysis.commentary : [];
  const analysisBlunders = analysis ? analysis.blunders : 0;
  const analysisMistakes = analysis ? analysis.mistakes : 0;
  const analysisInaccuracies = analysis ? analysis.inaccuracies : 0;
  const analysisBestMoves = analysis ? analysis.best_moves : 0;
  const analysisSummary = analysis ? analysis.overall_summary : "";
  const analysisPatterns = analysis ? analysis.identified_patterns : [];

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
                {gameWhite} vs {gameBlack}
              </h1>
              <p className="text-sm text-muted-foreground">
                {gamePlatform} • {gameResult} • You played {gameUserColor}
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
                      Using RAG to find similar patterns
                    </p>
                  </div>
                </div>
              ) : (
                <ChessBoardViewer
                  pgn={gamePgn}
                  userColor={gameUserColor}
                  onMoveChange={handleMoveChange}
                  commentary={analysisCommentary}
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
                        <p className="text-2xl font-bold text-red-500">{analysisBlunders}</p>
                        <p className="text-xs text-muted-foreground">Blunders</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-orange-500/10">
                        <p className="text-2xl font-bold text-orange-500">{analysisMistakes}</p>
                        <p className="text-xs text-muted-foreground">Mistakes</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-yellow-500/10">
                        <p className="text-2xl font-bold text-yellow-500">{analysisInaccuracies}</p>
                        <p className="text-xs text-muted-foreground">Inaccuracies</p>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-emerald-500/10">
                        <p className="text-2xl font-bold text-emerald-500">{analysisBestMoves}</p>
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
                          <p className="font-medium text-sm mb-1">Coach&apos;s Summary</p>
                          <p className="text-sm text-muted-foreground">{analysisSummary}</p>
                        </div>
                      </div>
                    </div>

                    {/* Identified Patterns */}
                    {((analysis && analysis.weaknesses) || analysisPatterns).length > 0 && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium">Patterns Identified</p>
                        <div className="flex flex-wrap gap-2">
                          {(analysis && analysis.weaknesses ? analysis.weaknesses : []).map((weakness, idx) => (
                            <Badge 
                              key={idx} 
                              variant="outline"
                              className="text-xs capitalize"
                            >
                              {weakness.display_name || (weakness.subcategory ? weakness.subcategory.replace(/_/g, ' ') : 'Pattern #' + (idx + 1))}
                            </Badge>
                          ))}
                          {/* Fallback for old data */}
                          {(!analysis || !analysis.weaknesses) && analysisPatterns.map((patternId, idx) => (
                            <Badge key={idx} variant="outline">
                              Pattern #{idx + 1}
                            </Badge>
                          ))}
                        </div>
                        {/* Show weakness details */}
                        {analysis && analysis.weaknesses && analysis.weaknesses.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {analysis.weaknesses.map((w, idx) => (
                              <div key={idx} className="p-2 rounded bg-muted/50 text-sm">
                                <span className="font-medium capitalize">{w.display_name || (w.subcategory ? w.subcategory.replace(/_/g, ' ') : '')}</span>
                                {w.description && (
                                  <p className="text-muted-foreground text-xs mt-1">{w.description}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Key Lesson */}
                    {analysis.key_lesson && (
                      <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                        <p className="text-sm font-medium text-amber-600 dark:text-amber-400 flex items-center gap-2">
                          <Sparkles className="w-4 h-4" />
                          Key Lesson
                        </p>
                        <p className="text-sm mt-1">{analysis.key_lesson}</p>
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="moves" className="mt-4">
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-3">
                        {analysisCommentary.map((item, index) => (
                          <div 
                            key={index}
                            className={`p-3 rounded-lg border-l-4 ${getEvalClass(item.evaluation)} cursor-pointer transition-all hover:scale-[1.01] ${
                              currentMoveNumber === item.move_number ? 'ring-2 ring-primary' : ''
                            }`}
                            data-testid={`move-comment-${index}`}
                          >
                            <div className="flex items-center justify-between mb-2">
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
                            
                            {/* Player Intention - What they were trying to do */}
                            {item.player_intention && (
                              <p className="text-sm text-blue-600 dark:text-blue-400 italic mb-2">
                                &ldquo;{item.player_intention}&rdquo;
                              </p>
                            )}
                            
                            {/* Coach Response - The main explanation */}
                            {item.coach_response && (
                              <p className="text-sm text-muted-foreground mb-2">{item.coach_response}</p>
                            )}
                            
                            {/* Fallback to old comment field */}
                            {!item.coach_response && item.comment && (
                              <p className="text-sm text-muted-foreground mb-2">{item.comment}</p>
                            )}
                            
                            {/* Better Move suggestion */}
                            {item.better_move && (
                              <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                                Better: {item.better_move}
                              </p>
                            )}
                            
                            {/* Expanded Explanation for mistakes/blunders */}
                            {item.explanation && (item.evaluation === 'blunder' || item.evaluation === 'mistake' || item.evaluation === 'inaccuracy') && (
                              <div className="mt-2 pt-2 border-t border-muted space-y-1">
                                {item.explanation.thinking_error && (
                                  <p className="text-xs">
                                    <span className="font-medium text-red-500">Thinking:</span>{' '}
                                    <span className="text-muted-foreground">{item.explanation.thinking_error}</span>
                                  </p>
                                )}
                                {item.explanation.one_repeatable_rule && (
                                  <p className="text-xs">
                                    <span className="font-medium text-emerald-500">Rule:</span>{' '}
                                    <span className="text-muted-foreground">{item.explanation.one_repeatable_rule}</span>
                                  </p>
                                )}
                              </div>
                            )}
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
                      Click &ldquo;Analyze with AI&rdquo; to get personalized coaching feedback
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
