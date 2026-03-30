/**
 * OpeningWalkthrough.jsx — "Your coach walks you through YOUR opening"
 * 
 * Step-by-step guided replay of the user's actual game in their most-played opening.
 * Each move has: the IDEA, the PLAN, and flags where they went wrong.
 * Interactive challenges at key positions.
 */

import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  Loader2, ChevronRight, ChevronLeft, BookOpen,
  Target, CheckCircle2, XCircle, AlertTriangle,
  Brain, Lightbulb, Trophy, RotateCcw,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const OpeningWalkthrough = ({ user }) => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const openingParam = searchParams.get("opening");

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Walkthrough state
  const [currentStep, setCurrentStep] = useState(-1); // -1 = intro
  const [boardFen, setBoardFen] = useState(START_FEN);
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [arrows, setArrows] = useState([]);
  const [lastMove, setLastMove] = useState(null);

  // Challenge state
  const [challengeActive, setChallengeActive] = useState(false);
  const [challengeResult, setChallengeResult] = useState(null);
  const [challengesSolved, setChallengesSolved] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const url = openingParam
          ? `${API}/opening-walkthrough?opening=${encodeURIComponent(openingParam)}`
          : `${API}/opening-walkthrough`;
        const res = await fetch(url, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to load walkthrough");
        const json = await res.json();
        if (json.error) {
          setError(json.message || "No data available");
        } else {
          setData(json);
          setBoardOrientation(json.game?.user_color === "black" ? "black" : "white");
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [openingParam]);

  const steps = data?.steps || [];
  const current = currentStep >= 0 && currentStep < steps.length ? steps[currentStep] : null;

  // Update board when step changes
  useEffect(() => {
    if (currentStep < 0) {
      setBoardFen(START_FEN);
      setArrows([]);
      setLastMove(null);
      setChallengeActive(false);
      setChallengeResult(null);
      return;
    }
    if (!current) return;

    // If this is a challenge and not yet attempted, show position BEFORE the move
    if (current.is_challenge && !challengeResult) {
      setBoardFen(current.fen_before || START_FEN);
      setChallengeActive(true);
      setArrows([]);
      setLastMove(null);
      return;
    }

    // Show position after the move
    setChallengeActive(false);
    setBoardFen(current.fen_before || START_FEN);

    // Show arrows for mistakes
    if (current.type === "mistake" && current.move_uci && current.best_move_uci) {
      setArrows([
        [current.move_uci.slice(0, 2), current.move_uci.slice(2, 4), "red"],
        [current.best_move_uci.slice(0, 2), current.best_move_uci.slice(2, 4), "green"],
      ]);
    } else {
      setArrows([]);
    }
  }, [currentStep, current, challengeResult]);

  const goNext = () => {
    if (challengeActive && !challengeResult) return; // Must solve challenge first
    setChallengeResult(null);
    setChallengeActive(false);
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const goPrev = () => {
    setChallengeResult(null);
    setChallengeActive(false);
    if (currentStep > -1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const skipChallenge = () => {
    setChallengeActive(false);
    setChallengeResult({ skipped: true });
  };

  const handleChallengeMove = useCallback((moveData) => {
    if (!challengeActive || !current) return false;

    const userMoveUci = moveData.from + moveData.to;
    const bestMoveUci = current.best_move_uci || "";

    if (userMoveUci === bestMoveUci || moveData.from + moveData.to === bestMoveUci.slice(0, 4)) {
      setChallengeResult({ correct: true });
      setChallengesSolved(prev => prev + 1);
      setArrows([[moveData.from, moveData.to, "green"]]);
      toast.success("You found it!");
      return true;
    } else {
      setChallengeResult({ correct: false, userMove: userMoveUci });
      setArrows([
        [moveData.from, moveData.to, "red"],
        [bestMoveUci.slice(0, 2), bestMoveUci.slice(2, 4), "green"],
      ]);
      toast.error(`Not quite. The best move was ${current.best_move}.`);
      return false;
    }
  }, [challengeActive, current]);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
          <p className="text-sm text-muted-foreground">Loading your opening lesson...</p>
        </div>
      </Layout>
    );
  }

  if (error || !data) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
          <AlertTriangle className="w-10 h-10 text-muted-foreground mb-4" strokeWidth={1.5} />
          <p className="text-lg text-foreground mb-2">{error || "No data available"}</p>
          <p className="text-sm text-muted-foreground mb-6">Play and analyze some games first.</p>
          <Button onClick={() => navigate("/lab")} variant="outline">Go to Lab</Button>
        </div>
      </Layout>
    );
  }

  const opening = data.opening;
  const game = data.game;
  const llm = data.llm_narrative;
  const remember = data.remember || [];
  const isIntro = currentStep === -1;
  const isEnd = currentStep >= steps.length - 1 && !challengeActive;
  const progress = steps.length > 0 ? Math.round(((currentStep + 1) / steps.length) * 100) : 0;

  return (
    <Layout user={user} hideNav>
      <div className="h-screen flex flex-col overflow-hidden bg-background" data-testid="opening-walkthrough">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
              <ChevronLeft className="w-4 h-4 mr-1" /> Back
            </Button>
            <h1 className="text-lg text-foreground tracking-tight" style={{ fontFamily: "'Playfair Display', serif" }}>
              Opening Walkthrough
            </h1>
            <Badge variant="outline" className="text-xs">{opening.name}</Badge>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>{opening.games_played} games played</span>
            <span className="text-emerald-600">{opening.win_rate}% win rate</span>
            <span>vs {game.opponent}</span>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Board */}
          <div className="w-[55%] flex flex-col border-r border-border">
            <div className="flex-1 flex items-center justify-center p-4">
              <div className="w-full max-w-[560px] aspect-square relative">
                <LichessBoard
                  fen={boardFen}
                  orientation={boardOrientation}
                  viewOnly={!challengeActive}
                  interactive={challengeActive}
                  movableColor={challengeActive ? game.user_color : undefined}
                  arrows={arrows}
                  lastMove={lastMove}
                  onMove={challengeActive ? handleChallengeMove : undefined}
                />
                {challengeActive && !challengeResult && (
                  <div className="absolute top-2 left-2 bg-amber-600/90 text-white px-3 py-1.5 rounded text-sm font-medium animate-pulse">
                    Your turn — find the best move!
                  </div>
                )}
                {challengeResult && (
                  <div className={`absolute top-2 left-2 px-3 py-1.5 rounded text-sm font-medium ${
                    challengeResult.correct ? "bg-emerald-600/90 text-white" :
                    challengeResult.skipped ? "bg-gray-600/90 text-white" :
                    "bg-red-600/90 text-white"
                  }`}>
                    {challengeResult.correct ? "Correct!" : challengeResult.skipped ? "Skipped" : `Best was ${current?.best_move}`}
                  </div>
                )}
              </div>
            </div>

            {/* Progress + nav */}
            <div className="p-4 border-t border-border">
              <div className="w-full bg-muted rounded-full h-1.5 mb-3">
                <div className="bg-primary h-1.5 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
              <div className="flex items-center justify-between">
                <Button variant="ghost" size="sm" onClick={goPrev} disabled={isIntro}>
                  <ChevronLeft className="w-4 h-4 mr-1" /> Previous
                </Button>
                <span className="text-xs text-muted-foreground">
                  {isIntro ? "Intro" : `Move ${currentStep + 1} / ${steps.length}`}
                </span>
                <Button variant="ghost" size="sm" onClick={goNext} disabled={isEnd || (challengeActive && !challengeResult)}>
                  Next <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          </div>

          {/* Right: Commentary */}
          <div className="w-[45%] flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6">
              <AnimatePresence mode="wait">
                {isIntro ? (
                  <motion.div key="intro" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                    <div className="mb-6">
                      <BookOpen className="w-8 h-8 text-primary mb-3" strokeWidth={1.5} />
                      <h2 className="text-2xl text-foreground mb-2" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
                        {opening.name}
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        {llm?.intro || `Let's walk through your game in the ${opening.name}. I'll show you what went right and what to fix.`}
                      </p>
                    </div>

                    {llm?.opening_idea && (
                      <div className="bg-primary/5 border border-primary/20 p-4 rounded mb-6">
                        <p className="text-xs font-mono uppercase tracking-widest text-primary mb-2">The Idea</p>
                        <p className="text-sm text-foreground">{llm.opening_idea}</p>
                      </div>
                    )}

                    <div className="space-y-2 mb-6">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Games played</span>
                        <span className="text-foreground font-medium">{opening.games_played}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Win rate</span>
                        <span className="text-emerald-600 font-medium">{opening.win_rate}%</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">This game</span>
                        <span className="text-foreground font-medium">
                          vs {game.opponent} — {game.result.includes("1-0") && game.user_color === "white" || game.result.includes("0-1") && game.user_color === "black" ? "Won" : game.result.includes("1/2") ? "Draw" : "Lost"}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Challenges</span>
                        <span className="text-foreground font-medium">{data.stats.challenges} positions to solve</span>
                      </div>
                    </div>

                    <Button onClick={goNext} className="w-full" data-testid="start-walkthrough-btn">
                      Start Walkthrough <ChevronRight className="w-4 h-4 ml-2" />
                    </Button>
                  </motion.div>
                ) : isEnd && !challengeActive ? (
                  <motion.div key="end" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                    <Trophy className="w-8 h-8 text-primary mb-3" strokeWidth={1.5} />
                    <h2 className="text-2xl text-foreground mb-4" style={{ fontFamily: "'Cormorant Garamond', serif" }}>
                      Walkthrough Complete
                    </h2>

                    {data.stats.challenges > 0 && (
                      <div className="bg-primary/5 border border-primary/20 p-4 rounded mb-4">
                        <p className="text-lg text-foreground font-medium">
                          {challengesSolved} / {data.stats.challenges} challenges solved
                        </p>
                      </div>
                    )}

                    <div className="mb-6">
                      <p className="text-xs font-mono uppercase tracking-widest text-primary mb-3">Remember This</p>
                      <div className="space-y-2">
                        {remember.map((line, i) => (
                          <div key={i} className="flex items-start gap-2">
                            <Lightbulb className="w-4 h-4 text-primary mt-0.5 shrink-0" strokeWidth={1.5} />
                            <p className="text-sm text-foreground">{line}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {llm?.encouragement && (
                      <p className="text-sm text-muted-foreground italic mb-6">{llm.encouragement}</p>
                    )}

                    <div className="space-y-2">
                      <Button onClick={() => { setCurrentStep(-1); setChallengesSolved(0); }} variant="outline" className="w-full">
                        <RotateCcw className="w-4 h-4 mr-2" /> Replay
                      </Button>
                      <Button onClick={() => navigate("/lab")} className="w-full">
                        Back to Lab
                      </Button>
                    </div>
                  </motion.div>
                ) : current ? (
                  <motion.div key={`step-${currentStep}`} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.2 }}>
                    {/* Move header */}
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-xs font-mono text-muted-foreground uppercase">
                        Move {current.move_number}
                      </span>
                      <Badge variant={
                        current.type === "good" ? "default" :
                        current.type === "mistake" ? "destructive" :
                        current.type === "inaccuracy" ? "secondary" :
                        "outline"
                      } className="text-xs">
                        {current.is_user_move ? (current.type === "good" ? "Good" : current.type === "mistake" ? "Mistake" : current.type === "inaccuracy" ? "Okay" : "Opponent") : "Opponent"}
                      </Badge>
                      <span className="text-lg font-mono text-foreground">{current.move_san}</span>
                    </div>

                    {/* Challenge mode */}
                    {challengeActive && !challengeResult && (
                      <div className="bg-amber-500/10 border border-amber-500/30 p-4 rounded mb-4">
                        <Target className="w-5 h-5 text-amber-600 mb-2" strokeWidth={1.5} />
                        <p className="text-sm text-foreground font-medium mb-1">Find the best move!</p>
                        <p className="text-xs text-muted-foreground mb-3">
                          You made a mistake here in your game. Can you find the right move now?
                        </p>
                        <Button variant="ghost" size="sm" onClick={skipChallenge} className="text-xs">
                          Show me the answer
                        </Button>
                      </div>
                    )}

                    {/* Challenge result */}
                    {challengeResult && (
                      <div className={`p-4 rounded mb-4 ${
                        challengeResult.correct ? "bg-emerald-500/10 border border-emerald-500/30" :
                        "bg-red-500/10 border border-red-500/30"
                      }`}>
                        {challengeResult.correct ? (
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                            <p className="text-sm text-foreground font-medium">You found it! Great pattern recognition.</p>
                          </div>
                        ) : (
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <XCircle className="w-5 h-5 text-red-500" />
                              <p className="text-sm text-foreground font-medium">
                                {challengeResult.skipped ? "Here's what you should play:" : "Not quite."}
                              </p>
                            </div>
                            <p className="text-sm text-muted-foreground">
                              Best move: <span className="font-mono font-medium text-foreground">{current.best_move}</span>
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Coach commentary */}
                    {(!challengeActive || challengeResult) && (
                      <div className="space-y-4">
                        <div className="border-l-2 border-primary/40 pl-4">
                          <p className="text-sm text-foreground leading-relaxed">
                            {current.idea}
                          </p>
                        </div>

                        {current.type === "mistake" && current.best_move && (
                          <div className="bg-destructive/5 border border-destructive/20 p-3 rounded">
                            <p className="text-xs text-destructive font-medium mb-1">Better move</p>
                            <p className="text-sm text-foreground">
                              <span className="font-mono font-medium">{current.best_move}</span> — {current.idea}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Next button (only when challenge resolved or no challenge) */}
                    {(!challengeActive || challengeResult) && !isEnd && (
                      <Button onClick={goNext} variant="ghost" className="mt-6 w-full" size="sm">
                        Next move <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                    )}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default OpeningWalkthrough;
