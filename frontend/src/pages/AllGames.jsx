/**
 * GAME REVIEW — one coach-selected lesson first, complete archive second.
 */

import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import CurriculumStateStrip from "@/components/curriculum/CurriculumStateStrip";
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  ChevronLeft,
  Swords,
  Import,
  Sparkles,
} from "lucide-react";
import { CURRICULUM_ROUTES } from "@/lib/personalCurriculum";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";

const resultWord = (g) => {
  const r = String(g.result || "").toLowerCase().trim();
  if (r === "win" || r === "w") return "Won";
  if (r === "loss" || r === "l") return "Lost";
  if (r === "draw" || r === "d" || r === "1/2-1/2" || r === "½-½") return "Drew";
  const color = String(g.user_color || "").toLowerCase();
  if (r === "1-0") return color === "white" ? "Won" : "Lost";
  if (r === "0-1") return color === "black" ? "Won" : "Lost";
  return r ? r.charAt(0).toUpperCase() + r.slice(1) : "—";
};

const fmtDate = (g) => {
  const d = g.played_at || g.analyzed_at || g.created_at || g.date;
  if (!d) return "";
  const ts = new Date(d);
  const diffH = (Date.now() - ts.getTime()) / 3600000;
  if (diffH < 1) return `${Math.floor(diffH * 60)}m ago`;
  if (diffH < 24) return `${Math.floor(diffH)}h ago`;
  const days = Math.floor(diffH / 24);
  if (days < 7) return `${days}d ago`;
  return ts.toLocaleDateString();
};

