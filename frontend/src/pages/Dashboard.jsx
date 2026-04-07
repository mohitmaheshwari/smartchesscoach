/**
 * LAB — "Where you finally understand what you're doing wrong."
 *
 * LOCKED: tension → curiosity → force training
 * UNLOCKED: clarity → rule → example → "aha moment"
 *
 * NOT a dashboard. NOT analysis. A coaching revelation.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, Target, Lock, Eye, Import } from "lucide-react";

// Technical key → headline (pain, specific)
const HEADLINES = {
  tactical_miss:      "You are missing tactics that are right in front of you.",
  one_move_blunder:   "You are giving away pieces for free.",
  calculation_error:  "You are losing games because you stop thinking too early.",
  positional:         "You are being outplayed. Your pieces have no plan.",
  endgame_collapse:   "You reach endgames you should win. You don't finish them.",
  opening_disaster:   "Your games are lost before they start.",
  time_collapse:      "You are losing on the clock, not on the board.",
  threw_winning:      "You are losing games from winning positions.",
  piece_safety:       "You are giving away pieces for free.",
  ignore_threat:      "You are not looking at what your opponent is doing.",
  calculation_depth:  "You are losing games because you stop thinking too early.",
  missed_tactic:      "You are missing simple winning chances.",
  king_safety:        "You are leaving your king exposed and getting punished.",
  conversion:         "You get the advantage. Then you give it back.",
};

// Technical key → human behavior (locked teaser)
const BEHAVIOR_TEASERS = {
  tactical_miss:      "You don't scan the board before you move.\nThat's why winning chances slip past you.",
  one_move_blunder:   "You move without checking if your piece is safe.\nThat's why material disappears.",
  calculation_error:  "You stop checking your opponent once you decide your move.\nThat's why good positions collapse.",
  positional:         "You move pieces without a plan.\nThat's why you get outplayed slowly.",
  endgame_collapse:   "You reach winning endgames but can't finish them.\nThat's why wins become draws.",
  opening_disaster:   "You make unsound moves early.\nThat's why you start every game on the back foot.",
  time_collapse:      "You spend time on easy moves, then panic on hard ones.\nThat's why the clock beats you.",
  threw_winning:      "You stop paying attention once you're ahead.\nThat's why good positions collapse.",
  piece_safety:       "You don't check if your pieces are protected.\nThat's why you keep losing material.",
  ignore_threat:      "You don't look at what your opponent just did.\nThat's why you miss threats.",
  calculation_depth:  "You stop checking your opponent once you decide your move.\nThat's why good positions collapse.",
  missed_tactic:      "You don't scan for captures, checks, and threats.\nThat's why you miss winning chances.",
  king_safety:        "You attack before your king is safe.\nThat's why your attacks backfire.",
  conversion:         "You get creative when you should simplify.\nThat's why advantages disappear.",
};

// Technical key → unlocked explanation (the "aha")
const BEHAVIOR_EXPLANATIONS = {
  tactical_miss:      "You choose your move without scanning for captures, checks, and threats.\n\nThe winning move is right there on the board.\nYou just don't look for it.",
  one_move_blunder:   "You move a piece without asking one question:\nis it safe where it's going?\n\nOne careless move. That's all it takes to lose a game.",
  calculation_error:  "You choose your move, but you don't stay to see what changes after it.\n\nYou stop your thinking too early.\nThat's why your position slips.",
  positional:         "You develop pieces without thinking about what they're doing.\n\nYour opponent has a plan. You're reacting.\nThat's why you get outmaneuvered.",
  endgame_collapse:   "You reach an endgame you should win.\nBut you don't know the technique.\n\nSo you shuffle pieces and the advantage fades.",
  opening_disaster:   "You deviate from sound play before move 10.\n\nBy the time the real game starts, you're already in trouble.",
  time_collapse:      "You spend time on positions that are obvious.\nThen you have no time left when it matters.\n\nThe clock beats you, not your opponent.",
  threw_winning:      "You see you're winning and you relax.\nYou stop checking what your opponent is doing.\n\nOne moment of inattention costs everything.",
  piece_safety:       "You move without asking: is anything I own under attack?\n\nThat one question would save you games.\nYou're not asking it.",
  ignore_threat:      "You play your move.\nYou don't check what your opponent just did.\n\nTheir threat is right there. You're not seeing it.",
  calculation_depth:  "You choose your move, but you don't stay to see what changes after it.\n\nYou stop your thinking too early.\nThat's why your position slips.",
  missed_tactic:      "The tactic is there. A fork. A pin. A winning capture.\n\nYou don't look for it.\nYou play a safe move instead.",
  king_safety:        "You start attacking before your king is safe.\n\nYour opponent turns the attack around.\nYou never recover.",
  conversion:         "When you're ahead, you try to win brilliantly.\nInstead of simply.\n\nThat's where the advantage slips away.",
};

// Technical key → the rule (coaching card)
const BEHAVIOR_RULES = {
  tactical_miss:      { title: "Scan before you move", rule: "Before every move — check captures, checks, and threats." },
  one_move_blunder:   { title: "Safety check", rule: "Before every move — is anything I own under attack?" },
  calculation_error:  { title: "Stay for their turn", rule: "Before you move — check their best reply." },
  positional:         { title: "Find your worst piece", rule: "Before every move — which piece is doing the least?" },
  endgame_collapse:   { title: "Activate the king", rule: "In endgames — your king is a fighting piece. Use it." },
  opening_disaster:   { title: "Sound development", rule: "First 10 moves — develop, control center, castle." },
  time_collapse:      { title: "Spend time wisely", rule: "Under 2 minutes — play the simplest move." },
  threw_winning:      { title: "Stay alert when winning", rule: "When ahead — keep checking your opponent. Don't relax." },
  piece_safety:       { title: "Safety check", rule: "Before every move — is anything I own under attack?" },
  ignore_threat:      { title: "Read your opponent", rule: "Before every move — what is my opponent attacking?" },
  calculation_depth:  { title: "Stay for their turn", rule: "Before you move — check their best reply." },
  missed_tactic:      { title: "Scan before you move", rule: "Before every move — is there a tactic here?" },
  king_safety:        { title: "King first", rule: "Before you attack — is my king safe?" },
  conversion:         { title: "Simplify when ahead", rule: "When ahead — trade pieces, not pawns. Keep it simple." },
};

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
        if (res.ok) setData(await res.json());
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const coaching = data?.coaching;
  const games = data?.games || [];

  // ── Empty ──
  if (games.length === 0) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-20 text-center" data-testid="lab-page">
          <div className="w-16 h-16 rounded-2xl bg-muted/50 border border-border flex items-center justify-center mx-auto mb-6">
            <Import className="w-7 h-7 text-muted-foreground/40" strokeWidth={1.5} />
          </div>
          <h2 className="text-xl font-heading font-semibold text-foreground mb-2">No games yet</h2>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto mb-8">Import your games. Your coach will tell you what's wrong.</p>
          <button onClick={() => navigate("/import")} className="px-6 py-3 text-sm font-semibold rounded-lg gradient-gold text-black shadow-lg shadow-amber-500/20 hover:opacity-90 transition-all" data-testid="lab-empty-import-btn">
            Import your games
          </button>
        </div>
      </Layout>
    );
  }

  const lock = coaching?.training_lock;
  const isUnlocked = lock?.unlocked;
  const root = coaching?.root_problem;
  const topProblem = coaching?.top_problems?.[0];
  const pg = coaching?.priority_game;

  const mistakeKey = topProblem?.category || root?.pattern || "calculation_depth";
  const headline = HEADLINES[mistakeKey] || HEADLINES.calculation_depth;
  const teaser = BEHAVIOR_TEASERS[mistakeKey] || BEHAVIOR_TEASERS.calculation_depth;
  const explanation = BEHAVIOR_EXPLANATIONS[mistakeKey] || BEHAVIOR_EXPLANATIONS.calculation_depth;
  const ruleData = BEHAVIOR_RULES[mistakeKey] || BEHAVIOR_RULES.calculation_depth;

  // ═══════════════════════════════════════════
  // LOCKED STATE
  // ═══════════════════════════════════════════
  if (!isUnlocked) {
    return (
      <Layout user={user}>
        <div className="max-w-md mx-auto px-6 py-10" data-testid="lab-page">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>

            {/* Headline — specific, emotional */}
            <h1 className="text-2xl sm:text-[28px] font-heading text-foreground tracking-tight leading-[1.2] mb-6">
              {headline}
            </h1>

            {/* Behavior pattern */}
            <p className="text-[15px] text-muted-foreground leading-[1.7] whitespace-pre-line mb-6">
              {teaser}
            </p>

            {/* Repetition signal — direct */}
            <p className="text-sm text-foreground/50 mb-8">
              You did this again and again in your recent games.
            </p>

            {/* Lock block */}
            <div className="rounded-xl border border-border bg-card p-6 mb-8">
              <div className="flex items-center gap-2.5 mb-4">
                <Lock className="w-4.5 h-4.5 text-muted-foreground" strokeWidth={2} />
                <p className="text-sm font-semibold text-foreground">Unlock your lesson</p>
              </div>

              <p className="text-sm text-muted-foreground mb-4">
                Complete 3 quick training exercises to see:
              </p>

              <div className="space-y-2 mb-6">
                {[
                  "What exactly goes wrong",
                  "The rule you're breaking",
                  "One example from your own games",
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-500/50" />
                    <p className="text-sm text-foreground/70">{item}</p>
                  </div>
                ))}
              </div>

              <button
                onClick={() => navigate(root?.pattern ? `/training?focus=${root.pattern}` : "/training")}
                className="w-full py-3.5 text-[15px] font-semibold rounded-xl gradient-gold text-black hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
              >
                <Target className="w-4 h-4" strokeWidth={2} />
                Start training (3 min)
                <ChevronRight className="w-4 h-4 opacity-60" />
              </button>
            </div>

          </motion.div>
        </div>
      </Layout>
    );
  }

  // ═══════════════════════════════════════════
  // UNLOCKED STATE
  // ═══════════════════════════════════════════
  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-10" data-testid="lab-page">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>

          {/* Reward line — natural, not caps */}
          <p className="text-sm text-emerald-500 font-medium mb-6">
            Now you can see it clearly.
          </p>

          {/* Explanation — continuous flow, no section headers */}
          <p className="text-[15px] text-foreground leading-[1.8] whitespace-pre-line mb-8">
            {explanation}
          </p>

          {/* Rule — separated, feels like a coaching card */}
          <div className="rounded-xl bg-amber-500/[0.05] border border-amber-500/15 p-5 mb-8">
            <p className="text-base font-heading font-semibold text-foreground mb-1.5">
              {ruleData.title}
            </p>
            <p className="text-[15px] text-foreground/80 leading-relaxed">
              {ruleData.rule}
            </p>
          </div>

          {/* Personal example — natural intro, no caps label */}
          {pg && (
            <div className="mb-8">
              <p className="text-sm text-muted-foreground/60 mb-3">This is from your game:</p>
              <div className="rounded-xl border border-border bg-card p-5">
                <p className="text-sm text-foreground/80 leading-[1.8] mb-4">
                  {pg.description || "You were in control of the position.\n\nThen it became uncomfortable.\n\nYou moved too quickly.\n\nThat's where it slipped."}
                </p>
                <button
                  onClick={() => navigate(`/replay/${pg.game_id}`)}
                  className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" strokeWidth={2} />
                  Review this position
                  <ChevronRight className="w-3.5 h-3.5 opacity-60" />
                </button>
              </div>
            </div>
          )}

        </motion.div>
      </div>
    </Layout>
  );
};

export default Dashboard;
