/**
 * Opening Mastery Quiz Mode
 * 
 * Tests the user's knowledge of openings:
 * - Key ideas and concepts
 * - Trap positions (find the winning move)
 * - Move order knowledge
 * 
 * Integrated with coach memory for personalized feedback.
 */

import React, { useState, useEffect, useCallback } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import CoachBoard from "@/components/CoachBoard";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Brain,
  Trophy,
  Lightbulb,
  HelpCircle,
  ChevronRight,
  RotateCcw,
  Star,
  Target,
  BookOpen,
  Zap,
} from "lucide-react";

const OpeningQuiz = ({ openingKey, openingName, onClose, onComplete }) => {
  const [loading, setLoading] = useState(true);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [showResult, setShowResult] = useState(false);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [showHint, setShowHint] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [quizResult, setQuizResult] = useState(null);
  const [boardFen, setBoardFen] = useState(null);
  const [userMove, setUserMove] = useState(null);

  // Load quiz questions
  useEffect(() => {
    const loadQuiz = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API}/training/openings/${openingKey}/quiz`, {
          credentials: "include"
        });
        
        if (!response.ok) throw new Error("Failed to load quiz");
        
        const data = await response.json();
        setQuestions(data.questions || []);
        
        // Initialize answers array
        setAnswers(new Array(data.questions?.length || 0).fill(null));
        
        // Set initial board position if first question is position-based
        if (data.questions?.[0]?.fen) {
          setBoardFen(data.questions[0].fen);
        }
      } catch (error) {
        console.error("Failed to load quiz:", error);
        toast.error("Could not load quiz questions");
      } finally {
        setLoading(false);
      }
    };
    
    if (openingKey) {
      loadQuiz();
    }
  }, [openingKey]);

  const currentQuestion = questions[currentIndex];
  const progress = questions.length > 0 ? ((currentIndex + 1) / questions.length) * 100 : 0;

  // Handle answer selection for concept/idea questions
  const handleSelectAnswer = useCallback((answer) => {
    if (showResult) return;
    setSelectedAnswer(answer);
  }, [showResult]);

  // Handle move on board for position questions
  const handleMove = useCallback((move) => {
    if (showResult) return;
    setUserMove(move.san || move);
    setSelectedAnswer(move.san || move);
  }, [showResult]);

  // Submit current answer and move to next
  const handleSubmitAnswer = useCallback(() => {
    if (!selectedAnswer) {
      toast.error("Please select or make an answer first");
      return;
    }

    // Update answers array
    const newAnswers = [...answers];
    newAnswers[currentIndex] = selectedAnswer;
    setAnswers(newAnswers);

    // Show result
    setShowResult(true);
  }, [selectedAnswer, answers, currentIndex]);

  // Move to next question
  const handleNextQuestion = useCallback(() => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setSelectedAnswer(null);
      setShowResult(false);
      setShowHint(false);
      setUserMove(null);
      
      // Update board for next question if position-based
      const nextQ = questions[currentIndex + 1];
      if (nextQ?.fen) {
        setBoardFen(nextQ.fen);
      } else {
        setBoardFen(null);
      }
    } else {
      // Submit quiz
      submitQuiz();
    }
  }, [currentIndex, questions]);

  // Submit all answers
  const submitQuiz = async () => {
    try {
      setSubmitting(true);
      
      const response = await fetch(`${API}/training/openings/${openingKey}/quiz/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ answers })
      });
      
      if (!response.ok) throw new Error("Failed to submit quiz");
      
      const result = await response.json();
      setQuizResult(result);
      
      if (onComplete) {
        onComplete(result);
      }
    } catch (error) {
      console.error("Failed to submit quiz:", error);
      toast.error("Failed to submit quiz");
    } finally {
      setSubmitting(false);
    }
  };

  // Check if answer is correct (for showing result)
  const isCorrect = useCallback(() => {
    if (!currentQuestion || !selectedAnswer) return false;
    
    if (currentQuestion.type === "position") {
      return selectedAnswer.toLowerCase() === currentQuestion.correct_move?.toLowerCase();
    } else if (currentQuestion.type === "concept") {
      return currentQuestion.options?.includes(selectedAnswer);
    } else if (currentQuestion.type === "move_order") {
      return selectedAnswer.toLowerCase().replace(/\s/g, "") === 
             currentQuestion.correct_answer?.toLowerCase().replace(/\s/g, "");
    }
    return false;
  }, [currentQuestion, selectedAnswer]);

  // Loading state
  if (loading) {
    return (
      <Card className="w-full max-w-2xl mx-auto" data-testid="opening-quiz-loading">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="mt-4 text-muted-foreground">Loading quiz...</p>
        </CardContent>
      </Card>
    );
  }

  // No questions available
  if (questions.length === 0) {
    return (
      <Card className="w-full max-w-2xl mx-auto" data-testid="opening-quiz-empty">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <HelpCircle className="w-12 h-12 text-muted-foreground" />
          <p className="mt-4 text-lg">No quiz available for this opening yet.</p>
          <Button variant="outline" onClick={onClose} className="mt-4">
            Go Back
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Show final results
  if (quizResult) {
    const getScoreColor = (score) => {
      if (score >= 90) return "text-green-400";
      if (score >= 70) return "text-blue-400";
      if (score >= 50) return "text-yellow-400";
      return "text-red-400";
    };

    const getScoreEmoji = (score) => {
      if (score >= 90) return <Trophy className="w-12 h-12 text-yellow-400" />;
      if (score >= 70) return <Star className="w-12 h-12 text-blue-400" />;
      if (score >= 50) return <Target className="w-12 h-12 text-yellow-400" />;
      return <BookOpen className="w-12 h-12 text-muted-foreground" />;
    };

    return (
      <Card className="w-full max-w-2xl mx-auto" data-testid="opening-quiz-results">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            {getScoreEmoji(quizResult.score)}
          </div>
          <CardTitle className="text-2xl">Quiz Complete!</CardTitle>
          <CardDescription>{quizResult.opening_name}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Score */}
          <div className="text-center">
            <p className={`text-5xl font-bold ${getScoreColor(quizResult.score)}`}>
              {Math.round(quizResult.score)}%
            </p>
            <p className="text-muted-foreground mt-2">
              {quizResult.correct} / {quizResult.total} correct
            </p>
          </div>

          {/* Mastery Level */}
          <div className="p-4 rounded-lg bg-primary/10 border border-primary/20 text-center">
            <Badge variant="outline" className="mb-2">
              {quizResult.mastery_level}
            </Badge>
            <p className="text-sm">{quizResult.mastery_feedback}</p>
          </div>

          {/* Results breakdown */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Question Breakdown</h4>
            {quizResult.results.map((r, i) => (
              <div 
                key={i} 
                className={`flex items-center gap-2 p-2 rounded ${
                  r.is_correct ? "bg-green-500/10" : "bg-red-500/10"
                }`}
              >
                {r.is_correct ? (
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-400" />
                )}
                <span className="text-sm capitalize">{r.type} question</span>
                {!r.is_correct && r.correct_answer && (
                  <span className="text-xs text-muted-foreground ml-auto">
                    Answer: {r.correct_answer}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={onClose}>
              <ChevronRight className="w-4 h-4 mr-2" />
              Done
            </Button>
            <Button onClick={() => {
              setQuizResult(null);
              setCurrentIndex(0);
              setAnswers(new Array(questions.length).fill(null));
              setSelectedAnswer(null);
              setShowResult(false);
              if (questions[0]?.fen) {
                setBoardFen(questions[0].fen);
              }
            }}>
              <RotateCcw className="w-4 h-4 mr-2" />
              Retry Quiz
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Quiz in progress
  return (
    <Card className="w-full max-w-2xl mx-auto" data-testid="opening-quiz">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">{openingName} Quiz</CardTitle>
            <CardDescription>
              Question {currentIndex + 1} of {questions.length}
            </CardDescription>
          </div>
          <Badge variant="outline">
            {currentQuestion?.type}
          </Badge>
        </div>
        <Progress value={progress} className="h-2 mt-2" />
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Question */}
        <div className="p-4 rounded-lg bg-muted/30">
          <div className="flex items-start gap-3">
            <Brain className="w-5 h-5 text-primary mt-0.5" />
            <p className="text-lg">{currentQuestion?.question}</p>
          </div>
        </div>

        {/* Position-based questions show board */}
        {currentQuestion?.type === "position" && boardFen && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-full max-w-md">
              <CoachBoard
                position={boardFen}
                onMove={handleMove}
                playerColor="white"
                allowMoves={!showResult}
              />
            </div>
            {userMove && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Your move:</span>
                <Badge>{userMove}</Badge>
              </div>
            )}
            {showResult && (
              <div className={`flex items-center gap-2 p-3 rounded-lg ${
                isCorrect() ? "bg-green-500/10" : "bg-red-500/10"
              }`}>
                {isCorrect() ? (
                  <>
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                    <span className="text-green-400">Correct! Great find.</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-red-400" />
                    <span>
                      The winning move was <strong>{currentQuestion.correct_move}</strong>
                    </span>
                  </>
                )}
              </div>
            )}
            {showResult && currentQuestion.explanation && (
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20 text-sm">
                <Lightbulb className="w-4 h-4 text-primary inline mr-2" />
                {currentQuestion.explanation}
              </div>
            )}
          </div>
        )}

        {/* Concept questions show options */}
        {currentQuestion?.type === "concept" && currentQuestion.options && (
          <div className="space-y-2">
            {currentQuestion.options.map((option, i) => (
              <button
                key={i}
                onClick={() => handleSelectAnswer(option)}
                disabled={showResult}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedAnswer === option
                    ? showResult
                      ? isCorrect()
                        ? "border-green-500 bg-green-500/10"
                        : "border-red-500 bg-red-500/10"
                      : "border-primary bg-primary/10"
                    : "border-border hover:border-primary/50 hover:bg-muted/30"
                } ${showResult ? "cursor-default" : "cursor-pointer"}`}
                data-testid={`quiz-option-${i}`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-6 h-6 rounded-full border flex items-center justify-center text-sm ${
                    selectedAnswer === option ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground"
                  }`}>
                    {String.fromCharCode(65 + i)}
                  </div>
                  <span>{option}</span>
                  {showResult && option === currentQuestion.correct_answer && (
                    <CheckCircle2 className="w-4 h-4 text-green-400 ml-auto" />
                  )}
                </div>
              </button>
            ))}
            {showResult && currentQuestion.explanation && (
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20 text-sm mt-4">
                <Lightbulb className="w-4 h-4 text-primary inline mr-2" />
                {currentQuestion.explanation}
              </div>
            )}
          </div>
        )}

        {/* Move order questions */}
        {currentQuestion?.type === "move_order" && (
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Enter the main line (e.g., e4 e5 Nf3 Nc6)"
              value={selectedAnswer || ""}
              onChange={(e) => setSelectedAnswer(e.target.value)}
              disabled={showResult}
              className="w-full p-3 rounded-lg border bg-background"
              data-testid="quiz-move-order-input"
            />
            {showResult && (
              <div className={`p-3 rounded-lg ${isCorrect() ? "bg-green-500/10" : "bg-red-500/10"}`}>
                {isCorrect() ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                    <span className="text-green-400">Correct!</span>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <XCircle className="w-5 h-5 text-red-400" />
                      <span>Not quite right</span>
                    </div>
                    <p className="text-sm">
                      Correct answer: <strong>{currentQuestion.correct_answer}</strong>
                    </p>
                  </div>
                )}
              </div>
            )}
            {showResult && currentQuestion.explanation && (
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20 text-sm">
                <Lightbulb className="w-4 h-4 text-primary inline mr-2" />
                {currentQuestion.explanation}
              </div>
            )}
          </div>
        )}

        {/* Hint */}
        {!showResult && currentQuestion?.hint && (
          <div className="flex justify-center">
            {showHint ? (
              <div className="p-3 rounded-lg bg-muted/30 text-sm flex items-center gap-2">
                <Zap className="w-4 h-4 text-yellow-400" />
                {currentQuestion.hint}
              </div>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setShowHint(true)}>
                <HelpCircle className="w-4 h-4 mr-2" />
                Show Hint
              </Button>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-between">
          <Button variant="outline" onClick={onClose}>
            Exit Quiz
          </Button>
          
          {!showResult ? (
            <Button 
              onClick={handleSubmitAnswer}
              disabled={!selectedAnswer}
              data-testid="submit-answer-btn"
            >
              Check Answer
            </Button>
          ) : (
            <Button 
              onClick={handleNextQuestion}
              disabled={submitting}
              data-testid="next-question-btn"
            >
              {submitting ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : currentIndex < questions.length - 1 ? (
                <>
                  Next Question
                  <ChevronRight className="w-4 h-4 ml-2" />
                </>
              ) : (
                <>
                  <Trophy className="w-4 h-4 mr-2" />
                  See Results
                </>
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default OpeningQuiz;
