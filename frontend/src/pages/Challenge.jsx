import { useState, useEffect, useCallback } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { 
  Target, 
  Loader2, 
  CheckCircle2, 
  XCircle,
  RefreshCw,
  Brain,
  Trophy,
  Zap,
  ChevronRight,
  Lightbulb
} from "lucide-react";

const Challenge = ({ user }) => {
  const [patterns, setPatterns] = useState([]);
  const [currentPuzzle, setCurrentPuzzle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [game, setGame] = useState(new Chess());
  const [puzzleState, setPuzzleState] = useState("waiting"); // waiting, playing, solved, failed
  const [attempts, setAttempts] = useState(0);
  const [showHint, setShowHint] = useState(false);
  const [stats, setStats] = useState({ solved: 0, attempted: 0, streak: 0 });
  const [selectedPattern, setSelectedPattern] = useState(null);

  // Fetch user's weakness patterns
  useEffect(() => {
    const fetchPatterns = async () => {
      try {
        const response = await fetch(`${API}/patterns`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          setPatterns(data);
        }
      } catch (error) {
        console.error('Error fetching patterns:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchPatterns();
  }, []);

  // Generate a puzzle based on weakness
  const generatePuzzle = async (pattern = null) => {
    setGenerating(true);
    setShowHint(false);
    setPuzzleState("waiting");
    
    const targetPattern = pattern || selectedPattern || (patterns.length > 0 ? patterns[0] : null);
    
    try {
      const response = await fetch(`${API}/generate-puzzle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          pattern_id: targetPattern?.pattern_id,
          category: targetPattern?.category || "tactical",
          subcategory: targetPattern?.subcategory || "general"
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate puzzle');
      }

      const puzzle = await response.json();
      setCurrentPuzzle(puzzle);
      
      // Set up the board with the puzzle position
      const newGame = new Chess();
      if (puzzle.fen) {
        newGame.load(puzzle.fen);
      }
      setGame(newGame);
      setPuzzleState("playing");
      setAttempts(0);
      
    } catch (error) {
      toast.error('Failed to generate puzzle');
      console.error(error);
    } finally {
      setGenerating(false);
    }
  };

  // Handle piece drop (make a move)
  const onDrop = useCallback((sourceSquare, targetSquare) => {
    if (puzzleState !== "playing") return false;

    try {
      const move = game.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: 'q' // Always promote to queen for simplicity
      });

      if (move === null) return false;

      // Check if this is the correct move
      const isCorrect = currentPuzzle?.solution?.some(
        sol => sol.from === sourceSquare && sol.to === targetSquare
      ) || (currentPuzzle?.solution_san === move.san);

      if (isCorrect) {
        // Correct move!
        setPuzzleState("solved");
        setStats(prev => ({
          solved: prev.solved + 1,
          attempted: prev.attempted + 1,
          streak: prev.streak + 1
        }));
        toast.success("Correct! Well done!");
      } else {
        // Wrong move
        setAttempts(prev => prev + 1);
        
        if (attempts >= 2) {
          // Too many attempts
          setPuzzleState("failed");
          setStats(prev => ({
            ...prev,
            attempted: prev.attempted + 1,
            streak: 0
          }));
          toast.error("Not quite. The solution was: " + (currentPuzzle?.solution_san || "hidden"));
        } else {
          // Allow retry
          game.undo();
          toast.error("Not the best move. Try again!");
          return false;
        }
      }

      setGame(new Chess(game.fen()));
      return true;

    } catch (e) {
      return false;
    }
  }, [game, puzzleState, currentPuzzle, attempts]);

  const getCategoryColor = (category) => {
    const colors = {
      tactical: 'bg-red-500/10 text-red-500 border-red-500/20',
      positional: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
      endgame: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
      opening: 'bg-green-500/10 text-green-500 border-green-500/20'
    };
    return colors[category] || 'bg-muted text-muted-foreground';
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
      <div className="space-y-8" data-testid="challenge-page">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Challenge Mode</h1>
          <p className="text-muted-foreground">
            Practice puzzles based on your specific weaknesses
          </p>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Solved</p>
                  <p className="text-2xl font-bold text-emerald-500">{stats.solved}</p>
                </div>
                <Trophy className="w-8 h-8 text-emerald-500/50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Attempted</p>
                  <p className="text-2xl font-bold">{stats.attempted}</p>
                </div>
                <Target className="w-8 h-8 text-muted-foreground/50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Streak</p>
                  <p className="text-2xl font-bold text-primary">{stats.streak}</p>
                </div>
                <Zap className="w-8 h-8 text-primary/50" />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Weakness Selection */}
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="text-lg">Your Weaknesses</CardTitle>
              <CardDescription>Select a weakness to practice</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {patterns.length > 0 ? (
                patterns.slice(0, 6).map((pattern) => (
                  <button
                    key={pattern.pattern_id}
                    onClick={() => {
                      setSelectedPattern(pattern);
                      generatePuzzle(pattern);
                    }}
                    className={`w-full p-3 rounded-lg text-left transition-all hover:scale-[1.02] ${
                      selectedPattern?.pattern_id === pattern.pattern_id
                        ? 'ring-2 ring-primary bg-primary/10'
                        : 'bg-muted/50 hover:bg-muted'
                    }`}
                    data-testid={`weakness-btn-${pattern.pattern_id}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm capitalize">
                        {pattern.subcategory.replace(/_/g, ' ')}
                      </span>
                      <Badge 
                        variant="outline" 
                        className={`${getCategoryColor(pattern.category)} text-xs`}
                      >
                        {pattern.occurrences}x
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                      {pattern.description}
                    </p>
                  </button>
                ))
              ) : (
                <div className="text-center py-8">
                  <Target className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-sm text-muted-foreground">
                    Analyze some games first to discover your weaknesses
                  </p>
                </div>
              )}
              
              <Button 
                className="w-full mt-4"
                onClick={() => generatePuzzle()}
                disabled={generating || patterns.length === 0}
                data-testid="random-puzzle-btn"
              >
                {generating ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <RefreshCw className="w-4 h-4 mr-2" />
                )}
                Random Puzzle
              </Button>
            </CardContent>
          </Card>

          {/* Puzzle Board */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Brain className="w-5 h-5 text-primary" />
                    {currentPuzzle ? currentPuzzle.title || "Puzzle" : "Start a Puzzle"}
                  </CardTitle>
                  {currentPuzzle && (
                    <CardDescription>
                      {currentPuzzle.description || `Practice your ${selectedPattern?.subcategory || 'tactics'}`}
                    </CardDescription>
                  )}
                </div>
                {currentPuzzle && puzzleState === "playing" && (
                  <Badge variant="outline">
                    {game.turn() === 'w' ? 'White' : 'Black'} to move
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {currentPuzzle ? (
                <div className="space-y-4">
                  {/* Chess Board */}
                  <div className="relative aspect-square w-full max-w-[500px] mx-auto">
                    <Chessboard
                      position={game.fen()}
                      onPieceDrop={onDrop}
                      boardOrientation={currentPuzzle.player_color || "white"}
                      arePiecesDraggable={puzzleState === "playing"}
                      customBoardStyle={{
                        borderRadius: "8px",
                        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)"
                      }}
                      customDarkSquareStyle={{ backgroundColor: "#4F46E5" }}
                      customLightSquareStyle={{ backgroundColor: "#E0E7FF" }}
                    />
                    
                    {/* Overlay for solved/failed */}
                    {(puzzleState === "solved" || puzzleState === "failed") && (
                      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center rounded-lg">
                        <div className="text-center space-y-4">
                          {puzzleState === "solved" ? (
                            <>
                              <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto" />
                              <p className="text-xl font-bold text-emerald-500">Correct!</p>
                            </>
                          ) : (
                            <>
                              <XCircle className="w-16 h-16 text-red-500 mx-auto" />
                              <p className="text-xl font-bold text-red-500">Not quite</p>
                              <p className="text-sm text-muted-foreground">
                                Solution: {currentPuzzle.solution_san}
                              </p>
                            </>
                          )}
                          <Button onClick={() => generatePuzzle()} data-testid="next-puzzle-btn">
                            Next Puzzle
                            <ChevronRight className="w-4 h-4 ml-1" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Puzzle Controls */}
                  {puzzleState === "playing" && (
                    <div className="flex items-center justify-center gap-4">
                      <Button 
                        variant="outline"
                        onClick={() => setShowHint(!showHint)}
                        data-testid="hint-btn"
                      >
                        <Lightbulb className="w-4 h-4 mr-2" />
                        {showHint ? "Hide Hint" : "Show Hint"}
                      </Button>
                      <Button 
                        variant="ghost"
                        onClick={() => generatePuzzle()}
                      >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Skip
                      </Button>
                    </div>
                  )}

                  {/* Hint */}
                  {showHint && currentPuzzle.hint && (
                    <div className="p-4 rounded-lg bg-primary/10 border border-primary/20">
                      <div className="flex items-start gap-3">
                        <Lightbulb className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                        <p className="text-sm">{currentPuzzle.hint}</p>
                      </div>
                    </div>
                  )}

                  {/* Attempts Progress */}
                  {puzzleState === "playing" && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Attempts</span>
                        <span>{attempts}/3</span>
                      </div>
                      <Progress value={(3 - attempts) / 3 * 100} className="h-2" />
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 space-y-4">
                  <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
                    <Target className="w-10 h-10 text-primary" />
                  </div>
                  <div className="text-center">
                    <p className="font-medium">Select a weakness to practice</p>
                    <p className="text-sm text-muted-foreground">
                      Or click "Random Puzzle" to get started
                    </p>
                  </div>
                  <Button 
                    onClick={() => generatePuzzle()}
                    disabled={generating || patterns.length === 0}
                    data-testid="start-puzzle-btn"
                  >
                    {generating ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Zap className="w-4 h-4 mr-2" />
                    )}
                    Start Challenge
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </Layout>
  );
};

export default Challenge;
