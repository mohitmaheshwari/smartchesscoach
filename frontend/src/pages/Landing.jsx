import { useTheme } from "@/context/ThemeContext";
import { ChevronRight, Moon, Sun, Code, Zap, Brain, Target, TrendingUp, MessageSquare, Shield, Crown, Eye } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { motion, useInView, useAnimation } from "framer-motion";
import { API } from "@/App";

// ── Chess piece unicode characters for floating animation ──
const CHESS_PIECES = ["♔", "♕", "♖", "♗", "♘", "♙", "♚", "♛", "♜", "♝", "♞", "♟"];

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
    <div className="min-h-screen bg-[#08080E] text-gray-100 overflow-hidden">

      {/* ═══ FLOATING CHESS PIECES BACKGROUND ═══ */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        {CHESS_PIECES.map((piece, i) => (
          <motion.div
            key={i}
            className="absolute text-white/[0.03] select-none"
            style={{
              fontSize: `${30 + (i * 7) % 40}px`,
              left: `${(i * 8.3) % 100}%`,
              top: `${(i * 13.7) % 100}%`,
            }}
            animate={{
              y: [0, -30, 0],
              rotate: [0, (i % 2 === 0 ? 5 : -5), 0],
              opacity: [0.03, 0.06, 0.03],
            }}
            transition={{
              duration: 6 + (i % 4),
              repeat: Infinity,
              ease: "easeInOut",
              delay: i * 0.5,
            }}
          >
            {piece}
          </motion.div>
        ))}
      </div>

      {/* ═══ NAVBAR ═══ */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#08080E]/80 backdrop-blur-xl">
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
        {/* Animated gradient orbs */}
        <motion.div
          className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full blur-[150px]"
          style={{ background: "radial-gradient(circle, rgba(234,179,8,0.12) 0%, transparent 70%)" }}
          animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute bottom-1/3 right-1/4 w-[400px] h-[400px] rounded-full blur-[120px]"
          style={{ background: "radial-gradient(circle, rgba(234,179,8,0.08) 0%, transparent 70%)" }}
          animate={{ scale: [1.2, 1, 1.2], opacity: [0.2, 0.4, 0.2] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />

        <div className="relative z-10 max-w-6xl mx-auto px-6 py-24 w-full">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Left: Text */}
            <div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-amber-500/20 bg-amber-500/5 text-amber-400 text-xs font-mono mb-6"
              >
                <motion.div
                  animate={{ rotate: [0, 360] }}
                  transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                >
                  <Zap className="w-3 h-3" strokeWidth={2.5} />
                </motion.div>
                AI-Powered Chess Coaching
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="text-5xl sm:text-6xl font-heading font-bold tracking-tighter leading-[0.95] text-white mb-6"
              >
                Your coach
                <br />
                <span className="relative">
                  <span className="text-amber-400">remembers</span>
                  <motion.div
                    className="absolute -bottom-1 left-0 right-0 h-[3px] bg-amber-400/40 rounded-full"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ delay: 0.8, duration: 0.6 }}
                  />
                </span>
                <br />
                every mistake.
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="text-lg text-gray-400 leading-relaxed max-w-lg mb-8"
              >
                Not another analysis tool. A coach that tracks your patterns, knows your weaknesses by name, and tells you exactly what to fix.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                className="flex flex-col sm:flex-row gap-4"
              >
                <button
                  onClick={handleLogin}
                  data-testid="hero-cta-button"
                  className="group px-8 py-4 text-base font-semibold text-black rounded-xl bg-amber-400 hover:bg-amber-300 transition-all shadow-lg shadow-amber-500/20 hover:shadow-amber-500/40 flex items-center justify-center gap-2"
                >
                  Start Free
                  <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
                <button
                  onClick={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })}
                  className="px-8 py-4 text-base text-gray-300 border border-white/10 rounded-xl hover:border-white/25 hover:text-white transition-all"
                  data-testid="learn-more-button"
                >
                  How it works
                </button>
              </motion.div>
            </div>

            {/* Right: AI Coach Visual */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.4, duration: 0.6 }}
              className="hidden lg:block relative"
            >
              {/* Chess board with AI overlay */}
              <div className="relative">
                {/* Glowing border */}
                <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-amber-500/20 via-amber-500/5 to-amber-500/20 blur-sm" />

                <div className="relative rounded-2xl border border-white/10 bg-[#0C0C14] overflow-hidden">
                  {/* AI Coach header bar */}
                  <div className="px-4 py-3 border-b border-white/5 flex items-center gap-3">
                    <div className="relative">
                      <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center">
                        <Brain className="w-4 h-4 text-amber-400" />
                      </div>
                      <motion.div
                        className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-[#0C0C14]"
                        animate={{ scale: [1, 1.3, 1] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">ChessGuru Coach</p>
                      <p className="text-[10px] text-emerald-400">Watching your game...</p>
                    </div>
                  </div>

                  {/* Mini chess board (CSS) */}
                  <div className="p-4">
                    <div className="grid grid-cols-8 gap-0 aspect-square rounded-lg overflow-hidden border border-white/5">
                      {Array.from({ length: 64 }).map((_, i) => {
                        const row = Math.floor(i / 8);
                        const col = i % 8;
                        const isLight = (row + col) % 2 === 0;
                        const pieces = { 0: "♜♞♝♛♚♝♞♜", 1: "♟♟♟♟♟♟♟♟", 6: "♙♙♙♙♙♙♙♙", 7: "♖♘♗♕♔♗♘♖" };
                        const piece = pieces[row]?.[col] || "";
                        // Highlight some squares for coaching effect
                        const isHighlighted = (row === 4 && col === 4) || (row === 3 && col === 3);
                        const isArrowStart = row === 6 && col === 4;
                        const isArrowEnd = row === 4 && col === 4;
                        return (
                          <div
                            key={i}
                            className={`aspect-square flex items-center justify-center text-sm sm:text-base relative ${
                              isLight ? "bg-amber-200/10" : "bg-amber-900/15"
                            } ${isHighlighted ? "ring-1 ring-inset ring-amber-500/30" : ""}`}
                          >
                            {piece && <span className="opacity-80">{piece}</span>}
                            {isArrowEnd && (
                              <motion.div
                                className="absolute inset-0 bg-green-500/15 rounded-sm"
                                animate={{ opacity: [0, 0.4, 0] }}
                                transition={{ duration: 2, repeat: Infinity }}
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Coach message overlay */}
                  <motion.div
                    className="mx-4 mb-4 p-3 rounded-lg border border-amber-500/20 bg-amber-500/5"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 1.2 }}
                  >
                    <motion.p
                      className="text-xs text-amber-300 leading-relaxed"
                      animate={{ opacity: [0.7, 1, 0.7] }}
                      transition={{ duration: 3, repeat: Infinity }}
                    >
                      "Piece safety again. We keep coming back to this. Rule: before every move, check — is anything under attack?"
                    </motion.p>
                  </motion.div>

                  {/* Escape squares indicator */}
                  <div className="mx-4 mb-4 flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/10 border border-red-500/20">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
                      <span className="text-[10px] text-red-400 font-mono">2 escapes</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span className="text-[10px] text-emerald-400 font-mono">Pattern: -3</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/20">
                      <Zap className="w-2.5 h-2.5 text-amber-400" />
                      <span className="text-[10px] text-amber-400 font-mono">Brilliant</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══ SOCIAL PROOF BAR ═══ */}
      <section className="py-8 border-y border-white/5 bg-white/[0.01]">
        <div className="max-w-4xl mx-auto px-6">
          <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12 text-center">
            {[
              { value: "600-1500", label: "Target Rating" },
              { value: "6", label: "Strength Domains" },
              { value: "<2s", label: "Move Analysis" },
              { value: "Free", label: "To Start" },
            ].map((s) => (
              <div key={s.label}>
                <p className="text-xl sm:text-2xl font-heading font-bold text-white">{s.value}</p>
                <p className="text-[10px] uppercase tracking-wider text-gray-600 font-mono">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section id="how-it-works" className="py-28 relative">
        <div className="relative z-10 max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">How it works</p>
            <h2 className="text-3xl sm:text-4xl font-heading font-bold tracking-tight text-white text-center mb-16">
              Three steps to better chess.
            </h2>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { step: "01", title: "Import your games", desc: "Connect Chess.com or Lichess. We analyze every game with Stockfish and behavioral AI.", icon: Target },
              { step: "02", title: "See your patterns", desc: "Not just blunders — recurring thinking errors. The same mistake in game 5 and game 50? We track it.", icon: Eye },
              { step: "03", title: "Train what matters", desc: "Puzzles from YOUR games. Training plans for YOUR weaknesses. Progress you can measure.", icon: TrendingUp },
            ].map((item, i) => (
              <FadeIn key={item.step} delay={i * 0.15}>
                <div className="group border border-white/5 rounded-xl p-6 bg-white/[0.02] hover:border-amber-500/20 hover:bg-amber-500/[0.02] transition-all duration-300 h-full">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-amber-400/30 font-mono text-sm font-bold">{item.step}</span>
                    <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center group-hover:bg-amber-500/15 transition-colors">
                      <item.icon className="w-4 h-4 text-amber-400" strokeWidth={1.5} />
                    </div>
                  </div>
                  <h3 className="text-lg font-heading font-semibold text-white mb-2">{item.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ KEY FEATURES ═══ */}
      <section className="py-28 relative">
        <div className="relative z-10 max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase font-mono text-amber-400 text-center mb-4">Why this is different</p>
            <h2 className="text-3xl sm:text-4xl font-heading font-bold tracking-tight text-white text-center mb-4">
              Chess.com shows you the blunder.
            </h2>
            <p className="text-xl text-gray-500 text-center mb-16">
              We show you <span className="text-amber-400 font-medium">why you keep making it.</span>
            </p>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              {
                icon: Brain, title: "Pattern Memory",
                desc: '"This is the 5th game where you collapse when winning." Your coach tracks every mistake pattern and knows when it\'s getting worse — or better.',
                detail: { label: "piece_safety: 7x this week", color: "red" },
              },
              {
                icon: MessageSquare, title: "Talks to YOUR level",
                desc: "An 800 and a 1600 player get completely different coaching from the same game. Beginners get encouragement. Advanced players get Socratic questions.",
                detail: null,
              },
              {
                icon: Zap, title: "Celebrates your wins",
                desc: "Most tools only tell you what went wrong. We detect brilliant sacrifices, track your strengths, and tell you what you're actually good at.",
                detail: { label: "Brilliant sacrifice detected", color: "amber" },
              },
              {
                icon: Crown, title: "Escape Square Awareness",
                desc: "No other chess app teaches you to count escape squares, reduce them, and trap pieces. This is real positional intelligence.",
                detail: { label: "2 escapes left — block one", color: "amber" },
              },
            ].map((item, i) => (
              <FadeIn key={item.title} delay={i * 0.1}>
                <div className="group border border-white/5 rounded-xl p-6 bg-white/[0.02] hover:border-amber-500/15 transition-all duration-300">
                  <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center mb-4 group-hover:bg-amber-500/15 transition-colors">
                    <item.icon className="w-5 h-5 text-amber-400" strokeWidth={1.5} />
                  </div>
                  <h3 className="text-lg font-heading font-semibold text-white mb-2">{item.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed mb-3">{item.desc}</p>
                  {item.detail && (
                    <div className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md border ${
                      item.detail.color === "red" ? "text-red-400 bg-red-500/10 border-red-500/20" :
                      "text-amber-400 bg-amber-500/10 border-amber-500/20"
                    }`}>
                      {item.detail.color === "amber" && <Zap className="w-2.5 h-2.5" strokeWidth={2.5} />}
                      {item.detail.label}
                    </div>
                  )}
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ COACH QUOTE ═══ */}
      <section className="py-24 relative">
        <div className="relative z-10 max-w-3xl mx-auto px-6 text-center">
          <FadeIn>
            <motion.div
              className="w-14 h-14 rounded-xl bg-amber-500/10 flex items-center justify-center mx-auto mb-8 border border-amber-500/20"
              animate={{ rotate: [0, 5, -5, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            >
              <img src="/chessguru-logo.svg" alt="" className="w-7 h-7" />
            </motion.div>
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

      {/* ═══ FINAL CTA ═══ */}
      <section className="py-28">
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
              className="group px-10 py-4 text-base font-semibold text-black rounded-xl bg-amber-400 hover:bg-amber-300 transition-all shadow-lg shadow-amber-500/20 hover:shadow-amber-500/40 inline-flex items-center gap-2"
            >
              Start Free with Google
              <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
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
          <p className="text-xs text-gray-700">Built with AI. Made for chess players.</p>
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
