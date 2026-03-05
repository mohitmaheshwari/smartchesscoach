/**
 * LAB PAGE - Surgical Game Correction Environment
 * 
 * Purpose: Deep correction of a single game.
 * Not diagnosis. Not trend. One game → fully understood → corrected.
 * 
 * When user leaves this page, they should feel:
 * "I understand exactly where I lost control."
 */

import { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { LessonCard, CoachNotice, FocusLockStatus, AlternateTimeline } from "@/components/Lab";
import { 
  ArrowLeft, 
  Loader2, 
  Brain,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Target,
  Zap,
  Play,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Eye,
  EyeOff,
  BookOpen,
  Lightbulb,
  TrendingUp,
  TrendingDown,
  Pause,
  Sparkles,
  RefreshCw,
  HelpCircle,
  Star,
  Trophy,
  MessageCircle,
  Send,
  ListChecks,
  Square,
  CheckSquare,
  Lock,
  GraduationCap,
  ArrowRight
} from "lucide-react";
import { formatEvalWithContext, formatCpLoss } from "@/utils/evalFormatter";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Convert SAN move to arrow coordinates [from, to, color]
// Used to show arrows for punishing moves
const sanToArrow = (san, fen, color = "rgb(220,38,38)") => {
  if (!san || !fen) return null;
  try {
    const chess = new Chess(fen);
    const move = chess.move(san);
    if (move) {
      return [move.from, move.to, color];
    }
  } catch (e) {
    console.error("Error converting SAN to arrow:", e);
  }
  return null;
};

// Get FEN after a move is played
const getFenAfterMove = (fen, san) => {
  if (!fen || !san) return null;
  try {
    const chess = new Chess(fen);
    chess.move(san);
    return chess.fen();
  } catch (e) {
    return null;
  }
};

// Convert FEN to position object for react-chessboard
const fenToPositionObject = (fen) => {
  const position = {};
  const parts = fen.split(' ');
  const rows = parts[0].split('/');
  
  for (let row = 0; row < 8; row++) {
    let col = 0;
    for (const char of rows[row]) {
      if (char >= '1' && char <= '8') {
        col += parseInt(char);
      } else {
        const file = String.fromCharCode(97 + col);
        const rank = 8 - row;
        const square = file + rank;
        const color = char === char.toUpperCase() ? 'w' : 'b';
        const piece = char.toUpperCase();
        position[square] = color + piece;
        col++;
      }
    }
  }
  return position;
};

const Lab = ({ user }) => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialMove = searchParams.get('move');
  const sourceContext = searchParams.get('src'); // 'journey' if coming from Journey page
  
  // Data states
  const [game, setGame] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [labData, setLabData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [coachCommentary, setCoachCommentary] = useState(null);
  const [reanalyzing, setReanalyzing] = useState(false);
  
  // Board states
  const [moves, setMoves] = useState([]);
  const [allFens, setAllFens] = useState([START_FEN]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [positionObject, setPositionObject] = useState(() => fenToPositionObject(START_FEN));
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [lastMoveSquares, setLastMoveSquares] = useState({});
  const [customArrows, setCustomArrows] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  
  // UI states
  const [showOnlyCritical, setShowOnlyCritical] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState("milestones");
  
  // Deep strategy analysis (position-specific insights)
  const [deepStrategy, setDeepStrategy] = useState(null);
  const [loadingDeepStrategy, setLoadingDeepStrategy] = useState(false);
  
  // Practice mode
  const [practiceMode, setPracticeMode] = useState(false);
  const [practicePositions, setPracticePositions] = useState([]);
  const [practiceIndex, setPracticeIndex] = useState(0);
  
  // Focus Module state (behavioral coaching)
  const [focusModule, setFocusModule] = useState(null);
  const [protocolChecks, setProtocolChecks] = useState([false, false, false]);
  
  // Focus Lock state (Step 9.1 - Micro Reinforcement)
  const [focusLock, setFocusLock] = useState(null);
  
  // Module Trigger state (Step 10 - Pattern Injection)
  const [moduleTrigger, setModuleTrigger] = useState(null);
  
  // User's recurring patterns from home-intelligence (for coaching connection)
  const [userPatterns, setUserPatterns] = useState(null);
  
  // Re-analyze game handler
  const handleReanalyze = async () => {
    setReanalyzing(true);
    try {
      const response = await fetch(`${API}/games/${gameId}/reanalyze`, {
        method: "POST",
        credentials: "include"
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to queue re-analysis");
      }
      
      const data = await response.json();
      toast.success(data.message || "Game queued for re-analysis!");
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API}/games/${gameId}/analysis-status`, { credentials: "include" });
          if (statusRes.ok) {
            const status = await statusRes.json();
            if (status.status === "analyzed") {
              clearInterval(pollInterval);
              // Refetch analysis
              const analysisRes = await fetch(`${API}/analysis/${gameId}`, { credentials: "include" });
              if (analysisRes.ok) {
                const analysisData = await analysisRes.json();
                setAnalysis(analysisData);
                toast.success("Analysis complete!");
              }
              // Refetch lab data
              const labRes = await fetch(`${API}/lab/${gameId}`, { credentials: "include" });
              if (labRes.ok) {
                setLabData(await labRes.json());
              }
              setReanalyzing(false);
            } else if (status.status === "failed") {
              clearInterval(pollInterval);
              toast.error("Analysis failed. Please try again.");
              setReanalyzing(false);
            }
          }
        } catch (err) {
          console.error("Poll error:", err);
        }
      }, 3000); // Poll every 3 seconds
      
      // Stop polling after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setReanalyzing(false);
      }, 120000);
      
    } catch (error) {
      toast.error(error.message || "Failed to queue re-analysis");
      setReanalyzing(false);
    }
  };
  
  // Fetch game and analysis data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch game data
        const gameResponse = await fetch(`${API}/games/${gameId}`, { credentials: "include" });
        if (!gameResponse.ok) throw new Error("Game not found");
        const gameData = await gameResponse.json();
        setGame(gameData);
        setBoardOrientation(gameData.user_color === "black" ? "black" : "white");
        
        // Fetch analysis
        const analysisResponse = await fetch(`${API}/analysis/${gameId}`, { credentials: "include" });
        if (analysisResponse.ok) {
          const analysisData = await analysisResponse.json();
          setAnalysis(analysisData);
          
          // Fetch coach commentary if analysis exists
          if (analysisData) {
            try {
              const coachResponse = await fetch(`${API}/coach/commentary/${gameId}`, { credentials: "include" });
              if (coachResponse.ok) {
                const coachData = await coachResponse.json();
                if (coachData.commentary) {
                  setCoachCommentary(coachData.commentary);
                }
              }
            } catch (e) {
              console.log("Coach commentary not available");
            }
          }
        }
        
        // Fetch lab-specific data
        const labResponse = await fetch(`${API}/lab/${gameId}`, { credentials: "include" });
        if (labResponse.ok) {
          const labDataResponse = await labResponse.json();
          setLabData(labDataResponse);
        }
        
        // Fetch active focus module
        try {
          const focusResponse = await fetch(`${API}/cognitive/training-priority`, { credentials: "include" });
          if (focusResponse.ok) {
            const focusData = await focusResponse.json();
            if (focusData.primary_focus) {
              setFocusModule(focusData.primary_focus);
            }
          }
        } catch (e) {
          console.log("Focus module not available");
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

  // Fetch deep strategy analysis when Strategy tab is selected
  useEffect(() => {
    const fetchDeepStrategy = async () => {
      if (activeTab === "strategy" && !deepStrategy && !loadingDeepStrategy && gameId) {
        setLoadingDeepStrategy(true);
        try {
          const response = await fetch(`${API}/lab/${gameId}/deep-strategy`, {
            credentials: "include"
          });
          if (response.ok) {
            const data = await response.json();
            setDeepStrategy(data);
          }
        } catch (error) {
          console.error("Error fetching deep strategy:", error);
        } finally {
          setLoadingDeepStrategy(false);
        }
      }
    };
    
    fetchDeepStrategy();
  }, [activeTab, gameId, deepStrategy, loadingDeepStrategy]);

  // Fetch Focus Lock state (Step 9.1)
  useEffect(() => {
    const fetchFocusLock = async () => {
      try {
        const response = await fetch(`${API}/coach/focus-lock`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          if (data.active) {
            setFocusLock(data);
          }
        }
      } catch (error) {
        console.error('Error fetching focus lock:', error);
      }
    };
    fetchFocusLock();
  }, []);

  // Fetch user's recurring patterns for coaching connection
  useEffect(() => {
    const fetchUserPatterns = async () => {
      try {
        const response = await fetch(`${API}/coach/home-intelligence`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          if (data.specific_patterns?.has_pattern) {
            setUserPatterns(data.specific_patterns);
          }
        }
      } catch (error) {
        console.error('Error fetching user patterns:', error);
      }
    };
    fetchUserPatterns();
  }, []);

  // Fetch Module Trigger (Step 10)
  useEffect(() => {
    if (!gameId) return;
    
    const fetchModuleTrigger = async () => {
      try {
        const response = await fetch(`${API}/coach/module/${gameId}`, {
          credentials: 'include'
        });
        if (response.ok) {
          const data = await response.json();
          if (data.triggered) {
            setModuleTrigger(data);
          }
        }
      } catch (error) {
        console.error('Error fetching module trigger:', error);
      }
    };
    fetchModuleTrigger();
  }, [gameId]);

  // Parse PGN and setup board
  useEffect(() => {
    if (!game?.pgn) return;
    
    const tempGame = new Chess();
    try {
      tempGame.loadPgn(game.pgn);
    } catch {
      // Try parsing moves only
      const lines = game.pgn.split('\n');
      let movesText = '';
      for (const line of lines) {
        if (!line.startsWith('[') && line.trim()) {
          movesText += ' ' + line;
        }
      }
      movesText = movesText.replace(/\{[^}]*\}/g, '').replace(/\([^)]*\)/g, '').trim();
      try {
        tempGame.loadPgn(movesText);
      } catch {
        return;
      }
    }
    
    const history = tempGame.history({ verbose: true });
    const fens = [START_FEN];
    const calcGame = new Chess();
    
    for (const m of history) {
      calcGame.move({ from: m.from, to: m.to, promotion: m.promotion });
      fens.push(calcGame.fen());
    }
    
    setAllFens(fens);
    setMoves(history);
    setPositionObject(fenToPositionObject(START_FEN));
    setCurrentMoveIndex(-1);
  }, [game?.pgn]);

  // Handle initial move from URL
  useEffect(() => {
    if (initialMove && moves.length > 0) {
      const moveNum = parseInt(initialMove, 10);
      if (!isNaN(moveNum) && moveNum > 0) {
        // Convert move number to index (move 1 = index 0 or 1 depending on color)
        const targetIndex = (moveNum - 1) * 2 + (game?.user_color === "black" ? 1 : 0);
        goToMove(Math.min(targetIndex, moves.length - 1));
        
        // If coming from Journey, switch to milestones tab to show the moment
        if (sourceContext === 'journey') {
          setActiveTab('milestones');
        }
      }
    }
  }, [initialMove, moves.length, game?.user_color, sourceContext]);

  // Navigate to a specific move
  const goToMove = (targetIndex) => {
    const clampedIndex = Math.max(-1, Math.min(targetIndex, moves.length - 1));
    const posIndex = clampedIndex + 1;
    const fen = allFens[posIndex] || START_FEN;
    
    setPositionObject(fenToPositionObject(fen));
    setCurrentMoveIndex(clampedIndex);
    
    if (clampedIndex >= 0 && moves[clampedIndex]) {
      const move = moves[clampedIndex];
      setLastMoveSquares({
        [move.from]: { backgroundColor: "rgba(255, 255, 0, 0.4)" },
        [move.to]: { backgroundColor: "rgba(255, 255, 0, 0.4)" }
      });
      // Show arrow for "you played" move (orange/red for user moves)
      // react-chessboard expects: [[from, to, color]]
      if (move.from && move.to) {
        setCustomArrows([[move.from, move.to, "rgb(255,100,0)"]]);
      } else {
        setCustomArrows([]);
      }
    } else {
      setLastMoveSquares({});
      setCustomArrows([]);
    }
  };

  // Navigation helpers
  const goToStart = () => { goToMove(-1); setIsPlaying(false); };
  const goToEnd = () => { goToMove(moves.length - 1); setIsPlaying(false); };
  const goBack = () => currentMoveIndex <= 0 ? goToStart() : goToMove(currentMoveIndex - 1);
  const goForward = () => currentMoveIndex < moves.length - 1 && goToMove(currentMoveIndex + 1);
  const flipBoard = () => setBoardOrientation(o => o === "white" ? "black" : "white");
  
  // Play a variation from a specific FEN position
  // This animates the best line on the board so users can visualize it
  const [variationMode, setVariationMode] = useState(false);
  const [variationMoves, setVariationMoves] = useState([]);
  const [variationIndex, setVariationIndex] = useState(0);
  const [variationBaseFen, setVariationBaseFen] = useState(null);
  
  const playVariation = (fenBefore, bestMove, pvLine) => {
    if (!fenBefore || !bestMove) {
      toast.error("Position data not available");
      return;
    }
    
    // Build the full line: best move + continuation
    const fullLine = [bestMove, ...(pvLine || [])];
    
    // Check if we have a meaningful line to show
    if (fullLine.length === 1) {
      toast.info("Showing the better move (no continuation available)");
    }
    
    // Set up variation mode
    setVariationBaseFen(fenBefore);
    setVariationMoves(fullLine);
    setVariationIndex(0);
    setVariationMode(true);
    setIsPlaying(false); // Stop any normal playback
    
    // Show the starting position
    setPositionObject(fenToPositionObject(fenBefore));
    setLastMoveSquares({});
    
    toast.success(`Playing ${fullLine.length} move variation...`);
  };
  
  // Show punishment - displays the user's bad move followed by opponent's best response with arrow
  // This helps users understand WHY their move was bad
  const showPunishment = (fenBefore, userMove, pvAfterPlayed) => {
    if (!fenBefore || !userMove) {
      toast.error("Position data not available");
      return;
    }
    
    // First, play the user's bad move to get to the position after
    const fenAfterUserMove = getFenAfterMove(fenBefore, userMove);
    if (!fenAfterUserMove) {
      toast.error("Could not reconstruct position");
      return;
    }
    
    // Show the position after user's move
    setPositionObject(fenToPositionObject(fenAfterUserMove));
    
    // Build arrows:
    // 1. User's bad move (orange/red)
    const userArrow = sanToArrow(userMove, fenBefore, "rgb(239,68,68)"); // Red for user's mistake
    
    // 2. Opponent's best punishing response (dark red/crimson)
    const punishingMove = pvAfterPlayed && pvAfterPlayed[0];
    const punishArrow = punishingMove ? sanToArrow(punishingMove, fenAfterUserMove, "rgb(185,28,28)") : null;
    
    // Set arrows - show both user's move and opponent's punishment
    const arrows = [];
    if (userArrow) arrows.push(userArrow);
    if (punishArrow) arrows.push(punishArrow);
    setCustomArrows(arrows);
    
    // Show highlight for the punishment move
    if (punishArrow) {
      setLastMoveSquares({
        [punishArrow[0]]: { backgroundColor: "rgba(220,38,38,0.4)" },
        [punishArrow[1]]: { backgroundColor: "rgba(220,38,38,0.4)" }
      });
    }
    
    // If there's a continuation, offer to play the full punishment line
    if (pvAfterPlayed && pvAfterPlayed.length > 1) {
      toast.success(
        `After ${userMove}, opponent plays ${punishingMove}! Click "Play variation" to see the full continuation.`,
        { duration: 5000 }
      );
    } else if (punishingMove) {
      toast.success(`After ${userMove}, opponent punishes with ${punishingMove}!`);
    } else {
      toast.info(`Showing position after ${userMove}`);
    }
  };
  
  // Exit variation mode and return to game
  const exitVariation = () => {
    setVariationMode(false);
    setVariationMoves([]);
    setVariationIndex(0);
    setVariationBaseFen(null);
    // Return to current position in the actual game
    const fen = allFens[currentMoveIndex + 1] || START_FEN;
    setPositionObject(fenToPositionObject(fen));
  };
  
  // Step through variation
  const variationNext = () => {
    if (variationIndex >= variationMoves.length) return;
    
    try {
      // Build position up to current variation index
      const chess = new Chess(variationBaseFen);
      for (let i = 0; i <= variationIndex; i++) {
        const move = variationMoves[i];
        if (move) {
          const result = chess.move(move);
          if (!result) {
            console.error(`Invalid move in variation: ${move}`);
            return;
          }
        }
      }
      
      // Update board
      setPositionObject(fenToPositionObject(chess.fen()));
      
      // Highlight the last move
      const lastMove = chess.history({ verbose: true }).slice(-1)[0];
      if (lastMove) {
        setLastMoveSquares({
          [lastMove.from]: { backgroundColor: "rgba(100, 200, 100, 0.5)" },
          [lastMove.to]: { backgroundColor: "rgba(100, 200, 100, 0.5)" }
        });
      }
      
      setVariationIndex(i => i + 1);
    } catch (e) {
      console.error("Error playing variation:", e);
    }
  };
  
  const variationBack = () => {
    if (variationIndex <= 0) {
      // Back to base position
      setPositionObject(fenToPositionObject(variationBaseFen));
      setLastMoveSquares({});
      return;
    }
    
    try {
      // Build position up to one move before current
      const chess = new Chess(variationBaseFen);
      for (let i = 0; i < variationIndex - 1; i++) {
        chess.move(variationMoves[i]);
      }
      
      setPositionObject(fenToPositionObject(chess.fen()));
      setVariationIndex(i => i - 1);
      
      // Highlight last move if any
      if (variationIndex > 1) {
        const lastMove = chess.history({ verbose: true }).slice(-1)[0];
        if (lastMove) {
          setLastMoveSquares({
            [lastMove.from]: { backgroundColor: "rgba(100, 200, 100, 0.5)" },
            [lastMove.to]: { backgroundColor: "rgba(100, 200, 100, 0.5)" }
          });
        }
      } else {
        setLastMoveSquares({});
      }
    } catch (e) {
      console.error("Error going back in variation:", e);
    }
  };
  
  // Toggle play
  const togglePlay = () => {
    if (currentMoveIndex >= moves.length - 1) {
      goToStart();
      setTimeout(() => setIsPlaying(true), 100);
    } else {
      setIsPlaying(p => !p);
    }
  };

  // Auto-play effect
  useEffect(() => {
    if (!isPlaying || currentMoveIndex >= moves.length - 1) {
      if (currentMoveIndex >= moves.length - 1) setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => goToMove(currentMoveIndex + 1), 600);
    return () => clearTimeout(timer);
  }, [isPlaying, currentMoveIndex, moves.length]);

  // Trigger analysis
  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const response = await fetch(`${API}/analyze-game`, {
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
      
      // Refetch lab data
      const labResponse = await fetch(`${API}/lab/${gameId}`, { credentials: "include" });
      if (labResponse.ok) {
        setLabData(await labResponse.json());
      }
      toast.success("Analysis complete!");
    } catch (error) {
      toast.error(error.message || "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  // Extract data from analysis
  const stockfishData = analysis?.stockfish_analysis || {};
  const moveEvaluations = stockfishData.move_evaluations || [];
  const accuracy = stockfishData.accuracy;
  const coreLesson = labData?.core_lesson;
  const strategicAnalysis = labData?.strategic_analysis;
  const positionalInsight = labData?.positional_insight;
  const wisdomLessons = labData?.wisdom_lessons || [];
  
  // State for collapsible positional insight
  const [insightExpanded, setInsightExpanded] = useState(false);
  
  // Coach Mode vs Engine Mode toggle
  const [coachMode, setCoachMode] = useState(true); // Default to Coach Mode
  
  // User color from game data (needed for move filtering)
  const userColor = game?.user_color || "white";
  
  // Determine if move eval is user's move based on FEN (more accurate)
  const isUserMoveFromFen = (eval_entry) => {
    if (eval_entry.is_user_move !== undefined) return eval_entry.is_user_move;
    const fen = eval_entry.fen_before || '';
    const parts = fen.split(' ');
    const turn = parts[1]; // 'w' or 'b'
    return (userColor === 'white' && turn === 'w') || (userColor === 'black' && turn === 'b');
  };
  
  // COACHING PHILOSOPHY:
  // Coach Mode: Only show human-improvable errors
  // - Forcing tactics (missed/allowed)
  // - Repeated patterns
  // - Threat-check failures
  // - No-plan moves in critical phases
  // Engine Mode: Show all engine disagreements
  
  // Categorize a move for coaching
  const categorizeMoveForCoaching = (m) => {
    const cpLoss = Math.abs(m.cp_loss || 0);
    const mistakeType = m.mistake_type || '';
    const move = m.move || '';
    
    // Check for prophylactic moves (h6, a6, g6, h3, a3, g3 type moves)
    const isProphylactic = /^[hag][36]$/.test(move.toLowerCase());
    
    // Determine category
    if (cpLoss >= 300) {
      return { category: 'blunder', showInCoachMode: true, priority: 1 };
    }
    
    // Check for tactical content
    const hasTactic = mistakeType.includes('mate') || 
                      mistakeType.includes('fork') || 
                      mistakeType.includes('pin') ||
                      mistakeType.includes('hanging') ||
                      mistakeType.includes('trap');
    
    if (cpLoss >= 150 || hasTactic) {
      return { category: 'tactical_mistake', showInCoachMode: true, priority: 2 };
    }
    
    // Prophylactic moves - only show if really wrong (>150cp) or creates tactic
    if (isProphylactic && cpLoss < 150) {
      if (cpLoss < 100) {
        // Good prophylaxis - don't show
        return { category: 'engine_preference', showInCoachMode: false, priority: 99 };
      } else {
        // Questionable prophylaxis - show as coaching moment but not puzzle
        return { category: 'phantom_threat', showInCoachMode: true, priority: 3 };
      }
    }
    
    // Strategic slip (50-149cp)
    if (cpLoss >= 100) {
      return { category: 'strategic_slip', showInCoachMode: true, priority: 3 };
    }
    
    // Small inaccuracies (50-99cp) - check if there's a coaching angle
    if (cpLoss >= 50) {
      // These are engine preferences unless they reveal a thinking pattern
      return { category: 'engine_preference', showInCoachMode: false, priority: 99 };
    }
    
    return { category: 'good_move', showInCoachMode: false, priority: 99 };
  };
  
  // Count mistakes - updated to reflect coaching philosophy
  const mistakeCounts = useMemo(() => {
    let blunders = 0, mistakes = 0, inaccuracies = 0, enginePrefs = 0;
    moveEvaluations.forEach(m => {
      if (!isUserMoveFromFen(m)) return;
      const cpLoss = Math.abs(m.cp_loss || 0);
      const coaching = categorizeMoveForCoaching(m);
      
      if (cpLoss >= 300) blunders++;
      else if (cpLoss >= 150 || coaching.category === 'tactical_mistake') mistakes++;
      else if (cpLoss >= 100 || coaching.category === 'strategic_slip') inaccuracies++;
      else if (cpLoss >= 50) enginePrefs++;
    });
    return { blunders, mistakes, inaccuracies, enginePrefs };
  }, [moveEvaluations, userColor]);

  // Group milestones - brilliant moves, good moves, and learning moments
  // Now respects Coach Mode vs Engine Mode
  const groupedMilestones = useMemo(() => {
    const groups = {
      brilliant_moves: [],  // Outstanding moves - very low cp_loss in complex positions
      great_moves: [],      // Good tactical/positional decisions
      learning_moments: [], // Mistakes reframed as growth opportunities
      engine_preferences: [], // Hidden by default in Coach Mode
    };
    
    moveEvaluations.forEach(m => {
      if (!isUserMoveFromFen(m)) return;
      const cpLoss = Math.abs(m.cp_loss || 0);
      const evalBefore = m.eval_before || 0;
      const evalAfter = m.eval_after || 0;
      const coaching = categorizeMoveForCoaching(m);
      
      // Brilliant/Great moves: low cp_loss OR gained significant advantage
      if (cpLoss <= 5) {
        // Perfect or near-perfect move
        const evalSwing = evalAfter - evalBefore;
        const entry = {
          move_number: m.move_number,
          move: m.move,
          best_move: m.best_move,
          cp_loss: cpLoss,
          eval_before: evalBefore,
          eval_after: evalAfter,
          fen_before: m.fen_before,
          phase: m.phase || (m.move_number <= 10 ? 'opening' : m.move_number <= 30 ? 'middlegame' : 'endgame'),
          isBrilliant: evalSwing > 150 || (cpLoss === 0 && Math.abs(evalBefore) < 100), // Found winning move OR played perfectly in balanced position
          isGreat: cpLoss <= 5,
          context: getPositiveContext(m),
          type: 'positive'
        };
        
        // Classify as brilliant if: found a winning shot OR played perfectly when under pressure
        if (entry.isBrilliant || (evalBefore < -50 && cpLoss === 0)) {
          groups.brilliant_moves.push(entry);
        } else if (cpLoss <= 5) {
          groups.great_moves.push(entry);
        }
      }
      
      // Learning moments: based on coaching classification
      if (cpLoss >= 50) {
        const mistakeType = m.mistake_type || '';
        const entry = {
          move_number: m.move_number,
          move: m.move,
          best_move: m.best_move,
          cp_loss: cpLoss,
          eval_before: evalBefore,
          eval_after: evalAfter,
          fen_before: m.fen_before,
          phase: m.phase || (m.move_number <= 10 ? 'opening' : m.move_number <= 30 ? 'middlegame' : 'endgame'),
          context: getContextLabel(m),
          isBlunder: cpLoss >= 300,
          isMistake: coaching.category === 'tactical_mistake' || (cpLoss >= 150 && cpLoss < 300),
          isInaccuracy: coaching.category === 'strategic_slip' || (cpLoss >= 100 && cpLoss < 150),
          isEnginePreference: coaching.category === 'engine_preference',
          isPhantomThreat: coaching.category === 'phantom_threat',
          mistakeType: mistakeType,
          coachingCategory: coaching.category,
          coachingPriority: coaching.priority,
          showInCoachMode: coaching.showInCoachMode,
          type: 'learning',
          // PV lines for visualization
          pv_after_played: m.pv_after_played || [],
          pv_after_best: m.pv_after_best || []
        };
        
        // In Coach Mode, separate engine preferences
        if (coaching.showInCoachMode) {
          groups.learning_moments.push(entry);
        } else {
          groups.engine_preferences.push(entry);
        }
      }
    });
    
    // Limit brilliant/great to top 5 each, sort learning chronologically (first to last mistake)
    groups.brilliant_moves = groups.brilliant_moves.slice(0, 5);
    groups.great_moves = groups.great_moves.slice(0, 5);
    groups.learning_moments.sort((a, b) => a.move_number - b.move_number);
    
    // Build final array - ORDER DEPENDS ON GAME RESULT
    // For losses: Learning Moments first (what went wrong matters most)
    // For wins: Brilliant moves first (celebrate, but still show issues)
    const result = [];
    
    // Determine if it's a loss
    const gameResult = game?.result || "";
    const isLoss = (gameResult === "0-1" && userColor === "white") || 
                   (gameResult === "1-0" && userColor === "black");
    
    if (isLoss) {
      // LOSS: Show learning moments first (what went wrong)
      if (groups.learning_moments.length > 0) {
        result.push({
          type: 'learning_moments',
          label: "Where It Went Wrong",
          icon: "lightbulb",
          count: groups.learning_moments.length,
          items: groups.learning_moments.sort((a, b) => a.coachingPriority - b.coachingPriority),
          positive: false
        });
      }
      
      // Then show what went well (silver linings)
      if (groups.brilliant_moves.length > 0) {
        result.push({
          type: 'brilliant_moves',
          label: "What Worked",
          icon: "sparkles",
          count: groups.brilliant_moves.length,
          items: groups.brilliant_moves,
          positive: true
        });
      }
      
      if (groups.great_moves.length > 0) {
        result.push({
          type: 'great_moves', 
          label: "Good Decisions",
          icon: "star",
          count: groups.great_moves.length,
          items: groups.great_moves,
          positive: true
        });
      }
    } else {
      // WIN/DRAW: Show brilliant moves first (celebrate)
      if (groups.brilliant_moves.length > 0) {
        result.push({
          type: 'brilliant_moves',
          label: "Brilliant Moves",
          icon: "sparkles",
          count: groups.brilliant_moves.length,
          items: groups.brilliant_moves,
          positive: true
        });
      }
      
      if (groups.great_moves.length > 0) {
        result.push({
          type: 'great_moves', 
          label: "Great Decisions",
          icon: "star",
          count: groups.great_moves.length,
          items: groups.great_moves,
          positive: true
        });
      }
      
      if (groups.learning_moments.length > 0) {
        result.push({
          type: 'learning_moments',
          label: "Room for Improvement",
          icon: "lightbulb",
          count: groups.learning_moments.length,
          items: groups.learning_moments.sort((a, b) => a.coachingPriority - b.coachingPriority),
          positive: false
        });
      }
    }
    
    // In Engine Mode, also show engine preferences
    if (groups.engine_preferences.length > 0) {
      result.push({
        type: 'engine_preferences',
        label: "Engine Preferences",
        icon: "cpu",
        count: groups.engine_preferences.length,
        items: groups.engine_preferences,
        positive: false,
        hidden: true // Hidden by default in Coach Mode
      });
    }
    
    return result;
  }, [moveEvaluations, userColor, game?.result]);
  
  // Filter milestones based on mode
  const displayedMilestones = useMemo(() => {
    if (!coachMode) {
      // Engine Mode - merge learning_moments and engine_preferences into one combined view
      const engineResult = groupedMilestones.map(group => {
        if (group.type === 'learning_moments') {
          // Find engine preferences and merge them
          const enginePrefs = groupedMilestones.find(g => g.type === 'engine_preferences');
          if (enginePrefs && enginePrefs.items.length > 0) {
            return {
              ...group,
              label: "All Engine Findings",
              items: [...group.items, ...enginePrefs.items].sort((a, b) => a.move_number - b.move_number),
              count: group.items.length + enginePrefs.items.length
            };
          }
        }
        return group;
      }).filter(g => g.type !== 'engine_preferences'); // Remove the separate engine_preferences group
      return engineResult;
    }
    // Coach Mode - hide engine preferences (only show human-improvable errors)
    return groupedMilestones.filter(g => !g.hidden);
  }, [groupedMilestones, coachMode]);

  // Critical moves (eval swing > 1.5 or big cp loss)
  const criticalMoves = useMemo(() => {
    return moveEvaluations.filter(m => {
      if (!isUserMoveFromFen(m)) return false;
      const cpLoss = Math.abs(m.cp_loss || 0);
      return cpLoss >= 150; // 1.5 pawns - matches new threshold
    });
  }, [moveEvaluations, userColor]);

  // Get biggest eval swing
  const biggestEvalSwing = useMemo(() => {
    let maxSwing = null;
    moveEvaluations.forEach(m => {
      if (!isUserMoveFromFen(m)) return;
      const cpLoss = Math.abs(m.cp_loss || 0);
      if (!maxSwing || cpLoss > maxSwing.cp_loss) {
        maxSwing = { ...m, cp_loss: cpLoss };
      }
    });
    return maxSwing;
  }, [moveEvaluations, userColor]);

  // Move list for the board panel
  const movePairs = useMemo(() => {
    const pairs = [];
    for (let i = 0; i < moves.length; i += 2) {
      const whiteMove = moves[i];
      const blackMove = moves[i + 1];
      
      // Get evaluations for these moves
      const whiteEval = moveEvaluations.find(e => 
        e.move_number === Math.floor(i / 2) + 1 && 
        (game?.user_color === 'white' ? e.is_user_move : !e.is_user_move)
      );
      const blackEval = moveEvaluations.find(e => 
        e.move_number === Math.floor(i / 2) + 1 && 
        (game?.user_color === 'black' ? e.is_user_move : !e.is_user_move)
      );
      
      pairs.push({
        num: Math.floor(i / 2) + 1,
        white: whiteMove?.san || "",
        black: blackMove?.san || "",
        wIdx: i,
        bIdx: i + 1,
        wCpLoss: game?.user_color === 'white' ? (whiteEval?.cp_loss || 0) : 0,
        bCpLoss: game?.user_color === 'black' ? (blackEval?.cp_loss || 0) : 0,
        wIsCritical: game?.user_color === 'white' && Math.abs(whiteEval?.cp_loss || 0) >= 150,
        bIsCritical: game?.user_color === 'black' && Math.abs(blackEval?.cp_loss || 0) >= 150
      });
    }
    return pairs;
  }, [moves, moveEvaluations, game?.user_color]);

  // Start practice mode
  const startPracticeMode = () => {
    const positions = criticalMoves.slice(0, 5).map(m => ({
      fen: m.fen_before,
      move_number: m.move_number,
      best_move: m.best_move,
      played_move: m.move,
      cp_loss: Math.abs(m.cp_loss || 0),
      eval_before: m.eval_before
    }));
    setPracticePositions(positions);
    setPracticeIndex(0);
    setPracticeMode(true);
  };
  
  // Reset practice to first position (for retry all)
  const resetPractice = () => {
    setPracticeIndex(0);
  };

  // Loading state
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </Layout>
    );
  }

  // Extract game info
  const whitePlayer = game?.white_player || "White";
  const blackPlayer = game?.black_player || "Black";
  const result = game?.result || "";
  const opponent = userColor === "white" ? blackPlayer : whitePlayer;
  const opponentRating = userColor === "white" ? game?.black_rating : game?.white_rating;

  return (
    <Layout user={user}>
      <div className="h-[calc(100vh-80px)] flex flex-col" data-testid="lab-page">
        {/* FROM JOURNEY BREADCRUMB */}
        {sourceContext === 'journey' && (
          <div className="bg-blue-900/20 border-b border-blue-800/30 px-4 py-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-blue-400">From Journey</span>
              <span className="text-slate-500">•</span>
              <button 
                onClick={() => navigate('/journey')}
                className="text-slate-400 hover:text-white transition-colors"
              >
                Back to Journey
              </button>
            </div>
          </div>
        )}
        
        {/* STICKY HEADER */}
        <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/50 px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="w-5 h-5" />
              </Button>
              
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold">vs {opponent}</h1>
                  {opponentRating && (
                    <Badge variant="outline" className="text-xs">
                      {opponentRating}
                    </Badge>
                  )}
                  <Badge 
                    variant={result.includes("1-0") ? (userColor === "white" ? "default" : "destructive") : 
                            result.includes("0-1") ? (userColor === "black" ? "default" : "destructive") : 
                            "secondary"}
                    className="text-xs"
                  >
                    {result.includes("1-0") ? (userColor === "white" ? "WIN" : "LOSS") :
                     result.includes("0-1") ? (userColor === "black" ? "WIN" : "LOSS") :
                     "DRAW"}
                  </Badge>
                  {/* Termination badge - shows how game ended */}
                  {game?.termination_text && (
                    <Badge 
                      variant="outline" 
                      className={`text-xs ${
                        game.termination_text.toLowerCase().includes('abandoned') || 
                        game.termination_text.toLowerCase().includes('disconnection')
                          ? 'border-amber-500/50 text-amber-400'
                          : 'border-slate-500/50 text-slate-400'
                      }`}
                    >
                      {game.termination_text}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  You played {userColor} • {accuracy ? `${accuracy}% accuracy` : ''}
                </p>
              </div>
            </div>
            
            {/* Stats */}
            {analysis && (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-red-500 font-bold">{mistakeCounts.blunders}</span>
                  <span className="text-muted-foreground">Blunders</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-orange-500 font-bold">{mistakeCounts.mistakes}</span>
                  <span className="text-muted-foreground">Tactical</span>
                </div>
                {!coachMode && mistakeCounts.enginePrefs > 0 && (
                  <div className="flex items-center gap-2 text-sm opacity-60">
                    <span className="text-gray-400 font-bold">{mistakeCounts.enginePrefs}</span>
                    <span className="text-muted-foreground">Prefs</span>
                  </div>
                )}
              </div>
            )}
            
            {/* Coach/Engine Mode Toggle */}
            <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-gray-800/50 border border-gray-700">
              <button
                onClick={() => setCoachMode(true)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  coachMode 
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                    : 'text-gray-400 hover:text-gray-300'
                }`}
                data-testid="coach-mode-btn"
                title="Shows only human-improvable errors"
              >
                <Brain className="w-3 h-3 inline mr-1" />
                Coach
              </button>
              <button
                onClick={() => setCoachMode(false)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  !coachMode 
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                    : 'text-gray-400 hover:text-gray-300'
                }`}
                data-testid="engine-mode-btn"
                title="Shows all engine disagreements"
              >
                <Zap className="w-3 h-3 inline mr-1" />
                Engine
              </button>
            </div>
            
            {/* Focus Lock Badge - Step 9.1 Micro Reinforcement */}
            {focusLock && focusLock.active && (
              <div 
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium ${
                  (focusLock.compliance?.average || 0) >= 80 
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' 
                    : (focusLock.compliance?.average || 0) >= 60 
                      ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                      : 'bg-red-500/10 text-red-400 border border-red-500/30'
                }`}
                data-testid="focus-lock-badge"
                title={`Focus Lock: ${focusLock.rule_description || 'Active'}`}
              >
                <Lock className="w-3 h-3" />
                <span>Focus Lock</span>
              </div>
            )}
            
            {/* Core Lesson - One sentence */}
            {coreLesson && coreLesson.pattern === "needs_detailed_analysis" ? (
              <Button 
                onClick={handleReanalyze} 
                disabled={reanalyzing}
                variant="outline"
                size="sm"
                className="gap-2 bg-amber-500/10 border-amber-500/30 hover:bg-amber-500/20 text-amber-400"
                data-testid="reanalyze-banner-btn"
              >
                <Lightbulb className="w-4 h-4" />
                {reanalyzing ? "Analyzing..." : "Re-analyze for detailed insights"}
                {reanalyzing && <Loader2 className="w-3 h-3 animate-spin ml-1" />}
              </Button>
            ) : coreLesson && coreLesson.pattern !== "clean_game" && (
              <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 max-w-md">
                <Lightbulb className="w-4 h-4 text-amber-500 shrink-0" />
                <span className="text-sm truncate">{coreLesson.lesson}</span>
              </div>
            )}
            
            {/* Practice Button */}
            {criticalMoves.length > 0 && (
              <Button 
                size="sm" 
                onClick={startPracticeMode}
                className="gap-1.5 bg-primary hover:bg-primary/90"
                data-testid="practice-btn"
              >
                <Target className="w-4 h-4" />
                Practice Critical Moments
              </Button>
            )}
            
            {/* Analyze Button (for unanalyzed games) */}
            {!analysis && (
              <Button onClick={handleAnalyze} disabled={analyzing}>
                {analyzing ? (
                  <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analyzing...</>
                ) : (
                  <><Brain className="w-4 h-4 mr-2" />Analyze</>
                )}
              </Button>
            )}
            
            {/* Re-analyze Button (for games missing strategic analysis) */}
            {analysis && !strategicAnalysis?.has_strategy && (
              <Button 
                onClick={handleReanalyze} 
                disabled={reanalyzing}
                variant="outline"
                size="sm"
                data-testid="reanalyze-header-btn"
              >
                {reanalyzing ? (
                  <><Loader2 className="w-4 h-4 animate-spin mr-2" />Re-analyzing...</>
                ) : (
                  <><RefreshCw className="w-4 h-4 mr-2" />Re-analyze</>
                )}
              </Button>
            )}
          </div>
        </div>

        {/* FOCUS MODE BANNER - Shows active behavioral focus */}
        {focusModule && coachMode && (
          <div className="px-4 py-2 bg-gradient-to-r from-amber-950/40 to-slate-900 border-b border-amber-500/20" data-testid="focus-mode-banner">
            <div className="flex items-center justify-between max-w-6xl mx-auto">
              <div className="flex items-center gap-3">
                <div className="p-1.5 bg-amber-500/20 rounded">
                  <Target className="w-4 h-4 text-amber-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-amber-400">
                    Active Focus: {focusModule.display_name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {focusModule.message || "Review your thinking process for this pattern."}
                  </p>
                </div>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                className="text-xs border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
                onClick={() => navigate("/training")}
                data-testid="view-training-module-btn"
              >
                View Training Module
              </Button>
            </div>
          </div>
        )}

        {/* MAIN CONTENT - Two Panel */}
        <div className="flex-1 flex overflow-hidden">
          {/* LEFT: BOARD */}
          <div className={`flex-1 p-4 overflow-auto ${rightPanelCollapsed ? 'max-w-3xl mx-auto' : ''}`}>
            <div className="flex flex-col items-center gap-4">
              {/* Board */}
              <div className="relative w-full max-w-[500px]">
                <Chessboard
                  position={positionObject}
                  boardOrientation={boardOrientation}
                  customSquareStyles={lastMoveSquares}
                  customArrows={customArrows}
                  arePiecesDraggable={false}
                  animationDuration={0}
                  customBoardStyle={{
                    borderRadius: '8px',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.2)'
                  }}
                />
              </div>
              
              {/* Variation Mode Banner */}
              {variationMode && (
                <div className="bg-emerald-500/20 border border-emerald-500/30 rounded-lg p-3 mb-2 animate-in slide-in-from-top-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Play className="w-4 h-4 text-emerald-500" />
                      <span className="text-sm font-medium text-emerald-400">
                        Viewing Better Line ({variationIndex}/{variationMoves.length} moves)
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-7 px-2 text-xs"
                        onClick={variationBack}
                        disabled={variationIndex <= 0}
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </Button>
                      <Button 
                        variant="default" 
                        size="sm" 
                        className="h-7 px-3 text-xs bg-emerald-600 hover:bg-emerald-700"
                        onClick={variationNext}
                        disabled={variationIndex >= variationMoves.length}
                        data-testid="variation-next-btn"
                      >
                        Next Move
                        <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="h-7 px-2 text-xs"
                        onClick={exitVariation}
                        data-testid="variation-exit-btn"
                      >
                        Exit
                      </Button>
                    </div>
                  </div>
                  {variationIndex > 0 && variationIndex <= variationMoves.length && (
                    <p className="text-xs text-emerald-400/80 mt-2">
                      Move played: <span className="font-mono font-bold">{variationMoves[variationIndex - 1]}</span>
                    </p>
                  )}
                </div>
              )}
              
              {/* Navigation */}
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" onClick={goToStart} disabled={currentMoveIndex < 0}>
                  <ChevronsLeft className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={goBack} disabled={currentMoveIndex < 0}>
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button variant="default" size="icon" onClick={togglePlay} disabled={moves.length === 0}>
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>
                <Button variant="outline" size="icon" onClick={goForward} disabled={currentMoveIndex >= moves.length - 1}>
                  <ChevronRight className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={goToEnd} disabled={currentMoveIndex >= moves.length - 1}>
                  <ChevronsRight className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={flipBoard}>
                  <RotateCcw className="w-4 h-4" />
                </Button>
                <Button 
                  variant={showOnlyCritical ? "default" : "outline"} 
                  size="sm"
                  onClick={() => setShowOnlyCritical(!showOnlyCritical)}
                  className={`ml-2 gap-1.5 ${showOnlyCritical ? 'bg-red-500 hover:bg-red-600 text-white' : ''}`}
                  data-testid="critical-toggle"
                >
                  {showOnlyCritical ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  {showOnlyCritical ? `Critical (${criticalMoves.length})` : 'Critical Only'}
                </Button>
              </div>
              
              {/* Move List */}
              <div className="w-full max-w-[500px] bg-muted/30 rounded-lg p-3 max-h-48 overflow-y-auto">
                {showOnlyCritical && criticalMoves.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No critical moves in this game - great job!
                  </p>
                )}
                <div className="grid grid-cols-[auto_1fr_1fr] gap-x-3 gap-y-1 text-sm font-mono">
                  {movePairs.map((p) => {
                    // Filter if showing only critical
                    if (showOnlyCritical && !p.wIsCritical && !p.bIsCritical) {
                      return null;
                    }
                    return (
                      <div key={p.num} className="contents">
                        <span className="text-muted-foreground">{p.num}.</span>
                        <button
                          className={`text-left px-1.5 py-0.5 rounded transition-colors ${
                            currentMoveIndex === p.wIdx ? "bg-primary/30 font-bold" : "hover:bg-muted"
                          } ${p.wIsCritical ? "text-red-500" : ""} ${
                            Math.abs(p.wCpLoss) >= 300 ? "border-l-2 border-red-500" :
                            Math.abs(p.wCpLoss) >= 100 ? "border-l-2 border-orange-500" : ""
                          }`}
                          onClick={() => goToMove(p.wIdx)}
                        >
                          {p.white}
                        </button>
                        <button
                          className={`text-left px-1.5 py-0.5 rounded transition-colors ${
                            currentMoveIndex === p.bIdx ? "bg-primary/30 font-bold" : "hover:bg-muted"
                          } ${p.bIsCritical ? "text-red-500" : ""} ${
                            Math.abs(p.bCpLoss) >= 300 ? "border-l-2 border-red-500" :
                            Math.abs(p.bCpLoss) >= 100 ? "border-l-2 border-orange-500" : ""
                          }`}
                          onClick={() => p.black && goToMove(p.bIdx)}
                          disabled={!p.black}
                        >
                          {p.black}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: TABS */}
          {!rightPanelCollapsed && (
            <div className="w-[400px] lg:w-[450px] border-l border-border/50 flex flex-col overflow-hidden">
              {analysis ? (
                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
                  <TabsList className="grid w-full grid-cols-3 rounded-none border-b shrink-0">
                    <TabsTrigger value="summary">Summary</TabsTrigger>
                    <TabsTrigger value="strategy">Strategy</TabsTrigger>
                    <TabsTrigger value="milestones" className="relative">
                      Milestones
                      {(groupedMilestones.find(g => g.type === 'brilliant_moves')?.count || 0) > 0 && (
                        <span className="absolute -top-1 -right-1 w-4 h-4 bg-amber-500 text-white text-[10px] rounded-full flex items-center justify-center">
                          {groupedMilestones.find(g => g.type === 'brilliant_moves')?.count || 0}
                        </span>
                      )}
                    </TabsTrigger>
                  </TabsList>
                  
                  <div className="flex-1 min-h-0 overflow-hidden">
                    <ScrollArea className="h-full">
                    {/* SUMMARY TAB - Redesigned: Max 3 lessons, clean structure */}
                    <TabsContent value="summary" className="p-4 space-y-4 m-0">
                      
                      {/* 💬 COACHING INTRO - Personal, conversational opener */}
                      {result && (
                        <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/30" data-testid="coaching-intro">
                          <p className="text-sm leading-relaxed">
                            {(() => {
                              const isLoss = result === "0-1" && userColor === "white" || result === "1-0" && userColor === "black";
                              const isWin = result === "1-0" && userColor === "white" || result === "0-1" && userColor === "black";
                              const blunderCount = labData?.blunders || analysis?.stockfish_analysis?.blunders || 0;
                              const mainLesson = coreLesson?.lesson || "";
                              
                              // Check if this game's issue matches user's recurring pattern
                              const matchesRecurringPattern = userPatterns?.has_pattern && 
                                (mainLesson.toLowerCase().includes("undefended") || 
                                 mainLesson.toLowerCase().includes("threat") ||
                                 userPatterns.dominant_pattern === "missed_threat");
                              
                              if (isLoss && blunderCount >= 2) {
                                return matchesRecurringPattern 
                                  ? `Tough game. But here's the thing — this is the same pattern we've seen before. You've ${userPatterns.pattern_description.toLowerCase()} ${userPatterns.pattern_count} times recently. Let's fix this once and for all.`
                                  : `Tough loss. ${blunderCount} key moments went wrong, but there's a clear pattern here. Let's understand exactly what happened.`;
                              } else if (isLoss) {
                                return matchesRecurringPattern
                                  ? `Close game, but the same issue showed up again. You've ${userPatterns.pattern_description.toLowerCase()} ${userPatterns.pattern_count} times this week. Today we break that cycle.`
                                  : "Close game. One moment changed everything. Let's see what we can learn from it.";
                              } else if (isWin && blunderCount > 0) {
                                return `Good win, but you got away with ${blunderCount === 1 ? "one" : "a few"} shaky moment${blunderCount !== 1 ? "s" : ""}. Let's make sure these don't cost you next time.`;
                              } else if (isWin) {
                                return "Solid game. Let's see what made this one work so you can repeat it.";
                              }
                              return "Let's break down what happened in this game.";
                            })()}
                          </p>
                        </div>
                      )}
                      
                      {/* Clean Game State */}
                      {coreLesson?.pattern === "clean_game" ? (
                        <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="w-5 h-5 text-green-500" />
                            <p className="font-bold text-green-500">Clean Game!</p>
                          </div>
                          <p className="text-sm">{coreLesson.lesson}</p>
                        </div>
                      ) : (
                        <>
                          {/* ⭐ MAIN LESSON - Full coaching structure */}
                          <LessonCard
                            lesson={{
                              concept: coreLesson?.lesson || moduleTrigger?.module_name || "Analyzing...",
                              module_key: moduleTrigger?.module_key || coreLesson?.pattern,
                              move_number: biggestEvalSwing?.move_number,
                              move_san: biggestEvalSwing?.move,
                              your_move: biggestEvalSwing?.move,
                              better_move: biggestEvalSwing?.best_move,
                              description: (() => {
                                // Build game-specific "what happened" explanation
                                if (moduleTrigger?.explanation) return moduleTrigger.explanation;
                                if (coreLesson?.context) return coreLesson.context;
                                if (biggestEvalSwing) {
                                  const cpLoss = Math.abs(biggestEvalSwing.cp_loss || 0);
                                  if (cpLoss >= 300) return `This move lost ${(cpLoss / 100).toFixed(1)} pawns of advantage.`;
                                  if (cpLoss >= 150) return `This inaccuracy shifted the game's balance.`;
                                }
                                return null;
                              })(),
                              better_idea: (() => {
                                // Build "what should have happened" from best move context
                                if (biggestEvalSwing?.best_move) {
                                  const bestMove = biggestEvalSwing.best_move;
                                  // Try to give context based on piece type
                                  if (bestMove.startsWith('O-O')) return 'Castle to secure your king.';
                                  if (bestMove.startsWith('R')) return `Activate the rook with ${bestMove}.`;
                                  if (bestMove.startsWith('N')) return `Improve the knight with ${bestMove}.`;
                                  if (bestMove.startsWith('B')) return `Develop the bishop with ${bestMove}.`;
                                  return `The better continuation was ${bestMove}.`;
                                }
                                return null;
                              })(),
                              rule: moduleTrigger?.rule || coreLesson?.behavioral_fix
                            }}
                            variant="main"
                            onMoveClick={(moveNum) => {
                              const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                              goToMove(targetIdx);
                            }}
                            onSeeStrategy={() => setActiveTab('strategy')}
                          />
                          
                          {/* 🌿 ALTERNATE TIMELINE - What if you played the better move? */}
                          {biggestEvalSwing?.pv_after_best?.length > 0 && (
                            <AlternateTimeline
                              fen={biggestEvalSwing.fen_before}
                              yourMove={biggestEvalSwing.move}
                              betterMove={biggestEvalSwing.best_move}
                              pvAfterBest={biggestEvalSwing.pv_after_best}
                              cpLoss={biggestEvalSwing.cp_loss}
                              userColor={userColor}
                              onPractice={(practiceFen, firstMove) => {
                                // Navigate to coach play with this position
                                // Store position in sessionStorage for CoachPlay to pick up
                                const practiceData = {
                                  fen: practiceFen,
                                  firstMove: firstMove,
                                  userColor: userColor,
                                  source: 'alternate_timeline',
                                  gameId: gameId
                                };
                                sessionStorage.setItem('practice_position', JSON.stringify(practiceData));
                                navigate('/play-with-coach?mode=practice');
                              }}
                            />
                          )}
                          
                          {/* 📘 SUPPORTING LESSONS - From other moments (max 2) */}
                          {labData?.additional_lessons?.slice(0, 2).map((lesson, idx) => (
                            <LessonCard
                              key={idx}
                              lesson={{
                                ...lesson,
                                index: idx + 2
                              }}
                              variant="supporting"
                              onMoveClick={(moveNum) => {
                                const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                                goToMove(targetIdx);
                              }}
                            />
                          ))}
                          
                          {/* 📚 WISDOM-BASED LESSONS - From teaching engine */}
                          {wisdomLessons.length > 0 && (
                            <div className="space-y-3">
                              <p className="text-xs text-muted-foreground uppercase tracking-wide">Chess Principles Applied</p>
                              {wisdomLessons.map((lesson, idx) => (
                                <div key={idx} className="p-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
                                  <div className="flex items-center gap-2 mb-2">
                                    <Lightbulb className="w-3.5 h-3.5 text-violet-400" />
                                    <button
                                      onClick={() => {
                                        const targetIdx = (lesson.move_number - 1) * 2 + (userColor === 'black' ? 1 : 0);
                                        goToMove(targetIdx);
                                      }}
                                      className="text-xs text-violet-400 hover:text-violet-300"
                                    >
                                      Move {lesson.move_number}: {lesson.your_move} → {lesson.better_move}
                                    </button>
                                    <span className="text-xs text-red-400 ml-auto">{lesson.delta_cp} cp</span>
                                  </div>
                                  <p className="text-sm text-muted-foreground mb-2">{lesson.concept}</p>
                                  <p className="text-xs text-violet-300 italic">"{lesson.rule}"</p>
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                      
                      {/* ⚠ COACH NOTICE - Pattern Reminder */}
                      <CoachNotice
                        pattern={coreLesson?.pattern || moduleTrigger?.module_key}
                        similarGames={labData?.similar_games || []}
                      />
                      
                      {/* 🔒 FOCUS LOCK STATUS */}
                      <FocusLockStatus lock={focusLock} />
                      
                      {/* 💪 ENCOURAGEMENT - End on a positive note */}
                      {coreLesson?.pattern !== "clean_game" && (
                        <div className="p-3 rounded-lg bg-primary/5 border border-primary/20" data-testid="encouragement">
                          <p className="text-sm text-primary/90">
                            {(() => {
                              const isLoss = result === "0-1" && userColor === "white" || result === "1-0" && userColor === "black";
                              const mainLesson = coreLesson?.behavioral_fix || coreLesson?.lesson || "";
                              
                              // Specific, actionable encouragement
                              if (mainLesson.toLowerCase().includes("safe") || mainLesson.toLowerCase().includes("piece")) {
                                return "One habit change: after every move, scan for hanging pieces. Do this for 10 games and watch your wins climb.";
                              }
                              if (mainLesson.toLowerCase().includes("threat") || mainLesson.toLowerCase().includes("opponent")) {
                                return "Before your next game, try this: pause 3 seconds before each move and ask 'what can they do to me?' That's it.";
                              }
                              if (mainLesson.toLowerCase().includes("castle") || mainLesson.toLowerCase().includes("king")) {
                                return "Your next game goal: castle by move 10. That simple rule will save you from many problems.";
                              }
                              if (isLoss) {
                                return "Fix this ONE pattern and you'll start winning games like this. You've got this.";
                              }
                              return "Small improvements compound. Keep playing, keep learning.";
                            })()}
                          </p>
                        </div>
                      )}
                      
                      {/* 📖 COACH FULL REVIEW - Collapsed by default */}
                      {coachCommentary && (
                        <details className="group">
                          <summary className="flex items-center gap-2 cursor-pointer text-sm text-muted-foreground hover:text-foreground py-2">
                            <Sparkles className="w-3 h-3" />
                            <span>Coach Full Review</span>
                            <ChevronDown className="w-3 h-3 group-open:rotate-180 transition-transform ml-auto" />
                          </summary>
                          <div className="mt-2 p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
                            <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">
                              {coachCommentary}
                            </p>
                          </div>
                        </details>
                      )}
                    </TabsContent>

                    {/* STRATEGY TAB - Position-specific insights from deep analysis */}
                    <TabsContent value="strategy" className="p-4 space-y-4 m-0">
                      {loadingDeepStrategy ? (
                        <div className="flex items-center justify-center py-8">
                          <Loader2 className="w-6 h-6 animate-spin text-primary" />
                          <span className="ml-2 text-sm text-muted-foreground">Analyzing position strategy...</span>
                        </div>
                      ) : deepStrategy?.critical_moments?.length > 0 ? (
                        <div className="space-y-4">
                          {/* Header */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <GraduationCap className="w-5 h-5 text-violet-400" />
                              <h3 className="font-semibold text-white">What You Missed</h3>
                            </div>
                            <Badge variant="outline" className="text-xs">
                              {deepStrategy.total_mistakes} critical moments
                            </Badge>
                          </div>
                          
                          {/* Each critical moment with position-specific insight */}
                          {deepStrategy.critical_moments.map((moment, idx) => {
                            const insight = moment.insight || {};
                            
                            return (
                              <div 
                                key={idx}
                                className="p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 space-y-3"
                                data-testid={`critical-moment-${idx}`}
                              >
                                {/* Move header */}
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <Badge className={idx === 0 ? "bg-red-500" : "bg-amber-500"}>
                                      Move {moment.move_number}
                                    </Badge>
                                    <span className="text-sm text-red-400">
                                      -{Math.abs(moment.cp_loss / 100).toFixed(1)} pawns
                                    </span>
                                  </div>
                                  <button
                                    onClick={() => {
                                      const moveNum = moment.move_number;
                                      if (moveNum) {
                                        const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                                        goToMove(targetIdx);
                                      }
                                    }}
                                    className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                                    data-testid={`see-position-${idx}`}
                                  >
                                    <Play className="w-3 h-3" />
                                    See on board
                                  </button>
                                </div>
                                
                                {/* Your move vs Best move */}
                                <div className="flex items-center gap-4 text-sm">
                                  <div>
                                    <span className="text-muted-foreground">You played: </span>
                                    <span className="text-red-400 font-medium">{moment.your_move}</span>
                                  </div>
                                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                                  <div>
                                    <span className="text-muted-foreground">Best was: </span>
                                    <span className="text-green-400 font-medium">{moment.best_move}</span>
                                  </div>
                                </div>
                                
                                {/* WHAT YOU MISSED - The key insight */}
                                {insight.what_you_missed && (
                                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                                    <p className="text-xs text-amber-400 font-medium mb-1 flex items-center gap-1">
                                      <Eye className="w-3 h-3" />
                                      WHAT YOU DIDN'T SEE
                                    </p>
                                    <p className="text-sm text-amber-300">
                                      {insight.what_you_missed}
                                    </p>
                                  </div>
                                )}
                                
                                {/* WHAT BEST MOVE ACHIEVES */}
                                {insight.what_best_move_achieves && (
                                  <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                                    <p className="text-xs text-green-400 font-medium mb-1 flex items-center gap-1">
                                      <Zap className="w-3 h-3" />
                                      WHAT {moment.best_move} ACHIEVES
                                    </p>
                                    <p className="text-sm text-green-300">
                                      {insight.what_best_move_achieves}
                                    </p>
                                  </div>
                                )}
                                
                                {/* WHY YOUR MOVE WAS WRONG */}
                                {insight.why_your_move_was_wrong && (
                                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                                    <p className="text-xs text-red-400 font-medium mb-1">
                                      WHY {moment.your_move} WAS WRONG
                                    </p>
                                    <p className="text-sm text-red-300">
                                      {insight.why_your_move_was_wrong}
                                    </p>
                                  </div>
                                )}
                                
                                {/* THE PATTERN TO RECOGNIZE */}
                                {(insight.the_idea_you_should_learn || insight.how_to_spot_this) && (
                                  <div className="p-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
                                    <p className="text-xs text-violet-400 font-medium mb-1 flex items-center gap-1">
                                      <Lightbulb className="w-3 h-3" />
                                      PATTERN TO RECOGNIZE
                                    </p>
                                    {insight.the_idea_you_should_learn && (
                                      <p className="text-sm text-violet-300 mb-2">
                                        {insight.the_idea_you_should_learn}
                                      </p>
                                    )}
                                    {insight.how_to_spot_this && (
                                      <p className="text-sm text-violet-200 italic">
                                        💡 {insight.how_to_spot_this}
                                      </p>
                                    )}
                                  </div>
                                )}
                                
                                {/* LLM COACH EXPLANATION (if available) */}
                                {moment.coach_explanation && (
                                  <div className="p-3 rounded-lg bg-primary/10 border border-primary/20">
                                    <p className="text-xs text-primary font-medium mb-1 flex items-center gap-1">
                                      <Brain className="w-3 h-3" />
                                      COACH EXPLANATION
                                    </p>
                                    <p className="text-sm text-white/90">
                                      {moment.coach_explanation}
                                    </p>
                                  </div>
                                )}
                                
                                {/* Continuation line */}
                                {moment.pv_after_best?.length > 0 && (
                                  <div className="pt-2 border-t border-slate-700/30">
                                    <p className="text-xs text-muted-foreground">
                                      After {moment.best_move}: {moment.pv_after_best.join(" → ")}
                                    </p>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                          
                          {/* Overall lesson from the game */}
                          {deepStrategy.lesson?.main_strategic_theme && (
                            <div className="p-4 rounded-lg bg-gradient-to-br from-violet-900/30 to-slate-900/50 border border-violet-500/20">
                              <div className="flex items-center gap-2 mb-2">
                                <BookOpen className="w-4 h-4 text-violet-400" />
                                <p className="text-sm font-medium text-violet-400">
                                  Main Theme: {deepStrategy.lesson.main_strategic_theme}
                                </p>
                              </div>
                              <p className="text-sm text-muted-foreground">
                                Practice spotting these patterns by scanning for undefended pieces before every move.
                              </p>
                            </div>
                          )}
                          
                          {/* Link to Milestones */}
                          <button
                            onClick={() => setActiveTab('milestones')}
                            className="w-full p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/50 transition-colors flex items-center justify-center gap-2 text-sm text-violet-400 hover:text-violet-300"
                            data-testid="strategy-to-milestones"
                          >
                            <Lightbulb className="w-4 h-4" />
                            See all learning moments
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      ) : strategicAnalysis?.has_strategy ? (
                        <div className="space-y-4">
                          {/* Abandoned game notice - coach acknowledges incomplete game */}
                          {(game?.termination?.toLowerCase().includes('abandoned') || 
                            game?.termination_text?.toLowerCase().includes('abandoned') ||
                            game?.termination_text?.toLowerCase().includes('disconnection')) && (
                            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                              <p className="text-sm text-amber-400">
                                This game ended by disconnection, so the final position doesn't tell the whole story. 
                                Focus on the opening decisions instead.
                              </p>
                            </div>
                          )}
                          
                          {/* THE STRATEGIC LESSON - Main learning from this game */}
                          {(() => {
                            const themes = strategicAnalysis.strategic_themes || [];
                            const primaryTheme = themes[0]; // First theme is most relevant
                            
                            if (!primaryTheme) return null;
                            
                            return (
                              <div className="p-4 rounded-lg bg-gradient-to-br from-violet-900/30 to-slate-900/50 border border-violet-500/20">
                                <div className="flex items-start gap-3 mb-3">
                                  <div className="p-2 rounded-lg bg-violet-500/20">
                                    <GraduationCap className="w-5 h-5 text-violet-400" />
                                  </div>
                                  <div>
                                    <p className="text-xs text-violet-400 uppercase tracking-wide font-medium">Today's Lesson</p>
                                    <h3 className="text-lg font-semibold text-white">{primaryTheme.theme}</h3>
                                  </div>
                                </div>
                                
                                <p className="text-sm text-muted-foreground mb-4">
                                  {primaryTheme.description}
                                </p>
                                
                                {/* The Theory - What you should know */}
                                <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/30 mb-3">
                                  <p className="text-xs text-amber-400 font-medium mb-2 flex items-center gap-1">
                                    <BookOpen className="w-3 h-3" />
                                    THEORY
                                  </p>
                                  <p className="text-sm text-white">
                                    {primaryTheme.principle}
                                  </p>
                                </div>
                                
                                {/* The Rule to Remember */}
                                {primaryTheme.remember && (
                                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                                    <p className="text-xs text-amber-400 font-medium mb-1 flex items-center gap-1">
                                      <Lightbulb className="w-3 h-3" />
                                      RULE TO REMEMBER
                                    </p>
                                    <p className="text-sm text-amber-300 italic">
                                      "{primaryTheme.remember}"
                                    </p>
                                  </div>
                                )}
                                
                                {/* Verdict */}
                                {primaryTheme.verdict && (
                                  <div className={`mt-3 p-2 rounded-lg text-sm ${
                                    primaryTheme.verdict.includes('✔') || primaryTheme.verdict.includes('✓')
                                      ? 'bg-green-500/10 text-green-400'
                                      : 'bg-red-500/10 text-red-400'
                                  }`}>
                                    {primaryTheme.verdict}
                                  </div>
                                )}
                              </div>
                            );
                          })()}
                          
                          {/* CRITICAL POSITION - The key moment with board link */}
                          {(() => {
                            const themes = strategicAnalysis.strategic_themes || [];
                            const criticalMoment = themes[0]?.critical_moment || 
                                                   strategicAnalysis.pawn_structure?.execution?.critical_moment;
                            
                            if (!criticalMoment) return null;
                            
                            return (
                              <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
                                <div className="flex items-center justify-between mb-3">
                                  <div className="flex items-center gap-2">
                                    <Target className="w-4 h-4 text-red-400" />
                                    <p className="text-xs text-red-400 uppercase tracking-wide font-medium">Critical Position</p>
                                  </div>
                                  <Badge variant="outline" className="text-xs">Move {criticalMoment.move_number}</Badge>
                                </div>
                                
                                <p className="text-sm text-muted-foreground mb-3">
                                  {criticalMoment.description}
                                </p>
                                
                                {criticalMoment.impact && (
                                  <p className="text-sm text-red-400 mb-3">
                                    {criticalMoment.impact}
                                  </p>
                                )}
                                
                                <button 
                                  className="w-full p-3 rounded bg-slate-700/30 hover:bg-slate-700/50 transition-colors text-left flex items-center justify-between group"
                                  onClick={() => {
                                    const moveNum = criticalMoment.move_number;
                                    if (moveNum) {
                                      const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                                      goToMove(targetIdx);
                                    }
                                  }}
                                  data-testid="critical-position-btn"
                                >
                                  <div>
                                    <p className="text-sm text-white font-medium">
                                      You played: <span className="text-red-400">{criticalMoment.your_move}</span>
                                    </p>
                                    {criticalMoment.what_went_wrong && (
                                      <p className="text-xs text-muted-foreground mt-1">
                                        {criticalMoment.what_went_wrong}
                                      </p>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-1 text-xs text-primary group-hover:text-primary/80">
                                    <Play className="w-3 h-3" />
                                    See on board
                                  </div>
                                </button>
                              </div>
                            );
                          })()}
                          
                          {/* IMPROVEMENT PLAN - What to do differently next time */}
                          <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
                            <div className="flex items-center gap-2 mb-3">
                              <TrendingUp className="w-4 h-4 text-green-400" />
                              <p className="text-xs text-green-400 uppercase tracking-wide font-medium">Improvement Plan</p>
                            </div>
                            
                            <div className="space-y-3">
                              {(() => {
                                const themes = strategicAnalysis.strategic_themes || [];
                                const primaryTheme = themes[0];
                                const opening = strategicAnalysis.opening;
                                
                                const improvements = [];
                                
                                // Theme-specific improvement
                                if (primaryTheme?.theme?.includes('Converting')) {
                                  improvements.push({
                                    title: "When you're winning",
                                    action: "Trade pieces (not pawns), reduce counterplay, keep it simple."
                                  });
                                }
                                if (primaryTheme?.theme?.includes('Defensive')) {
                                  improvements.push({
                                    title: "When you're worse",
                                    action: "Create complications. Avoid trades. Make your opponent prove they can win."
                                  });
                                }
                                if (primaryTheme?.theme?.includes('Activity')) {
                                  improvements.push({
                                    title: "Before each move",
                                    action: "Ask: 'Which piece is my worst? How can I improve it?'"
                                  });
                                }
                                
                                // Opening-specific improvement
                                if (opening?.key_ideas?.length > 0) {
                                  improvements.push({
                                    title: "In similar positions",
                                    action: opening.key_ideas[0]
                                  });
                                }
                                
                                // Fallback
                                if (improvements.length === 0) {
                                  improvements.push({
                                    title: "Next time",
                                    action: "Pause on critical moves. Calculate one move deeper before committing."
                                  });
                                }
                                
                                return improvements.map((item, idx) => (
                                  <div key={idx} className="flex items-start gap-3">
                                    <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                                      <span className="text-xs text-green-400 font-medium">{idx + 1}</span>
                                    </div>
                                    <div>
                                      <p className="text-sm font-medium text-white">{item.title}</p>
                                      <p className="text-xs text-muted-foreground mt-0.5">{item.action}</p>
                                    </div>
                                  </div>
                                ));
                              })()}
                            </div>
                          </div>
                          
                          {/* OTHER LESSONS - Secondary themes from this game */}
                          {(() => {
                            const themes = strategicAnalysis.strategic_themes || [];
                            const otherThemes = themes.slice(1, 3); // Up to 2 more themes
                            
                            if (otherThemes.length === 0) return null;
                            
                            return (
                              <div className="p-4 rounded-lg bg-slate-800/30 border border-slate-700/30">
                                <p className="text-xs text-muted-foreground uppercase tracking-wide font-medium mb-3">
                                  Also relevant in this game
                                </p>
                                <div className="space-y-3">
                                  {otherThemes.map((theme, idx) => (
                                    <div key={idx} className="flex items-start gap-3">
                                      <BookOpen className="w-4 h-4 text-muted-foreground mt-0.5" />
                                      <div>
                                        <p className="text-sm text-white font-medium">{theme.theme}</p>
                                        <p className="text-xs text-muted-foreground">{theme.principle}</p>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}
                          
                          {/* Link to Milestones */}
                          <button
                            onClick={() => setActiveTab('milestones')}
                            className="w-full p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/50 transition-colors flex items-center justify-center gap-2 text-sm text-violet-400 hover:text-violet-300"
                            data-testid="strategy-to-milestones"
                          >
                            <Lightbulb className="w-4 h-4" />
                            See all learning moments
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="text-center py-8 text-muted-foreground">
                          <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-30" />
                          <p>Strategic analysis not available</p>
                          <p className="text-sm mt-2 mb-4">Re-analyze this game to see strategic insights.</p>
                          <Button 
                            onClick={handleReanalyze} 
                            disabled={reanalyzing}
                            variant="outline"
                            data-testid="reanalyze-strategy-btn"
                          >
                            {reanalyzing ? (
                              <><Loader2 className="w-4 h-4 animate-spin mr-2" />Analyzing...</>
                            ) : (
                              <><RefreshCw className="w-4 h-4 mr-2" />Re-analyze Game</>
                            )}
                          </Button>
                        </div>
                      )}
                    </TabsContent>

                    {/* MILESTONES TAB - Brilliant Moves & Learning Moments */}
                    <TabsContent value="milestones" className="p-4 space-y-4 m-0">
                      {/* MICRO-PROTOCOL CARD - Behavioral checklist */}
                      {focusModule && coachMode && (
                        <div className="p-3 rounded-lg border border-slate-700 bg-slate-900/50" data-testid="micro-protocol-card">
                          <div className="flex items-center gap-2 mb-3">
                            <ListChecks className="w-4 h-4 text-slate-400" />
                            <p className="text-sm font-medium text-slate-300">Decision Protocol</p>
                          </div>
                          <div className="space-y-2">
                            {(focusModule.category === "missed_forcing_move" ? [
                              "Check all forcing moves",
                              "Check opponent forcing replies",
                              "Confirm no hanging pieces"
                            ] : focusModule.category === "ignored_opponent_forcing" ? [
                              "Decide your candidate move",
                              "Ask: what's their best reply?",
                              "If dangerous, reconsider"
                            ] : focusModule.category === "phantom_threat_reaction" ? [
                              "Identify the 'threat'",
                              "Ask: what happens if I ignore it?",
                              "Only defend if truly forcing"
                            ] : focusModule.category === "advantage_mismanagement" ? [
                              "Recognize you're winning",
                              "Look for forcing continuations",
                              "Don't trade into a drawn endgame"
                            ] : [
                              "Analyze the position",
                              "Consider candidate moves",
                              "Verify your choice"
                            ]).map((step, idx) => (
                              <button
                                key={idx}
                                onClick={() => {
                                  const newChecks = [...protocolChecks];
                                  newChecks[idx] = !newChecks[idx];
                                  setProtocolChecks(newChecks);
                                }}
                                className="flex items-center gap-2 w-full text-left text-sm text-slate-400 hover:text-slate-300 transition-colors"
                                data-testid={`protocol-check-${idx}`}
                              >
                                {protocolChecks[idx] ? (
                                  <CheckSquare className="w-4 h-4 text-green-500 flex-shrink-0" />
                                ) : (
                                  <Square className="w-4 h-4 text-slate-600 flex-shrink-0" />
                                )}
                                <span className={protocolChecks[idx] ? "text-slate-500 line-through" : ""}>
                                  {step}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {displayedMilestones.length > 0 ? (
                        displayedMilestones.map((group) => (
                          <MilestoneGroup 
                            key={group.type}
                            group={group}
                            userColor={userColor}
                            gameId={gameId}
                            focusModule={focusModule}
                            onMoveClick={(moveNum) => {
                              const targetIdx = (moveNum - 1) * 2 + (userColor === 'black' ? 1 : 0);
                              goToMove(targetIdx);
                            }}
                            onPlayVariation={playVariation}
                            onShowPunishment={showPunishment}
                          />
                        ))
                      ) : (
                        <div className="text-center py-8">
                          <Sparkles className="w-12 h-12 mx-auto mb-4 text-amber-500/50" />
                          <p className="font-medium text-muted-foreground">No key moments identified</p>
                          <p className="text-sm text-muted-foreground">Analysis may still be processing</p>
                        </div>
                      )}
                    </TabsContent>
                    </ScrollArea>
                  </div>
                </Tabs>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center p-8">
                    <Brain className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
                    <p className="text-muted-foreground">Analyze the game to see insights</p>
                    <Button onClick={handleAnalyze} disabled={analyzing} className="mt-4">
                      {analyzing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                      Analyze Game
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Collapse toggle */}
          <button 
            className="absolute right-0 top-1/2 -translate-y-1/2 z-30 bg-muted hover:bg-muted/80 p-1 rounded-l"
            onClick={() => setRightPanelCollapsed(!rightPanelCollapsed)}
          >
            {rightPanelCollapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {/* PRACTICE MODE OVERLAY */}
        {practiceMode && (
          <PracticeModeOverlay 
            positions={practicePositions}
            currentIndex={practiceIndex}
            onNext={() => {
              if (practiceIndex < practicePositions.length - 1) {
                setPracticeIndex(i => i + 1);
              } else {
                // Will show summary screen inside component
                setPracticeIndex(i => i);
              }
            }}
            onClose={() => {
              setPracticeMode(false);
              setPracticeIndex(0);
            }}
            onComplete={(score) => {
              if (score.correct === score.total) {
                toast.success(`Perfect! ${score.correct}/${score.total} correct!`);
              } else {
                toast.info(`Practice complete: ${score.correct}/${score.total}`);
              }
            }}
            userColor={userColor}
          />
        )}
      </div>
    </Layout>
  );
};

const MilestoneGroup = ({ group, userColor, gameId, focusModule, onMoveClick, onPlayVariation, onShowPunishment }) => (
  <div className="space-y-2">
    <div className="flex items-center justify-between">
      <h3 className="font-medium flex items-center gap-2">
        {getMilestoneIcon(group.type)}
        {group.label}
      </h3>
      <Badge 
        variant="outline" 
        className={`text-xs ${group.positive ? 'border-amber-500/50 text-amber-400' : 'border-muted-foreground/50'}`}
      >
        {group.count}
      </Badge>
    </div>
    <div className="space-y-2">
      {group.items.map((item, idx) => (
        group.positive ? (
          <BrilliantMoveItem 
            key={idx} 
            move={item} 
            onClick={() => onMoveClick(item.move_number)}
          />
        ) : (
          <LearningMomentItem 
            key={idx} 
            mistake={item} 
            userColor={userColor}
            gameId={gameId}
            focusModule={focusModule}
            onClick={() => onMoveClick(item.move_number)}
            onPlayVariation={onPlayVariation}
            onShowPunishment={onShowPunishment}
          />
        )
      ))}
    </div>
  </div>
);

// Brilliant/Great Move Item - Positive, coach-like celebration
const BrilliantMoveItem = ({ move, onClick }) => {
  const isBrilliant = move.isBrilliant;
  
  return (
    <button
      className={`w-full text-left p-3 rounded-lg border-l-4 transition-all hover:bg-white/5 ${
        isBrilliant 
          ? 'border-l-amber-500 bg-gradient-to-r from-amber-500/10 to-transparent' 
          : 'border-l-green-500 bg-gradient-to-r from-green-500/10 to-transparent'
      }`}
      onClick={onClick}
      data-testid={`milestone-${move.move_number}`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          {isBrilliant ? (
            <Sparkles className="w-4 h-4 text-amber-500" />
          ) : (
            <Star className="w-4 h-4 text-green-500" />
          )}
          <span className="font-mono text-sm">Move {move.move_number}</span>
          <Badge 
            variant="outline" 
            className={`text-xs ${isBrilliant ? 'border-amber-500/50 text-amber-400' : 'border-green-500/50 text-green-400'}`}
          >
            {isBrilliant ? 'Brilliant!' : 'Great'}
          </Badge>
        </div>
        <span className="text-xs text-muted-foreground">{move.phase}</span>
      </div>
      
      <div className="flex items-center gap-2">
        <span className={`font-mono font-medium ${isBrilliant ? 'text-amber-400' : 'text-green-400'}`}>
          {move.move}
        </span>
      </div>
      
      <p className={`text-xs mt-1 ${isBrilliant ? 'text-amber-400/80' : 'text-green-400/80'}`}>
        {move.context}
      </p>
    </button>
  );
};

// Learning Moment Item - Constructive, coach-like feedback
const LearningMomentItem = ({ mistake, onClick, userColor, gameId, focusModule, onPlayVariation, onShowPunishment }) => {
  const cpLossInfo = formatCpLoss(mistake.cp_loss);
  const [expanded, setExpanded] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // "What were you thinking?" state
  const [thoughtText, setThoughtText] = useState("");
  const [thoughtSaved, setThoughtSaved] = useState(false);
  const [savingThought, setSavingThought] = useState(false);
  const [showThoughtInput, setShowThoughtInput] = useState(false);
  
  // Load existing thought on mount
  useEffect(() => {
    const loadExistingThought = async () => {
      if (!gameId) return;
      try {
        const response = await fetch(`${API}/games/${gameId}/thoughts`, { credentials: "include" });
        if (response.ok) {
          const data = await response.json();
          const existingThought = data.thoughts?.find(t => t.move_number === mistake.move_number);
          if (existingThought) {
            setThoughtText(existingThought.thought_text);
            setThoughtSaved(true);
          }
        }
      } catch (err) {
        // Silent fail - not critical
      }
    };
    loadExistingThought();
  }, [gameId, mistake.move_number]);
  
  // Save user thought
  const handleSaveThought = async () => {
    if (!thoughtText.trim() || !gameId) return;
    
    setSavingThought(true);
    try {
      const response = await fetch(`${API}/games/${gameId}/thought`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          move_number: mistake.move_number,
          fen: mistake.fen_before || "",
          thought_text: thoughtText.trim()
        })
      });
      
      if (response.ok) {
        setThoughtSaved(true);
        setShowThoughtInput(false);
        toast.success("Thanks! This helps improve your coaching.");
      } else {
        toast.error("Could not save thought");
      }
    } catch (err) {
      toast.error("Could not save thought");
    } finally {
      setSavingThought(false);
    }
  };
  
  // Fetch explanation on-demand when expanded
  const handleExpand = async (e) => {
    e.stopPropagation();
    
    if (expanded) {
      setExpanded(false);
      return;
    }
    
    setExpanded(true);
    
    // Don't fetch if we already have it
    if (explanation) return;
    
    // Need fen_before to analyze
    if (!mistake.fen_before) {
      setExplanation({
        explanation: "Position data not available for analysis.",
        mistake_type: "unknown",
        short_label: "Unknown"
      });
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API}/explain-mistake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          fen_before: mistake.fen_before,
          move: mistake.move,
          best_move: mistake.best_move,
          cp_loss: mistake.cp_loss,
          user_color: userColor,
          move_number: mistake.move_number
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        setExplanation(data);
      } else {
        setExplanation({
          explanation: "Could not generate explanation. Try re-analyzing the game.",
          mistake_type: "error",
          short_label: "Error"
        });
      }
    } catch (err) {
      console.error("Explanation fetch error:", err);
      setExplanation({
        explanation: "Could not generate explanation.",
        mistake_type: "error",
        short_label: "Error"
      });
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div
      className={`w-full text-left rounded-lg border-l-4 transition-all ${
        mistake.isBlunder ? 'border-l-red-500 bg-red-500/5' :
        mistake.isMistake ? 'border-l-orange-500 bg-orange-500/5' :
        mistake.isPhantomThreat ? 'border-l-purple-500 bg-purple-500/5' :
        mistake.isEnginePreference ? 'border-l-gray-500 bg-gray-500/5' :
        'border-l-yellow-500 bg-yellow-500/5'
      }`}
      data-testid={`mistake-${mistake.move_number}`}
    >
      {/* Clickable header - goes to position */}
      <button
        className="w-full text-left p-2 hover:bg-white/5 transition-colors"
        onClick={onClick}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">Move {mistake.move_number}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${cpLossInfo.className} bg-current/10`}>
              {cpLossInfo.text}
            </span>
          </div>
          <span className="text-xs text-muted-foreground">{mistake.phase}</span>
        </div>
        
        <div className="flex items-center gap-2 mt-1">
          <span className="text-sm">
            <span className="text-muted-foreground">Played:</span>{' '}
            <span className="font-mono text-red-400">{mistake.move}</span>
          </span>
          <span className="text-muted-foreground">→</span>
          <span className="text-sm">
            <span className="text-muted-foreground">Better:</span>{' '}
            <span className="font-mono text-green-400">{mistake.best_move}</span>
          </span>
        </div>
      </button>
      
      {/* Expandable explanation section */}
      <button
        className="w-full px-2 py-1.5 flex items-center justify-between text-xs border-t border-border/30 hover:bg-white/5 transition-colors"
        onClick={handleExpand}
        data-testid={`explain-btn-${mistake.move_number}`}
      >
        <span className="flex items-center gap-1.5 text-primary">
          <Lightbulb className="w-3.5 h-3.5" />
          What can I learn here?
        </span>
        {loading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
        ) : (
          expanded ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
        )}
      </button>
      
      {/* Explanation content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 animate-in slide-in-from-top-2 duration-200">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Analyzing position...
            </div>
          ) : explanation ? (
            <>
              {/* Focus context indicator - neural linking */}
              {focusModule && focusModule.category && (
                mistake.coachingCategory === focusModule.category ||
                (focusModule.category === "missed_forcing_move" && mistake.mistakeType?.includes("missed")) ||
                (focusModule.category === "ignored_opponent_forcing" && mistake.mistakeType?.includes("allowed"))
              ) && (
                <div className="flex items-center gap-1.5 text-xs text-amber-400 mb-2" data-testid="focus-context-indicator">
                  <Target className="w-3 h-3" />
                  <span>This relates to your current focus area.</span>
                </div>
              )}
              
              {/* Mistake type badge */}
              {explanation.short_label && (
                <div className="flex items-center gap-2">
                  <Badge 
                    variant="outline" 
                    className={`text-xs ${
                      explanation.severity === 'blunder' ? 'border-red-500/50 text-red-400' :
                      explanation.severity === 'mistake' ? 'border-orange-500/50 text-orange-400' :
                      'border-yellow-500/50 text-yellow-400'
                    }`}
                  >
                    {explanation.short_label}
                  </Badge>
                </div>
              )}
              
              {/* Main explanation */}
              <p className="text-sm leading-relaxed">
                {explanation.explanation}
              </p>
              
              {/* Thinking habit tip */}
              {explanation.thinking_habit && (
                <div className="p-2 rounded bg-primary/10 border border-primary/20">
                  <p className="text-xs text-primary flex items-start gap-1.5">
                    <Lightbulb className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    <span><strong>Tip:</strong> {explanation.thinking_habit}</span>
                  </p>
                </div>
              )}
              
              {/* Play the better line - Visual learning */}
              {mistake.best_move && mistake.fen_before && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full h-8 text-xs gap-2 border-emerald-500/30 text-emerald-500 hover:bg-emerald-500/10"
                  onClick={() => onPlayVariation(mistake.fen_before, mistake.best_move, mistake.pv_after_best)}
                  data-testid={`play-variation-${mistake.move_number}`}
                >
                  <Play className="w-3.5 h-3.5" />
                  Play the better line on board
                </Button>
              )}
              
              {/* Show Punishment - Opponent's best response to your bad move */}
              {mistake.pv_after_played && mistake.pv_after_played.length > 0 && mistake.fen_before && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full h-8 text-xs gap-2 border-red-500/30 text-red-400 hover:bg-red-500/10"
                  onClick={() => onShowPunishment(mistake.fen_before, mistake.move, mistake.pv_after_played)}
                  data-testid={`show-punishment-${mistake.move_number}`}
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Show why it's bad (opponent's response)
                </Button>
              )}
              
              {/* "What were you thinking?" - Gold Data Collection */}
              <div className="mt-3 pt-2 border-t border-border/30" data-testid={`thought-section-${mistake.move_number}`}>
                {thoughtSaved ? (
                  <div className="flex items-center gap-2 text-xs text-emerald-500">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>You shared your thought on this move</span>
                  </div>
                ) : showThoughtInput ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Brain className="w-4 h-4 text-violet-500" />
                      <span className="text-sm font-medium text-violet-400">What were you thinking?</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Help us understand your thought process. This helps improve your coaching.
                    </p>
                    <textarea
                      value={thoughtText}
                      onChange={(e) => setThoughtText(e.target.value)}
                      placeholder="e.g., I was trying to attack... I missed the threat... I was running low on time..."
                      className="w-full p-2 text-sm rounded border border-violet-500/30 bg-background/50 resize-none focus:outline-none focus:ring-1 focus:ring-violet-500"
                      rows={3}
                      data-testid={`thought-input-${mistake.move_number}`}
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => setShowThoughtInput(false)}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        className="h-7 text-xs gap-1"
                        onClick={handleSaveThought}
                        disabled={savingThought || !thoughtText.trim()}
                        data-testid={`thought-save-${mistake.move_number}`}
                      >
                        {savingThought ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Send className="w-3 h-3" />
                        )}
                        Save
                      </Button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowThoughtInput(true)}
                    className="flex items-center gap-2 text-xs text-violet-500 hover:text-violet-400 transition-colors"
                    data-testid={`thought-prompt-${mistake.move_number}`}
                  >
                    <MessageCircle className="w-4 h-4" />
                    <span>What were you thinking here?</span>
                  </button>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground py-2">
              Click to load explanation
            </p>
          )}
        </div>
      )}
    </div>
  );
};

const PracticeModeOverlay = ({ positions, currentIndex, onNext, onClose, userColor, onComplete }) => {
  const [selectedMove, setSelectedMove] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState({ correct: 0, total: 0 });
  const [showSummary, setShowSummary] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const pos = positions[currentIndex];
  
  // Shuffle options so best move isn't always first
  const shuffledOptions = useMemo(() => {
    if (!pos) return [];
    const opts = [
      { move: pos.best_move, isBest: true },
      { move: pos.played_move, isBest: false, label: "(what you played)" }
    ];
    // Simple shuffle - sometimes show played move first
    return pos.move_number % 2 === 0 ? opts : opts.reverse();
  }, [pos]);
  
  const handleCheck = () => {
    const isCorrect = selectedMove === pos?.best_move;
    setScore(prev => ({
      correct: prev.correct + (isCorrect ? 1 : 0),
      total: prev.total + 1
    }));
    setShowResult(true);
  };
  
  const handleNext = () => {
    setShowResult(false);
    setSelectedMove(null);
    setShowHint(false);
    
    if (currentIndex >= positions.length - 1) {
      setShowSummary(true);
    } else {
      onNext();
    }
  };
  
  const handleRetry = () => {
    setShowResult(false);
    setSelectedMove(null);
    setShowHint(false);
  };
  
  const handleFinish = () => {
    if (onComplete) onComplete(score);
    onClose();
  };
  
  // Get eval context for hint
  const getEvalContext = () => {
    if (!pos?.eval_before) return "";
    const eval_val = pos.eval_before / 100;
    if (eval_val > 4) return "You were completely winning here.";
    if (eval_val > 2) return "You had a winning advantage.";
    if (eval_val > 0.5) return "You had a comfortable position.";
    if (eval_val > -0.5) return "The position was roughly equal.";
    return "You were under pressure here.";
  };
  
  // Summary screen
  if (showSummary) {
    const percentage = Math.round((score.correct / score.total) * 100);
    const isGood = percentage >= 60;
    
    return (
      <div className="fixed inset-0 z-50 bg-background/95 flex items-center justify-center p-4" data-testid="practice-summary">
        <div className="max-w-md w-full text-center space-y-6">
          <div className={`w-20 h-20 mx-auto rounded-full flex items-center justify-center ${isGood ? 'bg-green-500/20' : 'bg-amber-500/20'}`}>
            {isGood ? (
              <CheckCircle2 className="w-10 h-10 text-green-500" />
            ) : (
              <Target className="w-10 h-10 text-amber-500" />
            )}
          </div>
          
          <div>
            <h2 className="text-2xl font-bold mb-2">Practice Complete!</h2>
            <p className="text-4xl font-bold text-primary mb-2">{score.correct} / {score.total}</p>
            <p className="text-muted-foreground">
              {percentage >= 80 ? "Excellent! You found the best moves." :
               percentage >= 60 ? "Good job! Keep practicing these patterns." :
               percentage >= 40 ? "You're learning. Review these positions again." :
               "These positions need more study. Try again!"}
            </p>
          </div>
          
          <div className="flex gap-3 justify-center">
            <Button variant="outline" onClick={() => {
              setShowSummary(false);
              setScore({ correct: 0, total: 0 });
              onNext(); // Reset to first position
            }}>
              <RotateCcw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
            <Button onClick={handleFinish}>
              Done
            </Button>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="fixed inset-0 z-50 bg-background/95 flex items-center justify-center p-4" data-testid="practice-mode">
      <div className="max-w-3xl w-full space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Target className="w-5 h-5 text-primary" />
            Practice Critical Positions
          </h2>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-muted">
              <span className="text-sm font-medium text-green-500">{score.correct}</span>
              <span className="text-muted-foreground">/</span>
              <span className="text-sm">{score.total + (showResult ? 0 : 1)}</span>
            </div>
            <span className="text-sm text-muted-foreground">
              Position {currentIndex + 1} of {positions.length}
            </span>
            <Button variant="ghost" size="sm" onClick={onClose}>Exit</Button>
          </div>
        </div>
        
        {/* Progress bar */}
        <div className="h-1 bg-muted rounded-full overflow-hidden">
          <div 
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${((currentIndex + 1) / positions.length) * 100}%` }}
          />
        </div>
        
        <div className="flex gap-6">
          {/* Board */}
          <div className="w-[400px] shrink-0">
            <Chessboard
              position={pos?.fen || "start"}
              boardOrientation={userColor}
              arePiecesDraggable={false}
              customBoardStyle={{
                borderRadius: '8px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
              }}
            />
            
            {/* Context info below board */}
            <div className="mt-3 p-3 rounded-lg bg-muted/50 text-sm">
              <div className="flex items-center justify-between text-muted-foreground">
                <span>Move {pos?.move_number}</span>
                <span>Lost {((pos?.cp_loss || 0) / 100).toFixed(1)} pawns</span>
              </div>
            </div>
          </div>
          
          {/* Question panel */}
          <div className="flex-1 flex flex-col">
            <div className="flex-1">
              <p className="text-lg font-medium mb-2">What's the best move here?</p>
              
              {/* Hint */}
              {!showResult && (
                <button 
                  className="text-sm text-muted-foreground hover:text-primary mb-4 flex items-center gap-1"
                  onClick={() => setShowHint(!showHint)}
                >
                  <Lightbulb className="w-3 h-3" />
                  {showHint ? "Hide hint" : "Show hint"}
                </button>
              )}
              
              {showHint && !showResult && (
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 mb-4 text-sm">
                  <p className="text-amber-400">{getEvalContext()}</p>
                  <p className="text-muted-foreground mt-1">Think about what this position needs.</p>
                </div>
              )}
              
              {!showResult ? (
                <>
                  <div className="space-y-3 mb-6">
                    {shuffledOptions.map((opt, idx) => (
                      <Button
                        key={idx}
                        variant={selectedMove === opt.move ? "default" : "outline"}
                        className={`w-full justify-start font-mono text-lg h-14 ${
                          selectedMove === opt.move ? 'ring-2 ring-primary' : ''
                        }`}
                        onClick={() => setSelectedMove(opt.move)}
                        data-testid={`option-${idx}`}
                      >
                        {opt.move}
                        {opt.label && (
                          <span className="ml-auto text-xs text-muted-foreground font-sans">{opt.label}</span>
                        )}
                      </Button>
                    ))}
                  </div>
                  <Button 
                    onClick={handleCheck} 
                    disabled={!selectedMove}
                    className="w-full h-12"
                    data-testid="check-btn"
                  >
                    Check Answer
                  </Button>
                </>
              ) : (
                <div className={`p-5 rounded-lg ${selectedMove === pos?.best_move ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
                  {selectedMove === pos?.best_move ? (
                    <div className="flex items-center gap-2 text-green-500 mb-3">
                      <CheckCircle2 className="w-6 h-6" />
                      <span className="text-xl font-bold">Correct!</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-red-500 mb-3">
                      <AlertTriangle className="w-6 h-6" />
                      <span className="text-xl font-bold">Not quite</span>
                    </div>
                  )}
                  
                  <div className="space-y-2 mb-4">
                    <p className="text-sm">
                      <span className="text-muted-foreground">Best move:</span>{' '}
                      <span className="font-mono text-green-400 text-lg">{pos?.best_move}</span>
                    </p>
                    <p className="text-sm">
                      <span className="text-muted-foreground">You played:</span>{' '}
                      <span className="font-mono text-red-400">{pos?.played_move}</span>
                      <span className="text-muted-foreground ml-2">(-{((pos?.cp_loss || 0) / 100).toFixed(1)} pawns)</span>
                    </p>
                  </div>
                  
                  <div className="flex gap-3">
                    {selectedMove !== pos?.best_move && (
                      <Button variant="outline" onClick={handleRetry} data-testid="retry-btn">
                        <RotateCcw className="w-4 h-4 mr-2" />
                        Retry
                      </Button>
                    )}
                    <Button onClick={handleNext} className="flex-1" data-testid="next-btn">
                      {currentIndex < positions.length - 1 ? 'Next Position' : 'See Results'}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Utility functions
const getContextLabel = (move) => {
  const evalBefore = move.eval_before || 0;
  if (evalBefore > 2) return "After gaining advantage";
  if (evalBefore > 0.5) return "In a comfortable position";
  if (evalBefore < -2) return "Under pressure";
  return "";
};

const getPositiveContext = (move) => {
  const evalBefore = (move.eval_before || 0) / 100; // Convert cp to pawns
  const evalAfter = (move.eval_after || 0) / 100;
  const evalSwing = evalAfter - evalBefore;
  
  if (evalSwing > 2) return "Found a winning shot!";
  if (evalBefore < -1 && evalAfter > 0) return "Turned the game around!";
  if (evalBefore < -0.5 && move.cp_loss === 0) return "Held strong under pressure";
  if (Math.abs(evalBefore) < 0.5 && move.cp_loss <= 5) return "Maintained the balance";
  if (evalBefore > 1 && move.cp_loss <= 5) return "Kept the pressure";
  return "Solid choice";
};

const formatGroupLabel = (type) => {
  const labels = {
    blunders: "Major Blunders",
    hanging_pieces: "Hanging Pieces",
    tactical_misses: "Missed Tactics",
    positional_errors: "Positional Errors",
    other: "Other Mistakes"
  };
  return labels[type] || type;
};

const getMistakeIcon = (type) => {
  const icons = {
    blunders: <AlertTriangle className="w-4 h-4 text-red-500" />,
    hanging_pieces: <AlertCircle className="w-4 h-4 text-orange-500" />,
    tactical_misses: <Zap className="w-4 h-4 text-yellow-500" />,
    positional_errors: <Target className="w-4 h-4 text-blue-500" />,
    other: <AlertCircle className="w-4 h-4 text-muted-foreground" />
  };
  return icons[type] || icons.other;
};

const getMilestoneIcon = (type) => {
  const icons = {
    brilliant_moves: <Sparkles className="w-4 h-4 text-amber-500" />,
    great_moves: <Star className="w-4 h-4 text-green-500" />,
    learning_moments: <Lightbulb className="w-4 h-4 text-blue-500" />
  };
  return icons[type] || <Trophy className="w-4 h-4 text-muted-foreground" />;
};

const getThemeIcon = (iconName) => {
  const icons = {
    'trending-up': <TrendingUp className="w-4 h-4 text-green-500" />,
    'trending-down': <TrendingDown className="w-4 h-4 text-red-500" />,
    'shield': <Target className="w-4 h-4 text-blue-500" />,
    'target': <Target className="w-4 h-4 text-amber-500" />,
    'zap': <Zap className="w-4 h-4 text-yellow-500" />,
    'lightbulb': <Lightbulb className="w-4 h-4 text-amber-500" />,
    'book-open': <BookOpen className="w-4 h-4 text-green-500" />
  };
  return icons[iconName] || <Brain className="w-4 h-4 text-purple-500" />;
};

const getAdviceIcon = (iconName) => {
  const icons = {
    'book-open': <BookOpen className="w-4 h-4 text-green-500" />,
    'grid': <Target className="w-4 h-4 text-yellow-500" />,
    'lightbulb': <Lightbulb className="w-4 h-4 text-amber-500" />,
    'zap': <Zap className="w-4 h-4 text-purple-500" />,
    'trending-up': <TrendingUp className="w-4 h-4 text-green-500" />,
    'shield': <Target className="w-4 h-4 text-blue-500" />,
    'target': <Target className="w-4 h-4 text-amber-500" />
  };
  return icons[iconName] || <Lightbulb className="w-4 h-4 text-blue-500" />;
};

export default Lab;
