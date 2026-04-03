/**
 * PatternTraining — Practice puzzles for a specific weakness pattern
 *
 * Shows positions from the user's own games first, then community
 * puzzles. Tracks solve progress and never shows already-solved puzzles.
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Chessboard } from "react-chessboard";
import {
  ArrowLeft,
  Check,
  X,
  ChevronRight,
  Target,
  Users,
  BookOpen,
  RotateCcw,
} from "lucide-react";

const PatternTraining = () => {
  const { pattern } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userMove, setUserMove] = useState("");
  const [result, setResult] = useState(null); // null | "correct" | "wrong"
  const [stats, setStats] = useState({ solved: 0, attempted: 0 });

  const fetchPuzzles = useCallback(async () => {
    try {
      const res = await fetch(`${API}/training/pattern-puzzles/${pattern}`, {
        credentials: "include",
      });
      if (res.ok) {
        const d = await res.json();
        setData(d);
      }
    } catch (e) {
      console.error("Failed to fetch pattern puzzles:", e);
    } finally {
      setLoading(false);
    }
  }, [pattern]);

  useEffect(() => {
    fetchPuzzles();
  }, [fetchPuzzles]);

  // Merge own + community, unsolved first
  const allPuzzles = useMemo(() => {
    if (!data) return [];
    const own = (data.own_puzzles || []).filter((p) => !p.already_solved);
    const community = data.community_puzzles || [];
    const solved = (data.own_puzzles || []).filter((p) => p.already_solved);
    return [...own, ...community, ...solved];
  }, [data]);

  const currentPuzzle = allPuzzles[currentIndex];

  const boardOrientation = currentPuzzle?.user_color === "black" ? "black" : "white";

  const handleMoveAttempt = async (sourceSquare, targetSquare) => {
    if (!currentPuzzle || result) return false;

    const moveSan = `${sourceSquare}${targetSquare}`;
    const bestMove = currentPuzzle.best_move_san;

    // Simple check: does the move match the best move?
    // We accept both SAN and UCI-like notation
    const isCorrect =
      bestMove &&
      (moveSan.includes(bestMove.toLowerCase().replace(/[+#x]/g, "")) ||
        bestMove.toLowerCase().replace(/[+#x]/g, "").includes(targetSquare));

    setUserMove(`${sourceSquare}-${targetSquare}`);
    setResult(isCorrect ? "correct" : "wrong");
    setStats((s) => ({
      solved: s.solved + (isCorrect ? 1 : 0),
      attempted: s.attempted + 1,
    }));

    // Record attempt
    try {
      await fetch(`${API}/training/puzzle-attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          puzzle_id: currentPuzzle.puzzle_id,
          correct: isCorrect,
          weakness_type: pattern,
          moves_tried: [`${sourceSquare}${targetSquare}`],
        }),
      });
    } catch (e) {
      // Non-blocking
    }

    return isCorrect;
  };

  const nextPuzzle = () => {
    if (currentIndex < allPuzzles.length - 1) {
      setCurrentIndex((i) => i + 1);
      setResult(null);
      setUserMove("");
    }
  };

  const retryPuzzle = () => {
    setResult(null);
    setUserMove("");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-pulse text-muted-foreground">Loading training puzzles...</div>
      </div>
    );
  }

  const readablePattern = (pattern || "").replace(/_/g, " ");

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6" data-testid="pattern-training-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(-1)}
          data-testid="back-button"
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div className="flex-1">
          <h1
            className="text-xl font-semibold text-foreground capitalize"
            style={{ fontFamily: "'Playfair Display', serif" }}
          >
            {readablePattern} Training
          </h1>
          <p className="text-sm text-muted-foreground">
            {data?.total_available || 0} positions available
            {data?.solved_count > 0 && ` · ${data.solved_count} already solved`}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Badge
            variant="outline"
            className="font-mono"
            data-testid="solve-stats"
          >
            {stats.solved}/{stats.attempted}
          </Badge>
        </div>
      </div>

      {/* No puzzles state */}
      {allPuzzles.length === 0 && (
        <div
          className="text-center py-16 space-y-3"
          data-testid="no-puzzles-message"
        >
          <Target className="w-8 h-8 mx-auto text-muted-foreground/50" />
          <p className="text-muted-foreground">
            No training puzzles for {readablePattern} yet.
          </p>
          <p className="text-sm text-muted-foreground/70">
            As more games are analyzed, puzzles will appear here automatically.
          </p>
          <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
            Go Back
          </Button>
        </div>
      )}

      {/* Puzzle view */}
      {currentPuzzle && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          {/* Board */}
          <div className="space-y-3">
            <div
              className="rounded-lg overflow-hidden border border-border shadow-sm"
              data-testid="puzzle-board"
            >
              <Chessboard
                position={currentPuzzle.fen}
                boardOrientation={boardOrientation}
                onPieceDrop={handleMoveAttempt}
                boardWidth={480}
                customBoardStyle={{
                  borderRadius: "0",
                }}
                customDarkSquareStyle={{ backgroundColor: "#779952" }}
                customLightSquareStyle={{ backgroundColor: "#edeed1" }}
              />
            </div>

            {/* Progress bar */}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>
                {currentIndex + 1} / {allPuzzles.length}
              </span>
              <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all"
                  style={{
                    width: `${((currentIndex + 1) / allPuzzles.length) * 100}%`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Side panel */}
          <div className="space-y-4">
            {/* Source badge */}
            <div className="flex items-center gap-2">
              {currentPuzzle.source === "own_game" ? (
                <Badge
                  variant="outline"
                  className="text-xs border-amber-500/30 text-amber-600"
                >
                  <BookOpen className="w-3 h-3 mr-1" />
                  From your game
                </Badge>
              ) : (
                <Badge
                  variant="outline"
                  className="text-xs border-blue-500/30 text-blue-600"
                >
                  <Users className="w-3 h-3 mr-1" />
                  Community puzzle
                </Badge>
              )}
              <Badge variant="secondary" className="text-xs capitalize">
                {currentPuzzle.difficulty}
              </Badge>
            </div>

            {/* Prompt */}
            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <p className="text-sm text-foreground leading-relaxed">
                {result === null
                  ? "Find the best move in this position."
                  : result === "correct"
                  ? "Correct! You found the best move."
                  : `Not quite. The best move was ${currentPuzzle.best_move_san}.`}
              </p>
              {currentPuzzle.description && result !== null && (
                <p className="text-xs text-muted-foreground mt-2">
                  {currentPuzzle.description}
                </p>
              )}
            </div>

            {/* Result feedback */}
            {result && (
              <div
                className={`p-3 rounded-lg border ${
                  result === "correct"
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-red-500/10 border-red-500/30"
                }`}
                data-testid="puzzle-result"
              >
                <div className="flex items-center gap-2">
                  {result === "correct" ? (
                    <Check className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <X className="w-4 h-4 text-red-500" />
                  )}
                  <span
                    className={`text-sm font-medium ${
                      result === "correct" ? "text-emerald-600" : "text-red-500"
                    }`}
                  >
                    {result === "correct" ? "Correct!" : "Incorrect"}
                  </span>
                </div>
                {result === "wrong" && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Best move: <span className="font-mono font-medium">{currentPuzzle.best_move_san}</span>
                  </p>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
              {result && currentIndex < allPuzzles.length - 1 && (
                <Button
                  className="flex-1"
                  size="sm"
                  onClick={nextPuzzle}
                  data-testid="next-puzzle-btn"
                >
                  Next Puzzle
                  <ChevronRight className="w-3 h-3 ml-1" />
                </Button>
              )}
              {result === "wrong" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={retryPuzzle}
                  data-testid="retry-puzzle-btn"
                >
                  <RotateCcw className="w-3 h-3 mr-1" />
                  Retry
                </Button>
              )}
            </div>

            {/* Completion */}
            {currentIndex === allPuzzles.length - 1 && result && (
              <div
                className="p-4 rounded-lg bg-primary/5 border border-primary/20 text-center space-y-2"
                data-testid="training-complete"
              >
                <p className="text-sm font-medium text-foreground">
                  Training Complete
                </p>
                <p className="text-xs text-muted-foreground">
                  {stats.solved} of {stats.attempted} correct
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate(-1)}
                >
                  Done
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PatternTraining;
