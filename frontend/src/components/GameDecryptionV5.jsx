/**
 * GameDecryptionV5.jsx - "Thinking Simulator"
 * 
 * Vision:
 * - Coach on EVERY move (user + opponent)
 * - Show PLANS (transferable knowledge, not just moves)
 * - "I understand" button for concept acknowledgment
 * - Clickable moves to show the future on the board
 * - Simple, 1200-friendly language
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import ClickableLine, { extractMovesFromText } from "@/components/ClickableLine";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  Target,
  ThumbsDown,
  Send,
  X,
  Loader2,
  BookOpen,
  Brain,
  Eye,
  Swords,
  GraduationCap,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Zap,
  Trophy,
  ArrowRight,
  Check
} from "lucide-react";
import { InlineFlag } from "@/components/shared/FlagMoveDialog";
import { API } from "@/App";

/**
 * Generate POSITION-SPECIFIC reflection options.
 * Uses the actual pieces, squares, and threats from this position.
 */
function _generateThoughtOptions(move, posCommentary) {
  const options = [];
  const san = move.move_san || "";
  const phase = move.phase || "";

  // 1. What the move ACTUALLY does — from the move itself
  if (move.plan?.goal) {
    options.push({ text: move.plan.goal, category: "intention" });
  }

  // 2. If it's a capture — name the piece and square
  if (san.includes("x") && move.narrative) {
    const captureMatch = move.narrative.match(/(?:takes?|captures?|took)\s+(?:the\s+)?(\w+\s+on\s+[a-h][1-8])/i);
    if (captureMatch) {
      options.push({ text: `I wanted to take the ${captureMatch[1]}`, category: "piece_safety" });
    }
  }

  // 3. From position commentary — specific observations
  if (posCommentary?.observations) {
    for (const obs of posCommentary.observations.slice(0, 2)) {
      const title = (obs.title || "").toLowerCase();
      const desc = obs.description || "";
      const shortDesc = desc.split(".")[0].toLowerCase();
      if (title.includes("undefended") || title.includes("hanging")) {
        options.push({ text: `I didn't see that ${shortDesc}`, category: "piece_safety" });
      } else if (title.includes("pin")) {
        options.push({ text: `I missed the pin — ${shortDesc}`, category: "tactical_vision" });
      } else if (title.includes("fork")) {
        options.push({ text: `I didn't see the fork — ${shortDesc}`, category: "tactical_vision" });
      } else if (title.includes("overloaded")) {
        options.push({ text: `I didn't notice ${shortDesc}`, category: "calculation" });
      } else if (title.includes("threat") || title.includes("attack")) {
        options.push({ text: `I didn't notice ${shortDesc}`, category: "threat_awareness" });
      }
    }
  }

  // 4. From the threat field — what opponent was threatening
  if (move.threat) {
    options.push({ text: `I didn't see their ${move.threat} was threatening`, category: "threat_awareness" });
  }

  // 5. From the best move — what the user SHOULD have done
  if ((move.best_move_san || move.best_move) && move.plan?.better_approach) {
    const best = move.best_move_san || move.best_move;
    options.push({ text: `I didn't consider ${best} — ${move.plan.better_approach.split(".")[0].toLowerCase()}`, category: "calculation" });
  }

  // 6. Position-specific plan from commentary
  if (posCommentary?.plan) {
    const planShort = posCommentary.plan.split(".")[0].toLowerCase();
    if (planShort.length > 15 && !options.some(o => o.text.includes(planShort.slice(0, 20)))) {
      options.push({ text: `I didn't see that the position needed: ${planShort}`, category: "planning" });
    }
  }

  // 7. Opening theory — only if actually in opening
  if (phase === "opening" && move.opening_name) {
    options.push({ text: `I didn't know the theory for the ${move.opening_name}`, category: "opening_knowledge" });
  }

  // Only genuine options — no padding, no forced minimums
  // Deduplicate and clean
  const seen = new Set();
  return options.filter(o => {
    const t = o.text?.trim();
    if (!t || t.length < 10 || seen.has(t)) return false;
    seen.add(t);
    return true;
  });
}


