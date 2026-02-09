import { useState, useEffect, useRef } from "react";
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
  ChevronDown,
  ChevronUp,
  Volume2,
  VolumeX,
  Mic,
  BookOpen,
  Target,
  Lightbulb,
  TrendingUp,
  Play,
  MessageCircle,
  Send,
  X
} from "lucide-react";
import { Input } from "@/components/ui/input";

const GameAnalysis = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentMoveNumber, setCurrentMoveNumber] = useState(0);
  const [expandedMoves, setExpandedMoves] = useState({});
  
  // Voice coaching state
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const audioRef = useRef(null);
  const boardRef = useRef(null);
  
  // Ask About Move state
  const [askQuestion, setAskQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [askResponse, setAskResponse] = useState(null);
  const [showAskPanel, setShowAskPanel] = useState(false);
  const [conversationHistory, setConversationHistory] = useState([]);  // Q&A history for follow-up questions
  const [lastAskedMoveNumber, setLastAskedMoveNumber] = useState(null);  // Track which move the conversation is about

  // Clear conversation when move changes significantly
  useEffect(() => {
    if (lastAskedMoveNumber !== null && currentMoveNumber !== lastAskedMoveNumber) {
      // User moved to a different position - clear conversation
      setConversationHistory([]);
      setAskResponse(null);
      setLastAskedMoveNumber(null);
    }
  }, [currentMoveNumber, lastAskedMoveNumber]);

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

  // Voice functions
  const playVoiceSummary = async (gId) => {
    if (!voiceEnabled) return;
    setVoiceLoading(true);
    try {
      const url = API + "/tts/analysis-summary/" + gId;
      const response = await fetch(url, { method: "POST", credentials: "include" });
      if (!response.ok) throw new Error("Voice failed");
      const data = await response.json();
      const audioSrc = "data:audio/mp3;base64," + data.audio_base64;
      if (audioRef.current) {
        audioRef.current.src = audioSrc;
        audioRef.current.play();
        setIsPlaying(true);
      }
    } catch (e) {
      console.error("Voice error:", e);
    } finally {
      setVoiceLoading(false);
    }
  };

  const playMoveVoice = async (moveIndex) => {
    if (!voiceEnabled) return;
    setVoiceLoading(true);
    try {
      const url = API + "/tts/move-explanation";
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ game_id: gameId, move_index: moveIndex })
      });
      if (!response.ok) throw new Error("Voice failed");
      const data = await response.json();
      const audioSrc = "data:audio/mp3;base64," + data.audio_base64;
      if (audioRef.current) {
        audioRef.current.src = audioSrc;
        audioRef.current.play();
        setIsPlaying(true);
      }
    } catch (e) {
      console.error("Move voice error:", e);
    } finally {
      setVoiceLoading(false);
    }
  };

  const stopVoice = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlaying(false);
    }
  };

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
      if (voiceEnabled) {
        setTimeout(() => playVoiceSummary(gameId), 500);
      }
    } catch (error) {
      toast.error(error.message || "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleMoveExpanded = (index) => {
    setExpandedMoves(prev => ({ ...prev, [index]: !prev[index] }));
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
  const termination = game ? game.termination_text : "";
  
  const commentary = analysis ? analysis.commentary : [];
  const blunders = analysis ? analysis.blunders : 0;
  const mistakes = analysis ? analysis.mistakes : 0;
  const inaccuracies = analysis ? analysis.inaccuracies : 0;
  const bestMoves = analysis ? analysis.best_moves : 0;
  
  // Stockfish accuracy data
  const stockfishData = analysis ? analysis.stockfish_analysis : null;
  const accuracy = stockfishData ? stockfishData.accuracy : null;
  const avgCpLoss = stockfishData ? stockfishData.avg_cp_loss : null;
  const excellentMoves = stockfishData ? stockfishData.excellent_moves : 0;
  const moveEvaluations = stockfishData ? stockfishData.move_evaluations : [];
  
  // Full game moves (including opponent)
  const fullMoves = analysis ? analysis.full_moves : [];
  
  // Best move suggestions from Stockfish
  const bestMoveSuggestions = analysis ? analysis.best_move_suggestions : [];
  
  // New split summary format
  const summaryP1 = analysis ? (analysis.summary_p1 || analysis.overall_summary || "") : "";
  const summaryP2 = analysis ? (analysis.summary_p2 || "") : "";
  const improvementNote = analysis ? analysis.improvement_note : "";
  const focusThisWeek = analysis ? (analysis.focus_this_week || analysis.key_lesson || "") : "";
  
  // Phase-aware strategic coaching (NEW)
  const phaseAnalysis = analysis ? analysis.phase_analysis : null;
  const strategicLesson = analysis ? analysis.strategic_lesson : null;
  const phaseTheory = analysis ? analysis.phase_theory : null;
  
  let weaknesses = [];
  if (analysis && analysis.weaknesses) weaknesses = analysis.weaknesses;
  if (analysis && analysis.identified_weaknesses) weaknesses = analysis.identified_weaknesses;
  
  let patterns = [];
  if (analysis && analysis.identified_patterns) patterns = analysis.identified_patterns;

  const getEvalColor = (ev) => {
    if (ev === "blunder") return "border-l-red-500 bg-red-500/5";
    if (ev === "mistake") return "border-l-orange-500 bg-orange-500/5";
    if (ev === "inaccuracy") return "border-l-yellow-500 bg-yellow-500/5";
    if (ev === "good" || ev === "solid") return "border-l-emerald-500 bg-emerald-500/5";
    return "border-l-muted-foreground/30";
  };

  const getEvalIcon = (ev) => {
    if (ev === "blunder") return <AlertTriangle className="w-4 h-4 text-red-500" />;
    if (ev === "mistake") return <AlertCircle className="w-4 h-4 text-orange-500" />;
    if (ev === "inaccuracy") return <AlertCircle className="w-4 h-4 text-yellow-500" />;
    if (ev === "good" || ev === "solid") return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
    return null;
  };

  const isMistake = (ev) => ev === "blunder" || ev === "mistake" || ev === "inaccuracy";

  // Jump to move on the board when clicking a move
  const handleMoveClick = (ply) => {
    if (boardRef.current) {
      // ply is the index in the full game (0, 1, 2, 3...)
      boardRef.current.goToMove(ply);
    }
  };

  // Render a single move in the full moves list (including opponent moves)
  const renderFullMove = (move, index) => {
    const isUserMove = move.is_user_move;
    const ev = move.evaluation;
    
    // Get color class based on evaluation
    let colorClass = "border-l-muted-foreground/30 bg-muted/10"; // Default for opponent/neutral
    if (isUserMove) {
      if (ev === "blunder") colorClass = "border-l-red-500 bg-red-500/10";
      else if (ev === "mistake") colorClass = "border-l-orange-500 bg-orange-500/10";
      else if (ev === "inaccuracy") colorClass = "border-l-yellow-500 bg-yellow-500/10";
      else if (ev === "good" || ev === "solid" || ev === "excellent") colorClass = "border-l-emerald-500 bg-emerald-500/10";
      else colorClass = "border-l-blue-500/50 bg-blue-500/5";
    }
    
    const icon = isUserMove ? getEvalIcon(ev) : null;
    const isActive = currentMoveNumber === move.move_number && (
      (move.is_white && userColor === "white") || (!move.is_white && userColor === "black")
    );
    
    return (
      <div
        key={index}
        onClick={() => handleMoveClick(move.ply)}
        className={`p-2 rounded border-l-4 cursor-pointer transition-all hover:ring-1 hover:ring-primary/30 ${colorClass} ${isActive ? "ring-2 ring-primary" : ""}`}
      >
        <div className="flex items-center gap-2">
          {/* Move number - show only for white's move */}
          <span className="text-xs text-muted-foreground w-6">
            {move.is_white ? `${move.move_number}.` : ""}
          </span>
          
          {/* Player indicator */}
          <span className={`text-xs px-1.5 py-0.5 rounded ${
            isUserMove 
              ? "bg-primary/20 text-primary" 
              : "bg-muted text-muted-foreground"
          }`}>
            {isUserMove ? "You" : "Opp"}
          </span>
          
          {/* Move */}
          <span className="font-mono text-sm font-medium flex-1">
            {move.move}
          </span>
          
          {/* Evaluation icon for user moves */}
          {icon && <span>{icon}</span>}
          
          {/* Evaluation badge for significant moves */}
          {isUserMove && isMistake(ev) && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              ev === "blunder" ? "bg-red-500/20 text-red-500" :
              ev === "mistake" ? "bg-orange-500/20 text-orange-500" :
              "bg-yellow-500/20 text-yellow-500"
            }`}>
              {ev === "blunder" ? "Discipline broke" : ev === "mistake" ? "Slipped" : "Imprecise"}
            </span>
          )}
        </div>
        
        {/* Feedback for user's significant moves */}
        {isUserMove && move.feedback && isMistake(ev) && (
          <p className="text-xs text-muted-foreground mt-1 ml-8 line-clamp-2">
            {move.feedback}
          </p>
        )}
      </div>
    );
  };

  const renderMoveComment = (item, index) => {
    const colorClass = getEvalColor(item.evaluation);
    const icon = getEvalIcon(item.evaluation);
    const isActive = currentMoveNumber === item.move_number;
    const isExpanded = expandedMoves[index];
    const showExpandable = isMistake(item.evaluation) && item.details;
    
    // Support both old and new field names
    const intent = item.intent || item.player_intention || "";
    const feedback = item.feedback || item.coach_response || item.comment || "";
    const consider = item.consider || item.better_move || "";
    const memoryNote = item.memory_note || item.memory_reference || "";
    const details = item.details || item.explanation || {};
    const rule = details.rule || details.one_repeatable_rule || "";
    
    return (
      <div 
        key={index}
        onClick={() => handleMoveClick(item.move_number)}
        className={"p-3 rounded-lg border-l-4 cursor-pointer transition-all hover:ring-1 hover:ring-primary/50 " + colorClass + " " + (isActive ? "ring-2 ring-primary" : "")}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-medium">
              {item.move_number}. {item.move}
            </span>
            {icon}
            {item.evaluation && item.evaluation !== "neutral" && (
              <Badge variant="outline" className="text-xs capitalize">
                {item.evaluation}
              </Badge>
            )}
            {/* Show CP loss for mistakes - from Stockfish */}
            {isMistake(item.evaluation) && item.cp_loss > 0 && (
              <span className="text-xs text-muted-foreground font-mono">
                -{(item.cp_loss / 100).toFixed(1)}
              </span>
            )}
          </div>
          {voiceEnabled && feedback && (
            <button
              onClick={(e) => { e.stopPropagation(); playMoveVoice(index); }}
              className="text-muted-foreground hover:text-primary p-1"
              disabled={voiceLoading}
            >
              <Volume2 className="w-3 h-3" />
            </button>
          )}
        </div>
        
        {/* Memory Reference - Always visible when present */}
        {memoryNote && (
          <p className="text-xs text-amber-600 dark:text-amber-400 mb-2">
            ⚠️ {memoryNote}
          </p>
        )}
        
        {/* DEFAULT VIEW: Intent + Feedback + Rule */}
        {intent && (
          <p className="text-sm text-blue-600 dark:text-blue-400 italic mb-1">
            {intent}
          </p>
        )}
        
        {feedback && (
          <p className="text-sm text-muted-foreground mb-2">{feedback}</p>
        )}
        
        {rule && (
          <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
            → {rule}
          </p>
        )}
        
        {/* EXPAND TOGGLE - Only for mistakes with details */}
        {showExpandable && (
          <button
            onClick={() => toggleMoveExpanded(index)}
            className="mt-2 text-xs text-muted-foreground hover:text-primary flex items-center gap-1"
          >
            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {isExpanded ? "Less" : "More details"}
          </button>
        )}
        
        {/* EXPANDED VIEW - Additional details */}
        {isExpanded && details && (
          <div className="mt-2 pt-2 border-t border-muted/50 space-y-1 text-xs">
            {details.thinking_pattern && details.thinking_pattern !== "solid_thinking" && (
              <p className="text-muted-foreground">
                <span className="text-orange-500">Pattern:</span> {details.thinking_pattern.split("_").join(" ")}
              </p>
            )}
            {details.habit_note && (
              <p className="text-muted-foreground">{details.habit_note}</p>
            )}
            {consider && (
              <p className="text-blue-500">
                Consider: {consider}
              </p>
            )}
          </div>
        )}
        
        {/* BEST MOVE SUGGESTION - Show for mistakes */}
        {isMistake(item.evaluation) && getBestMoveForMove(item.move_number) && (
          <div className="mt-2 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded text-xs">
            <div className="flex items-center justify-between">
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                The disciplined move: <span className="font-mono">{getBestMoveForMove(item.move_number).best_move}</span>
              </span>
              {getBestMoveForMove(item.move_number).pv && (
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-6 px-2 text-xs gap-1 text-emerald-600 hover:text-emerald-700"
                  onClick={() => playVariationOnBoard(item.move_number, [getBestMoveForMove(item.move_number).best_move, ...getBestMoveForMove(item.move_number).pv.slice(0, 4)])}
                >
                  <Play className="w-3 h-3" /> Play
                </Button>
              )}
            </div>
            {getBestMoveForMove(item.move_number).reason && (
              <p className="text-muted-foreground mt-1">{getBestMoveForMove(item.move_number).reason}</p>
            )}
          </div>
        )}
      </div>
    );
  };

  // Helper to get best move suggestion for a move number
  const getBestMoveForMove = (moveNumber) => {
    if (!analysis || !analysis.best_move_suggestions) return null;
    return analysis.best_move_suggestions.find(s => s.move_number === moveNumber);
  };

  // Helper to get FEN at a specific move number
  const getFenAtMove = (moveNumber) => {
    // Try from move evaluations first
    if (moveEvaluations && moveEvaluations.length > 0) {
      const evalAtMove = moveEvaluations.find(e => e.move_number === moveNumber);
      if (evalAtMove?.fen) return evalAtMove.fen;
    }
    
    // Try from commentary
    if (commentary && commentary.length > 0) {
      const commentAtMove = commentary.find(c => c.move_number === moveNumber);
      if (commentAtMove?.fen) return commentAtMove.fen;
    }
    
    return null;
  };

  // Play a variation on the board
  const playVariationOnBoard = (moveNumber, variation) => {
    if (!boardRef.current || !variation || variation.length === 0) return;
    
    const fen = getFenAtMove(moveNumber);
    if (!fen) {
      toast.error("Position not available");
      return;
    }
    
    boardRef.current.playVariation(fen, variation, game?.user_color || 'white');
    toast.success("Playing variation...");
  };

  // Get current FEN from the board (position AFTER the move)
  const getCurrentFen = () => {
    // First, try to get FEN directly from the board component (most accurate)
    if (boardRef.current && boardRef.current.getCurrentFen) {
      const boardFen = boardRef.current.getCurrentFen();
      if (boardFen) {
        return boardFen;
      }
    }
    
    // Fallback: Try to get FEN from current move in move evaluations
    if (moveEvaluations && moveEvaluations.length > 0) {
      const evalAtMove = moveEvaluations.find(e => e.move_number === currentMoveNumber);
      if (evalAtMove?.fen) return evalAtMove.fen;
      if (evalAtMove?.fen_before) return evalAtMove.fen_before;
    }
    
    // Fallback: Try from commentary
    if (commentary && commentary.length > 0) {
      const commentAtMove = commentary.find(c => c.move_number === currentMoveNumber);
      if (commentAtMove?.fen) return commentAtMove.fen;
    }
    
    // Last resort: Return starting position
    console.warn("Could not get FEN, using starting position");
    return "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
  };

  // Get FEN BEFORE the current move (for analyzing what user should have played)
  const getFenBeforeMove = () => {
    if (boardRef.current && boardRef.current.getFenBeforeMove) {
      const fenBefore = boardRef.current.getFenBeforeMove();
      if (fenBefore) {
        return fenBefore;
      }
    }
    
    // Fallback: Try from move evaluations
    if (moveEvaluations && moveEvaluations.length > 0) {
      const evalAtMove = moveEvaluations.find(e => e.move_number === currentMoveNumber);
      if (evalAtMove?.fen_before) return evalAtMove.fen_before;
    }
    
    return null;  // Return null if we can't determine it
  };

  // Get the move played at current position
  const getPlayedMoveAtCurrent = () => {
    if (fullMoves && fullMoves.length > 0) {
      const moveAtPos = fullMoves.find(m => m.move_number === currentMoveNumber && m.is_user_move);
      if (moveAtPos) return moveAtPos.move;
    }
    if (commentary && commentary.length > 0) {
      const commentAtMove = commentary.find(c => c.move_number === currentMoveNumber);
      if (commentAtMove) return commentAtMove.move;
    }
    return null;
  };

  // Handle asking about the current position
  const handleAskAboutMove = async () => {
    // Prevent double submission
    if (askLoading) {
      console.log("Blocked: Already loading");
      return;
    }
    
    if (!askQuestion.trim()) {
      toast.error("Please enter a question");
      return;
    }
    
    const fen = getCurrentFen();
    const fenBefore = getFenBeforeMove();  // Position BEFORE the move (for analyzing alternatives)
    const playedMove = getPlayedMoveAtCurrent();
    const questionToAsk = askQuestion.trim();
    const currentHistory = [...conversationHistory]; // Snapshot the history
    
    console.log("Starting ask request:", { fen, fenBefore, playedMove, questionToAsk, historyLength: currentHistory.length });
    
    // Clear input immediately to prevent double submit
    setAskQuestion("");
    setAskLoading(true);
    
    try {
      const url = API + "/game/" + gameId + "/ask";
      console.log("Fetching:", url);
      
      // Only send question/answer strings to backend (not stockfish objects)
      const historyForBackend = currentHistory.map(h => ({
        question: h.question,
        answer: h.answer
      }));
      
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen: fen,
          fen_before: fenBefore,  // Send position BEFORE the move too
          question: questionToAsk,
          played_move: playedMove,
          move_number: currentMoveNumber,
          user_color: userColor,
          conversation_history: historyForBackend
        })
      });
      
      console.log("Response received, status:", response.status);
      
      // Read response as text first to avoid body stream issues
      const responseText = await response.text();
      console.log("Response text length:", responseText.length);
      
      let data;
      try {
        data = JSON.parse(responseText);
      } catch (parseError) {
        console.error("JSON parse error:", parseError, "Response:", responseText.substring(0, 500));
        throw new Error("Invalid response from server");
      }
      
      console.log("Parsed data successfully");
      
      if (!response.ok) {
        throw new Error(data.detail || "Failed to get answer");
      }
      
      setAskResponse(data);
      
      // Track which move this conversation is about
      setLastAskedMoveNumber(currentMoveNumber);
      
      // Add to conversation history (keep stockfish for frontend display)
      setConversationHistory(prev => [...prev, {
        question: questionToAsk,
        answer: data.answer,
        stockfish: data.stockfish
      }]);
      
      console.log("Ask completed successfully");
      
    } catch (error) {
      // Restore the question if there was an error
      setAskQuestion(questionToAsk);
      toast.error(error.message || "Failed to analyze position");
      console.error("Ask error:", error);
    } finally {
      setAskLoading(false);
    }
  };

  // Clear conversation when moving to a different position
  const handleClearConversation = () => {
    setConversationHistory([]);
    setAskResponse(null);
    setAskQuestion("");
  };

  // Get evaluation of current move
  const getCurrentMoveEvaluation = () => {
    // Try fullMoves first
    if (fullMoves && fullMoves.length > 0) {
      const moveAtPos = fullMoves.find(m => m.move_number === currentMoveNumber && m.is_user_move);
      if (moveAtPos?.evaluation) return moveAtPos.evaluation;
    }
    // Try commentary
    if (commentary && commentary.length > 0) {
      const commentAtMove = commentary.find(c => c.move_number === currentMoveNumber);
      if (commentAtMove?.evaluation) return commentAtMove.evaluation;
    }
    // Try moveEvaluations from Stockfish
    if (moveEvaluations && moveEvaluations.length > 0) {
      const evalAtMove = moveEvaluations.find(e => e.move_number === currentMoveNumber);
      if (evalAtMove?.evaluation) {
        // Handle enum values
        const ev = evalAtMove.evaluation;
        return typeof ev === 'object' && ev.value ? ev.value : ev;
      }
    }
    return null;
  };

  // Suggested questions based on current position
  const getSuggestedQuestions = () => {
    // If there's conversation history, offer follow-up questions
    if (conversationHistory.length > 0) {
      return [
        "What happens after that?",
        "Why not a different move?",
        "What's the main idea?"
      ];
    }
    
    const questions = [
      "What was the best move here?",
      "What was my opponent threatening?",
      "What should my plan be?",
    ];
    
    // Add move-specific question based on actual evaluation
    const playedMove = getPlayedMoveAtCurrent();
    const evaluation = getCurrentMoveEvaluation();
    
    if (playedMove && evaluation) {
      if (evaluation === "blunder") {
        questions.unshift(`Why was ${playedMove} a blunder?`);
      } else if (evaluation === "mistake") {
        questions.unshift(`Why was ${playedMove} a mistake?`);
      } else if (evaluation === "inaccuracy") {
        questions.unshift(`Why was ${playedMove} inaccurate?`);
      } else if (evaluation === "good" || evaluation === "solid" || evaluation === "excellent") {
        questions.unshift(`Why was ${playedMove} a good move?`);
      } else {
        questions.unshift(`Tell me about ${playedMove}`);
      }
    }
    
    return questions.slice(0, 3);
  };

  const renderWeakness = (w, i) => {
    const name = w.subcategory ? w.subcategory.split("_").join(" ") : "pattern";
    const desc = w.habit_description || w.description || "";
    const tip = w.practice_tip || w.coach_advice || w.advice || "";
    return (
      <div key={i} className="p-2 rounded bg-muted/50 text-sm">
        <span className="font-medium capitalize">{name}</span>
        {desc && <p className="text-muted-foreground text-xs mt-1">{desc}</p>}
        {tip && <p className="text-emerald-600 dark:text-emerald-400 text-xs mt-1">→ {tip}</p>}
      </div>
    );
  };

  return (
    <Layout user={user}>
      <audio ref={audioRef} onEnded={() => setIsPlaying(false)} onPause={() => setIsPlaying(false)} />
      
      <div className="space-y-6" data-testid="game-analysis-page">
        {/* Header */}
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
                {termination && <span className="ml-2 text-amber-400">• {termination}</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => { if (isPlaying) stopVoice(); setVoiceEnabled(!voiceEnabled); }}
              title={voiceEnabled ? "Disable voice" : "Enable voice"}
            >
              {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </Button>
            {isPlaying && (
              <Button variant="outline" size="sm" onClick={stopVoice}>Stop</Button>
            )}
            {!analysis && (
              <Button onClick={handleAnalyze} disabled={analyzing} className="glow-primary">
                {analyzing ? (
                  <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analyzing...</>
                ) : (
                  <><Brain className="w-4 h-4 mr-2" />Analyze with AI</>
                )}
              </Button>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Board */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded bg-primary/10 flex items-center justify-center text-xs font-bold">♟</span>
                  Board
                </div>
                {analysis && (
                  <Button
                    variant={showAskPanel ? "default" : "outline"}
                    size="sm"
                    onClick={() => setShowAskPanel(!showAskPanel)}
                    className="gap-1.5"
                    data-testid="ask-about-move-toggle"
                  >
                    <MessageCircle className="w-4 h-4" />
                    Ask
                  </Button>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {analyzing ? (
                <div className="flex flex-col items-center justify-center py-16 space-y-4">
                  <div className="relative">
                    <div className="w-16 h-16 rounded-full border-4 border-primary border-t-transparent animate-spin" />
                    <Brain className="w-8 h-8 text-primary absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
                  </div>
                  <p className="font-medium">Analyzing...</p>
                </div>
              ) : (
                <ChessBoardViewer 
                  ref={boardRef}
                  pgn={pgn} 
                  userColor={userColor} 
                  onMoveChange={setCurrentMoveNumber} 
                  commentary={commentary} 
                />
              )}
              
              {/* Ask About This Move Panel */}
              {showAskPanel && analysis && (
                <div className="mt-4 p-4 rounded-lg bg-gradient-to-r from-violet-500/10 to-blue-500/10 border border-violet-500/20" data-testid="ask-about-move-panel">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium flex items-center gap-2">
                      <MessageCircle className="w-4 h-4 text-violet-500" />
                      Ask About This Position
                      {conversationHistory.length > 0 && (
                        <span className="text-xs text-muted-foreground">
                          ({conversationHistory.length} message{conversationHistory.length !== 1 ? 's' : ''})
                        </span>
                      )}
                    </p>
                    <div className="flex items-center gap-1">
                      {conversationHistory.length > 0 && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
                          onClick={handleClearConversation}
                        >
                          Clear
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setShowAskPanel(false)}>
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  
                  {/* Conversation History */}
                  {conversationHistory.length > 0 && (
                    <div className="mb-4 max-h-48 overflow-y-auto space-y-3" data-testid="conversation-history">
                      {conversationHistory.map((exchange, i) => (
                        <div key={i} className="space-y-2">
                          {/* User Question */}
                          <div className="flex items-start gap-2">
                            <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                              <span className="text-xs text-primary">Q</span>
                            </div>
                            <p className="text-sm text-muted-foreground">{exchange.question}</p>
                          </div>
                          {/* Coach Answer */}
                          <div className="flex items-start gap-2 ml-2">
                            <div className="w-5 h-5 rounded-full bg-violet-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                              <Brain className="w-3 h-3 text-violet-500" />
                            </div>
                            <div className="flex-1">
                              <p className="text-sm">{exchange.answer}</p>
                              {exchange.stockfish?.best_move && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  Best: <span className="font-mono text-violet-500">
                                    {typeof exchange.stockfish.best_move === 'object' 
                                      ? exchange.stockfish.best_move.san || exchange.stockfish.best_move.uci 
                                      : exchange.stockfish.best_move}
                                  </span>
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* Suggested Questions */}
                  <div className="flex flex-wrap gap-2 mb-3">
                    {getSuggestedQuestions().map((q, i) => (
                      <button
                        key={i}
                        onClick={() => setAskQuestion(q)}
                        className="text-xs px-2 py-1 rounded-full bg-violet-500/20 text-violet-600 dark:text-violet-400 hover:bg-violet-500/30 transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                  
                  {/* Question Input */}
                  <div className="flex gap-2">
                    <Input
                      value={askQuestion}
                      onChange={(e) => setAskQuestion(e.target.value)}
                      placeholder={conversationHistory.length > 0 ? "Ask a follow-up question..." : "e.g., What if I played Nf3 instead?"}
                      className="flex-1 text-sm"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !askLoading && askQuestion.trim()) {
                          e.preventDefault();
                          handleAskAboutMove();
                        }
                      }}
                      disabled={askLoading}
                      data-testid="ask-question-input"
                    />
                    <Button 
                      size="sm" 
                      onClick={handleAskAboutMove} 
                      disabled={askLoading || !askQuestion.trim()}
                      data-testid="ask-submit-btn"
                    >
                      {askLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                  
                  {/* Current Response (for alternative analysis display) */}
                  {askResponse?.alternative_analysis && !askResponse.alternative_analysis.error && (
                    <div className="mt-3 p-2 rounded bg-blue-500/10 border border-blue-500/20 text-xs">
                      <span className="font-medium text-blue-600 dark:text-blue-400">
                        After {askResponse.alternative_analysis.move}:
                      </span>
                      <span className="ml-2 font-mono">
                        eval {(askResponse.alternative_analysis.evaluation / 100).toFixed(1)}
                      </span>
                      {askResponse.alternative_analysis.opponent_best_response && (
                        <span className="ml-2 text-muted-foreground">
                          → {askResponse.alternative_analysis.opponent_best_response}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                Coach
              </CardTitle>
            </CardHeader>
            <CardContent>
              {analysis ? (
                <Tabs defaultValue="summary" className="w-full">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="summary">Summary</TabsTrigger>
                    <TabsTrigger value="strategy">Strategy</TabsTrigger>
                    <TabsTrigger value="moves">Moves</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="summary" className="space-y-4 mt-4">
                    {/* Stockfish Accuracy - NEW */}
                    {accuracy !== null && (
                      <div className="p-4 rounded-lg bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center">
                              <span className="text-xl font-bold text-blue-500">{accuracy}%</span>
                            </div>
                            <div>
                              <p className="font-medium">Accuracy</p>
                              <p className="text-xs text-muted-foreground">Powered by Stockfish 15</p>
                            </div>
                          </div>
                          {avgCpLoss !== null && (
                            <div className="text-right">
                              <p className="text-sm font-medium">{avgCpLoss} cp</p>
                              <p className="text-xs text-muted-foreground">Avg. loss</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Stats */}
                    <div className="grid grid-cols-4 gap-2">
                      <div className="text-center p-2 rounded-lg bg-red-500/10">
                        <p className="text-xl font-bold text-red-500">{blunders}</p>
                        <p className="text-xs text-muted-foreground">Blunders</p>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-orange-500/10">
                        <p className="text-xl font-bold text-orange-500">{mistakes}</p>
                        <p className="text-xs text-muted-foreground">Mistakes</p>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-yellow-500/10">
                        <p className="text-xl font-bold text-yellow-500">{inaccuracies}</p>
                        <p className="text-xs text-muted-foreground">Inaccuracies</p>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-emerald-500/10">
                        <p className="text-xl font-bold text-emerald-500">{bestMoves}</p>
                        <p className="text-xs text-muted-foreground">Good</p>
                      </div>
                    </div>

                    {/* Coach Summary - Split into 2 paragraphs */}
                    <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                          <Brain className="w-5 h-5 text-primary" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-2">
                            <p className="font-medium text-sm">Coach</p>
                            {voiceEnabled && (
                              <button
                                onClick={() => playVoiceSummary(gameId)}
                                disabled={voiceLoading}
                                className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
                              >
                                {voiceLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : isPlaying ? <Mic className="w-3 h-3 animate-pulse" /> : <Volume2 className="w-3 h-3" />}
                                {isPlaying ? "Playing" : "Listen"}
                              </button>
                            )}
                          </div>
                          {summaryP1 && <p className="text-sm text-muted-foreground mb-2">{summaryP1}</p>}
                          {summaryP2 && <p className="text-sm text-muted-foreground">{summaryP2}</p>}
                        </div>
                      </div>
                    </div>

                    {/* Improvement Note */}
                    {improvementNote && (
                      <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                        <p className="text-sm text-blue-600 dark:text-blue-400">📈 {improvementNote}</p>
                      </div>
                    )}

                    {/* Focus This Week */}
                    {focusThisWeek && (
                      <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                        <p className="text-sm font-medium text-amber-600 dark:text-amber-400 mb-1">Focus This Week</p>
                        <p className="text-sm">{focusThisWeek}</p>
                      </div>
                    )}

                    {/* Habits to Work On */}
                    {weaknesses.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium">Habits to Work On</p>
                        <div className="space-y-2">
                          {weaknesses.map(renderWeakness)}
                        </div>
                      </div>
                    )}
                  </TabsContent>

                  {/* STRATEGY TAB - Phase-Aware Coaching */}
                  <TabsContent value="strategy" className="space-y-4 mt-4">
                    {strategicLesson ? (
                      <>
                        {/* Game Phase Summary */}
                        {phaseAnalysis && (
                          <div className="p-4 rounded-lg bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20">
                            <div className="flex items-center gap-2 mb-2">
                              <TrendingUp className="w-4 h-4 text-purple-500" />
                              <p className="font-medium text-sm">Game Phases</p>
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {phaseAnalysis.phase_summary || `This game reached the ${phaseAnalysis.final_phase || 'middlegame'} phase.`}
                            </p>
                            {phaseAnalysis.phases && phaseAnalysis.phases.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-3">
                                {phaseAnalysis.phases.map((p, i) => (
                                  <span 
                                    key={i} 
                                    className={`text-xs px-2 py-1 rounded ${
                                      p.phase === 'opening' ? 'bg-green-500/20 text-green-400' :
                                      p.phase === 'middlegame' ? 'bg-yellow-500/20 text-yellow-400' :
                                      'bg-blue-500/20 text-blue-400'
                                    }`}
                                  >
                                    {p.phase.charAt(0).toUpperCase() + p.phase.slice(1)} ({p.start_move}-{p.end_move})
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Strategic Lesson */}
                        <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
                          <div className="flex items-center gap-2 mb-3">
                            <Lightbulb className="w-4 h-4 text-amber-500" />
                            <p className="font-medium text-sm">{strategicLesson.lesson_title || "Strategic Lesson"}</p>
                            {strategicLesson.rating_bracket && (
                              <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 capitalize">
                                {strategicLesson.rating_bracket}
                              </span>
                            )}
                          </div>
                          
                          {/* One Sentence Takeaway - Main message */}
                          {strategicLesson.one_sentence_takeaway && (
                            <p className="text-sm font-medium text-amber-600 dark:text-amber-400 mb-3">
                              {strategicLesson.one_sentence_takeaway}
                            </p>
                          )}
                          
                          {/* What to Remember */}
                          {strategicLesson.what_to_remember && strategicLesson.what_to_remember.length > 0 && (
                            <div className="space-y-1.5 mb-3">
                              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Remember</p>
                              {strategicLesson.what_to_remember.slice(0, 4).map((item, i) => (
                                <p key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                  <span className="text-amber-500 mt-0.5">•</span>
                                  <span>{item}</span>
                                </p>
                              ))}
                            </div>
                          )}
                          
                          {/* Next Step - Actionable */}
                          {strategicLesson.next_step && (
                            <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20 mt-3">
                              <p className="text-xs font-medium text-emerald-500 mb-1">Next Step</p>
                              <p className="text-sm text-emerald-600 dark:text-emerald-400">{strategicLesson.next_step}</p>
                            </div>
                          )}
                        </div>

                        {/* Phase Theory - Key Principles */}
                        {phaseTheory && phaseTheory.key_principles && phaseTheory.key_principles.length > 0 && (
                          <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                            <div className="flex items-center gap-2 mb-3">
                              <BookOpen className="w-4 h-4 text-blue-500" />
                              <p className="font-medium text-sm">{phaseTheory.phase?.charAt(0).toUpperCase() + phaseTheory.phase?.slice(1) || "Phase"} Principles</p>
                            </div>
                            
                            {/* Key Concept - Highlighted */}
                            {phaseTheory.key_concept && (
                              <div className="p-2 rounded bg-blue-500/20 mb-3">
                                <p className="text-sm font-medium text-blue-600 dark:text-blue-400">
                                  {phaseTheory.key_concept}
                                </p>
                              </div>
                            )}
                            
                            {/* Principles List */}
                            <div className="space-y-1.5">
                              {phaseTheory.key_principles.slice(0, 5).map((principle, i) => (
                                <p key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                                  <span className="text-blue-500 font-mono text-xs mt-0.5">{i + 1}.</span>
                                  <span>{principle}</span>
                                </p>
                              ))}
                            </div>
                            
                            {/* One Thing to Remember */}
                            {phaseTheory.one_thing_to_remember && (
                              <div className="mt-3 pt-3 border-t border-blue-500/20">
                                <p className="text-xs text-muted-foreground">
                                  <span className="text-blue-500 font-medium">One thing to remember:</span>{" "}
                                  {phaseTheory.one_thing_to_remember}
                                </p>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Theory to Study */}
                        {strategicLesson.theory_to_study && strategicLesson.theory_to_study.length > 0 && (
                          <div className="p-3 rounded-lg bg-muted/50">
                            <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                              <Target className="w-3 h-3" />
                              Recommended Study
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {strategicLesson.theory_to_study.map((topic, i) => (
                                <span key={i} className="text-xs px-2 py-1 rounded bg-muted text-muted-foreground">
                                  {topic}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-12 text-center">
                        <BookOpen className="w-12 h-12 text-muted-foreground/30 mb-3" />
                        <p className="text-sm text-muted-foreground">
                          Strategic analysis not available for this game.
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Re-analyze the game to get phase-aware coaching.
                        </p>
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="moves" className="mt-4">
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-1">
                        {fullMoves.length > 0 ? (
                          fullMoves.map(renderFullMove)
                        ) : (
                          commentary.map(renderMoveComment)
                        )}
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
                  <p className="text-sm text-muted-foreground text-center">
                    Click &ldquo;Analyze with AI&rdquo; to get coaching feedback
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
