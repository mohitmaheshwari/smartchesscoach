/**
 * The academy's own pages: set-up, the class view and one child's page.
 * docs/academy_pilot_scope.md. Staff only; the server checks the academy on
 * every call (routes/academy.py), so a link to another academy's batch is a 403.
 *
 * WhatsApp: there is no ChessGuru WhatsApp Business number yet, so "Send on
 * WhatsApp" opens WhatsApp with the parent's number and the message filled in,
 * and the coach presses send.
 */
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { API } from "@/App";
import Layout, { rememberAcademyStaff } from "@/components/Layout";
import ParentReport from "@/components/academy/ParentReport";

async function call(path, { method = "GET", body } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Try again.");
  return data;
}

function useLoad(path) {
  const [state, setState] = useState({ loading: true });
  const load = useCallback(async () => {
    try {
      setState((s) => ({ ...s, loading: !s.data }));
      setState({ data: await call(path) });
    } catch (err) {
      setState({ error: err.message });
    }
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return [state, load];
}

const field = "rounded-lg border bg-background px-3 py-2 w-full";
const primary = "rounded-full bg-foreground px-4 py-2 font-semibold text-background disabled:opacity-60";
const secondary = "rounded-full border px-4 py-2 font-semibold";

function Page({ children }) {
  return (
    <Layout>
      <div className="mx-auto grid w-full max-w-5xl gap-6 px-4 py-6">{children}</div>
    </Layout>
  );
}

function Eyebrow({ children }) {
  return <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{children}</p>;
}

function Card({ children, className = "" }) {
  return <section className={`grid gap-3 rounded-2xl border bg-card p-5 ${className}`}>{children}</section>;
}

function WhatsAppButton({ href, label = "Send on WhatsApp", onClick }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" onClick={onClick}
      className="inline-flex items-center rounded-full bg-emerald-600 px-4 py-2 font-semibold text-white">
      {label}
    </a>
  );
}

function CopyButton({ text, label = "Copy link" }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className={secondary} onClick={async () => {
      try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); }
      catch { window.prompt?.("Copy this link", text); }
    }}>
      {done ? "Copied" : label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// /academy
// ---------------------------------------------------------------------------
export function AcademyHome() {
  const navigate = useNavigate();
  const [state, reload] = useLoad("/academy/me");
  const [form, setForm] = useState({ name: "", city: "" });
  const [batchName, setBatchName] = useState({});
  const [coachEmail, setCoachEmail] = useState({});
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (state.data) rememberAcademyStaff(state.data.academies.length > 0);
  }, [state.data]);

  const run = async (fn) => {
    setError(""); setNote("");
    try { await fn(); await reload(); } catch (err) { setError(err.message); }
  };

  if (state.loading) return <Page><p>Loading…</p></Page>;
  if (state.error) return <Page><p className="text-red-600">{state.error}</p></Page>;
  const academies = state.data.academies;

  return (
    <Page>
      <header className="grid gap-1">
        <Eyebrow>ChessGuru for academies</Eyebrow>
        <h1 className="text-3xl font-extrabold">Your academy</h1>
      </header>
      {error && <p className="text-red-600">{error}</p>}
      {note && <p className="text-emerald-700">{note}</p>}

      {academies.length === 0 && (
        <Card>
          <h2 className="text-xl font-semibold">I am a parent</h2>
          <p>No academy? Set up your child at home. You get the same weekly report.</p>
          <button type="button" className={primary + " w-fit"} onClick={() => run(async () => {
            const out = await call("/academy", { method: "POST", body: { kind: "family" } });
            if (out.batch_id) navigate(`/academy/batch/${out.batch_id}`);
          })}>
            Set up my child
          </button>
        </Card>
      )}

      {academies.length === 0 && (
        <Card>
          <h2 className="text-xl font-semibold">Set up your academy</h2>
          <p>Add your batches and children. Each parent gets a weekly report on WhatsApp.</p>
          <form className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]" onSubmit={(e) => {
            e.preventDefault();
            run(() => call("/academy", { method: "POST", body: form }));
          }}>
            <input id="academy-name" className={field} placeholder="Academy name" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input id="academy-city" className={field} placeholder="City" value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })} />
            <button className={primary} type="submit">Create</button>
          </form>
        </Card>
      )}

      {academies.map((a) => (
        <div key={a.academy_id} className="grid gap-4">
          <h2 className="text-2xl font-bold">{a.name}{a.city ? ` · ${a.city}` : ""}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {a.batches.map((b) => (
              <Link key={b.batch_id} to={`/academy/batch/${b.batch_id}`}
                className="grid gap-1 rounded-2xl border bg-card p-5 hover:border-foreground">
                <span className="text-lg font-semibold">{b.name}</span>
                <span className="text-sm text-muted-foreground">
                  {b.children === 0 ? "No children yet" : b.children === 1 ? "One child" : `${b.children} children`}
                  {b.coach_name ? ` · ${b.coach_name}` : ""}
                </span>
              </Link>
            ))}
          </div>
          <Card>
            <h3 className="font-semibold">Add a batch</h3>
            <form className="flex flex-wrap gap-2" onSubmit={(e) => {
              e.preventDefault();
              run(() => call(`/academy/${a.academy_id}/batches`, { method: "POST", body: batchName[a.academy_id] || {} }));
            }}>
              <input id={`batch-name-${a.academy_id}`} className={`${field} sm:w-56`} placeholder="Batch name, e.g. Saturday batch"
                value={(batchName[a.academy_id] || {}).name || ""}
                onChange={(e) => setBatchName({ ...batchName, [a.academy_id]: { ...(batchName[a.academy_id] || {}), name: e.target.value } })} />
              <input id={`batch-coach-${a.academy_id}`} className={`${field} sm:w-56`} placeholder="Coach's name, e.g. Coach Priya"
                value={(batchName[a.academy_id] || {}).coach_name || ""}
                onChange={(e) => setBatchName({ ...batchName, [a.academy_id]: { ...(batchName[a.academy_id] || {}), coach_name: e.target.value } })} />
              <button className={primary} type="submit">Add batch</button>
            </form>
          </Card>
          {(a.my_role === "owner" || a.my_role === "admin") && (
            <Card>
              <h3 className="font-semibold">Coaches</h3>
              <ul className="grid gap-1 text-sm">
                {a.staff.map((s) => <li key={s.user_id}>{s.name || s.email} · {s.role}</li>)}
              </ul>
              <form className="flex flex-wrap gap-2" onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  const out = await call(`/academy/${a.academy_id}/coaches`, { method: "POST", body: { email: coachEmail[a.academy_id] || "" } });
                  setNote(`${out.name || "The coach"} can now open this academy.`);
                });
              }}>
                <input id={`coach-email-${a.academy_id}`} className={`${field} sm:w-72`} placeholder="Coach's ChessGuru email"
                  value={coachEmail[a.academy_id] || ""}
                  onChange={(e) => setCoachEmail({ ...coachEmail, [a.academy_id]: e.target.value })} />
                <button className={secondary} type="submit">Add coach</button>
              </form>
            </Card>
          )}
        </div>
      ))}
    </Page>
  );
}

