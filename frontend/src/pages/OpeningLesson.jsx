import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessground } from "chessground";
import { 
  BookOpen, 
  ChevronLeft,
  ChevronRight,
  Play,
  RotateCcw,
  Target,
  Lightbulb,
  AlertTriangle,
  CheckCircle2,
  Brain,
  Sparkles,
  ExternalLink,
  MessageCircle
} from "lucide-react";
import ChessLoader from "@/components/ChessLoader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

import "chessground/assets/chessground.base.css";
import "chessground/assets/chessground.brown.css";
import "chessground/assets/chessground.cburnett.css";

import InteractivePractice from "@/components/openings/InteractivePractice";
import TrapPractice from "@/components/openings/TrapPractice";
import GuidedOpeningLesson from "@/components/openings/GuidedOpeningLesson";
import { OpeningCorrectionDialog } from "@/components/openings/OpeningCorrectionDialog";
import { API } from "@/App";
import { ANALYTICS_EVENTS, trackCurriculum } from "@/lib/analytics";

const OpeningLesson = () => {
  const { openingKey } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const boardRef = useRef(null);
  const groundRef = useRef(null);
  const chessRef = useRef(new Chess());
  const lessonStartedRef = useRef(null);
  
  // Get current game mistake passed from Lab page
  const currentGameMistake = location.state?.currentGameMistake;
  
  const [lesson, setLesson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [practiceOpen, setPracticeOpen] = useState(false);
  
  // Learning state
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  // Trap practice state
  const [selectedTrap, setSelectedTrap] = useState(null);
  const [trapPracticeMode, setTrapPracticeMode] = useState(false);
  const [plan, setPlan] = useState(null);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [openingKey]);
  
  // Fetch lesson data
  useEffect(() => {
    const fetchLesson = async () => {
      try {
        const res = await fetch(`${API}/openings/${openingKey}`, {
          credentials: "include"
        });
        if (res.ok) {
          const data = await res.json();
          setLesson(data);
          if (lessonStartedRef.current !== openingKey) {
            lessonStartedRef.current = openingKey;
            trackCurriculum(ANALYTICS_EVENTS.LESSON_STARTED, {
              surface: "legacy_opening_lesson",
              content_type: "opening",
              content_id: openingKey,
              origin: "lesson_route",
              is_recommended: false,
            });
          }
          // Reset board state when variation changes
          setCurrentMoveIndex(-1);
          chessRef.current.reset();
        } else {
          toast.error("Opening not found");
          navigate("/openings");
        }
      } catch (err) {
        console.error("Error fetching lesson:", err);
        toast.error("Failed to load lesson");
      } finally {
        setLoading(false);
      }
    };
    fetchLesson();
  }, [openingKey, navigate]);

  // The order the coach teaches in. Fetched alongside the opening so the
  // page never has to decide what comes first.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API}/openings/${openingKey}/lesson-plan`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setPlan(data);
      } catch {
        // The lesson still works without it; the thread falls back to the
        // main line rather than showing the student nothing.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [openingKey]);

  // Ping Engine 2 once per page visit to register "seen" on the matching
  // opening skill (if the tree has one). Fire-and-forget — don't block UI.
  // Also ticks the trap_set skill for this opening (same content_ref slug).
  useEffect(() => {
    if (!openingKey) return;
    const engine2Candidates = [
      `opening_${openingKey}_white`,
      `opening_${openingKey}_black`,
      `opening_${openingKey}`,
      `trap_set_${openingKey}`,
    ];
    (async () => {
      for (const skillId of engine2Candidates) {
        try {
          await fetch(`${API}/engine2/skill-seen`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ skill_id: skillId }),
          });
        } catch {
          // non-fatal — skill might not be in the tree, that's OK
        }
      }
    })();
  }, [openingKey]);
  
  // Resolve board orientation from whichever path has data. Before the
  // backend fix, `lesson.opening.color` was undefined for every lesson, so
  // every board rendered white-on-bottom. Now the API returns `color` both
  // at the top level (`lesson.color`) and nested (`lesson.opening.color`).
  // The URL key fallback handles explicit `_black` suffixes (`italian_game_black`).
  const resolvedOrientation =
    lesson?.color ||
    lesson?.opening?.color ||
    (openingKey?.toLowerCase().endsWith("_black") ? "black" : "white");

  // Initialize board
  useEffect(() => {
    if (boardRef.current && !groundRef.current) {
      groundRef.current = Chessground(boardRef.current, {
        fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        orientation: resolvedOrientation,
        movable: {
          free: false,
          color: undefined
        },
        animation: { duration: 300 },
        drawable: { enabled: true, visible: true }
      });
    }

    return () => {
      if (groundRef.current) {
        groundRef.current.destroy();
        groundRef.current = null;
      }
    };
  }, [lesson, resolvedOrientation]);

  // Update board orientation when lesson loads
  useEffect(() => {
    if (groundRef.current && resolvedOrientation) {
      groundRef.current.set({
        orientation: resolvedOrientation
      });
    }
  }, [resolvedOrientation]);
  
  // Update board position
  const updateBoard = useCallback((fen, lastMove = null) => {
    if (groundRef.current) {
      groundRef.current.set({
        fen,
        lastMove: lastMove ? [lastMove.slice(0, 2), lastMove.slice(2, 4)] : undefined
      });
    }
  }, []);

  // Play a mistake move on the board with an arrow. Resets to `fenBefore`
  // first, then after a short beat applies the move so chessground animates
  // the piece sliding, plus draws a colored arrow showing the move.
  // `brush`: "red" for the user's played move, "green" for the best move.
  const playMistakeMove = useCallback((fenBefore, moveUci, brush) => {
    if (!groundRef.current || !fenBefore || !moveUci || moveUci.length < 4) return;
    const from = moveUci.slice(0, 2);
    const to = moveUci.slice(2, 4);

    // Step 1: snap to the position *before* the move, clear any existing arrows.
    groundRef.current.set({
      fen: fenBefore,
      lastMove: undefined,
    });
    groundRef.current.setAutoShapes([]);

    // Step 2: after a beat, apply the move using chess.js for a clean FEN
    // and let chessground animate. Draw the arrow once the move lands.
    setTimeout(() => {
      try {
        const c = new Chess(fenBefore);
        const res = c.move({ from, to, promotion: moveUci[4] || "q" });
        if (!res) return;
        groundRef.current.set({
          fen: c.fen(),
          lastMove: [from, to],
        });
        groundRef.current.setAutoShapes([{ orig: from, dest: to, brush }]);
      } catch (e) {
        // Invalid move against this FEN — just draw the arrow on the before-position.
        groundRef.current.set({ fen: fenBefore });
        groundRef.current.setAutoShapes([{ orig: from, dest: to, brush }]);
      }
    }, 300);
  }, []);
  
  // Go to specific move in main line
  const goToMove = useCallback((index) => {
    if (!lesson?.opening?.main_line) return;
    
    chessRef.current.reset();
    let lastMove = null;
    
    for (let i = 0; i <= index && i < lesson.opening.main_line.length; i++) {
      const moveData = lesson.opening.main_line[i];
      const move = chessRef.current.move(moveData.move);
      if (move) {
        lastMove = move.from + move.to;
      }
    }
    
    setCurrentMoveIndex(index);
    updateBoard(chessRef.current.fen(), lastMove);
  }, [lesson, updateBoard]);
  
  // Trap practice - use TrapPractice component
  const startTrapPractice = useCallback((trap) => {
    setSelectedTrap(trap);
    setTrapPracticeMode(true);
    setPracticeOpen(true);
  }, []);
  
  const closeTrapPractice = useCallback(() => {
    setSelectedTrap(null);
    setTrapPracticeMode(false);
    // Reset board to opening start
    chessRef.current.reset();
    updateBoard(chessRef.current.fen());
  }, [updateBoard]);
  
  const onTrapComplete = useCallback(() => {
    // Record completion
    toast.success(`Mastered: ${selectedTrap?.name}!`);
  }, [selectedTrap]);

  // Finishing the thread hands the student straight to practice instead of
  // leaving them to find a tab.
  const onGuidedComplete = useCallback(() => {
    setPracticeOpen(true);
  }, []);

  const startGuidedPractice = useCallback(() => {
    trackCurriculum(ANALYTICS_EVENTS.EXPLANATION_COMPLETED, {
      surface: "legacy_opening_lesson",
      content_type: "opening",
      content_id: openingKey,
      origin: "lesson_route",
      is_recommended: false,
    });
    setPracticeOpen(true);
  }, [openingKey]);
  
  if (loading) {
    return (
      <ChessLoader fullPage />
    );
  }
  
  if (!lesson) return null;
  
  const { opening, user_stats, user_mistakes, learning_progress } = lesson;
  
  return (
    <div className="experience-page experience-lesson-page opening-lesson-shell min-h-screen bg-background">
      {/* Header */}
      <div className="opening-lesson-header border-b border-border/70 bg-card/80 backdrop-blur-xl">
        <div className="mx-auto max-w-[1440px] px-3 py-4 sm:px-6 sm:py-7 lg:px-8">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => navigate("/openings")}
            className="-ml-3 mb-2 h-8 text-muted-foreground hover:text-foreground sm:mb-3"
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Back to Repertoire
          </Button>
          
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 sm:h-11 sm:w-11">
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
              <div className="min-w-0">
                <p className="experience-eyebrow mb-1 text-[10px] font-bold uppercase">Opening lesson</p>
                <h1 className="truncate font-heading text-xl font-bold tracking-tight sm:text-3xl">{opening.name}</h1>
                <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
                  {opening.eco} • {opening.color === "white" ? "White Opening" : "Black Defense"}
                </p>
              </div>
            </div>

            <div className="flex w-full flex-wrap items-center gap-2 sm:ml-auto sm:w-auto sm:justify-end sm:gap-3">
              <OpeningCorrectionDialog
                sourceContext="openings_page"
                openingKey={openingKey}
                openingName={opening.name}
                variationName={opening.variation || null}
                trapName={selectedTrap?.name || null}
                currentMoves={(opening.main_line || []).map((moveData) => moveData.move)}
                currentFen={chessRef.current?.fen?.() || ""}
                triggerLabel="Correct opening data"
                compact={true}
              />
              {user_stats && (
                <div className="flex min-w-0 items-center gap-2 rounded-full border border-border/70 bg-background/65 px-2.5 py-1.5 sm:gap-3 sm:px-3">
                  <Badge variant={user_stats.win_rate >= 50 ? "default" : "destructive"}>
                    {user_stats.win_rate?.toFixed(0)}% win rate
                  </Badge>
                  <span className="whitespace-nowrap text-xs text-muted-foreground">
                    {user_stats.games_played} games
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="opening-lesson-main mx-auto max-w-[1440px] px-3 py-4 sm:px-6 sm:py-7 lg:px-8">
        {/* One coach-led thread. No variation chips and no tabs: deciding
            what someone should study next is the coaching, and a student who
            could pick between the Bishop's Line and the Frankenstein-Dracula
            would not need us. The traps and the student's own mistakes used
            to be tabs three and four, which is where the most useful thing on
            the page went to be ignored; they are chapters now. */}
        <div className="mx-auto max-w-6xl space-y-6">
          <GuidedOpeningLesson
            openingKey={openingKey}
            opening={opening}
            plan={plan}
            onComplete={onGuidedComplete}
            onStartPractice={startGuidedPractice}
          />

          {/* Practice is where the thread ends, not somewhere to go looking. */}
          {practiceOpen && (
            <div data-testid="lesson-practice">
              <InteractivePractice
                openingKey={openingKey}
                openingName={opening.name}
                userColor={opening.color}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default OpeningLesson;
