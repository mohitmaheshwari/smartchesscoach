import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookOpen,
  ChevronRight,
  Crown,
  Sparkles,
  Swords,
  Target,
  X,
  Compass,
  ArrowRight,
  ShieldCheck,
  Zap,
} from "lucide-react";
import Layout from "@/components/Layout";
import ChessLoader from "@/components/ChessLoader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API } from "@/App";
import { ANALYTICS_EVENTS, trackCurriculum } from "@/lib/analytics";

const KNOWLEDGE_BANDS = [
  {
    id: "learn",
    title: "Needs Immediate Attention",
    badge: "High Priority",
    badgeColor: "bg-rose-500/15 text-rose-400 border border-rose-500/30",
    blurb: "You lose the most ground here in the first 12 moves. High impact area to fix first.",
  },
  {
    id: "drill",
    title: "Sharpen & Drill",
    badge: "Work in Progress",
    badgeColor: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
    blurb: "You know the main line, but slip on tricky responses. A little practice makes them solid.",
  },
  {
    id: "know",
    title: "Repertoire Strengths",
    badge: "Solid Foundation",
    badgeColor: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
    blurb: "You navigate these openings accurately. When games are lost here, it is during the middlegame or endgame.",
  },
];

function OpeningCard({ opening, onClick }) {
  const games = Number(opening.games_played || 0);
  const coachingSummary = (() => {
    if (opening.knowledge_band === "know") {
      return `Across ${games} game${games === 1 ? "" : "s"}, you handled early moves with confidence. We focus on mid-game plans here.`;
    }
    if (opening.knowledge_band === "drill") {
      return `Across ${games} game${games === 1 ? "" : "s"}, some early decisions are steady, but key variations need tightening.`;
    }
    if (opening.knowledge_band === "learn") {
      return `This opening has cost early evaluation drops across ${games} game${games === 1 ? "" : "s"}. We start with the recurring blunder.`;
    }
    return "Play a few more games with this opening to unlock deep pattern analysis.";
  })();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2 }}
      onClick={onClick}
      className="group relative cursor-pointer rounded-2xl border border-border bg-card/80 p-5 shadow-sm backdrop-blur-md transition-all hover:border-cyan-500/50 hover:shadow-md dark:border-zinc-800/80 dark:bg-zinc-950/70 dark:hover:shadow-[0_4px_24px_rgba(6,182,212,0.12)]"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-heading text-[16px] font-bold text-foreground group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors">
              {opening.name}
            </h3>
            {games > 0 && (
              <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                {games} {games === 1 ? "game" : "games"}
              </span>
            )}
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {coachingSummary}
          </p>
        </div>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-muted/60 border border-border text-muted-foreground transition-all group-hover:bg-cyan-500/10 group-hover:border-cyan-500/40 group-hover:text-cyan-600 dark:group-hover:text-cyan-400">
          <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 pt-2 border-t border-border/50">
        {opening.in_library && (
          <span className="inline-flex items-center gap-1 rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-cyan-700 dark:text-cyan-400 border border-cyan-500/20">
            <Zap className="h-3 w-3" /> Lesson Ready
          </span>
        )}
        {opening.traps_learned?.length > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700 dark:text-rose-400 border border-rose-500/20">
            <Target className="h-3 w-3" /> Trap Known
          </span>
        )}
        {Number(opening.independent_practice_completions || 0) > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="h-3 w-3" /> Mastered {opening.independent_practice_completions}x
          </span>
        )}
      </div>
    </motion.div>
  );
}

