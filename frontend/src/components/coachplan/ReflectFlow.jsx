/**
 * The child's reflection on one moment from their own game, answered only by
 * tapping the board. docs/coach_assistant_plan_scope.md, section 2c.
 *
 * Three kinds of moment, one shape:
 *   landing        a piece went where it could be taken (piece safety)
 *   king_attack    his pieces were gathering near the king and the move ignored it
 *   missed_tactic  there was a fork / pin / skewer / mate and the move missed it
 *
 * Steps: what was it for → the check (tap test) → did you see it in the game →
 * what happened → your turn → reflection card and the week's rule.
 *
 * Every option on the board is computed by the server from the board, and every
 * line below is built from those facts. There is no typing and no AI-written
 * text anywhere in this flow. No numbers in what the child reads.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import "./coachplan.css";

const FILES = "abcdefgh";
const GLYPH = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟︎" };
const NAME = { k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" };
const VALUE = { pawn: 1, knight: 3, bishop: 3, rook: 5, queen: 9, king: 100 };
const PATTERN_WORDS = {
  fork: "a fork, one piece attacking two at once",
  pin: "a pin, a piece stuck in front of a bigger one",
  skewer: "a skewer, a big piece forced to move and leave the one behind it",
  mate: "a checkmate",
};

export function parseFen(fen) {
  const pos = {};
  String(fen || "").split(" ")[0].split("/").forEach((row, i) => {
    let f = 0;
    for (const c of row) {
      if (/\d/.test(c)) f += Number(c);
      else { pos[FILES[f] + (8 - i)] = c; f += 1; }
    }
  });
  return pos;
}
const isWhitePiece = (p) => p === p.toUpperCase();
const andList = (a) => (a.length < 2 ? a.join("") : `${a.slice(0, -1).join(", ")} and ${a[a.length - 1]}`);
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const his = (p, sq) => `his ${p} on ${sq}`;
const your = (p, sq) => `your ${p} on ${sq}`;
const DEVELOP = { kind: "develop" };

function develops(color, piece, from) {
  const origin = { queen: ["d"], king: ["e"], rook: ["a", "h"], bishop: ["c", "f"], knight: ["b", "g"] };
  const home = color === "white" ? "1" : "8";
  return !!from && from[1] === home && (origin[piece] || []).includes(from[0]);
}

function kindWords(t, to) {
  if (t.kind === "knight") return `Knights jump. From ${t.sq} it reaches ${to} in one hop, and nothing can block a jump. Squares a knight can reach often don't look close.`;
  if (t.kind === "near") return "It was right next to the square.";
  const d = (a, b) => Math.max(Math.abs(FILES.indexOf(a[0]) - FILES.indexOf(b[0])), Math.abs(Number(a[1]) - Number(b[1])));
  const mid = (t.path || []).slice().sort((x, y) => d(t.sq, x) - d(t.sq, y));
  return `It's far away, along the ${t.kind === "far_diagonal" ? "diagonal" : "line"} ${[t.sq, ...mid, to].join(", ")}. When we move a piece we look near it, so a piece at the far end of a line is easy to miss.`;
}

function takerKindWords(kind) {
  if (kind === "knight") return "a knight jump";
  if (kind === "near") return "a piece close by";
  return "a long line";
}

/** Where a piece moved from fen A to fen B: the square that gained an enemy-to-A piece. */
function moveDiff(fenA, fenB) {
  const a = parseFen(fenA), b = parseFen(fenB);
  const to = Object.keys(b).find((sq) => a[sq] !== b[sq]);
  return to || null;
}