const AllGames = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("imported");
  const [expandedGameId, setExpandedGameId] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [recommendationBusy, setRecommendationBusy] = useState(false);
  const [recommendationError, setRecommendationError] = useState("");
  const recommendationImpressionRef = useRef("");

  useEffect(() => {
    (async () => {
      try {
        await Promise.all([
          fetch(`${API}/lab-coach-pick`, { credentials: "include" })
            .then(async (res) => {
              if (res.ok) setData(await res.json());
            }),
          fetch(`${API}/game-review/recommendation`, {
            credentials: "include",
          }).then(async (res) => {
            if (!res.ok) throw new Error("recommendation unavailable");
            setRecommendation(await res.json());
          }).catch(() => {
            setRecommendation({ load_failed: true });
          }),
        ]);
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => {
    if (recommendation?.enabled !== true) return;
    const prescription = recommendation?.prescription;
    if (prescription) {
      const key = `${prescription.prescription_id}:${prescription.state}`;
      if (recommendationImpressionRef.current === key) return;
      recommendationImpressionRef.current = key;
      track(
        prescription.state === "started"
          ? ANALYTICS_EVENTS.GAME_REVIEW_PRESCRIPTION_RESUMED
          : ANALYTICS_EVENTS.GAME_REVIEW_PRESCRIPTION_SERVED,
        {
          surface: "game_review",
          state: prescription.state,
          chapter_count: prescription.chapters?.length || 0,
        },
      );
      return;
    }

    const emptyKey = `empty:${recommendation?.empty?.reason || "none"}`;
    if (recommendationImpressionRef.current === emptyKey) return;
    recommendationImpressionRef.current = emptyKey;
    track(ANALYTICS_EVENTS.GAME_REVIEW_NO_ELIGIBLE_GAME, {
      surface: "game_review",
      state: recommendation?.empty?.reason || "empty",
    });
    if (recommendation?.empty?.primary_action?.href) {
      track(ANALYTICS_EVENTS.GAME_REVIEW_FALLBACK_OFFERED, {
        surface: "game_review",
        action_kind: recommendation.empty.primary_action.href.includes("import")
          ? "import_games"
          : "play_with_coach",
      });
    }
  }, [recommendation]);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const coaching = data?.coaching;
  const groupedGames = coaching?.grouped_games || {};
  const allGamesRaw = coaching?.all_games?.length
    ? coaching.all_games
    : Object.values(groupedGames).flatMap(g => g.games || []);

  const seen = new Set();
  const uniqueGames = allGamesRaw.filter(g => {
    if (seen.has(g.game_id)) return false;
    seen.add(g.game_id);
    return true;
  });

  const sortByDate = (a, b) => {
    const da = new Date(a.analyzed_at || a.created_at || a.date || 0).getTime();
    const db = new Date(b.analyzed_at || b.created_at || b.date || 0).getTime();
    return db - da;
  };

  const coachGames = uniqueGames
    .filter(g => g.platform === "coach" || g.opponent === "Coach")
    .sort(sortByDate);
  const importedGames = uniqueGames
    .filter(g => g.platform !== "coach" && g.opponent !== "Coach")
    .sort(sortByDate);

  const activeGames = tab === "coach" ? coachGames : importedGames;
  const selected = recommendation?.prescription;
  const recommendationEnabled = recommendation?.enabled === true;
  const recommendationFailed = recommendation?.load_failed === true;

  const startSelectedReview = async () => {
    if (!selected?.prescription_id || recommendationBusy) return;
    setRecommendationBusy(true);
    setRecommendationError("");
    try {
      const res = await fetch(
        `${API}/game-review/recommendation/${selected.prescription_id}/start`,
        { method: "POST", credentials: "include" },
      );
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || !payload?.prescription?.review_url) {
        throw new Error(payload?.detail || "This review could not be opened.");
      }
      setRecommendation(payload);
      track(ANALYTICS_EVENTS.GAME_REVIEW_PRESCRIPTION_STARTED, {
        surface: "game_review",
        resumed: selected.state === "started",
        chapter_count: selected.chapters?.length || 0,
      });
      navigate(payload.prescription.review_url);
    } catch (error) {
      setRecommendationError(error.message);
    } finally {
      setRecommendationBusy(false);
    }
  };

  const dismissSelectedReview = async () => {
    if (!selected?.prescription_id || recommendationBusy) return;
    setRecommendationBusy(true);
    setRecommendationError("");
    try {
      const res = await fetch(
        `${API}/game-review/recommendation/${selected.prescription_id}/dismiss`,
        { method: "POST", credentials: "include" },
      );
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(payload?.detail || "I could not choose another game.");
      }
      track(ANALYTICS_EVENTS.GAME_REVIEW_PRESCRIPTION_DISMISSED, {
        surface: "game_review",
        state: "dismissed",
      });
      setRecommendation(payload);
    } catch (error) {
      setRecommendationError(error.message);
    } finally {
      setRecommendationBusy(false);
    }
  };

  const GameRow = ({ g }) => {
    const isExpanded = expandedGameId === g.game_id;
    const reviewState =
      recommendation?.review_states?.[g.game_id]
      || (g.reviewed ? "completed" : "not_reviewed");
    const reviewStateLabels = {
      recommended: "Coach’s pick",
      started: "In progress",
      completed: "Completed",
      dismissed: "Left for later",
      superseded: "Needs a fresh review",
      not_reviewed: "Not reviewed",
    };
    return (
      <div className="cg-panel overflow-hidden">
        <div
          onClick={() => setExpandedGameId(isExpanded ? null : g.game_id)}
          className="flex items-center justify-between p-4 hover:bg-emerald-500/[0.045] cursor-pointer transition-all group"
        >
          <div className="flex items-center gap-3 min-w-0">
            <Swords className="w-3.5 h-3.5 flex-shrink-0 text-muted-foreground/60" strokeWidth={2} />
            <div className="min-w-0 flex-1">
              <div className="text-sm text-foreground truncate">
                {resultWord(g)}
                {g.platform === "coach"
                  ? " vs Coach"
                  : g.opponent && g.opponent !== "Opponent"
                  ? ` vs ${g.opponent}`
                  : ""}
                {g.opening ? (
                  <span className="text-[10px] text-muted-foreground/40 ml-2">{g.opening}</span>
                ) : null}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`rounded-full px-2 py-1 text-[9px] font-medium ${
              reviewState === "started"
                ? "bg-amber-100 text-amber-800"
                : reviewState === "completed"
                  ? "bg-emerald-100 text-emerald-800"
                  : reviewState === "recommended"
                    ? "bg-lime-200 text-emerald-950"
                    : "bg-muted text-muted-foreground"
            }`}>
              {reviewStateLabels[reviewState] || "Not reviewed"}
            </span>
            <span className="text-[10px] text-muted-foreground/50">{fmtDate(g)}</span>
            <ChevronRight className={`w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-primary transition-all ${isExpanded ? "rotate-90" : ""}`} />
          </div>
        </div>

        {isExpanded && (
          <div className="px-3 pb-3 pt-1 bg-muted/20 border-t border-muted/30">
            {g.coach_take && (
              <p className="text-sm leading-relaxed text-foreground/85 mb-3">{g.coach_take}</p>
            )}
            {g.coach_line ? (
              <p className="text-[11px] text-muted-foreground/60 mb-2">
                {g.coach_line.charAt(0).toUpperCase() + g.coach_line.slice(1)}.
              </p>
            ) : g.critical_move ? (
              <p className="text-[11px] text-muted-foreground/60 mb-2">
                There is a turning point in this game worth looking at together.
              </p>
            ) : null}
            <button
              onClick={(e) => { e.stopPropagation(); navigate(`/game/${g.game_id}`); }}
              className="cg-primary-action !min-h-9 !px-4 !py-2 text-xs"
            >
              Review this with me
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <Layout user={user}>
      <div className="experience-page experience-utility-page experience-games-page cg-page max-w-[920px]" data-testid="all-games-page">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

          <CurriculumStateStrip user={user} surface="game_review" />

          {recommendationFailed ? (
            <section className="cg-hero" data-testid="coach-selected-review-error">
              <p className="cg-eyebrow">Game Review</p>
              <h1 className="cg-title !text-[clamp(2rem,4vw,3.35rem)]">
                I could not load the right game just now.
              </h1>
              <p className="cg-lede mt-3">
                Your game library is still here. I will not guess which game
                should be your next lesson.
              </p>
            </section>
          ) : recommendationEnabled ? (
            <section
              className="cg-hero overflow-hidden relative"
              data-testid="coach-selected-review"
            >
              <div className="absolute -right-16 -top-20 h-56 w-56 rounded-full bg-lime-300/20 blur-3xl" />
              <div className="relative">
                <div className="flex items-center gap-2 mb-5">
                  <button
                    onClick={() => navigate(CURRICULUM_ROUTES.home)}
                    className="p-1.5 rounded-lg hover:bg-muted/50 transition"
                    aria-label="Back to Home"
                  >
                    <ChevronLeft className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
                  </button>
                  <Sparkles className="w-4 h-4 text-emerald-700" />
                  <p className="cg-eyebrow">Your coach’s pick</p>
                </div>

                {selected ? (
                  <div className="grid gap-7 lg:grid-cols-[0.9fr_1.1fr]">
                    <div>
                      <p className="text-xs text-muted-foreground mb-3">
                        {selected.game.result} against {selected.game.opponent}
                        {selected.game.played_at ? ` · ${fmtDate(selected.game)}` : ""}
                      </p>
                      <h1 className="cg-title !text-[clamp(2rem,4vw,3.35rem)]">
                        {selected.state === "started"
                          ? "Let’s continue where we stopped."
                          : "This is the game I want to study with you."}
                      </h1>
                      <p className="text-lg font-medium text-foreground mt-5">
                        {selected.reason.headline}
                      </p>
                      <p className="cg-lede mt-2">{selected.reason.body}</p>
                      {selected.game.opening ? (
                        <p className="mt-4 text-xs text-muted-foreground">
                          The game began as {selected.game.opening}.
                        </p>
                      ) : null}
                      <div className="mt-7 flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={startSelectedReview}
                          disabled={recommendationBusy}
                          className="cg-primary-action"
                        >
                          {selected.state === "started"
                            ? "Continue this review"
                            : "Review this with me"}
                          <ArrowRight className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={dismissSelectedReview}
                          disabled={recommendationBusy}
                          className="px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground transition"
                        >
                          Choose a different game
                        </button>
                      </div>
                      {recommendationError ? (
                        <p className="mt-3 text-sm text-red-600" role="alert">
                          {recommendationError}
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-[24px] border border-emerald-900/10 bg-white/55 p-5 md:p-6 backdrop-blur">
                      <div className="flex items-center gap-2 mb-4">
                        <BookOpen className="w-4 h-4 text-emerald-700" />
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-800">
                          What we’ll uncover
                        </p>
                      </div>
                      <div className="space-y-4">
                        {selected.chapters.map((chapter, index) => (
                          <div
                            key={chapter.event_id}
                            className="grid grid-cols-[28px_1fr] gap-3"
                          >
                            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-950 text-xs text-white">
                              {index + 1}
                            </span>
                            <div>
                              <p className="text-sm font-semibold text-foreground">
                                {chapter.label}
                                {chapter.move_number ? ` · Move ${chapter.move_number}` : ""}
                              </p>
                              <p className="mt-1 text-sm leading-relaxed text-muted-foreground line-clamp-2">
                                {chapter.headline || chapter.explanation}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="max-w-2xl">
                    <p className="cg-eyebrow">No guesswork</p>
                    <h1 className="cg-title !text-[clamp(2rem,4vw,3.35rem)]">
                      {recommendation?.empty?.headline}
                    </h1>
                    <p className="cg-lede mt-3">{recommendation?.empty?.body}</p>
                    <div className="mt-6 flex flex-wrap gap-3">
                      <button
                        className="cg-primary-action"
                        onClick={() => navigate(recommendation?.empty?.primary_action?.href || "/play-with-coach")}
                      >
                        {recommendation?.empty?.primary_action?.label || "Play with Coach"}
                        <ArrowRight className="w-4 h-4" />
                      </button>
                      <button
                        className="px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground"
                        onClick={() => navigate(recommendation?.empty?.secondary_action?.href || "/import")}
                      >
                        {recommendation?.empty?.secondary_action?.label || "Import recent games"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </section>
          ) : (
            <div className="cg-hero">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate(CURRICULUM_ROUTES.home)}
                  className="p-1.5 rounded-lg hover:bg-muted/50 transition"
                  aria-label="Back to Home"
                >
                  <ChevronLeft className="w-4 h-4 text-muted-foreground" strokeWidth={2} />
                </button>
                <p className="cg-eyebrow">Your games</p>
              </div>
              <h1 className="cg-title !text-[clamp(2rem,5vw,3.6rem)]">Let’s find the moment worth understanding.</h1>
              <p className="cg-lede">
                You do not need to study every move. Choose a game and I’ll take you to the decision that can teach you something useful.
              </p>
            </div>
          )}

          <div id="all-games" className="pt-2">
            <p className="cg-eyebrow">Your game library</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">
              Every analyzed game, when you want it.
            </h2>
          </div>

          <div className="flex items-center gap-1 p-1 rounded-xl bg-muted/30 border border-border/40">
            <button
              onClick={() => { setTab("imported"); setExpandedGameId(null); }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                tab === "imported" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Games from your accounts
            </button>
            <button
              onClick={() => { setTab("coach"); setExpandedGameId(null); }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                tab === "coach" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Games with your coach
            </button>
          </div>

          {activeGames.length === 0 ? (
            <div className="cg-coach-card text-center py-10">
              <p className="text-sm text-muted-foreground/80 mb-4">
                {tab === "coach"
                  ? "We have not played together yet. One natural game is enough to begin."
                  : "Connect the place where you already play and I’ll start looking through your games."}
              </p>
              <button
                onClick={() => navigate(tab === "coach" ? "/play-with-coach" : "/import")}
                className="cg-primary-action text-xs"
              >
                {tab === "coach" ? <><Swords className="w-3.5 h-3.5" />Play with Coach</> : <><Import className="w-3.5 h-3.5" />Import games</>}
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {activeGames.map(g => <GameRow key={g.game_id} g={g} />)}
            </div>
          )}

        </motion.div>
      </div>
    </Layout>
  );
};

export default AllGames;
