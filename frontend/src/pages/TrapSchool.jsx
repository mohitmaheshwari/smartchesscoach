/**
 * The trap school (services/trap_school.py, data/trap_school.json).
 *
 *   /learn/traps        his own traps first (caught / waiting / could set /
 *                       sprang, from his player file), then every trap that
 *                       really happens at 1000-1800 on Lichess.
 *   /learn/traps/:slug  one trap: the line move by move with what each move
 *                       does, the tempting move, and real games where it
 *                       happened, replayed on our board.
 *
 * No figures on the page: how common a trap is comes as a sentence.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, ExternalLink, Target } from "lucide-react";

import Layout from "@/components/Layout";
import { API } from "@/App";

function useJson(path) {
  const [state, setState] = useState({ loading: true, data: null, error: false });
  useEffect(() => {
    let alive = true;
    setState({ loading: true, data: null, error: false });
    fetch(`${API}${path}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => alive && setState({ loading: false, data, error: false }))
      .catch(() => alive && setState({ loading: false, data: null, error: true }));
    return () => {
      alive = false;
    };
  }, [path]);
  return state;
}

function MiniBoard({ fen, orientation, size = 180, arrows = [] }) {
  return (
    <div className="w-full shrink-0" style={{ maxWidth: size }}>
      <div className="aspect-square w-full">
        <Chessboard
          position={fen}
          arePiecesDraggable={false}
          boardOrientation={orientation === "black" ? "black" : "white"}
          customBoardStyle={{ borderRadius: "10px" }}
          customArrows={arrows}
        />
      </div>
    </div>
  );
}

function TrapCardLink({ trap, note }) {
  return (
    <Link
      to={`/learn/traps/${trap.slug}`}
      className="flex items-center gap-4 rounded-card border border-border/70 p-4 hover:bg-muted/40"
      data-testid="trap-school-card"
    >
      <MiniBoard fen={trap.setup_fen} orientation={trap.victim} size={84} />
      <div className="min-w-0">
        <p className="text-body font-semibold text-foreground">{trap.name}</p>
        <p className="mt-0.5 text-note text-muted-foreground">{note || trap.how_common}</p>
      </div>
    </Link>
  );
}

const CASE_NOTES = {
  caught: "It caught you. See how, and how to avoid it.",
  waiting: "Your opponent missed it. Next time they may not.",
  could_set: "Your games reach it. Learn to set it.",
  sprang: "You sprang it. Well played.",
};

export function TrapSchoolHome({ user }) {
  const { loading, data, error } = useJson("/trap-school");
  return (
    <Layout user={user}>
      <div className="experience-page cg-page" data-testid="trap-school-page">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
          <header>
            <Link to="/learn" className="text-note text-muted-foreground hover:underline">Learn</Link>
            <h1 className="mt-2 font-heading text-display text-foreground">Trap school</h1>
            <p className="mt-2 max-w-[640px] text-body text-muted-foreground">
              Opening traps that really happen in games at your level, each with real games where it happened.
            </p>
          </header>
          {loading && <p className="text-body text-muted-foreground">Loading…</p>}
          {error && <p className="text-body text-muted-foreground">The trap school did not load. Try again in a moment.</p>}
          {data?.mine?.map((group) => (
            <section key={group.case} className="cg-panel rounded-panel p-6 md:p-8" data-testid={`trap-school-${group.case}`}>
              <h2 className="font-heading text-title text-foreground">{group.title}</h2>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {group.traps.map((t) => <TrapCardLink key={t.slug} trap={t} note={CASE_NOTES[group.case]} />)}
              </div>
            </section>
          ))}
          {data?.all?.length > 0 && (
            <section className="cg-panel rounded-panel p-6 md:p-8" data-testid="trap-school-all">
              <h2 className="font-heading text-title text-foreground">Every trap</h2>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {data.all.map((t) => <TrapCardLink key={t.slug} trap={t} />)}
              </div>
            </section>
          )}
        </motion.div>
      </div>
    </Layout>
  );
}

function squaresOf(fenBefore, san) {
  try {
    const g = new Chess(fenBefore);
    const m = g.move(san);
    return m ? [m.from, m.to] : null;
  } catch {
    return null;
  }
}

function LineStepper({ trap }) {
  // Step 0 = the setup position; step i = after the i-th trap-line move.
  const [i, setI] = useState(0);
  const fens = [trap.setup_fen, ...trap.steps.map((s) => s.fen_after)];
  const step = i > 0 ? trap.steps[i - 1] : null;
  const sq = step ? squaresOf(fens[i - 1], step.san) : null;
  const isTempting = step && step.san === trap.tempting_move && step.by === trap.victim;
  return (
    <div className="flex flex-col gap-6 md:flex-row md:items-start md:gap-8" data-testid="trap-line">
      <MiniBoard fen={fens[i]} orientation={trap.victim} size={340}
        arrows={sq ? [[sq[0], sq[1], isTempting ? "#b45309" : "#047857"]] : []} />
      <div className="min-w-0 flex-1">
        <p className="cg-eyebrow">{i === 0 ? "The position" : i === trap.steps.length ? "The end of the trap" : "The line"}</p>
        {i === 0 ? (
          <p className="mt-2 text-body text-foreground">{trap.description}</p>
        ) : (
          <>
            <p className="mt-2 font-heading text-lead text-foreground">
              <span className="font-mono">{step.san}</span>
              {isTempting && <span className="ml-2 text-note font-medium text-amber-700 dark:text-amber-400">the tempting move</span>}
            </p>
            {step.explanation && <p className="mt-2 text-body text-muted-foreground">{step.explanation}</p>}
          </>
        )}
        {i === trap.steps.length && trap.how_to_avoid && (
          <p className="mt-4 text-body text-foreground"><span className="font-semibold">How to avoid it:</span> {trap.how_to_avoid}</p>
        )}
        <div className="mt-5 flex gap-2">
          <button type="button" className="cg-secondary-action" disabled={i === 0} onClick={() => setI(i - 1)}>
            <ChevronLeft className="h-4 w-4" /> Back
          </button>
          <button type="button" className="cg-primary-action" disabled={i === trap.steps.length} onClick={() => setI(i + 1)}>
            Next <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function GameReplay({ game, orientation }) {
  const positions = useMemo(() => {
    const g = new Chess();
    const out = [{ fen: g.fen(), san: null, from: null, to: null }];
    for (const san of game.moves || []) {
      try {
        const m = g.move(san);
        out.push({ fen: g.fen(), san, from: m.from, to: m.to });
      } catch {
        break;
      }
    }
    return out;
  }, [game]);
  const end = Math.min(game.line_plies || positions.length - 1, positions.length - 1);
  const [i, setI] = useState(end);
  const cur = positions[i];
  const resultWords = game.winner ? `${game.winner === "white" ? "White" : "Black"} won` : "Draw";
  return (
    <div className="rounded-card border border-border/70 p-4" data-testid="trap-example">
      <MiniBoard fen={cur.fen} orientation={orientation} size={260}
        arrows={cur.from ? [[cur.from, cur.to, "#047857"]] : []} />
      <p className="mt-3 text-note text-muted-foreground">
        A real game on Lichess. {resultWords}.
        {cur.san ? <> Last move <span className="font-mono text-foreground">{cur.san}</span>.</> : null}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" className="cg-secondary-action !min-h-8 !px-3" disabled={i === 0} onClick={() => setI(i - 1)}>
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button type="button" className="cg-secondary-action !min-h-8 !px-3" disabled={i === positions.length - 1} onClick={() => setI(i + 1)}>
          <ChevronRight className="h-4 w-4" />
        </button>
        <button type="button" className="text-note text-primary hover:underline" onClick={() => setI(end)}>The trap</button>
        <a href={game.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-note text-muted-foreground hover:underline">
          Lichess <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}

export function TrapSchoolTrap({ user }) {
  const { slug } = useParams();
  const { loading, data, error } = useJson(`/trap-school/${slug}`);
  return (
    <Layout user={user}>
      <div className="experience-page cg-page" data-testid="trap-school-trap">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
          <Link to="/learn/traps" className="text-note text-muted-foreground hover:underline">Trap school</Link>
          {loading && <p className="text-body text-muted-foreground">Loading…</p>}
          {error && <p className="text-body text-muted-foreground">This trap is not in the school.</p>}
          {data && (
            <>
              <header>
                <h1 className="font-heading text-display text-foreground">{data.name}</h1>
                <p className="mt-2 text-body text-muted-foreground">{data.how_common}</p>
                <p className="mt-1 text-note text-muted-foreground">
                  It wins for {data.setter === "white" ? "White" : "Black"}. The board is shown from the side that falls for it.
                </p>
              </header>
              <section className="cg-panel rounded-panel p-6 md:p-8">
                <h2 className="font-heading text-title text-foreground">The line, move by move</h2>
                <div className="mt-6"><LineStepper trap={data} /></div>
                {data.practice_url && (
                  <Link to={data.practice_url} className="cg-primary-action mt-6 inline-flex" data-testid="trap-practise">
                    <Target className="h-4 w-4" /> Practise it with your coach
                  </Link>
                )}
              </section>
              {data.examples?.length > 0 && (
                <section className="cg-panel rounded-panel p-6 md:p-8">
                  <h2 className="font-heading text-title text-foreground">Real games where it happened</h2>
                  <p className="mt-2 text-body text-muted-foreground">Players at club level, on Lichess. Each game opens on the trap.</p>
                  <div className="mt-6 grid gap-4 md:grid-cols-2">
                    {data.examples.map((g) => <GameReplay key={g.id} game={g} orientation={data.victim} />)}
                  </div>
                </section>
              )}
            </>
          )}
        </motion.div>
      </div>
    </Layout>
  );
}
