/**
 * /admin/plan-outcomes: does following the plan raise ratings?
 * (services/plan_outcomes.py) For every player on the plan, week by week:
 * the step, last week's verdict, the work done, games played, and his real
 * rating against his rating before the plan. Admin only; read-only.
 */
import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { API } from "@/App";

const signed = (n) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n}`);

export default function AdminPlanOutcomes() {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const [open, setOpen] = useState(null);

  useEffect(() => {
    fetch(`${API}/admin/plan-outcomes`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => setState({ loading: false, data, error: null }))
      .catch((e) => setState({ loading: false, data: null, error: e.message }));
  }, []);

  if (state.loading) return <div className="cg-page p-8 text-body">Loading…</div>;
  if (state.error) return <div className="cg-page p-8 text-body text-red-600">{state.error}</div>;
  const { players, summary } = state.data;

  return (
    <div className="cg-page mx-auto max-w-6xl p-6 md:p-8" data-testid="admin-plan-outcomes">
      <Link to="/admin" className="text-note text-muted-foreground hover:underline">Admin</Link>
      <h1 className="mt-2 font-heading text-display text-foreground">Plan outcomes</h1>
      <p className="mt-2 max-w-3xl text-body text-muted-foreground">
        Does following the plan raise ratings? Each player's real rating each week (median of that week's game
        ratings) against his rating before the plan. "Followed" = did plan work in at least half his weeks.
      </p>

      <div className="mt-6 grid gap-3 md:grid-cols-3">
        <div className="rounded-card border border-border p-4"><p className="text-meta text-muted-foreground">Players on the plan</p><p className="text-title">{summary.players}</p></div>
        <div className="rounded-card border border-border p-4"><p className="text-meta text-muted-foreground">Followed it · median change</p><p className="text-title">{summary.followed} · {signed(summary.followed_median_change)}</p></div>
        <div className="rounded-card border border-border p-4"><p className="text-meta text-muted-foreground">Did not · median change</p><p className="text-title">{summary.not_followed} · {signed(summary.not_followed_median_change)}</p></div>
      </div>

      <table className="mt-8 w-full text-note">
        <thead className="text-left text-muted-foreground">
          <tr><th className="py-2">Player</th><th>Before plan</th><th>Weeks</th><th>Weeks with work</th><th>Change now</th><th>This week's step</th></tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <Fragment key={p.user_id}>
              <tr className="cursor-pointer border-t border-border/60 hover:bg-muted/40" onClick={() => setOpen(open === p.user_id ? null : p.user_id)}>
                <td className="py-2 font-mono">…{p.user_id.slice(-6)}</td>
                <td>{p.baseline_rating ?? "—"}</td>
                <td>{p.weeks_on_plan}</td>
                <td>{p.weeks_with_work}</td>
                <td className={p.change_now > 0 ? "text-emerald-700" : p.change_now < 0 ? "text-amber-700" : ""}>{signed(p.change_now)}</td>
                <td>{p.weeks[p.weeks.length - 1]?.step || "—"}</td>
              </tr>
              {open === p.user_id && (
                <tr><td colSpan={6} className="bg-muted/20 p-3">
                  <table className="w-full text-meta">
                    <thead className="text-left text-muted-foreground"><tr><th>Week</th><th>Step</th><th>Last week</th><th>Learn / find / play</th><th>Games</th><th>Rating</th><th>Change</th></tr></thead>
                    <tbody>
                      {p.weeks.map((w) => (
                        <tr key={w.week_start}>
                          <td>{w.week_start}</td><td>{w.step}</td><td>{w.verdict_on_last_week || "—"}</td>
                          <td>{w.work.learn} / {w.work.find} / {w.work.play}</td><td>{w.games}</td><td>{w.rating ?? "—"}</td><td>{signed(w.change)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </td></tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
