import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { API } from "@/App";
import CoachBoard from "@/components/CoachBoard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { toast } from "sonner";
import {
  Loader2,
  BookOpen,
  ChevronRight,
  ChevronDown,
  Play,
  Target,
  Trophy,
  AlertTriangle,
  Lightbulb,
  Swords,
  Crown,
  RotateCcw,
  CheckCircle2,
  XCircle,
  ChevronLeft,
  Layers,
  GraduationCap,
  Zap,
  Users,
  TrendingUp,
  TrendingDown,
  Minus,
  Shield,
  Eye,
  Flame,
} from "lucide-react";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Mastery level styling
const MASTERY_STYLES = {
  mastered: { bg: "bg-green-500/10", border: "border-green-500/30", text: "text-green-500", label: "Mastered" },
  comfortable: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-500", label: "Comfortable" },
  needs_work: { bg: "bg-orange-500/10", border: "border-orange-500/30", text: "text-orange-500", label: "Needs Work" },
  learning: { bg: "bg-gray-500/10", border: "border-gray-500/30", text: "text-gray-400", label: "Learning" },
};

/**
 * Opening Trainer Component
 * 
 * Features:
 * - Tree view of user's most-played openings
 * - Key variations and move orders
 * - Common traps (to set and avoid)
 * - Practice positions
 */
