/**
 * CoachPlay.jsx - Play With Coach Feature (P2)
 * 
 * A training mode where users play full games against a pedagogical coach engine.
 * Now with Live Socratic Coaching - the coach asks WHY you played each move!
 * 
 * Features:
 * - Pre-move guardian: Catches blunders before they happen
 * - Live reflection: Coach asks "Why did you play that?" after each move
 * - Socratic feedback: Targeted coaching based on your reasoning
 * - Eval bar: Real-time position evaluation
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Chess } from "chess.js";
import LichessBoard from "@/components/LichessBoard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import {
  Play,
  Pause,
  RotateCcw,
  Flag,
  Clock,
  Trophy,
  Loader2,
  ArrowLeft,
  Swords,
  Brain,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  Lightbulb,
  TrendingUp,
  TrendingDown,
  MessageCircle,
  Send,
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  Target,
  X,
  History,
  BookOpen
} from "lucide-react";
import TeachingPanel from "@/components/TeachingPanel";
import PostGameLesson from "@/components/PostGameLesson";
import EmotionalStateIndicator from "@/components/coach/EmotionalStateIndicator";
import { 
  OpeningTeachingOffer, 
  ActiveLessonPanel, 
  LessonCompletePanel 
} from "@/components/coach/OpeningTeachingPanel";

/**
 * EvalBar - Visual evaluation bar showing position advantage
 * 
 * A vertical bar that fills its container height:
 * - Score displayed in the CENTER of the bar for readability
 */
const EvalBar = ({ evaluation, userColor, gameOver }) => {
  const { score, mate_in } = evaluation || { score: 0, mate_in: null };
  
  // Calculate percentage for the bar (50% = equal, >50% = white advantage)
  const getBarPercentage = () => {
    if (mate_in !== null) {
      return mate_in > 0 ? 95 : 5;
    }
    const clamped = Math.max(-10, Math.min(10, score));
    return 50 + (clamped * 4.5);
  };
  
  const whitePercent = getBarPercentage();
  
  // Determine display text with sign
  const getEvalText = () => {
    if (mate_in !== null) {
      const sign = mate_in > 0 ? "+" : "-";
      return `${sign}M${Math.abs(mate_in)}`;
    }
    if (Math.abs(score) < 0.1) return "0.0";
    const sign = score > 0 ? "+" : "-";
    return `${sign}${Math.abs(score).toFixed(1)}`;
  };
  
  // Determine who is winning
  const isWhiteWinning = score > 0.3 || (mate_in !== null && mate_in > 0);
  const isBlackWinning = score < -0.3 || (mate_in !== null && mate_in < 0);
  
  // Color coding based on user's perspective
  const userIsWhite = userColor === "white";
  const userWinning = (userIsWhite && isWhiteWinning) || (!userIsWhite && isBlackWinning);
  const userLosing = (userIsWhite && isBlackWinning) || (!userIsWhite && isWhiteWinning);
  
  return (
    <div 
      className="w-full h-full flex flex-col rounded overflow-hidden border border-zinc-700 relative select-none"
      data-testid="eval-bar"
      title={`Evaluation: ${getEvalText()}`}
    >
      {/* Black portion (top) */}
      <div 
        className="bg-zinc-800 transition-all duration-500 ease-out"
        style={{ height: `${100 - whitePercent}%` }}
      />
      
      {/* White portion (bottom) */}
      <div 
        className="bg-zinc-200 transition-all duration-500 ease-out"
        style={{ height: `${whitePercent}%` }}
      />
      
      {/* Score displayed in the CENTER of the bar for readability */}
      <div 
        className="absolute inset-0 flex items-center justify-center pointer-events-none"
      >
        <div 
          className={`px-1.5 py-1 rounded text-xs font-bold leading-none whitespace-nowrap shadow-md ${
            userWinning 
              ? "bg-green-500 text-white" 
              : userLosing 
                ? "bg-red-500 text-white"
                : "bg-zinc-600 text-white"
          }`}
          data-testid="eval-text"
        >
          {getEvalText()}
        </div>
      </div>
    </div>
  );
};

