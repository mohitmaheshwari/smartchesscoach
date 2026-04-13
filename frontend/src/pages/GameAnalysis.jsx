/**
 * GAME REVIEW PAGE → Understand
 * 
 * One screen. One job. Understand what went wrong.
 * 
 * Structure:
 * - Board (large, front and center)
 * - Coaching for current move (V5 narrative)
 * - Move list (mistakes highlighted, click to navigate)
 * 
 * That's it. No stats. No strategy tabs. No clutter.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
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
  ChevronRight,
  MessageCircle,
  Send,
  X,
  Zap,
  Target,
  Lightbulb
} from "lucide-react";
import { Input } from "@/components/ui/input";

/* ── Game Overview: phases + opening + behaviors ── */
const GameOverview = ({ review, navigate }) => {
  const phases = review.phases || {};
  const opening = review.opening_analysis;
  const behaviors = review.behaviors || [];
  const keyMoments = review.key_moments || [];
  const fundamentals = review.fundamentals || {};

  return (
    <div className="mb-4 space-y-3">
      {/* Phase Accuracy Bar */}
      <div className="flex gap-2">
        {["opening", "middlegame", "endgame"].map(key => {
          const p = phases[key];
          if (!p) return null;
          const color = p.accuracy >= 80 ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
            : p.accuracy >= 60 ? "bg-amber-500/10 border-amber-500/20 text-amber-400"
            : "bg-red-500/10 border-red-500/20 text-red-400";
          return (
            <div key={key} className={`flex-1 rounded-xl border p-3 ${color}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold">{p.name}</span>
                <span className="text-sm font-bold font-mono">{p.accuracy}%</span>
              </div>
              <p className="text-[10px] opacity-70">{p.verdict} · {p.moves} moves</p>
            </div>
          );
        })}
      </div>

      {/* Opening Awareness */}
      {opening && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-widest text-primary/60">Opening</span>
              <span className="text-sm font-medium text-white">{opening.name}</span>
            </div>
            <span className="text-[10px] text-zinc-500">
              {opening.moves_in_theory}/{opening.total_theory_moves} theory moves
            </span>
          </div>

          {opening.deviation && (
            <p className="text-xs text-zinc-400 mb-2">
              Deviated on move {Math.floor(opening.deviation.ply / 2) + 1}: played <span className="font-mono text-red-400">{opening.deviation.played}</span> instead of <span className="font-mono text-emerald-400">{opening.deviation.expected}</span>
              {opening.deviation.idea && <span className="text-zinc-500"> — {opening.deviation.idea.toLowerCase()}</span>}
            </p>
          )}

          {!opening.deviation && opening.moves_in_theory === opening.total_theory_moves && (
            <p className="text-xs text-emerald-400/70">Followed theory perfectly.</p>
          )}

          {opening.traps?.length > 0 && opening.traps.map((t, i) => {
            const trapColor = t.sprung && t.victim_color === review.user_color
              ? "bg-red-500/10 border-red-500/20"  // User fell for it
              : t.sprung
              ? "bg-emerald-500/10 border-emerald-500/20"  // User sprung it on opponent
              : t.avoided
              ? "bg-emerald-500/5 border-emerald-500/15"  // User avoided it
              : "bg-amber-500/5 border-amber-500/15";  // Position reached
            const iconColor = t.sprung && t.victim_color === review.user_color
              ? "text-red-400" : t.sprung ? "text-emerald-400" : "text-amber-500";

            return (
              <div key={i} className={`mt-2 rounded-lg border px-3 py-2 ${trapColor}`}>
                <div className="flex items-center gap-1.5">
                  <Zap className={`w-3 h-3 ${iconColor}`} strokeWidth={2.5} />
                  <span className={`text-[10px] font-bold ${iconColor}`}>{t.name}</span>
                  {t.sprung && <span className="text-[9px] px-1 py-0 rounded bg-zinc-800 text-zinc-400 ml-auto">
                    {t.victim_color === review.user_color ? "Fell for it" : "Caught them"}
                  </span>}
                  {t.avoided && <span className="text-[9px] px-1 py-0 rounded bg-zinc-800 text-emerald-400 ml-auto">Avoided</span>}
                </div>
                <p className="text-[10px] text-zinc-400 mt-0.5">{t.story || t.explanation}</p>
                {t.sprung && t.victim_color === review.user_color && t.refutation && (
                  <p className="text-[10px] text-zinc-500 mt-1 italic">How to avoid: {t.refutation}</p>
                )}
              </div>
            );
          })}

          {opening.branches && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] text-zinc-500">Variations:</span>
              {opening.branches.branches.map((b, i) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">{b.name}</span>
              ))}
            </div>
          )}

          <button
            onClick={() => navigate(`/play-with-coach?opening=${encodeURIComponent(opening.name)}`)}
            className="mt-2 text-[10px] text-primary hover:text-primary/80 flex items-center gap-1"
          >
            Practice this opening with Coach <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Behavioral Summary + Fundamentals */}
      {(behaviors.length > 0 || Object.keys(fundamentals).length > 0) && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          {/* Behaviors */}
          {behaviors.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-bold uppercase tracking-widest text-red-400/60 mb-2">What went wrong</p>
              {behaviors.map((b, i) => (
                <div key={i} className="flex items-center justify-between py-1">
                  <span className="text-sm text-zinc-300">{b.label}</span>
                  <span className="text-xs font-mono text-zinc-500">{b.count}x</span>
                </div>
              ))}
            </div>
          )}

          {/* Fundamentals by phase */}
          {Object.entries(fundamentals).map(([phase, funds]) => {
            if (!funds || funds.length === 0) return null;
            return (
              <div key={phase} className="mb-2">
                <p className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1 capitalize">{phase} fundamentals</p>
                {funds.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 py-0.5">
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${f.progress >= 70 ? "bg-emerald-500" : f.progress >= 40 ? "bg-amber-400" : "bg-red-400"}`}
                        style={{ width: `${f.progress}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-zinc-400 w-32 truncate">{f.name}</span>
                    <span className="text-[10px] font-mono text-zinc-500 w-6 text-right">{f.progress}</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};


const GameAnalysis = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialMove = searchParams.get('move');
  
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(0);
  const [initialMoveHandled, setInitialMoveHandled] = useState(false);
  
  // V5 Decryption data
  const [decryptionData, setDecryptionData] = useState(null);
  const [decryptionLoading, setDecryptionLoading] = useState(false);
  const [decryptionStatus, setDecryptionStatus] = useState(null);
  
  // Coach Review (fundamentals, phases, opening, behaviors)
  const [coachReview, setCoachReview] = useState(null);

  // Ask About Move
  const [askQuestion, setAskQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [showAsk, setShowAsk] = useState(false);
  const [conversationHistory, setConversationHistory] = useState([]);
  
  const boardRef = useRef(null);

  // Fetch game and analysis
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [gameRes, analysisRes] = await Promise.all([
          fetch(`${API}/games/${gameId}`, { credentials: "include" }),
          fetch(`${API}/analysis/${gameId}`, { credentials: "include" })
        ]);
        
        if (!gameRes.ok) throw new Error("Game not found");
        setGame(await gameRes.json());
        
        if (analysisRes.ok) {
          setAnalysis(await analysisRes.json());
        }
      } catch (error) {
        toast.error("Failed to load game");
        navigate("/lab");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [gameId, navigate]);

  // Fetch coach review (fundamentals, phases, opening)
  useEffect(() => {
    if (!analysis) return;
    (async () => {
      try {
        const res = await fetch(`${API}/games/${gameId}/coach-review`, { credentials: "include" });
        if (res.ok) setCoachReview(await res.json());
      } catch (e) { console.error("Coach review fetch failed:", e); }
    })();
  }, [analysis, gameId]);

  // Fetch V5 decryption data
  useEffect(() => {
    if (!analysis) return;
    
    const fetchDecryption = async () => {
      setDecryptionLoading(true);
      try {
        const res = await fetch(`${API}/coach/decryption/v5/${gameId}`, { 
          credentials: "include" 
        });
        const data = await res.json();
        
        if (data.status === "complete") {
          setDecryptionData(data.decryption_data || []);
          setDecryptionStatus("complete");
        } else if (data.status === "generating") {
          setDecryptionStatus("generating");
          // Poll for completion
          setTimeout(fetchDecryption, 3000);
        } else {
          setDecryptionStatus("error");
        }
      } catch (e) {
        console.error("Decryption fetch error:", e);
        setDecryptionStatus("error");
      } finally {
        setDecryptionLoading(false);
      }
    };
    
    fetchDecryption();
  }, [analysis, gameId]);

  // Jump to initial move from URL
  useEffect(() => {
    if (!initialMoveHandled && initialMove && boardRef.current && !loading && decryptionData) {
      const moveNum = parseInt(initialMove, 10);
      if (!isNaN(moveNum) && moveNum > 0) {
        setTimeout(() => {
          boardRef.current.goToMove(moveNum - 1);
          setCurrentMoveIndex(moveNum - 1);
          setInitialMoveHandled(true);
        }, 300);
      }
    }
  }, [initialMove, loading, initialMoveHandled, decryptionData]);

  // Clear conversation when move changes
  useEffect(() => {
    setConversationHistory([]);
    setShowAsk(false);
  }, [currentMoveIndex]);

  // Derived data
  const pgn = game?.pgn || "";
  const userColor = game?.user_color || "white";
  
  // Get current move's coaching data
  const currentMoveData = decryptionData?.[currentMoveIndex] || null;
  
  // Get all moves for the move list
  const moves = decryptionData || [];

  // Handle analyze
  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const res = await fetch(`${API}/analyze-game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ game_id: gameId })
      });
      
      if (!res.ok) throw new Error("Analysis failed");
      
      const data = await res.json();
      setAnalysis(data);
      toast.success("Analysis complete!");
    } catch (e) {
      toast.error("Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  // Handle ask about position
  const handleAsk = async () => {
    if (!askQuestion.trim() || askLoading) return;
    
    const question = askQuestion.trim();
    setAskQuestion("");
    setAskLoading(true);
    
    try {
      const res = await fetch(`${API}/game/${gameId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: currentMoveData?.fen_after || currentMoveData?.fen_before,
          fen_before: currentMoveData?.fen_before,
          question,
          played_move: currentMoveData?.move_san,
          move_number: currentMoveData?.move_number,
          user_color: userColor,
          conversation_history: conversationHistory.map(h => ({
            question: h.question,
            answer: h.answer
          }))
        })
      });
      
      if (!res.ok) throw new Error("Failed to get answer");
      
      const data = await res.json();
      setConversationHistory(prev => [...prev, {
        question,
        answer: data.answer,
        stockfish: data.stockfish
      }]);
    } catch (e) {
      toast.error("Could not get answer");
      setAskQuestion(question);
    } finally {
      setAskLoading(false);
    }
  };

  // Get severity color
  const getSeverityColor = (severity) => {
    switch (severity) {
      case "blunder": return "text-red-500 bg-red-500/10";
      case "mistake": return "text-orange-500 bg-orange-500/10";
      case "inaccuracy": return "text-yellow-500 bg-yellow-500/10";
      case "good": case "best": return "text-emerald-500 bg-emerald-500/10";
      case "opp_blunder": case "opp_mistake": return "text-blue-500 bg-blue-500/10";
      default: return "text-zinc-400 bg-zinc-500/10";
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case "blunder": return <Zap className="w-4 h-4" />;
      case "mistake": return <AlertTriangle className="w-4 h-4" />;
      case "inaccuracy": return <AlertCircle className="w-4 h-4" />;
      case "good": case "best": return <CheckCircle2 className="w-4 h-4" />;
      case "opp_blunder": case "opp_mistake": return <Target className="w-4 h-4" />;
      default: return null;
    }
  };

  const getSeverityLabel = (severity, isUserMove) => {
    if (!isUserMove) {
      if (severity === "opp_blunder") return "Their blunder";
      if (severity === "opp_mistake") return "Their mistake";
      if (severity === "opp_inaccuracy") return "Their slip";
      return null;
    }
    switch (severity) {
      case "blunder": return "Blunder";
      case "mistake": return "Mistake";
      case "inaccuracy": return "Inaccuracy";
      case "good": return "Good";
      case "best": return "Best";
      default: return null;
    }
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-6xl mx-auto py-4 px-4" data-testid="game-review-page">
        {/* Header - Minimal */}
        <div className="flex items-center gap-3 mb-4">
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => navigate("/lab")}
            className="h-8 w-8"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-white truncate">
              vs {userColor === "white" ? game?.black_player : game?.white_player}
            </h1>
            <p className="text-xs text-zinc-500">
              {game?.result} · {game?.opening_name || "Unknown opening"}
            </p>
          </div>
          {!analysis && (
            <Button onClick={handleAnalyze} disabled={analyzing} size="sm">
              {analyzing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Brain className="w-4 h-4 mr-2" />}
              Analyze
            </Button>
          )}
        </div>

        {/* Game Overview — Phase analysis + Opening + Behaviors */}
        {coachReview && <GameOverview review={coachReview} navigate={navigate} />}

        {/* Main Content - Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

          {/* LEFT: Board + Coaching (3 cols) */}
          <div className="lg:col-span-3 space-y-4">
            
            {/* Chess Board */}
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                {analyzing ? (
                  <div className="flex flex-col items-center justify-center py-20">
                    <div className="relative">
                      <div className="w-16 h-16 rounded-full border-4 border-primary border-t-transparent animate-spin" />
                      <Brain className="w-8 h-8 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                    </div>
                    <p className="mt-4 text-sm text-zinc-400">Analyzing game...</p>
                  </div>
                ) : (
                  <ChessBoardViewer 
                    ref={boardRef}
                    pgn={pgn} 
                    userColor={userColor} 
                    onMoveChange={setCurrentMoveIndex}
                  />
                )}
              </CardContent>
            </Card>

            {/* Coaching Panel - The Heart of Review */}
            {analysis && (
              <Card className="bg-zinc-900/50 border-zinc-800">
                <CardContent className="p-4">
                  {decryptionStatus === "generating" ? (
                    <div className="flex items-center gap-3 py-6">
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                      <div>
                        <p className="text-sm font-medium">Coach is analyzing...</p>
                        <p className="text-xs text-zinc-500">This takes about 45 seconds</p>
                      </div>
                    </div>
                  ) : currentMoveData ? (
                    <div className="space-y-4">
                      {/* Move Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl font-bold text-white">
                            {currentMoveData.move_number}. {currentMoveData.move_san}
                          </span>
                          {getSeverityLabel(currentMoveData.severity, currentMoveData.is_user_move) && (
                            <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${getSeverityColor(currentMoveData.severity)}`}>
                              {getSeverityIcon(currentMoveData.severity)}
                              {getSeverityLabel(currentMoveData.severity, currentMoveData.is_user_move)}
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-zinc-500 capitalize">
                          {currentMoveData.phase}
                        </span>
                      </div>

                      {/* Main Narrative */}
                      <p className="text-sm text-zinc-300 leading-relaxed">
                        {currentMoveData.narrative}
                      </p>

                      {/* Your Plan Now */}
                      {currentMoveData.your_plan_now && (
                        <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
                          <p className="text-sm">
                            <span className="text-primary font-medium">→ </span>
                            {currentMoveData.your_plan_now}
                          </p>
                        </div>
                      )}

                      {/* Best Move (if user made a mistake) */}
                      {currentMoveData.is_user_move && 
                       currentMoveData.best_move_san && 
                       currentMoveData.severity !== "good" && 
                       currentMoveData.severity !== "best" && (
                        <div className="flex items-center gap-2 text-sm">
                          <span className="text-zinc-500">Best was:</span>
                          <span className="font-mono text-emerald-400">{currentMoveData.best_move_san}</span>
                        </div>
                      )}

                      {/* Transferable Learning */}
                      {currentMoveData.plan?.transferable_learning && (
                        <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                          <div className="flex items-start gap-2">
                            <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                            <p className="text-sm text-amber-200/80">
                              {currentMoveData.plan.transferable_learning}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Ask Button */}
                      <div className="pt-2">
                        {!showAsk ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowAsk(true)}
                            className="text-zinc-400 hover:text-white"
                          >
                            <MessageCircle className="w-4 h-4 mr-2" />
                            Ask about this position
                          </Button>
                        ) : (
                          <div className="space-y-3 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-zinc-500">Ask your coach</span>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={() => setShowAsk(false)}
                              >
                                <X className="w-3 h-3" />
                              </Button>
                            </div>
                            
                            {/* Conversation History */}
                            {conversationHistory.length > 0 && (
                              <div className="space-y-2 max-h-40 overflow-y-auto">
                                {conversationHistory.map((ex, i) => (
                                  <div key={i} className="space-y-1">
                                    <p className="text-xs text-zinc-400">Q: {ex.question}</p>
                                    <p className="text-sm text-zinc-200">{ex.answer}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                            
                            {/* Quick suggestions */}
                            <div className="flex flex-wrap gap-1">
                              {["Why is this bad?", "What if I played differently?", "What's the idea here?"].map(q => (
                                <button
                                  key={q}
                                  onClick={() => setAskQuestion(q)}
                                  className="text-xs px-2 py-1 rounded bg-zinc-700 text-zinc-300 hover:bg-zinc-600"
                                >
                                  {q}
                                </button>
                              ))}
                            </div>
                            
                            {/* Input */}
                            <div className="flex gap-2">
                              <Input
                                value={askQuestion}
                                onChange={(e) => setAskQuestion(e.target.value)}
                                placeholder="Ask anything..."
                                className="flex-1 text-sm bg-zinc-800 border-zinc-700"
                                onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                                disabled={askLoading}
                              />
                              <Button size="sm" onClick={handleAsk} disabled={askLoading || !askQuestion.trim()}>
                                {askLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="py-8 text-center text-zinc-500">
                      <Brain className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">Navigate through the game to see coaching</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* RIGHT: Move List (2 cols) */}
          <div className="lg:col-span-2">
            <Card className="bg-zinc-900/50 border-zinc-800 h-full">
              <CardContent className="p-0">
                <div className="p-3 border-b border-zinc-800">
                  <h3 className="text-sm font-medium text-zinc-400">Moves</h3>
                </div>
                <ScrollArea className="h-[600px]">
                  <div className="p-2">
                    {moves.length > 0 ? (
                      <div className="space-y-0.5">
                        {moves.map((move, idx) => {
                          const isActive = idx === currentMoveIndex;
                          const hasSeverity = move.severity && move.severity !== "context" && move.severity !== "good";
                          const isUserMistake = move.is_user_move && hasSeverity;
                          const isOppMistake = !move.is_user_move && (move.severity === "opp_blunder" || move.severity === "opp_mistake");
                          
                          return (
                            <button
                              key={idx}
                              onClick={() => {
                                setCurrentMoveIndex(idx);
                                boardRef.current?.goToMove(idx);
                              }}
                              className={`w-full text-left px-3 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                                isActive 
                                  ? "bg-primary/20 border border-primary/30" 
                                  : isUserMistake
                                    ? "bg-red-500/5 hover:bg-red-500/10 border border-transparent"
                                    : isOppMistake
                                      ? "bg-blue-500/5 hover:bg-blue-500/10 border border-transparent"
                                      : "hover:bg-zinc-800 border border-transparent"
                              }`}
                            >
                              {/* Move number + notation */}
                              <span className={`font-mono text-sm ${
                                isActive ? "text-white" : "text-zinc-400"
                              }`}>
                                {move.move_number}.{!move.is_white && ".."} {move.move_san}
                              </span>
                              
                              {/* Severity badge */}
                              {(isUserMistake || isOppMistake) && (
                                <span className={`ml-auto flex items-center gap-1 text-xs ${getSeverityColor(move.severity)}`}>
                                  {getSeverityIcon(move.severity)}
                                  {move.is_user_move ? (
                                    move.severity === "blunder" ? "!" : 
                                    move.severity === "mistake" ? "?" : "?!"
                                  ) : (
                                    "opportunity"
                                  )}
                                </span>
                              )}
                              
                              {/* Arrow for active */}
                              {isActive && (
                                <ChevronRight className="w-4 h-4 text-primary ml-auto" />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    ) : analysis ? (
                      <div className="py-8 text-center text-zinc-500">
                        <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
                        <p className="text-xs">Loading moves...</p>
                      </div>
                    ) : (
                      <div className="py-8 text-center text-zinc-500">
                        <p className="text-sm">Analyze the game first</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default GameAnalysis;
