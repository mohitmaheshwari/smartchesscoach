import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight, BookOpen, BrainCircuit, Check, ChevronDown, ChevronRight,
  Clock3, Code, Crosshair, Eye, Flag, Gamepad2, GraduationCap,
  LineChart, LockKeyhole, Moon, RefreshCw, ShieldCheck, Sparkles, Sun, Target,
  TimerReset, TrendingDown, Zap,
} from "lucide-react";
import { API } from "@/App";
import { ANALYTICS_EVENTS, track } from "@/lib/analytics";
import { Capacitor } from "@capacitor/core";
import { Browser } from "@capacitor/browser";
import { useTheme } from "@/context/ThemeContext";

const ACID = "#7FB069";
const MINT = "#7EE7C2";
const CORAL = "#FF8066";
const ease = [0.22, 1, 0.36, 1];

const scrollToId = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

function Reveal({ children, className = "", delay = 0 }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 28 }}
      whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.7, delay, ease }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function PrimaryButton({ children, onClick, testId, className = "" }) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.button
      type="button"
      onClick={onClick}
      data-testid={testId}
      whileHover={reduceMotion ? undefined : { y: -2, scale: 1.01 }}
      whileTap={reduceMotion ? undefined : { scale: 0.98 }}
      className={`group inline-flex min-h-12 items-center justify-center gap-2 rounded-full px-6 py-3.5 text-sm font-bold text-[#0A1712] shadow-[0_18px_55px_rgba(127,176,105,0.2)] transition-shadow hover:shadow-[0_22px_70px_rgba(127,176,105,0.3)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7FB069] focus-visible:ring-offset-2 focus-visible:ring-offset-[#071411] ${className}`}
      style={{ background: ACID }}
    >
      {children}<ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
    </motion.button>
  );
}

function PlanPreview() {
  const { theme } = useTheme();
  const isDark = theme !== "light";
  const reduceMotion = useReducedMotion();
  const stages = ["Learn", "Practise", "Blind test", "Play", "Verify"];
  return (
    <div className="relative mx-auto w-full max-w-[520px]">
      <motion.div aria-hidden="true" animate={reduceMotion ? undefined : { rotate: [0, 3, 0], y: [0, -7, 0] }} transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }} className="absolute -right-6 top-12 h-32 w-32 rounded-[32px] border border-[#7FB069]/20 bg-[#7FB069]/10 pointer-events-none" />
      <motion.div aria-hidden="true" animate={reduceMotion ? undefined : { rotate: [0, -4, 0], y: [0, 8, 0] }} transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }} className="absolute -bottom-6 -left-5 h-28 w-28 rounded-full border border-[#7EE7C2]/20 bg-[#7EE7C2]/10 pointer-events-none" />
      <div className={`relative overflow-hidden rounded-[30px] border shadow-2xl backdrop-blur-xl transition-all ${isDark ? "border-white/15 bg-[#0D211B]/95 shadow-[0_36px_100px_rgba(0,0,0,0.38)]" : "border-slate-300/80 bg-white/95 shadow-[0_30px_70px_rgba(0,0,0,0.08)]"}`}>
        <div className={`flex items-center justify-between border-b px-5 py-4 sm:px-6 ${isDark ? "border-white/10" : "border-slate-200"}`}>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-[#7FB069] dark:text-[#7FB069]">A sample coaching conversation</p>
            <p className={`mt-1 font-heading text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Your path to 1200</p>
          </div>
          <div className="grid h-11 w-11 place-items-center rounded-2xl border border-[#7FB069]/25 bg-[#7FB069]/10"><Target className="h-5 w-5 text-[#7FB069]" /></div>
        </div>
        <div className="p-5 sm:p-6">
          <p className={`mb-4 text-sm leading-6 ${isDark ? "text-white/65" : "text-slate-600 font-medium"}`}>I’ve been looking through your games. You already see plenty of tactical chances. The part holding you back happens when your opponent attacks one of your pieces.</p>
          <div className={`rounded-2xl border p-4 ${isDark ? "border-[#FF8066]/25 bg-[#FF8066]/[0.07]" : "border-rose-200 bg-rose-50/70"}`}>
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-[#B94D37] dark:text-[#FF9B86]"><Crosshair className="h-3.5 w-3.5" /> Here’s where we start</div>
            <p className={`mt-2.5 font-heading text-xl font-semibold leading-tight ${isDark ? "text-white" : "text-slate-900"}`}>Slow down when a piece is attacked.</p>
            <ul className={`mt-4 space-y-2 text-xs leading-relaxed ${isDark ? "text-white/60" : "text-slate-600"}`}>
              <li className="flex gap-2"><span className="text-[#FF8066] font-bold">•</span>You often save the attacked piece but forget what it was protecting.</li>
              <li className="flex gap-2"><span className="text-[#FF8066] font-bold">•</span>It happens most when you answer quickly.</li>
              <li className="flex gap-2"><span className="text-[#FF8066] font-bold">•</span>Fixing this will help more than learning another opening line.</li>
            </ul>
          </div>
          <div className="mt-5">
            <div className="mb-3 flex items-center justify-between">
              <p className={`text-[10px] font-bold uppercase tracking-[0.18em] ${isDark ? "text-white/45" : "text-slate-400"}`}>This week</p>
              <p className="text-[10px] font-semibold text-emerald-600 dark:text-[#7EE7C2]">Adapts after every game</p>
            </div>
            <div className="grid grid-cols-5 gap-1.5">
              {stages.map((stage, index) => (
                <div key={stage} className="min-w-0">
                  <div className={`h-1.5 rounded-full ${index < 2 ? "bg-[#7FB069]" : (isDark ? "bg-white/10" : "bg-slate-200")}`} />
                  <p className={`mt-2 truncate text-[9px] ${index < 2 ? (isDark ? "text-white/75 font-semibold" : "text-slate-800 font-semibold") : (isDark ? "text-white/35" : "text-slate-400")}`}>{stage}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <motion.div animate={reduceMotion ? undefined : { y: [0, -6, 0] }} transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }} className={`absolute -bottom-7 right-5 flex items-center gap-3 rounded-2xl border px-4 py-3 shadow-xl sm:-right-7 ${isDark ? "border-white/15 bg-[#F4EFE4] text-[#071411]" : "border-slate-200 bg-white text-slate-900"}`}>
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-[#DDFCA4]"><TrendingDown className="h-4 w-4 text-emerald-800" /></div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#355047]">Your coach is noticing</p>
          <p className="text-sm font-bold">You’re checking first more often.</p>
        </div>
      </motion.div>
    </div>
  );
}

function SkillProfile() {
  const { theme } = useTheme();
  const isDark = theme !== "light";
  return (
    <div className={`rounded-[28px] border p-5 shadow-sm transition-all sm:p-7 ${isDark ? "border-[#16372C] bg-[#0B2019] shadow-[0_30px_70px_rgba(7,20,17,0.16)]" : "border-slate-300/80 bg-white shadow-md"}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className={`text-[10px] font-bold uppercase tracking-[0.2em] ${isDark ? "text-[#7EE7C2]" : "text-emerald-700"}`}>What your coach sees</p>
          <h3 className={`mt-2 font-heading text-2xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>You don’t need more opening theory right now.</h3>
        </div>
        <BrainCircuit className="h-6 w-6 text-[#7FB069]" />
      </div>
      <div className="mt-7 space-y-3">
        <div className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-slate-200 bg-slate-50"}`}>
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#7FB069]">What you already do well</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-white/65" : "text-slate-600"}`}>You notice attacking chances and usually understand what your opening is trying to achieve.</p>
        </div>
        <div className="rounded-2xl border border-[#FF8066]/20 bg-[#FF8066]/[0.06] p-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#FF9B86]">What keeps getting in the way</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-white/70" : "text-slate-700"}`}>When your opponent attacks something, you react to that piece and stop looking at the rest of the board.</p>
        </div>
      </div>
      <div className="mt-6 rounded-2xl bg-[#7FB069] p-4 text-[#071411]">
        <p className="text-[10px] font-bold uppercase tracking-[0.15em]">Our one rule for now</p>
        <p className="mt-1.5 text-sm font-semibold leading-relaxed">Before moving an attacked piece, ask what it is protecting. We’ll make that check feel automatic.</p>
      </div>
    </div>
  );
}

