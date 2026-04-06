import { useTheme } from "@/context/ThemeContext";
import { ChevronRight, Code, Zap, Brain, Target, TrendingUp, MessageSquare, Crown, Eye, Swords, FlaskConical, BarChart3, ArrowRight, Check, X as XIcon, Shield, BookOpen, Sparkles } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { motion, useInView } from "framer-motion";
import { API } from "@/App";

const Landing = () => {
  const { theme } = useTheme();
  const [devMode, setDevMode] = useState(false);
  const [devLoading, setDevLoading] = useState(false);

  const getPostAuthRedirect = () => window.sessionStorage.getItem("post_auth_redirect") || "/dashboard";

  useEffect(() => {
    const checkDevMode = async () => {
      try {
        const response = await fetch(`${API}/auth/status`);
        const data = await response.json();
        setDevMode(data.dev_mode === true);
      } catch (e) {}
    };
    checkDevMode();
  }, []);

  const handleLogin = async () => {
    try {
      const response = await fetch(`${API}/auth/google/login`);
      const data = await response.json();
      if (data.auth_url) window.location.href = data.auth_url;
      else alert("Login failed. Please try again.");
    } catch (error) {
      alert("Login failed. Please try again.");
    }
  };

  const handleDevLogin = async () => {
    setDevLoading(true);
    try {
      const response = await fetch(`${API}/auth/dev-login`, { credentials: "include" });
      const data = await response.json();
      if (data.status === "ok") window.location.href = getPostAuthRedirect();
      else alert("Dev login failed");
    } catch (error) {
      alert("Dev login failed.");
    } finally {
      setDevLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#06060B] text-gray-100 overflow-hidden">

      {/* ═══ NAVBAR ═══ */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-white/[0.04] bg-[#06060B]/80 backdrop-blur-2xl">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2.5">
              <img src="/chessguru-logo.svg" alt="ChessGuru" className="w-7 h-7" />
              <span className="text-[15px] font-heading font-bold tracking-tight text-white">ChessGuru</span>
            </div>
            <nav className="hidden md:flex items-center gap-8">
              {["Features", "How it works", "Compare"].map((item) => (
                <button key={item} onClick={() => document.getElementById(item.toLowerCase().replace(/\s/g, "-"))?.scrollIntoView({ behavior: "smooth" })}
                  className="text-sm text-gray-500 hover:text-white transition-colors">{item}</button>
              ))}
            </nav>
            <div className="flex items-center gap-3">
              {devMode && (
                <button onClick={handleDevLogin} disabled={devLoading}
                  className="px-4 py-2 text-sm border border-white/10 text-gray-400 rounded-lg hover:border-white/20 hover:text-white transition-all flex items-center gap-1.5"
                  data-testid="dev-login-button">
                  <Code className="w-3.5 h-3.5" />{devLoading ? "..." : "Dev"}
                </button>
              )}
              <button onClick={handleLogin} data-testid="login-button"
                className="px-5 py-2 text-sm font-semibold text-black rounded-lg bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 transition-all shadow-lg shadow-amber-500/20">
                Get Started Free
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ═══ HERO ═══ */}
      <section className="relative min-h-[100vh] flex items-center pt-16">
        {/* Background effects */}
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] rounded-full blur-[180px] bg-amber-500/[0.07]" />
          <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] rounded-full blur-[150px] bg-amber-600/[0.05]" />
          {/* Grid */}
          <div className="absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)", backgroundSize: "60px 60px" }} />
        </div>

        <div className="relative z-10 max-w-6xl mx-auto px-6 py-24 w-full">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            {/* Left: Copy */}
            <div>
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-amber-500/20 bg-amber-500/5 text-amber-400 text-xs font-mono mb-6">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                AI Chess Coaching That Learns You
              </motion.div>

              <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                className="text-[3.2rem] sm:text-[4rem] font-heading font-bold tracking-[-0.04em] leading-[0.95] text-white mb-6">
                Stop making
                <br />
                the same
                <br />
                <span className="relative inline-block">
                  <span className="bg-gradient-to-r from-amber-400 to-amber-500 bg-clip-text text-transparent">mistakes.</span>
                  <motion.div className="absolute -bottom-2 left-0 right-0 h-[3px] rounded-full bg-gradient-to-r from-amber-400/60 to-transparent"
                    initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.8, duration: 0.6 }} style={{ transformOrigin: "left" }} />
                </span>
              </motion.h1>

              <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
                className="text-lg text-gray-400 leading-relaxed max-w-lg mb-10">
                ChessGuru remembers every mistake you've ever made, finds the patterns you can't see, and trains you on positions from <em>your own games</em> until the pattern breaks.
              </motion.p>

              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}
                className="flex flex-col sm:flex-row gap-4 mb-8">
                <button onClick={handleLogin} data-testid="hero-cta-button"
                  className="group px-8 py-4 text-base font-semibold text-black rounded-xl bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 transition-all shadow-xl shadow-amber-500/25 hover:shadow-amber-500/40 flex items-center justify-center gap-2">
                  Start Free with Google
                  <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
                <button onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}
                  className="px-8 py-4 text-base text-gray-400 border border-white/10 rounded-xl hover:border-white/20 hover:text-white transition-all"
                  data-testid="learn-more-button">
                  See what it does
                </button>
              </motion.div>

              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.9 }}
                className="flex items-center gap-6 text-xs text-gray-600">
                <span className="flex items-center gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500/60" /> Free to start</span>
                <span className="flex items-center gap-1.5"><Check className="w-3.5 h-3.5 text-emerald-500/60" /> Works with Chess.com & Lichess</span>
              </motion.div>
            </div>

            {/* Right: Coaching Demo */}
            <motion.div initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5, duration: 0.7 }}
              className="hidden lg:block">
              <CoachingDemo />
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══ TRUSTED BY BAR ═══ */}
      <section className="py-10 border-y border-white/[0.04]">
        <div className="max-w-5xl mx-auto px-6">
          <div className="flex flex-wrap items-center justify-center gap-10 sm:gap-16">
            {[
              { value: "600-1500", label: "Target ELO Range" },
              { value: "6", label: "Strength Domains Tracked" },
              { value: "<2s", label: "Per-Move Analysis" },
              { value: "28+", label: "Lesson Types" },
            ].map((s, i) => (
              <FadeIn key={s.label} delay={i * 0.05}>
                <div className="text-center">
                  <p className="text-2xl sm:text-3xl font-heading font-bold text-white">{s.value}</p>
                  <p className="text-[10px] uppercase tracking-[0.15em] text-gray-600 mt-1">{s.label}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ PROBLEM STATEMENT ═══ */}
      <section className="py-28 relative">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-gray-600 mb-6">The real problem</p>
            <h2 className="text-3xl sm:text-4xl font-heading font-bold tracking-tight text-white leading-snug mb-6">
              Chess.com tells you <em className="text-red-400 not-italic">what</em> went wrong.
              <br />
              Nobody tells you <em className="text-amber-400 not-italic">why it keeps happening.</em>
            </h2>
            <p className="text-base text-gray-500 leading-relaxed max-w-xl mx-auto">
              You review your games. You see the blunder. You move on. Next game — same mistake, different position.
              That's because analysis tools show you the move. ChessGuru shows you the <strong className="text-gray-300">thinking error</strong> behind it.
            </p>
          </FadeIn>
        </div>
      </section>

      {/* ═══ FEATURE SHOWCASES ═══ */}
      <section id="features" className="py-16 relative">
        <div className="max-w-6xl mx-auto px-6">

          {/* Feature 1: Play with Coach */}
          <FeatureRow
            badge="Play with Coach"
            title="A coach that talks to you while you play."
            description="Play against an adaptive engine while your AI coach watches every move. Get real-time feedback calibrated to your rating — an 800 player gets encouragement, a 1600 gets Socratic questions."
            points={["Rating-aware feedback thresholds", "Pre-move warnings on dangerous positions", "Celebrates brilliant sacrifices", "Adapts coaching intensity to your momentum"]}
            visual={<MockCoachingSidebar />}
          />

          {/* Feature 2: Pattern Memory */}
          <FeatureRow
            badge="Pattern Memory"
            title={<>Your coach remembers what you <span className="text-amber-400">keep forgetting.</span></>}
            description="Not just 'you blundered.' ChessGuru tracks recurring thinking errors across all your games with a decay-weighted model. Recent mistakes matter more. Recovery streaks earn credit."
            points={["Tracks 10+ cognitive gap types", "Decay model: recent mistakes weigh more", "Named rules: 'Piece Safety Check', 'Threat Awareness'", "Recovery detection: knows when you've improved"]}
            visual={<MockPatternCard />}
            reverse
          />

          {/* Feature 3: Lab — Game Review */}
          <FeatureRow
            badge="The Lab"
            title="Your coach picks which game to review."
            description="Not a random game list. The Lab uses behavioral AI to find the game with the most to teach you — thrown wins, recurring patterns, one-move blunders that decided everything."
            points={["Smart pick: best unreviewed game to study", "Behavioral diagnosis for every game", "Move-by-move story of what happened", "One-click training from any mistake"]}
            visual={<MockLabCard />}
          />

          {/* Feature 4: Training from YOUR games */}
          <FeatureRow
            badge="Targeted Training"
            title="Puzzles extracted from your own blunders."
            description="Every time you blunder, ChessGuru extracts the position as a training puzzle. You don't practice random tactics — you practice the exact situations where you fail."
            points={["Auto-extracted from your analyzed games", "Grouped by weakness pattern", "Difficulty scales with your rating", "Community puzzles from similar-rated players"]}
            visual={<MockTrainingCard />}
            reverse
          />

          {/* Feature 5: Progress & Strength Profile */}
          <FeatureRow
            badge="Progress Tracking"
            title="Six domains. One clear picture."
            description="Your strength profile tracks tactical vision, calculation depth, positional sense, endgame technique, opening knowledge, and pressure handling — across every game you play."
            points={["Strength profile across 6 domains", "Weekly trend comparison", "Phase accuracy: opening vs middlegame vs endgame", "Pattern frequency over time"]}
            visual={<MockStrengthProfile />}
          />

          {/* Feature 6: Escape Square Awareness */}
          <FeatureRow
            badge="Unique to ChessGuru"
            title={<>Learn to <span className="text-amber-400">trap pieces</span>, not just attack them.</>}
            description="No other chess app teaches escape square awareness. Your coach counts escape squares for opponent pieces, shows you which squares to block, and celebrates when you execute the trap."
            points={["Detects trap opportunities for any piece", "Shows escape squares on the board", "Suggests blocking moves", "Tracks your trap awareness over time"]}
            visual={<MockEscapeSquares />}
            reverse
          />
        </div>
      </section>

      {/* ═══ MORE FEATURES GRID ═══ */}
      <section className="py-24 relative">
        <div className="max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">And there's more</p>
            <h2 className="text-3xl font-heading font-bold tracking-tight text-white text-center mb-14">
              Everything a chess coach would do.
            </h2>
          </FadeIn>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { icon: BookOpen, title: "Opening Repertoire", desc: "Build your opening library. Track win rates per opening. Get taught variations from your own games." },
              { icon: Shield, title: "Trap & Endgame Lessons", desc: "18 verified traps and 10 endgame lessons. Interactive — you play the moves, the coach validates." },
              { icon: MessageSquare, title: "Coach Personality", desc: "Your coach develops a relationship. Formal at first. Familiar after 20 games. Blunt when it matters." },
              { icon: Swords, title: "Post-Loss Recovery", desc: "After a tough loss, your coach walks you through what happened and gives you one thing to fix." },
              { icon: Brain, title: "Chess DNA", desc: "Instant analysis of your playing style — aggressive vs. positional, time management, castling habits." },
              { icon: Sparkles, title: "Brilliant Move Detection", desc: "Detects sacrifices that only work with deep calculation. Celebrates what you're actually good at." },
            ].map((item, i) => (
              <FadeIn key={item.title} delay={i * 0.06}>
                <div className="group p-5 rounded-xl border border-white/[0.04] bg-white/[0.015] hover:border-amber-500/15 hover:bg-amber-500/[0.02] transition-all duration-300 h-full">
                  <div className="w-9 h-9 rounded-lg bg-amber-500/10 flex items-center justify-center mb-3 group-hover:bg-amber-500/15 transition-colors">
                    <item.icon className="w-4.5 h-4.5 text-amber-400" strokeWidth={1.5} />
                  </div>
                  <h3 className="text-[15px] font-heading font-semibold text-white mb-1.5">{item.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ COMPARISON TABLE ═══ */}
      <section id="compare" className="py-24 relative">
        <div className="max-w-3xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">How we compare</p>
            <h2 className="text-3xl font-heading font-bold tracking-tight text-white text-center mb-12">
              This isn't another analysis tool.
            </h2>
          </FadeIn>

          <FadeIn delay={0.1}>
            <div className="rounded-xl border border-white/[0.06] overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left text-xs text-gray-500 font-mono uppercase tracking-wider p-4 w-1/2">Feature</th>
                    <th className="text-center text-xs text-gray-500 font-mono uppercase tracking-wider p-4">Others</th>
                    <th className="text-center text-xs font-mono uppercase tracking-wider p-4 text-amber-400">ChessGuru</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Shows you the best move", true, true],
                    ["Explains why your move was bad", false, true],
                    ["Tracks recurring mistake patterns", false, true],
                    ["Adapts coaching to your rating", false, true],
                    ["Trains you on YOUR positions", false, true],
                    ["Remembers across games", false, true],
                    ["Real-time coaching during play", false, true],
                    ["Detects behavioral patterns", false, true],
                    ["Teaches escape square awareness", false, true],
                  ].map(([feature, others, cg], i) => (
                    <tr key={i} className="border-b border-white/[0.03] last:border-0">
                      <td className="p-4 text-sm text-gray-300">{feature}</td>
                      <td className="p-4 text-center">
                        {others ? <Check className="w-4 h-4 text-gray-600 mx-auto" /> : <XIcon className="w-4 h-4 text-gray-700 mx-auto" />}
                      </td>
                      <td className="p-4 text-center">
                        <Check className="w-4 h-4 text-amber-400 mx-auto" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section id="how-it-works" className="py-28 relative">
        <div className="max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">Getting started</p>
            <h2 className="text-3xl sm:text-4xl font-heading font-bold tracking-tight text-white text-center mb-16">
              Three minutes to your first insight.
            </h2>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { step: "01", title: "Connect your account", desc: "Link your Chess.com or Lichess username. We import and analyze every game automatically with Stockfish + behavioral AI.", icon: Target },
              { step: "02", title: "Meet your coach", desc: "Your AI coach scans your games, finds your patterns, and builds a profile of how you think. Not just what you play — why you play it.", icon: Brain },
              { step: "03", title: "Start improving", desc: "Play coached games. Train on your own mistakes. Track progress across 6 strength domains. Watch the same patterns finally stop appearing.", icon: TrendingUp },
            ].map((item, i) => (
              <FadeIn key={item.step} delay={i * 0.12}>
                <div className="relative">
                  {i < 2 && <div className="hidden md:block absolute top-8 left-[calc(100%+1rem)] w-[calc(100%-2rem)] h-px border-t border-dashed border-white/10" />}
                  <div className="text-center">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500/15 to-amber-600/5 border border-amber-500/10 flex items-center justify-center mx-auto mb-5">
                      <item.icon className="w-7 h-7 text-amber-400" strokeWidth={1.5} />
                    </div>
                    <span className="text-amber-400/30 font-mono text-xs font-bold">{item.step}</span>
                    <h3 className="text-lg font-heading font-semibold text-white mt-1 mb-2">{item.title}</h3>
                    <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ COACH QUOTE ═══ */}
      <section className="py-20 relative">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <FadeIn>
            <div className="w-14 h-14 rounded-xl bg-amber-500/10 flex items-center justify-center mx-auto mb-8 border border-amber-500/15">
              <img src="/chessguru-logo.svg" alt="" className="w-7 h-7" />
            </div>
            <blockquote className="text-2xl sm:text-3xl font-heading italic text-gray-300 leading-snug mb-6">
              "You didn't lose because of many mistakes.
              <br />
              <span className="text-amber-400 not-italic font-semibold">You lost in one moment</span> of inattention."
            </blockquote>
            <p className="text-sm text-gray-600">
              Your coach finds that moment. Then trains you to never repeat it.
            </p>
          </FadeIn>
        </div>
      </section>

      {/* ═══ FINAL CTA ═══ */}
      <section className="py-28 relative">
        <div className="absolute inset-0">
          <div className="absolute bottom-0 left-1/3 w-[500px] h-[400px] rounded-full blur-[160px] bg-amber-500/[0.06]" />
        </div>
        <div className="relative z-10 max-w-2xl mx-auto px-6 text-center">
          <FadeIn>
            <h2 className="text-4xl sm:text-5xl font-heading font-bold tracking-[-0.03em] text-white mb-6 leading-tight">
              Your mistakes have a pattern.
              <br />
              <span className="text-amber-400">Let's break it.</span>
            </h2>
          </FadeIn>
          <FadeIn delay={0.1}>
            <p className="text-base text-gray-500 mb-10 max-w-md mx-auto">
              Import your games from Chess.com or Lichess. Your coach starts learning who you are from game one.
            </p>
          </FadeIn>
          <FadeIn delay={0.2}>
            <button onClick={handleLogin} data-testid="cta-button"
              className="group px-10 py-4 text-base font-semibold text-black rounded-xl bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 transition-all shadow-xl shadow-amber-500/25 hover:shadow-amber-500/40 inline-flex items-center gap-2">
              Start Free with Google
              <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </FadeIn>
          <FadeIn delay={0.3}>
            <p className="text-xs text-gray-700 mt-6">No credit card required. Free tier available.</p>
          </FadeIn>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-10 border-t border-white/[0.04]">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <img src="/chessguru-logo.svg" alt="" className="w-4 h-4 opacity-40" />
            <span className="text-xs text-gray-600 font-heading">ChessGuru</span>
          </div>
          <p className="text-xs text-gray-700">Built for chess players stuck on a plateau.</p>
        </div>
      </footer>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════
// MOCK UI COMPONENTS — These look like real app screenshots
// ═══════════════════════════════════════════════════════════════

// ── Coaching Sidebar Demo (Hero) ──
const CoachingDemo = () => {
  const [step, setStep] = useState(0);
  const totalSteps = 5;

  useEffect(() => {
    const durations = [2000, 3000, 4000, 3500, 3000];
    let timeout;
    const advance = (current) => {
      timeout = setTimeout(() => {
        const next = (current + 1) % totalSteps;
        setStep(next);
        advance(next);
      }, durations[current]);
    };
    advance(0);
    return () => clearTimeout(timeout);
  }, []);

  return (
    <div className="relative">
      <div className="absolute -inset-3 rounded-2xl bg-gradient-to-br from-amber-500/10 via-transparent to-amber-600/10 blur-2xl" />
      <div className="relative rounded-2xl border border-white/[0.08] bg-[#0A0A12] overflow-hidden shadow-2xl shadow-black/60">
        {/* Header */}
        <div className="px-4 py-3 border-b border-white/[0.04] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-500/25 to-amber-600/15 flex items-center justify-center">
                <Brain className="w-4 h-4 text-amber-400" />
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-[#0A0A12]" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Your Coach</p>
              <p className="text-[10px] text-emerald-400/80 font-mono">Game #14 together</p>
            </div>
          </div>
          <div className="flex gap-1">
            <div className="w-2 h-2 rounded-full bg-white/[0.06]" />
            <div className="w-2 h-2 rounded-full bg-white/[0.06]" />
            <div className="w-2 h-2 rounded-full bg-white/[0.06]" />
          </div>
        </div>

        {/* Messages */}
        <div className="p-4 space-y-2.5 min-h-[320px]">
          {/* User move */}
          <motion.div animate={{ opacity: 1, y: 0 }} className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center"><span className="text-sm">&#9822;</span></div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">You played</span>
              <span className="text-sm font-mono font-bold text-white bg-white/5 px-2 py-0.5 rounded">Nf3</span>
            </div>
          </motion.div>

          {/* Step 0: Thinking */}
          {step === 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 text-gray-500 text-xs py-2">
              <div className="flex gap-1">
                <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.2, repeat: Infinity, delay: 0 }} className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.2, repeat: Infinity, delay: 0.2 }} className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.2, repeat: Infinity, delay: 0.4 }} className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              </div>
              Coach is analyzing...
            </motion.div>
          )}

          {/* Step 1: Good move */}
          {step === 1 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
              <div className="flex items-center gap-2 mb-1">
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Good Move</span>
              </div>
              <p className="text-xs text-gray-300 leading-relaxed">Solid development. You're getting your pieces out before attacking — that's the right instinct.</p>
            </motion.div>
          )}

          {/* Step 2: Mistake + pattern */}
          {step === 2 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
              <div className="p-3 rounded-lg border border-red-500/20 bg-red-500/5">
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-4 h-4 rounded bg-red-500/20 flex items-center justify-center">
                    <span className="text-[9px] font-bold text-red-400">!</span>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-red-400">Mistake</span>
                  <span className="text-[10px] text-gray-600 ml-auto font-mono">Best: Bd5</span>
                </div>
                <p className="text-xs text-gray-300 leading-relaxed">Your knight is unprotected on that square. Their bishop covers it.</p>
              </div>
              <div className="p-2.5 rounded-lg border border-amber-500/15 bg-amber-500/[0.03]">
                <div className="flex items-center gap-2">
                  <Eye className="w-3 h-3 text-amber-400" />
                  <span className="text-[10px] text-amber-400 font-medium">This is the 4th time — piece safety.</span>
                </div>
              </div>
            </motion.div>
          )}

          {/* Step 3: Escape squares */}
          {step === 3 && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className="p-3 rounded-lg border border-amber-500/15 bg-amber-500/[0.03]">
              <div className="flex items-center gap-2 mb-1.5">
                <Target className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Escape Square Control</span>
              </div>
              <p className="text-xs text-gray-300 leading-relaxed">Their bishop has only 2 escape squares. Block one — it gets trapped.</p>
              <div className="flex items-center gap-2 mt-2">
                {["f7", "d5"].map((sq) => (
                  <motion.span key={sq} animate={{ opacity: [0.5, 1, 0.5] }} transition={{ duration: 1.5, repeat: Infinity }}
                    className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/15">{sq}</motion.span>
                ))}
                <div className="flex-1" />
                <span className="text-[10px] text-gray-600 font-mono">2/6 squares</span>
              </div>
            </motion.div>
          )}

          {/* Step 4: Brilliant */}
          {step === 4 && (
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
              className="p-3 rounded-lg border border-amber-400/25 bg-gradient-to-r from-amber-500/10 to-amber-600/5">
              <div className="flex items-center gap-2 mb-1.5">
                <motion.div animate={{ rotate: [0, 15, -15, 0] }} transition={{ duration: 0.5 }}>
                  <Zap className="w-3.5 h-3.5 text-amber-400" strokeWidth={2.5} />
                </motion.div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Brilliant Sacrifice!</span>
              </div>
              <p className="text-xs text-amber-200/80 leading-relaxed">That only works if you saw three moves ahead. You did. This is the level you're capable of.</p>
            </motion.div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 border-t border-white/[0.04] flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-[10px] text-gray-600 font-mono"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500/50" />78% accuracy</span>
          <span className="flex items-center gap-1.5 text-[10px] text-gray-600 font-mono"><Eye className="w-2.5 h-2.5 text-amber-500/40" />3 patterns</span>
          <span className="flex items-center gap-1.5 text-[10px] text-gray-600 font-mono ml-auto"><Zap className="w-2.5 h-2.5 text-amber-500/40" />1 brilliant</span>
        </div>
      </div>
    </div>
  );
};