const OpeningTrainer = () => {
  // State
  const [loading, setLoading] = useState(true);
  const [userOpenings, setUserOpenings] = useState([]);
  const [allOpenings, setAllOpenings] = useState([]);
  const [selectedOpening, setSelectedOpening] = useState(null);
  const [openingContent, setOpeningContent] = useState(null);
  const [loadingContent, setLoadingContent] = useState(false);
  
  // Trick Library State
  const [tricks, setTricks] = useState([]);
  const [trickCategories, setTrickCategories] = useState([]);
  const [selectedTrick, setSelectedTrick] = useState(null);
  const [trickPracticeMode, setTrickPracticeMode] = useState(null); // execution | avoidance | recognition
  const [trickPracticeState, setTrickPracticeState] = useState("ready"); // ready | playing | success | failed
  const [trickPracticeData, setTrickPracticeData] = useState(null);
  const [trickMoveIndex, setTrickMoveIndex] = useState(0); // Current move in execution mode
  const [trickChess, setTrickChess] = useState(null); // Chess.js instance for execution mode
  const [avoidanceValidating, setAvoidanceValidating] = useState(false);
  const [recognitionAnswer, setRecognitionAnswer] = useState({ hasTrap: null, winningMove: "" });
  const [recognitionResult, setRecognitionResult] = useState(null);
  
  // Tree expansion state
  const [expandedNodes, setExpandedNodes] = useState({});
  
  // Practice mode state
  const [practiceMode, setPracticeMode] = useState(null); // null | "trap" | "variation"
  const [currentPracticeItem, setCurrentPracticeItem] = useState(null);
  const [practiceState, setPracticeState] = useState("ready"); // ready | playing | revealed
  const [moveIndex, setMoveIndex] = useState(0);
  
  // Board state
  const [boardFen, setBoardFen] = useState(START_FEN);
  const [boardOrientation, setBoardOrientation] = useState("white");
  const boardRef = useRef(null);

  // Fetch user's openings on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch user's openings, database, and tricks
        const [userRes, dbRes, tricksRes] = await Promise.all([
          fetch(`${API}/training/openings/stats`, { credentials: "include" }),
          fetch(`${API}/training/openings-database`, { credentials: "include" }),
          fetch(`${API}/training/tricks`, { credentials: "include" })
        ]);
        
        if (userRes.ok) {
          const data = await userRes.json();
          setUserOpenings(data.openings || []);
        }
        
        if (dbRes.ok) {
          const data = await dbRes.json();
          setAllOpenings(data.openings || []);
        }
        
        if (tricksRes.ok) {
          const data = await tricksRes.json();
          setTricks(data.traps || []);
          setTrickCategories(data.categories || {});
        }
      } catch (err) {
        console.error("Error fetching openings:", err);
        toast.error("Failed to load openings");
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);

  // Fetch opening content when selected
  const fetchOpeningContent = async (openingKey) => {
    try {
      setLoadingContent(true);
      
      // First try to get from our curated database
      const res = await fetch(`${API}/training/openings/${openingKey}`, { credentials: "include" });
      
      if (res.ok) {
        const data = await res.json();
        
        // If we have curated content, use it
        if (!data.error && data.opening) {
          // Also fetch Lichess stats to enrich the data
          const mainLine = data.opening?.main_line || [];
          if (mainLine.length > 0) {
            try {
              const lichessRes = await fetch(
                `${API}/training/lichess/opening?moves=${mainLine.join(",")}&source=lichess`,
                { credentials: "include" }
              );
              if (lichessRes.ok) {
                const lichessData = await lichessRes.json();
                data.lichess_stats = lichessData;
              }
            } catch (e) {
              console.log("Could not fetch Lichess stats:", e);
            }
          }
          
          setOpeningContent(data);
          
          if (mainLine.length > 0) {
            playMainLine(mainLine);
          }
          return;
        }
      }
      
      // If no curated content, try to fetch from Lichess by name
      const lichessRes = await fetch(
        `${API}/training/lichess/search?name=${encodeURIComponent(openingKey.replace(/_/g, " "))}`,
        { credentials: "include" }
      );
      
      if (lichessRes.ok) {
        const lichessData = await lichessRes.json();
        
        if (!lichessData.error) {
          // Transform Lichess data to our format
          const transformedData = {
            opening: lichessData.opening,
            variations: lichessData.top_moves?.map((move, idx) => ({
              name: `${move.san} (${move.games.toLocaleString()} games)`,
              moves: [...(lichessData.opening?.main_line || []), move.san],
              idea: `White wins: ${move.white_percent}% | Draws: ${move.draw_percent}% | Black wins: ${move.black_percent}%`,
              games: move.games
            })) || [],
            traps: [],
            key_ideas: [],
            lichess_stats: lichessData.statistics,
            from_lichess: true
          };
          
          setOpeningContent(transformedData);
          
          if (lichessData.opening?.main_line?.length > 0) {
            playMainLine(lichessData.opening.main_line);
          }
          return;
        }
      }
      
      // No data found
      setOpeningContent({
        opening: { name: openingKey.replace(/_/g, " "), main_line: [] },
        variations: [],
        traps: [],
        key_ideas: [],
        error: "No training content available for this opening yet."
      });
      
    } catch (err) {
      console.error("Error fetching opening content:", err);
      toast.error("Failed to load opening details");
    } finally {
      setLoadingContent(false);
    }
  };

  // Play through main line
  const playMainLine = (moves) => {
    const chess = new Chess();
    for (const move of moves) {
      try {
        chess.move(move, { sloppy: true });
      } catch (e) {
        break;
      }
    }
    setBoardFen(chess.fen());
    setBoardOrientation(chess.turn() === "w" ? "white" : "black");
  };

  // Toggle tree node expansion
  const toggleNode = (nodeId) => {
    setExpandedNodes(prev => ({
      ...prev,
      [nodeId]: !prev[nodeId]
    }));
  };

  // Handle trick selection
  const handleSelectTrick = async (trick) => {
    setSelectedTrick(trick);
    setSelectedOpening(null); // Clear opening selection
    setTrickPracticeMode(null);
    setTrickPracticeState("ready");
    setTrickPracticeData(null);
    
    // Set board to the trap position
    setBoardFen(trick.trap_position_fen || START_FEN);
    setBoardOrientation(trick.trap_for === "white" ? "white" : "black");
  };

  // Start trick practice mode
  const startTrickPractice = async (mode) => {
    if (!selectedTrick) return;
    
    try {
      const res = await fetch(
        `${API}/training/tricks/${selectedTrick.key}/practice?mode=${mode}`,
        { credentials: "include" }
      );
      
      if (res.ok) {
        const data = await res.json();
        setTrickPracticeMode(mode);
        setTrickPracticeState("playing");
        setTrickPracticeData(data);
        setTrickMoveIndex(0);
        
        if (mode === "execution") {
          // Start from the beginning with a fresh chess instance
          const chess = new Chess();
          setTrickChess(chess);
          setBoardFen(chess.fen());
          setBoardOrientation(data.user_color || selectedTrick.trap_for);
          
          // If the first move is engine's move, play it automatically
          const firstEngineMove = data.engine_moves?.find(m => m.index === 0);
          if (firstEngineMove) {
            setTimeout(() => {
              playEngineMove(chess, firstEngineMove.move, data);
            }, 500);
          }
        } else {
          // For avoidance/recognition, just set the position
          setBoardFen(data.fen || selectedTrick.trap_position_fen);
          setBoardOrientation(data.user_color || (mode === "avoidance" ? selectedTrick.victim_color : "white"));
          setTrickChess(null);
        }
      }
    } catch (err) {
      console.error("Error starting practice:", err);
      toast.error("Failed to start practice mode");
    }
  };

  // Play engine's automatic response
  const playEngineMove = (chess, moveSan, practiceData) => {
    try {
      const result = chess.move(moveSan, { sloppy: true });
      if (result) {
        setBoardFen(chess.fen());
        setTrickMoveIndex(prev => prev + 1);
        
        // Check if we've reached the trap position
        const setupMoves = practiceData.setup_moves || [];
        const currentMoveCount = chess.history().length;
        
        if (currentMoveCount >= setupMoves.length) {
          // Reached trap position - user must find winning move
          toast.info("Find the winning move!", { duration: 2000 });
        }
      }
    } catch (e) {
      console.error("Engine move failed:", e);
    }
  };

  // Handle user's move in trick practice
  const handleTrickPracticeMove = (moveData) => {
    if (!trickPracticeData || trickPracticeState !== "playing") return;
    
    const moveSan = moveData.san || moveData;
    
    if (trickPracticeMode === "execution" && trickChess) {
      const fullSequence = trickPracticeData.full_sequence || trickPracticeData.setup_moves || [];
      const currentMoveCount = trickChess.history().length;
      
      // Check if we've completed the trap
      if (currentMoveCount >= fullSequence.length) {
        setTrickPracticeState("success");
        toast.success("Trap complete! Well done!");
        return;
      }
      
      // Get the expected move at this position
      const expectedMove = fullSequence[currentMoveCount];
      const normalizedPlayed = moveSan.replace(/[+#=]/g, "");
      const normalizedExpected = expectedMove.replace(/[+#=]/g, "");
      
      if (normalizedPlayed === normalizedExpected || moveSan === expectedMove) {
        // Correct move - play it
        try {
          trickChess.move(moveSan, { sloppy: true });
          setBoardFen(trickChess.fen());
          setTrickMoveIndex(currentMoveCount + 1);
          
          // Check if this was the winning move (trap complete!)
          const isWinningMove = trickPracticeData.user_moves?.find(
            m => m.index === currentMoveCount && m.is_winning
          );
          
          if (isWinningMove || currentMoveCount + 1 >= fullSequence.length) {
            // Trap completed!
            setTrickPracticeState("success");
            toast.success("Brilliant! You've learned the trap!");
            return;
          }
          
          // Check if engine needs to respond
          const nextMoveIndex = currentMoveCount + 1;
          if (nextMoveIndex < fullSequence.length) {
            const nextEngineMove = trickPracticeData.engine_moves?.find(m => m.index === nextMoveIndex);
            if (nextEngineMove) {
              setTimeout(() => {
                playEngineMove(trickChess, nextEngineMove.move, trickPracticeData);
              }, 500);
            }
          }
        } catch (e) {
          console.error("Move error:", e);
          toast.error("Invalid move - try again");
        }
      } else {
        // Wrong move - show hint
        toast.error(`Play ${expectedMove} to continue the trap`);
      }
    } else if (trickPracticeMode === "avoidance") {
      // Validate the avoidance move against the API
      setAvoidanceValidating(true);
      try {
        const res = await fetch(`${API}/training/tricks/validate-avoidance`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            fen: boardFen,
            user_move: moveSan,
            trap_key: selectedTrick.key,
            winning_move: trickPracticeData?.winning_move,
            user_color: trickPracticeData?.user_color || selectedTrick.victim_color
          })
        });
        
        if (res.ok) {
          const result = await res.json();
          
          if (result.fell_into_trap) {
            // User fell into the trap
            setTrickPracticeState("failed");
            toast.error(result.message || "You fell into the trap!");
          } else if (result.is_safe) {
            // User avoided the trap!
            setTrickPracticeState("success");
            toast.success(result.message || "Great! You avoided the trap!");
            if (result.new_fen) {
              setBoardFen(result.new_fen);
            }
          } else {
            toast.error("That move doesn't avoid the trap - try again!");
          }
        } else {
          toast.error("Failed to validate move");
        }
      } catch (err) {
        console.error("Avoidance validation error:", err);
        toast.error("Error validating move");
      } finally {
        setAvoidanceValidating(false);
      }
    }
  };

  // Reset trick practice
  const resetTrickPractice = () => {
    setTrickPracticeMode(null);
    setTrickPracticeState("ready");
    setTrickPracticeData(null);
    setTrickMoveIndex(0);
    setTrickChess(null);
    setAvoidanceValidating(false);
    setRecognitionAnswer({ hasTrap: null, winningMove: "" });
    setRecognitionResult(null);
    if (selectedTrick) {
      setBoardFen(selectedTrick.trap_position_fen || START_FEN);
    }
  };

  // Select an opening
  const handleSelectOpening = (opening) => {
    setSelectedOpening(opening);
    setPracticeMode(null);
    setCurrentPracticeItem(null);
    fetchOpeningContent(opening.key);
  };

  // Start trap practice
  const startTrapPractice = (trap) => {
    setPracticeMode("trap");
    setCurrentPracticeItem(trap);
    setPracticeState("ready");
    setMoveIndex(0);
    setBoardFen(trap.position || trap.fen);
    setBoardOrientation(trap.for_color || "white");
  };

  // Start variation practice
  const startVariationPractice = (variation) => {
    setPracticeMode("variation");
    setCurrentPracticeItem(variation);
    setPracticeState("ready");
    setMoveIndex(0);
    setBoardFen(START_FEN);
    setBoardOrientation("white");
  };

  // Play next move in practice
  const playNextMove = () => {
    if (!currentPracticeItem) return;
    
    const moves = practiceMode === "trap" 
      ? currentPracticeItem.winning_line || currentPracticeItem.correct_line
      : currentPracticeItem.moves;
    
    if (moveIndex >= moves.length) {
      setPracticeState("revealed");
      return;
    }
    
    const chess = new Chess(boardFen);
    try {
      chess.move(moves[moveIndex], { sloppy: true });
      setBoardFen(chess.fen());
      setMoveIndex(prev => prev + 1);
      setPracticeState("playing");
    } catch (e) {
      console.error("Invalid move:", moves[moveIndex]);
    }
  };

  // Reset practice
  const resetPractice = () => {
    if (!currentPracticeItem) return;
    
    if (practiceMode === "trap") {
      setBoardFen(currentPracticeItem.position || currentPracticeItem.fen);
    } else {
      setBoardFen(START_FEN);
    }
    setMoveIndex(0);
    setPracticeState("ready");
  };

  // Exit practice mode
  const exitPractice = () => {
    setPracticeMode(null);
    setCurrentPracticeItem(null);
    if (openingContent?.opening?.main_line) {
      playMainLine(openingContent.opening.main_line);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading your openings...</p>
        </div>
      </div>
    );
  }

  // Render tree view of openings
  const renderOpeningTree = () => {
    const userOpeningKeys = new Set(userOpenings.map(o => o.key?.toLowerCase().replace(/\s+/g, "_")));
    
    return (
      <div className="space-y-2">
        {/* Your Openings Section */}
        <div className="mb-4">
          <button
            onClick={() => toggleNode("your_openings")}
            className="flex items-center gap-2 w-full p-2 rounded-lg hover:bg-muted/50 transition-colors"
            data-testid="your-openings-toggle"
          >
            {expandedNodes["your_openings"] ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <Crown className="w-4 h-4 text-amber-500" />
            <span className="font-medium">Your Repertoire</span>
            <Badge variant="outline" className="ml-auto text-xs">
              {userOpenings.length} openings
            </Badge>
          </button>
          
          <AnimatePresence>
            {expandedNodes["your_openings"] && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="ml-6 mt-1 space-y-1 overflow-hidden"
              >
                {userOpenings.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-2 px-2">
                    Play more games to see your opening repertoire here!
                  </p>
                ) : (
                  userOpenings.map((opening, idx) => {
                    const mastery = MASTERY_STYLES[opening.mastery_level] || MASTERY_STYLES.learning;
                    const openingKey = opening.key || opening.name?.toLowerCase().replace(/\s+/g, "_");
                    const community = opening.community || {};
                    const hasComparison = community.comparison_status && community.comparison_status !== "neutral";
                    
                    return (
                      <button
                        key={idx}
                        onClick={() => handleSelectOpening({ ...opening, key: openingKey })}
                        className={`flex items-center gap-2 w-full p-2 rounded-lg transition-colors text-left ${
                          selectedOpening?.key === openingKey 
                            ? "bg-primary/20 border border-primary/50" 
                            : "hover:bg-muted/50"
                        }`}
                        data-testid={`opening-item-${idx}`}
                      >
                        <BookOpen className={`w-4 h-4 ${mastery.text}`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{opening.name}</p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{opening.games_played} games</span>
                            <span>•</span>
                            <span>{opening.avg_accuracy}% accuracy</span>
                            {hasComparison && (
                              <>
                                <span>•</span>
                                <span className={`font-medium ${
                                  community.comparison_status === "above" ? "text-green-500" :
                                  community.comparison_status === "below" ? "text-orange-500" :
                                  "text-blue-400"
                                }`}>
                                  {community.comparison_status === "above" && "↑"}
                                  {community.comparison_status === "below" && "↓"}
                                  {community.comparison_status === "average" && "≈"}
                                  {community.comparison_status === "above" ? ` Top ${100 - community.percentile}%` :
                                   community.comparison_status === "below" ? ` Bottom ${community.percentile}%` :
                                   " Average"}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                        <Badge variant="outline" className={`text-xs ${mastery.text}`}>
                          {mastery.label}
                        </Badge>
                      </button>
                    );
                  })
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        
        {/* All Openings Database Section */}
        <div>
          <button
            onClick={() => toggleNode("all_openings")}
            className="flex items-center gap-2 w-full p-2 rounded-lg hover:bg-muted/50 transition-colors"
            data-testid="all-openings-toggle"
          >
            {expandedNodes["all_openings"] ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <Layers className="w-4 h-4 text-blue-500" />
            <span className="font-medium">Opening Library</span>
            <Badge variant="outline" className="ml-auto text-xs">
              {allOpenings.length} openings
            </Badge>
          </button>
          
          <AnimatePresence>
            {expandedNodes["all_openings"] && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="ml-6 mt-1 space-y-1 overflow-hidden"
              >
                {allOpenings.map((opening, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSelectOpening(opening)}
                    className={`flex items-center gap-2 w-full p-2 rounded-lg transition-colors text-left ${
                      selectedOpening?.key === opening.key 
                        ? "bg-primary/20 border border-primary/50" 
                        : "hover:bg-muted/50"
                    }`}
                    data-testid={`library-opening-${idx}`}
                  >
                    <BookOpen className={`w-4 h-4 ${opening.color === "white" ? "text-amber-400" : "text-slate-400"}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{opening.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {opening.color === "white" ? "As White" : "As Black"} • {opening.variations_count} variations
                      </p>
                    </div>
                    {opening.traps_count > 0 && (
                      <Badge variant="outline" className="text-xs text-orange-500 border-orange-500/30">
                        {opening.traps_count} traps
                      </Badge>
                    )}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        
        {/* Trick Library Section */}
        <div>
          <button
            onClick={() => toggleNode("trick_library")}
            className="flex items-center gap-2 w-full p-2 rounded-lg hover:bg-muted/50 transition-colors"
            data-testid="trick-library-toggle"
          >
            {expandedNodes["trick_library"] ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <Flame className="w-4 h-4 text-orange-500" />
            <span className="font-medium">Trick Library</span>
            <Badge variant="outline" className="ml-auto text-xs text-orange-500 border-orange-500/30">
              {tricks.length} traps
            </Badge>
          </button>
          
          <AnimatePresence>
            {expandedNodes["trick_library"] && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="ml-6 mt-1 space-y-1 overflow-hidden"
              >
                {/* Group by difficulty */}
                {["beginner", "intermediate", "advanced"].map((difficulty) => {
                  const diffTricks = tricks.filter(t => t.difficulty === difficulty);
                  if (diffTricks.length === 0) return null;
                  
                  return (
                    <div key={difficulty} className="mb-2">
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-2 py-1">
                        {difficulty} ({diffTricks.length})
                      </p>
                      {diffTricks.map((trick, idx) => (
                        <button
                          key={trick.key}
                          onClick={() => handleSelectTrick(trick)}
                          className={`flex items-center gap-2 w-full p-2 rounded-lg transition-colors text-left ${
                            selectedTrick?.key === trick.key 
                              ? "bg-orange-500/20 border border-orange-500/50" 
                              : "hover:bg-muted/50"
                          }`}
                          data-testid={`trick-${trick.key}`}
                        >
                          <Swords className={`w-4 h-4 ${
                            trick.trap_for === "white" ? "text-amber-400" : "text-slate-400"
                          }`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{trick.name}</p>
                            <p className="text-xs text-muted-foreground truncate">
                              {trick.opening}
                            </p>
                          </div>
                          <Badge variant="outline" className={`text-xs ${
                            trick.trap_for === "white" 
                              ? "text-amber-400 border-amber-400/30" 
                              : "text-slate-400 border-slate-400/30"
                          }`}>
                            {trick.trap_for}
                          </Badge>
                        </button>
                      ))}
                    </div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    );
  };

  // Render opening content detail view
  const renderOpeningContent = () => {
    // If a trick is selected, render trick content instead
    if (selectedTrick) {
      return renderTrickContent();
    }
    
    if (!selectedOpening) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <GraduationCap className="w-12 h-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">Select an Opening</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Choose an opening from your repertoire or the library to study its key variations, traps, and ideas.
          </p>
        </div>
      );
    }
    
    if (loadingContent) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      );
    }
    
    // Practice mode view
    if (practiceMode && currentPracticeItem) {
      return renderPracticeMode();
    }
    
    const opening = openingContent?.opening;
    const variations = openingContent?.variations || [];
    const traps = openingContent?.traps || [];
    const keyIdeas = openingContent?.key_ideas || opening?.key_ideas || [];
    const typicalMistakes = openingContent?.typical_mistakes || opening?.typical_mistakes || [];
    const lichessStats = openingContent?.lichess_stats;
    const fromLichess = openingContent?.from_lichess;
    
    return (
      <ScrollArea className="h-full">
        <div className="space-y-4 pr-4">
          {/* Opening header */}
          <div className="flex items-start gap-3">
            <div className={`p-2 rounded-lg ${opening?.color === "white" ? "bg-amber-500/10" : "bg-slate-500/10"}`}>
              <BookOpen className={`w-6 h-6 ${opening?.color === "white" ? "text-amber-500" : "text-slate-400"}`} />
            </div>
            <div>
              <h3 className="text-xl font-bold">{opening?.name || selectedOpening.name}</h3>
              <p className="text-sm text-muted-foreground">
                {opening?.eco} • Play as {opening?.color || selectedOpening.color}
                {fromLichess && <Badge variant="outline" className="ml-2 text-xs">Lichess Data</Badge>}
              </p>
            </div>
          </div>
          
          {/* Lichess Statistics */}
          {lichessStats && (lichessStats.lichess?.total_games > 0 || lichessStats.total_games > 0) && (
            <Card className="bg-gradient-to-r from-green-500/10 to-blue-500/10 border-green-500/30">
              <CardContent className="py-3">
                <div className="flex items-center gap-2 mb-2">
                  <Trophy className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium">Lichess Statistics</span>
                  <span className="text-xs text-muted-foreground ml-auto">
                    {((lichessStats.lichess?.total_games || lichessStats.total_games || 0) / 1000000).toFixed(1)}M games
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded bg-background/50">
                    <p className="text-lg font-bold text-green-500">
                      {lichessStats.lichess?.white_wins || lichessStats.white_wins || 0}%
                    </p>
                    <p className="text-xs text-muted-foreground">White wins</p>
                  </div>
                  <div className="p-2 rounded bg-background/50">
                    <p className="text-lg font-bold text-gray-400">
                      {lichessStats.lichess?.draws || lichessStats.draws || 0}%
                    </p>
                    <p className="text-xs text-muted-foreground">Draws</p>
                  </div>
                  <div className="p-2 rounded bg-background/50">
                    <p className="text-lg font-bold text-red-500">
                      {lichessStats.lichess?.black_wins || lichessStats.black_wins || 0}%
                    </p>
                    <p className="text-xs text-muted-foreground">Black wins</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Community Comparison - Show for user's openings */}
          {selectedOpening?.community && selectedOpening.community.comparison_status !== "neutral" && (
            <Card className={`border ${
              selectedOpening.community.comparison_status === "above" 
                ? "bg-green-500/10 border-green-500/30" 
                : selectedOpening.community.comparison_status === "below"
                  ? "bg-orange-500/10 border-orange-500/30"
                  : "bg-blue-500/10 border-blue-500/30"
            }`} data-testid="community-comparison-card">
              <CardContent className="py-3">
                <div className="flex items-center gap-2 mb-3">
                  <Users className={`w-4 h-4 ${
                    selectedOpening.community.comparison_status === "above" ? "text-green-500" :
                    selectedOpening.community.comparison_status === "below" ? "text-orange-500" :
                    "text-blue-400"
                  }`} />
                  <span className="text-sm font-medium">Compare to Community</span>
                  <Badge variant="outline" className="ml-auto text-xs">
                    {selectedOpening.community.rating_band_label} players
                  </Badge>
                </div>
                
                <div className="grid grid-cols-2 gap-3">
                  {/* Your Accuracy */}
                  <div className="p-2 rounded bg-background/50 text-center">
                    <p className="text-2xl font-bold">{selectedOpening.avg_accuracy}%</p>
                    <p className="text-xs text-muted-foreground">Your Accuracy</p>
                  </div>
                  
                  {/* Community Average */}
                  <div className="p-2 rounded bg-background/50 text-center">
                    <p className="text-2xl font-bold text-muted-foreground">
                      {selectedOpening.community.avg_accuracy}%
                    </p>
                    <p className="text-xs text-muted-foreground">Community Avg</p>
                  </div>
                </div>
                
                {/* Comparison Status */}
                <div className={`mt-3 p-2 rounded text-center ${
                  selectedOpening.community.comparison_status === "above" 
                    ? "bg-green-500/20" 
                    : selectedOpening.community.comparison_status === "below"
                      ? "bg-orange-500/20"
                      : "bg-blue-500/20"
                }`}>
                  <div className="flex items-center justify-center gap-2">
                    {selectedOpening.community.comparison_status === "above" && (
                      <TrendingUp className="w-4 h-4 text-green-500" />
                    )}
                    {selectedOpening.community.comparison_status === "below" && (
                      <TrendingDown className="w-4 h-4 text-orange-500" />
                    )}
                    {selectedOpening.community.comparison_status === "average" && (
                      <Minus className="w-4 h-4 text-blue-400" />
                    )}
                    <span className={`text-sm font-medium ${
                      selectedOpening.community.comparison_status === "above" ? "text-green-500" :
                      selectedOpening.community.comparison_status === "below" ? "text-orange-500" :
                      "text-blue-400"
                    }`}>
                      {selectedOpening.community.comparison_text}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {selectedOpening.community.comparison_status === "above" 
                      ? `Better than ${selectedOpening.community.percentile}% of players` 
                      : selectedOpening.community.comparison_status === "below"
                        ? `Work on this opening to improve`
                        : `Performing at the expected level`}
                  </p>
                </div>
                
                {/* Stats footer */}
                <p className="text-xs text-muted-foreground text-center mt-2">
                  Based on {selectedOpening.community.total_games} games from {selectedOpening.community.player_count} players
                </p>
              </CardContent>
            </Card>
          )}
          
          {/* Description */}
          {opening?.description && (
            <Card className="bg-muted/30">
              <CardContent className="py-3">
                <p className="text-sm">{opening.description}</p>
              </CardContent>
            </Card>
          )}
          
          {/* Main Line */}
          {opening?.main_line && opening.main_line.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Main Line</h4>
              <div className="flex flex-wrap gap-1">
                {opening.main_line.map((move, idx) => (
                  <span key={idx} className="text-sm font-mono px-2 py-1 rounded bg-muted">
                    {idx % 2 === 0 && <span className="text-muted-foreground mr-1">{Math.floor(idx/2) + 1}.</span>}
                    {move}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {/* Key Ideas */}
          {keyIdeas.length > 0 && (
            <Card className="bg-blue-500/10 border-blue-500/30">
              <CardHeader className="py-3 pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Lightbulb className="w-4 h-4 text-blue-500" />
                  Key Ideas
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                <ul className="space-y-1">
                  {keyIdeas.map((idea, idx) => (
                    <li key={idx} className="text-sm flex items-start gap-2">
                      <span className="text-blue-500 mt-1">•</span>
                      {idea}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          
          {/* Variations */}
          {variations.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                <Layers className="w-4 h-4" />
                Key Variations ({variations.length})
              </h4>
              <div className="space-y-2">
                {variations.map((variation, idx) => (
                  <Card key={idx} className="hover:bg-muted/30 transition-colors">
                    <CardContent className="py-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1">
                          <p className="font-medium text-sm">{variation.name}</p>
                          <p className="text-xs text-muted-foreground mt-1">{variation.idea}</p>
                          <div className="flex flex-wrap gap-1 mt-2">
                            {variation.moves?.slice(0, 6).map((move, i) => (
                              <span key={i} className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted">
                                {move}
                              </span>
                            ))}
                            {variation.moves?.length > 6 && (
                              <span className="text-xs text-muted-foreground">...</span>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => startVariationPractice(variation)}
                          className="shrink-0"
                          data-testid={`practice-variation-${idx}`}
                        >
                          <Play className="w-3 h-3 mr-1" />
                          Study
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
          
          {/* Traps */}
          {traps.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                <Swords className="w-4 h-4 text-orange-500" />
                Traps to Know ({traps.length})
              </h4>
              <div className="space-y-2">
                {traps.map((trap, idx) => (
                  <Card key={idx} className="bg-orange-500/10 border-orange-500/30 hover:bg-orange-500/15 transition-colors">
                    <CardContent className="py-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1">
                          <p className="font-medium text-sm text-orange-400">{trap.name}</p>
                          <Badge variant="outline" className="text-xs mt-1">
                            For {trap.for_color}
                          </Badge>
                          <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                            {trap.explanation}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => startTrapPractice(trap)}
                          className="shrink-0 border-orange-500/30 text-orange-400 hover:bg-orange-500/20"
                          data-testid={`practice-trap-${idx}`}
                        >
                          <Zap className="w-3 h-3 mr-1" />
                          Practice
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
          
          {/* Typical Mistakes */}
          {typicalMistakes.length > 0 && (
            <Card className="bg-red-500/10 border-red-500/30">
              <CardHeader className="py-3 pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-red-400">
                  <AlertTriangle className="w-4 h-4" />
                  Common Mistakes to Avoid
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                <ul className="space-y-1">
                  {typicalMistakes.map((mistake, idx) => (
                    <li key={idx} className="text-sm flex items-start gap-2">
                      <XCircle className="w-3 h-3 text-red-500 mt-1 shrink-0" />
                      {mistake}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          
          {/* User's mistakes in this opening */}
          {openingContent?.your_mistakes?.length > 0 && (
            <Card className="bg-violet-500/10 border-violet-500/30">
              <CardHeader className="py-3 pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-violet-400">
                  <Target className="w-4 h-4" />
                  Your Mistakes in This Opening
                </CardTitle>
              </CardHeader>
              <CardContent className="py-2">
                <p className="text-xs text-muted-foreground mb-2">
                  Focus areas based on your games:
                </p>
                <div className="space-y-2">
                  {openingContent.your_mistakes.slice(0, 3).map((mistake, idx) => (
                    <div key={idx} className="text-sm p-2 rounded bg-background/50">
                      <span className="text-muted-foreground">Move {mistake.move_number}:</span>{" "}
                      <span className="font-mono text-red-400">{mistake.move}</span>
                      {" → "}
                      <span className="font-mono text-green-400">{mistake.best_move}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </ScrollArea>
    );
  };

  // Render practice mode
  const renderPracticeMode = () => {
    const item = currentPracticeItem;
    const moves = practiceMode === "trap" 
      ? item.winning_line || item.correct_line
      : item.moves;
    
    return (
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold">{item.name}</h3>
            <p className="text-sm text-muted-foreground">
              {practiceMode === "trap" ? "Find the winning continuation" : "Learn the move order"}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={exitPractice}>
            <ChevronLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
        </div>
        
        {/* Board */}
        <div className="flex justify-center">
          <div className="w-full max-w-sm">
            <CoachBoard
              ref={boardRef}
              position={boardFen}
              userColor={boardOrientation}
              interactive={false}
              showControls={false}
            />
          </div>
        </div>
        
        {/* Move progress */}
        <div className="text-center">
          <div className="flex justify-center gap-1 mb-2">
            {moves?.map((move, idx) => (
              <span
                key={idx}
                className={`text-sm font-mono px-2 py-1 rounded ${
                  idx < moveIndex 
                    ? "bg-green-500/20 text-green-400" 
                    : idx === moveIndex 
                      ? "bg-primary/20 text-primary ring-1 ring-primary" 
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {move}
              </span>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Move {moveIndex} of {moves?.length || 0}
          </p>
        </div>
        
        {/* Controls */}
        <div className="flex justify-center gap-2">
          <Button variant="outline" size="sm" onClick={resetPractice}>
            <RotateCcw className="w-4 h-4 mr-1" />
            Reset
          </Button>
          {practiceState !== "revealed" ? (
            <Button size="sm" onClick={playNextMove} data-testid="play-next-move">
              <Play className="w-4 h-4 mr-1" />
              {practiceState === "ready" ? "Start" : "Next Move"}
            </Button>
          ) : (
            <Badge variant="outline" className="py-2 px-4 text-green-400 border-green-500/30">
              <CheckCircle2 className="w-4 h-4 mr-1" />
              Complete!
            </Badge>
          )}
        </div>
        
        {/* Explanation */}
        {item.explanation && (
          <Card className="bg-muted/30">
            <CardContent className="py-3">
              <div className="flex items-start gap-2">
                <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                <p className="text-sm">{item.explanation || item.idea}</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    );
  };

  // Render trick content panel
  const renderTrickContent = () => {
    const trick = selectedTrick;
    
    return (
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start gap-3">
          <Swords className="w-6 h-6 text-orange-500 mt-1" />
          <div className="flex-1">
            <h3 className="text-lg font-semibold">{trick.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline" className="text-xs">
                {trick.eco} • {trick.opening}
              </Badge>
              <Badge 
                variant="outline" 
                className={`text-xs ${
                  trick.difficulty === "beginner" ? "text-green-400 border-green-500/30" :
                  trick.difficulty === "intermediate" ? "text-blue-400 border-blue-500/30" :
                  "text-purple-400 border-purple-500/30"
                }`}
              >
                {trick.difficulty}
              </Badge>
              <Badge 
                variant="outline" 
                className={`text-xs ${
                  trick.trap_for === "white" ? "text-amber-400 border-amber-400/30" : "text-slate-400 border-slate-400/30"
                }`}
              >
                {trick.trap_for === "white" ? "White sets trap" : "Black sets trap"}
              </Badge>
            </div>
          </div>
        </div>
        
        {/* Description */}
        <Card className="bg-orange-500/10 border-orange-500/30">
          <CardContent className="py-3">
            <p className="text-sm">{trick.description}</p>
          </CardContent>
        </Card>
        
        {/* Practice Modes */}
        {!trickPracticeMode && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
              <Target className="w-4 h-4" />
              Practice Modes
            </h4>
            <div className="grid grid-cols-1 gap-2">
              {/* Execution Mode */}
              <Card 
                className="bg-green-500/10 border-green-500/30 hover:bg-green-500/20 transition-colors cursor-pointer"
                onClick={() => startTrickPractice("execution")}
                data-testid="practice-execution"
              >
                <CardContent className="py-3">
                  <div className="flex items-center gap-3">
                    <Target className="w-5 h-5 text-green-500" />
                    <div className="flex-1">
                      <p className="font-medium text-green-400">Learn the Trap</p>
                      <p className="text-xs text-muted-foreground">Play through the trap step by step</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
              
              {/* Avoidance Mode */}
              <Card 
                className="bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/20 transition-colors cursor-pointer"
                onClick={() => startTrickPractice("avoidance")}
                data-testid="practice-avoidance"
              >
                <CardContent className="py-3">
                  <div className="flex items-center gap-3">
                    <Shield className="w-5 h-5 text-blue-500" />
                    <div className="flex-1">
                      <p className="font-medium text-blue-400">Avoidance Mode</p>
                      <p className="text-xs text-muted-foreground">Don't fall for it - find a safe move!</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
              
              {/* Recognition Mode */}
              <Card 
                className="bg-purple-500/10 border-purple-500/30 hover:bg-purple-500/20 transition-colors cursor-pointer"
                onClick={() => startTrickPractice("recognition")}
                data-testid="practice-recognition"
              >
                <CardContent className="py-3">
                  <div className="flex items-center gap-3">
                    <Eye className="w-5 h-5 text-purple-500" />
                    <div className="flex-1">
                      <p className="font-medium text-purple-400">Recognition Mode</p>
                      <p className="text-xs text-muted-foreground">Spot the trap - what's the danger?</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
        
        {/* Practice Mode Active */}
        {trickPracticeMode && trickPracticeData && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Badge 
                className={`${
                  trickPracticeMode === "execution" ? "bg-green-500/20 text-green-400" :
                  trickPracticeMode === "avoidance" ? "bg-blue-500/20 text-blue-400" :
                  "bg-purple-500/20 text-purple-400"
                }`}
              >
              {trickPracticeMode === "execution" ? "🎯 Learn Mode" :
                 trickPracticeMode === "avoidance" ? "🛡️ Avoidance Mode" :
                 "👁️ Recognition Mode"}
              </Badge>
              <Button variant="ghost" size="sm" onClick={resetTrickPractice}>
                <RotateCcw className="w-4 h-4 mr-1" />
                Reset
              </Button>
            </div>
            
            {/* Hint */}
            <Card className="bg-muted/30">
              <CardContent className="py-3">
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5" />
                  <p className="text-sm">{trickPracticeData.hints}</p>
                </div>
              </CardContent>
            </Card>
            
            {/* Move Progress for Execution Mode */}
            {trickPracticeMode === "execution" && trickPracticeData.setup_moves && trickPracticeState === "playing" && (
              <Card className="bg-muted/30">
                <CardContent className="py-3">
                  <p className="text-xs text-muted-foreground mb-2">Setup Progress:</p>
                  <div className="flex flex-wrap gap-1">
                    {trickPracticeData.setup_moves.map((move, idx) => {
                      const isUserMove = trickPracticeData.user_moves?.some(m => m.index === idx);
                      const isPlayed = idx < trickMoveIndex;
                      const isCurrent = idx === trickMoveIndex;
                      
                      return (
                        <span
                          key={idx}
                          className={`text-xs font-mono px-2 py-1 rounded ${
                            isPlayed 
                              ? "bg-green-500/20 text-green-400" 
                              : isCurrent 
                                ? isUserMove 
                                  ? "bg-primary/30 text-primary ring-1 ring-primary animate-pulse" 
                                  : "bg-muted text-muted-foreground"
                                : "bg-muted/50 text-muted-foreground/50"
                          }`}
                        >
                          {idx % 2 === 0 ? `${Math.floor(idx/2) + 1}.` : ""}{move}
                          {isUserMove && !isPlayed && isCurrent && " ←"}
                        </span>
                      );
                    })}
                    <span className="text-xs font-mono px-2 py-1 rounded bg-orange-500/20 text-orange-400">
                      {trickPracticeData.winning_move} 🎯
                    </span>
                  </div>
                </CardContent>
              </Card>
            )}
            
            {/* Result */}
            {trickPracticeState === "success" && (
              <Card className="bg-green-500/20 border-green-500/50">
                <CardContent className="py-3">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle2 className="w-5 h-5 text-green-500" />
                    <span className="font-medium text-green-400">Trap Complete!</span>
                  </div>
                  <p className="text-sm font-medium mb-2">Why it works:</p>
                  <p className="text-sm text-muted-foreground">{trick.why_it_works || trick.explanation}</p>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="mt-3"
                    onClick={resetTrickPractice}
                  >
                    <RotateCcw className="w-4 h-4 mr-1" />
                    Practice Again
                  </Button>
                </CardContent>
              </Card>
            )}
            
            {trickPracticeState === "failed" && (
              <Card className="bg-red-500/20 border-red-500/50">
                <CardContent className="py-3">
                  <div className="flex items-center gap-2">
                    <XCircle className="w-5 h-5 text-red-500" />
                    <span className="font-medium text-red-400">Not quite!</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    The winning move was <span className="font-mono text-orange-400">{trick.winning_move}</span>
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">{trick.explanation}</p>
                </CardContent>
              </Card>
            )}
          </div>
        )}
        
        {/* Winning Line (when not in practice) */}
        {!trickPracticeMode && trick.winning_line && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
              <Zap className="w-4 h-4 text-orange-500" />
              Winning Continuation
            </h4>
            <div className="flex flex-wrap gap-1">
              {trick.winning_line.map((move, idx) => (
                <span key={idx} className="text-sm font-mono bg-orange-500/20 text-orange-400 px-2 py-1 rounded">
                  {move}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {/* Why It Works */}
        {!trickPracticeMode && trick.why_it_works && (
          <Card className="bg-muted/30">
            <CardContent className="py-3">
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-500" />
                Why It Works
              </h4>
              <p className="text-sm text-muted-foreground">{trick.why_it_works}</p>
            </CardContent>
          </Card>
        )}
        
        {/* How to Avoid */}
        {!trickPracticeMode && trick.how_to_avoid && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
              <Shield className="w-4 h-4 text-blue-500" />
              How to Avoid
            </h4>
            <ul className="space-y-1">
              {trick.how_to_avoid.map((tip, idx) => (
                <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="text-blue-400 shrink-0">•</span>
                  {tip}
                </li>
              ))}
            </ul>
          </div>
        )}
        
        {/* Key Squares */}
        {!trickPracticeMode && trick.key_squares && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground">Key squares:</span>
            {trick.key_squares.map((sq, idx) => (
              <Badge key={idx} variant="outline" className="text-xs font-mono">
                {sq}
              </Badge>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
      {/* Left panel - Opening tree */}
      <div className="lg:col-span-1">
        <Card className="h-full">
          <CardHeader className="py-4">
            <CardTitle className="text-lg flex items-center gap-2">
              <GraduationCap className="w-5 h-5 text-primary" />
              Opening Trainer
            </CardTitle>
          </CardHeader>
          <CardContent className="py-0 pb-4">
            <ScrollArea className="h-[400px] lg:h-[500px]">
              {renderOpeningTree()}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
      
      {/* Center panel - Board */}
      <div className="lg:col-span-1">
        <Card className="h-full">
          <CardContent className="py-4">
            <div className="flex justify-center">
              <div className="w-full max-w-sm">
                <CoachBoard
                  ref={boardRef}
                  position={boardFen}
                  userColor={boardOrientation}
                  interactive={trickPracticeMode === "execution" && trickPracticeState === "playing"}
                  showControls={!trickPracticeMode}
                  onUserMove={trickPracticeMode === "execution" ? handleTrickPracticeMove : undefined}
                />
              </div>
            </div>
            {/* Execution mode indicator */}
            {trickPracticeMode === "execution" && trickPracticeState === "playing" && (
              <div className="text-center mt-3">
                <Badge className="bg-green-500/20 text-green-400">
                  Your turn - make a move on the board
                </Badge>
              </div>
            )}
            {selectedOpening && !practiceMode && (
              <div className="text-center mt-4">
                <p className="text-sm text-muted-foreground">
                  {openingContent?.opening?.name || selectedOpening.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  Main line position
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
      
      {/* Right panel - Content */}
      <div className="lg:col-span-1">
        <Card className="h-full">
          <CardContent className="py-4 h-[400px] lg:h-[550px]">
            {renderOpeningContent()}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default OpeningTrainer;
