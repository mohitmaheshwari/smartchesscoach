import { Button } from "@/components/ui/button";
import { useTheme } from "@/context/ThemeContext";
import { ChevronRight, Moon, Sun, Code } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { motion, useInView } from "framer-motion";

const HERO_IMG = "https://static.prod-images.emergentagent.com/jobs/55020d83-23ce-4764-a37f-0abe803378b2/images/c9263ac5c3e6cf8ed2eaf315c1308e2fe6cb6feafe328f091610d7fae02abf30.png";
const COACH_EYES = "https://static.prod-images.emergentagent.com/jobs/55020d83-23ce-4764-a37f-0abe803378b2/images/c88d28423f6c01a8e6fe222c26163e3840080d26944deba24ae81b4d029001ed.png";
const WINE_TEXTURE = "https://static.prod-images.emergentagent.com/jobs/55020d83-23ce-4764-a37f-0abe803378b2/images/d7c061453f7782ee85190ad5328b89d3d498bd026d789180f54299ac5a0a4304.png";

const WINE = "#722F37";
const GOLD = "#CBA135";

const Landing = () => {
  const { theme, toggleTheme } = useTheme();
  const [devMode, setDevMode] = useState(false);
  const [devLoading, setDevLoading] = useState(false);
  const API_URL = process.env.REACT_APP_BACKEND_URL || "";

  const getPostAuthRedirect = () => window.sessionStorage.getItem("post_auth_redirect") || "/dashboard";

  useEffect(() => {
    const checkDevMode = async () => {
      try {
        const response = await fetch(`${API_URL}/api/auth/status`);
        const data = await response.json();
        setDevMode(data.dev_mode === true);
      } catch (e) {}
    };
    checkDevMode();
  }, [API_URL]);

  const handleLogin = async () => {
    const isEmergentEnv = window.location.hostname.includes("emergentagent") || window.location.hostname.includes("preview") || API_URL.includes("emergentagent") || API_URL.includes("preview");
    if (isEmergentEnv) {
      const redirectUrl = window.location.origin + getPostAuthRedirect();
      window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    } else {
      try {
        const response = await fetch(`${API_URL}/api/auth/google/login`);
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
      const response = await fetch(`${API_URL}/api/auth/dev-login`, { credentials: "include" });
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
    <div className="min-h-screen" style={{ background: "#F5F3F0", fontFamily: "'DM Sans', sans-serif" }}>
      {/* ═══ NAVBAR ═══ */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b" style={{ borderColor: "rgba(0,0,0,0.06)", background: "rgba(245,243,240,0.7)", backdropFilter: "blur(24px)" }}>
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <img src="/chessguru-logo.svg" alt="ChessGuru" className="w-7 h-7" />
              <span className="text-lg font-semibold tracking-tight text-gray-900" style={{ fontFamily: "'Playfair Display', serif" }}>
                ChessGuru
              </span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={toggleTheme} className="p-2 text-gray-500 hover:text-gray-900 transition-colors" data-testid="theme-toggle">
                {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button
                onClick={handleLogin}
                data-testid="login-button"
                className="px-5 py-2 text-sm text-gray-900 transition-all hover:opacity-90"
                style={{ background: WINE, border: `1px solid ${WINE}` }}
              >
                Get Started
              </button>
              {devMode && (
                <button
                  onClick={handleDevLogin}
                  disabled={devLoading}
                  className="px-4 py-2 text-sm text-amber-400 border border-amber-500/40 hover:bg-amber-500/10 transition-all flex items-center gap-1.5"
                  data-testid="dev-login-button"
                >
                  <Code className="w-3.5 h-3.5" />
                  {devLoading ? "..." : "Dev Login"}
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ═══ HERO ═══ */}
      <section className="relative min-h-screen flex items-center overflow-hidden pt-16">
        <div className="absolute inset-0 z-0">
          <img src={HERO_IMG} alt="" className="w-full h-full object-cover object-center" />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to right, #F5F3F0 0%, #F5F3F0 35%, rgba(245,243,240,0.6) 65%, transparent 100%)" }} />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to top, #F5F3F0 0%, transparent 40%)" }} />
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-8 py-24 w-full">
          <div className="max-w-2xl">
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-xs tracking-[0.25em] uppercase mb-6"
              style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}
            >
              AI Chess Coaching
            </motion.p>

            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-light tracking-tighter leading-[0.9] text-gray-900 mb-8"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              Your coach
              <br />
              <span style={{ color: WINE }} className="font-semibold">remembers</span>
              <br />
              everything.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="text-lg text-gray-500 leading-relaxed max-w-lg mb-10"
            >
              Not another analysis tool. A coach that tracks your patterns across games, 
              knows your weaknesses by name, and tells you exactly what to fix.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 }}
              className="flex flex-col sm:flex-row gap-4"
            >
              <button
                onClick={handleLogin}
                data-testid="hero-cta-button"
                className="px-8 py-4 text-base text-gray-900 transition-all hover:opacity-90 flex items-center justify-center gap-2"
                style={{ background: WINE, border: `1px solid ${WINE}` }}
              >
                Start Free
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => document.getElementById("coach-section")?.scrollIntoView({ behavior: "smooth" })}
                className="px-8 py-4 text-base text-gray-900/70 border transition-all hover:text-gray-900 hover:border-white/30"
                style={{ borderColor: "rgba(0,0,0,0.1)", background: "transparent" }}
                data-testid="learn-more-button"
              >
                See how it works
              </button>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══ COACH PERSONA ═══ */}
      <section id="coach-section" className="relative py-32 overflow-hidden">
        <div className="absolute inset-0 z-0">
          <img src={COACH_EYES} alt="" className="w-full h-full object-cover object-top opacity-30" />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to bottom, #F5F3F0, rgba(245,243,240,0.3) 40%, #F5F3F0)" }} />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to right, #F5F3F0 20%, transparent 60%, #F5F3F0 100%)" }} />
        </div>

        <div className="relative z-10 max-w-5xl mx-auto px-6 lg:px-8 text-center">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase mb-8" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              Meet Your Coach
            </p>
          </FadeIn>
          <FadeIn delay={0.2}>
            <blockquote
              className="text-3xl sm:text-4xl lg:text-5xl italic text-gray-200 leading-tight mb-10"
              style={{ fontFamily: "'Playfair Display', serif" }}
            >
              "You didn't lose over many mistakes.
              <br />
              <span style={{ color: WINE }}>You lost in one moment</span>
              <br />
              of inattention."
            </blockquote>
          </FadeIn>
          <FadeIn delay={0.4}>
            <p className="text-base text-gray-500 max-w-xl mx-auto leading-relaxed">
              No generic advice. No engine dumps. Your coach identifies the ONE thing 
              that cost you the game and tells you exactly how to fix it.
            </p>
          </FadeIn>
        </div>
      </section>

      {/* ═══ BENTO FEATURES ═══ */}
      <section className="py-32">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase mb-4" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
              What Makes This Different
            </p>
            <h2 className="text-4xl sm:text-5xl tracking-tighter text-gray-900 mb-16" style={{ fontFamily: "'Playfair Display', serif" }}>
              Built around <span style={{ color: WINE }}>you</span>, not the engine.
            </h2>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
            {/* Chess DNA — Large card */}
            <FadeIn className="md:col-span-8 md:row-span-2" delay={0.1}>
              <div className="relative h-full min-h-[320px] overflow-hidden border" style={{ borderColor: "rgba(0,0,0,0.08)", background: "rgba(255,255,255,0.6)", backdropFilter: "blur(16px)" }}>
                <div className="absolute inset-0 z-0 opacity-20">
                  <img src={WINE_TEXTURE} alt="" className="w-full h-full object-cover" />
                </div>
                <div className="relative z-10 p-8 lg:p-10 h-full flex flex-col justify-between">
                  <div>
                    <p className="text-xs tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>Your Chess DNA</p>
                    <h3 className="text-2xl sm:text-3xl text-gray-900 tracking-tight mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
                      Know who you are as a player.
                    </h3>
                    <p className="text-gray-500 text-sm leading-relaxed max-w-lg">
                      Every game shapes your identity. Are you "The Thrower" who collapses in winning positions? 
                      "The Blind Spot" who misses opponent threats? Your Chess DNA evolves game by game, 
                      showing exactly who you're becoming.
                    </p>
                  </div>
                  <div className="mt-8 flex flex-wrap gap-3">
                    {["The Thrower", "The Blind Spot", "The Strategist", "The Clock Fighter"].map((arch) => (
                      <span key={arch} className="px-3 py-1.5 text-xs border" style={{ borderColor: "rgba(203,161,53,0.3)", color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>
                        {arch}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </FadeIn>

            {/* Adaptive Decryption */}
            <FadeIn className="md:col-span-4" delay={0.2}>
              <div className="h-full min-h-[150px] border p-6 lg:p-8 flex flex-col justify-between" style={{ borderColor: "rgba(0,0,0,0.08)", background: "rgba(255,255,255,0.6)", backdropFilter: "blur(16px)" }}>
                <div>
                  <p className="text-xs tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>Adaptive Decryption</p>
                  <h3 className="text-xl text-gray-900 tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
                    Only what matters.
                  </h3>
                </div>
                <p className="text-gray-500 text-sm leading-relaxed">
                  A 1100 player sees blunders. A 1600 sees inaccuracies. 
                  The same game, different coaching depth.
                </p>
              </div>
            </FadeIn>

            {/* Pattern Memory */}
            <FadeIn className="md:col-span-4" delay={0.3}>
              <div className="h-full min-h-[150px] border p-6 lg:p-8 flex flex-col justify-between" style={{ borderColor: "rgba(0,0,0,0.08)", background: "rgba(255,255,255,0.6)", backdropFilter: "blur(16px)" }}>
                <div>
                  <p className="text-xs tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>Pattern Memory</p>
                  <h3 className="text-xl text-gray-900 tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
                    "This is the 5th time."
                  </h3>
                </div>
                <p className="text-gray-500 text-sm leading-relaxed">
                  Your coach tracks every mistake across every game.
                  Recurring patterns get flagged with brutal honesty.
                </p>
              </div>
            </FadeIn>

            {/* Community Training */}
            <FadeIn className="md:col-span-6" delay={0.4}>
              <div className="h-full min-h-[150px] border p-6 lg:p-8" style={{ borderColor: "rgba(0,0,0,0.08)", background: "rgba(255,255,255,0.6)", backdropFilter: "blur(16px)" }}>
                <p className="text-xs tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>Community Training</p>
                <h3 className="text-xl text-gray-900 tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
                  Train on real mistakes.
                </h3>
                <p className="text-gray-500 text-sm leading-relaxed">
                  No composed puzzles. Solve positions where real players at your rating actually blundered. 
                  Learn from the community, not a textbook.
                </p>
              </div>
            </FadeIn>

            {/* Live Coach */}
            <FadeIn className="md:col-span-6" delay={0.5}>
              <div className="h-full min-h-[150px] border p-6 lg:p-8" style={{ borderColor: "rgba(0,0,0,0.08)", background: "rgba(255,255,255,0.6)", backdropFilter: "blur(16px)" }}>
                <p className="text-xs tracking-[0.2em] uppercase mb-3" style={{ color: GOLD, fontFamily: "'JetBrains Mono', monospace" }}>Play With Coach</p>
                <h3 className="text-xl text-gray-900 tracking-tight mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>
                  Feedback on every move.
                </h3>
                <p className="text-gray-500 text-sm leading-relaxed">
                  Play against an AI opponent while your coach watches every move. 
                  Real-time guidance, not post-game analysis.
                </p>
              </div>
            </FadeIn>
          </div>
        </div>
      </section>

      {/* ═══ STATS ═══ */}
      <section className="py-24 border-t border-b" style={{ borderColor: "rgba(0,0,0,0.06)" }}>
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12">
            {[
              { value: "24/7", label: "Always available" },
              { value: "100%", label: "Personalized" },
              { value: "<2s", label: "Move analysis" },
              { value: "Free", label: "To start" },
            ].map((stat, i) => (
              <FadeIn key={stat.label} delay={i * 0.1} className="text-center">
                <p className="text-4xl sm:text-5xl font-light tracking-tighter text-gray-900 mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>
                  {stat.value}
                </p>
                <p className="text-xs tracking-[0.15em] uppercase text-gray-500" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {stat.label}
                </p>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA ═══ */}
      <section className="py-32">
        <div className="max-w-3xl mx-auto px-6 lg:px-8 text-center">
          <FadeIn>
            <h2 className="text-4xl sm:text-5xl tracking-tighter text-gray-900 mb-6" style={{ fontFamily: "'Playfair Display', serif" }}>
              Stop guessing.
              <br />
              <span style={{ color: WINE }}>Start knowing.</span>
            </h2>
          </FadeIn>
          <FadeIn delay={0.2}>
            <p className="text-base text-gray-500 mb-10 max-w-md mx-auto">
              Import your games from Chess.com or Lichess. 
              Your coach starts learning who you are from game one.
            </p>
          </FadeIn>
          <FadeIn delay={0.4}>
            <button
              onClick={handleLogin}
              data-testid="cta-button"
              className="px-10 py-4 text-base text-gray-900 transition-all hover:opacity-90 inline-flex items-center gap-2"
              style={{ background: WINE, border: `1px solid ${WINE}` }}
            >
              Start Free with Google
              <ChevronRight className="w-4 h-4" />
            </button>
          </FadeIn>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-8 border-t" style={{ borderColor: "rgba(0,0,0,0.06)" }}>
        <div className="max-w-7xl mx-auto px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/chessguru-logo.svg" alt="" className="w-5 h-5" />
            <span className="text-sm text-gray-500" style={{ fontFamily: "'Playfair Display', serif" }}>ChessGuru</span>
          </div>
          <p className="text-xs text-gray-500">
            Built with AI. Made for chess players.
          </p>
        </div>
      </footer>
    </div>
  );
};

// Scroll-triggered fade-in component
const FadeIn = ({ children, delay = 0, className = "" }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 30 }}
      transition={{ duration: 0.7, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

export default Landing;
