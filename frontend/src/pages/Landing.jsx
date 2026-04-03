import { useTheme } from "@/context/ThemeContext";
import { ChevronRight, Moon, Sun, Code, Zap, Brain, Target, TrendingUp, MessageSquare, Shield } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { motion, useInView } from "framer-motion";
import { API } from "@/App";

const Landing = () => {
  const { theme, toggleTheme } = useTheme();
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
    const isEmergentEnv = window.location.hostname.includes("emergentagent") || window.location.hostname.includes("preview") || API.includes("emergentagent") || API.includes("preview");
    if (isEmergentEnv) {
      const redirectUrl = window.location.origin + getPostAuthRedirect();
      window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    } else {
      try {
        const response = await fetch(`${API}/auth/google/login`);
        const data = await response.json();
        if (data.auth_url) window.location.href = data.auth_url;
        else alert("Login failed. Please try again.");
      } catch (error) {
        alert("Login failed. Please try again.");
      }
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
    <div className="min-h-screen bg-[#09090F] text-gray-100 overflow-hidden">

      {/* ═══ NAVBAR ═══ */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#09090F]/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2.5">
              <img src="/chessguru-logo.svg" alt="ChessGuru" className="w-7 h-7" />
              <span className="text-[15px] font-heading font-bold tracking-tight text-white">ChessGuru</span>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleLogin}
                data-testid="login-button"
                className="px-5 py-2 text-sm font-medium text-black rounded-lg bg-amber-400 hover:bg-amber-300 transition-colors"
              >
                Get Started
              </button>
              {devMode && (
                <button
                  onClick={handleDevLogin}
                  disabled={devLoading}
                  className="px-4 py-2 text-sm border border-white/10 text-gray-400 rounded-lg hover:border-white/20 hover:text-white transition-all flex items-center gap-1.5"
                  data-testid="dev-login-button"
                >
                  <Code className="w-3.5 h-3.5" />
                  {devLoading ? "..." : "Dev"}
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ═══ HERO ═══ */}
      <section className="relative min-h-screen flex items-center pt-16">
        {/* Background grid pattern */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }} />
        {/* Gradient orbs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-amber-500/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-amber-500/5 rounded-full blur-[100px]" />

        <div className="relative z-10 max-w-6xl mx-auto px-6 py-24 w-full">
          <div className="text-center max-w-3xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-amber-500/20 bg-amber-500/5 text-amber-400 text-xs font-mono mb-8"
            >
              <Zap className="w-3 h-3" strokeWidth={2.5} />
              AI-Powered Chess Coaching
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-heading font-bold tracking-tighter leading-[0.95] text-white mb-6"
            >
              Your coach
              <br />
              <span className="text-amber-400">remembers</span>
              <br />
              every mistake.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="text-lg text-gray-400 leading-relaxed max-w-xl mx-auto mb-10"
            >
              Not another analysis tool. A coach that tracks your patterns across every game, knows your weaknesses by name, and builds training around exactly what you get wrong.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              <button
                onClick={handleLogin}
                data-testid="hero-cta-button"
                className="px-8 py-4 text-base font-semibold text-black rounded-xl bg-amber-400 hover:bg-amber-300 transition-all shadow-lg shadow-amber-500/20 hover:shadow-amber-500/30 flex items-center justify-center gap-2"
              >
                Start Free
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })}
                className="px-8 py-4 text-base text-gray-300 border border-white/10 rounded-xl hover:border-white/20 hover:text-white transition-all"
                data-testid="learn-more-button"
              >
                How it works
              </button>
            </motion.div>
          </div>

          {/* ── Product Preview ── */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8, duration: 0.6 }}
            className="mt-16 max-w-4xl mx-auto"
          >
            <div className="relative rounded-xl border border-white/10 bg-[#0E0E16] overflow-hidden shadow-2xl shadow-black/50">
              {/* Mock app header */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
                <div className="w-3 h-3 rounded-full bg-white/10" />
                <div className="w-3 h-3 rounded-full bg-white/10" />
                <div className="w-3 h-3 rounded-full bg-white/10" />
                <span className="text-xs text-gray-600 ml-2 font-mono">chessguru.ai/home</span>
              </div>
              {/* Mock coaching dashboard */}
              <div className="p-6 sm:p-8">
                <div className="flex items-start gap-6">
                  {/* Left: Coach message */}
                  <div className="flex-1 min-w-0">
                    <p className="text-amber-400 text-xs font-mono mb-2">3 losses in a row</p>
                    <h2 className="text-xl sm:text-2xl font-heading font-bold text-white mb-2 tracking-tight">
                      Piece safety is showing up in almost every game.
                    </h2>
                    <p className="text-sm text-gray-500 mb-6">7 times recently. This is your biggest leak right now.</p>

                    {/* Mock pattern cards */}
                    <div className="space-y-2">
                      {[
                        { name: "Piece Safety", count: "7x", severity: "HIGH", color: "bg-red-400" },
                        { name: "Missed Tactics", count: "4x", severity: "MED", color: "bg-amber-400" },
                        { name: "Time Pressure", count: "3x", severity: "MED", color: "bg-amber-400" },
                      ].map((p) => (
                        <div key={p.name} className="flex items-center justify-between px-4 py-2.5 rounded-lg border border-white/5 bg-white/[0.02]">
                          <div className="flex items-center gap-2.5">
                            <div className={`w-1.5 h-1.5 rounded-full ${p.color}`} />
                            <span className="text-sm text-gray-300">{p.name}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-gray-500">{p.count}</span>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                              p.severity === "HIGH" ? "bg-red-500/15 text-red-400" : "bg-amber-500/15 text-amber-400"
                            }`}>{p.severity}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Right: Mock strength radar */}
                  <div className="hidden sm:block w-48 flex-shrink-0">
                    <div className="border border-white/5 rounded-lg p-4 bg-white/[0.02]">
                      <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-3 font-bold">Your Strengths</p>
                      {[
                        { name: "Tactics", score: 72, best: true },
                        { name: "Calculation", score: 58 },
                        { name: "Positional", score: 45 },
                        { name: "Endgame", score: 34 },
                      ].map((s) => (
                        <div key={s.name} className="mb-2.5">
                          <div className="flex items-center justify-between mb-1">
                            <span className={`text-[10px] ${s.best ? "text-emerald-400" : "text-gray-500"}`}>{s.name}</span>
                            <span className="text-[10px] font-mono text-gray-600">{s.score}</span>
                          </div>
                          <div className="w-full h-1 bg-white/5 rounded-full">
                            <div className={`h-full rounded-full ${s.best ? "bg-emerald-500" : "bg-white/10"}`} style={{ width: `${s.score}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section id="how-it-works" className="py-32 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-[#09090F] via-[#0A0A12] to-[#09090F]" />
        <div className="relative z-10 max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">How it works</p>
            <h2 className="text-3xl sm:text-4xl font-heading font-bold tracking-tight text-white text-center mb-16">
              Three steps to better chess.
            </h2>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                step: "01",
                title: "Import your games",
                desc: "Connect Chess.com or Lichess. We analyze every game with Stockfish and behavioral AI.",
                icon: Target,
              },
              {
                step: "02",
                title: "See your patterns",
                desc: "Not just blunders — recurring thinking errors. The same mistake in game 5 and game 50? We track it.",
                icon: Brain,
              },
              {
                step: "03",
                title: "Train what matters",
                desc: "Puzzles from YOUR games. Training plans for YOUR weaknesses. Progress you can measure.",
                icon: TrendingUp,
              },
            ].map((item, i) => (
              <FadeIn key={item.step} delay={i * 0.15}>
                <div className="border border-white/5 rounded-xl p-6 bg-white/[0.02] hover:border-amber-500/20 transition-colors h-full">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-amber-400/40 font-mono text-sm font-bold">{item.step}</span>
                    <item.icon className="w-4 h-4 text-amber-400" strokeWidth={1.5} />
                  </div>
                  <h3 className="text-lg font-heading font-semibold text-white mb-2">{item.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ KEY DIFFERENTIATORS ═══ */}
      <section className="py-32 relative">
        <div className="relative z-10 max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">Why this is different</p>
            <h2 className="text-3xl sm:text-4xl font-heading font-bold tracking-tight text-white text-center mb-4">
              Chess.com shows you the blunder.
            </h2>
            <p className="text-xl text-gray-500 text-center mb-16">
              We show you <span className="text-amber-400">why you keep making it.</span>
            </p>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Pattern Memory */}
            <FadeIn delay={0.1}>
              <div className="border border-white/5 rounded-xl p-6 bg-white/[0.02] hover:border-amber-500/15 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center mb-4">
                  <Brain className="w-5 h-5 text-amber-400" strokeWidth={1.5} />
                </div>
                <h3 className="text-lg font-heading font-semibold text-white mb-2">Pattern Memory</h3>
                <p className="text-sm text-gray-500 leading-relaxed mb-4">
                  "This is the 5th game where you collapse when winning." Your coach tracks every mistake pattern and knows when it's getting worse — or better.
                </p>
                <div className="flex items-center gap-2 text-xs text-amber-400/60 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                  piece_safety: 7x this week (worsening)
                </div>
              </div>
            </FadeIn>

            {/* Rating-Aware */}
            <FadeIn delay={0.2}>
              <div className="border border-white/5 rounded-xl p-6 bg-white/[0.02] hover:border-amber-500/15 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center mb-4">
                  <MessageSquare className="w-5 h-5 text-amber-400" strokeWidth={1.5} />
                </div>
                <h3 className="text-lg font-heading font-semibold text-white mb-2">Talks to YOUR level</h3>
                <p className="text-sm text-gray-500 leading-relaxed mb-4">
                  An 800 and a 1600 player get completely different coaching from the same game. Beginners get encouragement. Advanced players get Socratic questions.
                </p>
                <div className="space-y-1 text-xs font-mono text-gray-600">
                  <p><span className="text-gray-400">800:</span> "Nf3 is fine for now. Let's keep going!"</p>
                  <p><span className="text-gray-400">1600:</span> "Hmm, Nf3 is okay but what about Nd5?"</p>
                </div>
              </div>
            </FadeIn>

            {/* Brilliant Detection */}
            <FadeIn delay={0.3}>
              <div className="border border-white/5 rounded-xl p-6 bg-white/[0.02] hover:border-amber-500/15 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center mb-4">
                  <Zap className="w-5 h-5 text-amber-400" strokeWidth={1.5} />
                </div>
                <h3 className="text-lg font-heading font-semibold text-white mb-2">Celebrates your wins</h3>
                <p className="text-sm text-gray-500 leading-relaxed mb-4">
                  Most tools only tell you what went wrong. We detect brilliant sacrifices, track your strengths, and tell you what you're actually good at.
                </p>
                <div className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2 py-1 rounded-md border border-amber-500/20">
                  <Zap className="w-3 h-3" strokeWidth={2.5} />
                  Brilliant sacrifice detected
                </div>
              </div>
            </FadeIn>

            {/* Live Coaching */}
            <FadeIn delay={0.4}>
              <div className="border border-white/5 rounded-xl p-6 bg-white/[0.02] hover:border-amber-500/15 transition-colors">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center mb-4">
                  <Shield className="w-5 h-5 text-amber-400" strokeWidth={1.5} />
                </div>
                <h3 className="text-lg font-heading font-semibold text-white mb-2">Play with your coach</h3>
                <p className="text-sm text-gray-500 leading-relaxed mb-4">
                  Play against an AI opponent while your coach watches every move. Real-time feedback, not post-game analysis. Like having a GM behind your shoulder.
                </p>
                <div className="text-xs text-gray-600 font-mono">
                  Move 14: <span className="text-emerald-400">"Brilliant! That sacrifice is stunning!"</span>
                </div>
              </div>
            </FadeIn>
          </div>
        </div>
      </section>

      {/* ═══ COACH QUOTE ═══ */}
      <section className="py-24 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-[#09090F] via-[#0C0C14] to-[#09090F]" />
        <div className="relative z-10 max-w-3xl mx-auto px-6 text-center">
          <FadeIn>
            <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center mx-auto mb-8 border border-amber-500/20">
              <img src="/chessguru-logo.svg" alt="" className="w-6 h-6" />
            </div>
            <blockquote className="text-2xl sm:text-3xl font-heading italic text-gray-300 leading-snug mb-6">
              "You didn't lose because of many mistakes.
              <br />
              <span className="text-amber-400">You lost in one moment</span> of inattention."
            </blockquote>
            <p className="text-sm text-gray-600">
              Your coach finds that moment. Then trains you to never repeat it.
            </p>
          </FadeIn>
        </div>
      </section>

      {/* ═══ BUILT FOR ═══ */}
      <section className="py-24">
        <div className="max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">Built for</p>
            <h2 className="text-3xl sm:text-4xl font-heading font-bold tracking-tight text-white text-center mb-16">
              Players stuck on a plateau.
            </h2>
          </FadeIn>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { value: "600-1500", label: "Target rating" },
              { value: "<2s", label: "Move analysis" },
              { value: "6", label: "Strength domains" },
              { value: "Free", label: "To start" },
            ].map((stat, i) => (
              <FadeIn key={stat.label} delay={i * 0.1} className="text-center">
                <p className="text-3xl sm:text-4xl font-heading font-bold tracking-tighter text-white mb-1">
                  {stat.value}
                </p>
                <p className="text-xs tracking-wider uppercase text-gray-600 font-mono">
                  {stat.label}
                </p>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA ═══ */}
      <section className="py-32">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <FadeIn>
            <h2 className="text-4xl sm:text-5xl font-heading font-bold tracking-tighter text-white mb-6">
              Stop repeating
              <br />
              the same mistakes.
            </h2>
          </FadeIn>
          <FadeIn delay={0.15}>
            <p className="text-base text-gray-500 mb-10 max-w-md mx-auto">
              Import your games from Chess.com or Lichess. Your coach starts learning who you are from game one.
            </p>
          </FadeIn>
          <FadeIn delay={0.3}>
            <button
              onClick={handleLogin}
              data-testid="cta-button"
              className="px-10 py-4 text-base font-semibold text-black rounded-xl bg-amber-400 hover:bg-amber-300 transition-all shadow-lg shadow-amber-500/20 hover:shadow-amber-500/30 inline-flex items-center gap-2"
            >
              Start Free with Google
              <ChevronRight className="w-4 h-4" />
            </button>
          </FadeIn>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-8 border-t border-white/5">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/chessguru-logo.svg" alt="" className="w-4 h-4 opacity-40" />
            <span className="text-xs text-gray-600 font-heading">ChessGuru</span>
          </div>
          <p className="text-xs text-gray-700">
            Built with AI. Made for chess players.
          </p>
        </div>
      </footer>
    </div>
  );
};


// Scroll-triggered fade-in
const FadeIn = ({ children, delay = 0, className = "" }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 24 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

export default Landing;
