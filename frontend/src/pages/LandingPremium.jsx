import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Chessboard } from "react-chessboard";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Brain, Check, ChevronDown, Code, Eye, RotateCcw, ShieldCheck, Sparkles, Target } from "lucide-react";
import { API } from "@/App";

const DEMO_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4";
const MATE_FEN = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4";
const BOARD = { light: { backgroundColor: "#eadfc9" }, dark: { backgroundColor: "#75644d" } };
const FAQ = [
  ["Who is ChessGuru built for?", "Players rated 600–1500 who understand some chess but keep repeating the same costly habits."],
  ["How is this different from Chess.com or Lichess analysis?", "Those tools are excellent at showing which move changed the evaluation. ChessGuru connects mistakes across games, explains the recurring habit, and turns your own positions into focused practice."],
  ["Does it work with my existing account?", "Yes. Connect Chess.com or Lichess and keep playing where you already play."],
  ["Does AI decide what is true on the board?", "No. Board state and engine analysis establish the chess facts. AI helps express verified facts in useful coaching language."],
  ["Will solving a few puzzles be called improvement?", "No. Practice completion is not proof. ChessGuru treats later games as separate evidence and describes only what that evidence supports."],
];

const Reveal = ({ children, delay = 0, className = "" }) => {
  const reduced = useReducedMotion();
  return <motion.div className={className} initial={reduced ? false : { opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }} transition={{ duration: .55, delay, ease: [0.22, 1, 0.36, 1] }}>{children}</motion.div>;
};

const PrimaryButton = ({ children, onClick, testid, dark = false }) => (
  <button type="button" onClick={onClick} data-testid={testid} className={`group inline-flex min-h-12 items-center justify-center gap-2 rounded-full px-7 py-3 text-sm font-bold transition-all hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${dark ? "bg-[#f1c36f] text-[#191811] hover:bg-[#ffda91] focus-visible:ring-white" : "bg-[#a96510] text-white shadow-[0_14px_36px_rgba(119,71,5,.22)] hover:bg-[#8d540b] focus-visible:ring-[#82500d]"}`}>
    {children}<ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1"/>
  </button>
);

