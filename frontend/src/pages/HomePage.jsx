/**
 * HOME — A text from your coach.
 *
 * Implements `redesign/01_Home.html`:
 *   - Greeting strip (one line, quiet)
 *   - Hero prescription (via <TodayHero/>, editorial variant)
 *   - Evidence (last session recap + optional improvement trend)
 *   - Nav tiles (quiet four-up)
 *
 * All data paths and onboarding flows are preserved from the previous
 * HomePage. Engine 1 + Engine 2 prescriptions are still driven by
 * /api/today inside <TodayHero/>. The old mood-based layered sections
 * ("celebrating / encouraging / confronting / neutral") collapse into a
 * single Evidence block that speaks in one voice regardless of mood.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import TodayHero from "@/components/TodayHero";
import {
  ChevronRight,
  Swords,
  FlaskConical,
  Target,
  BookOpen,
  Import,
  ArrowRight,
  TrendingUp,
} from "lucide-react";

// ─── Utilities ──────────────────────────────────────────────────────────────

const resultLabel = (session) => {
  const r = String(session?.result || "").toLowerCase();
  if (r === "win" || r === "w") return "Win";
  if (r === "loss" || r === "l") return "Loss";
  if (r === "draw" || r === "d" || r === "1/2-1/2") return "Draw";
  return null;
};

const timeOfDayGreeting = () => {
  const h = new Date().getHours();
  if (h < 5) return "Up late";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
};

const formatWhen = () => {
  const now = new Date();
  const day = now.toLocaleDateString(undefined, { weekday: "long" });
  const time = now.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  return `${day} · ${time}`;
};

// ─── Nav tiles (design spec) ────────────────────────────────────────────────

const NAV = [
  { id: "play", icon: Swords, label: "Play with Coach", sub: "coached games", href: "/play-with-coach" },
  { id: "lab", icon: FlaskConical, label: "Lab", sub: "review games", href: "/lab" },
  { id: "training", icon: Target, label: "Training", sub: "drill patterns", href: "/training" },
  { id: "openings", icon: BookOpen, label: "Openings", sub: "your repertoire", href: "/openings" },
];

// ─── Page ───────────────────────────────────────────────────────────────────

const HomePage = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hasGames, setHasGames] = useState(false);
  const [proof, setProof] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [homeRes, dashRes, proofRes] = await Promise.all([
          fetch(`${API}/home/coach-home`, { credentials: "include" }),
          fetch(`${API}/home/dashboard-v2`, { credentials: "include" }),
          fetch(`${API}/progress/improvement-proof`, { credentials: "include" }),
        ]);
        if (homeRes.ok) setData(await homeRes.json());
        if (dashRes.ok) {
          const d = await dashRes.json();
          if (d.games_analyzed > 0 || d.games_imported > 0) setHasGames(true);
        }
        if (proofRes.ok) {
          const proofData = await proofRes.json();
          setProof(proofData);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ─── Loading ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="w-6 h-6 border-2 border-violet-400/30 border-t-violet-400 rounded-full animate-spin" />
        </div>
      </Layout>
    );
  }

  // ─── Derived ─────────────────────────────────────────────────────────
  const greeting = data?.greeting || {};
  const coachGamesPlayed = greeting.games_together || 0;
  const lastSession = data?.last_session;

  // Pretty first name
  const rawName = user?.display_name || user?.name || user?.email?.split("@")[0] || "";
  const firstName = rawName.split(/[._-]/).filter(Boolean)[0] || "";
  const displayName =
    firstName.length <= 12
      ? firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase()
      : "";

  // ─── New user onboarding (no games yet) ──────────────────────────────
  if (!hasGames && !lastSession) {
    return (
      <Layout user={user}>
        <div
          className="max-w-[640px] mx-auto px-6 md:px-10 py-12 md:py-16"
          data-testid="home-page"
        >
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-12"
          >
            {/* Greeting */}
            <div className="flex items-baseline justify-between">
              <p className="text-muted-foreground text-[13px]">
                {displayName
                  ? `${timeOfDayGreeting()}, ${displayName}.`
                  : `${timeOfDayGreeting()}.`}
              </p>
              <p className="text-muted-foreground/60 text-[11px] uppercase tracking-[0.22em]">
                {formatWhen()}
              </p>
            </div>

            {/* Welcome hero */}
            <section>
              <p className="text-[10.5px] uppercase tracking-[0.22em] text-violet-500 dark:text-violet-300/80 font-semibold mb-5">
                First session
              </p>
              <h1 className="font-serif text-[32px] md:text-[44px] leading-[1.06] tracking-[-0.02em] font-medium text-foreground max-w-[560px]">
                I'm your personal chess coach. Let's find out how you play.
              </h1>
              <p className="mt-6 text-[14px] text-muted-foreground max-w-[520px] leading-relaxed">
                {coachGamesPlayed === 0
                  ? "Play a game and I'll watch how you think. No preparation — your natural game is what I need to see."
                  : coachGamesPlayed < 3
                    ? `We've played ${coachGamesPlayed} game${coachGamesPlayed > 1 ? "s" : ""} together. ${3 - coachGamesPlayed} more and I'll have your full profile.`
                    : "Your profile is ready. Let's keep working."}
              </p>

              <div className="mt-10 flex flex-wrap items-center gap-5">
                <button
                  onClick={() => navigate("/play-with-coach")}
                  className="h-12 px-7 rounded-xl bg-violet-500 hover:bg-violet-400 text-white font-medium text-[15px] transition-colors inline-flex items-center gap-2"
                >
                  <Swords className="h-4 w-4" strokeWidth={2} />
                  {coachGamesPlayed === 0 ? "Play my first game" : "Play another game"}
                  <ArrowRight className="h-4 w-4" strokeWidth={2} />
                </button>
              </div>
            </section>

            {/* Already have an account? */}
            <section className="pt-8 border-t border-border/60">
              <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-3">
                Already play elsewhere?
              </p>
              <p className="text-[13.5px] text-muted-foreground mb-5 leading-relaxed max-w-[480px]">
                Connect your Chess.com or Lichess account and I'll analyze your
                existing games. Instant profile — no games with me needed.
              </p>
              <button
                onClick={() => navigate("/import")}
                className="text-[13px] text-foreground hover:underline transition-colors inline-flex items-center gap-1.5"
              >
                <Import className="h-3.5 w-3.5" strokeWidth={1.75} />
                Connect Chess.com or Lichess
              </button>
            </section>
          </motion.div>
        </div>
      </Layout>
    );
  }

  // ─── Evidence data ───────────────────────────────────────────────────
  const lastResult = resultLabel(lastSession);
  const lastBoard = lastSession?.critical_fen || lastSession?.board_fen;
  const lastStory = lastSession?.story;
  const lastAccuracy = lastSession?.accuracy;
  const lastMoves = lastSession?.total_moves;
  const hasEvidence = Boolean(lastStory || lastBoard);

  // Improvement trend — optional
  const trendShowing =
    proof?.has_data &&
    (proof.primary_pattern?.reduction_pct > 0 ||
      proof.streaks?.no_big_mistake_games >= 3);

  // ─── Main render ─────────────────────────────────────────────────────
  return (
    <Layout user={user}>
      <div
        className="max-w-[880px] mx-auto px-6 md:px-10 py-10 md:py-16"
        data-testid="home-page"
      >
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {/* ─── Greeting strip ─── */}
          <div className="flex items-baseline justify-between mb-10 md:mb-12">
            <p className="text-muted-foreground text-[13px]">
              {displayName
                ? `${timeOfDayGreeting()}, ${displayName}.`
                : `${timeOfDayGreeting()}.`}
            </p>
            <p className="text-muted-foreground/60 text-[11px] uppercase tracking-[0.22em]">
              {formatWhen()}
            </p>
          </div>

          {/* ━━ HERO PRESCRIPTION (via TodayHero) ━━ */}
          <section className="mb-16 md:mb-20">
            <TodayHero />
          </section>

          {/* ━━ EVIDENCE ━━ */}
          {hasEvidence && (
            <section className="mb-16 md:mb-20">
              <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
                Evidence
              </div>

              <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-8 md:gap-10 items-start">
                {/* Board thumb */}
                {lastBoard && (
                  <div>
                    <div className="rounded-lg overflow-hidden ring-1 ring-border w-[168px]">
                      <LichessBoard fen={lastBoard} viewOnly={true} width={168} />
                    </div>
                    <div className="mt-3 text-[11px] tabular-nums text-muted-foreground leading-relaxed">
                      {lastSession?.opponent && (
                        <>vs {lastSession.opponent}</>
                      )}
                      {lastSession?.opponent_rating && (
                        <> · {lastSession.opponent_rating}</>
                      )}
                      <br />
                      {[
                        lastResult,
                        lastAccuracy != null ? `${lastAccuracy}% acc` : null,
                        lastMoves != null ? `${lastMoves} moves` : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                  </div>
                )}

                {/* Story + trend + link */}
                <div className="pt-1 space-y-6">
                  {lastStory && (
                    <p className="font-serif italic text-[17px] md:text-[18px] text-foreground leading-snug max-w-[440px]">
                      "{lastStory}"
                    </p>
                  )}

                  {trendShowing && (
                    <div className="flex items-baseline gap-4">
                      <TrendingUp
                        className="h-4 w-4 text-emerald-500 shrink-0"
                        strokeWidth={2}
                      />
                      <div>
                        <p className="font-serif text-[17px] md:text-[19px] text-emerald-600 dark:text-emerald-400 leading-snug tracking-[-0.01em]">
                          <span className="tabular-nums font-medium">
                            {proof.primary_pattern?.reduction_pct}% fewer
                          </span>{" "}
                          {proof.primary_pattern?.label?.toLowerCase() || "mistakes"}
                        </p>
                        <p className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground mt-1.5 font-medium">
                          30-day trend
                        </p>
                      </div>
                    </div>
                  )}

                  <button
                    onClick={() => navigate("/lab")}
                    className="inline-flex items-center gap-1.5 text-[12.5px] text-violet-500 dark:text-violet-300 hover:text-violet-400 dark:hover:text-violet-200 transition-colors group"
                  >
                    Open in Lab
                    <ChevronRight
                      className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
                      strokeWidth={2}
                    />
                  </button>
                </div>
              </div>
            </section>
          )}

          {/* ━━ NAV TILES — quiet row ━━ */}
          <section>
            <div className="text-[10.5px] uppercase tracking-[0.22em] text-muted-foreground font-semibold mb-5">
              Elsewhere
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {NAV.map((n) => (
                <button
                  key={n.id}
                  onClick={() => navigate(n.href)}
                  className="group text-left rounded-xl border border-border/60 bg-muted/20 hover:bg-muted/40 hover:border-border transition-colors px-4 py-4"
                >
                  <n.icon
                    className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors mb-3"
                    strokeWidth={1.75}
                  />
                  <div className="text-[13.5px] font-medium text-foreground leading-tight">
                    {n.label}
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    {n.sub}
                  </div>
                </button>
              ))}
            </div>
          </section>
        </motion.div>
      </div>
    </Layout>
  );
};

export default HomePage;
