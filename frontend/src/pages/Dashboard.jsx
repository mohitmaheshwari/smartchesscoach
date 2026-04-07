/**
 * LAB — "The Diagnosis"
 *
 * No lock. No gates. Just the truth.
 *
 * 1. Root problem headline
 * 2. Explanation
 * 3. Sub-causes breakdown (why this keeps happening)
 * 4. Rule
 * 5. Training suggestion (not forced)
 * 6. Games to review (grouped by problem, sequential)
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import {
  Import, ChevronRight, Check, Target, Zap, Eye
} from "lucide-react";

const HEADLINES = {
  tactical_miss:      "You are missing tactics right in front of you.",
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
  king_safety:        "You are leaving your king exposed.",
  conversion:         "You get the advantage. Then you give it back.",
};

const EXPLANATIONS = {
  tactical_miss:      "You choose your move without scanning for captures, checks, and threats.\n\nThe winning move is right there on the board.\nYou just don't look for it.",
  one_move_blunder:   "You move a piece without asking one question:\nis it safe where it's going?\n\nOne careless move. That's all it takes.",
  calculation_error:  "You choose your move, but you don't stay to see what changes after it.\n\nYou stop your thinking too early.\nThat's why your position slips.",
  positional:         "You develop pieces without thinking about what they're doing.\n\nYour opponent has a plan. You're reacting.",
  endgame_collapse:   "You reach an endgame you should win.\nBut you don't know the technique.\n\nSo you shuffle pieces and the advantage fades.",
  opening_disaster:   "You deviate from sound play before move 10.\n\nBy the time the real game starts, you're already in trouble.",
  time_collapse:      "You spend time on positions that are obvious.\nThen you have no time left when it matters.",
  threw_winning:      "You see you're winning and you relax.\nYou stop checking what your opponent is doing.\n\nOne moment of inattention costs everything.",
  piece_safety:       "You move without asking: is anything I own under attack?\n\nThat one question would save you games.",
  ignore_threat:      "You play your move.\nYou don't check what your opponent just did.\n\nTheir threat is right there. You're not seeing it.",
  calculation_depth:  "You choose your move, but you don't stay to see what changes after it.\n\nYou stop your thinking too early.\nThat's why your position slips.",
  missed_tactic:      "The tactic is there. A fork. A pin. A winning capture.\n\nYou don't look for it.",
  king_safety:        "You start attacking before your king is safe.\n\nYour opponent turns the attack around.",
  conversion:         "When you're ahead, you try to win brilliantly.\nInstead of simply.\n\nThat's where the advantage slips away.",
};

const RULES = {
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

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/lab-coach-pick`, { credentials: "include" });
      if (res.ok) setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  if (loading) {
    return <Layout user={user}><div className="flex items-center justify-center h-[60vh]"><div className="w-6 h-6 border-2 border-primary/30 border-t-primary rounded-full animate-spin" /></div></Layout>;
  }

  const coaching = data?.coaching;
  const games = data?.games || [];

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

  const pg = coaching?.priority_game;
  const problemGames = coaching?.problem_games || [];
  const subCauses = coaching?.sub_causes || [];
  const totalProblem = coaching?.total_problem_games || 0;
  const reviewedProblem = coaching?.reviewed_problem_games || 0;
  const topProblem = coaching?.top_problems?.[0];

  const mistakeKey = topProblem?.category || coaching?.root_problem?.pattern || "calculation_depth";
  const headline = HEADLINES[mistakeKey] || HEADLINES.calculation_depth;
  const explanation = EXPLANATIONS[mistakeKey] || EXPLANATIONS.calculation_depth;
  const ruleData = RULES[mistakeKey] || RULES.calculation_depth;

  const unreviewedGames = problemGames.filter(g => !g.reviewed);
  const reviewedGames = problemGames.filter(g => g.reviewed);

  return (
    <Layout user={user}>
      <div className="max-w-md mx-auto px-6 py-10" data-testid="lab-page">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>

          {/* 1. HEADLINE */}
          <h1 className="text-2xl sm:text-[28px] font-heading text-foreground tracking-tight leading-[1.2] mb-6">
            {headline}
          </h1>

          {/* 2. EXPLANATION */}
          <p className="text-[15px] text-foreground/70 leading-[1.8] whitespace-pre-line mb-8">
            {explanation}
          </p>

          {/* 3. SUB-CAUSES — why this keeps happening */}
          {subCauses.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5 mb-6">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Why this keeps happening
                </p>
                <p className="text-xs text-muted-foreground/50">
                  {totalProblem} game{totalProblem !== 1 ? "s" : ""}
                </p>
              </div>
              <div className="space-y-2.5">
                {subCauses.map((sc, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-2 h-2 rounded-full ${i === 0 ? "bg-red-400" : i === 1 ? "bg-amber-400" : "bg-muted-foreground/30"}`} />
                      <p className="text-sm text-foreground">{sc.cause}</p>
                    </div>
                    <p className="text-xs font-mono text-muted-foreground">{sc.count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4. RULE */}
          <div className="rounded-xl bg-amber-500/[0.05] border border-amber-500/15 p-5 mb-6">
            <p className="text-base font-heading font-semibold text-foreground mb-1.5">
              {ruleData.title}
            </p>
            <p className="text-[15px] text-foreground/80 leading-relaxed">
              {ruleData.rule}
            </p>
          </div>

          {/* 5. TRAINING SUGGESTION (not forced) */}
          <div className="rounded-xl border border-border bg-card p-4 mb-8 flex items-center justify-between">
            <div>
              <p className="text-sm text-foreground font-medium">Practice this pattern</p>
              <p className="text-xs text-muted-foreground">3 min · puzzles from your games</p>
            </div>
            <motion.button
              onClick={() => {
                // Train the dominant sub-cause pattern (move-level), not the game-level category
                const pattern = coaching?.root_problem?.pattern || "";
                navigate(pattern ? `/training?focus=${pattern}` : "/training");
              }}
              className="px-4 py-2 text-sm font-semibold rounded-lg gradient-gold text-black hover:opacity-90 transition-all flex items-center gap-1.5"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <Target className="w-3.5 h-3.5" strokeWidth={2} />
              Train
            </motion.button>
          </div>

          {/* 6. GAMES TO REVIEW */}
          {/* Current game — with board preview */}
          {pg && !pg.reviewed && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  {reviewedProblem > 0 ? `Game ${reviewedProblem + 1} of ${totalProblem}` : "Start with this one"}
                </p>
                {totalProblem > 1 && (
                  <p className="text-xs text-muted-foreground/50">
                    {reviewedProblem} of {totalProblem} reviewed
                  </p>
                )}
              </div>

              <div className="rounded-xl border border-border bg-card overflow-hidden">
                {pg.replay?.mistake_fen && (
                  <div className="relative">
                    <div className="aspect-square max-h-[240px]">
                      <LichessBoard
                        fen={pg.replay.setup_fen || pg.replay.mistake_fen}
                        orientation={pg.user_color || "white"}
                        viewOnly={true}
                      />
                    </div>
                    <div className="absolute top-2 left-2 bg-black/60 text-white text-[10px] font-medium px-2.5 py-1 rounded backdrop-blur-sm">
                      Before your mistake
                    </div>
                  </div>
                )}
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-foreground">vs {pg.opponent}</span>
                    {pg.opening && <span className="text-xs text-muted-foreground/50">{pg.opening}</span>}
                  </div>
                  <p className="text-xs text-muted-foreground mb-1">{pg.sub_cause}</p>
                  <p className="text-sm text-foreground/70 leading-[1.7] mb-4">
                    You were in control. Then it slipped.
                  </p>
                  <motion.button
                    onClick={() => navigate(`/replay/${pg.game_id}`)}
                    className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors group"
                    whileHover={{ x: 3 }}
                  >
                    <Eye className="w-3.5 h-3.5" strokeWidth={2} />
                    Show me what I missed
                    <ChevronRight className="w-3.5 h-3.5 opacity-40 group-hover:opacity-80 transition-opacity" />
                  </motion.button>
                </div>
              </div>
            </div>
          )}

          {/* Remaining unreviewed games */}
          {unreviewedGames.length > 1 && (
            <div className="mb-6">
              <p className="text-[10px] tracking-[0.15em] uppercase mb-2 font-bold text-muted-foreground/50">
                More games with this problem
              </p>
              <div className="space-y-1.5">
                {unreviewedGames.filter(g => g.game_id !== pg?.game_id).map((g) => (
                  <motion.div key={g.game_id}
                    className="flex items-center gap-3 px-3 py-2.5 bg-card border border-border rounded-lg cursor-pointer hover:border-primary/20 transition-all"
                    onClick={() => navigate(`/replay/${g.game_id}`)}
                    whileHover={{ x: 2 }}>
                    <div className="w-2 h-2 rounded-full bg-red-400" />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-foreground">vs {g.opponent}</span>
                    </div>
                    <span className="text-xs text-muted-foreground/50">{g.sub_cause}</span>
                    <ChevronRight className="w-3 h-3 text-muted-foreground/20" />
                  </motion.div>
                ))}
              </div>
            </div>
          )}

          {/* Reviewed games */}
          {reviewedGames.length > 0 && (
            <div className="mb-6">
              <p className="text-[10px] tracking-[0.15em] uppercase mb-2 font-bold text-muted-foreground/30">
                <Check className="w-3 h-3 inline mr-1" strokeWidth={2} />
                Reviewed ({reviewedGames.length})
              </p>
              <div className="space-y-1">
                {reviewedGames.map((g) => (
                  <div key={g.game_id}
                    className="flex items-center gap-3 px-3 py-2 bg-card border border-border rounded-lg opacity-40 cursor-pointer hover:opacity-60 transition-all"
                    onClick={() => navigate(`/game/${g.game_id}`)}>
                    <Check className="w-3 h-3 text-emerald-500/50" strokeWidth={2} />
                    <span className="text-sm text-foreground">vs {g.opponent}</span>
                    <span className="text-xs text-muted-foreground/40 ml-auto">{g.sub_cause}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* All reviewed celebration */}
          {unreviewedGames.length === 0 && totalProblem > 0 && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-5 mb-6 text-center">
              <Check className="w-6 h-6 text-emerald-500 mx-auto mb-2" strokeWidth={2} />
              <p className="text-sm text-emerald-500 font-medium">
                You've reviewed all {totalProblem} games.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Now apply the rule in your next game.
              </p>
              <button onClick={() => navigate("/play-with-coach")}
                className="mt-4 px-5 py-2.5 text-sm font-semibold rounded-lg gradient-gold text-black hover:opacity-90 transition-all inline-flex items-center gap-2">
                Play with Coach <ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            </div>
          )}

          {/* Import more */}
          <div className="text-center pt-2">
            <button onClick={() => navigate("/import")} className="text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors">
              Import more games
            </button>
          </div>

        </motion.div>
      </div>
    </Layout>
  );
};

export default Dashboard;
