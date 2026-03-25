/**
 * OpeningsOverview.jsx → "Your Opening World"
 *
 * Personal opening portrait. Not an encyclopedia — a mirror.
 * Shows what you play, how well, your weakest opening as focus,
 * and progress from coach + real games.
 *
 * Uses existing endpoints:
 * - GET /api/openings/repertoire (what you play + win rates)
 * - GET /api/training/opening-progress (coach lessons + real game stats)
 */

import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
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
  Swords,
  Zap,
  CheckCircle2,
  AlertTriangle,
  GraduationCap,
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
  const [loading, setLoading] = useState(true);
  const [repertoire, setRepertoire] = useState(null);
  const [progress, setProgress] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [repRes, progRes] = await Promise.all([
        fetch(`${API}/openings/repertoire`, { credentials: "include" }),
        fetch(`${API}/training/opening-progress`, { credentials: "include" }),
      ]);

      if (repRes.ok) {
        const data = await repRes.json();
        setRepertoire(data);
      }
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

  // Find the weakest opening (needs most attention)
  const focusOpening = useMemo(() => {
    if (!progress.length) return null;

    // Prioritize: openings with real games + low win rate, then needs_work
    const candidates = progress
      .filter((p) => p.real_games >= 2 && p.real_win_rate < 55)
      .sort((a, b) => a.real_win_rate - b.real_win_rate);

    if (candidates.length > 0) return candidates[0];

    // Fallback: lowest accuracy with enough games
    const byAccuracy = progress
      .filter((p) => p.real_games >= 2 && p.real_accuracy > 0)
      .sort((a, b) => a.real_accuracy - b.real_accuracy);

    return byAccuracy.length > 0 ? byAccuracy[0] : null;
  }, [progress]);

  // Separate progress into coach-taught and played
  const coachTaught = useMemo(
    () => progress.filter((p) => p.coach_taught),
    [progress]
  );

  const allWhite = repertoire?.white_repertoire || [];
  const allBlack = repertoire?.black_repertoire || [];
  const totalGames =
    allWhite.reduce((s, o) => s + o.games_played, 0) +
    allBlack.reduce((s, o) => s + o.games_played, 0);

  if (loading) {
    return (
      <Layout user={user}>
        <div
          className="flex flex-col items-center justify-center min-h-[60vh] gap-4"
          data-testid="openings-loading"
        >
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading your opening world...</p>
        </div>
      </Layout>
    );
  }

  // Empty state
  if (totalGames === 0 && coachTaught.length === 0) {
    return (
      <Layout user={user}>
        <div
          className="flex flex-col items-center justify-center min-h-[60vh] gap-4"
          data-testid="openings-empty"
        >
          <BookOpen className="w-12 h-12 text-muted-foreground" />
          <h2 className="text-xl font-semibold">No Openings Yet</h2>
          <p className="text-muted-foreground text-center max-w-md">
            Play some games and your opening portrait will build itself.
          </p>
          <Button
            onClick={() => navigate("/play-with-coach")}
            data-testid="play-btn"
          >
            <Swords className="w-4 h-4 mr-2" />
            Play a Game
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout user={user}>
      <div
        className="max-w-4xl mx-auto py-4 px-4 space-y-6"
        data-testid="openings-overview"
      >
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold tracking-tight">Your Openings</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {totalGames} games analyzed
            {coachTaught.length > 0 &&
              ` · ${coachTaught.length} taught by coach`}
          </p>
        </div>

        {/* FOCUS OPENING — The prescription */}
        {focusOpening && (
          <FocusCard
            opening={focusOpening}
            allWhite={allWhite}
            allBlack={allBlack}
            onStudy={(key) => key && navigate(`/openings/${key}`)}
          />
        )}

        {/* AS WHITE */}
        {allWhite.length > 0 && (
          <RepertoireSection
            title="As White"
            icon={<Crown className="w-4 h-4 text-amber-400" />}
            openings={allWhite}
            progress={progress}
            onOpeningClick={(key) => key && navigate(`/openings/${key}`)}
          />
        )}

        {/* AS BLACK */}
        {allBlack.length > 0 && (
          <RepertoireSection
            title="As Black"
            icon={<Shield className="w-4 h-4 text-blue-400" />}
            openings={allBlack}
            progress={progress}
            onOpeningClick={(key) => key && navigate(`/openings/${key}`)}
          />
        )}

        {/* COACH PROGRESS */}
        {coachTaught.length > 0 && (
          <CoachProgress items={coachTaught} navigate={navigate} />
        )}
      </div>
    </Layout>
  );
};

/* ============================================================
 * FOCUS CARD — Your weakest opening, highlighted
 * ============================================================ */
