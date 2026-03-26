/**
 * OpeningsOverview.jsx → "Study" page with Openings | Endgames tabs
 *
 * Personal opening portrait with inline interactive board preview.
 * Endgame lesson categories with direct links to interactive lessons.
 *
 * Uses existing endpoints:
 * - GET /api/openings/repertoire
 * - GET /api/training/opening-progress
 * - GET /api/openings/{key} (for inline board data)
 * - GET /api/endgames/categories (endgame lessons)
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Loader2,
  Crown,
  Shield,
  TrendingUp,
  TrendingDown,
  Target,
  BookOpen,
  ChevronRight,
  ChevronLeft,
  Swords,
  Zap,
  CheckCircle2,
  AlertTriangle,
  GraduationCap,
  RotateCcw,
  Expand,
  X,
  Castle,
  Lightbulb,
} from "lucide-react";

const masteryColors = {
  mastered: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  comfortable: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  learning: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  needs_work: "text-red-400 bg-red-500/10 border-red-500/30",
  introduced: "text-purple-400 bg-purple-500/10 border-purple-500/30",
  unknown: "text-zinc-400 bg-zinc-500/10 border-zinc-500/30",
};

const masteryLabels = {
  mastered: "Mastered",
  comfortable: "Comfortable",
  learning: "Learning",
  needs_work: "Needs Work",
  introduced: "Introduced",
  unknown: "New",
};

const OpeningsOverview = ({ user }) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get("tab") || "openings");
  const [loading, setLoading] = useState(true);
  const [repertoire, setRepertoire] = useState(null);
  const [progress, setProgress] = useState([]);
  const [expandedKey, setExpandedKey] = useState(null);
  const [endgameCategories, setEndgameCategories] = useState([]);
  const [endgameLoading, setEndgameLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (activeTab === "endgames" && endgameCategories.length === 0) {
      fetchEndgames();
    }
  }, [activeTab]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams(tab === "openings" ? {} : { tab });
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [repRes, progRes] = await Promise.all([
        fetch(`${API}/openings/repertoire`, { credentials: "include" }),
        fetch(`${API}/training/opening-progress`, { credentials: "include" }),
      ]);
      if (repRes.ok) setRepertoire(await repRes.json());
      if (progRes.ok) {
        const data = await progRes.json();
        setProgress(data.progress || []);
      }
    } catch (e) {
      console.error("Failed to load openings:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchEndgames = async () => {
    setEndgameLoading(true);
    try {
      const res = await fetch(`${API}/endgames/categories`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setEndgameCategories(data.categories || []);
      }
    } catch (e) {
      console.error("Failed to load endgames:", e);
    } finally {
      setEndgameLoading(false);
    }
  };

  const focusOpening = useMemo(() => {
    if (!progress.length) return null;
    const candidates = progress
      .filter((p) => p.real_games >= 2 && p.real_win_rate < 55)
      .sort((a, b) => a.real_win_rate - b.real_win_rate);
    if (candidates.length > 0) return candidates[0];
    const byAccuracy = progress
      .filter((p) => p.real_games >= 2 && p.real_accuracy > 0)
      .sort((a, b) => a.real_accuracy - b.real_accuracy);
    return byAccuracy.length > 0 ? byAccuracy[0] : null;
  }, [progress]);

  const coachTaught = useMemo(
    () => progress.filter((p) => p.coach_taught),
    [progress]
  );

  const allWhite = repertoire?.white_repertoire || [];
  const allBlack = repertoire?.black_repertoire || [];
  const totalGames =
    allWhite.reduce((s, o) => s + o.games_played, 0) +
    allBlack.reduce((s, o) => s + o.games_played, 0);

  const handleToggleExpand = useCallback(
    (key) => {
      setExpandedKey((prev) => (prev === key ? null : key));
    },
    []
  );

  if (loading && activeTab === "openings") {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="openings-loading">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div className="max-w-4xl mx-auto py-4 px-4 space-y-6" data-testid="openings-overview">
        {/* Header + Tabs */}
        <div>
          <h1 className="text-xl font-bold tracking-tight">Study</h1>
          <div className="flex gap-1 mt-3 bg-zinc-900 rounded-lg p-1 w-fit" data-testid="study-tabs">
            <button
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === "openings"
                  ? "bg-zinc-800 text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
              onClick={() => handleTabChange("openings")}
              data-testid="tab-openings"
            >
              Openings
            </button>
            <button
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === "endgames"
                  ? "bg-zinc-800 text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
              onClick={() => handleTabChange("endgames")}
              data-testid="tab-endgames"
            >
              Endgames
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === "openings" ? (
          <OpeningsTab
            totalGames={totalGames}
            coachTaught={coachTaught}
            focusOpening={focusOpening}
            allWhite={allWhite}
            allBlack={allBlack}
            progress={progress}
            expandedKey={expandedKey}
            handleToggleExpand={handleToggleExpand}
            navigate={navigate}
          />
        ) : (
          <EndgamesTab
            categories={endgameCategories}
            loading={endgameLoading}
            navigate={navigate}
          />
        )}
      </div>
    </Layout>
  );
};

