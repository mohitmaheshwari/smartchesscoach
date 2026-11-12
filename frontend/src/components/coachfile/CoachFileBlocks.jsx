/**
 * The blocks of the player file, shared by Home, Learn, Progress and the
 * academy view (docs/coach_pages_scope.md). Every block renders what the
 * server put in the file, or nothing: no block computes chess, and no figure
 * reaches the player (the server keeps numbers in `measured`, never shown).
 *
 * Under 1000 the file says `notation: false`: the boards carry the moves and
 * the words point at the arrows instead of naming squares.
 */
import { Link, useNavigate } from "react-router-dom";
import { Chessboard } from "react-chessboard";
import { Coffee, Play, Target, TrendingDown, TrendingUp, Minus, Check, Clock } from "lucide-react";

import { playFrom } from "@/lib/coachFile";

const PLAYED = "#b45309";
const BETTER = "#047857";

function Board({ fen, orientation, arrows = [], marks = {}, size = 220 }) {
  return (
    <div className="w-full shrink-0" style={{ maxWidth: size }}>
      <div className="aspect-square w-full">
        <Chessboard
          position={fen}
          arePiecesDraggable={false}
          boardOrientation={orientation === "black" ? "black" : "white"}
          customBoardStyle={{ borderRadius: "10px" }}
          customArrows={arrows}
          customSquareStyles={marks}
        />
      </div>
    </div>
  );
}

function Moves({ notation, san, better }) {
  if (!notation) {
    return (
      <p className="mt-4 text-note text-foreground/90">
        The orange arrow is what you played. The green arrow is the better move.
      </p>
    );
  }
  return (
    <p className="mt-4 text-note text-foreground/90">
      You played <span className="font-mono text-amber-700 dark:text-amber-400">{san}</span> here.
      {better ? (
        <>
          {" "}Better was <span className="font-mono text-emerald-700 dark:text-emerald-400">{better}</span>.
        </>
      ) : null}
    </p>
  );
}

function Action({ to, onClick, children, testid, quiet = false }) {
  const cls = quiet
    ? "inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-note font-medium text-foreground hover:bg-muted/50"
    : "cg-primary-action !min-h-9 !px-4 !py-2 text-note";
  if (to) {
    return <Link to={to} className={cls} data-testid={testid}>{children}</Link>;
  }
  return <button type="button" onClick={onClick} className={cls} data-testid={testid}>{children}</button>;
}