const FocusCard = ({ opening, allWhite, allBlack, onStudy }) => {
  // Find library key from repertoire
  const all = [...allWhite, ...allBlack];
  const match = all.find(
    (o) => o.name.toLowerCase() === opening.opening_name?.toLowerCase()
  );
  const libraryKey = match?.library_key;
  const winRate = opening.real_win_rate || 0;
  const accuracy = opening.real_accuracy || 0;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card
        className="border-amber-500/30 bg-amber-500/5"
        data-testid="focus-opening"
      >
        <CardContent className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-amber-500" />
              <div>
                <p className="text-xs text-amber-400 uppercase tracking-wide font-medium">
                  Focus
                </p>
                <h2 className="font-semibold text-base mt-0.5">
                  {opening.opening_name}
                </h2>
              </div>
            </div>
            {libraryKey && (
              <Button
                size="sm"
                onClick={() => onStudy(libraryKey)}
                data-testid="study-focus-btn"
              >
                Study
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>

          <div className="grid grid-cols-3 gap-3 mt-3">
            <Stat
              label="Win Rate"
              value={`${winRate.toFixed(0)}%`}
              color={winRate >= 50 ? "text-emerald-400" : "text-red-400"}
            />
            <Stat
              label="Accuracy"
              value={accuracy > 0 ? `${accuracy.toFixed(0)}%` : "—"}
              color={accuracy >= 70 ? "text-emerald-400" : "text-amber-400"}
            />
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
 * REPERTOIRE SECTION — Your openings as white/black
 * ============================================================ */
const RepertoireSection = ({ title, icon, openings, progress, onOpeningClick }) => {
  // Match progress data
  const enriched = openings.map((o) => {
    const prog = progress.find(
      (p) => p.opening_name?.toLowerCase() === o.name?.toLowerCase()
    );
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
            onClick={() => onOpeningClick(o.library_key)}
          />
        ))}
      </div>
    </div>
  );
};

const OpeningRow = ({ opening, onClick }) => {
  const winRate = opening.win_rate || 0;
  const hasLibrary = !!opening.library_key;
  const mastery = opening.progress?.mastery_level || "unknown";
  const coachTaught = opening.progress?.coach_taught;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={`rounded-lg border border-border/50 p-3 ${
        hasLibrary
          ? "cursor-pointer hover:border-primary/40 transition-all"
          : "opacity-75"
      }`}
      onClick={hasLibrary ? onClick : undefined}
      data-testid={`opening-row-${opening.library_key || opening.name}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium truncate">{opening.name}</h3>
            {coachTaught && (
              <GraduationCap className="w-3.5 h-3.5 text-purple-400 shrink-0" title="Coach taught" />
            )}
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-muted-foreground">
              {opening.games_played} game{opening.games_played !== 1 ? "s" : ""}
            </span>
            {opening.avg_accuracy > 0 && (
              <span className="text-xs text-muted-foreground">
                {opening.avg_accuracy.toFixed(0)}% accuracy
              </span>
            )}
            {opening.learning_progress > 0 && (
              <div className="flex items-center gap-1">
                <div className="w-10 h-1 rounded-full bg-zinc-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{
                      width: `${Math.min(opening.learning_progress * 10, 100)}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {/* Win rate */}
          <div className="flex items-center gap-1">
            {winRate >= 50 ? (
              <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <TrendingDown className="w-3.5 h-3.5 text-red-400" />
            )}
            <span
              className={`text-sm font-medium ${
                winRate >= 50 ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {winRate.toFixed(0)}%
            </span>
          </div>

          {/* Mastery badge */}
          <Badge
            variant="outline"
            className={`text-xs px-1.5 py-0 ${
              masteryColors[mastery] || masteryColors.unknown
            }`}
          >
            {masteryLabels[mastery] || "New"}
          </Badge>

          {hasLibrary && (
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </div>
    </motion.div>
  );
};

/* ============================================================
 * COACH PROGRESS — Openings the coach has taught you
 * ============================================================ */
const CoachProgress = ({ items, navigate }) => {
  return (
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
                <span>
                  {item.times_practiced}x practiced
                </span>
                {item.real_games > 0 && (
                  <span
                    className={
                      item.real_win_rate >= 50
                        ? "text-emerald-400"
                        : "text-red-400"
                    }
                  >
                    {item.real_win_rate.toFixed(0)}% win in {item.real_games}{" "}
                    game{item.real_games !== 1 ? "s" : ""}
                  </span>
                )}
                {item.real_games === 0 && (
                  <span className="text-amber-400">Not tested in a game yet</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={`text-xs ${
                  masteryColors[item.mastery_level] || masteryColors.unknown
                }`}
              >
                {masteryLabels[item.mastery_level] || "Introduced"}
              </Badge>
              {item.real_games > 0 &&
                item.real_win_rate >= 50 && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                )}
              {item.needs_work && (
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default OpeningsOverview;