function RecommendedCard({ opening, onClick }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      onClick={onClick}
      className="group relative cursor-pointer overflow-hidden rounded-2xl border border-cyan-500/30 bg-gradient-to-br from-cyan-500/5 via-card to-card dark:from-cyan-950/40 dark:via-zinc-950 dark:to-zinc-950 p-6 shadow-md backdrop-blur-md transition-all hover:border-cyan-500/60 hover:shadow-lg dark:hover:shadow-[0_0_30px_rgba(6,182,212,0.18)]"
    >
      <div className="absolute right-0 top-0 h-28 w-28 translate-x-8 -translate-y-8 rounded-full bg-cyan-500/10 blur-2xl pointer-events-none" />
      <div className="flex items-start gap-3.5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-600 dark:text-cyan-400">
          <Sparkles className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-cyan-500/15 px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-cyan-700 dark:text-cyan-300 border border-cyan-500/20">
              Coach Recommended
            </span>
            {opening.focus_title && opening.focus_title !== opening.name && (
              <span className="text-[11px] font-medium text-muted-foreground">
                {opening.name}
              </span>
            )}
          </div>
          <h3 className="font-heading text-lg font-bold text-foreground mt-1.5 group-hover:text-cyan-600 dark:group-hover:text-cyan-300 transition-colors">
            {opening.focus_title || opening.name}
          </h3>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {opening.description}
          </p>
          {opening.reason && (
            <p className="mt-3 text-xs font-semibold leading-relaxed text-cyan-700 dark:text-cyan-400">
              💡 {opening.reason}
            </p>
          )}
          <div className="mt-4 flex items-center gap-1.5 text-xs font-bold text-cyan-600 dark:text-cyan-400 group-hover:text-cyan-500">
            <span>Start Practice</span>
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default function OpeningRepertoire({ user }) {
  const navigate = useNavigate();
  const shownRecommendationRef = useRef(null);
  const [repertoire, setRepertoire] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("white");
  const [showAllOpenings, setShowAllOpenings] = useState(false);
  const [allOpenings, setAllOpenings] = useState([]);

  useEffect(() => {
    const fetchRepertoire = async () => {
      try {
        const res = await fetch(`${API}/openings/repertoire`, { credentials: "include" });
        if (res.ok) setRepertoire(await res.json());

        const libraryResponse = await fetch(`${API}/openings/library`, { credentials: "include" });
        if (libraryResponse.ok) {
          const data = await libraryResponse.json();
          setAllOpenings(data.openings || []);
        }
      } catch (error) {
        console.error("Error fetching repertoire:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchRepertoire();
  }, []);

  useEffect(() => {
    const recommendation = (
      activeTab === "black"
        ? repertoire?.recommended_black
        : repertoire?.recommended_white
    )?.[0];
    if (!recommendation) return;
    const contentId = recommendation.library_key || recommendation.key;
    if (!contentId) return;
    const decisionId = `${activeTab}:${contentId}`;
    if (shownRecommendationRef.current === decisionId) return;
    shownRecommendationRef.current = decisionId;
    trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_DECISION_SHOWN, {
      surface: "opening_repertoire",
      decision_id: decisionId,
      decision_source: recommendation.from_your_games ? "player_games" : "new_ground",
      recommendation_kind: recommendation.focus_title && recommendation.focus_title !== recommendation.name
        ? "recurring_decision"
        : "opening_family",
      content_type: "opening",
      content_id: contentId,
      tab: activeTab,
      is_recommended: true,
    });
  }, [activeTab, repertoire]);

  const openLesson = (opening, isRecommended = false) => {
    const key = opening.library_key || opening.key;
    const playerColor = opening.player_color || activeTab;
    if (key && isRecommended) {
      trackCurriculum(ANALYTICS_EVENTS.CURRICULUM_PRIMARY_CLICKED, {
        surface: "opening_repertoire",
        decision_id: `${playerColor}:${key}`,
        decision_source: opening.from_your_games ? "player_games" : "new_ground",
        recommendation_kind: opening.focus_title && opening.focus_title !== opening.name
          ? "recurring_decision"
          : "opening_family",
        content_type: "opening",
        content_id: key,
        tab: playerColor,
        is_recommended: true,
      });
    }
    if (key) navigate(`/openings/${key}?player_color=${playerColor}`);
  };

  if (loading) {
    return (
      <Layout user={user}>
        <div className="grid min-h-[60vh] place-items-center">
          <ChessLoader />
        </div>
      </Layout>
    );
  }

  const sections = {
    white: {
      recommendations: repertoire?.recommended_white || [],
      played: repertoire?.white_repertoire || [],
      empty: "Play naturally as White. The coach will map your repertoire directly from the games you play.",
    },
    black: {
      recommendations: repertoire?.recommended_black || [],
      played: repertoire?.black_repertoire || [],
      empty: "Play naturally as Black. The coach will map your repertoire directly from the games you play.",
    },
  };
  const current = sections[activeTab];

  return (
    <Layout user={user}>
      <main className="max-w-6xl mx-auto px-4 py-8 md:py-10 space-y-8" data-testid="opening-repertoire-page">
        {/* Hero Section */}
        <header className="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-card via-card to-card/90 dark:border-zinc-800/80 dark:from-zinc-900/90 dark:via-zinc-950 dark:to-zinc-950 p-6 md:p-10 shadow-sm dark:shadow-2xl backdrop-blur-xl">
          <div className="absolute right-0 top-0 h-64 w-64 translate-x-16 -translate-y-16 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />
          <div className="relative z-10 max-w-2xl">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-600 dark:text-cyan-400">
                <BookOpen className="h-4 w-4" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-cyan-600 dark:text-cyan-400">
                Opening Intelligence
              </span>
            </div>
            <h1 className="font-heading text-3xl md:text-4xl font-extrabold tracking-tight text-foreground dark:text-white">
              Build Openings You Understand.
            </h1>
            <p className="mt-3 text-sm md:text-base leading-relaxed text-muted-foreground dark:text-zinc-400">
              We focus on the plans behind the positions you actually reach — not memorizing empty moves you’ll never play.
            </p>
          </div>
        </header>

        {/* Tab Switcher: White / Black */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <TabsList className="grid w-full sm:w-80 grid-cols-2 rounded-2xl bg-muted/80 border border-border dark:bg-zinc-900/90 dark:border-zinc-800 p-1.5">
              <TabsTrigger 
                value="white" 
                className="gap-2 rounded-xl text-xs font-semibold data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm dark:data-[state=active]:bg-cyan-500/20 dark:data-[state=active]:text-cyan-300 dark:data-[state=active]:border dark:data-[state=active]:border-cyan-500/40"
              >
                <Crown className="h-4 w-4" /> As White
              </TabsTrigger>
              <TabsTrigger 
                value="black" 
                className="gap-2 rounded-xl text-xs font-semibold data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm dark:data-[state=active]:bg-cyan-500/20 dark:data-[state=active]:text-cyan-300 dark:data-[state=active]:border dark:data-[state=active]:border-cyan-500/40"
              >
                <Swords className="h-4 w-4" /> As Black
              </TabsTrigger>
            </TabsList>

            <button 
              type="button" 
              onClick={() => setShowAllOpenings(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-border bg-card/80 hover:bg-muted text-xs font-semibold text-foreground dark:border-zinc-800 dark:bg-zinc-900/60 dark:hover:bg-zinc-800/80 dark:text-zinc-300 dark:hover:text-white transition-all shadow-sm"
            >
              <Compass className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
              <span>Explore All Lessons ({allOpenings.length})</span>
            </button>
          </div>

          {["white", "black"].map((color) => (
            <TabsContent key={color} value={color} className="space-y-10">
              {/* Coach Recommended Section */}
              {current.recommendations.length > 0 && (
                <section className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-cyan-400" />
                    <h2 className="font-heading text-lg font-bold text-white tracking-tight">
                      What I’d Teach Next
                    </h2>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {current.recommendations.map((opening, index) => (
                      <RecommendedCard 
                        key={opening.key || index} 
                        opening={opening} 
                        onClick={() => openLesson(opening, true)} 
                      />
                    ))}
                  </div>
                </section>
              )}

              {/* Observed in Your Games Section */}
              <section className="space-y-6">
                <div>
                  <h2 className="font-heading text-xl font-bold tracking-tight text-white">
                    Openings from Your Recent Games
                  </h2>
                  <p className="mt-1 text-xs text-zinc-400">
                    Grouped by how consistently you navigate the first 12 moves.
                  </p>
                </div>

                {current.played.length > 0 ? (
                  <div className="space-y-8">
                    {KNOWLEDGE_BANDS.map(({ id, title, badge, badgeColor, blurb }) => {
                      const group = current.played.filter(
                        (opening) => opening.knowledge_band === id
                      );
                      if (group.length === 0) return null;
                      return (
                        <div key={id} className="space-y-3">
                          <div className="flex items-center gap-3">
                            <h3 className="text-sm font-bold text-zinc-200">{title}</h3>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${badgeColor}`}>
                              {badge}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-500">{blurb}</p>
                          <div className="mt-3 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {group.map((opening, index) => (
                              <OpeningCard 
                                key={opening.key || `${id}-${index}`} 
                                opening={opening} 
                                onClick={() => openLesson(opening)} 
                              />
                            ))}
                          </div>
                        </div>
                      );
                    })}

                    {/* Needs more games */}
                    {current.played.some((opening) => !opening.knowledge_band) && (
                      <div className="space-y-3 pt-4 border-t border-zinc-900">
                        <h3 className="text-sm font-bold text-zinc-400">Analyzing More Games</h3>
                        <p className="text-xs text-zinc-500">
                          These openings need more matches before we determine your accuracy pattern.
                        </p>
                        <div className="mt-3 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                          {current.played
                            .filter((opening) => !opening.knowledge_band)
                            .map((opening, index) => (
                              <OpeningCard 
                                key={opening.key || `none-${index}`} 
                                opening={opening} 
                                onClick={() => openLesson(opening)} 
                              />
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-zinc-800/80 bg-zinc-950/60 p-8 text-center text-sm text-zinc-400">
                    <p>{current.empty}</p>
                  </div>
                )}
              </section>
            </TabsContent>
          ))}
        </Tabs>

        {/* Modal: Explore All Openings */}
        <AnimatePresence>
          {showAllOpenings && (
            <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4 backdrop-blur-md">
              <motion.section 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="max-h-[85vh] w-full max-w-3xl rounded-3xl border border-zinc-800 bg-zinc-950 shadow-2xl overflow-hidden flex flex-col"
              >
                <header className="flex items-center justify-between border-b border-zinc-800/80 p-5 bg-zinc-900/40">
                  <div className="flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                      <BookOpen className="h-4 w-4" />
                    </div>
                    <div>
                      <h2 className="font-heading text-lg font-bold text-white">Opening Lesson Library</h2>
                      <p className="text-xs text-zinc-400">Complete curriculum of theoretical and tactical lines</p>
                    </div>
                  </div>
                  <button 
                    type="button" 
                    onClick={() => setShowAllOpenings(false)} 
                    className="rounded-full p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 transition" 
                    aria-label="Close"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </header>
                <div className="flex-1 overflow-y-auto p-5">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {allOpenings.map((opening) => (
                      <button
                        key={opening.key}
                        type="button"
                        className="group flex items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 text-left transition-all hover:border-cyan-500/40 hover:bg-zinc-800/50"
                        onClick={() => {
                          navigate(`/openings/${opening.key}?player_color=${opening.color}`);
                          setShowAllOpenings(false);
                        }}
                      >
                        <div>
                          <h3 className="text-sm font-bold text-zinc-200 group-hover:text-cyan-400 transition-colors">
                            {opening.name}
                          </h3>
                          <span className="mt-1 inline-block text-[11px] font-mono text-zinc-500 uppercase">
                            Play as {opening.color}
                          </span>
                        </div>
                        <ChevronRight className="h-4 w-4 shrink-0 text-zinc-500 transition-transform group-hover:translate-x-1 group-hover:text-cyan-400" />
                      </button>
                    ))}
                  </div>
                </div>
              </motion.section>
            </div>
          )}
        </AnimatePresence>
      </main>
    </Layout>
  );
}