/* ============================================================
 * OPENINGS TAB — existing openings content
 * ============================================================ */
const OpeningsTab = ({ totalGames, coachTaught, focusOpening, allWhite, allBlack, progress, expandedKey, handleToggleExpand, navigate }) => {
  if (totalGames === 0 && coachTaught.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4" data-testid="openings-empty">
        <BookOpen className="w-12 h-12 text-muted-foreground" />
        <h2 className="text-xl font-semibold">No Openings Yet</h2>
        <p className="text-muted-foreground text-center max-w-md">
          Play some games and your opening portrait will build itself.
        </p>
        <Button onClick={() => navigate("/play-with-coach")} data-testid="play-btn">
          <Swords className="w-4 h-4 mr-2" /> Play a Game
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="openings-tab-content">
      <p className="text-xs text-muted-foreground">
        {totalGames} games analyzed
        {coachTaught.length > 0 && ` · ${coachTaught.length} taught by coach`}
      </p>

        {focusOpening && (
          <FocusCard
            opening={focusOpening}
            allWhite={allWhite}
            allBlack={allBlack}
            onStudy={(key) => key && navigate(`/openings/${key}`)}
          />
        )}

        {allWhite.length > 0 && (
          <RepertoireSection
            title="As White"
            icon={<Crown className="w-4 h-4 text-amber-400" />}
            openings={allWhite}
            progress={progress}
            expandedKey={expandedKey}
            onToggleExpand={handleToggleExpand}
            onStudy={(key) => key && navigate(`/openings/${key}`)}
          />
        )}

        {allBlack.length > 0 && (
          <RepertoireSection
            title="As Black"
            icon={<Shield className="w-4 h-4 text-blue-400" />}
            openings={allBlack}
            progress={progress}
            expandedKey={expandedKey}
            onToggleExpand={handleToggleExpand}
            onStudy={(key) => key && navigate(`/openings/${key}`)}
          />
        )}

        {coachTaught.length > 0 && <CoachProgress items={coachTaught} navigate={navigate} />}
    </div>
  );
};

/* ============================================================
 * ENDGAMES TAB — category listing
 * ============================================================ */
const categoryIcons = {
  king_and_pawn: <Crown className="w-5 h-5 text-amber-400" />,
  rook_endgames: <Castle className="w-5 h-5 text-blue-400" />,
  queen_vs_pawn: <Zap className="w-5 h-5 text-purple-400" />,
};