function InteractiveCoachDemo() {
  const [solved, setSolved] = useState(false);
  const [message, setMessage] = useState("Drag the white queen to the finishing square.");
  const mark = solved ? { f7: { background: "rgba(44,142,106,.62)" }, e8: { boxShadow: "inset 0 0 0 4px rgba(184,58,47,.8)" } } : { f7: { background: "rgba(210,154,66,.5)" } };
  const drop = (from, to) => {
    if (from === "h5" && to === "f7") { setSolved(true); setMessage("Checkmate. The queen is protected by the bishop on c4."); return true; }
    setMessage("Look at f7: only the king protects it.");
    return false;
  };
  const reset = () => { setSolved(false); setMessage("Drag the white queen to the finishing square."); };
  return <div className="relative mx-auto max-w-[650px]">
    <div className="absolute -inset-4 translate-x-4 translate-y-4 border border-[#8e6428]/25" aria-hidden="true"/>
    <div className="relative overflow-hidden border border-black/10 bg-[#fffaf0] shadow-[0_32px_80px_rgba(48,38,21,.24)]">
      <div className="flex items-center justify-between border-b border-black/10 px-4 py-3">
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#2c8e6a]"/><span className="text-xs font-bold">Live coaching example</span></div>
        <span className="font-mono text-[10px] uppercase tracking-widest text-[#777064]">White to move</span>
      </div>
      <div className="grid md:grid-cols-[1fr_190px]">
        <div className="min-w-0">
          <Chessboard position={solved ? MATE_FEN : DEMO_FEN} onPieceDrop={drop} arePiecesDraggable={!solved} customLightSquareStyle={BOARD.light} customDarkSquareStyle={BOARD.dark} customSquareStyles={mark} customBoardStyle={{ borderRadius: 0 }}/>
        </div>
        <div className="flex flex-col justify-between border-l border-black/10 bg-[#f7f0e3] p-4">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-[.16em] text-[#986618]">{solved ? "Why it works" : "Your turn"}</span>
            <p className="mt-3 text-sm font-semibold leading-6">{message}</p>
            {solved && <div className="mt-4 border-l-2 border-[#2c8e6a] pl-3 text-xs leading-5 text-[#625d52]">Before defending a threat, check whether you have a forcing move: check, capture, or mate.</div>}
          </div>
          <button type="button" onClick={reset} className="mt-5 flex items-center gap-1.5 text-xs font-semibold text-[#766034]"><RotateCcw className="h-3.5 w-3.5"/>Reset position</button>
        </div>
      </div>
      <div className="flex items-center gap-4 border-t border-black/10 px-4 py-3 text-[10px] uppercase tracking-widest text-[#817a6e]"><span>Example position</span><span>·</span><span>Board verified</span><span className="ml-auto text-[#2c765e]">{solved ? "Solved" : "Try Qxf7"}</span></div>
    </div>
  </div>;
}

const ProductStory = () => (
  <section id="how" className="bg-[#171a17] py-24 text-[#f5efe4] sm:py-32">
    <div className="mx-auto max-w-6xl px-5 sm:px-8">
      <Reveal><p className="text-[11px] font-bold uppercase tracking-[.22em] text-[#d6a452]">The product is the loop</p><h2 className="mt-5 max-w-4xl font-heading text-4xl font-bold leading-[1.02] tracking-[-.045em] sm:text-6xl">Your mistake should not disappear when the review closes.</h2></Reveal>
      <div className="mt-16 grid gap-5 lg:grid-cols-12">
        <Reveal className="lg:col-span-7"><div className="h-full border border-white/10 bg-[#20231f] p-5 sm:p-7"><div className="flex items-center justify-between"><span className="text-xs font-bold text-[#e8dfd0]">Game review · Move 18</span><span className="rounded-full bg-[#a94b40]/15 px-2 py-1 text-[10px] font-bold text-[#e58b81]">PIECE SAFETY</span></div><div className="mt-8 grid gap-7 sm:grid-cols-[170px_1fr]"><div className="aspect-square overflow-hidden"><Chessboard position={DEMO_FEN} arePiecesDraggable={false} customLightSquareStyle={BOARD.light} customDarkSquareStyle={BOARD.dark}/></div><div><p className="font-serif text-2xl italic leading-8 text-white">“You answered the attack, but missed that f7 was already ending the game.”</p><div className="mt-6 space-y-2 text-xs text-[#a7a196]"><p><b className="text-[#d6a452]">What happened:</b> a forcing move came first.</p><p><b className="text-[#d6a452]">Carry forward:</b> scan checks before defending.</p></div></div></div></div></Reveal>
        <Reveal delay={.06} className="lg:col-span-5"><div className="h-full border border-white/10 bg-[#eee3d0] p-6 text-[#1b1a14]"><Brain className="h-6 w-6 text-[#9a6717]"/><p className="mt-8 text-[10px] font-bold uppercase tracking-widest text-[#986618]">Coach memory</p><h3 className="mt-3 font-heading text-3xl font-bold">Checks before defence</h3><p className="mt-3 text-sm leading-6 text-[#635d52]">ChessGuru watches for the same decision in later games instead of treating every review as a blank slate.</p><div className="mt-8 space-y-3">{["Game review","Focused practice","Next-game check"].map((x,i)=><div key={x} className="flex items-center gap-3 border-t border-black/10 pt-3 text-sm"><span className={`h-2.5 w-2.5 rounded-full ${i===2?"bg-[#d29a42]":"bg-[#2c8e6a]"}`}/><span>{x}</span><span className="ml-auto text-xs text-[#81786a]">{i===2?"Waiting":"Ready"}</span></div>)}</div></div></Reveal>
        <Reveal delay={.08} className="lg:col-span-5"><div className="h-full bg-[#8f4e34] p-7 text-[#fff5e9]"><Target className="h-6 w-6"/><h3 className="mt-10 font-heading text-3xl font-bold">Practice the decision, not the label.</h3><p className="mt-4 text-sm leading-6 text-white/75">A short session asks you to find forcing moves in positions connected to your current focus.</p><div className="mt-8 flex gap-2">{["Check","Capture","Threat"].map(x=><span key={x} className="border border-white/25 px-3 py-2 text-xs">{x}</span>)}</div></div></Reveal>
        <Reveal delay={.1} className="lg:col-span-7"><div className="h-full border border-black/10 bg-[#d9ccb6] p-7 text-[#1b1a14]"><p className="text-[10px] font-bold uppercase tracking-widest text-[#79500f]">Honest progress</p><div className="mt-8 grid gap-7 sm:grid-cols-2"><div><span className="text-sm text-[#716a5e]">Practice completed</span><p className="mt-2 font-heading text-4xl font-bold">Useful—not proof.</p></div><div><span className="text-sm text-[#716a5e]">Later games</span><p className="mt-2 font-heading text-4xl font-bold">Evidence over time.</p></div></div><div className="mt-8 h-px bg-black/15"><div className="h-1 w-2/3 -translate-y-1/2 bg-[#2c8e6a]"/></div></div></Reveal>
      </div>
    </div>
  </section>
);

export default function LandingPremium() {
  const navigate = useNavigate();
  const [devMode, setDevMode] = useState(false);
  const [devLoading, setDevLoading] = useState(false);
  const reduced = useReducedMotion();
  useEffect(() => { fetch(`${API}/auth/status`).then(r => r.json()).then(d => setDevMode(d.dev_mode === true)).catch(() => {}); }, []);
  const login = async () => { try { const d = await (await fetch(`${API}/auth/google/login`)).json(); if (d.auth_url) window.location.href = d.auth_url; else alert("Login failed. Please try again."); } catch { alert("Login failed. Please try again."); } };
  const devLogin = async () => { setDevLoading(true); try { const d = await (await fetch(`${API}/auth/dev-login`, { credentials: "include" })).json(); if (d.status === "ok") window.location.href = sessionStorage.getItem("post_auth_redirect") || "/dashboard"; } finally { setDevLoading(false); } };
  const scroll = id => document.getElementById(id)?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  const schema = useMemo(() => JSON.stringify({ "@context": "https://schema.org", "@type": "FAQPage", mainEntity: FAQ.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) }), []);

  return <div className="min-h-screen overflow-hidden bg-[#f5efe4] text-[#1b1a14]">
    <header className="fixed inset-x-0 top-0 z-50 border-b border-black/10 bg-[#f5efe4]/90 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
        <button type="button" onClick={() => window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" })} className="flex items-center gap-2.5 rounded focus-visible:ring-2"><img src="/chessguru-logo.svg" alt="" className="h-7 w-7"/><span className="font-heading text-[17px] font-bold">ChessGuru</span></button>
        <nav className="hidden items-center gap-8 text-sm text-[#645f54] md:flex"><button onClick={() => scroll("how")}>How it works</button><button onClick={() => scroll("human")}>The philosophy</button><button onClick={() => scroll("faq")}>FAQ</button><button onClick={() => navigate("/pricing")}>Pricing</button></nav>
        <div className="flex items-center gap-3">{devMode && <button onClick={devLogin} disabled={devLoading} data-testid="dev-login-button" className="hidden items-center gap-1.5 text-xs sm:flex"><Code className="h-3.5 w-3.5"/>{devLoading ? "..." : "Dev"}</button>}<button onClick={() => navigate("/login")} data-testid="signin-link" className="hidden text-sm font-medium sm:block">Sign in</button><button onClick={login} data-testid="login-button" className="rounded-full bg-[#1b1a14] px-5 py-2.5 text-sm font-bold text-white">Start free</button></div>
      </div>
    </header>

    <main>
      <section className="relative pt-28 sm:pt-36 lg:pt-40">
        <div className="absolute left-[6%] top-16 hidden h-[70%] w-px bg-black/10 lg:block" aria-hidden="true"/>
        <div className="mx-auto grid max-w-7xl gap-14 px-5 pb-24 sm:px-8 lg:grid-cols-[.78fr_1.22fr] lg:items-center lg:gap-20 lg:pb-32">
          <Reveal><p className="text-[11px] font-bold uppercase tracking-[.22em] text-[#986618]">Your games. Your patterns. Your coach.</p><h1 className="mt-6 font-heading text-[3.4rem] font-bold leading-[.92] tracking-[-.055em] sm:text-[4.9rem]">Stop studying everything.<br/><em className="font-serif font-normal text-[#9d5f10]">Fix what keeps beating you.</em></h1><p className="mt-7 max-w-xl text-lg leading-8 text-[#5f5a50]">ChessGuru studies the games you already play, finds the decision you keep getting wrong, and turns it into focused coaching from your own positions.</p><div className="mt-9 flex flex-col gap-3 sm:flex-row"><PrimaryButton onClick={login} testid="hero-cta-button">Connect my games</PrimaryButton><button onClick={() => scroll("how")} data-testid="learn-more-button" className="min-h-12 rounded-full border border-black/20 px-7 text-sm font-bold transition hover:bg-white/50">See the coaching loop</button></div><div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[#736d62]"><span className="flex gap-1.5"><Check className="h-4 w-4 text-[#2c765e]"/>Free to start</span><span className="flex gap-1.5"><Check className="h-4 w-4 text-[#2c765e]"/>Chess.com + Lichess</span><span className="flex gap-1.5"><Check className="h-4 w-4 text-[#2c765e]"/>No engine jargon</span></div></Reveal>
          <Reveal delay={.08}><InteractiveCoachDemo/></Reveal>
        </div>
      </section>

      <section className="border-y border-black/10 bg-[#e8decc]">
        <div className="mx-auto grid max-w-7xl divide-y divide-black/10 px-5 sm:grid-cols-3 sm:divide-x sm:divide-y-0 sm:px-8">
          {[["BOARD TRUTH","Stockfish-grounded positions"],["PERSONAL CONTEXT","Patterns across your games"],["CLEAR NEXT STEP","One instruction to practise"]].map(([a,b]) => <div key={a} className="py-5 text-center"><b className="text-[10px] tracking-[.2em] text-[#8b5c14]">{a}</b><span className="ml-3 text-xs text-[#70695e]">{b}</span></div>)}
        </div>
      </section>

      <ProductStory/>

      <section id="human" className="bg-[#f5efe4] py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <Reveal><div className="relative min-h-[570px] overflow-hidden bg-[#20231f]">
            <img src="/landing/chess-player-study-v1.webp" alt="A chess player studying a position at home with a laptop nearby" className="absolute inset-0 h-full w-full object-cover object-center" loading="lazy"/>
            <div className="absolute inset-0 bg-gradient-to-r from-[#141713]/95 via-[#141713]/55 to-transparent"/>
            <div className="relative z-10 flex min-h-[570px] max-w-xl flex-col justify-center p-7 text-white sm:p-14">
              <p className="text-[11px] font-bold uppercase tracking-[.22em] text-[#e2b96d]">The philosophy</p>
              <h2 className="mt-5 font-heading text-4xl font-bold leading-[1.04] tracking-[-.04em] sm:text-6xl">A coach should make the next game feel different.</h2>
              <p className="mt-6 max-w-md text-base leading-7 text-white/70">Not because it gave you twenty engine lines. Because one useful idea stayed in your head when the same decision appeared again.</p>
            </div>
          </div></Reveal>
        </div>
      </section>

      <section className="bg-[#d9ccb6] py-24 sm:py-32">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <Reveal><div className="text-center"><p className="text-[11px] font-bold uppercase tracking-[.22em] text-[#84560f]">The difference in one move</p><h2 className="mx-auto mt-5 max-w-4xl font-heading text-4xl font-bold tracking-[-.04em] sm:text-6xl">An engine gives a verdict.<br/>ChessGuru gives you a habit.</h2></div></Reveal>
          <div className="mt-14 border-y border-black/15">
            <div className="grid gap-4 border-b border-black/15 py-7 sm:grid-cols-[190px_1fr]"><span className="text-[10px] font-bold uppercase tracking-widest text-[#777064]">Ordinary analysis</span><p className="font-mono text-sm text-[#6f685c]">3...Nf6?? &nbsp; Evaluation: mate in one</p></div>
            <div className="grid gap-4 py-8 sm:grid-cols-[190px_1fr]"><span className="text-[10px] font-bold uppercase tracking-widest text-[#84560f]">ChessGuru</span><p className="font-serif text-2xl italic leading-8">“Before you answer a threat, scan your checks. Qxf7 is mate because your bishop protects the queen.”</p></div>
          </div>
          <div className="mt-10 grid gap-6 sm:grid-cols-3"><Value icon={ShieldCheck} title="Grounded" text="The board establishes what is true."/><Value icon={Eye} title="Memorable" text="The explanation names the square and reason."/><Value icon={Sparkles} title="Personal" text="Later practice comes from your current focus."/></div>
        </div>
      </section>

      <section id="faq" className="bg-[#f5efe4] py-24 sm:py-32">
        <div className="mx-auto grid max-w-6xl gap-12 px-5 sm:px-8 lg:grid-cols-[.7fr_1.3fr]">
          <Reveal><div><p className="text-[11px] font-bold uppercase tracking-[.22em] text-[#986618]">Questions, answered plainly</p><h2 className="mt-5 font-heading text-4xl font-bold tracking-[-.04em]">Before you connect your games.</h2></div></Reveal>
          <div className="border-t border-black/15">{FAQ.map(([q,a]) => <details key={q} className="group border-b border-black/15"><summary className="flex cursor-pointer list-none items-start justify-between gap-5 py-6 font-bold">{q}<ChevronDown className="h-4 w-4 shrink-0 transition-transform group-open:rotate-180"/></summary><p className="max-w-2xl pb-7 pr-9 text-sm leading-7 text-[#625d52]">{a}</p></details>)}</div>
        </div>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: schema }}/>
      </section>

      <section className="bg-[#171a17] py-24 text-center text-white sm:py-32">
        <Reveal><div className="mx-auto max-w-4xl px-5"><p className="text-[11px] font-bold uppercase tracking-[.22em] text-[#e0b568]">Built for players rated 600–1500</p><h2 className="mt-5 font-heading text-5xl font-bold leading-[1.02] tracking-[-.045em] sm:text-7xl">Your next breakthrough is hiding in games you already played.</h2><p className="mx-auto mt-6 max-w-xl text-base leading-7 text-white/60">Connect your account. Let ChessGuru find the first pattern worth working on.</p><div className="mt-9"><PrimaryButton onClick={login} testid="cta-button" dark>Connect my games</PrimaryButton></div><p className="mt-4 text-xs text-white/35">Free to start. No credit card required.</p></div></Reveal>
      </section>
    </main>

    <footer className="border-t border-white/10 bg-[#171a17] py-10 text-[#8f897d]"><div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-5 px-5 sm:px-8 md:flex-row"><span className="flex items-center gap-2 font-bold text-white"><img src="/chessguru-logo.svg" alt="" className="h-5 w-5"/>ChessGuru</span><div className="flex flex-wrap justify-center gap-5 text-xs"><a href="/terms">Terms</a><a href="/privacy">Privacy</a><a href="/refund">Refunds</a><a href="/contact">Contact</a><a href="/pricing">Pricing</a></div><span className="text-xs">For players stuck on a plateau.</span></div></footer>
  </div>;
}

const Value = ({ icon: Icon, title, text }) => <div className="border-t border-black/15 pt-5"><Icon className="h-5 w-5 text-[#8b5c14]"/><h3 className="mt-4 font-bold">{title}</h3><p className="mt-2 text-sm leading-6 text-[#716a5e]">{text}</p></div>;
