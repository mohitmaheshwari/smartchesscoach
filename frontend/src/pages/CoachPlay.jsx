/**
 * CoachPlay — Main "Play with Coach" page
 *
 * This file is the orchestrator that holds all state and logic.
 * Rendering is delegated to:
 *   - CoachPlaySetup  (pre-game screen)
 *   - CoachPlayBoard  (left: board + eval + controls)
 *   - CoachPlaySidebar (right: coaching panels)
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { toast } from "sonner";
import { Target } from "lucide-react";
import { PostGameStreakResult } from "@/components/streak";
import EnforcementCheckboxModal from "@/components/coach-play/EnforcementCheckboxModal";
import CoachPlaySetup from "@/components/coach/CoachPlaySetup";
import CoachPlayBoard from "@/components/coach/CoachPlayBoard";
import CoachPlaySidebar from "@/components/coach/CoachPlaySidebar";
import useTeachingMode from "@/hooks/useTeachingMode";
import usePlayerData from "@/hooks/usePlayerData";
import useGuardian from "@/hooks/useGuardian";
import { useCoachFlow, INTERACTION_STATES, CLOCK_STATES } from "@/coachFlow";
import ActiveCoachingCard from "@/components/coach/ActiveCoachingCard";
import ActiveCoachStrip from "@/components/coach/ActiveCoachStrip";
import CoachTimelinePanel from "@/components/coach/CoachTimelinePanel";
import CommentaryPanel from "@/components/coach/CommentaryPanel";

const CoachPlay = ({ user }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const boardRef = useRef(null);

  // Read opening from URL query params (from Progress page)
  const openingFromUrl = searchParams.get("opening");

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
  const [selectedOpening, setSelectedOpening] = useState(openingFromUrl || null);
  const [guidedMode, setGuidedMode] = useState(true); // true = Guide Me, false = I Know It
  const [activeBranch, setActiveBranch] = useState(null); // current variation being taught
  const [allBranches, setAllBranches] = useState(null); // all available branches {key: {name, branch_move, ideas}}
  const [branchPoint, setBranchPoint] = useState(null); // ply where branches diverge
  const [openingTraps, setOpeningTraps] = useState([]); // traps for current opening

  // Sync opening from URL when navigating from Progress page
  useEffect(() => {
    if (openingFromUrl && !gameStarted) {
      setSelectedOpening(openingFromUrl);
    }
  }, [openingFromUrl, gameStarted]);

  const [timeControl, setTimeControl] = useState("15+10");
  const [coachingMode, setCoachingMode] = useState("intermediate"); // "beginner" | "intermediate" | "advanced"
  
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

  // Pre-game focus rule
  const [focusRule, setFocusRule] = useState(null);
  const [showFocusBanner, setShowFocusBanner] = useState(false);
  
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

  // NEW: Visual move hints state
  const [moveHints, setMoveHints] = useState([]);
  
  // ── Hooks: Teaching, Player Data, Guardian ──
  const teaching = useTeachingMode({
    session,
    currentFen,
    setChatMessages,
    setCurrentFen,
    setCurrentInsight: (v) => setCurrentInsight(v),
    newGameFn: () => newGame(),
    startGameFn: () => startGame(),
  });

  const playerData = usePlayerData({
    user,
    session,
    gameOver,
    selectedColor,
  });

  const handleCancelRestore = useCallback((originalFen) => {
    setCurrentFen(originalFen);
    setLastMove(null);
    setIsPlayerTurn(true);
    if (boardRef.current?.setPosition) {
      boardRef.current.setPosition(originalFen);
    }
  }, []);

  const guardian = useGuardian({
    session,
    onCancelRestore: handleCancelRestore,
  });

  // Coach Flow — pending move, hold states, clock commit, timeline
  const coachFlow = useCoachFlow({
    session,
    userRating: session?.user_rating || 1200,
  });

  // Destructure for backwards compatibility with existing code
  const {
    teachingOffer, setTeachingOffer,
    activeLesson, setActiveLesson,
    lessonInstruction, setLessonInstruction,
    lessonComplete, setLessonComplete,
    isInTeachingMode, setIsInTeachingMode,
    openingGuidance, setOpeningGuidance,
    inlineOpening, setInlineOpening,
    inlineTrap, setInlineTrap,
    coachIntroMessage, setCoachIntroMessage,
    curriculumFeedback, setCurriculumFeedback,
    lastCoachMoveSan, setLastCoachMoveSan,
    positionCoaching, setPositionCoaching,
    openingCorrectionCount, setOpeningCorrectionCount,
    handleStartLesson, handleSkipTeachingOffer, handleExitLesson,
    handleTeachingMove, resetTeachingState,
  } = teaching;

  const {
    pastGamesHistory, playerIdentityData,
    blundersThisGame, setBlundersThisGame,
    recentResults,
    showPreGameStreakPopup, setShowPreGameStreakPopup,
    showPostGameStreakResult, setShowPostGameStreakResult,
    postGameStreakResult,
    hasCastled, developedPieces,
    playerWeaknesses,
    showChecklist, setShowChecklist,
    hideEvalBar, setHideEvalBar,
    opportunitiesFound, setOpportunitiesFound,
    opportunitiesMissed, setOpportunitiesMissed,
    resetPlayerData,
  } = playerData;

  const {
    guardianIntervention, setGuardianIntervention,
    pendingMove,
    remainingInterventions, setRemainingInterventions,
    evaluateMove,
    cancelRiskyMove,
    setIntervention: setGuardianPending,
    clearIntervention: clearGuardian,
  } = guardian;
  
  // NEW: Real-time move feedback state
  const [moveFeedback, setMoveFeedback] = useState(null);
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  
  // Board arrows for coaching visualization
  const [coachArrows, setCoachArrows] = useState([]);

  // Client-side opening guidance — no server dependency for arrows
  const [openingIdeas, setOpeningIdeas] = useState([]); // ALL move ideas from /start
  const [gamePly, setGamePly] = useState(0); // total half-moves played

  // Compute and show guidance arrow from local data
  useEffect(() => {
    if (!openingIdeas.length || !isPlayerTurn || gameOver) return;
    // The user's next move is at the current gamePly
    const idea = openingIdeas[gamePly];
    // The coach's last move (just played) is at gamePly - 1
    const coachIdea = gamePly > 0 ? openingIdeas[gamePly - 1] : null;

    if (idea?.arrow) {
      console.log("[CoachPlay] Client-side arrow for ply", gamePly, ":", idea.arrow, idea.move);
      setCoachArrows([[idea.arrow[0], idea.arrow[1], "green"]]);
      // Update guidance for CommentaryPanel
      coachFlow.setOpeningGuidance({
        opening_key: openingIdeas._key || "",
        move_idea: idea.idea,
        expected_move: idea.move,
        arrow: idea.arrow,
        coach_move_idea: coachIdea?.idea || null,
        coach_move: coachIdea?.move || null,
      });
    } else if (idea && !idea.arrow) {
      // User move exists but has no arrow (shouldn't happen for user moves, but handle it)
      coachFlow.setOpeningGuidance({
        move_idea: idea.idea,
        expected_move: idea.move,
        arrow: null,
        coach_move_idea: coachIdea?.idea || null,
        coach_move: coachIdea?.move || null,
      });
      setCoachArrows([]);
    } else {
      // Past the teaching line — clear guidance
      setCoachArrows([]);
      coachFlow.setOpeningGuidance(null);
    }
  }, [gamePly, openingIdeas, isPlayerTurn, gameOver]);

  // Legacy: still accept server-side guidance for fallback
  useEffect(() => {
    const guidance = coachFlow.openingGuidance;
    if (guidance?.arrow && isPlayerTurn && !gameOver && !openingIdeas.length) {
      setCoachArrows([[guidance.arrow[0], guidance.arrow[1], "green"]]);
    }
  }, [coachFlow.openingGuidance?.arrow?.[0], coachFlow.openingGuidance?.arrow?.[1], isPlayerTurn, gameOver, openingIdeas.length]);

  // Opening line completion summary
  const [openingComplete, setOpeningComplete] = useState(null);

  // Detect when the teaching line is finished
  useEffect(() => {
    if (!openingIdeas.length || gameOver || openingComplete) return;
    if (gamePly >= openingIdeas.length && isPlayerTurn) {
      // All teaching moves played — show summary
      const branchName = activeBranch?.name || selectedOpening || "opening";
      const otherBranches = allBranches
        ? Object.values(allBranches).filter(b => b.name !== activeBranch?.name).map(b => b.name)
        : [];

      // Get current eval from coachFlow or evaluation state
      const evalScore = evaluation?.score || 0;
      const evalText = evalScore > 50 ? "You have a slight advantage"
        : evalScore > 150 ? "You have a clear advantage"
        : evalScore < -50 ? "Black has a slight edge"
        : "The position is roughly equal";

      setOpeningComplete({
        branchName,
        evalText,
        evalScore,
        otherBranches,
        totalMoves: openingIdeas.length,
        deviations: 0, // TODO: track during play
      });

      // Log to backend for mastery tracking
      if (session?.session_id) {
        fetch(`${API}/coach/play/opening-line-complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            session_id: session.session_id,
            opening_key: activeBranch?.key || selectedOpening,
            branch_key: activeBranch?.key || null,
            guided_mode: guidedMode,
            moves_total: openingIdeas.length,
            played_perfectly: true, // no deviations if we got here
          }),
        }).catch(() => {}); // fire-and-forget
      }

      // Clear teaching data — game continues freely
      setOpeningIdeas([]);
      setCoachArrows([]);
      coachFlow.setOpeningGuidance(null);
    }
  }, [gamePly, openingIdeas, isPlayerTurn, gameOver, openingComplete]);

  // Opening deviation state — shown when user plays wrong move
  const [openingDeviation, setOpeningDeviation] = useState(null);

  // Client-side trap detection — check if we're approaching a known trap
  useEffect(() => {
    if (!openingTraps.length || !openingIdeas.length || !isPlayerTurn || gameOver) return;
    // Build the moves played so far from openingIdeas[0..gamePly-1]
    const movesPlayed = openingIdeas.slice(0, gamePly).map(i => i.move);
    if (movesPlayed.length < 3) return; // too early

    for (const trap of openingTraps) {
      const setup = trap.setup_moves;
      // Check if current moves match the trap setup prefix
      const matchLen = Math.min(movesPlayed.length, setup.length);
      let matches = true;
      for (let i = 0; i < matchLen; i++) {
        if (movesPlayed[i]?.replace(/[+#]/g, "").toLowerCase() !== setup[i]?.replace(/[+#]/g, "").toLowerCase()) {
          matches = false;
          break;
        }
      }
      if (matches) {
        const remaining = setup.length - movesPlayed.length;
        if (remaining >= 0 && remaining <= 2) {
          // We're close to a trap — warn the user
          coachFlow.setTrapWarning({
            trap_name: trap.name,
            warning: trap.explanation,
            refutation: trap.refutation,
            trap_move: trap.trap_move,
            remaining_moves: remaining,
          });
          return;
        }
      }
    }
    // No trap nearby — clear warning
    coachFlow.setTrapWarning(null);
  }, [gamePly, openingTraps, openingIdeas, isPlayerTurn, gameOver]);

  // V5 Coaching State - Unified with Lab
  const [v5Coaching, setV5Coaching] = useState(null);
  const [acknowledgedConcepts, setAcknowledgedConcepts] = useState(new Set());
  const [preMoveTrap, setPreMoveTrap] = useState(null);
  const [fundamentalViolations, setFundamentalViolations] = useState([]);
  
  // Interactive Coaching State - Two-part dialogue (user move + coach move)
  const [interactiveCoaching, setInteractiveCoaching] = useState({
    userMoveCoaching: null,
    coachMoveCoaching: null
  });
  
  // Behavioral Coaching State - Smart Coach habits feedback
  const [behavioralCoaching, setBehavioralCoaching] = useState(null);
  
  // Clean UX State
  const [currentInsight, setCurrentInsight] = useState(null);
  const [isCoachThinking, setIsCoachThinking] = useState(false);
  const [activeTrapAlert, setActiveTrapAlert] = useState(null);
  const [cleanUIMode, setCleanUIMode] = useState(true);
  
  // Pedagogical state (not in hooks)
  const [consequenceFeedback, setConsequenceFeedback] = useState(null);

  // Escape Squares Quiz state
  const [escapeSquaresQuiz, setEscapeSquaresQuiz] = useState(null);

  // Check for escape squares teaching moment
  const checkEscapeSquares = useCallback(async () => {
    if (!session?.session_id || isInTeachingMode || gameOver) return;
    try {
      const res = await fetch(`${API}/coach/play/escape-squares/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: session.session_id }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.has_quiz) {
          setEscapeSquaresQuiz(data.quiz);
        }
      }
    } catch (e) {
      // Silently fail — quiz is optional
    }
  }, [session?.session_id, isInTeachingMode, gameOver]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Fetch post-game reflection when game ends
  useEffect(() => {
    if (gameOver && session?.session_id && !summary) {
      (async () => {
        try {
          const res = await fetch(`${API}/coach/play/postgame/${session.session_id}`, { credentials: "include" });
          if (res.ok) {
            const data = await res.json();
            setSummary(data);
          }
        } catch (e) {
          console.error("Postgame fetch failed:", e);
        }
      })();
    }
  }, [gameOver, session?.session_id]);

  // Poll for coach messages when game is active (skip during curriculum — curriculum handles coaching)
  useEffect(() => {
    if (session && gameStarted && !gameOver && !session.curriculum_active && !session.teaching_opening) {
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
    
    // Don't poll during active interactive teaching lessons (not regular game teaching)
    if (isInTeachingMode && lessonInstruction) return;
    
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
            // Only set if we have valid data
            if (offer.opening_name) {
              // Set inline opening lesson (new non-disruptive approach)
              setInlineOpening({
                name: offer.opening_name,
                key: offer.opening_key,
                main_idea: offer.message || `We're in the ${offer.opening_name}!`,
                simple_explanation: offer.message,
                key_moves: offer.main_moves || [],
                key_squares: offer.key_squares || []
              });
              
              // Set inline trap if available
              if (offer.trap_name) {
                setInlineTrap({
                  name: offer.trap_name,
                  opening_key: offer.opening_key,
                  description: `A trap in the ${offer.opening_name}`,
                  moves: offer.trap_moves || [],
                  trigger_move: offer.trap_trigger
                });
              }
              
              // Also set legacy teaching offer as fallback
              setTeachingOffer({
                opening_name: offer.opening_name,
                opening_key: offer.opening_key,
                message: offer.message || `We're in the ${offer.opening_name}! Want to learn more?`,
                options: offer.options || [
                  { id: "learn_trap", label: "Learn a trap", description: "Interactive trap lesson" },
                  { id: "learn_main_line", label: "Learn the main line", description: "Step-by-step opening theory" },
                  { id: "just_play", label: "Just play", description: "Continue without lesson" }
                ],
                trap_name: offer.trap_name
              });
            }
          }
          
          // Check for position coaching offers
          const positionCoachingOffers = data.messages.filter(msg => 
            msg.type === "position_coaching"
          );
          
          if (positionCoachingOffers.length > 0 && !positionCoaching) {
            const coaching = positionCoachingOffers[0];
            setPositionCoaching({
              structure_name: coaching.structure_name,
              structure_type: coaching.structure_type,
              game_phase: coaching.game_phase,
              main_idea: coaching.message,
              key_characteristics: coaching.key_characteristics || [],
              strategic_plans: coaching.strategic_plans || [],
              tactical_features: coaching.tactical_features || {},
              tactical_insights: coaching.tactical_insights || [],
              teaching_points: coaching.teaching_points || [],
              critical_squares: coaching.critical_squares || [],
              options: coaching.options || []
            });
          }
          
          // Filter out teaching offers from regular messages
          const regularMessages = data.messages.filter(msg => 
            msg.type !== "opening_teaching_offer" && msg.type !== "position_coaching"
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
            
            // Update currentInsight for clean UI mode (latest message)
            const latestCoachMsg = regularMessages.filter(m => m.type === "coach").pop();
            if (latestCoachMsg) {
              setCurrentInsight({
                quality: latestCoachMsg.trigger || latestCoachMsg.classification || "neutral",
                main_insight: latestCoachMsg.message,
                why: latestCoachMsg.detailed_feedback || null,
                next_idea: latestCoachMsg.question?.prompt || latestCoachMsg.socratic_question,
                has_better_move: false,
                can_explain: true,
                deeper_explanation: null
              });
              setIsCoachThinking(false);
            }
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
  }, []);

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


  // Keyboard arrow navigation — browse through move history
  const [browseIndex, setBrowseIndex] = useState(-1); // -1 = live position
  
  useEffect(() => {
    if (!session?.move_history) return;
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      const history = session.move_history || [];
      if (history.length === 0) return;
      
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setBrowseIndex(prev => {
          const newIdx = prev === -1 ? history.length - 2 : Math.max(0, prev - 1);
          const move = history[newIdx];
          if (move?.fen_before) setCurrentFen(move.fen_before);
          return newIdx;
        });
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        setBrowseIndex(prev => {
          if (prev === -1) return -1;
          const newIdx = prev + 1;
          if (newIdx >= history.length) {
            // Back to live position
            const lastMove = history[history.length - 1];
            if (lastMove?.fen_after) setCurrentFen(lastMove.fen_after);
            else setCurrentFen(session.current_fen);
            return -1;
          }
          const move = history[newIdx];
          if (move?.fen_before) setCurrentFen(move.fen_before);
          return newIdx;
        });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [session?.move_history, session?.current_fen]);

  // Reset browse when new moves come in
  useEffect(() => {
    if (browseIndex !== -1) {
      setBrowseIndex(-1);
    }
  }, [session?.move_history?.length]);

  // Auto-dismiss opening suggestions once past the opening phase
  useEffect(() => {
    const moves = session?.move_history || [];
    if (moves.length >= 14 && (inlineOpening || inlineTrap)) {
      setInlineOpening(null);
      setInlineTrap(null);
    }
  }, [session?.move_history?.length, inlineOpening, inlineTrap, setInlineOpening, setInlineTrap]);

  const checkActiveSession = async () => {
    try {
      const response = await fetch(`${API}/coach/play/active`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        if (data.active_sessions && data.active_sessions.length > 0 && !openingFromUrl) {
          // Resume existing session (but NOT if user came with a specific opening to practice)
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
        // Always ensure we have a valid FEN - fall back to starting position
        const validFen = data.current_fen || data.session?.current_fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
        setCurrentFen(validFen);
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
          
          // Fetch feedback for the last move on resume
          setTimeout(() => {
            fetchInteractiveCoaching(sessionId);
          }, 500);
        }
        
        if (data.is_player_turn) {
          setMoveStartTime(Date.now());
        } else if (!data.game_over) {
          // It's coach's turn - trigger coach to make a move
          // The coach might have been interrupted mid-move
          setTimeout(() => {
            triggerCoachMove(sessionId);
          }, 500);
        }
        
        // Restore teaching mode state if session is in teaching mode
        // Don't auto-resume - show suggestion to continue instead
        if (data.session.teaching_mode && data.session.teaching_data) {
          const td = data.session.teaching_data;
          const lessonName = td.trap_name || td.variation_name;
          // Show as a suggestion, not active teaching
          // User must click "Start" to continue the lesson
          if (td.trap_name) {
            setInlineTrap({
              name: lessonName,
              key: data.session.teaching_opening,
              moves: td.trap_moves || [],
              explanation: td.explanation
            });
          } else {
            setInlineOpening({
              name: lessonName,
              key: data.session.teaching_opening,
              main_idea: "Continue where you left off",
              key_moves: td.main_line_moves || []
            });
          }
          toast.info(`You were learning "${lessonName}" - click Start to continue`);
        }
        // If not in teaching mode, check for opening suggestion
        else if (data.opening_teaching && !data.game_over) {
          const ot = data.opening_teaching;
          const openingKey = ot.opening_key;
          const openingName = ot.opening_name || (openingKey ? openingKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : null);
          
          // Set trap suggestion if available
          if (ot.suggested_trap) {
            setInlineTrap({
              name: ot.suggested_trap.name,
              opening_key: openingKey,
              explanation: ot.suggested_trap.explanation || `A trap in the ${openingName || 'opening'}`,
              moves: ot.suggested_trap.moves || []
            });
          } else if (openingName) {
            setInlineOpening({
              name: openingName,
              key: openingKey,
              main_idea: ot.why || ot.guidance?.message || `Learn the ${openingName}`,
              key_moves: ot.first_moves || []
            });
          }
          
          // Also set opening guidance
          setOpeningGuidance(ot);
        }
        
        toast.success("Resumed your game!");
      }
    } catch (error) {
      console.error("Error resuming session:", error);
    }
  };

  useEffect(() => {
    if (!session?.session_id || openingCorrectionCount === 0) return;
    resumeSession(session.session_id);
  }, [openingCorrectionCount, session?.session_id]);
  
  // Trigger coach to make a move (used after resume when it's coach's turn)
  const triggerCoachMove = async (sessionId) => {
    setCoachThinking(true);
    setThinkingMessage("Coach is thinking...");
    
    try {
      const response = await fetch(`${API}/coach/play/trigger-coach-move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId })
      });
      
      // Read body once to avoid "body stream already read" errors
      const data = await response.json();
      if (response.ok) {
        if (data.success) {
          setCurrentFen(data.current_fen);
          setIsPlayerTurn(data.is_player_turn);
          
          if (data.coach_move) {
            toast.success(data.message || `Coach played ${data.coach_move}`);
            // Update last move highlight
            // The move format is UCI, parse it
            if (data.coach_move.length >= 4) {
              // For SAN moves, we need to get UCI from the API response
              // For now, just refetch the state to get proper lastMove
              setTimeout(() => {
                fetchInteractiveCoaching(sessionId);
              }, 500);
            }
          }
          
          setMoveStartTime(Date.now());
        } else {
          toast.info(data.message || "It's your turn!");
        }
      } else {
        toast.error(data.detail || "Couldn't get coach move");
      }
    } catch (error) {
      console.error("Error triggering coach move:", error);
      toast.error("Error getting coach move");
    } finally {
      setCoachThinking(false);
    }
  };

  const startGame = async () => {
    await actuallyStartGame();
  };
  
  const actuallyStartGame = async () => {
    setShowPreGameStreakPopup(false);
    setLoading(true);
    // Reset emotional state tracking for new game
    setBlundersThisGame(0);

    // Fetch active focus rule for pre-game banner
    try {
      const focusRes = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
      if (focusRes.ok) {
        const focusData = await focusRes.json();
        const coaching = focusData.coaching;
        if (coaching?.rule && coaching?.diagnosis) {
          setFocusRule({
            name: coaching.rule.name,
            rule: coaching.rule.rule,
            pattern: coaching.root_problem?.pattern,
          });
          setShowFocusBanner(true);
          // Auto-hide after 6 seconds
          setTimeout(() => setShowFocusBanner(false), 6000);
        }
      }
    } catch (e) { /* non-fatal */ }
    
    // Clear any stale teaching state from previous games
    setActiveLesson(null);
    setLessonInstruction(null);
    setIsInTeachingMode(false);
    setTeachingOffer(null);
    setInlineTrap(null);
    setInlineOpening(null);
    setOpeningGuidance(null);
    setLessonComplete(false);
    setPositionCoaching(null);
    
    try {
      // Build request body
      const requestBody = {
        user_color: selectedColor,
        time_control: timeControl,
      };

      // If user selected a specific opening to practice, pass it
      console.log("[CoachPlay] selectedOpening:", selectedOpening, "openingFromUrl:", openingFromUrl);
      if (selectedOpening) {
        requestBody.opening_name = selectedOpening;
        requestBody.guided_mode = guidedMode;
        console.log("[CoachPlay] Sending opening_name:", selectedOpening, "guided_mode:", guidedMode);
      }
      
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

      // Read body once to avoid "body stream already read" errors
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to start game");
      }
      setSession(data.session);
      // Ensure we have a valid FEN
      const validFen = data.current_fen || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
      setCurrentFen(validFen);
      setBoardOrientation(selectedColor);
      setIsPlayerTurn(data.is_player_turn);
      setGameStarted(true);
      setMoveStartTime(Date.now());

      // Set initial opening guidance — store ALL ideas for client-side arrows
      console.log("[CoachPlay] Start response openingGuidance:", data.openingGuidance);
      if (data.openingGuidance) {
        coachFlow.setOpeningGuidance(data.openingGuidance);
        // Store full ideas list for client-side guidance (no server dependency)
        if (data.openingGuidance.all_ideas?.length) {
          console.log("[CoachPlay] Loaded", data.openingGuidance.all_ideas.length, "opening move ideas, branch:", data.openingGuidance.branch?.name || "default");
          setOpeningIdeas(data.openingGuidance.all_ideas);
        }
        // Store branch info for variation awareness
        if (data.openingGuidance.branch) {
          setActiveBranch(data.openingGuidance.branch);
        }
        if (data.openingGuidance.all_branches) {
          setAllBranches(data.openingGuidance.all_branches);
        }
        if (data.openingGuidance.branch_point != null) {
          setBranchPoint(data.openingGuidance.branch_point);
        }
        // Store traps for client-side awareness
        if (data.openingGuidance.traps?.length) {
          console.log("[CoachPlay] Loaded", data.openingGuidance.traps.length, "traps for", data.openingGuidance.opening_key);
          setOpeningTraps(data.openingGuidance.traps);
        }
        setGamePly(0); // Reset ply counter for new game
      }

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
        // Coach already played move 0, so user's first move is at ply 1
        if (openingIdeas.length) setGamePly(1);
      }
      
      // Store intro message for coach panel (don't toast — show in panel instead)
      if (data.message) {
        setCoachIntroMessage(data.message);
      }
      
      // Fetch session state to get opening guidance info
      // (This is updated in DB after session creation)
      try {
        const stateResponse = await fetch(`${API}/coach/play/state/${data.session.session_id}`, {
          credentials: "include"
        });
        if (stateResponse.ok) {
          const stateData = await stateResponse.json();
          if (stateData.opening_teaching) {
            setOpeningGuidance(stateData.opening_teaching);
            
            // Also set inline suggestion for the prominent card
            // BUT only if game has actually started with some moves
            const moveCount = data.session?.move_history?.length || 0;
            
            // Only show opening guidance after a few moves (don't overwhelm at start)
            if (moveCount >= 2 && stateData.opening_teaching) {
              const ot = stateData.opening_teaching;
              const openingKey = ot.opening_key;
              const openingName = ot.opening_name || (openingKey ? openingKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : null);
              
              // Set trap suggestion if available (prioritize trap over opening)
              if (ot.suggested_trap) {
                setInlineTrap({
                  name: ot.suggested_trap.name,
                  opening_key: openingKey,
                  explanation: ot.suggested_trap.explanation || `A trap in the ${openingName || 'opening'}`,
                  moves: ot.suggested_trap.moves || []
                });
                
                // Also trigger trap alert for clean UI mode
                setActiveTrapAlert({
                  name: ot.suggested_trap.name,
                  message: ot.suggested_trap.explanation || `Watch out for the ${ot.suggested_trap.name}!`,
                  moves: ot.suggested_trap.moves || []
                });
              } else if (openingName) {
                // No trap, but we have an opening
                setInlineOpening({
                  name: openingName,
                  key: openingKey,
                  main_idea: ot.why || ot.teaching_message || ot.guidance?.message || `Learn the ${openingName}`,
                  key_moves: ot.first_moves || []
                });
              }
            }
          }
        }
      } catch (stateError) {
        console.error("Error fetching opening guidance:", stateError);
      }
    } catch (error) {
      toast.error(error.message || "Failed to start game");
    } finally {
      setLoading(false);
    }
  };

  // Fetch comprehensive move feedback after coach responds
  const fetchMoveFeedback = async () => {
    if (!session?.session_id) return;
    fetchMoveFeedbackForSession(session.session_id);
  };
  
  // Fetch feedback for a specific session ID (used for resume)
  const fetchMoveFeedbackForSession = async (sessionId) => {
    if (!sessionId) return;
    
    setLoadingFeedback(true);
    setIsCoachThinking(true);
    try {
      const response = await fetch(`${API}/coach/play/feedback/${sessionId}`, {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.feedback) {
          setMoveFeedback(data.feedback);

          // ═══ BOARD ANNOTATIONS — Draw arrows via props (not ref) ═══
          {
            const fb = data.feedback;
            const newArrows = [];

            // Show best move as green arrow when user made a mistake
            const q = fb.user_move_quality || fb.quality || "";
            if (fb.best_move_uci && ["mistake", "blunder", "inaccuracy"].includes(q)) {
              const uci = fb.best_move_uci;
              if (uci.length >= 4) {
                newArrows.push([uci.slice(0, 2), uci.slice(2, 4), "green"]);
              }
            }

            if (newArrows.length > 0) {
              setCoachArrows(newArrows);
              // Clear after 6 seconds
              setTimeout(() => setCoachArrows([]), 6000);
            } else {
              setCoachArrows([]);
            }
          }

          // Determine severity from quality
          const quality = data.feedback.user_move_quality || data.feedback.quality || "neutral";
          const severity = quality === "best" ? "good" :
                          quality === "good" ? "good" :
                          quality === "inaccuracy" ? "inaccuracy" :
                          quality === "mistake" ? "mistake" :
                          quality === "blunder" ? "blunder" : "good";
          
          // Transform to V5 format - NO EXTRA API CALL!
          // Use the analysis data that's already available
          const v5Data = {
            narrative: transformToFunLanguage(data.feedback, severity),
            severity: severity,
            current_problem: data.feedback.best_move_explanation || data.feedback.detailed_feedback,
            consequence: data.feedback.consequence || data.feedback.what_happens_next,
            better_approach: data.feedback.best_move ? 
              `${data.feedback.best_move} was better${data.feedback.best_move_explanation ? ` - ${data.feedback.best_move_explanation}` : ''}` : null,
            transferable_learning: data.feedback.pattern_reference || data.feedback.golden_rule || data.feedback.learning,
            concept_id: data.feedback.concept_id || data.feedback.pattern_id,
            candidate_moves: data.feedback.candidate_moves || transformCandidates(data.feedback),
            best_move: data.feedback.best_move,
            your_plan_now: data.feedback.suggestion || data.feedback.next_idea,
            move_san: data.feedback.user_move,
            fen_before: data.feedback.fen_before
          };
          
          setV5Coaching(v5Data);

          // Track fundamental violations for post-game summary
          if (v5Data.fundamental_violated) {
            setFundamentalViolations(prev => [...prev, {
              fundamental: v5Data.fundamental_violated,
              label: v5Data.fundamental_label,
            }]);
          }

          // Also update currentInsight for compatibility
          setCurrentInsight({
            quality: quality,
            main_insight: v5Data.narrative,
            why: v5Data.consequence || v5Data.current_problem,
            next_idea: v5Data.your_plan_now || v5Data.better_approach,
            has_better_move: data.feedback.best_move && data.feedback.best_move !== data.feedback.user_move,
            can_explain: !!v5Data.transferable_learning,
            deeper_explanation: v5Data.transferable_learning,
            best_move: data.feedback.best_move,
            candidate_moves: v5Data.candidate_moves,
            concept_id: v5Data.concept_id
          });
        }
      }
    } catch (error) {
      console.error("Error fetching move feedback:", error);
    } finally {
      setLoadingFeedback(false);
      setIsCoachThinking(false);
    }
  };
  
  // Phase 1: Fetch V5 coaching for user's move (called RIGHT after user plays)
  const fetchUserMoveCoaching = async (sessionId) => {
    if (!sessionId) return;
    
    setLoadingFeedback(true);
    
    try {
      const response = await fetch(`${API}/coach/play/v5/interactive-feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId, phase: "user_move" })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.user_move_coaching) {
          setV5Coaching(data.user_move_coaching);
          setInteractiveCoaching(prev => ({
            ...prev,
            userMoveCoaching: data.user_move_coaching
          }));

          // ═══ BOARD ARROWS from V5 coaching ═══
          const v5 = data.user_move_coaching;
          const sev = v5.severity || "";
          if (v5.best_move && v5.fen_before && ["mistake", "blunder", "inaccuracy"].includes(sev)) {
            try {
              // best_move is in SAN — we need to find UCI from the response
              // Check if best_move_uci exists directly or in raw feedback
              const rawUci = data.best_move_uci || v5.best_move_uci || "";
              if (rawUci && rawUci.length >= 4) {
                setCoachArrows([[rawUci.slice(0, 2), rawUci.slice(2, 4), "green"]]);
                setTimeout(() => setCoachArrows([]), 6000);
              }
            } catch (e) {}
          } else if (v5.trap_opportunity) {
            // Show trap opportunity on board — highlight escape squares + suggested reducer
            const trap = v5.trap_opportunity;
            const trapArrows = [];

            // Green arrow for suggested blocking move
            if (trap.reduction_moves && trap.reduction_moves.length > 0) {
              const reducer = trap.reduction_moves[0];
              if (reducer.from && reducer.to) {
                trapArrows.push([reducer.from, reducer.to, "green"]);
              }
            }

            // Red arrow pointing at the trapped piece (from nearest attacker if any)
            // For now just show the suggested move
            if (trapArrows.length > 0) {
              setCoachArrows(trapArrows);
              setTimeout(() => setCoachArrows([]), 8000);
            }
          } else {
            setCoachArrows([]);
          }
        }

        // Behavioral coaching (Smart Coach)
        setBehavioralCoaching(data.behavioral_coaching || null);
      }
    } catch (error) {
      console.error("Error fetching user move coaching:", error);
    } finally {
      setLoadingFeedback(false);
    }
  };
  
  // Phase 2: Fetch coach's move explanation (called AFTER coach responds)
  const fetchCoachMoveExplanation = async (sessionId) => {
    if (!sessionId) return;
    
    try {
      const response = await fetch(`${API}/coach/play/v5/interactive-feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId, phase: "coach_move" })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.coach_move_coaching) {
          setInteractiveCoaching(prev => ({
            ...prev,
            coachMoveCoaching: data.coach_move_coaching
          }));
        }

        // Pre-move trap prompt — show BEFORE user's next move
        if (data.pre_move_trap) {
          setPreMoveTrap(data.pre_move_trap);
          // Show trap arrows on board
          if (data.pre_move_trap.reduction_moves?.length > 0) {
            const r = data.pre_move_trap.reduction_moves[0];
            if (r.from && r.to) {
              setCoachArrows([[r.from, r.to, "green"]]);
              setTimeout(() => setCoachArrows([]), 10000);
            }
          }
        } else {
          setPreMoveTrap(null);
        }
      }
    } catch (error) {
      console.error("Error fetching coach move explanation:", error);
    }
  };
  
  // Combined fetch for resume/trigger (gets both at once)
  const fetchInteractiveCoaching = async (sessionId) => {
    if (!sessionId) return;
    
    setLoadingFeedback(true);
    
    try {
      const response = await fetch(`${API}/coach/play/v5/interactive-feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: sessionId })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        setInteractiveCoaching({
          userMoveCoaching: data.user_move_coaching || null,
          coachMoveCoaching: data.coach_move_coaching || null
        });
        
        if (data.user_move_coaching) {
          setV5Coaching(data.user_move_coaching);
        }
      }
    } catch (error) {
      console.error("Error fetching interactive coaching:", error);
    } finally {
      setLoadingFeedback(false);
    }
  };

  // Transform feedback message to fun V5 language
  const transformToFunLanguage = (feedback, severity) => {
    const move = feedback.user_move || "that move";
    const piece = feedback.piece_moved || "";
    
    // Fun language based on severity and piece
    if (severity === "good" || severity === "best") {
      const goodPhrases = [
        `Nice! ${move} is a solid choice!`,
        `Good thinking! ${move} works well here.`,
        `That's the spirit! ${move} keeps you in the game.`
      ];
      return goodPhrases[Math.floor(Math.random() * goodPhrases.length)];
    }
    
    if (piece?.toLowerCase().includes("knight") || move?.toLowerCase().startsWith("n")) {
      if (severity === "blunder" || severity === "mistake") {
        return `Naughty Knight! ${move} gets your Horsey in trouble!`;
      }
      return `Hmm, ${move} - what's your Horsey doing there?`;
    }
    
    if (piece?.toLowerCase().includes("bishop") || move?.toLowerCase().startsWith("b")) {
      return `Your Slicey Boi looks a bit sad after ${move}!`;
    }
    
    if (piece?.toLowerCase().includes("pawn") || /^[a-h]/.test(move?.toLowerCase() || "")) {
      return `Careful with ${move} - Little Soldiers can't go backwards!`;
    }
    
    if (severity === "blunder") {
      return `Oops! ${move} is a blunder - let's see why.`;
    }
    if (severity === "mistake") {
      return `${move} is a mistake - there was something better here.`;
    }
    if (severity === "inaccuracy") {
      return `${move} is okay, but there's a stronger idea here.`;
    }
    
    return feedback.coaching_message || feedback.explanation || `Let's look at ${move}.`;
  };
  
  // Transform existing feedback to candidate moves format
  const transformCandidates = (feedback) => {
    const candidates = [];
    
    // Add best move if available
    if (feedback.best_move && feedback.best_move !== feedback.user_move) {
      candidates.push({
        move: feedback.best_move,
        idea: feedback.best_move_explanation || `${feedback.best_move} was the engine's top choice`,
        type: feedback.best_move_type || "engine_choice",
        is_best: true
      });
    }
    
    // Add alternative moves if available
    if (feedback.alternative_moves) {
      for (const alt of feedback.alternative_moves.slice(0, 2)) {
        candidates.push({
          move: alt.move || alt,
          idea: alt.explanation || alt.idea || `${alt.move || alt} is another good option`,
          type: alt.type || "alternative",
          is_best: false
        });
      }
    }
    
    return candidates.length > 0 ? candidates : null;
  };

  // Fetch V5 coaching feedback - Same style as Lab!
  const fetchV5Coaching = async (moveSan, fenBefore, isUserMove = true, bestMove = null, pvAfterPlayed = [], cpLoss = 0) => {
    if (!session?.session_id) return;
    
    setLoadingFeedback(true);
    setIsCoachThinking(true);
    
    try {
      const response = await fetch(`${API}/coach/play/v5/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move_san: moveSan,
          fen_before: fenBefore,
          is_user_move: isUserMove,
          best_move: bestMove,
          pv_after_played: pvAfterPlayed,
          cp_loss: cpLoss
        })
      });
      
      if (response.ok) {
        const coaching = await response.json();
        setV5Coaching({
          ...coaching,
          move_san: moveSan,
          fen_before: fenBefore
        });
        
        // Also update currentInsight for compatibility with existing UI
        setCurrentInsight({
          quality: coaching.severity === "good" ? "good" : 
                   coaching.severity === "inaccuracy" ? "inaccuracy" :
                   coaching.severity === "mistake" ? "mistake" :
                   coaching.severity === "blunder" ? "blunder" : "neutral",
          main_insight: coaching.narrative || "Let's continue playing.",
          why: coaching.consequence || coaching.current_problem,
          next_idea: coaching.your_plan_now || coaching.better_approach,
          has_better_move: coaching.best_move && coaching.best_move !== moveSan,
          can_explain: !!coaching.transferable_learning,
          deeper_explanation: coaching.transferable_learning,
          best_move: coaching.best_move,
          // V5 specific fields
          candidate_moves: coaching.candidate_moves,
          concept_id: coaching.concept_id
        });
      }
    } catch (error) {
      console.error("Error fetching V5 coaching:", error);
    } finally {
      setLoadingFeedback(false);
      setIsCoachThinking(false);
    }
  };

  // Handle concept acknowledgment
  const handleAcknowledgeConcept = async (conceptId) => {
    if (!conceptId) return;
    
    try {
      await fetch(`${API}/coach/v5/concept/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          concept_id: conceptId,
          session_id: session?.session_id
        })
      });
      
      setAcknowledgedConcepts(prev => new Set([...prev, conceptId]));
    } catch (error) {
      console.error("Error acknowledging concept:", error);
    }
  };

  // Show alternative move on board (for clickable candidate moves)
  const showAlternativeMove = (moveSan) => {
    // Get the fen_before from the user move coaching data
    const fenBefore = v5Coaching?.fen_before || interactiveCoaching?.userMoveCoaching?.fen_before;
    
    if (!fenBefore) {
      console.warn("No fen_before available for alternative move preview");
      return;
    }
    
    try {
      const chess = new Chess(fenBefore);
      const result = chess.move(moveSan);
      
      if (!result) {
        console.error("Invalid move:", moveSan, "from FEN:", fenBefore);
        return;
      }
      
      // Show the alternative position on the board
      setCurrentFen(chess.fen());
      setLastMove([result.from, result.to]);
      
      // Draw arrow on the board if possible
      if (boardRef.current?.drawArrows) {
        boardRef.current.drawArrows([[result.from, result.to, "blue"]]);
      }
      
      // Auto-revert back to the real position after 3 seconds
      setTimeout(() => {
        if (session?.current_fen) {
          setCurrentFen(session.current_fen);
          setLastMove(null);
          if (boardRef.current?.clearArrows) {
            boardRef.current.clearArrows();
          }
        }
      }, 3000);
    } catch (error) {
      console.error("Error showing alternative move:", error);
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
  const [undoLoading, setUndoLoading] = useState(false);

  // Execute the move (called after guardian check passes or user confirms)
  const executeMove = async (moveSan, timeSpent, isOverride = false, riskType = null) => {
    // IMMEDIATELY clear all coaching state for clean transition
    setV5Coaching(null);
    setInteractiveCoaching({ userMoveCoaching: null, coachMoveCoaching: null });
    setBehavioralCoaching(null);
    setCurrentInsight(null);
    setConsequenceFeedback(null);
    setCurriculumFeedback(null);
    setIsCoachThinking(true);
    setLoadingFeedback(true);
    setEscapeSquaresQuiz(null);

    try {
      // If this is an override (user confirmed risky move), first log the confirmation
      if (isOverride) {
        const confirmResponse = await fetch(`${API}/coach/play/move/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            session_id: session.session_id,
            move: moveSan,
            risk_level: riskType
          })
        });
        
        if (confirmResponse.ok) {
          const confirmData = await confirmResponse.json();
          // Update remaining interventions
          if (confirmData.remaining_interventions !== undefined) {
            setRemainingInterventions(confirmData.remaining_interventions);
          }
        }
        // Continue to execute the move even if confirm fails
      }
      
      // Now execute the actual move via /move endpoint
      const response = await fetch(`${API}/coach/play/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveSan,
          thinking_time_ms: Math.round(timeSpent * 1000)
        })
      });

      // Read body once to avoid "body stream already read" errors
      const data = await response.json();
      if (!response.ok) {
        toast.error(data.detail || "Invalid move");
        return false;
      }
      
      // CURRICULUM ENFORCEMENT: Backend rejected the move
      if (data.curriculum_redirect) {
        toast.error(data.message || "That's not the right move for this lesson.", { duration: 4000 });
        setIsCoachThinking(false);
        setLoadingFeedback(false);
        return false;
      }
      
      // Store curriculum feedback for display in right panel
      if (data.curriculum_feedback) {
        setCurriculumFeedback(data.curriculum_feedback);
      } else {
        setCurriculumFeedback(null);
      }
      
      // Handle consequence feedback from pedagogical opponent
      if (data.consequence_feedback) {
        setConsequenceFeedback(data.consequence_feedback);
        // Unhide eval bar now that user has responded
        setHideEvalBar(false);
      }
      
      // Handle pedagogical state update
      if (data.pedagogical) {
        const ped = data.pedagogical;
        setHideEvalBar(ped.hide_eval || false);
        setOpportunitiesFound(ped.opportunities_found || 0);
        setOpportunitiesMissed(ped.opportunities_missed || 0);
      }
      
      // Update board with user's move immediately - only if we have valid FEN
      if (data.current_fen) {
        setCurrentFen(data.current_fen);
      }
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
        
        // Skip heavy V5 feedback when curriculum is handling coaching
        // The curriculum provides its own feedback via the opening-guide endpoint
        if (!session?.curriculum_active && !session?.teaching_opening) {
          fetchUserMoveCoaching(session.session_id);
        } else {
          setLoadingFeedback(false);
          setIsCoachThinking(false);
        }
        
        // Add thinking message to chat
        setChatMessages(prev => [...prev.filter(m => m.type !== "thinking"), {
          type: "thinking",
          message: THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)],
          timestamp: Date.now()
        }]);
        
        // Poll for coach's response
        pollForCoachResponse();
      } else {
        // No coach response expected - clear loading state
        setLoadingFeedback(false);
        setIsCoachThinking(false);
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
            
            // Update board - only if we have valid FEN
            setSession(data.session);
            if (data.current_fen) {
              setCurrentFen(data.current_fen);
            }
            
            // Update evaluation
            if (data.evaluation) {
              setEvaluation(data.evaluation);
            }
            
            // Handle pedagogical opponent state
            if (data.pedagogical) {
              const ped = data.pedagogical;
              setHideEvalBar(ped.hide_eval || false);
              setOpportunitiesFound(ped.opportunities_found || 0);
              setOpportunitiesMissed(ped.opportunities_missed || 0);
            }
            
            // Update opening guidance
            if (data.opening_teaching) {
              setOpeningGuidance(data.opening_teaching);
            } else {
              setOpeningGuidance(null);
            }
            
            // Highlight coach's last move
            const lastMove = data.session.last_coach_move;
            if (lastMove?.uci) {
              highlightMove(lastMove.uci);
            }
            // Track coach move SAN for display
            if (lastMove?.move || lastMove?.san) {
              setLastCoachMoveSan(lastMove.san || lastMove.move);
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
              // Increment ply for coach's response move
              if (openingIdeas.length) setGamePly(prev => prev + 1);
              // Check for escape squares teaching moment
              checkEscapeSquares();
            }
            
            setCoachThinking(false);
            
            // Skip heavy coaching fetch when curriculum is active
            if (!session?.curriculum_active && !session?.teaching_opening) {
              fetchCoachMoveExplanation(session.session_id);
            }
            
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
  
  // Request on-demand position explanation
  const requestPositionExplanation = async () => {
    if (!session) return;
    
    setIsCoachThinking(true);
    
    // Add user request to chat
    setChatMessages(prev => [...prev, {
      type: "user",
      message: "Coach, explain my position!",
      timestamp: Date.now()
    }]);
    
    try {
      const response = await fetch(`${API}/coach/play/explain-position`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Build a comprehensive explanation message
        let explanationParts = [];
        
        if (data.explanation?.structure_name) {
          explanationParts.push(`**Position Type: ${data.explanation.structure_name}**`);
        }
        
        if (data.explanation?.game_phase) {
          explanationParts.push(`You're in the ${data.explanation.game_phase} phase.`);
        }
        
        if (data.explanation?.main_idea) {
          explanationParts.push(data.explanation.main_idea);
        }
        
        if (data.explanation?.key_characteristics?.length > 0) {
          explanationParts.push("\n**Key features:**");
          data.explanation.key_characteristics.forEach(c => {
            explanationParts.push(`• ${c}`);
          });
        }
        
        if (data.plans?.length > 0) {
          explanationParts.push(`\n**Your strategic plan:** ${data.plans[0].name}`);
          explanationParts.push(data.plans[0].description);
        }
        
        if (data.tips?.length > 0) {
          explanationParts.push("\n**Tips:**");
          data.tips.forEach(tip => {
            explanationParts.push(`• ${tip}`);
          });
        }
        
        const fullMessage = explanationParts.join("\n");
        
        setChatMessages(prev => [...prev, {
          id: `explain_${Date.now()}`,
          type: "coach",
          message: fullMessage || "Let me analyze this position for you...",
          trigger: "position_explanation",
          timestamp: Date.now()
        }]);
        
        // Also set as current insight for the clean UI
        setCurrentInsight({
          quality: "info",
          main_insight: data.explanation?.main_idea || "Position analyzed",
          why: data.plans?.[0]?.description || null,
          next_idea: data.tips?.[0] || null,
          can_explain: false
        });
      } else {
        setChatMessages(prev => [...prev, {
          type: "coach",
          message: "I couldn't analyze this position right now. Try again!",
          timestamp: Date.now()
        }]);
      }
    } catch (error) {
      console.error("Position explanation error:", error);
      setChatMessages(prev => [...prev, {
        type: "coach",
        message: "Sorry, something went wrong. Let me try again later.",
        timestamp: Date.now()
      }]);
    } finally {
      setIsCoachThinking(false);
    }
  };
  
  // Send chat message to coach
  const sendChatMessage = async (directMessage = null) => {
    const messageToSend = directMessage || chatInput.trim();
    if (!messageToSend || !session) return;
    
    if (!directMessage) {
      setChatInput("");
    }
    
    // Special handling for "Explain my position" prompt
    if (messageToSend === "Explain my position") {
      await requestPositionExplanation();
      return;
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
    
    // Update board to show the move
    setCurrentFen(chess.fen());
    setIsPlayerTurn(false);
    
    // Clear intervention state
    clearGuardian();
    
    // Clear coaching state for clean transition
    setV5Coaching(null);
    setInteractiveCoaching({ userMoveCoaching: null, coachMoveCoaching: null });
    setBehavioralCoaching(null);
    setCurrentInsight(null);
    setConsequenceFeedback(null);
    setIsCoachThinking(true);
    setLoadingFeedback(true);

    try {
      // Confirm endpoint processes the move AND triggers coach response
      const confirmResponse = await fetch(`${API}/coach/play/move/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: session.session_id,
          move: moveSan,
          time_spent: timeSpent,
          risk_acknowledged: riskType
        })
      });

      const data = await confirmResponse.json();
      
      if (!confirmResponse.ok) {
        toast.error(data.detail || "Move failed");
        setCurrentFen(originalFen);
        setIsPlayerTurn(true);
        setIsCoachThinking(false);
        setLoadingFeedback(false);
        return;
      }

      // Update remaining interventions
      if (data.remaining_interventions !== undefined) {
        setRemainingInterventions(data.remaining_interventions);
      }

      // Update board with confirmed position
      if (data.current_fen) {
        setCurrentFen(data.current_fen);
      }

      // Check game over
      if (data.game_over) {
        setGameOver(true);
        setGameResult(data.result);
        setIsCoachThinking(false);
        setLoadingFeedback(false);
        return;
      }

      // Coach is now thinking — poll for response
      if (data.awaiting_coach) {
        setCoachThinking(true);
        setThinkingMessage(THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)]);
        fetchUserMoveCoaching(session.session_id);
        pollForCoachResponse();
      } else {
        setIsCoachThinking(false);
        setLoadingFeedback(false);
      }
    } catch (error) {
      console.error("Confirm move error:", error);
      toast.error("Connection error. Please try again.");
      setCurrentFen(originalFen);
      setIsPlayerTurn(true);
      setIsCoachThinking(false);
      setLoadingFeedback(false);
    }
  };

  const makeMove = useCallback(async (sourceSquare, targetSquare, piece) => {
    // If in teaching mode, use teaching move handler
    if (isInTeachingMode && activeLesson) {
      return await handleTeachingMove(sourceSquare, targetSquare);
    }

    // If in hold state, treat as move revision
    if (coachFlow.isInHold) {
      const chess = new Chess(currentFen);
      let moveObj;
      try {
        moveObj = chess.move({
          from: sourceSquare,
          to: targetSquare,
          promotion: piece?.[1]?.toLowerCase() === "p" ? "q" : undefined
        });
      } catch { return false; }
      if (!moveObj) return false;

      // Cancel current hold and re-evaluate with new move
      coachFlow.cancelPendingMove();
      // Reset board to pre-pending state
      const fenBefore = coachFlow.pendingMove?.fenBefore || currentFen;
      setCurrentFen(chess.fen());
      highlightMove(moveObj.from + moveObj.to);

      const timeSpent = moveStartTime ? (Date.now() - moveStartTime) / 1000 : 0;
      const moveData = {
        san: moveObj.san,
        uci: moveObj.from + moveObj.to + (moveObj.promotion || ""),
        from: moveObj.from,
        to: moveObj.to,
        promotion: moveObj.promotion || null,
        fenBefore: fenBefore,
        fenAfterPreview: chess.fen(),
        moveIndexPreview: (session?.move_history?.length || 0),
      };

      const { autoCommitted } = await coachFlow.handleUserMove(
        moveData,
        (san, ts) => executeMove(san, ts),
        timeSpent
      );

      if (autoCommitted) {
        setIsPlayerTurn(false);
      }
      return true;
    }

    if (!session || !isPlayerTurn || gameOver || !currentFen) return false;

    // Clear coaching state for new move
    setCoachArrows([]);
    setPreMoveTrap(null);
    setV5Coaching(null);
    setOpeningDeviation(null);

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

    // OPENING DEVIATION CHECK — if teaching is active and user plays wrong move
    if (openingIdeas.length && gamePly < openingIdeas.length) {
      const expected = openingIdeas[gamePly];
      const playedSan = moveObj.san.replace(/[+#]/g, "").toLowerCase();
      const expectedSan = (expected?.move || "").replace(/[+#]/g, "").toLowerCase();
      if (expectedSan && playedSan !== expectedSan) {
        // Check if this move matches ANOTHER variation of the same opening
        if (allBranches && branchPoint != null && gamePly === branchPoint) {
          const matchedBranch = Object.entries(allBranches).find(([key, b]) =>
            b.branch_move?.replace(/[+#]/g, "").toLowerCase() === playedSan
          );
          if (matchedBranch) {
            const [branchKey, branch] = matchedBranch;
            console.log("[CoachPlay] User played into variation:", branch.name, "(" + branchKey + ")");
            // Switch to this branch's ideas — it's a valid variation, not a deviation
            const commonIdeas = openingIdeas.slice(0, branchPoint);
            const branchIdeas = branch.ideas || [];
            setOpeningIdeas([...commonIdeas, ...branchIdeas]);
            setActiveBranch({ key: branchKey, name: branch.name, intro: branch.intro, branch_move: branch.branch_move, branch_point: branchPoint });
            setGamePly(prev => prev + 1);
            // Don't treat as deviation — fall through to normal move handling
            // Skip the rest of the deviation block
            setCurrentFen(chess.fen());
            highlightMove(moveObj.from + moveObj.to);
            const timeSpent2 = moveStartTime ? (Date.now() - moveStartTime) / 1000 : 0;
            const moveData2 = {
              san: moveObj.san, uci: moveObj.from + moveObj.to + (moveObj.promotion || ""),
              from: moveObj.from, to: moveObj.to, promotion: moveObj.promotion || null,
              fenBefore: currentFen, fenAfterPreview: chess.fen(),
              moveIndexPreview: (session?.move_history?.length || 0),
            };
            const { autoCommitted: ac2 } = await coachFlow.handleUserMove(moveData2, (san, ts) => executeMove(san, ts), timeSpent2);
            if (ac2) setIsPlayerTurn(false);
            return true;
          }
        }

        console.log("[CoachPlay] Opening deviation:", moveObj.san, "expected:", expected.move);

        // Save ideas before clearing — may need to restore if move is rejected
        const savedIdeas = [...openingIdeas];
        // Immediately stop arrows — prevent the effect from re-setting them during async eval
        setOpeningIdeas([]);
        setCoachArrows([]);
        coachFlow.setOpeningGuidance(null);

        // Show move on board temporarily so user sees what they played
        setCurrentFen(chess.fen());

        // Call evaluate-pending to check if this deviation is acceptable
        try {
          const evalRes = await fetch(`${API}/coach/play/evaluate-pending`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              sessionId: session.session_id,
              fenBefore: currentFen,
              uci: moveObj.from + moveObj.to + (moveObj.promotion || ""),
              moveIndexPreview: session?.move_history?.length || 0,
              userRating: session?.user_rating || 1200,
            }),
          });
          const evalData = evalRes.ok ? await evalRes.json() : null;
          const cpLoss = evalData?.moveEvaluation?.cpLoss || 0;
          const quality = evalData?.moveEvaluation?.moveQuality || "good";
          const isBadMove = ["mistake", "blunder"].includes(quality) || cpLoss > 100;

          console.log("[CoachPlay] Deviation eval:", quality, "cpLoss:", cpLoss, "bad:", isBadMove);

          if (isBadMove) {
            // BAD deviation — reset the move, explain why
            setCurrentFen(currentFen); // Reset board to before the move
            // Restore teaching ideas so user can try again with arrows
            setOpeningIdeas(savedIdeas);
            setOpeningDeviation({
              played: moveObj.san,
              expected: expected.move,
              idea: expected.idea,
              arrow: expected.arrow,
              branch: activeBranch?.name || selectedOpening,
              rejected: true,
              reason: evalData?.commentary?.summary
                || `${moveObj.san} loses position strength. The ${activeBranch?.name || "opening"} plan is ${expected.move}.`,
              quality,
              cpLoss,
            });
            // Show correct move arrow in green
            if (expected.arrow) {
              setCoachArrows([[expected.arrow[0], expected.arrow[1], "green"]]);
            }
            return false; // Move rejected — user must try again
          } else {
            // OK deviation — accept it, but stop teaching this line
            setOpeningDeviation({
              played: moveObj.san,
              expected: expected.move,
              idea: expected.idea,
              arrow: expected.arrow,
              branch: activeBranch?.name || selectedOpening,
              accepted: true,
              reason: `${moveObj.san} is a reasonable move, but it leaves the ${activeBranch?.name || "opening"} line. We'll continue from here.`,
            });
            // openingIdeas already cleared above — teaching is done
            // Increment ply and fall through to normal move handling
            setGamePly(prev => prev + 1);
          }
        } catch (err) {
          console.warn("[CoachPlay] Deviation eval failed, accepting move:", err);
          setOpeningIdeas([]);
          // Fall through to normal move handling
        }
      }
    }

    // Calculate time spent
    const timeSpent = moveStartTime ? (Date.now() - moveStartTime) / 1000 : 0;

    // GUARDIAN CHECK: Evaluate move before making it
    const guardianResult = await evaluateMove(moveObj.san);

    if (guardianResult?.should_intervene) {
      setGuardianPending(guardianResult, {
        moveSan: moveObj.san,
        moveObj: moveObj,
        timeSpent: timeSpent,
        riskType: guardianResult.risk_type,
        chess: chess,
        originalFen: currentFen
      });
      return false;
    }

    // ─── INSTANT BOARD UPDATE ─────
    // Increment ply for user's move (coach's response adds +1 in pollForCoachResponse)
    if (openingIdeas.length) setGamePly(prev => prev + 1);
    setCurrentFen(chess.fen());
    highlightMove(moveObj.from + moveObj.to);

    // ─── COACH FLOW: 400ms eval window ─────
    const moveData = {
      san: moveObj.san,
      uci: moveObj.from + moveObj.to + (moveObj.promotion || ""),
      from: moveObj.from,
      to: moveObj.to,
      promotion: moveObj.promotion || null,
      fenBefore: currentFen,
      fenAfterPreview: chess.fen(),
      moveIndexPreview: (session?.move_history?.length || 0),
    };

    const { autoCommitted } = await coachFlow.handleUserMove(
      moveData,
      (san, ts) => executeMove(san, ts),
      timeSpent
    );

    if (autoCommitted) {
      // Normal flow — move committed, wait for coach
      setIsPlayerTurn(false);
    }
    // If not auto-committed, we're in hold state — board shows the move,
    // but it's pending. Player can revise or tap clock to commit.

    return true;
  }, [session, currentFen, isPlayerTurn, gameOver, moveStartTime, isInTeachingMode, activeLesson, coachFlow, openingIdeas, gamePly, activeBranch, allBranches, branchPoint, selectedOpening]);

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
    clearGuardian();
    resetTeachingState();
    // Reset move feedback
    setMoveFeedback(null);
    setV5Coaching(null);
    setInteractiveCoaching({ userMoveCoaching: null, coachMoveCoaching: null });
    setBehavioralCoaching(null);
    setFundamentalViolations([]);
    coachFlow.resetFlow();
    setChatMessages([]);
    resetPlayerData();
    setEscapeSquaresQuiz(null);
    setOpeningIdeas([]);
    setGamePly(0);
    setActiveBranch(null);
    setAllBranches(null);
    setBranchPoint(null);
    setOpeningDeviation(null);
    setOpeningComplete(null);
    setOpeningTraps([]);
  };

  const canUndoLastMove = () => {
    if (!session || gameOver || undoLoading) return false;

    if (isInTeachingMode) {
      return Boolean(activeLesson && lessonInstruction);
    }

    return (session.move_history || []).some((move) => move.by === "player");
  };

  const handleUndoMove = async () => {
    if (!session?.session_id || undoLoading || gameOver) return;

    setUndoLoading(true);
    try {
      const response = await fetch(`${API}/coach/play/undo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ session_id: session.session_id })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.message || "Could not undo the move");
      }
      setCoachThinking(false);
      setLoadingFeedback(false);
      setMoveFeedback(null);
      setActiveTrapAlert(null);

      if (data.mode === "teaching") {
        if (data.teaching_fen) {
          setCurrentFen(data.teaching_fen);
        }
        if (data.instruction) {
          setLessonInstruction(data.instruction);
          setCurrentInsight({
            quality: "teaching",
            main_insight: data.message || `Undid ${data.undone_move}`,
            why: activeLesson?.opening_name ? `Back in ${activeLesson.opening_name}` : null,
            next_idea: data.instruction.is_user_move
              ? `Your turn: play ${data.instruction.move}`
              : `Watch: I'll play ${data.instruction.move}`,
            has_better_move: false,
            can_explain: true,
            teaching_mode: true,
            lesson_name: activeLesson?.lesson_name,
            remaining_moves: data.instruction.remaining
          });
        }

        setChatMessages((prev) => [
          ...prev.filter((msg) => msg.type !== "thinking"),
          {
            type: "coach",
            trigger: "teaching",
            message: data.message || `Undid ${data.undone_move}`,
            timestamp: Date.now()
          }
        ]);
      } else {
        setSession(data.session);
        setCurrentFen(data.current_fen);
        setIsPlayerTurn(data.is_player_turn);
        setGameOver(data.game_over);
        setOpeningGuidance(data.opening_teaching || null);
        setEvaluation(data.evaluation || { score: 0, mate_in: null });

        const latestMove = data.session?.move_history?.[data.session.move_history.length - 1];
        if (latestMove?.uci) {
          setLastMove([latestMove.uci.slice(0, 2), latestMove.uci.slice(2, 4)]);
        } else {
          setLastMove(null);
        }

        setCurrentInsight(null);
        setChatMessages((prev) => prev.filter((msg) => {
          if (msg.type === "thinking") return false;
          const moveNumber = msg.context?.move_number;
          return !moveNumber || moveNumber < data.undone_move_number;
        }));
      }

      toast.success(data.message || "Undid your last move");
    } catch (error) {
      console.error("Undo move error:", error);
      toast.error(error.message || "Failed to undo move");
    } finally {
      setUndoLoading(false);
    }
  };

  // ========================================
  // RENDER
  // ========================================

  // Pre-game setup screen
  if (!gameStarted) {
    return (
      <CoachPlaySetup
        user={user}
        loading={loading}
        practiceMode={practiceMode}
        practicePosition={practicePosition}
        selectedColor={selectedColor}
        setSelectedColor={setSelectedColor}
        selectedOpening={selectedOpening}
        setSelectedOpening={setSelectedOpening}
        guidedMode={guidedMode}
        setGuidedMode={setGuidedMode}
        pastGamesHistory={pastGamesHistory}
        playerIdentityData={playerIdentityData}
        startGame={startGame}
        showPreGameStreakPopup={showPreGameStreakPopup}
        setShowPreGameStreakPopup={setShowPreGameStreakPopup}
        actuallyStartGame={actuallyStartGame}
      />
    );
  }

  // Game screen
  return (
    <Layout user={user}>
      {/* Pre-game focus banner */}
      {showFocusBanner && focusRule && (
        <div className="bg-amber-500/10 border-b border-amber-500/15 px-4 py-3 flex items-center justify-between animate-in fade-in slide-in-from-top duration-300">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-amber-500/15 flex items-center justify-center flex-shrink-0">
              <Target className="w-3.5 h-3.5 text-amber-500" strokeWidth={2} />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">{focusRule.name}</p>
              <p className="text-xs text-foreground">{focusRule.rule}</p>
            </div>
          </div>
          <button onClick={() => setShowFocusBanner(false)} className="text-muted-foreground/40 hover:text-muted-foreground text-xs ml-4">
            &times;
          </button>
        </div>
      )}
      <div className="h-[calc(100vh-80px)] flex" data-testid="coach-play-game">
        {/* Left: Board + controls */}
        <CoachPlayBoard
          ref={boardRef}
          session={session}
          currentFen={currentFen}
          boardOrientation={boardOrientation}
          lastMove={lastMove}
          isPlayerTurn={isPlayerTurn}
          gameOver={gameOver}
          evaluation={evaluation}
          selectedColor={selectedColor}
          isInTeachingMode={isInTeachingMode}
          activeLesson={activeLesson}
          lessonInstruction={lessonInstruction}
          lessonComplete={lessonComplete}
          inlineOpening={inlineOpening}
          inlineTrap={inlineTrap}
          setInlineOpening={setInlineOpening}
          setInlineTrap={setInlineTrap}
          openingGuidance={openingGuidance}
          openingCorrectionCount={openingCorrectionCount}
          setOpeningCorrectionCount={setOpeningCorrectionCount}
          hideEvalBar={hideEvalBar}
          coachArrows={coachArrows}
          coachThinking={coachThinking}
          undoLoading={undoLoading}
          hasCastled={hasCastled}
          developedPieces={developedPieces}
          playerWeaknesses={playerWeaknesses}
          showChecklist={showChecklist}
          setShowChecklist={setShowChecklist}
          positionCoaching={positionCoaching}
          setPositionCoaching={setPositionCoaching}
          setChatMessages={setChatMessages}
          makeMove={makeMove}
          flipBoard={flipBoard}
          resignGame={resignGame}
          newGame={newGame}
          canUndoLastMove={canUndoLastMove}
          handleUndoMove={handleUndoMove}
          handleExitLesson={handleExitLesson}
          triggerCoachMove={triggerCoachMove}
          handleStartLesson={handleStartLesson}
          moveClassification={(() => {
            if (!lastMove) return null;
            // User move — from v5 coaching
            if (v5Coaching?.severity) {
              return { square: lastMove[1], type: v5Coaching.severity };
            }
            // Coach/opponent move — from interactive coaching
            const coachCoaching = interactiveCoaching?.coachMoveCoaching;
            if (coachCoaching?.severity) {
              return { square: lastMove[1], type: coachCoaching.severity };
            }
            return null;
          })()}
        />

        {/* Middle: Commentary panel (board reading) */}
        {(coachFlow.commentary || openingComplete || openingDeviation) ? (
          <div className="w-64 flex-shrink-0 border-l border-border overflow-y-auto">
            <CommentaryPanel
              commentary={coachFlow.commentary}
              openingGuidance={coachFlow.openingGuidance}
              trapWarning={coachFlow.trapWarning}
              openingDeviation={openingDeviation}
              activeBranch={activeBranch}
              openingComplete={openingComplete}
            />
          </div>
        ) : gameStarted && session && !gameOver ? (
          <div className="w-64 flex-shrink-0 border-l border-border p-3">
            <p className="text-xs text-muted-foreground/30">Board reading loading...</p>
          </div>
        ) : null}

        {/* Right: Coach panel */}
        <CoachPlaySidebar
          session={session}
          currentFen={currentFen}
          isPlayerTurn={isPlayerTurn}
          gameOver={gameOver}
          gameResult={gameResult}
          summary={summary}
          selectedColor={selectedColor}
          cleanUIMode={cleanUIMode}
          openingGuidance={openingGuidance}
          coachIntroMessage={coachIntroMessage}
          curriculumFeedback={curriculumFeedback}
          lastCoachMoveSan={lastCoachMoveSan}
          v5Coaching={v5Coaching}
          preMoveTrap={preMoveTrap}
          interactiveCoaching={interactiveCoaching}
          behavioralCoaching={behavioralCoaching}
          consequenceFeedback={consequenceFeedback}
          setConsequenceFeedback={setConsequenceFeedback}
          isCoachThinking={isCoachThinking}
          loadingFeedback={loadingFeedback}
          acknowledgedConcepts={acknowledgedConcepts}
          activeTrapAlert={activeTrapAlert}
          setActiveTrapAlert={setActiveTrapAlert}
          moveFeedback={moveFeedback}
          setMoveFeedback={setMoveFeedback}
          guardianIntervention={guardianIntervention}
          pendingMove={pendingMove}
          cancelRiskyMove={cancelRiskyMove}
          confirmRiskyMove={confirmRiskyMove}
          remainingInterventions={remainingInterventions}
          isInTeachingMode={isInTeachingMode}
          activeLesson={activeLesson}
          lessonInstruction={lessonInstruction}
          lessonComplete={lessonComplete}
          teachingOffer={teachingOffer}
          inlineOpening={inlineOpening}
          inlineTrap={inlineTrap}
          setInlineOpening={setInlineOpening}
          handleStartLesson={handleStartLesson}
          handleSkipTeachingOffer={handleSkipTeachingOffer}
          handleExitLesson={handleExitLesson}
          setOpeningGuidance={setOpeningGuidance}
          chatMessages={chatMessages}
          isSendingChat={isSendingChat}
          sendChatMessage={sendChatMessage}
          chatEndRef={chatEndRef}
          setFeedbackMessage={setFeedbackMessage}
          feedbackMessage={feedbackMessage}
          feedbackType={feedbackType}
          setFeedbackType={setFeedbackType}
          feedbackComment={feedbackComment}
          setFeedbackComment={setFeedbackComment}
          feedbackCorrectPattern={feedbackCorrectPattern}
          setFeedbackCorrectPattern={setFeedbackCorrectPattern}
          submitFeedback={submitFeedback}
          showAlternativeMove={showAlternativeMove}
          handleAcknowledgeConcept={handleAcknowledgeConcept}
          blundersThisGame={blundersThisGame}
          recentResults={recentResults}
          escapeSquaresQuiz={escapeSquaresQuiz}
          onEscapeQuizComplete={() => setEscapeSquaresQuiz(null)}
          newGame={newGame}
          coachTimeline={coachFlow.timeline}
          coachFlowState={coachFlow.interactionState}
          activeStripCoaching={coachFlow.activeStripCoaching}
          activeCoachingMoment={coachFlow.activeCoachingMoment}
          liveChecklist={coachFlow.liveChecklist}
          playerWeaknessList={coachFlow.playerWeaknessList}
          playerProfile={coachFlow.playerProfile}
          rootProblem={coachFlow.rootProblem}
          isInHold={coachFlow.isInHold}
          clockState={coachFlow.clockState}
          onClockTap={() => {
            const timeSpent = moveStartTime ? (Date.now() - moveStartTime) / 1000 : 0;
            coachFlow.handleClockTap(
              (san, ts) => executeMove(san, ts),
              timeSpent
            ).then(success => {
              if (success) setIsPlayerTurn(false);
            });
          }}
        />
      </div>

      {/* Level 3 Enforcement: Checkbox Modal */}
      {guardianIntervention && pendingMove && guardianIntervention.enforcement?.requires_checkbox && (
        <EnforcementCheckboxModal
          isOpen={true}
          riskType={guardianIntervention.risk_type || guardianIntervention.enforcement?.risk_type}
          repeatCount={guardianIntervention.enforcement?.repeat_count || 3}
          onConfirm={() => confirmRiskyMove()}
        />
      )}

      {/* Post-Game Streak Result */}
      {showPostGameStreakResult && postGameStreakResult && (
        <PostGameStreakResult
          result={postGameStreakResult}
          onContinue={() => setShowPostGameStreakResult(false)}
          onGoToTraining={() => navigate("/plateau-breaker/training")}
        />
      )}
    </Layout>
  );
};

export default CoachPlay;
