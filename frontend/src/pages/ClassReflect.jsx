/**
 * "This week with your coach": the child's reflection on a few of their own
 * moments, reached from the class link. docs/coach_assistant_plan_scope.md 2c.
 *
 * No account and no typing. The server decides which moments, the warning
 * sign and the rule (routes/academy.py); this page only walks through them.
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { API } from "@/App";
import ReflectFlow from "@/components/coachplan/ReflectFlow";
import "@/components/room/room.css";

async function getReflect(token) {
  const res = await fetch(`${API}/academy/class/${token}/reflect`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Try again.");
  return data;
}

async function postAnswers(token, key, answers) {
  const res = await fetch(`${API}/academy/class/${token}/reflect/${encodeURIComponent(key)}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(answers),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Your answers did not save. Try again.");
  return data;
}

export default function ClassReflect() {
  const { token } = useParams();
  const [view, setView] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setView(await getReflect(token)); } catch (e) { setError(e.message); }
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const moments = view?.moments || [];
  const next = moments.find((x) => !x.done);
  const name = view?.child_name || "";

  return (
    <div className="room">
      <div className="room-top">
        <span className="room-mark">ChessGuru</span>
        <span className="room-where">{open ? "Looking back" : "This week with your coach"}</span>
      </div>
      <div className="room-page">
        {error && <div className="room-done"><h1>This link needs attention</h1><p>{error}</p></div>}
        {!error && !view && <p className="room-note">Loading…</p>}
        {!error && view && !view.available && (
          <div className="room-done">
            <span className="room-label">This week with your coach</span>
            <h1>Nothing to look back on yet</h1>
            <p>{view.reason}</p>
            <div className="room-acts"><Link className="room-btn quiet" to={`/class/${token}`}>Back to your lessons</Link></div>
          </div>
        )}
        {!error && view?.available && open && (
          <ReflectFlow
            key={open.key}
            moment={open}
            warningSign={view.warning_sign}
            rule={view.rule}
            onSubmit={async (answers) => {
              try { await postAnswers(token, open.key, answers); }
              catch (e) { setError(e.message); }
            }}
            onClose={() => { setOpen(null); load(); }}
          />
        )}
        {!error && view?.available && !open && (
          <div className="room-path">
            <div>
              <span className="room-label">This week with your coach</span>
              <h1>{name ? `${name}, a few moments from your games` : "A few moments from your games"}</h1>
              <p className="room-note">For each one, you answer on the board. No typing, no wrong answers.</p>
            </div>
            {view.warning_sign?.text && (
              <div className="room-next" style={{ gridTemplateColumns: "minmax(0,1fr)" }}>
                <div>
                  <span className="room-label">{view.warning_sign.title || "Before you move"}</span>
                  <p style={{ marginTop: 6 }}>{view.warning_sign.text}</p>
                </div>
              </div>
            )}
            {view.rule?.text && (
              <div className="room-next" style={{ gridTemplateColumns: "minmax(0,1fr)" }}>
                <div>
                  <span className="room-label">Your rule this week</span>
                  <p style={{ marginTop: 6 }}>{view.rule.text}</p>
                </div>
              </div>
            )}
            <div className="room-stage">
              <h3>Your moments</h3>
              <div className="room-rows">
                {moments.map((mo) => (
                  <div key={mo.key} className={`room-row ${mo.done ? "" : "open"}`}>
                    <span aria-hidden="true">{mo.done ? "✔" : "○"}</span>
                    <button type="button" onClick={() => setOpen(mo)} aria-label={`Look back at ${mo.san}`}>
                      <b>You played {mo.san}</b>
                      <span className="room-note">{mo.done ? "Done. You can go over it again." : "Not looked at yet"}</span>
                    </button>
                    <span />
                  </div>
                ))}
              </div>
            </div>
            <div className="room-acts">
              {next
                ? <button type="button" className="room-btn" onClick={() => setOpen(next)}>{moments.some((x) => x.done) ? "Next moment" : "Start"}</button>
                : <p className="room-note">All done for this week. Keep the rule in your games.</p>}
              <Link className="room-btn quiet" to={`/class/${token}`}>Back to your lessons</Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
