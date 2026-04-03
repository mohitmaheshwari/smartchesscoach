import { useTheme } from "@/context/ThemeContext";
import { ChevronRight, Moon, Sun, Code } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { motion, useInView } from "framer-motion";
import { API } from "@/App";

const HERO_IMG = "https://static.prod-images.emergentagent.com/jobs/55020d83-23ce-4764-a37f-0abe803378b2/images/c9263ac5c3e6cf8ed2eaf315c1308e2fe6cb6feafe328f091610d7fae02abf30.png";
const COACH_EYES = "https://static.prod-images.emergentagent.com/jobs/55020d83-23ce-4764-a37f-0abe803378b2/images/c88d28423f6c01a8e6fe222c26163e3840080d26944deba24ae81b4d029001ed.png";
const WINE_TEXTURE = "https://static.prod-images.emergentagent.com/jobs/55020d83-23ce-4764-a37f-0abe803378b2/images/d7c061453f7782ee85190ad5328b89d3d498bd026d789180f54299ac5a0a4304.png";

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
    <div className="min-h-screen bg-background">
      {/* ═══ NAVBAR ═══ */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-background/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2.5">
              <img src="/chessguru-logo.svg" alt="ChessGuru" className="w-7 h-7" />
              <span className="text-lg font-heading font-semibold text-foreground">ChessGuru</span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={toggleTheme} className="p-2 text-muted-foreground hover:text-foreground transition-colors rounded-md hover:bg-muted/50" data-testid="theme-toggle">
                {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button
                onClick={handleLogin}
                data-testid="login-button"
                className="px-5 py-2 text-sm text-white font-medium transition-all hover:opacity-90 rounded-md bg-wine"
              >
                Get Started
              </button>
              {devMode && (
                <button
                  onClick={handleDevLogin}
                  disabled={devLoading}
                  className="px-4 py-2 text-sm border border-primary/40 text-primary rounded-md transition-all flex items-center gap-1.5 hover:bg-primary/5"
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
          <div className="absolute inset-0 bg-gradient-to-r from-background via-background/90 to-background/30" />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-background/30" />
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-8 py-24 w-full">
          <div className="max-w-2xl">
            <motion.p
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
              className="text-xs tracking-[0.25em] uppercase mb-6 font-mono text-primary"
            >
              AI Chess Coaching
            </motion.p>

            <motion.h1
              initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
              className="text-5xl sm:text-6xl lg:text-7xl font-heading tracking-tighter leading-[0.9] text-foreground mb-8"
            >
              Your coach
              <br />
              <span className="text-wine font-bold">remembers</span>
              <br />
              everything.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}
              className="text-lg text-muted-foreground leading-relaxed max-w-lg mb-10"
            >
              Not another analysis tool. A coach that tracks your patterns across games,
              knows your weaknesses by name, and tells you exactly what to fix.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 }}
              className="flex flex-col sm:flex-row gap-4"
            >
              <button
                onClick={handleLogin}
                data-testid="hero-cta-button"
                className="px-8 py-4 text-base text-white font-medium transition-all hover:opacity-90 flex items-center justify-center gap-2 rounded-lg bg-wine"
              >
                Start Free
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => document.getElementById("coach-section")?.scrollIntoView({ behavior: "smooth" })}
                className="px-8 py-4 text-base text-foreground border border-border transition-all hover:border-foreground/30 rounded-lg"
                data-testid="learn-more-button"
              >
                See how it works
              </button>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══ COACH PERSONA ═══ */}
      <section id="coach-section" className="relative py-32 overflow-hidden bg-gray-950">
        <div className="absolute inset-0 z-0">
          <img src={COACH_EYES} alt="" className="w-full h-full object-cover object-top opacity-30" />
          <div className="absolute inset-0 bg-gradient-to-b from-gray-950 via-gray-950/60 to-gray-950" />
        </div>

        <div className="relative z-10 max-w-5xl mx-auto px-6 lg:px-8 text-center">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase mb-8 font-mono text-amber-400">
              Meet Your Coach
            </p>
          </FadeIn>
          <FadeIn delay={0.2}>
            <blockquote className="text-3xl sm:text-4xl lg:text-5xl italic text-gray-200 leading-tight mb-10 font-heading">
              "You didn't lose over many mistakes.
              <br />
              <span className="text-red-400/80">You lost in one moment</span>
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
      <section className="py-32 bg-background">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <FadeIn>
            <p className="text-xs tracking-[0.25em] uppercase mb-4 font-mono text-primary">
              What Makes This Different
            </p>
            <h2 className="text-4xl sm:text-5xl tracking-tighter text-foreground mb-16 font-heading">
              Built around <span className="text-wine">you</span>, not the engine.
            </h2>
          </FadeIn>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
            {/* Chess DNA — Large card */}
            <FadeIn className="md:col-span-8 md:row-span-2" delay={0.1}>
              <div className="relative h-full min-h-[320px] overflow-hidden border border-border bg-card rounded-lg">
                <div className="absolute inset-0 z-0 opacity-[0.04]">
                  <img src={WINE_TEXTURE} alt="" className="w-full h-full object-cover" />
                </div>
                <div className="relative z-10 p-8 lg:p-10 h-full flex flex-col justify-between">
                  <div>
                    <p className="text-xs tracking-[0.2em] uppercase mb-3 font-mono text-primary">Your Chess DNA</p>
                    <h3 className="text-2xl sm:text-3xl text-foreground tracking-tight mb-4 font-heading">
                      Know who you are as a player.
                    </h3>
                    <p className="text-muted-foreground text-sm leading-relaxed max-w-lg">
                      Every game shapes your identity. Are you "The Thrower" who collapses in winning positions?
                      "The Blind Spot" who misses opponent threats? Your Chess DNA evolves game by game.
                    </p>
                  </div>
                  <div className="mt-8 flex flex-wrap gap-3">
                    {["The Thrower", "The Blind Spot", "The Strategist", "The Clock Fighter"].map((arch) => (
                      <span key={arch} className="px-3 py-1.5 text-xs border border-primary/30 text-primary font-mono rounded-md">
                        {arch}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </FadeIn>

            {/* Adaptive Decryption */}
            <FadeIn className="md:col-span-4" delay={0.2}>
              <FeatureCard label="Adaptive Decryption" title="Only what matters.">
                A 1100 player sees blunders. A 1600 sees inaccuracies.
                The same game, different coaching depth.
              </FeatureCard>
            </FadeIn>

            {/* Pattern Memory */}
            <FadeIn className="md:col-span-4" delay={0.3}>
              <FeatureCard label="Pattern Memory" title={<>"This is the 5th time."</>}>
                Your coach tracks every mistake across every game.
                Recurring patterns get flagged with brutal honesty.
              </FeatureCard>
            </FadeIn>

            {/* Community Training */}
            <FadeIn className="md:col-span-6" delay={0.4}>
              <FeatureCard label="Community Training" title="Train on real mistakes.">
                No composed puzzles. Solve positions where real players at your rating actually blundered.
                Learn from the community, not a textbook.
              </FeatureCard>
            </FadeIn>

            {/* Live Coach */}
            <FadeIn className="md:col-span-6" delay={0.5}>
              <FeatureCard label="Play With Coach" title="Feedback on every move.">
                Play against an AI opponent while your coach watches every move.
                Real-time guidance, not post-game analysis.
              </FeatureCard>
            </FadeIn>
          </div>
        </div>
      </section>

      {/* ═══ STATS ═══ */}
      <section className="py-24 border-t border-b border-border">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12">
            {[
              { value: "24/7", label: "Always available" },
              { value: "100%", label: "Personalized" },
              { value: "<2s", label: "Move analysis" },
              { value: "Free", label: "To start" },
            ].map((stat, i) => (
              <FadeIn key={stat.label} delay={i * 0.1} className="text-center">
                <p className="text-4xl sm:text-5xl font-heading font-bold tracking-tighter text-foreground mb-2">
                  {stat.value}
                </p>
                <p className="text-xs tracking-[0.15em] uppercase text-muted-foreground font-mono">
                  {stat.label}
                </p>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FINAL CTA ═══ */}
      <section className="py-32 bg-background">
        <div className="max-w-3xl mx-auto px-6 lg:px-8 text-center">
          <FadeIn>
            <h2 className="text-4xl sm:text-5xl tracking-tighter text-foreground mb-6 font-heading">
              Stop guessing.
              <br />
              <span className="text-wine">Start knowing.</span>
            </h2>
          </FadeIn>
          <FadeIn delay={0.2}>
            <p className="text-base text-muted-foreground mb-10 max-w-md mx-auto">
              Import your games from Chess.com or Lichess.
              Your coach starts learning who you are from game one.
            </p>
          </FadeIn>
          <FadeIn delay={0.4}>
            <button
              onClick={handleLogin}
              data-testid="cta-button"
              className="px-10 py-4 text-base text-white font-medium transition-all hover:opacity-90 inline-flex items-center gap-2 rounded-lg bg-wine"
            >
              Start Free with Google
              <ChevronRight className="w-4 h-4" />
            </button>
          </FadeIn>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-8 border-t border-border">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/chessguru-logo.svg" alt="" className="w-5 h-5" />
            <span className="text-sm text-muted-foreground font-heading">ChessGuru</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Built with AI. Made for chess players.
          </p>
        </div>
      </footer>
    </div>
  );
};

// Feature card component
const FeatureCard = ({ label, title, children }) => (
  <div className="h-full min-h-[150px] border border-border bg-card p-6 lg:p-8 flex flex-col justify-between rounded-lg hover:border-primary/20 transition-colors">
    <div>
      <p className="text-xs tracking-[0.2em] uppercase mb-3 font-mono text-primary">{label}</p>
      <h3 className="text-xl text-foreground tracking-tight mb-3 font-heading">{title}</h3>
    </div>
    <p className="text-muted-foreground text-sm leading-relaxed">{children}</p>
  </div>
);

// Scroll-triggered fade-in
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