const CoachPlay = ({ user }) => {
  const navigate = useNavigate();
  const boardRef = useRef(null);
  
  // Session state
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [gameStarted, setGameStarted] = useState(false);
  
  // Board state
  const [currentFen, setCurrentFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMove, setLastMove] = useState(null);
  const [isPlayerTurn, setIsPlayerTurn] = useState(true);
  
  // Game settings
  const [selectedColor, setSelectedColor] = useState("white");
  const [timeControl, setTimeControl] = useState("15+10");
  
  // Timer state
  const [moveStartTime, setMoveStartTime] = useState(null);
  
  // Game over state
  const [gameOver, setGameOver] = useState(false);
  const [gameResult, setGameResult] = useState(null);
  const [summary, setSummary] = useState(null);
  const [cprResult, setCprResult] = useState(null);
  const [playerIdentity, setPlayerIdentity] = useState(null);
  
  // Evaluation state for eval bar
  const [evaluation, setEvaluation] = useState({ score: 0.0, mate_in: null });
  
  // Practice mode state (from Lab alternate timeline)
  const [practiceMode, setPracticeMode] = useState(false);
  const [practicePosition, setPracticePosition] = useState(null);
  
  // Chat state (replaces popup modal)
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState(null);
  const [feedbackType, setFeedbackType] = useState("");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackCorrectPattern, setFeedbackCorrectPattern] = useState("");
  const chatEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // NEW: Past games memory and identity state
  const [pastGamesHistory, setPastGamesHistory] = useState(null);
  const [playerIdentityData, setPlayerIdentityData] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  
  // NEW: Visual move hints state
  const [moveHints, setMoveHints] = useState([]);
  
  // NEW: Emotional state tracking for Human Coach
  const [blundersThisGame, setBlundersThisGame] = useState(0);
  const [recentResults, setRecentResults] = useState([]);
  
  // NEW: Opening Teaching State
  const [teachingOffer, setTeachingOffer] = useState(null);
  const [activeLesson, setActiveLesson] = useState(null);
  const [lessonInstruction, setLessonInstruction] = useState(null);
  const [lessonComplete, setLessonComplete] = useState(null);
  const [isInTeachingMode, setIsInTeachingMode] = useState(false);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Poll for coach messages when game is active
  useEffect(() => {
    if (session && gameStarted && !gameOver) {
      // Start polling for coach messages
      pollIntervalRef.current = setInterval(pollCoachMessages, 2000);
      return () => {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
        }
      };
    }
  }, [session?.session_id, gameStarted, gameOver]);

  // Poll for new coach messages
  const pollCoachMessages = async () => {
    if (!session?.session_id) return;
    
    // Don't poll during teaching mode - handled separately
    if (isInTeachingMode) return;
    
    try {
      const response = await fetch(`${API}/coach/play/messages/${session.session_id}`, {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
          // Check for opening teaching offers
          const teachingOffers = data.messages.filter(msg => 
            msg.type === "opening_teaching_offer"
          );
          
          if (teachingOffers.length > 0 && !teachingOffer) {
            // Show the first teaching offer
            const offer = teachingOffers[0];
            setTeachingOffer({
              opening_name: offer.opening_name,
              opening_key: offer.opening_key,
              message: offer.message,
              options: offer.options,
              trap_name: offer.trap_name
            });
          }
          
          // Filter out teaching offers from regular messages
          const regularMessages = data.messages.filter(msg => 
            msg.type !== "opening_teaching_offer"
          );
          
          // Track blunders for emotional state
          const newBlunders = regularMessages.filter(msg => 
            msg.trigger === "warning" || msg.trigger === "blunder"
          ).length;
          if (newBlunders > 0) {
            setBlundersThisGame(prev => prev + newBlunders);
          }
          
          // Add regular messages to chat (preserve id for feedback button!)
          if (regularMessages.length > 0) {
            setChatMessages(prev => [
              ...prev,
              ...regularMessages.map(msg => ({
                id: msg.id,  // CRITICAL: Preserve ID for feedback button
                type: msg.type,
                message: msg.message,
                trigger: msg.trigger,
                move: msg.move,
                isCoachMove: msg.is_coach_move,  // Track if this is about coach's move
                question: msg.question,  // For Socratic questions
                isSocratic: msg.is_socratic,  // Track Socratic messages
                emotionalState: msg.emotional_state,  // Track emotional adaptation
                context: {
                  fen: msg.fen,
                  move_number: msg.move_number,
                  classification: msg.trigger
                },
                timestamp: Date.now()
              }))
            ]);
          }
        }
      }
    } catch (error) {
      // Silent fail - polling is background task
    }
  };

  // Check for active session on mount
  useEffect(() => {
    checkActiveSession();
    fetchPastGamesAndIdentity();
  }, []);

  // NEW: Fetch past games history and player identity
  const fetchPastGamesAndIdentity = async () => {
    setLoadingHistory(true);
    try {
      const [historyRes, identityRes] = await Promise.all([
        fetch(`${API}/coach/play/history?limit=5`, { credentials: "include" }),
        fetch(`${API}/coach/play/identity`, { credentials: "include" })
      ]);
      
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setPastGamesHistory(historyData);
      }
      
      if (identityRes.ok) {
        const identityData = await identityRes.json();
        if (identityData.has_identity) {
          setPlayerIdentityData(identityData.identity);
        }
      }
    } catch (error) {
      console.error("Error fetching coach play history:", error);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Check for practice mode from Lab alternate timeline
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'practice') {
      const practiceData = sessionStorage.getItem('practice_position');
      if (practiceData) {
        try {
          const data = JSON.parse(practiceData);
          setPracticeMode(true);
          setPracticePosition(data);
          setSelectedColor(data.userColor || 'white');
          // Clear sessionStorage after reading
          sessionStorage.removeItem('practice_position');
        } catch (e) {
          console.error('Error parsing practice position:', e);
        }
      }
    }
  }, []);

  const checkActiveSession = async () => {
    try {
      const response = await fetch(`${API}/coach/play/active`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        if (data.active_sessions && data.active_sessions.length > 0) {
          // Resume existing session
          const activeSession = data.active_sessions[0];
          await resumeSession(activeSession.session_id);
        }
      }
    } catch (error) {
      console.error("Error checking active session:", error);
    }
  };

  const resumeSession = async (sessionId) => {
    try {
      const response = await fetch(`${API}/coach/play/state/${sessionId}`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        setSession(data.session);
        setCurrentFen(data.current_fen);
        setBoardOrientation(data.session.user_color);
        setSelectedColor(data.session.user_color);
        setIsPlayerTurn(data.is_player_turn);
        setGameStarted(true);
        setGameOver(data.game_over);
        
        // Set evaluation for eval bar
        if (data.evaluation) {
          setEvaluation(data.evaluation);
        }
        
        // Highlight last move
        if (data.session.move_history?.length > 0) {
          const lastMoveData = data.session.move_history[data.session.move_history.length - 1];
          if (lastMoveData.uci) {
            setLastMove([lastMoveData.uci.slice(0, 2), lastMoveData.uci.slice(2, 4)]);
          }
        }
        
        if (data.is_player_turn) {
          setMoveStartTime(Date.now());
        }
        
        toast.success("Resumed your game!");
      }
    } catch (error) {
      console.error("Error resuming session:", error);
    }
  };

  const startGame = async () => {
    setLoading(true);
    // Reset emotional state tracking for new game
    setBlundersThisGame(0);
    
    try {
      // Build request body
      const requestBody = {
        user_color: selectedColor,
        time_control: timeControl
      };
      
      // If in practice mode, use custom starting position
      if (practiceMode && practicePosition?.fen) {
        requestBody.starting_fen = practicePosition.fen;
        requestBody.practice_mode = true;
        requestBody.source_game_id = practicePosition.gameId;
      }
      
      const response = await fetch(`${API}/coach/play/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to start game");
      }

      const data = await response.json();
      setSession(data.session);
      setCurrentFen(data.current_fen);
      setBoardOrientation(selectedColor);
      setIsPlayerTurn(data.is_player_turn);
      setGameStarted(true);
      setMoveStartTime(Date.now());
      
      // Set initial evaluation
      if (data.evaluation) {
        setEvaluation(data.evaluation);
      }
      
      // If playing black, coach already made first move
      if (selectedColor === "black" && data.session.move_history?.length > 0) {
        const coachMove = data.session.move_history[0];
        if (coachMove.uci) {
          setLastMove([coachMove.uci.slice(0, 2), coachMove.uci.slice(2, 4)]);
        }
      }
      
      toast.success(data.message);
    } catch (error) {
      toast.error(error.message || "Failed to start game");
    } finally {
      setLoading(false);
    }
  };

  const highlightMove = (uci) => {
    if (!uci || uci.length < 4) return;
    const from = uci.slice(0, 2);
    const to = uci.slice(2, 4);
    setLastMove([from, to]);
  };

  // Submit feedback on coach message
  const submitFeedback = async () => {
    if (!feedbackMessage || !feedbackType) return;
    
    try {
      // Submit basic feedback
      const response = await fetch(`${API}/coach/play/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session?.session_id,
          message_id: feedbackMessage.id,
          feedback_type: feedbackType,
          comment: feedbackComment
        })
      });
      
      // If feedback type is "wrong" and user provided correction, submit to pattern learning
      if (feedbackType === "wrong" && feedbackCorrectPattern && feedbackMessage.context) {
        try {
          const patternResponse = await fetch(`${API}/coach/pattern-learning/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              position_fen: feedbackMessage.context.fen || session?.current_fen || "",
              move_played: feedbackMessage.context.move || "",
              move_san: feedbackMessage.context.move_san || feedbackMessage.context.move || "",
              system_classification: feedbackMessage.context.classification || "UNKNOWN",
              system_explanation: feedbackMessage.message || "",
              correct_classification: feedbackCorrectPattern,
              user_explanation: feedbackComment,
              eval_before: feedbackMessage.context.eval_before || 0,
              eval_after: feedbackMessage.context.eval_after || 0,
              best_move: feedbackMessage.context.best_move || "",
              pv_after_played: feedbackMessage.context.pv || [],
              game_id: session?.session_id || "",
              move_number: feedbackMessage.context.move_number || 0,
              user_color: session?.user_color || "white"
            })
          });
          
          if (patternResponse.ok) {
            const result = await patternResponse.json();
            if (result.corrected_explanation) {
              toast.success("Got it! The coach will learn from this.", {
                description: result.corrected_explanation.substring(0, 100) + "..."
              });
            } else {
              toast.success("Thanks! This helps the coach improve for everyone.");
            }
          }
        } catch (patternError) {
          console.error("Error submitting pattern learning feedback:", patternError);
          // Still show success for basic feedback
          toast.success("Thanks for your feedback!");
        }
      } else if (response.ok) {
        toast.success("Thanks for your feedback!");
      }
    } catch (error) {
      console.error("Error submitting feedback:", error);
    }
    
    // Reset feedback state
    setFeedbackMessage(null);
    setFeedbackType("");
    setFeedbackComment("");
    setFeedbackCorrectPattern("");
  };

  // Guardian intervention state
  const [guardianIntervention, setGuardianIntervention] = useState(null);
  const [pendingMove, setPendingMove] = useState(null);
  const [remainingInterventions, setRemainingInterventions] = useState(3);

  // Evaluate move with guardian before making it
  const evaluateMove = async (moveSan) => {
    try {
      const response = await fetch(`${API}/coach/play/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveSan
        })
      });

      if (response.ok) {
        const result = await response.json();
        
        // If Stockfish approved a "risky-looking" move, show positive feedback!
        if (result.tactical_awareness) {
          toast.success(result.tactical_message || "Good tactical awareness!");
          setChatMessages(prev => [...prev, {
            type: "coach",
            trigger: "encouragement",
            message: `Nice capture! Stockfish confirms this is a good trade. That's tactical awareness! 👏`,
            timestamp: Date.now()
          }]);
        }
        
        return result;
      }
    } catch (error) {
      console.error("Guardian evaluation error:", error);
    }
    return null;
  };

  // Fun thinking messages for coach
  const THINKING_MESSAGES = [
    "Coach is studying your move...",
    "Hmm, interesting choice...",
    "Let me think about that...",
    "Analyzing the position...",
    "Coach is pondering...",
    "Considering the options...",
  ];
  
  const [coachThinking, setCoachThinking] = useState(false);
  const [thinkingMessage, setThinkingMessage] = useState("");

  // Execute the move (called after guardian check passes or user confirms)
  const executeMove = async (moveSan, timeSpent, isOverride = false, riskType = null) => {
    const endpoint = isOverride ? `${API}/coach/play/move/confirm` : `${API}/coach/play/move`;
    
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveSan,
          time_spent: timeSpent,
          ...(isOverride && { risk_acknowledged: riskType })
        })
      });

      if (!response.ok) {
        const error = await response.json();
        toast.error(error.detail || "Invalid move");
        return false;
      }

      const data = await response.json();
      
      // Update board with user's move immediately
      setCurrentFen(data.current_fen);
      setIsPlayerTurn(false);
      
      // Check if game is over after user's move
      if (data.game_over) {
        setGameOver(true);
        setGameResult(data.result);
        if (data.result === "win") {
          toast.success("You won! Great game!");
        }
        return true;
      }
      
      // Show coach thinking state
      if (data.awaiting_coach) {
        setCoachThinking(true);
        setThinkingMessage(THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)]);
        
        // Add thinking message to chat
        setChatMessages(prev => [...prev, {
          type: "thinking",
          message: THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)],
          timestamp: Date.now()
        }]);
        
        // Poll for coach's response
        pollForCoachResponse();
      }

      return true;
    } catch (error) {
      console.error("Move error:", error);
      toast.error("Connection error. Please try again.");
      return false;
    }
  };
  
  // Poll for coach's move and messages
  const pollForCoachResponse = async () => {
    const maxAttempts = 30;  // 30 seconds max
    let attempts = 0;
    
    const poll = async () => {
      if (attempts >= maxAttempts) {
        setCoachThinking(false);
        toast.error("Coach took too long to respond");
        return;
      }
      
      attempts++;
      
      try {
        // Get latest session state
        const response = await fetch(`${API}/coach/play/state/${session.session_id}`, {
          credentials: "include"
        });
        
        if (response.ok) {
          const data = await response.json();
          
          // Check if coach has moved
          if (!data.session.coach_move_pending) {
            // Remove thinking message from chat
            setChatMessages(prev => prev.filter(m => m.type !== "thinking"));
            
            // Update board
            setSession(data.session);
            setCurrentFen(data.current_fen);
            
            // Update evaluation
            if (data.evaluation) {
              setEvaluation(data.evaluation);
            }
            
            // Highlight coach's last move
            const lastMove = data.session.last_coach_move;
            if (lastMove?.uci) {
              highlightMove(lastMove.uci);
            }
            
            // Check if game over
            if (data.game_over || data.session.status === "completed") {
              setGameOver(true);
              setGameResult(data.session.result);
              if (data.session.result === "loss") {
                toast.info("Coach wins! Keep practicing!");
              } else if (data.session.result === "draw") {
                toast.info("It's a draw!");
              }
            } else {
              setIsPlayerTurn(true);
              setMoveStartTime(Date.now());
            }
            
            setCoachThinking(false);
            return;
          }
        }
        
        // Keep polling
        setTimeout(poll, 1000);
        
      } catch (error) {
        console.error("Poll error:", error);
        setTimeout(poll, 1000);
      }
    };
    
    poll();
  };
  
  // Send chat message to coach
  const sendChatMessage = async (directMessage = null) => {
    const messageToSend = directMessage || chatInput.trim();
    if (!messageToSend || !session) return;
    
    if (!directMessage) {
      setChatInput("");
    }
    
    // Add user message to chat
    setChatMessages(prev => [...prev, {
      type: "user",
      message: messageToSend,
      timestamp: Date.now()
    }]);
    
    setIsSendingChat(true);
    
    try {
      const response = await fetch(`${API}/coach/play/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          message: messageToSend
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Generate a client-side ID for feedback on chat responses
        const chatResponseId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Add coach response to chat (with id for feedback button!)
        setChatMessages(prev => [...prev, {
          id: chatResponseId,  // For feedback button
          type: "coach",
          message: data.response,
          trigger: "chat_response",  // Mark as chat response
          suggestion_arrow: data.suggestion_arrow,
          best_move: data.best_move,
          missed_tactic: data.missed_tactic,
          move_quality: data.move_quality,
          context: {
            user_question: messageToSend,
            fen: currentFen,
            best_move: data.best_move,
            move_quality: data.move_quality
          },
          timestamp: Date.now()
        }]);
        
        // Show suggestion arrow on board if available
        if (data.suggestion_arrow && boardRef.current) {
          const from = data.suggestion_arrow.slice(0, 2);
          const to = data.suggestion_arrow.slice(2, 4);
          boardRef.current.drawArrows([[from, to, "green"]]);
          
          // Clear arrow after 8 seconds
          setTimeout(() => {
            if (boardRef.current) {
              boardRef.current.clearArrows();
            }
          }, 8000);
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setIsSendingChat(false);
    }
  };

  // Handle user confirming a risky move
  const confirmRiskyMove = async () => {
    if (!pendingMove) return;
    
    const { moveSan, timeSpent, riskType, chess, originalFen } = pendingMove;
    
    // Store original FEN for potential revert
    const fenBeforeMove = originalFen;
    
    // Update board to show the move
    setCurrentFen(chess.fen());
    setIsPlayerTurn(false);
    
    // Clear intervention state BEFORE the async call
    setGuardianIntervention(null);
    setPendingMove(null);
    
    // Execute with override
    const success = await executeMove(moveSan, timeSpent, true, riskType);
    
    if (!success) {
      // Revert to the position BEFORE the attempted move
      setCurrentFen(fenBeforeMove);
      setIsPlayerTurn(true);
      
      // Also reset the board ref if available
      if (boardRef.current?.setPosition) {
        boardRef.current.setPosition(fenBeforeMove);
      }
    }
  };

  // Handle user canceling a risky move
  const cancelRiskyMove = () => {
    // Reset the board to the position before the attempted move
    if (pendingMove?.originalFen) {
      const originalFen = pendingMove.originalFen;
      // Directly set the FEN - LichessBoard will update
      setCurrentFen(originalFen);
      setLastMove(null); // Clear last move highlight
      setIsPlayerTurn(true);
      
      // Force LichessBoard to re-render by using ref if needed
      if (boardRef.current?.setPosition) {
        boardRef.current.setPosition(originalFen);
      }
    }
    
    setGuardianIntervention(null);
    setPendingMove(null);
    toast.info("Move cancelled. Choose a different move.");
  };

  const makeMove = useCallback(async (sourceSquare, targetSquare, piece) => {
    // If in teaching mode, use teaching move handler
    if (isInTeachingMode && activeLesson) {
      return await handleTeachingMove(sourceSquare, targetSquare);
    }
    
    if (!session || !isPlayerTurn || gameOver) return false;

    // Try to make the move locally first
    const chess = new Chess(currentFen);
    let moveObj;
    try {
      moveObj = chess.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: piece?.[1]?.toLowerCase() === "p" ? "q" : undefined
      });
    } catch {
      return false;
    }

    if (!moveObj) return false;

    // Calculate time spent
    const timeSpent = moveStartTime ? (Date.now() - moveStartTime) / 1000 : 0;

    // GUARDIAN CHECK: Evaluate move before making it
    const guardianResult = await evaluateMove(moveObj.san);
    
    if (guardianResult?.should_intervene) {
      // Show intervention modal - don't make the move yet
      // Store the original FEN so we can reset if user cancels
      setGuardianIntervention(guardianResult);
      setPendingMove({
        moveSan: moveObj.san,
        moveObj: moveObj,
        timeSpent: timeSpent,
        riskType: guardianResult.risk_type,
        chess: chess,
        originalFen: currentFen  // Store original position to reset if cancelled
      });
      return false; // Don't complete the move yet
    }

    // No intervention needed - proceed with move
    setCurrentFen(chess.fen());
    setIsPlayerTurn(false);
    highlightMove(moveObj.from + moveObj.to);

    const success = await executeMove(moveObj.san, timeSpent);
    
    if (!success) {
      // Revert
      setCurrentFen(currentFen);
      setIsPlayerTurn(true);
      return false;
    }

    return true;
  }, [session, currentFen, isPlayerTurn, gameOver, moveStartTime, isInTeachingMode, activeLesson]);

  const resignGame = async () => {
    if (!session) return;

    try {
      const response = await fetch(`${API}/coach/play/end`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          reason: "resigned"
        })
      });

      if (response.ok) {
        const data = await response.json();
        setGameOver(true);
        setGameResult("loss");
        setSummary(data.summary);
        setCprResult(data.cpr);
        setPlayerIdentity(data.identity);
        toast.info("You resigned. Better luck next time!");
      }
    } catch (error) {
      toast.error("Failed to resign");
    }
  };

  const flipBoard = () => {
    setBoardOrientation(prev => prev === "white" ? "black" : "white");
  };

  const newGame = () => {
    setSession(null);
    setGameStarted(false);
    setGameOver(false);
    setGameResult(null);
    setSummary(null);
    setCprResult(null);
    setPlayerIdentity(null);
    setCurrentFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setLastMove(null);
    setIsPlayerTurn(true);
    setGuardianIntervention(null);
    setPendingMove(null);
    // Reset teaching state
    setTeachingOffer(null);
    setActiveLesson(null);
    setLessonInstruction(null);
    setLessonComplete(null);
    setIsInTeachingMode(false);
  };

  // ========================================
  // OPENING TEACHING HANDLERS
  // ========================================
  
  const handleStartLesson = (lessonData) => {
    setTeachingOffer(null);
    setActiveLesson(lessonData);
    setLessonInstruction(lessonData.instruction);
    setIsInTeachingMode(true);
    setCurrentFen(lessonData.teaching_fen);
    setLastMove(null);
    
    // Add lesson start message to chat
    setChatMessages(prev => [...prev, {
      type: "coach",
      trigger: "teaching",
      message: `Let's learn the ${lessonData.lesson_name}! Follow along and play the moves.`,
      timestamp: Date.now()
    }]);
    
    toast.success(`Starting lesson: ${lessonData.lesson_name}`);
  };
  
  const handleSkipTeachingOffer = () => {
    setTeachingOffer(null);
    setChatMessages(prev => [...prev, {
      type: "coach",
      trigger: "encouragement",
      message: "No problem! Let's continue playing. I'll guide you as we go.",
      timestamp: Date.now()
    }]);
  };
  
  const handleTeachingMoveValidated = (result) => {
    // Update instruction for next move
    if (result.next_instruction) {
      setLessonInstruction(result.next_instruction);
    }
    
    // Update board position
    if (result.teaching_fen) {
      setCurrentFen(result.teaching_fen);
    }
    
    // If there was an auto-play (opponent move), show it
    if (result.auto_played) {
      setChatMessages(prev => [...prev, {
        type: "coach",
        trigger: "teaching",
        message: result.message,
        timestamp: Date.now()
      }]);
    }
  };
  
  const handleLessonComplete = (completion) => {
    setLessonInstruction(null);
    setLessonComplete(completion);
    
    // Add celebration message to chat
    setChatMessages(prev => [...prev, {
      type: "coach",
      trigger: "encouragement",
      message: completion.message,
      timestamp: Date.now()
    }]);
    
    toast.success("Lesson complete!");
  };
  
  const handleExitLesson = async (choice, result) => {
    setActiveLesson(null);
    setLessonComplete(null);
    setIsInTeachingMode(false);
    
    if (choice === "continue_game" && result?.restored_fen) {
      // Restore original game position
      setCurrentFen(result.restored_fen);
      setChatMessages(prev => [...prev, {
        type: "coach",
        trigger: "teaching",
        message: "Game restored! Your turn to continue.",
        timestamp: Date.now()
      }]);
    } else if (choice === "new_game") {
      // Start a fresh game
      newGame();
      // Auto-start after a brief delay
      setTimeout(() => startGame(), 500);
    }
  };
  
  // Handle moves during teaching mode
  const handleTeachingMove = async (from, to) => {
    if (!activeLesson || !session) return false;
    
    // Build the move SAN
    const chess = new Chess(currentFen);
    let moveObj;
    try {
      moveObj = chess.move({ from, to, promotion: "q" });
    } catch {
      return false;
    }
    
    if (!moveObj) return false;
    
    // Validate with backend
    try {
      const response = await fetch(`${API}/coach/play/teaching/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveObj.san
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        
        if (result.complete) {
          handleLessonComplete(result);
        } else if (result.correct) {
          // Update board
          setCurrentFen(result.teaching_fen);
          handleTeachingMoveValidated(result);
          return true;
        } else {
          // Wrong move - show hint
          toast.error(result.message);
          setChatMessages(prev => [...prev, {
            type: "coach",
            trigger: "teaching",
            message: `${result.message} ${result.hint || ""}`,
            timestamp: Date.now()
          }]);
        }
      }
    } catch (error) {
      console.error("Teaching move error:", error);
    }
    
    return false;
  };

  // Pre-game setup screen
  if (!gameStarted) {
    return (
      <Layout user={user}>
        <div className="max-w-2xl mx-auto py-8 px-4" data-testid="coach-play-setup">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="mb-6"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>

          <Card className="border-primary/20">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-full bg-primary/10">
                  <Swords className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-2xl">
                    {practiceMode ? "Practice Position" : "Play With Coach"}
                  </CardTitle>
                  <p className="text-muted-foreground">
                    {practiceMode 
                      ? "Play from a position in your game and see how it could have gone differently"
                      : "Train against an intelligent opponent"
                    }
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Practice Mode Indicator */}
              {practiceMode && practicePosition && (
                <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20" data-testid="practice-mode-indicator">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-emerald-400" />
                    <span className="font-medium text-emerald-400">Practice Mode</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    You'll start from the position where you made a mistake. 
                    Try playing differently and see if you can win!
                  </p>
                </div>
              )}
              
              {/* Color Selection */}
              <div>
                <label className="text-sm font-medium mb-3 block">
                  Choose Your Color
                </label>
                <div className="flex gap-3">
                  <Button
                    variant={selectedColor === "white" ? "default" : "outline"}
                    onClick={() => setSelectedColor("white")}
                    className="flex-1"
                    data-testid="select-white"
                    disabled={practiceMode}
                  >
                    <div className="w-6 h-6 rounded-full bg-white border mr-2" />
                    White
                  </Button>
                  <Button
                    variant={selectedColor === "black" ? "default" : "outline"}
                    onClick={() => setSelectedColor("black")}
                    className="flex-1"
                    data-testid="select-black"
                    disabled={practiceMode}
                  >
                    <div className="w-6 h-6 rounded-full bg-gray-900 border mr-2" />
                    Black
                  </Button>
                </div>
                {practiceMode && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Color is set based on your original game position.
                  </p>
                )}
              </div>

              {/* Time Control */}
              <div>
                <label className="text-sm font-medium mb-3 block">
                  Time Control
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {["3+2", "10+5", "15+10"].map((tc) => (
                    <Button
                      key={tc}
                      variant={timeControl === tc ? "default" : "outline"}
                      onClick={() => setTimeControl(tc)}
                      size="sm"
                      data-testid={`time-${tc.replace("+", "-")}`}
                    >
                      <Clock className="w-4 h-4 mr-1" />
                      {tc}
                    </Button>
                  ))}
                </div>
              </div>

              {/* NEW: Past Games Memory */}
              {!practiceMode && pastGamesHistory?.sessions?.length > 0 && (
                <div className="p-4 rounded-lg border border-border bg-muted/30">
                  <div className="flex items-center gap-2 mb-3">
                    <History className="w-4 h-4 text-primary" />
                    <span className="font-medium text-sm">Coach Remembers</span>
                  </div>
                  
                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-2 text-center mb-3">
                    <div className="p-2 rounded bg-background/50">
                      <div className="text-lg font-bold text-green-500">{pastGamesHistory.stats.wins}</div>
                      <div className="text-xs text-muted-foreground">Wins</div>
                    </div>
                    <div className="p-2 rounded bg-background/50">
                      <div className="text-lg font-bold text-muted-foreground">{pastGamesHistory.stats.draws}</div>
                      <div className="text-xs text-muted-foreground">Draws</div>
                    </div>
                    <div className="p-2 rounded bg-background/50">
                      <div className="text-lg font-bold text-red-500">{pastGamesHistory.stats.losses}</div>
                      <div className="text-xs text-muted-foreground">Losses</div>
                    </div>
                  </div>
                  
                  {/* Recent sessions */}
                  <div className="space-y-1">
                    {pastGamesHistory.sessions.slice(0, 3).map((s, i) => (
                      <div key={i} className="flex items-center justify-between text-xs p-2 rounded bg-background/50">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${
                            s.result === 'win' ? 'bg-green-500' : 
                            s.result === 'loss' ? 'bg-red-500' : 'bg-gray-400'
                          }`} />
                          <span className="capitalize">{s.result || 'In progress'}</span>
                        </div>
                        <span className="text-muted-foreground">
                          {s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                  
                  {/* Identity snippet if available */}
                  {playerIdentityData?.identity_label && (
                    <div className="mt-3 pt-3 border-t border-border/50 text-xs">
                      <span className="text-muted-foreground">Your style: </span>
                      <Badge variant="secondary" className="ml-1">
                        {playerIdentityData.identity_label}
                      </Badge>
                    </div>
                  )}
                </div>
              )}

              {/* Start Button */}
              <Button
                onClick={startGame}
                disabled={loading}
                className="w-full h-12 text-lg"
                data-testid="start-game-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Starting...
                  </>
                ) : practiceMode ? (
                  <>
                    <Target className="w-5 h-5 mr-2" />
                    Start Practice
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5 mr-2" />
                    Start Game
                  </>
                )}
              </Button>

              {/* Info */}
              <div className="p-4 rounded-lg bg-muted/50 text-sm text-muted-foreground">
                <Brain className="w-4 h-4 inline mr-2" />
                The coach will adapt to your play and help you improve.
                Future updates will add real-time interventions when you're
                about to make mistakes.
              </div>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  // Game screen
  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex" data-testid="coach-play-game">
        {/* Left: Board + Eval Bar */}
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <div className="w-full max-w-[600px]">
            {/* Coach info bar */}
            <div className="flex items-center justify-between mb-3 p-3 rounded-lg bg-muted/50">
              <div className="flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary" />
                <span className="font-medium">Coach</span>
                <Badge variant="secondary" className="text-xs">
                  Level {session?.coach_skill_level || 8}
                </Badge>
              </div>
              <Badge variant="outline">
                <Clock className="w-3 h-3 mr-1" />
                {Math.floor((session?.coach_time_remaining || 900) / 60)}:
                {String(Math.floor((session?.coach_time_remaining || 900) % 60)).padStart(2, "0")}
              </Badge>
            </div>
            
            {/* Eval Bar + Board in same row */}
            <div className="flex gap-2 items-stretch">
              {/* Eval Bar - wider to fit text like -10.0 */}
              <div className="w-10 shrink-0">
                <EvalBar 
                  evaluation={evaluation} 
                  userColor={selectedColor}
                  gameOver={gameOver}
                />
              </div>
              
              {/* Chessboard - square aspect ratio, this sets the row height */}
              <div className="flex-1 rounded-lg overflow-hidden aspect-square" style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.3)" }}>
                <LichessBoard
                  ref={boardRef}
                  fen={currentFen}
                  orientation={boardOrientation}
                  lastMove={lastMove}
                  onMove={(moveData) => {
                    if (isPlayerTurn && !gameOver && moveData) {
                      makeMove(moveData.from, moveData.to);
                    }
                  }}
                  interactive={isPlayerTurn && !gameOver}
                  viewOnly={!isPlayerTurn || gameOver}
                  showDests={true}
                />
              </div>
            </div>

            {/* Player info bar */}
            <div className="flex items-center justify-between mt-3 p-3 rounded-lg bg-muted/50">
              <div className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded-full ${selectedColor === "white" ? "bg-white border" : "bg-gray-900"}`} />
                <span className="font-medium">You</span>
                {isPlayerTurn && !gameOver && (
                  <Badge className="bg-green-500/20 text-green-500 border-green-500/30">
                    Your turn
                  </Badge>
                )}
              </div>
              <Badge variant="outline">
                <Clock className="w-3 h-3 mr-1" />
                {Math.floor((session?.user_time_remaining || 900) / 60)}:
                {String(Math.floor((session?.user_time_remaining || 900) % 60)).padStart(2, "0")}
              </Badge>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-2 mt-4">
              <Button variant="outline" size="sm" onClick={flipBoard}>
                <RotateCcw className="w-4 h-4 mr-1" />
                Flip
              </Button>
              {!gameOver && (
                <Button 
                  variant="destructive" 
                  size="sm" 
                  onClick={resignGame}
                  data-testid="resign-btn"
                >
                  <Flag className="w-4 h-4 mr-1" />
                  Resign
                </Button>
              )}
              {gameOver && (
                <Button 
                  variant="default" 
                  size="sm" 
                  onClick={newGame}
                  data-testid="new-game-btn"
                >
                  <Play className="w-4 h-4 mr-1" />
                  New Game
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Right: Coach Chat Panel */}
        <div className="w-[380px] border-l border-border flex flex-col h-full" data-testid="coach-chat-panel">
          {/* Header */}
          <div className="p-4 border-b border-border">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Brain className="w-5 h-5 text-primary" />
              Coach Chat
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Ask questions anytime. Coach speaks on teachable moments.
            </p>
          </div>
          
          {/* Feedback Modal */}
          {feedbackMessage && (
            <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
              <Card className="w-full max-w-sm">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">What was wrong?</CardTitle>
                    <button 
                      onClick={() => setFeedbackMessage(null)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-2 bg-muted/50 rounded text-xs text-muted-foreground line-clamp-2">
                    "{feedbackMessage.message}"
                  </div>
                  
                  <div className="space-y-2">
                    {[
                      { value: "confusing", label: "Confusing / Hard to understand" },
                      { value: "wrong", label: "Wrong / Incorrect explanation" },
                      { value: "obvious", label: "Too obvious / I knew this" },
                      { value: "not_relevant", label: "Not relevant to my plan" },
                    ].map(option => (
                      <label 
                        key={option.value}
                        className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                          feedbackType === option.value 
                            ? "bg-primary/10 border border-primary/30" 
                            : "hover:bg-muted/50"
                        }`}
                      >
                        <input
                          type="radio"
                          name="feedback"
                          value={option.value}
                          checked={feedbackType === option.value}
                          onChange={(e) => setFeedbackType(e.target.value)}
                          className="sr-only"
                        />
                        <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                          feedbackType === option.value 
                            ? "border-primary bg-primary" 
                            : "border-muted-foreground"
                        }`}>
                          {feedbackType === option.value && (
                            <div className="w-2 h-2 rounded-full bg-background" />
                          )}
                        </div>
                        <span className="text-sm">{option.label}</span>
                      </label>
                    ))}
                  </div>
                  
                  {/* Pattern Correction Section - shown when "wrong" is selected */}
                  {feedbackType === "wrong" && (
                    <div className="space-y-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                      <p className="text-xs font-medium text-amber-600 dark:text-amber-400">
                        Help us learn! What was it actually?
                      </p>
                      <select
                        value={feedbackCorrectPattern}
                        onChange={(e) => setFeedbackCorrectPattern(e.target.value)}
                        className="w-full p-2 text-sm rounded border bg-background"
                        data-testid="pattern-correction-select"
                      >
                        <option value="">Select the correct pattern...</option>
                        <option value="WALKED_INTO_FORK">I walked into a fork</option>
                        <option value="WALKED_INTO_PIN">I walked into a pin</option>
                        <option value="WALKED_INTO_SKEWER">I walked into a skewer</option>
                        <option value="HANGING_PIECE">I left a piece hanging</option>
                        <option value="MISSED_FORK">I missed a fork opportunity</option>
                        <option value="MISSED_PIN">I missed a pin opportunity</option>
                        <option value="MISSED_WINNING_TACTIC">I missed a winning tactic</option>
                        <option value="BLUNDER_WHEN_AHEAD">I blundered when ahead</option>
                        <option value="IGNORED_THREAT">I ignored opponent's threat</option>
                        <option value="POSITIONAL_DRIFT">Small positional mistake</option>
                        <option value="OTHER">Something else</option>
                      </select>
                    </div>
                  )}
                  
                  <Textarea
                    placeholder={feedbackType === "wrong" 
                      ? "Explain what the mistake actually was (e.g., 'The pawn forks my knight and bishop')..." 
                      : "Tell us more (optional)..."}
                    value={feedbackComment}
                    onChange={(e) => setFeedbackComment(e.target.value)}
                    className="h-20 text-sm"
                  />
                  
                  <Button 
                    onClick={submitFeedback}
                    disabled={!feedbackType || (feedbackType === "wrong" && !feedbackCorrectPattern)}
                    className="w-full"
                  >
                    {feedbackType === "wrong" ? "Submit & Help Coach Learn" : "Submit Feedback"}
                  </Button>
                  
                  {feedbackType === "wrong" && (
                    <p className="text-xs text-center text-muted-foreground">
                      Your correction helps the coach improve for everyone!
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
          
          {/* Teaching Insights Panel - Shows structure and phase analysis */}
          {session && !gameOver && (
            <div className="p-4 border-b border-border">
              <TeachingPanel 
                fen={currentFen} 
                userColor={session.user_color}
                sessionId={session.session_id}
              />
            </div>
          )}
          
          {/* Post-Game Lesson - Shows when game is over */}
          {session && gameOver && (
            <div className="p-4 border-b border-border">
              <PostGameLesson
                sessionId={session.session_id}
                result={session.result || "1/2-1/2"}
                studentColor={session.user_color}
                moves={(session.move_history || []).map(m => m.move)}
                onPlayAgain={newGame}
              />
            </div>
          )}
          
          {/* Opening Teaching Offer - Shows when opening is detected */}
          {session && teachingOffer && !isInTeachingMode && !gameOver && (
            <div className="p-4 border-b border-border">
              <OpeningTeachingOffer
                offer={teachingOffer}
                sessionId={session.session_id}
                onStartLesson={handleStartLesson}
                onSkip={handleSkipTeachingOffer}
              />
            </div>
          )}
          
          {/* Active Lesson Panel - Shows during interactive teaching */}
          {session && activeLesson && isInTeachingMode && !lessonComplete && (
            <div className="p-4 border-b border-border">
              <ActiveLessonPanel
                lesson={activeLesson}
                sessionId={session.session_id}
                currentInstruction={lessonInstruction}
                onMoveValidated={handleTeachingMoveValidated}
                onLessonComplete={handleLessonComplete}
                onExitLesson={(choice) => handleExitLesson(choice, {})}
              />
            </div>
          )}
          
          {/* Lesson Complete Panel - Shows after finishing a lesson */}
          {session && lessonComplete && (
            <div className="p-4 border-b border-border">
              <LessonCompletePanel
                completion={lessonComplete}
                sessionId={session.session_id}
                onChoice={handleExitLesson}
              />
            </div>
          )}
          
          {/* Emotional State Indicator - Shows coach awareness of player mood */}
          {session && !gameOver && blundersThisGame > 0 && (
            <EmotionalStateIndicator
              blundersThisGame={blundersThisGame}
              recentResults={recentResults}
              onTakeBreak={() => {
                toast.info("Take a 5-minute break. The game will be here when you're back!");
              }}
            />
          )}
          
          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="chat-messages">
            {/* Welcome message */}
            {chatMessages.length === 0 && !gameOver && (
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <div className="flex items-start gap-2">
                  <Brain className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  <div className="text-sm">
                    <p className="font-medium text-primary">Let's play!</p>
                    <p className="text-muted-foreground mt-1">
                      I'll give you feedback on interesting moves. Feel free to ask me anything!
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            {/* Chat history */}
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg ${
                  msg.type === "coach"
                    ? msg.trigger === "warning" 
                      ? "bg-red-500/10 border border-red-500/20"
                      : msg.trigger === "teaching"
                      ? "bg-amber-500/10 border border-amber-500/20"
                      : msg.trigger === "encouragement"
                      ? "bg-green-500/10 border border-green-500/20"
                      : "bg-primary/10 border border-primary/20"
                    : msg.type === "thinking"
                    ? "bg-primary/5 border border-primary/10 animate-pulse"
                    : "bg-muted/50 ml-6"
                }`}
              >
                <div className="flex items-start gap-2">
                  {msg.type === "coach" ? (
                    <Brain className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                      msg.trigger === "warning" ? "text-red-400" :
                      msg.trigger === "teaching" ? "text-amber-400" :
                      msg.trigger === "encouragement" ? "text-green-400" :
                      "text-primary"
                    }`} />
                  ) : msg.type === "thinking" ? (
                    <Loader2 className="w-4 h-4 text-primary mt-0.5 flex-shrink-0 animate-spin" />
                  ) : (
                    <MessageCircle className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                  )}
                  <div className="text-sm flex-1">
                    {msg.type === "coach" && msg.trigger && (
                      <Badge variant="outline" className={`text-xs mb-1 capitalize ${
                        msg.trigger === "warning" ? "border-red-500/30 text-red-400" :
                        msg.trigger === "teaching" ? "border-amber-500/30 text-amber-400" :
                        msg.trigger === "encouragement" ? "border-green-500/30 text-green-400" :
                        ""
                      }`}>
                        {msg.trigger === "encouragement" ? "👏" : 
                         msg.trigger === "warning" ? "⚠️" : 
                         msg.trigger === "teaching" ? "💡" : "💬"} {msg.trigger}
                      </Badge>
                    )}
                    {msg.type === "coach" && msg.move && (
                      <span className="text-xs text-muted-foreground block">
                        After {msg.move}:
                      </span>
                    )}
                    <p className={
                      msg.type === "coach" ? "" : 
                      msg.type === "thinking" ? "text-primary italic" :
                      "text-muted-foreground"
                    }>
                      {msg.message}
                    </p>
                    
                    {/* Quick Action Buttons - Context-aware based on whose move */}
                    {msg.type === "coach" && msg.trigger === "teaching" && !msg.question && (
                      <div className="mt-2 flex items-center gap-2">
                        {/* Use the isCoachMove flag, fallback to text detection */}
                        {msg.isCoachMove || 
                         msg.message?.toLowerCase().includes("i played") || 
                         msg.message?.toLowerCase().includes("i moved") ? (
                          // Coach explaining their own move - include the move in the question!
                          <>
                            <button
                              onClick={() => sendChatMessage(`Why did you play ${msg.move || "that move"}?`)}
                              className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                              data-testid={`why-coach-btn-${i}`}
                            >
                              Why that move?
                            </button>
                            <button
                              onClick={() => sendChatMessage(`What's the idea behind ${msg.move || "your move"}?`)}
                              className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                              data-testid={`idea-btn-${i}`}
                            >
                              What's the idea?
                            </button>
                          </>
                        ) : (
                          // Coach teaching about user's move - include the move!
                          <>
                            <button
                              onClick={() => sendChatMessage(`Why was ${msg.move || "my move"} bad?`)}
                              className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
                              data-testid={`why-btn-${i}`}
                            >
                              Why?
                            </button>
                            <button
                              onClick={() => sendChatMessage(`What should I have played instead of ${msg.move || "that"}?`)}
                              className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                              data-testid={`what-btn-${i}`}
                            >
                              What instead?
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    
                    {/* Question options for coach questions */}
                    {msg.type === "coach" && msg.question && msg.question.options && (
                      <div className="mt-3 space-y-2">
                        {msg.question.options.map((option, optIdx) => (
                          <button
                            key={optIdx}
                            onClick={() => sendChatMessage(option)}
                            className="w-full text-left p-2 rounded-lg bg-muted/30 hover:bg-muted/50 text-sm transition-colors border border-transparent hover:border-primary/30 flex items-center gap-2"
                            data-testid={`question-option-${i}-${optIdx}`}
                          >
                            <span className="w-5 h-5 rounded-full bg-primary/10 text-primary text-xs flex items-center justify-center flex-shrink-0">
                              {String.fromCharCode(65 + optIdx)}
                            </span>
                            {option}
                          </button>
                        ))}
                      </div>
                    )}
                    {/* Feedback button for coach messages */}
                    {msg.type === "coach" && msg.id && (
                      <div className="mt-2 flex items-center gap-2">
                        <button
                          onClick={() => setFeedbackMessage(msg)}
                          className="text-xs text-muted-foreground hover:text-primary flex items-center gap-1 transition-colors"
                          data-testid={`feedback-btn-${i}`}
                        >
                          <ThumbsDown className="w-3 h-3" />
                          Not helpful
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            
            {/* Loading indicator */}
            {isSendingChat && (
              <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 text-primary animate-spin" />
                  <span className="text-sm text-muted-foreground">Coach is thinking...</span>
                </div>
              </div>
            )}
            
            <div ref={chatEndRef} />
          </div>
          
          {/* Game over summary */}
          {gameOver && (
            <div className="p-4 border-t border-border">
              <Card className={`${
                gameResult === "win" ? "border-green-500/30 bg-green-500/5" :
                gameResult === "loss" ? "border-red-500/30 bg-red-500/5" :
                "border-yellow-500/30 bg-yellow-500/5"
              }`}>
                <CardContent className="p-3">
                  <div className="flex items-center gap-2">
                    {gameResult === "win" ? (
                      <Trophy className="w-5 h-5 text-green-500" />
                    ) : gameResult === "loss" ? (
                      <XCircle className="w-5 h-5 text-red-500" />
                    ) : (
                      <CheckCircle2 className="w-5 h-5 text-yellow-500" />
                    )}
                    <span className="font-medium capitalize">{gameResult || "Draw"}</span>
                  </div>
                  {summary && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {summary.total_moves} moves • {Math.floor(summary.duration_seconds / 60)}m
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
          
          {/* Chat Input */}
          {!gameOver && (
            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask the coach anything..."
                  className="min-h-[60px] max-h-[100px] resize-none"
                  data-testid="chat-input"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && chatInput.trim()) {
                      e.preventDefault();
                      sendChatMessage();
                    }
                  }}
                />
                <Button
                  size="icon"
                  onClick={() => sendChatMessage()}
                  disabled={!chatInput.trim() || isSendingChat}
                  data-testid="send-chat-btn"
                >
                  {isSendingChat ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>
          )}
          
          {/* Move History (collapsed) */}
          <details className="border-t border-border">
            <summary className="p-3 text-sm cursor-pointer hover:bg-muted/50 flex items-center gap-2">
              <Swords className="w-4 h-4" />
              Move History ({session?.move_history?.length || 0} moves)
            </summary>
            <div className="px-3 pb-3 max-h-[150px] overflow-y-auto font-mono text-xs">
              {session?.move_history?.length > 0 ? (
                <div className="space-y-1">
                  {Array.from({ length: Math.ceil(session.move_history.length / 2) }).map((_, i) => {
                    const whiteMove = session.move_history[i * 2];
                    const blackMove = session.move_history[i * 2 + 1];
                    return (
                      <div key={i} className="flex gap-2">
                        <span className="text-muted-foreground w-5">{i + 1}.</span>
                        <span className={whiteMove?.by === "player" ? "text-primary" : ""}>
                          {whiteMove?.move || ""}
                        </span>
                        <span className={blackMove?.by === "player" ? "text-primary" : ""}>
                          {blackMove?.move || ""}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-2">No moves yet</p>
              )}
            </div>
          </details>
          
          {/* Guardian Status */}
          <div className="p-3 border-t border-border text-xs">
            <ShieldAlert className="w-3 h-3 inline mr-1 text-primary" />
            <span className="text-muted-foreground">
              Guardian: {remainingInterventions} intervention{remainingInterventions !== 1 ? "s" : ""} remaining
            </span>
          </div>
        </div>
      </div>

      {/* Guardian Intervention Modal */}
      {guardianIntervention && pendingMove && (
        <div 
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          data-testid="guardian-intervention-modal"
        >
          <Card className={`max-w-md w-full border-2 ${
            guardianIntervention.risk_level === "critical" ? "border-red-500" :
            guardianIntervention.risk_level === "high" ? "border-orange-500" :
            "border-yellow-500"
          }`}>
            <CardHeader className={`pb-3 ${
              guardianIntervention.risk_level === "critical" ? "bg-red-500/10" :
              guardianIntervention.risk_level === "high" ? "bg-orange-500/10" :
              "bg-yellow-500/10"
            }`}>
              <div className="flex items-center gap-3">
                <AlertTriangle className={`w-8 h-8 ${
                  guardianIntervention.risk_level === "critical" ? "text-red-500" :
                  guardianIntervention.risk_level === "high" ? "text-orange-500" :
                  "text-yellow-500"
                }`} />
                <div>
                  <CardTitle className="text-lg">
                    {guardianIntervention.intervention_type === "block" ? "Wait!" : "Think Again"}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Coach Guardian detected a potential mistake
                  </p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {/* Warning Message */}
              <div className="text-base font-medium">
                {guardianIntervention.message}
              </div>
              
              {/* Explanation */}
              <p className="text-sm text-muted-foreground">
                {guardianIntervention.explanation}
              </p>
              
              {/* Alternative Moves with Visual Hints */}
              {guardianIntervention.alternative_moves?.length > 0 && (
                <div className="p-3 rounded-lg bg-muted/50">
                  <div className="flex items-center gap-2 mb-2 text-sm font-medium">
                    <Lightbulb className="w-4 h-4 text-primary" />
                    Better alternatives (click to see on board):
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {guardianIntervention.alternative_moves.map((move, i) => (
                      <Badge 
                        key={i} 
                        variant="outline" 
                        className="font-mono cursor-pointer hover:bg-primary/20 hover:border-primary transition-colors"
                        onClick={() => {
                          // Extract squares from SAN move (e.g., "Nf3" -> "f3")
                          const squares = move.match(/[a-h][1-8]/g);
                          if (squares && squares.length > 0) {
                            toast.info(`Move ${move}: ${squares.join(' → ')}`, {
                              duration: 3000,
                              icon: <Lightbulb className="w-4 h-4 text-primary" />
                            });
                          }
                        }}
                      >
                        <Target className="w-3 h-3 mr-1 text-primary" />
                        {move}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    These moves maintain or improve your position.
                  </p>
                </div>
              )}
              
              {/* Pending Move */}
              <div className="text-sm text-muted-foreground">
                Your move: <span className="font-mono font-medium text-foreground">{pendingMove.moveSan}</span>
              </div>
              
              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={cancelRiskyMove}
                  data-testid="guardian-cancel-btn"
                >
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Choose Different Move
                </Button>
                <Button
                  variant={guardianIntervention.risk_level === "critical" ? "destructive" : "default"}
                  className="flex-1"
                  onClick={confirmRiskyMove}
                  data-testid="guardian-confirm-btn"
                >
                  Play Anyway
                </Button>
              </div>
              
              {/* Interventions remaining */}
              <p className="text-xs text-center text-muted-foreground pt-2">
                {remainingInterventions > 1 
                  ? `${remainingInterventions - 1} intervention${remainingInterventions - 1 !== 1 ? "s" : ""} remaining after this`
                  : "This is your last intervention warning"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </Layout>
  );
};

export default CoachPlay;