function LearningCard() {
  const { theme } = useTheme();
  const isDark = theme !== "light";
  return (
    <div className={`relative overflow-hidden rounded-[28px] border p-6 transition-all sm:p-8 ${isDark ? "border-white/10 bg-[#0D211B] shadow-[0_30px_70px_rgba(7,20,17,0.12)] text-white" : "border-slate-300/80 bg-white shadow-md text-slate-900"}`}>
      <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-[#FF8066]/10 blur-3xl pointer-events-none" />
      <div className="relative">
        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-[#B94D37]"><Eye className="h-4 w-4" /> Personal lesson</div>
        <h3 className={`mt-3 max-w-md font-heading text-3xl font-semibold leading-[1.08] ${isDark ? "text-white" : "text-slate-900"}`}>The lesson starts with what <em className="font-normal text-[#B94D37]">you</em> misunderstood.</h3>
        <div className="mt-7 grid gap-3">
          <div className={`rounded-2xl p-4 ${isDark ? "bg-white/5 border border-white/10" : "bg-slate-100/80 border border-slate-200"}`}>
            <p className={`text-[10px] font-bold uppercase tracking-[0.15em] ${isDark ? "text-white/50" : "text-slate-500"}`}>From your game</p>
            <p className={`mt-2 text-sm leading-relaxed ${isDark ? "text-white/85" : "text-slate-700"}`}>You moved the attacked knight, but that knight was the only piece defending e4.</p>
          </div>
          <div className={`rounded-2xl border border-[#7FB069] p-4 ${isDark ? "bg-[#7FB069]/15" : "bg-[#EEFFD0]"}`}>
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-[#466513] dark:text-[#7EE7C2]">Your coach</p>
            <p className={`mt-2 text-sm font-medium leading-relaxed ${isDark ? "text-white/90" : "text-[#17300F]"}`}>Before moving an attacked piece, look at what it protects. I’ve seen this same blind spot in your recent games, so we’re going to slow the moment down together.</p>
          </div>
          <div className={`flex items-center justify-between rounded-2xl border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"}`}>
            <div>
              <p className={`text-[10px] font-bold uppercase tracking-[0.15em] ${isDark ? "text-white/50" : "text-slate-500"}`}>Today’s practice</p>
              <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>A short set of new defender positions</p>
            </div>
            <div className={`grid h-11 w-11 place-items-center rounded-2xl ${isDark ? "bg-white/10 text-[#7FB069]" : "bg-slate-900 text-white"}`}><ArrowRight className="h-5 w-5" /></div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProofCard() {
  const { theme } = useTheme();
  const isDark = theme !== "light";
  return (
    <div className={`overflow-hidden rounded-[28px] border p-6 transition-all sm:p-8 ${isDark ? "border-white/10 bg-[#10271F] text-white" : "border-slate-300/80 bg-white text-slate-900 shadow-md"}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className={`text-[10px] font-bold uppercase tracking-[0.2em] ${isDark ? "text-[#7EE7C2]" : "text-emerald-700"}`}>A sample message from your coach</p>
          <h3 className={`mt-3 font-heading text-3xl font-semibold leading-tight ${isDark ? "text-white" : "text-slate-900"}`}>I’m not asking you to memorize the practice positions.</h3>
        </div>
        <LineChart className="h-6 w-6 shrink-0 text-[#7FB069]" />
      </div>
      <div className="mt-7 space-y-3">
        <div className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-black/10" : "border-slate-200 bg-slate-50"}`}>
          <p className={`text-[10px] font-bold uppercase tracking-[0.14em] ${isDark ? "text-white/40" : "text-slate-500"}`}>When we started</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-white/65" : "text-slate-600"}`}>When one of your pieces was attacked, you usually moved it at once. That was when another piece got left behind.</p>
        </div>
        <div className={`rounded-2xl border p-4 ${isDark ? "border-[#7FB069]/25 bg-[#7FB069]/[0.07]" : "border-emerald-200 bg-emerald-50/70"}`}>
          <p className={`text-[10px] font-bold uppercase tracking-[0.14em] ${isDark ? "text-[#7FB069]/75" : "text-emerald-700 font-semibold"}`}>What I’m seeing now</p>
          <p className={`mt-2 text-sm font-medium leading-6 ${isDark ? "text-white/80" : "text-slate-700"}`}>You’re beginning to pause and check what the piece protects before you move it. That is the habit we’re building.</p>
        </div>
        <div className={`flex items-start gap-3 rounded-2xl p-4 ${isDark ? "bg-black/15" : "bg-slate-100"}`}>
          <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-[#7EE7C2]" />
          <p className={`text-sm leading-6 ${isDark ? "text-white/60" : "text-slate-600"}`}><strong className="font-semibold text-emerald-700 dark:text-[#7EE7C2]">What comes next:</strong> I’ll keep watching your games. When this holds under pressure, we’ll move on together.</p>
        </div>
      </div>
    </div>
  );
}

const PROCESS = [
  ["01", "Evaluate", "Connect Chess.com or Lichess. ChessGuru studies recurring decisions across games—not one dramatic blunder.", Crosshair, CORAL],
  ["02", "Build your plan", "Tell me where you want to go and how much time you have. I’ll choose the one thing that deserves your attention first.", Target, ACID],
  ["03", "Learn and apply", "Understand the idea, practise with help, pass an unseen test, then carry one instruction into a real game.", GraduationCap, MINT],
  ["04", "See it in your games", "I’ll watch what happens when you play again. Once the new habit holds, we’ll choose your next lesson.", LineChart, "#FFD37E"],
];

const CURRICULUM = [
  ["Openings", BookOpen, "Plans selected from the structures you actually reach."],
  ["Traps", Zap, "Patterns taught when they matter in your games—not as tricks to memorize."],
  ["Endgames", Flag, "Exact technique matched to the endings you mishandle or are ready to learn."],
  ["Tactics", Crosshair, "Unlabelled positions that test recognition, not theme memorization."],
  ["Position play", BrainCircuit, "Weak squares, exchanges, pawn breaks, and piece relationships."],
  ["Decision habits", Clock3, "Threat response, candidate generation, calculation, and time use."],
];

const FAQS = [
  ["Does ChessGuru guarantee a rating jump by a deadline?", "No. Your rating also depends on how often you play, who you face, and the kind of games you choose. ChessGuru gives you a clear plan, teaches one important habit at a time, and watches your later games to see whether it is sticking."],
  ["How is this different from a game review?", "A game review explains one game. ChessGuru remembers what keeps happening, chooses the habit hurting you most, teaches it in different positions, and checks whether it returns when you play again."],
  ["Will I only get puzzles from my own games?", "Your games are the starting point, not the limit. ChessGuru can combine your positions with verified openings, traps, endgames, tactical geometry, and related positions selected for the same underlying skill."],
  ["Who is ChessGuru for?", "It is designed for 600–1500-rated players who are playing regularly, feel stuck, and want a clear answer to what they should learn next instead of another large content catalogue."],
];

const STRUCTURED_DATA = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      name: "ChessGuru",
      applicationCategory: "EducationalApplication",
      operatingSystem: "Web",
      description: "A personalized chess improvement system for 600–1500-rated players that builds training from their games and tracks recurring weaknesses.",
      offers: { "@type": "Offer", price: "0", priceCurrency: "INR" },
    },
    {
      "@type": "FAQPage",
      mainEntity: FAQS.map(([question, answer]) => ({
        "@type": "Question",
        name: question,
        acceptedAnswer: { "@type": "Answer", text: answer },
      })),
    },
  ],
};

export default function Landing() {
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();
  const [devMode, setDevMode] = useState(false);
  // Invite-only pre-launch. Defaults to CLOSED so a failed status fetch
  // never accidentally opens signups. docs/invite_only_signup_scope.md
  const [signupsOpen, setSignupsOpen] = useState(false);
  const [devLoading, setDevLoading] = useState(false);
  const [openFaq, setOpenFaq] = useState(0);

  useEffect(() => {
    track(ANALYTICS_EVENTS.FUNNEL_LANDING_VIEWED);
    fetch(`${API}/auth/status`).then((response) => response.json()).then((data) => setDevMode(data.dev_mode === true)).catch(() => {});
    fetch(`${API}/signup-status`).then((response) => response.json()).then((data) => setSignupsOpen(data.signups_open === true)).catch(() => {});
  }, []);

  const startPlan = async (source = "hero") => {
    track(ANALYTICS_EVENTS.FUNNEL_LANDING_CTA_CLICKED, { source });
    // INVITE-ONLY (2026-09-19). While signups are closed every landing CTA
    // asks for an invite instead of starting Google sign-in. /api/signup-status
    // is the single source of truth, so flipping SIGNUPS_OPEN=true restores
    // the original flow with no code change.
    // docs/invite_only_signup_scope.md
    if (!signupsOpen) {
      navigate(`/invite?from=${encodeURIComponent(source)}`);
      return;
    }
    window.sessionStorage.setItem("post_auth_redirect", "/welcome");
    const isNative = Capacitor.isNativePlatform();
    const startUrl = `${API}/auth/google/login?redirect_to=${encodeURIComponent("/welcome")}`;
    try {
      if (isNative) {
        await Browser.open({ url: `${startUrl}&platform=mobile&flow=redirect` });
        return;
      }

      const response = await fetch(startUrl, { credentials: "include" });
      const data = await response.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
        return;
      }
    } catch (_) { /* The normal login page remains the safe fallback. */ }
    navigate(`/login?redirect_to=${encodeURIComponent("/welcome")}`);
  };

  const handleDevLogin = async () => {
    setDevLoading(true);
    window.sessionStorage.setItem("post_auth_redirect", "/welcome");
    try {
      const response = await fetch(`${API}/auth/dev-login`, { credentials: "include" });
      const data = await response.json();
      if (data.status === "ok") window.location.href = "/welcome";
    } finally { setDevLoading(false); }
  };

  const { theme, toggleTheme } = useTheme();
  const isDark = theme !== "light";

  return (
    <div className={`experience-page experience-landing-page min-h-screen overflow-hidden transition-colors duration-300 ${isDark ? "bg-[#071411] text-white" : "!bg-[#FBF9F5] !text-slate-900"}`}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(STRUCTURED_DATA) }} />
      <header className={`fixed inset-x-0 top-0 z-50 border-b backdrop-blur-2xl transition-colors ${isDark ? "border-white/[0.08] bg-[#071411]/85" : "border-stone-200/90 bg-[#FBF9F5]/90"}`}>
        <div className="mx-auto flex h-[72px] max-w-[1240px] items-center justify-between px-5 sm:px-8">
          <button type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} className="flex items-center gap-2.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7FB069]">
            <img src="/chessguru-logo.svg" alt="" className="h-8 w-8" />
            <span className={`font-heading text-[17px] font-bold tracking-tight ${isDark ? "text-white" : "text-stone-900"}`}>ChessGuru</span>
          </button>
          <nav aria-label="Main navigation" className="hidden items-center gap-7 lg:flex">
            {[["How it works", "how-it-works"], ["The plan", "personal-plan"], ["Proof", "proof"]].map(([label, id]) => (
              <button key={id} type="button" onClick={() => scrollToId(id)} className={`text-sm transition-colors focus:outline-none focus-visible:text-[#7FB069] ${isDark ? "text-white/55 hover:text-white" : "text-stone-600 hover:text-stone-900 font-semibold"}`}>{label}</button>
            ))}
            <button type="button" onClick={() => navigate("/pricing")} className={`text-sm transition-colors ${isDark ? "text-white/55 hover:text-white" : "text-stone-600 hover:text-stone-900 font-semibold"}`}>Pricing</button>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Theme Toggle Button */}
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
              className={`inline-flex items-center justify-center h-9 w-9 rounded-full border transition-all ${isDark ? "border-white/15 bg-white/5 text-amber-400 hover:bg-white/10" : "border-stone-300 bg-white text-stone-700 hover:bg-stone-100 shadow-sm"}`}
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4 text-emerald-700" />}
            </button>
            {devMode && <button type="button" onClick={handleDevLogin} disabled={devLoading} data-testid="dev-login-button" className={`hidden rounded-full border px-3 py-2 text-xs transition-colors sm:inline-flex ${isDark ? "border-white/15 text-white/60 hover:text-white" : "border-stone-300 text-stone-700 hover:text-stone-900 bg-white"}`}><Code className="mr-1.5 h-3.5 w-3.5" />{devLoading ? "…" : "Dev"}</button>}
            <button type="button" onClick={() => navigate(`/login?redirect_to=${encodeURIComponent("/home")}`)} data-testid="signin-link" className={`hidden px-2 py-2 text-sm font-medium transition-colors sm:inline-flex ${isDark ? "text-white/60 hover:text-white" : "text-stone-600 hover:text-stone-900"}`}>Sign in</button>
            <button type="button" onClick={() => startPlan("nav")} data-testid="login-button" className={`rounded-full px-4 py-2.5 text-xs font-bold transition-all hover:-translate-y-0.5 sm:px-5 sm:text-sm ${isDark ? "bg-[#F4EFE4] text-[#071411] hover:bg-white" : "bg-stone-900 text-white hover:bg-stone-800 shadow-md"}`}>Build my plan</button>
          </div>
        </div>
      </header>

      <main>
        <section className={`relative isolate flex min-h-[900px] items-center overflow-hidden pb-28 pt-32 lg:min-h-screen lg:pb-24 lg:pt-28 transition-colors ${isDark ? "bg-[#071411]" : "bg-[#FBF9F5]"}`}>
          <div aria-hidden="true" className="absolute inset-0 -z-10 pointer-events-none">
            <div className={`absolute left-[-12%] top-[5%] h-[540px] w-[540px] rounded-full blur-[130px] ${isDark ? "bg-[#2C705A]/25" : "bg-emerald-400/10"}`} />
            <div className={`absolute right-[-8%] top-[18%] h-[500px] w-[500px] rounded-full blur-[140px] ${isDark ? "bg-[#7FB069]/10" : "bg-amber-400/10"}`} />
            <div className={`absolute inset-0 ${isDark ? "opacity-[0.045]" : "opacity-[0.03]"}`} style={{ backgroundImage: isDark ? "linear-gradient(rgba(255,255,255,.45) 1px, transparent 1px),linear-gradient(90deg,rgba(255,255,255,.45) 1px,transparent 1px)" : "linear-gradient(rgba(0,0,0,.35) 1px, transparent 1px),linear-gradient(90deg,rgba(0,0,0,.35) 1px,transparent 1px)", backgroundSize: "72px 72px", maskImage: "linear-gradient(to bottom, black, transparent 88%)" }} />
          </div>
          <div className="mx-auto grid w-full max-w-[1240px] grid-cols-1 items-center gap-16 px-5 sm:px-8 lg:grid-cols-[1.05fr_.95fr] lg:gap-12">
            <div className="max-w-[680px]">
              <motion.div initial={reduceMotion ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }} className={`mb-7 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.2em] ${isDark ? "border-[#7EE7C2]/25 bg-[#7EE7C2]/[0.07] text-[#9DF0D3]" : "border-emerald-600/30 bg-emerald-50 text-emerald-800"}`}><Sparkles className="h-3.5 w-3.5" /> Personal improvement for 600–1500 players</motion.div>
              <motion.h1 initial={reduceMotion ? false : { opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.08, ease }} className={`font-heading text-[clamp(3.2rem,7vw,6.8rem)] font-extrabold leading-[0.88] tracking-[-0.055em] ${isDark ? "text-[#F4EFE4]" : "!text-[#1A201C]"}`}>Your next rating milestone needs a plan built from <span className={isDark ? "text-[#7FB069]" : "text-emerald-700"}>your games.</span></motion.h1>
              <motion.p initial={reduceMotion ? false : { opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.18, ease }} className={`mt-7 max-w-[610px] text-base font-medium leading-7 sm:text-lg sm:leading-8 ${isDark ? "text-white/62" : "!text-[#4A5550]"}`}>ChessGuru discovers what is actually holding you back, teaches the chess you need next, and tracks whether the weakness disappears from your real games.</motion.p>
              <motion.div initial={reduceMotion ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.28, ease }} className="mt-9 flex flex-col gap-3 sm:flex-row">
                <PrimaryButton onClick={() => startPlan("hero")} testId="hero-cta-button" className="sm:px-7">Build my improvement plan</PrimaryButton>
                <button type="button" onClick={() => scrollToId("personal-plan")} data-testid="learn-more-button" className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-full border px-6 py-3.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 ${isDark ? "border-white/15 text-white/75 hover:border-white/30 hover:text-white" : "border-stone-300 text-stone-800 hover:border-stone-400 hover:text-stone-900 bg-white shadow-sm"}`}>See a real example <ChevronRight className="h-4 w-4" /></button>
              </motion.div>
              <motion.div initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.48, duration: 0.8 }} className={`mt-8 flex flex-wrap gap-x-6 gap-y-3 text-xs ${isDark ? "text-white/45" : "text-stone-500 font-medium"}`}>
                <span className="flex items-center gap-2"><Check className={`h-3.5 w-3.5 ${isDark ? "text-[#7EE7C2]" : "text-emerald-600 font-bold"}`} /> Chess.com + Lichess</span>
                <span className="flex items-center gap-2"><Check className={`h-3.5 w-3.5 ${isDark ? "text-[#7EE7C2]" : "text-emerald-600 font-bold"}`} /> Free to start</span>
                <span className="flex items-center gap-2"><LockKeyhole className={`h-3.5 w-3.5 ${isDark ? "text-[#7EE7C2]" : "text-emerald-600 font-bold"}`} /> No credit card</span>
              </motion.div>
            </div>
            <motion.div initial={reduceMotion ? false : { opacity: 0, x: 34 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.9, delay: 0.2, ease }} className="pb-6 lg:pb-0"><PlanPreview /></motion.div>
          </div>
        </section>

        <section className={`border-y py-6 transition-colors ${isDark ? "border-white/10 bg-[#0A1B16]" : "border-slate-200/90 bg-slate-100/70"}`}>
          <div className={`mx-auto flex max-w-[1240px] flex-wrap items-center justify-center gap-x-9 gap-y-4 px-5 text-[10px] font-bold uppercase tracking-[0.17em] sm:px-8 ${isDark ? "text-white/40" : "text-slate-500"}`}>
            <span className={isDark ? "text-[#7FB069]" : "text-emerald-700 font-extrabold"}>Not another analysis tool</span><span className={`hidden h-1 w-1 rounded-full sm:block ${isDark ? "bg-white/20" : "bg-slate-300"}`} /><span>One personal focus</span><span className={`hidden h-1 w-1 rounded-full sm:block ${isDark ? "bg-white/20" : "bg-slate-300"}`} /><span>Knowledge selected for you</span><span className={`hidden h-1 w-1 rounded-full sm:block ${isDark ? "bg-white/20" : "bg-slate-300"}`} /><span>Measured in future games</span>
          </div>
        </section>

        <section id="personal-plan" className={`scroll-mt-20 py-24 transition-colors sm:py-32 ${isDark ? "bg-[#0b211a] text-white" : "bg-[#f3ede1] text-slate-900"}`}>
          <div className="mx-auto max-w-[1240px] px-5 sm:px-8">
            <div className="grid items-end gap-8 lg:grid-cols-[.8fr_1.2fr]">
              <Reveal><p className={`text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-[#7EE7C2]" : "text-emerald-800 font-extrabold"}`}>Why generic training fails</p><h2 className={`mt-4 font-heading text-[clamp(2.7rem,5vw,5.4rem)] font-semibold leading-[0.93] tracking-[-0.045em] ${isDark ? "text-white" : "text-slate-900"}`}>One rating does not explain your chess.</h2></Reveal>
              <Reveal delay={0.08}><p className={`max-w-2xl text-base leading-7 sm:text-lg sm:leading-8 ${isDark ? "text-white/65" : "text-slate-700"}`}>Two players can share the same rating and need completely different lessons. ChessGuru listens to what your games are saying, then chooses the next thing that will make the biggest difference to you.</p></Reveal>
            </div>
            <div className="mt-14 grid gap-6 lg:grid-cols-2"><Reveal><SkillProfile /></Reveal><Reveal delay={0.08}><LearningCard /></Reveal></div>
          </div>
        </section>

        <section id="how-it-works" className={`scroll-mt-20 py-24 transition-colors sm:py-32 ${isDark ? "bg-[#071411]" : "bg-[#f8f6f0]"}`}>
          <div className="mx-auto max-w-[1240px] px-5 sm:px-8">
            <Reveal className="max-w-3xl"><p className={`text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-[#7EE7C2]" : "text-emerald-800 font-extrabold"}`}>How your coach works</p><h2 className={`mt-4 font-heading text-[clamp(2.7rem,5vw,5.2rem)] font-semibold leading-[0.94] tracking-[-0.045em] ${isDark ? "text-[#F4EFE4]" : "text-slate-900"}`}>We work on one thing until it feels different in a real game.</h2><p className={`mt-6 max-w-2xl text-base leading-7 sm:text-lg ${isDark ? "text-white/55" : "text-slate-600"}`}>I start with what your games keep showing me. I teach it, watch you try it, and change the plan when you are ready.</p></Reveal>
            <div className="mt-14 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              {PROCESS.map(([number, title, body, Icon, accent], index) => (
                <Reveal key={number} delay={index * 0.06}>
                  <div className={`group relative min-h-[300px] overflow-hidden rounded-[26px] border p-6 transition-all ${isDark ? "border-white/10 bg-white/[0.035] hover:bg-white/[0.06]" : "border-slate-200/80 bg-white hover:border-slate-300 hover:shadow-lg shadow-sm"}`}>
                    <div className="absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-10 blur-2xl group-hover:opacity-20" style={{ background: accent }} />
                    <div className="relative flex items-center justify-between">
                      <span className={`font-mono text-xs ${isDark ? "text-white/30" : "text-slate-400 font-semibold"}`}>{number}</span>
                      <div className={`grid h-11 w-11 place-items-center rounded-2xl border ${isDark ? "border-white/10" : "border-slate-200"}`} style={{ color: accent, background: `${accent}18` }}><Icon className="h-5 w-5" /></div>
                    </div>
                    <h3 className={`relative mt-16 font-heading text-2xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{title}</h3>
                    <p className={`relative mt-3 text-sm leading-6 ${isDark ? "text-white/50" : "text-slate-600"}`}>{body}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="proof" className={`scroll-mt-20 py-24 transition-colors sm:py-32 ${isDark ? "bg-[#11241d] text-white" : "bg-[#e8f1eb] text-slate-900"}`}>
          <div className="mx-auto grid max-w-[1240px] items-center gap-12 px-5 sm:px-8 lg:grid-cols-[.85fr_1.15fr]">
            <Reveal>
              <p className={`text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-[#7EE7C2]" : "text-emerald-800 font-extrabold"}`}>The standard that matters</p>
              <h2 className={`mt-4 font-heading text-[clamp(2.8rem,5vw,5.4rem)] font-semibold leading-[0.93] tracking-[-0.045em] ${isDark ? "text-white" : "text-slate-900"}`}>Did the mistake stop happening?</h2>
              <p className={`mt-6 max-w-lg text-base leading-7 sm:text-lg sm:leading-8 ${isDark ? "text-white/65" : "text-slate-700"}`}>Solving a practice position is encouraging. Using the idea in your next difficult game is what matters. Your coach keeps watching until the better decision begins to feel natural.</p>
              <div className="mt-8 space-y-3">
                {[[ShieldCheck, "I show you the games that taught me this"], [TimerReset, "I check again after you have had time to play"], [RefreshCw, "I change the focus when the new habit holds"]].map(([Icon, text]) => (
                  <div key={text} className={`flex items-center gap-3 text-sm font-medium ${isDark ? "text-white/85" : "text-slate-800"}`}>
                    <div className={`grid h-9 w-9 place-items-center rounded-xl shadow-sm ${isDark ? "bg-white/10" : "bg-white text-emerald-700"}`}><Icon className="h-4 w-4" /></div>{text}
                  </div>
                ))}
              </div>
            </Reveal>
            <Reveal delay={0.08}><ProofCard /></Reveal>
          </div>
        </section>

        <section className={`py-24 transition-colors sm:py-32 ${isDark ? "bg-[#071411] text-white" : "bg-[#f8f6f0] text-slate-900"}`}>
          <div className="mx-auto max-w-[1240px] px-5 sm:px-8">
            <Reveal className="mx-auto max-w-3xl text-center"><p className={`text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-[#7EE7C2]" : "text-rose-700 font-extrabold"}`}>A complete chess curriculum</p><h2 className={`mt-4 font-heading text-[clamp(2.7rem,5vw,5rem)] font-semibold leading-[0.95] tracking-[-0.045em] ${isDark ? "text-white" : "text-slate-900"}`}>ChessGuru can teach the whole game. Your games tell your coach what comes next.</h2></Reveal>
            <div className="mt-14 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {CURRICULUM.map(([title, Icon, body], index) => (
                <Reveal key={title} delay={index * 0.04}>
                  <div className={`h-full rounded-[24px] border p-5 transition-all hover:-translate-y-1 ${isDark ? "border-white/10 bg-white/[0.035] hover:bg-white/[0.06]" : "border-slate-200/90 bg-white hover:border-slate-300 hover:shadow-lg shadow-sm"}`}>
                    <div className={`grid h-11 w-11 place-items-center rounded-2xl ${isDark ? "bg-white/10 text-[#7FB069]" : "bg-emerald-50 text-emerald-700 border border-emerald-200"}`}><Icon className="h-5 w-5" /></div>
                    <h3 className={`mt-5 font-heading text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{title}</h3>
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-white/50" : "text-slate-600"}`}>{body}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className={`relative overflow-hidden py-24 transition-colors sm:py-32 ${isDark ? "bg-[#0B1F19]" : "bg-[#eaf3ed]"}`}>
          <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(127,176,105,.12),transparent_45%)]" />
          <div className="relative mx-auto max-w-[1060px] px-5 sm:px-8">
            <Reveal className={`grid items-center gap-10 rounded-[34px] border p-7 backdrop-blur sm:p-10 lg:grid-cols-[1fr_.72fr] lg:p-12 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-white/80 shadow-xl"}`}>
              <div>
                <p className={`text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-[#7EE7C2]" : "text-emerald-800 font-extrabold"}`}>Free to start</p>
                <h2 className={`mt-4 font-heading text-4xl font-semibold leading-[0.98] tracking-[-0.035em] sm:text-5xl ${isDark ? "text-white" : "text-slate-900"}`}>Meet the coach before you pay for the program.</h2>
                <p className={`mt-5 max-w-xl text-sm leading-7 sm:text-base ${isDark ? "text-white/55" : "text-slate-600"}`}>Import games, receive your first diagnosis, and experience personal training on the Free plan. Pro opens ongoing coaching only after the complete lifecycle is verified.</p>
              </div>
              <div className={`rounded-[24px] p-6 shadow-sm border ${isDark ? "bg-[#F4EFE4] text-[#071411] border-transparent" : "bg-white text-slate-900 border-slate-200"}`}>
                <div className="flex items-baseline justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.15em] text-[#537066]">Free</p><p className="mt-2 font-heading text-4xl font-semibold">₹0</p></div><Gamepad2 className="h-7 w-7 text-[#28745D]" /></div>
                <ul className="mt-5 space-y-2.5 text-sm text-[#365047]">{["Import Chess.com and Lichess games", "Receive your coaching focus", "Start personal pattern training"].map((text) => <li key={text} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-[#28745D]" />{text}</li>)}</ul>
                <button type="button" onClick={() => navigate("/pricing")} className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-[#071411] underline decoration-[#7FB069] decoration-2 underline-offset-4">See Free and Pro <ArrowRight className="h-4 w-4" /></button>
              </div>
            </Reveal>
          </div>
        </section>

        <section id="faq" className={`py-24 transition-colors sm:py-32 ${isDark ? "bg-[#0b211a] text-white" : "bg-[#f3ede1] text-slate-900"}`}>
          <div className="mx-auto grid max-w-[1060px] gap-12 px-5 sm:px-8 lg:grid-cols-[.65fr_1fr]">
            <Reveal><p className={`text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-[#7EE7C2]" : "text-emerald-800 font-extrabold"}`}>Questions before you begin</p><h2 className={`mt-4 font-heading text-4xl font-semibold leading-none tracking-[-0.035em] sm:text-5xl ${isDark ? "text-white" : "text-slate-900"}`}>Straight answers. No engine fog.</h2></Reveal>
            <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-slate-300/80 border-slate-300/80"}`}>
              {FAQS.map(([question, answer], index) => {
                const isOpen = openFaq === index;
                return <Reveal key={question} delay={index * 0.03}><div><button type="button" aria-expanded={isOpen} onClick={() => setOpenFaq(isOpen ? -1 : index)} className="flex w-full items-center justify-between gap-6 py-5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[#28745D]"><span className={`font-heading text-lg font-semibold sm:text-xl ${isDark ? "text-white" : "text-slate-900"}`}>{question}</span><motion.span animate={{ rotate: isOpen ? 180 : 0 }}><ChevronDown className={`h-5 w-5 shrink-0 ${isDark ? "text-white/60" : "text-slate-600"}`} /></motion.span></button><AnimatePresence initial={false}>{isOpen && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: reduceMotion ? 0 : 0.28 }} className="overflow-hidden"><p className={`max-w-2xl pb-6 text-sm leading-7 sm:text-base ${isDark ? "text-white/65" : "text-slate-600"}`}>{answer}</p></motion.div>}</AnimatePresence></div></Reveal>;
              })}
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden bg-[#7FB069] py-24 text-[#071411] sm:py-32">
          <motion.div aria-hidden="true" animate={reduceMotion ? undefined : { x: [0, 24, 0], rotate: [0, 5, 0] }} transition={{ duration: 9, repeat: Infinity }} className="absolute -right-24 -top-32 h-[400px] w-[400px] rounded-full border-[60px] border-[#071411]/[0.06]" />
          <div className="relative mx-auto max-w-[900px] px-5 text-center sm:px-8">
            <Reveal><p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#35510B]">Your games already contain the answer</p><h2 className="mt-5 font-heading text-[clamp(3rem,7vw,6rem)] font-semibold leading-[0.9] tracking-[-0.05em]">Stop guessing what to study next.</h2><p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-[#29420B]/80 sm:text-lg">Connect your games. Choose your goal. Let ChessGuru build the plan—and keep measuring until your chess changes.</p><button type="button" onClick={() => startPlan("final_cta")} className="group mt-9 inline-flex min-h-14 items-center justify-center gap-2 rounded-full bg-[#071411] px-8 py-4 text-sm font-bold text-white shadow-[0_20px_50px_rgba(7,20,17,0.25)] transition-transform hover:-translate-y-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#071411] focus-visible:ring-offset-4 focus-visible:ring-offset-[#7FB069]">Build my improvement plan <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></button><p className="mt-5 text-xs text-[#35510B]/70">Free to start · No credit card · Your plan changes as your chess changes</p></Reveal>
          </div>
        </section>
      </main>
      <footer className={`border-t py-9 transition-colors ${isDark ? "border-white/10 bg-[#071411] text-white/40" : "border-slate-200 bg-white text-slate-500"}`}>
        <div className="mx-auto flex max-w-[1240px] flex-col items-center justify-between gap-6 px-5 text-xs sm:px-8 md:flex-row">
          <div className="flex items-center gap-2.5"><img src="/chessguru-logo.svg" alt="" className="h-7 w-7" /><span className={`font-heading text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>ChessGuru</span><span>Built for players stuck on a plateau.</span></div>
          <nav aria-label="Footer navigation" className="flex flex-wrap justify-center gap-x-5 gap-y-2"><a href="/pricing" className={isDark ? "hover:text-white" : "hover:text-slate-900"}>Pricing</a><a href="/terms" className={isDark ? "hover:text-white" : "hover:text-slate-900"}>Terms</a><a href="/privacy" className={isDark ? "hover:text-white" : "hover:text-slate-900"}>Privacy</a><a href="/refund" className={isDark ? "hover:text-white" : "hover:text-slate-900"}>Refunds</a><a href="/contact" className={isDark ? "hover:text-white" : "hover:text-slate-900"}>Contact</a></nav>
        </div>
      </footer>
    </div>
  );
}