// ── Mock Pattern Memory Card ──
const MockPatternCard = () => (
  <MockFrame>
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-4 h-4 text-amber-400" />
        <span className="text-xs font-bold text-white uppercase tracking-wider">Pattern Memory</span>
      </div>

      {[
        { name: "Piece Safety", count: 7, trend: "active", rule: "Before moving, check: is anything I own under attack?" },
        { name: "Missed Tactic", count: 4, trend: "declining", rule: "Look for forcing moves: checks, captures, threats." },
        { name: "Time Pressure", count: 2, trend: "fading", rule: "Slow down when the position is complex." },
      ].map((p) => (
        <div key={p.name} className="p-3 rounded-lg border border-white/[0.04] bg-white/[0.02]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-sm font-medium text-white">{p.name}</span>
            <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
              p.trend === "active" ? "text-red-400 bg-red-500/10" :
              p.trend === "declining" ? "text-amber-400 bg-amber-500/10" :
              "text-emerald-400 bg-emerald-500/10"
            }`}>{p.count}x &middot; {p.trend}</span>
          </div>
          <p className="text-[11px] text-gray-500 italic">"{p.rule}"</p>
          {/* Decay bar */}
          <div className="mt-2 h-1 bg-white/[0.04] rounded-full overflow-hidden">
            <motion.div className={`h-full rounded-full ${
              p.trend === "active" ? "bg-red-400" : p.trend === "declining" ? "bg-amber-400" : "bg-emerald-400"
            }`} initial={{ width: 0 }} whileInView={{ width: `${p.count * 14}%` }} transition={{ duration: 1, delay: 0.3 }} viewport={{ once: true }} />
          </div>
        </div>
      ))}
    </div>
  </MockFrame>
);


// ── Mock Lab Card ──
const MockLabCard = () => (
  <MockFrame>
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <FlaskConical className="w-4 h-4 text-amber-400" />
        <span className="text-xs font-bold text-white uppercase tracking-wider">Coach's Pick</span>
      </div>
      <p className="text-[11px] text-amber-400/80 mb-3">This game has the most to teach you right now.</p>

      <div className="p-3 rounded-lg border border-amber-500/15 bg-amber-500/[0.03]">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-red-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-white">vs GrandMaster42</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/20 font-bold">LOST</span>
            </div>
            <p className="text-[11px] text-gray-500 mt-0.5">Sicilian Defense &middot; 78% accuracy</p>
          </div>
        </div>
        <div className="mt-3 p-2 rounded bg-white/[0.02] border border-white/[0.03]">
          <p className="text-xs text-gray-400 leading-relaxed">"You were +2.1 at move 18 and collapsed. Same piece safety issue — 5th game in a row."</p>
        </div>
      </div>

      <div className="space-y-1.5">
        {["vs chess_ninja99  W  91%", "vs KnightRider  L  64%", "vs TheRook  W  82%"].map((g, i) => (
          <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.015] border border-white/[0.03]">
            <div className={`w-2 h-2 rounded-full ${g.includes(" W ") ? "bg-emerald-400" : "bg-red-400"}`} />
            <span className="text-xs text-gray-400 font-mono flex-1">{g}</span>
          </div>
        ))}
      </div>
    </div>
  </MockFrame>
);


// ── Mock Training Card ──
const MockTrainingCard = () => (
  <MockFrame>
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-2">
        <Target className="w-4 h-4 text-amber-400" />
        <span className="text-xs font-bold text-white uppercase tracking-wider">Training: Piece Safety</span>
      </div>

      {/* Puzzle preview */}
      <div className="rounded-lg border border-white/[0.04] overflow-hidden">
        <div className="aspect-square bg-gradient-to-br from-[#779556] to-[#ebecd0] p-4 flex items-center justify-center relative">
          {/* Simplified chess grid */}
          <div className="grid grid-cols-4 gap-0 w-full h-full opacity-70">
            {Array(16).fill(0).map((_, i) => (
              <div key={i} className={`${(Math.floor(i/4) + i%4) % 2 === 0 ? 'bg-[#ebecd0]' : 'bg-[#779556]'}`} />
            ))}
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-4xl">&#9822;</span>
          </div>
        </div>
        <div className="p-3 bg-[#0D0D15]">
          <p className="text-xs text-gray-400 mb-1">From your game vs KnightRider, Move 23</p>
          <p className="text-sm text-white font-medium">Your knight is hanging. Find the safe square.</p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-gray-600 font-mono">
        <span>12 puzzles from your games</span>
        <span className="text-gray-700">&middot;</span>
        <span>8 community puzzles</span>
      </div>
    </div>
  </MockFrame>
);


// ── Mock Strength Profile ──
const MockStrengthProfile = () => {
  const domains = [
    { name: "Tactical Vision", score: 72, color: "text-amber-400" },
    { name: "Calculation", score: 58, color: "text-blue-400" },
    { name: "Positional Sense", score: 65, color: "text-emerald-400" },
    { name: "Endgame", score: 41, color: "text-purple-400" },
    { name: "Openings", score: 78, color: "text-cyan-400" },
    { name: "Pressure", score: 55, color: "text-rose-400" },
  ];

  return (
    <MockFrame>
      <div>
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">Strength Profile</span>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          {domains.map((d) => (
            <div key={d.name} className="p-2.5 rounded-lg border border-white/[0.04] bg-white/[0.015]">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] text-gray-400">{d.name}</span>
                <span className={`text-sm font-mono font-bold ${d.color}`}>{d.score}</span>
              </div>
              <div className="h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
                <motion.div className={`h-full rounded-full ${
                  d.score >= 70 ? "bg-emerald-400" : d.score >= 50 ? "bg-amber-400" : "bg-red-400"
                }`} initial={{ width: 0 }} whileInView={{ width: `${d.score}%` }} transition={{ duration: 1, delay: 0.2 }} viewport={{ once: true }} />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-3 p-2.5 rounded-lg border border-amber-500/10 bg-amber-500/[0.02]">
          <p className="text-[11px] text-gray-400"><span className="text-amber-400 font-medium">Focus area:</span> Endgame technique is your biggest opportunity for growth.</p>
        </div>
      </div>
    </MockFrame>
  );
};


// ── Mock Escape Squares ──
const MockEscapeSquares = () => (
  <MockFrame>
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Crown className="w-4 h-4 text-amber-400" />
        <span className="text-xs font-bold text-white uppercase tracking-wider">Escape Square Control</span>
      </div>

      {/* Mini board with highlights */}
      <div className="rounded-lg border border-white/[0.04] overflow-hidden mb-3">
        <div className="relative aspect-square bg-gradient-to-br from-[#779556] to-[#ebecd0]">
          <div className="grid grid-cols-5 gap-0 w-full h-full">
            {Array(25).fill(0).map((_, i) => {
              const isTarget = i === 12;
              const isEscape = i === 7 || i === 17;
              const isBlocked = i === 6 || i === 8 || i === 11 || i === 13 || i === 16 || i === 18;
              return (
                <div key={i} className={`relative flex items-center justify-center ${(Math.floor(i/5) + i%5) % 2 === 0 ? 'bg-[#ebecd0]' : 'bg-[#779556]'}`}>
                  {isTarget && <div className="absolute inset-0.5 rounded bg-red-500/30 border border-red-400/40" />}
                  {isTarget && <span className="relative text-lg z-10">&#9821;</span>}
                  {isEscape && <div className="absolute inset-0.5 rounded bg-emerald-500/25 border border-emerald-400/30" />}
                  {isEscape && <span className="relative text-[10px] font-mono text-emerald-300 z-10 font-bold">{i === 7 ? "f7" : "d5"}</span>}
                  {isBlocked && <div className="absolute inset-1 rounded bg-red-500/10"><XIcon className="w-full h-full text-red-400/20" /></div>}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="p-3 rounded-lg border border-amber-500/15 bg-amber-500/[0.03]">
        <p className="text-xs text-gray-300 leading-relaxed mb-2">Their bishop has <strong className="text-white">2 escape squares</strong> left. Block <span className="text-amber-400 font-mono">f7</span> and it's trapped.</p>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-600">Escapes:</span>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/15">f7</span>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/15">d5</span>
          <span className="text-[10px] text-gray-700 font-mono ml-auto">2/6</span>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <ArrowRight className="w-3 h-3 text-amber-400" />
        <span className="text-[11px] text-amber-400/80 font-medium">Try: Bc4 blocks one escape</span>
      </div>
    </div>
  </MockFrame>
);


// ── Mock Frame wrapper ──
const MockFrame = ({ children }) => (
  <FadeIn>
    <div className="relative">
      <div className="absolute -inset-2 rounded-2xl bg-gradient-to-br from-amber-500/[0.06] via-transparent to-amber-600/[0.04] blur-xl" />
      <div className="relative rounded-2xl border border-white/[0.06] bg-[#0A0A12] p-5 shadow-2xl shadow-black/40">
        {children}
      </div>
    </div>
  </FadeIn>
);


// ── Feature Row: alternating text + visual ──
const FeatureRow = ({ badge, title, description, points, visual, reverse = false }) => (
  <div className={`grid grid-cols-1 lg:grid-cols-2 gap-12 items-center py-16 ${reverse ? '' : ''}`}>
    <div className={reverse ? 'lg:order-2' : ''}>
      <FadeIn>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 border border-amber-500/15 mb-4">
          {badge}
        </span>
        <h3 className="text-2xl sm:text-3xl font-heading font-bold tracking-tight text-white leading-snug mb-4">{title}</h3>
        <p className="text-sm text-gray-400 leading-relaxed mb-6">{description}</p>
        <ul className="space-y-2">
          {points.map((p, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm text-gray-500">
              <Check className="w-4 h-4 text-amber-400/60 mt-0.5 flex-shrink-0" strokeWidth={2} />
              {p}
            </li>
          ))}
        </ul>
      </FadeIn>
    </div>
    <div className={reverse ? 'lg:order-1' : ''}>
      {visual}
    </div>
  </div>
);


// ── Scroll-triggered fade-in ──
const FadeIn = ({ children, delay = 0, className = "" }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className={className}>
      {children}
    </motion.div>
  );
};

export default Landing;
