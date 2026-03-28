/**
 * EndgameLesson.jsx — Interactive endgame lesson
 *
 * Flow: Position → "What would you play?" → User tries → Correct/Wrong feedback → Rule → Next Position
 * Each lesson = one idea, repeated across 3-4 positions.
 *
 * Route: /endgames/:categoryKey/:lessonKey
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  ChevronRight,
  ChevronLeft,
  RotateCcw,
  Check,
  X,
  Lightbulb,
  ArrowLeft,
  Trophy,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// Phase enum
const PHASE = {
  TRY: "try", // User is looking at position, about to make a move
  CORRECT: "correct", // User got it right
  WRONG: "wrong", // User got it wrong, show correct answer
  COMPLETE: "complete", // All positions done
};

export default function EndgameLesson({ user }) {
  const { categoryKey, lessonKey } = useParams();
  const navigate = useNavigate();
  const boardRef = useRef(null);

  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [posIndex, setPosIndex] = useState(0);
  const [phase, setPhase] = useState(PHASE.TRY);
  const [feedback, setFeedback] = useState(null);
  const [score, setScore] = useState(0);
  const [lastMove, setLastMove] = useState(null);
  const [boardFen, setBoardFen] = useState(null);

  useEffect(() => {
    fetchLesson();
  }, [categoryKey, lessonKey]);

  const fetchLesson = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/endgames/lesson/${categoryKey}/${lessonKey}`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setLesson(data);
        if (data.positions?.length > 0) {
          setBoardFen(data.positions[0].fen);
        }
      }
    } catch (e) {
      console.error("Failed to load endgame lesson:", e);
    } finally {
      setLoading(false);
    }
  };

  const currentPos = lesson?.positions?.[posIndex];
  const sideToMove = currentPos?.side_to_move || "white";

  const handleMove = useCallback(
    async (moveData) => {
      if (phase !== PHASE.TRY || !currentPos) return;

      const uci = moveData.from + moveData.to;
      try {
        const res = await fetch(`${API}/endgames/check-move`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            category_key: categoryKey,
            lesson_key: lessonKey,
            position_index: posIndex,
            user_move_uci: uci,
          }),
        });
        const result = await res.json();
        setFeedback(result);

        if (result.correct) {
          setPhase(PHASE.CORRECT);
          setScore((s) => s + 1);
          setLastMove([moveData.from, moveData.to]);
        } else {
          setPhase(PHASE.WRONG);
          // Reset board to original position and show the correct move
          setBoardFen(currentPos.fen);
          if (boardRef.current) {
            boardRef.current.setPosition(currentPos.fen);
          }
          // Show correct move as arrow after a tiny delay
          setLastMove(null);
          setTimeout(() => {
            const correctUci = result.correct_move_uci;
            if (correctUci && correctUci.length >= 4) {
              setLastMove([correctUci.slice(0, 2), correctUci.slice(2, 4)]);
            }
          }, 200);
        }
      } catch (e) {
        console.error("Check move failed:", e);
      }
    },
    [phase, currentPos, categoryKey, lessonKey, posIndex]
  );

  const goNext = useCallback(() => {
    if (posIndex + 1 >= (lesson?.total_positions || 0)) {
      setPhase(PHASE.COMPLETE);
    } else {
      const nextIdx = posIndex + 1;
      const nextPos = lesson.positions[nextIdx];
      setPosIndex(nextIdx);
      setPhase(PHASE.TRY);
      setFeedback(null);
      setLastMove(null);
      setBoardFen(nextPos.fen);
    }
  }, [posIndex, lesson]);

  const retry = useCallback(() => {
    if (!currentPos) return;
    setPhase(PHASE.TRY);
    setFeedback(null);
    setLastMove(null);
    setBoardFen(currentPos.fen);
  }, [currentPos]);

  const restartLesson = useCallback(() => {
    setPosIndex(0);
    setPhase(PHASE.TRY);
    setFeedback(null);
    setScore(0);
    setLastMove(null);
    if (lesson?.positions?.length > 0) {
      setBoardFen(lesson.positions[0].fen);
    }
  }, [lesson]);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="endgame-loading">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading lesson...</p>
        </div>
      </Layout>
    );
  }

  if (!lesson) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="endgame-not-found">
          <p className="text-muted-foreground">Lesson not found.</p>
          <Button onClick={() => navigate("/openings-overview?tab=endgames")} data-testid="back-to-study-btn">
            <ArrowLeft className="w-4 h-4 mr-2" /> Back to Study
          </Button>
        </div>
      </Layout>
    );
  }

  // COMPLETE screen
  if (phase === PHASE.COMPLETE) {
    return (
      <Layout user={user}>
        <div className="max-w-lg mx-auto py-8 px-4 space-y-6" data-testid="endgame-complete">
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
            <Card className="border-emerald-500/30 bg-emerald-500/5">
              <CardContent className="p-6 text-center space-y-4">
                <Trophy className="w-12 h-12 text-emerald-400 mx-auto" />
                <h2 className="text-xl font-bold">Lesson Complete</h2>
                <p className="text-sm text-muted-foreground">{lesson.name}</p>
                <div className="text-3xl font-bold text-emerald-400" data-testid="final-score">
                  {score}/{lesson.total_positions}
                </div>
                <p className="text-sm text-zinc-400">positions solved on first try</p>

                <div className="bg-zinc-900 rounded-lg p-4 mt-4 border border-zinc-800">
                  <Lightbulb className="w-5 h-5 text-amber-400 mx-auto mb-2" />
                  <p className="text-sm font-medium text-amber-400 mb-1">The Rule</p>
                  <p className="text-sm text-zinc-300" data-testid="lesson-rule">{lesson.rule}</p>
                </div>

                <div className="flex gap-3 justify-center pt-2">
                  <Button variant="outline" onClick={restartLesson} data-testid="restart-lesson-btn">
                    <RotateCcw className="w-4 h-4 mr-2" /> Try Again
                  </Button>
                  <Button onClick={() => navigate("/openings-overview?tab=endgames")} data-testid="back-to-endgames-btn">
                    More Lessons <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto py-4 px-4 space-y-4" data-testid="endgame-lesson">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <button
              className="text-xs text-muted-foreground hover:text-white transition-colors flex items-center gap-1 mb-1"
              onClick={() => navigate("/openings-overview?tab=endgames")}
              data-testid="back-to-endgames-link"
            >
              <ArrowLeft className="w-3 h-3" /> {lesson.category_name}
            </button>
            <h1 className="text-lg font-bold tracking-tight" data-testid="lesson-title">{lesson.name}</h1>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs" data-testid="position-counter">
              {posIndex + 1} / {lesson.total_positions}
            </Badge>
            <Badge variant="outline" className="text-xs text-emerald-400 border-emerald-500/30" data-testid="score-badge">
              {score} correct
            </Badge>
          </div>
        </div>

        {/* Board + Side Panel */}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_320px] gap-4">
          {/* Board */}
          <div className="aspect-square w-full max-w-[480px] mx-auto" data-testid="endgame-board">
            {boardFen && (
              <LichessBoard
                ref={boardRef}
                fen={boardFen}
                orientation={sideToMove}
                onMove={handleMove}
                interactive={phase === PHASE.TRY}
                viewOnly={phase !== PHASE.TRY}
                lastMove={lastMove}
                movableColor={sideToMove}
              />
            )}
          </div>

          {/* Prompt / Feedback Panel */}
          <div className="space-y-3">
            {/* Prompt */}
            <AnimatePresence mode="wait">
              {phase === PHASE.TRY && (
                <motion.div
                  key="prompt"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <Card className="border-zinc-700 bg-zinc-900">
                    <CardContent className="p-4">
                      <p className="text-sm font-medium text-white mb-2" data-testid="position-prompt">
                        {currentPos?.prompt}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {sideToMove === "white" ? "White" : "Black"} to move. Make your move on the board.
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {phase === PHASE.CORRECT && feedback && (
                <motion.div
                  key="correct"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <Card className="border-emerald-500/30 bg-emerald-500/5" data-testid="correct-feedback">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
                          <Check className="w-4 h-4 text-emerald-400" />
                        </div>
                        <span className="text-sm font-semibold text-emerald-400">Correct — {feedback.move_san}</span>
                      </div>
                      <p className="text-sm text-zinc-300" data-testid="correct-explanation">{feedback.on_correct}</p>
                      <div className="bg-zinc-900 rounded p-3 border border-zinc-800">
                        <p className="text-xs text-amber-400 font-medium mb-1">Rule</p>
                        <p className="text-xs text-zinc-400" data-testid="rule-text">{feedback.rule_reminder}</p>
                      </div>
                      <Button size="sm" className="w-full" onClick={goNext} data-testid="next-position-btn">
                        {feedback.is_last ? "Finish" : "Next Position"} <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                    </CardContent>
                  </Card>
                </motion.div>
              )}

              {phase === PHASE.WRONG && feedback && (
                <motion.div
                  key="wrong"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <Card className="border-red-500/30 bg-red-500/5" data-testid="wrong-feedback">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center">
                          <X className="w-4 h-4 text-red-400" />
                        </div>
                        <span className="text-sm font-semibold text-red-400">
                          Not quite — correct was {feedback.correct_move_san}
                        </span>
                      </div>
                      <p className="text-sm text-zinc-300" data-testid="wrong-explanation">{feedback.on_wrong}</p>
                      <div className="bg-zinc-900 rounded p-3 border border-zinc-800">
                        <p className="text-xs text-emerald-400 font-medium mb-1">The Idea</p>
                        <p className="text-xs text-zinc-400" data-testid="idea-text">{feedback.idea}</p>
                      </div>
                      <div className="bg-zinc-900 rounded p-3 border border-zinc-800">
                        <p className="text-xs text-amber-400 font-medium mb-1">Rule</p>
                        <p className="text-xs text-zinc-400">{feedback.rule_reminder}</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="flex-1" onClick={retry} data-testid="retry-btn">
                          <RotateCcw className="w-3.5 h-3.5 mr-1" /> Try Again
                        </Button>
                        <Button size="sm" className="flex-1" onClick={goNext} data-testid="next-position-btn">
                          {feedback.is_last ? "Finish" : "Next"} <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Lesson description - always visible */}
            <Card className="border-zinc-800 bg-zinc-900/50">
              <CardContent className="p-3">
                <p className="text-xs text-muted-foreground" data-testid="lesson-description">{lesson.description}</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </Layout>
  );
}