// --------------------------------------------------------------------------
export function SittingNote({ sitting }) {
  if (!sitting?.show) return null;
  return (
    <div
      data-testid="coach-file-sitting"
      className={`flex items-start gap-3 rounded-card border p-4 ${
        sitting.live ? "border-amber-500/40 bg-amber-500/10" : "border-border/70 bg-muted/30"
      }`}
    >
      <Coffee
        className={`mt-0.5 h-5 w-5 shrink-0 ${sitting.live ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground"}`}
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="text-body font-semibold text-foreground">{sitting.headline}</p>
        <p className="mt-1 text-note text-muted-foreground">{sitting.detail}</p>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
export function WatchFor({ habit, linkToLearn = true }) {
  if (!habit?.warning_sign) return null;
  return (
    <div data-testid="coach-file-watch" className="rounded-card border border-border/70 bg-card p-5">
      <p className="cg-eyebrow">Watch for in your next game</p>
      <p className="mt-2 font-heading text-lead text-foreground">
        {habit.warning_sign.title}
      </p>
      <p className="mt-1.5 text-note text-muted-foreground">{habit.warning_sign.text}</p>
      {habit.rule && (
        <p className="mt-3 text-note text-foreground/90">
          <span className="font-semibold">Your rule:</span> {habit.rule}
        </p>
      )}
      {linkToLearn && (
        <div className="mt-4">
          <Action to="/learn" quiet testid="coach-file-watch-learn">See where it happened</Action>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------
export function LastGameRepeat({ lastGame, notation }) {
  if (!lastGame || lastGame.clean || !lastGame.repeat) return null;
  return (
    <div data-testid="coach-file-repeat" className="rounded-card border border-amber-500/30 bg-amber-500/[0.06] p-5">
      <p className="cg-eyebrow">Your last game</p>
      <p className="mt-2 text-body text-foreground">
        {notation ? (
          <>
            The move that cost you most was{" "}
            <span className="font-mono text-amber-700 dark:text-amber-400">{lastGame.san}</span>.{" "}
          </>
        ) : (
          <>The move that cost you most is one you have played before. </>
        )}
        {lastGame.repeat.words}
      </p>
      <div className="mt-4">
        <Action to={lastGame.review_url} quiet testid="coach-file-repeat-see">See it</Action>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
export function OpeningHabit({ habit, notation, canPlay = true }) {
  const navigate = useNavigate();
  const side = habit.side === "black" ? "Black" : "White";
  return (
    <div className="flex flex-col gap-6 md:flex-row md:items-start md:gap-8" data-testid="coach-file-opening">
      <Board
        fen={habit.fen}
        orientation={habit.side}
        arrows={[
          [habit.played_from, habit.played_to, PLAYED],
          [habit.better_from, habit.better_to, BETTER],
        ]}
        marks={{
          [habit.played_to]: { background: "rgba(180,83,9,0.25)" },
          [habit.better_to]: { background: "rgba(4,120,87,0.22)" },
        }}
      />
      <div className="min-w-0 flex-1">
        <p className="cg-eyebrow">
          {side}
          {notation ? (
            <>
              {" "}· <span className="font-mono normal-case tracking-normal">{habit.line}</span>
            </>
          ) : null}
        </p>
        <h3 className="mt-3 font-heading text-lead text-foreground">
          {habit.headline}
        </h3>
        <p className="mt-2 max-w-[520px] text-body text-muted-foreground">{habit.detail}</p>
        <Moves notation={notation} san={habit.san} better={habit.better_san} />
        <div className="mt-5 flex flex-wrap gap-2">
          {canPlay && (
            <Action
              onClick={() => playFrom({ fen: habit.fen, user_color: habit.side, source_game_id: habit.game_id }, navigate)}
              testid="coach-file-opening-play"
            >
              <Play className="h-3.5 w-3.5" /> Play it the better way
            </Action>
          )}
          {habit.review_url && <Action to={habit.review_url} quiet>See the game</Action>}
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
function trapBoard(trap) {
  return trap.setup_fen || "start";
}

export function TrapCard({ trap, notation }) {
  return (
    <div className="flex flex-col gap-6 md:flex-row md:items-start md:gap-8" data-testid="coach-file-trap">
      <Board fen={trapBoard(trap)} orientation={trap.side} size={200} />
      <div className="min-w-0 flex-1">
        <p className="cg-eyebrow">{trap.name}</p>
        <h3 className="mt-3 font-heading text-lead text-foreground">{trap.headline}</h3>
        <p className="mt-2 text-body text-muted-foreground">{trap.detail}</p>
        {notation && trap.trap_line_san?.length > 0 && (
          <p className="mt-3 text-note text-foreground/90">
            The line: <span className="font-mono">{trap.trap_line_san.join(" ")}</span>
          </p>
        )}
        {trap.practice_url && (
          <div className="mt-4">
            <Action to={trap.practice_url} testid="coach-file-trap-practice">
              <Target className="h-3.5 w-3.5" /> Practise it with your coach
            </Action>
          </div>
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
export function HabitMoments({ habit, notation, canPlay = true }) {
  const navigate = useNavigate();
  const moments = Array.isArray(habit?.moments) ? habit.moments : [];
  if (!moments.length) return null;
  return (
    <div className="grid gap-6 md:grid-cols-3" data-testid="coach-file-moments">
      {moments.map((m) => (
        <div key={m.key || `${m.game_id}-${m.move_number}`} className="rounded-card border border-border/70 p-4">
          <Board
            fen={m.fen_before}
            orientation={m.color}
            size={260}
            arrows={m.from && m.to ? [[m.from, m.to, PLAYED]] : []}
          />
          <p className="mt-3 text-note text-muted-foreground">
            {notation && m.san ? (
              <>
                You played <span className="font-mono text-amber-700 dark:text-amber-400">{m.san}</span> here.
              </>
            ) : (
              <>The orange arrow is the move you played here.</>
            )}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {canPlay && (
              <Action
                onClick={() => playFrom({ fen: m.fen_before, user_color: m.color, source_game_id: m.game_id }, navigate)}
                testid="coach-file-moment-play"
              >
                <Play className="h-3.5 w-3.5" /> Play from here
              </Action>
            )}
            {m.game_id && (
              <Action to={`/game/${m.game_id}${m.move_number ? `?move=${m.move_number}` : ""}`} quiet>
                See the game
              </Action>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------
const STATE_ICON = {
  better: TrendingDown,
  kept: Check,
  worse: TrendingUp,
  same: Minus,
  waiting: Clock,
};
const STATE_TONE = {
  better: "text-emerald-700 dark:text-emerald-400",
  kept: "text-emerald-700 dark:text-emerald-400",
  worse: "text-amber-700 dark:text-amber-400",
  same: "text-muted-foreground",
  waiting: "text-muted-foreground",
};

function StateRow({ row, training }) {
  const Icon = STATE_ICON[row.state] || Minus;
  return (
    <div className="flex items-start justify-between gap-4 py-3.5" data-testid="coach-file-progress-row">
      <div className="min-w-0">
        <p className="text-body font-semibold text-foreground">
          {row.label}
          {training ? <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-meta font-medium text-muted-foreground">Training now</span> : null}
        </p>
        <p className="mt-0.5 text-note text-muted-foreground">{row.words}</p>
      </div>
      <span className={`inline-flex shrink-0 items-center gap-1.5 text-note font-medium ${STATE_TONE[row.state] || ""}`}>
        <Icon className="h-4 w-4" aria-hidden="true" /> {row.title}
      </span>
    </div>
  );
}

export function ProgressList({ file }) {
  const progress = file?.progress || {};
  const habits = Array.isArray(progress.habits) ? progress.habits : [];
  const kept = Array.isArray(progress.kept) ? progress.kept : [];
  const habit = file?.habit;
  const check = file?.habit_check;
  if (!habits.length && !kept.length && !habit) return null;
  return (
    <div data-testid="coach-file-progress">
      {habit && check && (
        <div className="mb-6 rounded-card border border-border/70 bg-muted/20 p-5">
          <p className="cg-eyebrow">Since you started training it</p>
          <StateRow row={{ ...check, label: habit.label }} training />
        </div>
      )}
      {habits.length > 0 && (
        <div className="divide-y divide-border/60">
          {habits.map((r) => (
            <StateRow key={r.quality_id} row={r} training={habit?.quality_id === r.quality_id} />
          ))}
        </div>
      )}
      {kept.length > 0 && (
        <div className="mt-8">
          <p className="cg-eyebrow">Kept · habits that stopped showing up in your games</p>
          <div className="mt-2 divide-y divide-border/60">
            {kept.map((r) => (
              <StateRow key={r.quality_id} row={r} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Progress page section: every habit his games show, and the kept shelf. */
export function CoachProgressSection({ file }) {
  if (!file?.enabled) return null;
  if (file.state === "building") {
    return (
      <section className="cg-panel mb-8 rounded-panel p-6 text-body text-muted-foreground" data-testid="coach-progress-building">
        Your coach is reading your games. This takes a moment the first time.
      </section>
    );
  }
  const p = file.progress || {};
  const empty = !(p.habits?.length || p.kept?.length || file.habit);
  const body = empty ? null : <ProgressList file={file} />;
  return (
    <section className="cg-panel mb-8 rounded-panel p-6 md:p-8" data-testid="coach-progress-section">
      <p className="cg-eyebrow">From your games, not from drills</p>
      <h2 className="mt-2 font-heading text-title text-foreground">
        Is it working?
      </h2>
      <p className="mt-2 max-w-[640px] text-note text-muted-foreground">
        Each habit your coach can check, in your recent games against the games before them.
      </p>
      <div className="mt-6">
        {body || (
          <p className="text-body text-muted-foreground">
            None of the problems your coach can check showed up in your games yet.
          </p>
        )}
      </div>
    </section>
  );
}

// --------------------------------------------------------------------------
export function PlayPositions({ positions, limit = 4 }) {
  const navigate = useNavigate();
  const rows = (Array.isArray(positions) ? positions : []).slice(0, limit);
  if (!rows.length) return null;
  return (
    <div className="space-y-3" data-testid="coach-file-play">
      {rows.map((p) => (
        <div key={p.fen} className="flex items-center justify-between gap-4 rounded-card border border-border/70 p-4">
          <div className="flex min-w-0 items-center gap-4">
            <Board fen={p.fen} orientation={p.user_color} size={72} />
            <div className="min-w-0">
              <p className="text-note font-semibold text-foreground">{p.title}</p>
              <p className="mt-0.5 text-note text-muted-foreground">
                {p.detail} You play {p.user_color === "black" ? "Black" : "White"}.
              </p>
            </div>
          </div>
          <Action onClick={() => playFrom(p, navigate)} testid="coach-file-play-start">
            <Play className="h-3.5 w-3.5" /> Play
          </Action>
        </div>
      ))}
    </div>
  );
}