// ---------------------------------------------------------------------------
// board
// ---------------------------------------------------------------------------
function Board({ color, pos, marks, arrows, live }) {
  const flip = color === "black";
  const xy = (sq) => {
    const f = FILES.indexOf(sq[0]), r = Number(sq[1]);
    const col = flip ? 7 - f : f, row = flip ? r - 1 : 8 - r;
    return [col * 12.5 + 6.25, row * 12.5 + 6.25];
  };
  const squares = [];
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const f = flip ? 7 - col : col, r = flip ? row + 1 : 8 - row, sq = FILES[f] + r;
      const p = pos[sq];
      const act = live[sq];
      const cls = ["cp-sq", (f + r) % 2 === 0 ? "dk" : "", ...(marks[sq] || []), act ? "live" : ""].filter(Boolean).join(" ");
      squares.push(
        <button key={sq} type="button" className={cls} tabIndex={act ? 0 : -1} onClick={act || undefined}
          aria-label={`${sq}${p ? ` ${isWhitePiece(p) ? "white" : "black"} ${NAME[p.toLowerCase()]}` : ""}`}>
          {p && <span className={`cp-pc ${isWhitePiece(p) ? "w" : "b"}`}>{GLYPH[p.toLowerCase()]}</span>}
          {row === 7 && <span className="cp-coord f">{FILES[f]}</span>}
          {col === 0 && <span className="cp-coord r">{r}</span>}
        </button>,
      );
    }
  }
  const color_ = { A: "var(--cp-bad)", G: "var(--cp-good)", T: "var(--cp-tap)" };
  return (
    <div className="cp-boardbox">
      <div className="cp-board" aria-label="Chess board">{squares}</div>
      <svg className="cp-arrows" viewBox="0 0 100 100" aria-hidden="true">
        <defs>
          {Object.entries(color_).map(([k, c]) => (
            <marker key={k} id={`cp-h${k}`} viewBox="0 0 10 10" refX="6" refY="5" markerWidth="3.2" markerHeight="3.2" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill={c} />
            </marker>
          ))}
        </defs>
        {arrows.map(([a, z, k], i) => {
          const [x1, y1] = xy(a), [x2, y2] = xy(z);
          const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
          return (
            <line key={`${a}${z}${i}`} x1={x1 + (dx / L) * 3} y1={y1 + (dy / L) * 3} x2={x2 - (dx / L) * 4.5} y2={y2 - (dy / L) * 4.5}
              stroke={color_[k]} strokeWidth="2.1" strokeLinecap="round" opacity=".9" markerEnd={`url(#cp-h${k})`} />
          );
        })}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// the flow
// ---------------------------------------------------------------------------
export default function ReflectFlow({ moment, warningSign, rule, onSubmit, onClose }) {
  const m = moment;
  const [stage, setStage] = useState("intent");
  const [log, setLog] = useState([]);
  const [picks, setPicks] = useState([]);
  const [taps, setTaps] = useState([]);           // tap_pieces test
  const [sel, setSel] = useState(null);           // a selected own piece (find_move / practice)
  const [tries, setTries] = useState(0);          // find_move wrong tries
  const [found, setFound] = useState(null);
  const [tapped, setTapped] = useState([]);
  const [seen, setSeen] = useState(null);
  const [graded, setGraded] = useState(false);
  const [practice, setPractice] = useState([]);   // ucis tried
  const [tryView, setTryView] = useState(null);   // {uci, v}
  const [revealView, setRevealView] = useState(null);
  const submitted = useRef(false);
  const logEnd = useRef(null);

  useEffect(() => { logEnd.current?.scrollIntoView?.({ block: "nearest" }); }, [log]);

  const say = (text, who = "coach", extra = {}) => setLog((l) => [...l, { who, text, ...extra }]);
  const sayAll = (items) => setLog((l) => [...l, ...items]);
  const mine = (p) => (m.color === "white" ? isWhitePiece(p) : !isWhitePiece(p));
  const dateWords = useMemo(() => {
    try { return new Date(`${m.date}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" }); }
    catch { return m.date; }
  }, [m.date]);
  const tapTest = m.test?.kind === "tap_pieces";
  const testFen = m.kind === "king_attack" || m.kind === "missed_tactic" ? m.fen_before : m.fen_after;

  // ---------- opening ----------
  useEffect(() => {
    const pace = m.think_s == null ? "" : m.think_s >= 15 ? " You took your time over it." : m.think_s <= 5 ? " You played it quickly." : "";
    const options = (m.intents || []).some((x) => x.kind === "defend")
      ? "Red rings: his pieces it now attacks. Green rings: your pieces it now guards."
      : (m.intents || []).length ? "Red rings: his pieces it now attacks." : "";
    setLog([
      { who: "coach", text: `Your game from ${dateWords}. You had ${m.color}, and you played ${m.san}.${pace}` },
      { who: "ask", text: `What was ${m.san} for? Tap everything it was about, then press Done.`,
        small: `${options}${options ? " " : ""}Or pick "Bring it into play" below. Tap again to take a pick back.` },
    ]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m.key]);

  const escapeOpt = useMemo(() => ({ kind: "escape", sq: m.from }), [m.from]);
  const intentOptions = () => [...(m.intents || []), ...(m.escape ? [escapeOpt] : [])];
  const togglePick = (it) => setPicks((ps) => (ps.includes(it) ? ps.filter((x) => x !== it) : [...ps, it]));

  // ---------- 1. what was it for ----------
  function pickWords(it) {
    if (it.kind === "attack") return `attack ${his(it.piece, it.sq)}`;
    if (it.kind === "defend") return `guard ${your(it.piece, it.sq)}`;
    if (it.kind === "develop") return `bring my ${m.moved} into play`;
    return "get it out of danger";
  }
  function intentReply(it) {
    if (!it || it.kind === "other") return "Okay. Whatever the plan, there is one check that comes first.";
    if (it.kind === "escape") return "Yes, it was under attack where it stood, so moving it made sense.";
    if (it.kind === "develop") {
      if (!(m.develops ?? develops(m.color, m.moved, m.from))) return `Your ${m.moved} was already in play before this move, so this one wasn't about bringing it out.`;
      if (m.moved === "queen") return "Bringing pieces into play is a good plan. With the queen it's usually best to bring the knights and bishops out first, because his smaller pieces can chase a queen around. Where it lands is the part to check.";
      return "Bringing pieces into play is a good plan. Where it lands is the part to check.";
    }
    if (it.kind === "attack") {
      let t = `Yes. From ${m.to} your ${m.moved} attacks ${his(it.piece, it.sq)}.`;
      if (it.already_attacked) t += " It was already under attack before this move.";
      t += it.guarded_by_them ? " But it's guarded, so he doesn't have to worry about it yet." : " And nothing guards it, so that's a real threat.";
      return t;
    }
    const a = it.attackers || [];
    const cheapest = a.slice().sort((x, y) => VALUE[x.piece] - VALUE[y.piece])[0];
    if (!cheapest) return `Yes, from ${m.to} it guards ${your(it.piece, it.sq)}.`;
    if (it.verdict === "cheaper_attacker") return `Right, ${his(cheapest.piece, cheapest.sq)} was attacking ${your(it.piece, it.sq)}. But guarding doesn't help against a ${cheapest.piece}. It's worth less than your ${it.piece}, so taking still wins for him.`;
    if (it.verdict === "needed") {
      const stuck = (it.guards || []).find((g) => g.pinned && g.pinned_by);
      let t = `Good eye. ${cap(his(a[0].piece, a[0].sq))} was attacking ${your(it.piece, it.sq)}.`;
      if (stuck) t += ` Your ${stuck.piece} on ${stuck.sq} couldn't help: it was stuck in front of your king, on the line of ${his(stuck.pinned_by.piece, stuck.pinned_by.sq)}.`;
      return `${t} So ${it.sq} really did need a guard.`;
    }
    const g = (it.guards || [])[0];
    return g ? `${cap(his(a[0].piece, a[0].sq))} was attacking ${your(it.piece, it.sq)}, but ${your(g.piece, g.sq)} already guarded it.`
      : `${cap(his(a[0].piece, a[0].sq))} was attacking ${your(it.piece, it.sq)}.`;
  }
  function finishIntent(chosen, label) {
    const real = (chosen || []).filter((it) => ["attack", "defend", "escape", "develop"].includes(it.kind));
    const items = [];
    if (label) items.push({ who: "child", text: label });
    else if (real.length) items.push({ who: "child", text: `To ${andList(real.map(pickWords))}.` });
    else items.push({ who: "child", text: "None of these." });
    (real.length ? real : [chosen && chosen[0]]).forEach((it) => items.push({ who: "coach", text: intentReply(it) }));
    if (real.length && m.kind !== "missed_tactic") items.push({ who: "coach", text: "Whatever the plan, there is one check that comes first." });
    if (m.kind === "missed_tactic") items.push({ who: "coach", text: "There was something better on the board, though." });
    items.push(testAsk());
    setPicks(real.length ? real : (chosen || []));
    sayAll(items);
    setStage("test");
  }

  // ---------- 2. the check ----------
  function testAsk() {
    if (m.kind === "landing") return { who: "ask", text: `Now the check. With your ${m.moved} on ${m.to}, which of his pieces could take it?`, small: "Tap every piece you think can reach it, then press Done. If none can, just press Done." };
    if (m.kind === "king_attack") return { who: "ask", text: "Back to the position before your move. Which of his pieces were aiming at the squares around your king?", small: "Tap them, then press Done." };
    return { who: "ask", text: "Back to the position before your move. There was a move here that wins something. Find it.", small: "Tap the piece, then where it goes." };
  }
  function gradeTaps() {
    const answer = m.test.answer || [];
    const right = new Set(answer.map((a) => a.sq));
    const pos = parseFen(testFen);
    const nm = (sq) => `${NAME[(pos[sq] || "p").toLowerCase()]} on ${sq}`;
    const wrong = taps.filter((s) => !right.has(s));
    const hit = taps.filter((s) => right.has(s));
    const items = [{ who: "child", text: taps.length ? `The ${andList(taps.map(nm))}.` : "None of them." }];
    let ok;
    if (m.kind === "landing") {
      const missed = answer.filter((a) => !taps.includes(a.sq));
      ok = missed.length === 0;
      if (ok) items.push({ who: "coach", text: `Yes, ${andList(answer.map((a) => his(a.piece, a.sq)))}. You saw it.${wrong.length ? ` (The ${andList(wrong.map(nm))} can't reach ${m.to}.)` : ""}` });
      else {
        const l = missed[0];
        items.push({ who: "coach", text: `${wrong.length ? `Not ${andList(wrong.map(nm))}: ${wrong.length > 1 ? "they" : "it"} can't reach ${m.to}. ` : ""}The piece that can take it is ${his(l.piece, l.sq)}.` });
        items.push({ who: "coach", text: kindWords(l, m.to) });
        const both = (m.intents || []).find((it) => it.kind === "attack" && it.sq === l.sq);
        if (both) items.push({ who: "coach", text: `And look: your ${m.moved} was attacking that ${l.piece}. A line works both ways. If your ${m.moved} can see ${l.sq}, the ${l.piece} on ${l.sq} can see ${m.to}.` });
      }
    } else {
      ok = hit.length >= Math.ceil(answer.length / 2) && wrong.length <= 1;
      const list = andList(answer.map((a) => his(a.piece, a.sq)));
      items.push({ who: "coach", text: ok ? `Yes. ${cap(list)} ${answer.length > 1 ? "were" : "was"} aiming at the squares around your king.` : `These were aiming at the squares around your king: ${list}.` });
      items.push({ who: "coach", text: "When several squares next to your king are under fire, the next move should help the king first." });
    }
    setFound(ok); setTapped(taps.slice()); setGraded(true);
    items.push(seenAsk());
    sayAll(items);
    setStage("seen");
  }
  function explainBest() {
    const ex = m.test?.explain || {};
    const t = ex.targets || [];
    if (ex.mate || m.pattern === "mate") return "It leads to checkmate.";
    if (m.pattern === "fork" && t.length >= 2) return `It attacks ${andList(t.map((x) => his(x.piece, x.sq)))} at once.`;
    if ((m.pattern === "pin" || m.pattern === "skewer") && t.length >= 2) return `It lines up ${his(t[0].piece, t[0].sq)} and ${his(t[1].piece, t[1].sq)}.`;
    return "It wins something for you.";
  }
  function tryFind(uci) {
    const best = m.test.best;
    const san = m.practice?.moves?.[uci]?.san || uci;
    setSel(null);
    if ((m.test.accept || []).includes(uci)) {
      setFound(true); setTapped((t) => [...t, uci]); setGraded(true);
      sayAll([{ who: "child", text: san }, { who: "coach", text: `Yes, ${san}. ${explainBest()}` }, seenAsk()]);
      setStage("seen");
      return;
    }
    const n = tries + 1;
    setTries(n); setTapped((t) => [...t, uci]);
    if (n >= 2) {
      setFound(false); setGraded(true);
      sayAll([{ who: "child", text: san }, { who: "coach", text: `Not that one. Here it is: ${best.san}. ${explainBest()}` }, seenAsk()]);
      setStage("seen");
    } else {
      sayAll([{ who: "child", text: san }, { who: "coach", text: "Not that one. Have another look." }]);
    }
  }

  // ---------- 2b. did you see it in the game ----------
  function seenAsk() {
    let what;
    if (m.kind === "landing") { const l = (m.test.answer || [])[0]; what = l ? his(l.piece, l.sq) : "the piece that could take it"; }
    else if (m.kind === "king_attack") what = "his pieces gathering near your king";
    else what = m.test.best.san;
    return { who: "ask", text: `One honest question. In the game, before you played ${m.san}, did you see ${what}?`, small: "There is no wrong answer here. It tells us what to practise." };
  }
  function answerSeen(v) {
    setSeen(v);
    const label = { no: "No, I didn't see it.", ok: "I saw it, but thought it was fine.", unsure: "Not sure." }[v];
    let t;
    if (v === "no") {
      if (found) t = "That's useful. You found it just now when you looked for it. So the job isn't learning something new, it's doing the look every time.";
      else if (m.kind === "landing") t = `That's the most common reason, and it can be trained. It's ${takerKindWords((m.test.answer || [])[0]?.kind)}, and that's what we'll practise.`;
      else if (m.kind === "king_attack") t = "That's what we'll practise: before each move, a look at the squares around your king.";
      else t = `That's what we'll practise: spotting ${PATTERN_WORDS[m.pattern] || "moves that win something"}.`;
    } else if (v === "ok") {
      t = m.kind === "missed_tactic"
        ? "Then the habit to build is trusting what you see: when you spot a move like that, look at it properly before playing something else."
        : "Then the gap is the next question: if he takes, is that okay for me? Let's see what happened.";
    } else t = "That's fine. Most players don't remember. The look we practise covers it either way.";
    const items = [{ who: "child", text: label }, { who: "coach", text: t }];
    if (m.kind === "missed_tactic") { sayAll(items); finish(); return; }
    sayAll([...items, ...replyLines()]);
    setStage("reply");
  }

  // ---------- 3. what happened ----------
  function replyLines() {
    if (!m.reply_san) return [];
    let cost = "";
    if (m.cost) cost = m.cost.can_recapture ? ` You can take back, but that's your ${m.cost.lost} for his ${m.cost.won}.` : ` Nothing of yours can take back, so your ${m.cost.lost} is simply gone.`;
    return [{ who: "coach", text: `What happened next: ${m.reply_san}.${cost}` }];
  }
  function job() {
    const real = picks.filter((it) => it.kind === "attack" || it.kind === "defend");
    return real.find((it) => it.kind === "defend" && it.verdict === "needed") || real[0] || null;
  }
  function startPractice() {
    if (!m.practice || !Object.keys(m.practice.moves || {}).length) { finish(); return; }
    const j = job();
    let ask;
    if (m.kind === "king_attack") ask = { who: "ask", text: "Your turn. Back to the position before your move. Find a move that looks after your king.", small: "Tap a piece, then where it goes." };
    else {
      const want = j ? (j.kind === "defend" && j.verdict !== "cheaper_attacker" ? ` Try to find one where it still guards ${j.sq} and can't be taken.`
        : j.kind === "attack" ? ` Try to find one where it still attacks ${his(j.piece, j.sq)} and can't be taken.` : " Try to find one where it can't be taken.")
        : " Try to find one where it can't be taken.";
      ask = { who: "ask", text: `Your turn. Back to the position before your move. Where else could your ${m.moved} go?${want}`, small: "Tap a dotted square. I will do the check with you." };
    }
    say(ask.text, "ask", { small: ask.small });
    setStage("practice");
  }
  function tryPractice(uci) {
    const v = m.practice.moves[uci];
    const to = uci.slice(2, 4);
    const j = job();
    const n = practice.length + 1;
    setPractice((p) => [...p, uci]);
    setSel(null);
    setTryView({ uci, v });
    let t; let good = false;
    if (m.kind === "king_attack") {
      good = v.loss <= 80;
      t = good ? "That's a good move here. It keeps you safe." : "There's a stronger move here.";
      if ((v.takers || []).length) t = `Do the check: ${andList(v.takers.map((x) => his(x.piece, x.sq)))} can take it on ${to}. ${good ? "Still, the engine likes this move." : "Not safe."}`;
    } else {
      const keeps = j && (j.kind === "defend" ? (v.guards || []).includes(j.sq) : (v.attacks || []).includes(j.sq));
      if ((v.takers || []).length) t = `Do the check: ${andList(v.takers.map((x) => his(x.piece, x.sq)))} can take it on ${to}. Not safe.`;
      else if (j && j.verdict === "cheaper_attacker") {
        const low = (j.attackers || []).slice().sort((x, y) => VALUE[x.piece] - VALUE[y.piece])[0];
        good = v.loss <= 120;
        t = `Safe. ${keeps ? `It still guards your ${j.piece}, but remember, guarding doesn't stop ${his(low.piece, low.sq)} from taking it.` : `But your ${j.piece} is still under attack.`}${good ? " Still, the engine likes this move." : " The engine finds something much stronger here."}`;
      } else if (j && !keeps) t = `Safe. But from ${to} it no longer ${j.kind === "defend" ? `guards ${j.sq}` : `attacks ${his(j.piece, j.sq)}`}.`;
      else {
        good = v.loss <= 120;
        t = `Safe. Nothing of his can reach ${to}.${j ? ` And it still ${j.kind === "defend" ? `guards ${j.sq}` : `attacks ${his(j.piece, j.sq)}`}.` : ""}${good ? " That's a good move." : " There's a stronger move here, though."}`;
      }
    }
    sayAll([{ who: "child", text: v.san }, { who: "coach", text: t }]);
    if (good || n >= 3) reveal();
  }
  function reveal() {
    const b = m.best || {};
    const freed = (b.frees || []).find((f) => (f.now_guards || []).length);
    const sameJob = (m.intents || []).find((it) => it.kind === "attack" && (b.attacks || []).includes(it.sq));
    const bFrom = (b.uci || "").slice(0, 2);
    const bPiece = NAME[(parseFen(m.fen_before)[bFrom] || "p").toLowerCase()];
    const alsoDevelops = picks.includes(DEVELOP) && develops(m.color, bPiece, bFrom);
    let t;
    if (freed) t = `The strongest move here was ${b.san}.${alsoDevelops ? " It brings a piece into play too, like you wanted." : ""} After it, your ${freed.piece} on ${freed.sq} is no longer stuck in front of your king, so it guards ${andList(freed.now_guards)} again. And nothing is left where it can be taken.`;
    else if (sameJob && b.safe) t = `The strongest move here was ${b.san}. It attacks the same ${sameJob.piece} on ${sameJob.sq}, from a square none of his pieces can reach.`;
    else if (b.san && m.kind === "king_attack") t = `The strongest move here was ${b.san}.`;
    else t = "The strongest move here is a hard one, and it isn't today's lesson. Today's lesson is the check you just did.";
    setRevealView({ freed, sameJob });
    say(t);
    finish();
  }

  // ---------- 4. the card and the rule ----------
  // The answers are read after the last state change has rendered, so the
  // final "seen" / "found" / practice taps are all in them.
  function finish() { setStage("done"); }
  useEffect(() => {
    if (stage !== "done" || submitted.current) return;
    submitted.current = true;
    const answers = {
      picks: picks.map((it) => (it.sq ? { kind: it.kind, sq: it.sq } : { kind: it.kind })),
      found_when_asked: !!found,
      tapped,
      seen_in_game: seen,
      practice,
    };
    const R = cardLines(answers);
    const items = [{ who: "card", title: "Your reflection", text: R.join("\n") }];
    if (warningSign?.text) items.push({ who: "card", title: warningSign.title || "Before you move", text: warningSign.text });
    if (rule?.text) items.push({ who: "card", title: "Your rule this week", text: rule.text });
    items.push({ who: "coach", text: "Next week I'll look through your new games for this, and tell you whether it happened less." });
    sayAll(items);
    if (onSubmit) Promise.resolve(onSubmit(answers)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  function cardLines(a) {
    const wanted = picks.filter((it) => ["attack", "defend", "escape", "develop"].includes(it.kind)).map(pickWords);
    let missed;
    if (m.kind === "landing") { const l = (m.test.answer || [])[0]; missed = l ? `Could be taken by: ${his(l.piece, l.sq)}, ${takerKindWords(l.kind)}.` : ""; }
    else if (m.kind === "king_attack") missed = `Pieces near your king: ${andList((m.test.answer || []).map((x) => his(x.piece, x.sq)))}.`;
    else missed = `The better move: ${m.test.best.san}, ${PATTERN_WORDS[m.pattern] || "a move that wins something"}.`;
    return [
      `Wanted: ${wanted.length ? andList(wanted) : "not sure"}.`,
      missed,
      `Found it when asked: ${a.found_when_asked ? "yes" : "no"}.`,
      `In the game: ${{ no: "didn't see it", ok: "saw it, thought it was fine", unsure: "not sure" }[a.seen_in_game] || "not asked"}.`,
    ].filter(Boolean);
  }

  // ---------- board for the current step ----------
  const board = (() => {
    const marks = {}; const arrows = []; const live = {};
    const mark = (sq, c) => { (marks[sq] = marks[sq] || []).push(c); };
    let fen = m.fen_after; let pos;
    if (stage === "intent") {
      mark(m.from, "last"); mark(m.to, "last");
      intentOptions().forEach((it) => {
        mark(it.sq, it.kind === "attack" ? "r-attack" : "r-guard");
        if (picks.includes(it)) { mark(it.sq, "r-tap"); if (it.kind !== "escape") arrows.push([m.to, it.sq, it.kind === "attack" ? "A" : "G"]); }
        live[it.sq] = () => togglePick(it);
      });
    } else if ((stage === "test" || stage === "seen" || stage === "reply") && tapTest) {
      fen = stage === "reply" && m.fen_reply ? m.fen_reply : testFen;
      pos = parseFen(fen);
      if (stage === "reply" && m.fen_reply) {
        const dest = moveDiff(m.fen_after, m.fen_reply);
        if (m.reply_from) mark(m.reply_from, "last");
        if (dest) mark(dest, "last");
      } else if (!graded) {
        if (m.kind === "landing") { mark(m.from, "last"); mark(m.to, "last"); }
        Object.entries(pos).forEach(([sq, p]) => {
          if (mine(p)) return;
          if (taps.includes(sq)) mark(sq, "r-tap");
          live[sq] = () => setTaps((t) => (t.includes(sq) ? t.filter((x) => x !== sq) : [...t, sq]));
        });
      } else {
        if (m.kind === "landing") {
          mark(m.from, "last"); mark(m.to, "last");
          (m.test.answer || []).forEach((l) => { mark(l.sq, "danger"); (l.path || []).forEach((p) => mark(p, "path")); arrows.push([l.sq, m.to, "A"]); });
        } else {
          (m.test.ring || []).forEach((sq) => mark(sq, "path"));
          if (m.test.king) mark(m.test.king, "last");
          (m.test.answer || []).forEach((l) => mark(l.sq, "danger"));
        }
      }
    } else if ((stage === "test" || stage === "seen") && !tapTest) {
      fen = m.fen_before; pos = parseFen(fen);
      if (stage === "test") {
        Object.entries(pos).forEach(([sq, p]) => { if (mine(p)) live[sq] = () => setSel(sq === sel ? null : sq); });
        if (sel) {
          mark(sel, "r-sel");
          Object.keys(m.practice?.moves || {}).filter((u) => u.slice(0, 2) === sel).forEach((u) => {
            const to = u.slice(2, 4); mark(to, "dest"); if (pos[to]) mark(to, "occ"); live[to] = () => tryFind(u);
          });
        }
      } else {
        const b = m.test.best.uci;
        mark(b.slice(0, 2), "last"); mark(b.slice(2, 4), "last"); arrows.push([b.slice(0, 2), b.slice(2, 4), "G"]);
        (m.test.explain?.targets || []).forEach((t) => arrows.push([b.slice(2, 4), t.sq, "A"]));
      }
    } else if (stage === "practice") {
      fen = m.fen_before; pos = parseFen(fen);
      if (tryView) {
        const from = tryView.uci.slice(0, 2), to = tryView.uci.slice(2, 4);
        pos = { ...pos }; pos[to] = pos[from]; delete pos[from];
        mark(from, "last"); mark(to, "last");
        (tryView.v.takers || []).forEach((t) => { mark(t.sq, "danger"); arrows.push([t.sq, to, "A"]); });
      } else {
        const fromSq = m.practice?.from || sel;
        if (m.practice?.from) mark(m.practice.from, "last");
        else Object.entries(pos).forEach(([sq, p]) => { if (mine(p)) live[sq] = () => setSel(sq === sel ? null : sq); });
        if (fromSq) {
          if (!m.practice?.from) mark(fromSq, "r-sel");
          Object.keys(m.practice?.moves || {}).filter((u) => u.slice(0, 2) === fromSq).forEach((u) => {
            const to = u.slice(2, 4); mark(to, "dest"); if (pos[to]) mark(to, "occ"); live[to] = () => tryPractice(u);
          });
        }
      }
    } else if (stage === "reply") {
      fen = m.fen_reply || m.fen_after;
    } else if (stage === "done") {
      const b = m.best || {};
      if (revealView && b.uci) {
        fen = m.fen_before; pos = parseFen(fen);
        const from = b.uci.slice(0, 2), to = b.uci.slice(2, 4);
        pos = { ...pos }; pos[to] = pos[from]; delete pos[from];
        mark(from, "last"); mark(to, "last");
        if (revealView.freed) revealView.freed.now_guards.forEach((g) => arrows.push([revealView.freed.sq, g, "G"]));
        else if (revealView.sameJob) arrows.push([to, revealView.sameJob.sq, "A"]);
      } else if (m.kind === "missed_tactic") {
        fen = m.fen_before; const bu = m.test.best.uci; mark(bu.slice(0, 2), "last"); mark(bu.slice(2, 4), "last");
        arrows.push([bu.slice(0, 2), bu.slice(2, 4), "G"]);
      } else { fen = m.fen_reply || m.fen_after; }
    }
    return { pos: pos || parseFen(fen), marks, arrows, live };
  })();

  const key = stage === "intent"
    ? [["box-shadow:inset 0 0 0 3px var(--cp-bad)", "his piece it attacks"], ["box-shadow:inset 0 0 0 3px var(--cp-good)", "your piece it guards"], ["box-shadow:inset 0 0 0 3px var(--cp-tap);border-radius:3px", "your picks"]]
    : stage === "practice" || (stage === "test" && !tapTest)
      ? [["background:radial-gradient(circle,var(--cp-dot) 0 35%,transparent 36%)", "squares it can go to"]]
      : graded && tapTest && stage !== "reply" ? [["background:var(--cp-danger);border-radius:3px", m.kind === "landing" ? "can take it" : "aiming at your king"]] : [];

  // ---------- buttons under the conversation ----------
  let bar = null;
  if (stage === "intent") {
    bar = (
      <>
        <button type="button" className="cp-chip" aria-pressed={picks.includes(DEVELOP)} onClick={() => togglePick(DEVELOP)}>Bring it into play</button>
        <button type="button" className="cp-chip go" onClick={() => finishIntent(picks.slice())}>Done</button>
        <button type="button" className="cp-chip" onClick={() => finishIntent(null, "Not sure.")}>Not sure</button>
        <button type="button" className="cp-chip" onClick={() => finishIntent([{ kind: "other" }], "Something else.")}>Something else</button>
      </>
    );
  } else if (stage === "test" && tapTest) {
    bar = <button type="button" className="cp-chip go" onClick={gradeTaps}>Done</button>;
  } else if (stage === "test") {
    bar = <span className="cp-hint">{sel ? "Now tap where it goes." : "Tap one of your pieces."}</span>;
  } else if (stage === "seen") {
    bar = (
      <>
        <button type="button" className="cp-chip" onClick={() => answerSeen("no")}>No, I didn't see it</button>
        <button type="button" className="cp-chip" onClick={() => answerSeen("ok")}>I saw it, but thought it was fine</button>
        <button type="button" className="cp-chip" onClick={() => answerSeen("unsure")}>Not sure</button>
      </>
    );
  } else if (stage === "reply") {
    bar = <button type="button" className="cp-chip go" onClick={startPractice}>Your turn</button>;
  } else if (stage === "practice") {
    bar = (
      <>
        {tryView && <button type="button" className="cp-chip go" onClick={() => setTryView(null)}>Try another square</button>}
        <button type="button" className="cp-chip" onClick={reveal}>Show me</button>
      </>
    );
  } else if (stage === "done" && onClose) {
    bar = <button type="button" className="cp-chip go" onClick={onClose}>Back to this week</button>;
  }

  return (
    <div className="cp" data-stage={stage}>
      <div className="cp-boardcol">
        <div className="cp-meta"><span>{dateWords} · you had {m.color}</span><span>you played {m.san}</span></div>
        <Board color={m.color} {...board} />
        {key.length > 0 && (
          <div className="cp-key">
            {key.map(([style, t]) => (
              <span key={t}><i style={Object.fromEntries(style.split(";").filter(Boolean).map((d) => { const [k, ...v] = d.split(":"); return [k.trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase()), v.join(":").trim()]; }))} />{t}</span>
            ))}
          </div>
        )}
      </div>
      <section className="cp-talk" aria-label="Coach">
        <div className="cp-log" aria-live="polite">
          {log.map((x, i) => (x.who === "card" ? (
            <div key={i} className="cp-card"><b>{x.title}</b>{x.text}</div>
          ) : (
            <div key={i} className={`cp-msg ${x.who}`}>{x.text}{x.small && <small>{x.small}</small>}</div>
          )))}
          <div ref={logEnd} />
        </div>
        <div className="cp-bar">{bar}</div>
      </section>
    </div>
  );
}