// ---------------------------------------------------------------------------
// class games, on the batch page
// ---------------------------------------------------------------------------
function ClassGames({ batchId, rows }) {
  const [state, reload] = useLoad(`/academy/batch/${batchId}/class-games`);
  const ready = rows.filter((r) => r.consent === "given");
  const [white, setWhite] = useState("");
  const [black, setBlack] = useState("");
  const [made, setMade] = useState(null);
  const [error, setError] = useState("");

  const create = async (e) => {
    e.preventDefault();
    setError("");
    try {
      setMade(await call(`/academy/batch/${batchId}/class-games`, {
        method: "POST", body: { white_student_id: white, black_student_id: black },
      }));
      reload();
    } catch (err) {
      setError(err.message);
    }
  };
  const nameOf = (id) => (rows.find((r) => r.student_id === id) || {}).name;

  return (
    <Card>
      <h2 className="text-lg font-semibold">Class games</h2>
      <p>Pair two children. Each gets a link to play the other here. The game counts in their weekly report.</p>
      {ready.length < 2 ? (
        <p className="text-sm text-muted-foreground">Two children with a parent's agreement are needed.</p>
      ) : (
        <form className="flex flex-wrap items-center gap-2" onSubmit={create}>
          <label htmlFor="cg-white" className="sr-only">White</label>
          <select id="cg-white" className={`${field} sm:w-48`} value={white} onChange={(e) => setWhite(e.target.value)}>
            <option value="">White…</option>
            {ready.map((r) => <option key={r.student_id} value={r.student_id}>{r.name}</option>)}
          </select>
          <span>plays</span>
          <label htmlFor="cg-black" className="sr-only">Black</label>
          <select id="cg-black" className={`${field} sm:w-48`} value={black} onChange={(e) => setBlack(e.target.value)}>
            <option value="">Black…</option>
            {ready.map((r) => <option key={r.student_id} value={r.student_id}>{r.name}</option>)}
          </select>
          <button className={primary} type="submit" disabled={!white || !black}>Start game</button>
        </form>
      )}
      {error && <p className="text-red-600">{error}</p>}
      {made && (
        <div className="grid gap-2 rounded-xl border border-emerald-300 p-3">
          <p>Game ready. Open each link on the child's device, or send it to the parent.</p>
          {["white", "black"].map((c) => (
            <div key={c} className="flex flex-wrap items-center gap-2">
              <span className="w-28 font-semibold">{nameOf(c === "white" ? white : black)} ({c})</span>
              <CopyButton text={made.links[c]} />
              <WhatsAppButton href={made.whatsapp[c]} label="Send to parent" />
            </div>
          ))}
        </div>
      )}
      {(state.data?.games || []).length > 0 && (
        <ul className="grid gap-1.5 text-sm">
          {state.data.games.map((g) => (
            <li key={g.class_game_id} className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{g.white_name} – {g.black_name}</span>
              <Pill>{g.status === "playing" ? (g.turn === "white" ? `${g.white_name} to move` : `${g.black_name} to move`) : g.status_words}</Pill>
              {g.status === "playing" && (
                <>
                  <CopyButton text={g.links.white} label={`${g.white_name}'s link`} />
                  <CopyButton text={g.links.black} label={`${g.black_name}'s link`} />
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// /academy/batch/:batchId
// ---------------------------------------------------------------------------
const TREND_TONE = {
  less: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  more: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};
const HOMEWORK_TONE = {
  kept: TREND_TONE.less, held: TREND_TONE.less, not_started: TREND_TONE.more,
};

function Pill({ tone, children }) {
  return <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-[13px] font-bold ${tone || "bg-muted"}`}>{children}</span>;
}

export function AcademyBatch() {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const [state, reload] = useLoad(`/academy/batch/${batchId}`);
  const blank = { display_name: "", lichess_username: "", chesscom_username: "", parent_name: "", parent_phone: "" };
  const [kid, setKid] = useState(blank);
  const [added, setAdded] = useState(null);
  const [error, setError] = useState("");

  if (state.loading) return <Page><p>Loading…</p></Page>;
  if (state.error) return <Page><p className="text-red-600">{state.error}</p></Page>;
  const view = state.data;

  const addKid = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const out = await call(`/academy/batch/${batchId}/students`, { method: "POST", body: kid });
      setAdded({ ...out, name: kid.display_name });
      setKid(blank);
      reload();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Page>
      <header className="grid gap-1">
        <Link to="/academy" className="text-sm text-muted-foreground underline">{view.academy.name}</Link>
        <h1 className="text-3xl font-extrabold">{view.batch.name}</h1>
        <p>{view.summary}</p>
      </header>

      {view.topic && (
        <Card className="border-transparent bg-amber-50 dark:bg-amber-950/40">
          <Eyebrow>Suggested class topic</Eyebrow>
          <h2 className="text-xl font-semibold">{view.topic.headline}</h2>
          <p>{view.topic.line}</p>
        </Card>
      )}

      {view.rows.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border bg-card">
          <table className="w-full min-w-[680px] border-collapse text-[15px]">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="p-3">Child</th><th className="p-3">Needs you?</th>
                <th className="p-3">Habit seen this week</th>
                <th className="p-3">Compared with last week</th><th className="p-3">Games</th>
                <th className="p-3">Homework</th>
              </tr>
            </thead>
            <tbody>
              {view.rows.map((r) => (
                <tr key={r.student_id} className="cursor-pointer border-t hover:bg-muted/50"
                  onClick={() => navigate(`/academy/student/${r.student_id}`)}>
                  <td className="p-3 font-bold underline">{r.name}</td>
                  <td className={`p-3 ${r.needs_you ? "font-bold text-amber-700 dark:text-amber-400" : ""}`}>
                    {r.needs_you ? `Yes. ${r.needs_you}` : "No"}
                  </td>
                  <td className="p-3">{r.consent === "given" ? r.habit : "—"}</td>
                  <td className="p-3">{r.consent === "given" ? <Pill tone={TREND_TONE[r.trend]}>{r.trend_words}</Pill> : "—"}</td>
                  <td className="p-3">{r.consent === "given" ? r.games_words : "—"}</td>
                  <td className="p-3">{r.consent === "given" ? <Pill tone={HOMEWORK_TONE[r.homework]}>{r.homework_words}</Pill> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ClassGames batchId={batchId} rows={view.rows} />

      {added && (
        <Card className="border-emerald-300">
          <h2 className="text-lg font-semibold">{added.name} is added</h2>
          {view.academy.kind === "family" ? (
            <>
              <p>Read and agree on the next page. Nothing is read until you do.</p>
              <a href={added.links.consent} className={primary + " w-fit"}>Read and agree</a>
            </>
          ) : (
            <>
              <p>Send the parent the link to agree. Nothing is read until they do.</p>
              <div className="flex flex-wrap gap-2">
                <WhatsAppButton href={added.whatsapp} label="Send consent link on WhatsApp" />
                <CopyButton text={added.links.consent} />
              </div>
            </>
          )}
        </Card>
      )}

      <Card>
        <h2 className="text-lg font-semibold">Add a child</h2>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={addKid}>
          <input id="kid-name" className={field} placeholder="Child's first name" value={kid.display_name}
            onChange={(e) => setKid({ ...kid, display_name: e.target.value })} />
          <input id="kid-lichess" className={field} placeholder="Lichess username (if any)" value={kid.lichess_username}
            onChange={(e) => setKid({ ...kid, lichess_username: e.target.value })} />
          <input id="kid-chesscom" className={field} placeholder="Chess.com username (if any)" value={kid.chesscom_username}
            onChange={(e) => setKid({ ...kid, chesscom_username: e.target.value })} />
          <input id="kid-parent" className={field} placeholder="Parent's name" value={kid.parent_name}
            onChange={(e) => setKid({ ...kid, parent_name: e.target.value })} />
          <input id="kid-phone" className={field} placeholder="Parent's WhatsApp number" inputMode="tel" value={kid.parent_phone}
            onChange={(e) => setKid({ ...kid, parent_phone: e.target.value })} />
          <div className="flex items-center"><button className={primary} type="submit">Add child</button></div>
        </form>
        {error && <p className="text-red-600">{error}</p>}
      </Card>
    </Page>
  );
}

// ---------------------------------------------------------------------------
// /academy/student/:studentId
// ---------------------------------------------------------------------------
export function AcademyStudent() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const [state, reload] = useLoad(`/academy/student/${studentId}`);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [confirmRemove, setConfirmRemove] = useState(false);

  if (state.loading) return <Page><p>Loading…</p></Page>;
  if (state.error) return <Page><p className="text-red-600">{state.error}</p></Page>;
  const view = state.data;
  const s = view.student;
  const consented = s.consent?.status === "given";

  const act = async (label, fn) => {
    setBusy(label); setError("");
    try { await fn(); } catch (err) { setError(err.message); } finally { setBusy(""); }
  };

  return (
    <Page>
      <header className="grid gap-1">
        <Link to={`/academy/batch/${view.batch.batch_id}`} className="text-sm text-muted-foreground underline">
          {view.academy.name} · {view.batch.name}
        </Link>
        <h1 className="text-3xl font-extrabold">{s.display_name}</h1>
        <p className="text-sm text-muted-foreground">
          {[s.lichess_username && `Lichess: ${s.lichess_username}`, s.chesscom_username && `Chess.com: ${s.chesscom_username}`].filter(Boolean).join(" · ") || "No online account added"}
          {s.parent_name ? ` · Parent: ${s.parent_name}` : ""}
        </p>
      </header>
      {error && <p className="text-red-600">{error}</p>}

      {!consented ? (
        <Card>
          <h2 className="text-lg font-semibold">Waiting for the parent to agree</h2>
          <p>Nothing about {s.display_name} is read until the parent agrees on the consent link.</p>
          <div className="flex flex-wrap gap-2">
            {view.academy.kind === "family" ? (
              <a href={view.links.consent} className={primary}>Read and agree</a>
            ) : (
              <>
                <WhatsAppButton href={view.whatsapp_consent} label="Send consent link on WhatsApp" />
                <CopyButton text={view.links.consent} />
              </>
            )}
          </div>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)]">
          <div className="grid content-start gap-4">
            {view.first_steps && (
              <Card>
                <Eyebrow>First steps classes</Eyebrow>
                {!view.first_steps.placed ? (
                  <p>{s.display_name} hasn't started yet. The first visit asks three quick questions to find the right class.</p>
                ) : view.first_steps.all_done ? (
                  <p>{s.display_name} has finished every rules class and is ready for real games.</p>
                ) : (
                  <p>Next class: <b>{view.first_steps.next?.title}</b></p>
                )}
                {view.first_steps.placed && (
                  <p className="text-sm text-muted-foreground" data-testid="first-steps-classes">
                    {view.first_steps.classes.map((c) => `${c.passed || c.skipped ? "✔" : "○"} ${c.title}`).join("  ·  ")}
                  </p>
                )}
                {view.first_steps.last && <p className="text-sm">Last class: {view.first_steps.last.parent}</p>}
                {view.first_steps.notes?.length > 0 && (
                  <p className="text-sm">What the taps show: {s.display_name} {view.first_steps.notes.join("; ")}.</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {view.academy.kind === "family" ? (
                    <a href={view.links.class} className={primary}>Open the class</a>
                  ) : (
                    <WhatsAppButton href={view.whatsapp_class} label="Send class link on WhatsApp" />
                  )}
                  <CopyButton text={view.links.class} label="Copy class link" />
                </div>
              </Card>
            )}
            <Card>
              <Eyebrow>This week</Eyebrow>
              <p className="text-lg">{view.row.habit}</p>
              <p className="text-sm text-muted-foreground">
                Compared with last week: {view.row.trend_words} · Homework: {view.row.homework_words}
              </p>
              <div className="flex flex-wrap gap-2">
                <button type="button" className={secondary} disabled={!!busy}
                  onClick={() => act("refresh", async () => { await call(`/academy/student/${studentId}/refresh`, { method: "POST" }); await reload(); })}>
                  {busy === "refresh" ? "Reading games…" : "Refresh from games"}
                </button>
              </div>
              {!view.week_built_at && (
                <p className="text-sm">
                  {s.lichess_username || s.chesscom_username
                    ? "The first games are being imported. Press Refresh in a few minutes."
                    : `This week fills in when ${s.display_name} finishes a lesson or plays a class game.`}
                </p>
              )}
            </Card>
            {(view.preview?.sections || []).some((sec) => sec.kind === "good") && (
              <Card>
                <Eyebrow>A good moment</Eyebrow>
                {(view.preview.sections.find((sec) => sec.kind === "good") || {}).confirmed ? (
                  <p>You confirmed this move. The report says so, in your name.</p>
                ) : (
                  <>
                    <p>Does this move show {s.display_name} understands the idea? If you confirm it, the report says so in your name.</p>
                    <button type="button" className={secondary} disabled={!!busy}
                      onClick={() => act("confirm", async () => { await call(`/academy/student/${studentId}/confirm-good-moment`, { method: "POST", body: {} }); await reload(); })}>
                      Yes, it shows they understand
                    </button>
                  </>
                )}
              </Card>
            )}
            <Card>
              <Eyebrow>Your note to the parent</Eyebrow>
              <textarea id="coach-note" rows={4} className={field} value={note} maxLength={400}
                placeholder={`One or two sentences about ${s.display_name}. Words only.`}
                onChange={(e) => setNote(e.target.value)} />
              <div className="flex flex-wrap gap-2">
                <button type="button" className={primary} disabled={!!busy || !view.preview || !!view.preview?.blocked}
                  onClick={() => act("approve", async () => {
                    setSent(await call(`/academy/student/${studentId}/report`, { method: "POST", body: { coach_note: note } }));
                    await reload();
                  })}>
                  Approve this week's report
                </button>
              </div>
              {view.preview?.blocked && <p className="text-sm">{view.preview.blocked}</p>}
              {sent && (
                <div className="grid gap-2 rounded-xl border border-emerald-300 p-3">
                  <p>Approved. The parent's link now shows this report.</p>
                  <div className="flex flex-wrap gap-2">
                    <WhatsAppButton href={sent.whatsapp}
                      onClick={() => { call(`/academy/student/${studentId}/sent`, { method: "POST" }).catch(() => {}); }} />
                    <CopyButton text={sent.link} />
                  </div>
                </div>
              )}
              {view.last_report && !sent && (
                <p className="text-sm text-muted-foreground">
                  Last report approved by {view.last_report.approved_by_name}
                  {view.last_report.first_opened_at ? ". The parent has opened it." : ". Not opened yet."}
                </p>
              )}
            </Card>
            <Card>
              <Eyebrow>Links for the family</Eyebrow>
              <div className="flex flex-wrap gap-2">
                <CopyButton text={view.links.report} label="Copy report link" />
                {(view.preview?.sections || []).some((sec) => sec.kind === "homework") && (
                  <CopyButton text={view.links.homework} label="Copy homework link" />
                )}
              </div>
              {!confirmRemove ? (
                <button type="button" className="w-fit text-sm text-red-700 underline" onClick={() => setConfirmRemove(true)}>
                  Remove {s.display_name} and delete their data
                </button>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <span>This cannot be undone.</span>
                  <button type="button" disabled={!!busy}
                    className="rounded-full bg-red-600 px-4 py-2 font-semibold text-white disabled:opacity-60"
                    onClick={() => act("remove", async () => {
                      await call(`/academy/student/${studentId}`, { method: "DELETE" });
                      navigate(`/academy/batch/${view.batch.batch_id}`);
                    })}>
                    {busy === "remove" ? "Removing…" : "Remove"}
                  </button>
                  <button type="button" className={secondary} onClick={() => setConfirmRemove(false)}>Keep</button>
                </div>
              )}
            </Card>
          </div>
          <div className="grid content-start gap-2">
            <Eyebrow>What the parent will see</Eyebrow>
            {view.preview ? <ParentReport report={view.preview} /> : <p>Nothing to report yet this week.</p>}
          </div>
        </div>
      )}
    </Page>
  );
}
