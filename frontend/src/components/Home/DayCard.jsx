/**
 * DayCard — today's tasks (docs/daily_coach_plan_scope.md).
 *
 * Fix from this week's plan, one new thing, a look back at something learned
 * a few days ago, and something to play. The server fixes the list when his
 * day starts (in his own time zone) and ticks puzzle and game tasks from their
 * proof; a task that is done by opening it is ticked when he opens it. The
 * week row shows the days he did his work and never counts the others.
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Circle, CircleDot } from "lucide-react";

import { API } from "@/App";
import { playFrom } from "@/lib/coachFile";

const SLOT_WORDS = { fix: "Fix", new: "New", look_back: "Look back", play: "Play" };
const SIZE_WORDS = { short: "Short", normal: "Normal", long: "Long" };

function timeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return "";
  }
}

async function post(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, tz: timeZone() }),
  });
  return res.ok;
}

function Tick({ done }) {
  return done
    ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-label="done" />
    : <Circle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground/60" aria-label="not yet" />;
}

function WeekDot({ state }) {
  if (state === "done") return <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" aria-label="done" />;
  if (state === "part") return <CircleDot className="h-4 w-4 text-primary" aria-label="part done" />;
  return <Circle className="h-4 w-4 text-muted-foreground/40" aria-label="" />;
}

function TaskAction({ task, onOpen }) {
  const navigate = useNavigate();
  if (task.done) return null;
  if (task.action === "play_position" && task.position) {
    return (
      <button type="button" onClick={() => { onOpen(task); playFrom(task.position, navigate); }}
        className="mt-2 inline-flex text-note font-medium text-primary hover:underline">
        Play it
      </button>
    );
  }
  if (task.action === "games") {
    return <p className="mt-2 text-meta text-muted-foreground">Ticked when the games reach your account.</p>;
  }
  if (!task.url) return null;
  const label = task.action === "puzzles" ? (task.count > 1 ? "Start" : "Solve") : "Open";
  return (
    <Link to={task.url} onClick={() => task.action !== "puzzles" && onOpen(task)}
      className="mt-2 inline-flex text-note font-medium text-primary hover:underline">
      {label}
    </Link>
  );
}

export default function DayCard() {
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/daily-plan?tz=${encodeURIComponent(timeZone())}`, { credentials: "include" });
      if (!res.ok) return;
      setData(await res.json());
    } catch {
      /* Home renders without the day card. */
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!data?.enabled || data.state !== "ready" || !data.tasks?.length) return null;

  const onOpen = (task) => {
    post("/daily-plan/tick", { task_id: task.id });
    setData((d) => ({ ...d, tasks: d.tasks.map((t) => (t.id === task.id ? { ...t, done: true } : t)) }));
  };
  const onSize = async (size) => {
    if (size === data.size) return;
    if (await post("/daily-plan/size", { size })) load();
  };

  return (
    <section data-testid="day-card" className="mb-10 rounded-panel border border-border/70 bg-card p-6 shadow-e2 md:p-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="cg-eyebrow">{data.all_done ? "Today · done" : "Today"}</p>
        <div className="flex items-center gap-1 text-meta text-muted-foreground" data-testid="day-card-size">
          <span>Your day:</span>
          {data.sizes.map((s) => (
            <button key={s} type="button" onClick={() => onSize(s)}
              className={`rounded-full px-2 py-0.5 ${s === data.size ? "bg-muted font-semibold text-foreground" : "hover:text-foreground"}`}>
              {SIZE_WORDS[s] || s}
            </button>
          ))}
        </div>
      </div>

      {data.all_done && (
        <p className="mt-3 text-body text-foreground" data-testid="day-card-done">
          Done for today. Tomorrow: something new, and the next step from your games.
        </p>
      )}

      <ol className="mt-4 space-y-4">
        {data.tasks.map((task) => (
          <li key={task.id} className="flex items-start gap-3" data-testid={`day-task-${task.slot}`}>
            <Tick done={task.done} />
            <div className="min-w-0">
              <p className="cg-eyebrow">{SLOT_WORDS[task.slot] || task.slot}</p>
              <p className={`mt-1 text-body font-semibold ${task.done ? "text-muted-foreground" : "text-foreground"}`}>{task.title}</p>
              {!task.done && <p className="mt-1 text-note text-muted-foreground">{task.text}</p>}
              <TaskAction task={task} onOpen={onOpen} />
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-border/60 pt-4" data-testid="day-card-week">
        <span className="text-meta text-muted-foreground">This week</span>
        {data.week.map((w) => (
          <span key={w.day} className={`inline-flex items-center gap-1 text-meta ${w.today ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
            {w.label} <WeekDot state={w.state} />
          </span>
        ))}
      </div>
    </section>
  );
}