const EndgamesTab = ({ categories, loading, navigate }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]" data-testid="endgames-loading">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!categories.length) {
    return (
      <div className="text-center py-12 text-muted-foreground" data-testid="endgames-empty">
        <p>No endgame lessons available yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="endgames-tab-content">
      <p className="text-xs text-muted-foreground">
        {categories.reduce((sum, c) => sum + c.lessons.length, 0)} lessons across {categories.length} categories
      </p>

      {categories.map((cat) => (
        <div key={cat.key} data-testid={`endgame-category-${cat.key}`}>
          <div className="flex items-center gap-2 mb-3">
            {categoryIcons[cat.key] || <Lightbulb className="w-5 h-5 text-zinc-400" />}
            <h2 className="text-sm font-semibold">{cat.name}</h2>
            <span className="text-xs text-muted-foreground">
              {cat.lessons.length} lesson{cat.lessons.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="space-y-2">
            {cat.lessons.map((lesson) => (
              <motion.div
                key={lesson.key}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="rounded-lg border border-border/50 p-3 cursor-pointer hover:border-primary/40 transition-all"
                onClick={() => navigate(`/endgames/${cat.key}/${lesson.key}`)}
                data-testid={`endgame-lesson-${lesson.key}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium">{lesson.name}</h3>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{lesson.description}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <Badge variant="outline" className="text-xs text-zinc-400 border-zinc-700">
                      {lesson.position_count} positions
                    </Badge>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

/* ============================================================
 * FOCUS CARD
 * ============================================================ */
const FocusCard = ({ opening, allWhite, allBlack, onStudy }) => {
  const all = [...allWhite, ...allBlack];
  const match = all.find((o) => o.name.toLowerCase() === opening.opening_name?.toLowerCase());
  const libraryKey = match?.library_key;
  const winRate = opening.real_win_rate || 0;
  const accuracy = opening.real_accuracy || 0;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="border-amber-500/30 bg-amber-500/5" data-testid="focus-opening">
        <CardContent className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-amber-500" />
              <div>
                <p className="text-xs text-amber-400 uppercase tracking-wide font-medium">Focus</p>
                <h2 className="font-semibold text-base mt-0.5">{opening.opening_name}</h2>
              </div>
            </div>
            {libraryKey && (
              <Button size="sm" onClick={() => onStudy(libraryKey)} data-testid="study-focus-btn">
                Study <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3">
            <Stat label="Win Rate" value={`${winRate.toFixed(0)}%`} color={winRate >= 50 ? "text-emerald-400" : "text-red-400"} />
            <Stat label="Accuracy" value={accuracy > 0 ? `${accuracy.toFixed(0)}%` : "—"} color={accuracy >= 70 ? "text-emerald-400" : "text-amber-400"} />
            <Stat label="Games" value={opening.real_games} color="text-zinc-300" />
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            {winRate < 40
              ? "This opening is costing you games. Study the key ideas and critical positions."
              : winRate < 55
              ? "You're close to comfortable here. A few targeted lessons could push you over."
              : "Improving steadily. Keep applying what you've learned."}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
};

const Stat = ({ label, value, color }) => (
  <div>
    <p className="text-xs text-muted-foreground">{label}</p>
    <p className={`text-lg font-semibold ${color}`}>{value}</p>
  </div>
);

/* ============================================================
 * REPERTOIRE SECTION with expandable inline board
 * ============================================================ */
const RepertoireSection = ({ title, icon, openings, progress, expandedKey, onToggleExpand, onStudy }) => {
  const enriched = openings.map((o) => {
    const prog = progress.find((p) => p.opening_name?.toLowerCase() === o.name?.toLowerCase());
    return { ...o, progress: prog };
  });

  return (
    <div data-testid={`repertoire-${title.toLowerCase().replace(/\s/g, "-")}`}>
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h2 className="text-sm font-semibold">{title}</h2>
        <span className="text-xs text-muted-foreground">
          {openings.length} opening{openings.length !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="space-y-2">
        {enriched.map((o, i) => (
          <OpeningRow
            key={`${o.name}-${i}`}
            opening={o}
            isExpanded={expandedKey === o.library_key}
            onToggleExpand={() => o.library_key && onToggleExpand(o.library_key)}
            onStudy={() => onStudy(o.library_key)}
          />
        ))}
      </div>
    </div>
  );
};

/* ============================================================
 * OPENING ROW with expandable inline board preview
 * ============================================================ */
const OpeningRow = ({ opening, isExpanded, onToggleExpand, onStudy }) => {
  const winRate = opening.win_rate || 0;
  const hasLibrary = !!opening.library_key;
  const mastery = opening.progress?.mastery_level || "unknown";
  const coachTaught = opening.progress?.coach_taught;

  return (
    <div data-testid={`opening-row-${opening.library_key || opening.name}`}>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={`rounded-lg border border-border/50 p-3 ${
          hasLibrary ? "cursor-pointer hover:border-primary/40 transition-all" : "opacity-75"
        } ${isExpanded ? "border-primary/40 bg-primary/5" : ""}`}
        onClick={hasLibrary ? onToggleExpand : undefined}
      >
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium truncate">{opening.name}</h3>
              {coachTaught && <GraduationCap className="w-3.5 h-3.5 text-purple-400 shrink-0" />}
            </div>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-muted-foreground">
                {opening.games_played} game{opening.games_played !== 1 ? "s" : ""}
              </span>
              {opening.avg_accuracy > 0 && (
                <span className="text-xs text-muted-foreground">{opening.avg_accuracy.toFixed(0)}% accuracy</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-1">
              {winRate >= 50 ? (
                <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5 text-red-400" />
              )}
              <span className={`text-sm font-medium ${winRate >= 50 ? "text-emerald-400" : "text-red-400"}`}>
                {winRate.toFixed(0)}%
              </span>
            </div>
            <Badge variant="outline" className={`text-xs px-1.5 py-0 ${masteryColors[mastery] || masteryColors.unknown}`}>
              {masteryLabels[mastery] || "New"}
            </Badge>
            {hasLibrary && (
              <ChevronRight
                className={`w-4 h-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-90" : ""}`}
              />
            )}
          </div>
        </div>
      </motion.div>

      {/* Inline board preview */}
      <AnimatePresence>
        {isExpanded && hasLibrary && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <InlineBoardPreview
              openingKey={opening.library_key}
              onStudy={onStudy}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

/* ============================================================
 * INLINE BOARD PREVIEW — Step through theory line
 * ============================================================ */
const InlineBoardPreview = ({ openingKey, onStudy }) => {
  const [lessonData, setLessonData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [moveIndex, setMoveIndex] = useState(-1);
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [lastMove, setLastMove] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setMoveIndex(-1);
    setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setLastMove(null);

    fetch(`${API}/openings/${openingKey}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) {
          setLessonData(data.opening || data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [openingKey]);

  const mainLine = useMemo(() => lessonData?.main_line || [], [lessonData]);
  const orientation = lessonData?.color || "white";
  const variations = lessonData?.variations || [];

  const goTo = useCallback(
    (idx) => {
      const target = Math.max(-1, Math.min(idx, mainLine.length - 1));
      const chess = new Chess();
      let lm = null;
      for (let i = 0; i <= target && i < mainLine.length; i++) {
        const move = chess.move(mainLine[i].move);
        if (move) lm = [move.from, move.to];
      }
      setMoveIndex(target);
      setFen(chess.fen());
      setLastMove(lm);
    },
    [mainLine]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!lessonData || mainLine.length === 0) {
    return (
      <div className="py-4 text-center text-xs text-muted-foreground">
        No theory data available for this opening.
      </div>
    );
  }

  const currentMoveData = moveIndex >= 0 ? mainLine[moveIndex] : null;

  return (
    <div className="mt-2 p-3 rounded-lg border border-border/30 bg-zinc-900/30" data-testid="inline-board-preview">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Board */}
        <div className="aspect-square max-w-[280px] mx-auto w-full" data-testid="preview-board">
          <LichessBoard
            fen={fen}
            orientation={orientation}
            viewOnly={true}
            lastMove={lastMove}
          />
        </div>

        {/* Controls + info */}
        <div className="flex flex-col justify-between">
          <div>
            <p className="text-xs text-muted-foreground mb-2">
              {moveIndex < 0
                ? "Starting position"
                : `Move ${Math.floor(moveIndex / 2) + 1}${moveIndex % 2 === 0 ? "." : "..."} ${currentMoveData?.move || ""}`}
            </p>

            {/* Move list */}
            <div className="flex flex-wrap gap-1 mb-3" data-testid="move-list">
              {mainLine.map((m, i) => (
                <button
                  key={i}
                  className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                    i === moveIndex
                      ? "bg-primary text-primary-foreground"
                      : i < moveIndex
                      ? "text-zinc-400 hover:bg-zinc-800"
                      : "text-zinc-500 hover:bg-zinc-800"
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    goTo(i);
                  }}
                  data-testid={`move-btn-${i}`}
                >
                  {i % 2 === 0 && `${Math.floor(i / 2) + 1}.`}
                  {m.move}
                </button>
              ))}
            </div>

            {/* Variations available */}
            {variations.length > 1 && (
              <p className="text-xs text-muted-foreground">
                {variations.length} variations available in full lesson
              </p>
            )}
          </div>

          {/* Navigation + Study button */}
          <div className="space-y-2 mt-3">
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={(e) => { e.stopPropagation(); goTo(-1); }}
                data-testid="preview-reset"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={(e) => { e.stopPropagation(); goTo(moveIndex - 1); }}
                disabled={moveIndex < 0}
                data-testid="preview-back"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>
              <span className="text-xs text-muted-foreground min-w-[50px] text-center">
                {moveIndex + 1} / {mainLine.length}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={(e) => { e.stopPropagation(); goTo(moveIndex + 1); }}
                disabled={moveIndex >= mainLine.length - 1}
                data-testid="preview-forward"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
            <Button
              size="sm"
              className="w-full"
              onClick={(e) => { e.stopPropagation(); onStudy(); }}
              data-testid="study-opening-btn"
            >
              <Expand className="w-3.5 h-3.5 mr-1.5" />
              Full Lesson
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ============================================================
 * COACH PROGRESS
 * ============================================================ */
const CoachProgress = ({ items, navigate }) => (
  <div data-testid="coach-progress">
    <div className="flex items-center gap-2 mb-3">
      <Zap className="w-4 h-4 text-purple-400" />
      <h2 className="text-sm font-semibold">Coach Taught</h2>
    </div>
    <div className="space-y-2">
      {items.map((item) => (
        <div
          key={item.opening_name}
          className="flex items-center justify-between p-3 rounded-lg border border-border/50"
          data-testid={`coach-item-${item.opening_name}`}
        >
          <div>
            <p className="text-sm font-medium">{item.opening_name}</p>
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
              <span>{item.times_practiced}x practiced</span>
              {item.times_applied_in_games > 0 && (
                <span className="text-emerald-400">
                  Applied {item.correct_applications || item.times_applied_in_games}x in games
                </span>
              )}
              {item.real_games > 0 ? (
                <span className={item.real_win_rate >= 50 ? "text-emerald-400" : "text-red-400"}>
                  {item.real_win_rate.toFixed(0)}% win in {item.real_games} game{item.real_games !== 1 ? "s" : ""}
                </span>
              ) : (
                <span className="text-amber-400">Not tested in a game yet</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={`text-xs ${masteryColors[item.mastery_level] || masteryColors.unknown}`}
            >
              {masteryLabels[item.mastery_level] || "Introduced"}
            </Badge>
            {item.real_games > 0 && item.real_win_rate >= 50 && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
            {item.needs_work && <AlertTriangle className="w-4 h-4 text-amber-400" />}
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default OpeningsOverview;