const GameDecryptionV5 = ({ gameId, analysis, pgn, userColor, onBack, coachSummary, coreLesson, gameResult, opponentName, coachReview, onPlayBestLine }) => {
  const [decryptionData, setDecryptionData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [boardFen, setBoardFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [acknowledgedConcepts, setAcknowledgedConcepts] = useState(new Set());
  const [habitsReport, setHabitsReport] = useState(null);
  const [posCommentary, setPosCommentary] = useState({}); // {moveIndex: commentary}
  const [showingFutureMoves, setShowingFutureMoves] = useState(false);
  const [futureMoveIndex, setFutureMoveIndex] = useState(0);
  const [highlights, setHighlights] = useState([]);
  const [arrows, setArrows] = useState([]);
  
  // "What were you thinking?" state
  const [userThoughts, setUserThoughts] = useState({});
  const [thoughtInputOpen, setThoughtInputOpen] = useState({});
  const [savingThought, setSavingThought] = useState(null);
  
  // "Show my plan" interactive mode state
  const [planMode, setPlanMode] = useState(false);
  const [planMoves, setPlanMoves] = useState([]);
  const [planBoard, setPlanBoard] = useState(null);
  const [planReasoning, setPlanReasoning] = useState("");
  const [analyzingPlan, setAnalyzingPlan] = useState(false);
  const [planAnalysis, setPlanAnalysis] = useState(null);
  
  const boardRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => { fetchDecryptionData(); }, [gameId]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      switch (e.key) {
        case 'ArrowRight': e.preventDefault(); goForward(); break;
        case 'ArrowLeft': e.preventDefault(); goBackward(); break;
        case 'ArrowUp': e.preventDefault(); goToStart(); break;
        case 'ArrowDown': e.preventDefault(); goToEnd(); break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [decryptionData, currentMoveIndex]);

  const fetchDecryptionData = async (isRetry = false) => {
    try {
      if (!isRetry) setLoading(true);
      setError(null);
      
      // Use V5 endpoint
      const res = await fetch(`${API}/coach/decryption/v5/${gameId}`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch decryption data");
      const data = await res.json();
      
      if (data.status === "generating") {
        setLoading(true);
        setTimeout(() => fetchDecryptionData(true), 5000);
        return;
      }
      
      if (data.error || !data.decryption_data) {
        setError(data.error || "Decryption data not available");
        return;
      }
      
      setDecryptionData(data.decryption_data);
      
      // Store habits report if available
      if (data.habits_report) {
        setHabitsReport(data.habits_report);
      }
      
      // Pre-load acknowledged concepts
      if (data.decryption_data) {
        const acked = new Set();
        data.decryption_data.forEach(m => {
          if (m.already_acknowledged && m.concept_id) {
            acked.add(m.concept_id);
          }
        });
        setAcknowledgedConcepts(acked);
      }
      
      // Fetch existing user thoughts for this game
      fetchUserThoughts();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch existing thoughts
  const fetchUserThoughts = async () => {
    try {
      const res = await fetch(`${API}/games/${gameId}/thoughts`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        if (data.thoughts?.length > 0) {
          const thoughts = {};
          data.thoughts.forEach(t => {
            thoughts[t.move_number] = { text: t.thought_text, saved: true };
          });
          setUserThoughts(thoughts);
        }
      }
    } catch (e) {
      console.log("Could not fetch existing thoughts");
    }
  };
  
  // Save user thought for a move
  const saveThought = async (moveNumber, fen, category) => {
    const thoughtText = userThoughts[moveNumber]?.text?.trim();
    const thoughtCategory = category || userThoughts[moveNumber]?.category || null;
    if (!thoughtText) {
      toast.error("Please enter your thought");
      return;
    }

    setSavingThought(moveNumber);
    try {
      const res = await fetch(`${API}/games/${gameId}/thought`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          move_number: moveNumber,
          fen: fen || "",
          thought_text: thoughtText,
          weakness_category: thoughtCategory,
        })
      });
      
      if (!res.ok) throw new Error("Failed to save");
      
      setUserThoughts(prev => ({
        ...prev,
        [moveNumber]: { text: thoughtText, saved: true }
      }));
      setThoughtInputOpen(prev => ({ ...prev, [moveNumber]: false }));
      toast.success("Thanks! This helps improve coaching.");
    } catch (e) {
      toast.error("Could not save thought");
    } finally {
      setSavingThought(null);
    }
  };

  // ─── PLAN MODE FUNCTIONS ───────────────────────────────────────────────
  
  // Start plan mode - user will play their intended moves
  const startPlanMode = (moveData) => {
    if (!moveData?.fen_after) return;
    
    // Initialize chess.js with position after user's move
    const chess = new Chess(moveData.fen_after);
    setPlanBoard(chess);
    setPlanMoves([]);
    setPlanReasoning("");
    setPlanAnalysis(null);
    setPlanMode(true);
  };
  
  // Handle move made in plan mode
  const handlePlanMove = (from, to, promotion) => {
    if (!planBoard) return false;
    
    try {
      const move = planBoard.move({ from, to, promotion: promotion || 'q' });
      if (move) {
        setPlanMoves(prev => [...prev, move.san]);
        // Update board state (force re-render)
        setPlanBoard(new Chess(planBoard.fen()));
        return true;
      }
    } catch (e) {
      console.log("Invalid move in plan mode");
    }
    return false;
  };
  
  // Undo last plan move
  const undoPlanMove = () => {
    if (!planBoard || planMoves.length === 0) return;
    
    planBoard.undo();
    setPlanMoves(prev => prev.slice(0, -1));
    setPlanBoard(new Chess(planBoard.fen()));
  };
  
  // Cancel plan mode
  const cancelPlanMode = () => {
    setPlanMode(false);
    setPlanMoves([]);
    setPlanBoard(null);
    setPlanReasoning("");
    setPlanAnalysis(null);
  };
  
  // Submit plan for analysis
  const submitPlan = async (moveData) => {
    if (planMoves.length === 0) {
      toast.error("Play at least one move to show your plan");
      return;
    }
    
    setAnalyzingPlan(true);
    
    try {
      const res = await fetch(`${API}/analyze-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: moveData.fen_before,
          user_move: moveData.move_san,
          plan_moves: planMoves,
          plan_reasoning: planReasoning
        })
      });
      
      if (!res.ok) throw new Error("Analysis failed");
      
      const data = await res.json();
      
      if (data.success && data.analysis) {
        setPlanAnalysis(data.analysis);
        setPlanMode(false);
        
        // Show the critical move on the board if available
        if (data.analysis.arrows?.length > 0) {
          setArrows(data.analysis.arrows.map(a => ({
            orig: a.from,
            dest: a.to,
            brush: a.color || 'red'
          })));
        }
      } else {
        toast.error(data.error || "Could not analyze plan");
      }
    } catch (e) {
      toast.error("Failed to analyze plan");
    } finally {
      setAnalyzingPlan(false);
    }
  };

  const goForward = useCallback(() => {
    if (!decryptionData || currentMoveIndex >= decryptionData.length - 1) return;
    resetFutureView();
    const i = currentMoveIndex + 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);

    const m = decryptionData[i];
    if (m.highlight_squares?.length) {
      setHighlights(m.highlight_squares);
    } else {
      setHighlights([]);
    }
  }, [decryptionData, currentMoveIndex]);

  const goBackward = useCallback(() => {
    if (!decryptionData || currentMoveIndex < 0) return;
    resetFutureView();
    const i = currentMoveIndex - 1;
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
    setHighlights([]);
  }, [decryptionData, currentMoveIndex]);

  const goToStart = useCallback(() => {
    resetFutureView();
    setCurrentMoveIndex(-1);
    setBoardFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setHighlights([]);
  }, []);

  const goToEnd = useCallback(() => {
    if (!decryptionData?.length) return;
    resetFutureView();
    const i = decryptionData.length - 1;
    setCurrentMoveIndex(i);
    setBoardFen(decryptionData[i].fen_after);
    setHighlights([]);
  }, [decryptionData]);

  const goToMove = useCallback((i) => {
    if (!decryptionData || i < -1 || i >= decryptionData.length) return;
    resetFutureView();
    setCurrentMoveIndex(i);
    setBoardFen(i === -1 ? "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" : decryptionData[i].fen_after);
    
    if (i >= 0 && decryptionData[i].highlight_squares?.length) {
      setHighlights(decryptionData[i].highlight_squares);
    } else {
      setHighlights([]);
    }
  }, [decryptionData]);

  const resetFutureView = () => {
    setShowingFutureMoves(false);
    setFutureMoveIndex(0);
    setArrows([]);
  };

  // Play future moves on the board (clickable line feature) - from position AFTER user's move
  const showFutureMoves = useCallback((moves, upToIndex) => {
    if (!decryptionData || currentMoveIndex < 0) return;
    
    const currentMove = decryptionData[currentMoveIndex];
    const startFen = currentMove.fen_after;
    
    try {
      const chess = new Chess(startFen);
      
      // Play moves up to the clicked one
      for (let i = 0; i <= upToIndex && i < moves.length; i++) {
        const move = chess.move(moves[i]);
        if (!move) break;
      }
      
      setBoardFen(chess.fen());
      setShowingFutureMoves(true);
      setFutureMoveIndex(upToIndex);
      
      // Draw arrow for last move
      const history = chess.history({ verbose: true });
      if (history.length > 0) {
        const lastMove = history[history.length - 1];
        setArrows([[lastMove.from, lastMove.to, "green"]]);
      }
    } catch (err) {
      console.error("Error showing future moves:", err);
    }
  }, [decryptionData, currentMoveIndex]);

  // Show ALTERNATIVE moves from position BEFORE the current move (for candidate moves)
  const showAlternativeMove = useCallback((move) => {
    if (!decryptionData || currentMoveIndex < 0) return;
    
    const currentMove = decryptionData[currentMoveIndex];
    const startFen = currentMove.fen_before; // Use position BEFORE the move!
    
    if (!startFen) {
      console.error("No fen_before available");
      return;
    }
    
    try {
      const chess = new Chess(startFen);
      const result = chess.move(move);
      
      if (!result) {
        console.error("Invalid move:", move, "from FEN:", startFen);
        return;
      }
      
      setBoardFen(chess.fen());
      setShowingFutureMoves(true);
      setFutureMoveIndex(0);
      
      // Draw arrow showing the alternative move
      setArrows([[result.from, result.to, "blue"]]);
    } catch (err) {
      console.error("Error showing alternative move:", err, move);
    }
  }, [decryptionData, currentMoveIndex]);

  const resetToCurrentMove = useCallback(() => {
    if (!decryptionData || currentMoveIndex < 0) return;
    setBoardFen(decryptionData[currentMoveIndex].fen_after);
    setShowingFutureMoves(false);
    setFutureMoveIndex(0);
    setArrows([]);
  }, [decryptionData, currentMoveIndex]);

  // Acknowledge a concept
  const acknowledgeConceptHandler = async (conceptId) => {
    try {
      const res = await fetch(`${API}/coach/decryption/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ concept_id: conceptId })
      });
      
      if (res.ok) {
        setAcknowledgedConcepts(prev => new Set([...prev, conceptId]));
        toast.success("Got it! I'll remember you understand this.");
      }
    } catch (err) {
      toast.error("Failed to save acknowledgment");
    }
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim() || currentMoveIndex < 0) return;
    const m = decryptionData[currentMoveIndex];
    try {
      setSubmittingFeedback(true);
      const res = await fetch(`${API}/coach/decryption/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          game_id: gameId,
          move_number: m.move_number,
          fen: m.fen_before,
          coach_explanation: m.narrative || "",
          user_feedback: "not_helpful",
          user_correction: feedbackText,
          is_user_move: m.is_user_move
        })
      });
      if (res.ok) {
        toast.success("Feedback saved — thanks!");
        setFeedbackOpen(false);
        setFeedbackText("");
      }
    } catch (err) {
      toast.error("Failed to send feedback");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const currentMove = currentMoveIndex >= 0 ? decryptionData?.[currentMoveIndex] : null;
  const orientation = userColor === "black" ? "black" : "white";

  // Fetch position commentary for mistake moves (lazy, one at a time)
  useEffect(() => {
    if (!currentMove || posCommentary[currentMoveIndex]) return;
    const sev = currentMove.severity;
    if (sev !== "blunder" && sev !== "mistake" && sev !== "inaccuracy") return;
    const fen = currentMove.fen_before || currentMove.fen;
    if (!fen) return;

    (async () => {
      try {
        const res = await fetch(`${API}/coach/play/position/read`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ fen, user_color: userColor }),
        });
        if (res.ok) {
          const data = await res.json();
          setPosCommentary(prev => ({ ...prev, [currentMoveIndex]: data }));
        } else {
          console.warn("[Decrypt] Position read failed:", res.status);
        }
      } catch (e) {
        console.warn("[Decrypt] Position read error:", e.message);
      }
    })();
  }, [currentMoveIndex, currentMove?.fen_before]);

  if (loading) return (
    <div className="flex flex-col items-center justify-center h-96" data-testid="decryption-loading">
      <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
      <span className="mt-3 text-gray-500">Your coach is analyzing every move...</span>
      <span className="mt-1 text-gray-400 text-sm">This takes about 45 seconds for V5 analysis</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center h-96 text-center" data-testid="decryption-error">
      <AlertTriangle className="w-12 h-12 text-amber-400 mb-4" />
      <p className="text-gray-600 mb-2">{error}</p>
      <Button variant="outline" onClick={() => fetchDecryptionData()} className="mt-4">Try Again</Button>
    </div>
  );

  return (
    <div ref={containerRef} className="flex flex-col lg:flex-row gap-4 p-4" data-testid="game-decryption-v5">
      {/* LEFT: Board + Controls */}
      <div className="lg:w-1/2 space-y-4">
        <div className="aspect-square max-w-[500px] mx-auto relative">
          <LichessBoard
            ref={boardRef}
            fen={planMode && planBoard ? planBoard.fen() : boardFen}
            orientation={orientation}
            viewOnly={!planMode}
            onMove={planMode ? handlePlanMove : undefined}
            lastMove={!planMode && currentMove && !showingFutureMoves ? getLastMoveSquares(currentMove) : null}
            arrows={arrows}
            highlights={highlights}
            moveClassification={(() => {
              if (!currentMove || planMode || showingFutureMoves) return null;
              const squares = getLastMoveSquares(currentMove);
              if (!squares) return null;

              let severity = currentMove.severity;

              // For opponent moves without severity, derive from cp_loss
              if ((!severity || severity === "context" || severity === "good") && !currentMove.is_user_move) {
                const cpLoss = Math.abs(currentMove.cp_loss || 0);
                if (cpLoss >= 200) severity = "blunder";
                else if (cpLoss >= 100) severity = "mistake";
                else if (cpLoss >= 50) severity = "inaccuracy";
                else if (cpLoss <= 5) severity = "best";
                else severity = "good";
              }

              if (!severity || severity === "context") return null;
              return { square: squares[1], type: severity };
            })()}
          />
          
          {/* Plan mode indicator */}
          {planMode && (
            <div className="absolute top-2 left-2 bg-cyan-500/90 text-gray-900 text-xs px-2 py-1 rounded flex items-center gap-1 animate-pulse">
              <Swords className="w-3 h-3" />
              Play your intended moves
            </div>
          )}
          
          {/* Future moves indicator */}
          {showingFutureMoves && !planMode && (
            <div className="absolute top-2 left-2 bg-emerald-500/90 text-gray-900 text-xs px-2 py-1 rounded flex items-center gap-1">
              <Eye className="w-3 h-3" />
              Showing future line
              <button 
                onClick={resetToCurrentMove}
                className="ml-2 bg-white/20 hover:bg-white/30 px-1.5 py-0.5 rounded text-xs"
              >
                Reset
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="icon" onClick={goToStart} disabled={currentMoveIndex === -1} data-testid="btn-go-start">
            <ChevronsLeft className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={goBackward} disabled={currentMoveIndex === -1} data-testid="btn-go-back">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="px-4 text-sm text-gray-500 min-w-[100px] text-center">
            {currentMoveIndex === -1 ? "Start" : `Move ${currentMove?.move_number || ""}`}
            {currentMove && !currentMove.is_user_move && " (opp)"}
          </span>
          <Button variant="outline" size="icon" onClick={goForward} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-forward">
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={goToEnd} disabled={!decryptionData || currentMoveIndex >= decryptionData.length - 1} data-testid="btn-go-end">
            <ChevronsRight className="w-4 h-4" />
          </Button>
        </div>

        <MoveListV5 
          decryptionData={decryptionData} 
          currentMoveIndex={currentMoveIndex} 
          onMoveClick={goToMove} 
        />
      </div>

      {/* RIGHT: Coaching */}
      <div className="lg:w-1/2 space-y-4">
        {currentMoveIndex === -1 ? (
          <GameStartCard 
            decryptionData={decryptionData} 
            habitsReport={habitsReport}
            coachSummary={coachSummary}
            coreLesson={coreLesson}
            gameResult={gameResult}
            opponentName={opponentName}
            onBegin={goForward}
          />
        ) : (
          <MoveCoachingCardV5 
            move={currentMove}
            gameId={gameId}
            acknowledgedConcepts={acknowledgedConcepts}
            onAcknowledge={acknowledgeConceptHandler}
            onShowFutureMoves={showFutureMoves}
            onShowAlternativeMove={showAlternativeMove}
            onFeedbackClick={() => setFeedbackOpen(true)}
            // Thought reflection props
            userThought={userThoughts[currentMove?.move_number]}
            thoughtInputOpen={thoughtInputOpen[currentMove?.move_number]}
            onToggleThoughtInput={(moveNum) => setThoughtInputOpen(prev => ({ ...prev, [moveNum]: !prev[moveNum] }))}
            onThoughtChange={(moveNum, text, category) => setUserThoughts(prev => ({ ...prev, [moveNum]: { text, category, saved: false } }))}
            onSaveThought={saveThought}
            savingThought={savingThought}
            // Plan mode props
            planMode={planMode}
            planMoves={planMoves}
            planBoard={planBoard}
            planReasoning={planReasoning}
            planAnalysis={planAnalysis}
            analyzingPlan={analyzingPlan}
            onStartPlanMode={() => startPlanMode(currentMove)}
            onPlanMove={handlePlanMove}
            onUndoPlanMove={undoPlanMove}
            onCancelPlan={cancelPlanMode}
            onSubmitPlan={() => submitPlan(currentMove)}
            onPlanReasoningChange={setPlanReasoning}
            // Enrichment props
            positionCommentary={posCommentary[currentMoveIndex]}
            openingAnalysis={coachReview?.opening_analysis}
            patternContext={coachReview?.pattern_context}
            onPlayBestLine={onPlayBestLine}
          />
        )}
        
        {feedbackOpen && currentMove && (
          <FeedbackPanel 
            move={currentMove} 
            feedbackText={feedbackText} 
            setFeedbackText={setFeedbackText}
            onSubmit={handleSubmitFeedback} 
            onCancel={() => { setFeedbackOpen(false); setFeedbackText(""); }}
            submitting={submittingFeedback} 
          />
        )}
        
        <div className="text-xs text-gray-400 text-center">
          Arrow keys: left/right navigate • Click moves in explanation to see on board
        </div>
      </div>
    </div>
  );
};


// ─── GAME START CARD ────────────────────────────────────────────────

const GameStartCard = ({ decryptionData, habitsReport, coachSummary, coreLesson, gameResult, opponentName, onBegin }) => {
  if (!decryptionData?.length) return null;
  
  // Calculate stats
  const userMoves = decryptionData.filter(m => m.is_user_move);
  const mistakes = userMoves.filter(m => m.severity === 'mistake' || m.severity === 'blunder').length;
  const bestMoves = userMoves.filter(m => m.is_best_move).length;
  const openingName = decryptionData[0]?.opening_name;
  
  // Build story hook from available data
  const storyHook = coachSummary?.opening_line || coachSummary?.key_observation || null;
  const lessonLabel = coreLesson?.short_label || null;
  const lessonText = coreLesson?.lesson || null;
  const takeaway = coachSummary?.actionable_takeaway || null;
  
  return (
    <div className="space-y-4" data-testid="game-start-card">
      {/* Story hook — the narrative intro */}
      {(storyHook || lessonLabel) && (
        <div className="rounded-lg border border-border bg-muted/30 p-5">
          {lessonLabel && (
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-amber-600 dark:text-amber-400 mb-2 block">
              {lessonLabel}
            </span>
          )}
          {lessonText && (
            <p className="text-base font-semibold text-foreground leading-relaxed mb-2 font-heading">
              {lessonText}
            </p>
          )}
          {storyHook && !lessonText && (
            <p className="text-sm text-foreground leading-relaxed">
              {storyHook}
            </p>
          )}
          {takeaway && lessonText && (
            <p className="text-xs text-muted-foreground leading-relaxed mt-1">
              {takeaway}
            </p>
          )}
        </div>
      )}

      {/* Opening + Stats row */}
      <div className="flex items-stretch gap-3">
        {openingName && (
          <div className="flex-1 rounded-lg bg-emerald-500/8 border border-emerald-500/15 p-3.5">
            <p className="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold mb-0.5">Opening</p>
            <p className="text-sm font-medium text-foreground">{openingName}</p>
          </div>
        )}
        <div className="flex gap-2">
          <div className="w-16 rounded-lg bg-muted/50 border border-border p-3 text-center">
            <p className="text-lg font-bold text-foreground font-mono">{userMoves.length}</p>
            <p className="text-[10px] text-muted-foreground">Moves</p>
          </div>
          <div className="w-16 rounded-lg bg-emerald-500/8 border border-emerald-500/15 p-3 text-center">
            <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 font-mono">{bestMoves}</p>
            <p className="text-[10px] text-muted-foreground">Best</p>
          </div>
          <div className="w-16 rounded-lg bg-red-500/8 border border-red-500/15 p-3 text-center">
            <p className="text-lg font-bold text-red-500 font-mono">{mistakes}</p>
            <p className="text-[10px] text-muted-foreground">Errors</p>
          </div>
        </div>
      </div>
      
      {/* What this analysis does */}
      <div className="rounded-lg border border-border p-4 bg-background">
        <p className="text-sm text-muted-foreground leading-relaxed">
          Your coach will walk you through <strong className="text-foreground">every move</strong> — yours and your opponent's.
          Tap <span className="text-amber-600 dark:text-amber-400 font-medium">"I understand"</span> on each concept to track what you've learned.
        </p>
      </div>
      
      {/* CTA */}
      <button 
        onClick={onBegin}
        className="w-full py-3.5 rounded-lg bg-foreground text-background font-medium text-sm hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
        data-testid="begin-decrypt-btn"
      >
        <ChevronRight className="w-4 h-4" />
        Begin walkthrough
      </button>
      
      {/* Keyboard hint */}
      <p className="text-[10px] text-muted-foreground/60 text-center">
        or press the right arrow key
      </p>
    </div>
  );
};


// ─── MOVE COACHING CARD V5 ──────────────────────────────────────────

const MoveCoachingCardV5 = ({
  move,
  gameId,
  acknowledgedConcepts,
  onAcknowledge,
  onShowFutureMoves,
  onShowAlternativeMove,
  onFeedbackClick,
  // Thought reflection props
  userThought,
  thoughtInputOpen,
  onToggleThoughtInput,
  onThoughtChange,
  onSaveThought,
  savingThought,
  // Plan mode props
  planMode,
  planMoves,
  planBoard,
  planReasoning,
  planAnalysis,
  analyzingPlan,
  onStartPlanMode,
  onPlanMove,
  onUndoPlanMove,
  onCancelPlan,
  onSubmitPlan,
  onPlanReasoningChange,
  // Enrichment props
  positionCommentary,
  openingAnalysis,
  patternContext,
  onPlayBestLine,
}) => {
  const [expanded, setExpanded] = useState(false);
  if (!move) return null;

  const isUser = move.is_user_move;
  const severity = move.severity || 'good';
  const priority = move.priority || (severity === 'good' ? 'silent' : 'essential');
  const weaknessMatch = move.weakness_match;
  const hasPlan = !!move.plan;
  const needsAck = move.needs_acknowledgment && move.concept_id && !acknowledgedConcepts.has(move.concept_id);
  const wasAcked = move.concept_id && acknowledgedConcepts.has(move.concept_id);
  
  // Show thought prompt for user mistakes
  const isMistake = isUser && (severity === 'blunder' || severity === 'mistake' || severity === 'inaccuracy');
  const hasThought = userThought?.saved;

  // Determine card style based on move type
  let borderClass = 'border-gray-200 bg-white';
  let headerIcon = <Brain className="w-5 h-5 text-blue-400" />;
  
  if (!isUser) {
    borderClass = 'border-indigo-500/30 bg-indigo-50';
    headerIcon = <Target className="w-5 h-5 text-indigo-400" />;
  } else if (severity === 'blunder' || severity === 'mistake') {
    borderClass = 'border-red-500/30 bg-red-50';
    headerIcon = <AlertTriangle className="w-5 h-5 text-red-400" />;
  } else if (severity === 'inaccuracy') {
    borderClass = weaknessMatch 
      ? 'border-amber-500/40 bg-amber-950/15 ring-1 ring-amber-500/20'
      : 'border-orange-500/30 bg-orange-50';
    headerIcon = <Lightbulb className="w-5 h-5 text-orange-400" />;
  } else if (move.is_best_move) {
    borderClass = 'border-emerald-500/30 bg-emerald-50';
    headerIcon = <Trophy className="w-5 h-5 text-emerald-400" />;
  } else if (severity === 'good') {
    borderClass = 'border-emerald-500/20 bg-emerald-50/50';
    headerIcon = <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
  }

  // Shared flag context for all inline flags on this move
  const flagCtx = {
    source: "lab",
    gameId,
    moveNumber: move.move_number,
    fen: move.fen || "",
    moveSan: move.move_san,
    side: isUser ? "user" : "opponent",
    severity,
    cpLoss: move.cp_loss,
    bestMove: move.best_move,
    evalBefore: move.eval_before,
    evalAfter: move.eval_after,
    phase: move.phase,
    component: "GameDecryptionV5",
    opening: move.opening_name,
    goal: move.plan?.goal,
    consequence: move.plan?.consequence,
    betterApproach: move.plan?.better_approach,
    yourPlanNow: move.your_plan_now,
  };

  return (
    <Card className={`border ${borderClass}`} data-testid="move-coaching-card-v5">
      <CardContent className="p-5 space-y-3">
        {/* ─── HEADER ──────────────────────────────────────── */}
        {/* Severity and phase tags removed — they were System-layer labels
            leaking into the Surface. The border color (red/amber) and the
            narrative below already convey how the move went. */}
        <div className="flex items-center gap-2">
          {headerIcon}
          <span className="font-bold text-gray-900 text-lg">{move.move_san}</span>
          <Badge variant={isUser ? "default" : "secondary"} className="text-xs">
            {isUser ? "Your move" : "Opponent"}
          </Badge>
          {move.is_best_move && (
            <Badge className="text-xs bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
              Best move!
            </Badge>
          )}
          {weaknessMatch && (
            <Badge className="text-xs bg-amber-500/20 text-amber-300 border-amber-500/30">
              Known pattern{move.weakness_count ? ` (${move.weakness_count}x)` : ''}
            </Badge>
          )}
        </div>

        {/* ─── NARRATIVE ────────────────────────────────────── */}
        {move.narrative && (
          <div className="leading-relaxed group" data-testid="move-narrative">
            <p className="text-sm text-gray-700 inline">{move.narrative}</p>
            <InlineFlag section="narrative" flaggedText={move.narrative} context={flagCtx} />
          </div>
        )}

        {/* ─── POSITION COMMENTARY (what the board says) ──────── */}
        {/* Header is "What this position tells us" — NOT "A better plan here".
            The plan/observations come from PLAN_RULES + position_reader,
            which describe position features (pins, back-rank pieces, etc.)
            independent of the move actually played. Labeling them as
            move-specific advice lies to the user. */}
        {positionCommentary && (isMistake || move.is_best_move) && (
          <div className="bg-blue-500/5 rounded-lg p-3 border border-blue-500/15">
            <p className="text-xs text-blue-400/70 font-semibold mb-1">What this position tells us</p>
            {positionCommentary.plan && (
              <p className="text-sm text-gray-700 mb-1">{positionCommentary.plan}</p>
            )}
            {positionCommentary.observations?.slice(0, 2).map((obs, i) => (
              <p key={i} className="text-xs text-gray-500 leading-snug">• {obs.title}: {obs.description}</p>
            ))}
          </div>
        )}

        {/* ─── OPENING THEORY (if in opening phase) ────────────── */}
        {openingAnalysis && move.phase === "opening" && move.move_number <= 12 && (
          <div className="bg-primary/5 rounded-lg p-3 border border-primary/15">
            <p className="text-xs text-primary/70 font-semibold mb-1">
              Opening: {openingAnalysis.name}
              <span className="text-primary/40 ml-2">{openingAnalysis.moves_in_theory}/{openingAnalysis.total_theory_moves} theory</span>
            </p>
            {openingAnalysis.deviation && openingAnalysis.deviation.ply <= (move.move_number * 2) && (
              <p className="text-xs text-gray-500">
                Deviated: played <span className="font-mono text-red-400">{openingAnalysis.deviation.played}</span>
                {" "}instead of <span className="font-mono text-emerald-400">{openingAnalysis.deviation.expected}</span>
                {openingAnalysis.deviation.idea && <span className="text-gray-400"> — {openingAnalysis.deviation.idea}</span>}
              </p>
            )}
            {openingAnalysis.traps?.map((t, i) => (
              <p key={i} className="text-xs text-amber-500 mt-1">
                <span className="font-semibold">{t.name}:</span> {t.story || t.explanation}
              </p>
            ))}
          </div>
        )}

        {/* ─── PATTERN CONNECTION (cross-game) ─────────────────── */}
        {patternContext?.is_recurring && isMistake && (
          <div className="bg-red-500/5 rounded-lg p-2.5 border border-red-500/15">
            <p className="text-xs text-red-400">
              This type of mistake happened in {patternContext.games_with} of your last {patternContext.games_checked} games.
              {patternContext.is_improving
                ? " But it's getting less frequent — you're improving."
                : " This is your most consistent pattern right now."
              }
            </p>
          </div>
        )}

        {/* ─── STOCKFISH BRANCHING (what if best move?) ────────── */}
        {isMistake && (move.best_move_san || move.best_move) && (
          <button
            onClick={() => {
              // Play the best move from fen_before, then PV continuation
              const bestMove = move.best_move_san || move.best_move;
              // First show the best move as an alternative
              onShowAlternativeMove(bestMove);
            }}
            className="w-full text-xs text-blue-400 hover:text-blue-300 bg-blue-500/5 hover:bg-blue-500/10 rounded-lg p-2.5 border border-blue-500/15 transition-all flex items-center justify-center gap-1.5"
          >
            <Eye className="w-3 h-3" />
            What if I played {move.best_move_san || move.best_move}? See on board
          </button>
        )}

        {/* ─── OPPONENT MOVE: YOUR PLAN NOW ─────────────────── */}
        {!isUser && move.your_plan_now && (
          <div className="bg-indigo-500/10 rounded-lg p-3 border border-indigo-500/30 group" data-testid="your-plan-now">
            <p className="text-xs text-indigo-400 mb-1 flex items-center gap-1">
              <Swords className="w-3 h-3" /> What's your plan now?
            </p>
            <p className="text-gray-900 text-sm inline">{move.your_plan_now}</p>
            <InlineFlag section="your_plan_now" flaggedText={move.your_plan_now} context={flagCtx} />
          </div>
        )}

        {/* ─── PLAN (THE TRANSFERABLE LEARNING) ─────────────── */}
        {hasPlan && (
          <div className="space-y-2">
            {/* Consequence with clickable moves */}
            {move.plan.consequence && (
              <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20 group" data-testid="plan-consequence">
                <p className="text-xs text-red-400 mb-1">What happens</p>
                <span className="inline">
                  <ClickableMoves 
                    text={move.plan.consequence}
                    moves={move.future_moves || []}
                    onMoveClick={onShowFutureMoves}
                  />
                </span>
                <InlineFlag section="consequence" flaggedText={move.plan.consequence} context={flagCtx} />
              </div>
            )}
            
            {/* Better approach */}
            {move.plan.better_approach && (
              <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20 group" data-testid="plan-better">
                <p className="text-xs text-emerald-400 mb-1">Better approach</p>
                <p className="text-gray-900 text-sm inline">{move.plan.better_approach}</p>
                <InlineFlag section="better_approach" flaggedText={move.plan.better_approach} context={flagCtx} />
              </div>
            )}
            
            {/* Candidate Moves with Ideas - CLICKABLE */}
            {move.plan.candidate_moves?.length > 0 && (
              <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/20" data-testid="candidate-moves">
                <p className="text-xs text-blue-400 mb-2 flex items-center gap-1">
                  <Lightbulb className="w-3 h-3" /> Alternative ideas in this position
                </p>
                <div className="space-y-2">
                  {move.plan.candidate_moves.map((candidate, idx) => (
                    <div 
                      key={idx}
                      className={`flex items-start gap-2 p-2 rounded cursor-pointer transition-all hover:scale-[1.01] ${
                        candidate.is_best 
                          ? 'bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-100' 
                          : 'bg-gray-50 hover:bg-gray-100'
                      }`}
                      onClick={() => onShowAlternativeMove(candidate.move)}
                      title={`Click to see ${candidate.move} on the board`}
                    >
                      <button
                        className={`font-mono font-bold text-sm min-w-[50px] px-2 py-1 rounded hover:ring-2 ring-offset-1 ring-offset-zinc-900 ${
                          candidate.is_best 
                            ? 'text-emerald-400 bg-emerald-500/20 hover:ring-emerald-500/50' 
                            : 'text-blue-400 bg-blue-500/20 hover:ring-blue-500/50'
                        }`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onShowAlternativeMove(candidate.move);
                        }}
                      >
                        {candidate.move}
                      </button>
                      <div className="flex-1 group">
                        <p className="text-sm text-gray-700 inline">{candidate.idea}</p>
                        <InlineFlag section={`candidate_move_${candidate.move}`} flaggedText={`${candidate.move}: ${candidate.idea}`} context={flagCtx} />
                        <Badge 
                          variant="outline" 
                          className={`mt-1 text-xs ${
                            candidate.type === 'counter_attack' ? 'text-orange-400 border-orange-500/30' :
                            candidate.type === 'prophylactic' ? 'text-purple-400 border-purple-500/30' :
                            candidate.type === 'development' ? 'text-blue-400 border-blue-500/30' :
                            candidate.type === 'central' ? 'text-yellow-400 border-yellow-500/30' :
                            candidate.type === 'tactical' ? 'text-red-400 border-red-500/30' :
                            'text-gray-500 border-zinc-500/30'
                          }`}
                        >
                          {candidate.type?.replace('_', ' ')}
                        </Badge>
                      </div>
                      {candidate.is_best && (
                        <Trophy className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Transferable learning */}
            {move.plan.transferable_learning && (
              <div className="bg-amber-500/10 rounded-lg p-4 border border-amber-500/30 group" data-testid="transferable-learning">
                <div className="flex items-center gap-2 mb-1">
                  <GraduationCap className="w-4 h-4 text-amber-400" />
                  <p className="text-xs font-semibold text-amber-400">Learning</p>
                </div>
                <p className="text-gray-900 text-sm font-medium inline">{move.plan.transferable_learning}</p>
                <InlineFlag section="transferable_learning" flaggedText={move.plan.transferable_learning} context={flagCtx} />
                
                {/* I Understand button */}
                {needsAck && (
                  <div className="mt-3 pt-3 border-t border-amber-500/20">
                    <p className="text-xs text-gray-500 mb-2">{move.acknowledgment_prompt || "Click when this concept is clear to you."}</p>
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => onAcknowledge(move.concept_id)}
                      className="text-amber-400 border-amber-500/30 hover:bg-amber-500/10"
                      data-testid="btn-i-understand"
                    >
                      <Check className="w-3 h-3 mr-1" /> I understand
                    </Button>
                  </div>
                )}
                
                {wasAcked && (
                  <div className="mt-2 flex items-center gap-1 text-xs text-emerald-400">
                    <CheckCircle2 className="w-3 h-3" /> You've learned this
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ─── CONCEPT APPLIED (for good moves) ──────────────── */}
        {move.concept_applied && !hasPlan && (
          <div className="bg-emerald-500/10 rounded-lg p-3 border border-emerald-500/20" data-testid="concept-applied">
            <p className="text-xs text-emerald-400 mb-1 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> You demonstrated
            </p>
            <p className="text-gray-900 text-sm">{move.concept_applied.replace(/_/g, ' ')}</p>
          </div>
        )}

        {/* ─── FUTURE MOVES (clickable) ───────────────────────── */}
        {move.future_moves?.length > 0 && !hasPlan && (
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-2">The line continues:</p>
            <div className="flex flex-wrap gap-1">
              {move.future_moves.slice(0, 4).map((m, i) => (
                <button
                  key={i}
                  onClick={() => onShowFutureMoves(move.future_moves, i)}
                  className="font-mono text-sm bg-gray-100 hover:bg-emerald-100 px-2 py-1 rounded text-gray-900 transition-colors"
                  title={`Click to see position after ${m}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ─── WHAT WERE YOU THINKING? (smart dropdown + board play) ── */}
        {isMistake && !planMode && !planAnalysis && (
          <div className="bg-violet-500/5 rounded-lg p-3 border border-violet-500/20" data-testid="thought-prompt">
            {hasThought ? (
              // Already saved thought
              <div className="space-y-3">
                <div className="flex items-start gap-2">
                  <Eye className="w-4 h-4 text-violet-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-violet-400 mb-1">Your thinking</p>
                    <p className="text-sm text-gray-600 italic">"{userThought.text}"</p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onStartPlanMode}
                  className="w-full text-xs border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10"
                >
                  <Swords className="w-3 h-3 mr-2" />
                  Show my plan on the board
                </Button>
              </div>
            ) : thoughtInputOpen ? (
              // Smart dropdown with context-aware options
              <div className="space-y-2">
                <p className="text-xs text-violet-400 flex items-center gap-1">
                  <Eye className="w-3 h-3" /> Why did you play {move.move_san}?
                </p>
                {/* Smart options generated from position context */}
                <div className="space-y-1">
                  {_generateThoughtOptions(move, positionCommentary).map((opt, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        onThoughtChange(move.move_number, opt.text, opt.category);
                        // Auto-save after selection
                        setTimeout(() => onSaveThought(move.move_number, move.fen_before, opt.category), 100);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all ${
                        userThought?.text === opt.text
                          ? "bg-violet-500/20 border border-violet-500/30 text-violet-300"
                          : "bg-gray-50 hover:bg-violet-500/10 text-gray-700 border border-transparent"
                      }`}
                    >
                      {opt.text}
                    </button>
                  ))}
                  {/* Other — show text input */}
                  <button
                    onClick={() => onThoughtChange(move.move_number, "")}
                    className="w-full text-left px-3 py-2 rounded-lg text-sm bg-gray-50 hover:bg-violet-500/10 text-gray-500 border border-transparent"
                  >
                    Other...
                  </button>
                </div>
                {/* Text input shows when "Other" is selected or text is custom */}
                {userThought?.text !== undefined && !_generateThoughtOptions(move, positionCommentary).some(o => o.text === userThought?.text) && (
                  <div className="space-y-2 pt-1">
                    <Textarea
                      value={userThought?.text || ""}
                      onChange={(e) => onThoughtChange(move.move_number, e.target.value)}
                      placeholder="What were you thinking..."
                      className="min-h-[50px] text-sm bg-gray-50 border-gray-200 resize-none"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => onSaveThought(move.move_number, move.fen_before)}
                        disabled={savingThought === move.move_number || !userThought?.text?.trim()}
                        className="text-xs bg-violet-600 hover:bg-violet-700"
                      >
                        {savingThought === move.move_number ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Check className="w-3 h-3 mr-1" />}
                        Save
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => onToggleThoughtInput(move.move_number)} className="text-xs text-gray-500">
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
                {/* Play my intended move on the board */}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onStartPlanMode}
                  className="w-full text-xs border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10 mt-1"
                >
                  <Swords className="w-3 h-3 mr-2" />
                  Or show what I wanted to play on the board
                </Button>
              </div>
            ) : (
              // Collapsed - show button to expand
              <div className="space-y-2">
                <button
                  onClick={() => onToggleThoughtInput(move.move_number)}
                  className="flex items-center gap-2 text-xs text-violet-400 hover:text-violet-300 transition-colors w-full"
                >
                  <Eye className="w-3 h-3" />
                  <span>Why did you play {move.move_san}?</span>
                  <ChevronDown className="w-3 h-3 ml-auto" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* ─── PLAN MODE: Interactive Board ────────────────────── */}
        {planMode && isMistake && (
          <div className="bg-cyan-500/5 rounded-lg p-4 border border-cyan-500/30 space-y-4" data-testid="plan-mode">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Swords className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-medium text-cyan-400">Show Your Plan</span>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={onCancelPlan}
                className="h-6 w-6 p-0 text-gray-500 hover:text-gray-700"
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
            
            <p className="text-xs text-gray-500">
              Play the moves you intended. What did you think would happen?
            </p>
            
            {/* Current plan moves */}
            {planMoves.length > 0 && (
              <div className="bg-gray-50 rounded p-2">
                <p className="text-xs text-gray-500 mb-1">Your line:</p>
                <div className="flex flex-wrap items-center gap-1">
                  <span className="font-mono text-sm text-gray-900">{move.move_san}</span>
                  {planMoves.map((m, i) => (
                    <span key={i} className="font-mono text-sm text-cyan-300">{m}</span>
                  ))}
                </div>
              </div>
            )}
            
            {/* Undo button */}
            {planMoves.length > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onUndoPlanMove}
                className="text-xs text-gray-500"
              >
                ← Undo last move
              </Button>
            )}
            
            {/* Submit plan */}
            <div className="space-y-2">
              <Textarea
                value={planReasoning}
                onChange={(e) => onPlanReasoningChange(e.target.value)}
                placeholder="Why did you think this would work? (optional)"
                className="min-h-[50px] text-sm bg-gray-50 border-gray-200 resize-none"
              />
              <Button
                size="sm"
                onClick={onSubmitPlan}
                disabled={planMoves.length === 0 || analyzingPlan}
                className="w-full bg-cyan-600 hover:bg-cyan-700"
              >
                {analyzingPlan ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin mr-2" />
                    Analyzing your calculation...
                  </>
                ) : (
                  <>
                    <Brain className="w-3 h-3 mr-2" />
                    Analyze my plan
                  </>
                )}
              </Button>
            </div>
            
            <p className="text-xs text-gray-400 text-center">
              Make moves on the board to show your intended line
            </p>
          </div>
        )}

        {/* ─── PLAN ANALYSIS RESULTS ───────────────────────────── */}
        {planAnalysis && isMistake && (
          <div className="bg-gradient-to-b from-cyan-500/10 to-transparent rounded-lg p-4 border border-cyan-500/30 space-y-4" data-testid="plan-analysis">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-cyan-400" />
              <span className="text-sm font-medium text-gray-900">Calculation Analysis</span>
              {planAnalysis.gap_severity === "critical" && (
                <Badge className="bg-red-500/20 text-red-400 text-xs">Critical Gap</Badge>
              )}
              {planAnalysis.gap_severity === "significant" && (
                <Badge className="bg-amber-500/20 text-amber-400 text-xs">Significant Gap</Badge>
              )}
            </div>
            
            {/* Gap type */}
            <div className="p-3 rounded bg-gray-50">
              <p className="text-xs text-gray-500 mb-1">What went wrong</p>
              <p className="text-sm text-gray-900 font-medium">
                {planAnalysis.gap_type === "missed_tactic" && "Missed Tactic"}
                {planAnalysis.gap_type === "calculation_depth" && "Calculation Too Shallow"}
                {planAnalysis.gap_type === "correct_plan" && "Your plan was actually reasonable!"}
              </p>
            </div>
            
            {/* Explanation */}
            <p className="text-sm text-gray-600">{planAnalysis.explanation}</p>
            
            {/* Divergence point */}
            {planAnalysis.divergence_move_number > 0 && (
              <div className="p-3 rounded bg-red-500/10 border border-red-500/20">
                <p className="text-xs text-red-400 mb-1">The critical moment (move {planAnalysis.divergence_move_number})</p>
                <p className="text-sm">
                  You expected <span className="font-mono text-gray-500">{planAnalysis.user_expected_move}</span>
                  {" "}but <span className="font-mono text-emerald-400">{planAnalysis.actual_best_move}</span> changes everything
                </p>
                {planAnalysis.missed_tactic_type && (
                  <p className="text-xs text-amber-400 mt-1">
                    Tactic: {planAnalysis.missed_tactic_type.replace(/_/g, ' ')}
                  </p>
                )}
              </div>
            )}
            
            {/* Eval swing */}
            {planAnalysis.eval_swing > 0 && (
              <p className="text-xs text-gray-500">
                Evaluation swing: <span className="text-red-400">{planAnalysis.eval_swing.toFixed(1)} pawns</span>
              </p>
            )}
            
            {/* Lesson */}
            {planAnalysis.lesson && (
              <div className="p-3 rounded bg-amber-500/10 border border-amber-500/20">
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-amber-200">{planAnalysis.lesson}</p>
                </div>
              </div>
            )}
            
            {/* Try again button */}
            <Button
              size="sm"
              variant="ghost"
              onClick={onStartPlanMode}
              className="text-xs text-cyan-400"
            >
              Show a different line
            </Button>
          </div>
        )}

        {/* ─── FEEDBACK ──────────────────────────────────────── */}
        <div className="flex items-center justify-end pt-2 border-t border-gray-200/50">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onFeedbackClick} 
            className="text-xs text-gray-500 hover:text-red-400" 
            data-testid="btn-not-helpful"
          >
            <ThumbsDown className="w-3 h-3 mr-1" /> Not helpful
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};


// ─── CLICKABLE MOVES COMPONENT ──────────────────────────────────────

const ClickableMoves = ({ text, moves, onMoveClick }) => {
  if (!moves?.length || !text) {
    return <p className="text-gray-900 text-sm">{text}</p>;
  }
  
  // Parse text and make moves clickable
  const movePattern = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]*|O-O-O|O-O)\b/g;
  const parts = [];
  let lastIndex = 0;
  let moveIndex = 0;
  let match;
  
  while ((match = movePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    
    const moveSan = match[0];
    const foundIndex = moves.findIndex((m, i) => 
      i >= moveIndex && m.replace(/[+#]/g, '') === moveSan.replace(/[+#]/g, '')
    );
    
    if (foundIndex !== -1) {
      parts.push({ type: 'move', content: moveSan, moveIndex: foundIndex });
      moveIndex = foundIndex + 1;
    } else {
      parts.push({ type: 'move-inactive', content: moveSan });
    }
    
    lastIndex = match.index + match[0].length;
  }
  
  if (lastIndex < text.length) {
    parts.push({ type: 'text', content: text.slice(lastIndex) });
  }
  
  return (
    <p className="text-gray-900 text-sm">
      {parts.map((part, i) => {
        if (part.type === 'move') {
          return (
            <button
              key={i}
              onClick={() => onMoveClick(moves, part.moveIndex)}
              className="font-mono font-bold text-amber-400 hover:text-amber-300 hover:underline cursor-pointer transition-colors"
              title={`Click to see this on the board`}
            >
              {part.content}
            </button>
          );
        }
        if (part.type === 'move-inactive') {
          return <span key={i} className="font-mono font-semibold text-gray-600">{part.content}</span>;
        }
        return <span key={i}>{part.content}</span>;
      })}
    </p>
  );
};


// ─── FEEDBACK PANEL ─────────────────────────────────────────────────

const FeedbackPanel = ({ move, feedbackText, setFeedbackText, onSubmit, onCancel, submitting }) => (
  <Card className="bg-white border-gray-200" data-testid="feedback-panel">
    <CardContent className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-gray-900">What should the explanation say?</p>
        <Button variant="ghost" size="icon" onClick={onCancel} className="h-6 w-6">
          <X className="w-4 h-4" />
        </Button>
      </div>
      <Textarea 
        value={feedbackText} 
        onChange={(e) => setFeedbackText(e.target.value)}
        placeholder="Write a better explanation..." 
        className="min-h-[100px] bg-gray-100 border-gray-200 text-gray-900" 
        data-testid="feedback-textarea" 
      />
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" onClick={onSubmit} disabled={!feedbackText.trim() || submitting} data-testid="submit-feedback-btn">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />} Submit
        </Button>
      </div>
    </CardContent>
  </Card>
);


// ─── MOVE LIST V5 ───────────────────────────────────────────────────

const MoveListV5 = ({ decryptionData, currentMoveIndex, onMoveClick }) => {
  if (!decryptionData?.length) return null;
  
  const pairs = [];
  for (let i = 0; i < decryptionData.length; i += 2) {
    pairs.push({
      num: decryptionData[i].move_number,
      w: decryptionData[i],
      b: decryptionData[i + 1] || null,
      wi: i,
      bi: i + 1
    });
  }
  
  const moveClass = (m, idx) => {
    if (currentMoveIndex === idx) return 'bg-emerald-500/30 text-gray-900 ring-1 ring-emerald-500/50';
    
    const severity = m.severity || 'good';
    if (severity === 'blunder') return 'text-red-400 bg-red-500/10 hover:bg-red-500/20';
    if (severity === 'mistake') return 'text-red-400 hover:bg-red-500/10';
    if (severity === 'inaccuracy') return 'text-orange-400 hover:bg-orange-500/10';
    if (m.is_best_move) return 'text-emerald-400 hover:bg-emerald-500/10';
    if (!m.is_user_move) return 'text-gray-500 hover:bg-gray-100';
    return 'text-gray-600 hover:bg-gray-100';
  };
  
  const indicator = (m) => {
    const severity = m.severity || 'good';
    if (severity === 'blunder') return <span className="text-red-400 ml-0.5">??</span>;
    if (severity === 'mistake') return <span className="text-red-400 ml-0.5">?</span>;
    if (severity === 'inaccuracy') return <span className="text-orange-400 ml-0.5">?!</span>;
    if (m.is_best_move) return <span className="text-emerald-400 ml-0.5">!</span>;
    return null;
  };

  return (
    <ScrollArea className="h-[180px] rounded-lg border border-gray-200 bg-gray-50">
      <div className="p-2 space-y-1">
        {pairs.map(p => (
          <div key={p.num} className="flex items-center gap-1 text-sm">
            <span className="w-8 text-gray-500 text-right shrink-0">{p.num}.</span>
            <button 
              onClick={() => onMoveClick(p.wi)} 
              className={`px-2 py-0.5 rounded font-mono transition-colors ${moveClass(p.w, p.wi)}`}
            >
              {p.w.move_san}{indicator(p.w)}
            </button>
            {p.b && (
              <button 
                onClick={() => onMoveClick(p.bi)} 
                className={`px-2 py-0.5 rounded font-mono transition-colors ${moveClass(p.b, p.bi)}`}
              >
                {p.b.move_san}{indicator(p.b)}
              </button>
            )}
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};


// ─── HELPER ─────────────────────────────────────────────────────────

const getLastMoveSquares = (move) => {
  if (!move?.fen_before || !move?.move_san) return null;
  try {
    const c = new Chess(move.fen_before);
    const p = c.move(move.move_san);
    return p ? [p.from, p.to] : null;
  } catch { 
    return null; 
  }
};


export default GameDecryptionV5;
