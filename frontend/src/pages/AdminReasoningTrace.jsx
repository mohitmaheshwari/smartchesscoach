/**
 * AdminReasoningTrace — the reasoning engine thinking out loud.
 *
 * Mohit, 2026-10-21: "I would like to create a page on admin chessguru, where
 * it will put all the samples thre, it used and the caption it generated and
 * teh steps it took".
 *
 * Two tabs, for the two halves of that ask:
 *
 *   A move, step by step   — one faulted move: the board, the sentence a
 *                            player would read, the eight steps, and EVERY
 *                            question the engine asked including the ones
 *                            that had nothing to say and the ones whose
 *                            answers were thrown out, with the board reason
 *                            for each.
 *   Where each question     — the positions that first showed each pattern,
 *   came from                 how far it reaches, and the defects it shipped
 *                             with.
 *
 * The one rule, from docs/reasoning_trace_admin_scope.md: this file holds NO
 * copy of the procedure. The step names, their order and their verdicts all
 * arrive from the API, which serialises the engine's own trace. A page that
 * keeps its own list of the steps is right the day it is written and silently
 * wrong the first time a question is added — and a page cannot fail a test for
 * being out of date.
 *
 * Read-only. /admin/detector-review and /admin/reason-judge record verdicts;
 * nothing here changes what a player sees.
 */
import { useCallback, useEffect, useState } from "react";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, RefreshCw, AlertTriangle, Check, Minus } from "lucide-react";

const TIER_NAME = { 3: "CAUSE", 2: "EVIDENCE", 1: "SYMPTOM" };
const TIER_STYLE = {
  3: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  2: "bg-sky-500/10 text-sky-300 border-sky-500/30",
  1: "bg-amber-500/10 text-amber-300 border-amber-500/30",
};
const VERDICT_STYLE = {
  kept: "text-emerald-300",
  dropped: "text-rose-300",
  "no answer": "text-slate-500",
};

const Pill = ({ children, className = "" }) => (
  <span className={`inline-block rounded border px-2 py-0.5 text-[11px] font-medium ${className}`}>
    {children}
  </span>
);

const Panel = ({ title, children, right = null }) => (
  <section className="rounded-lg border border-slate-800 bg-slate-900/40">
    <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
      <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {title}
      </h2>
      {right}
    </header>
    <div className="p-4">{children}</div>
  </section>
);

/** The eight steps, exactly as the engine reported them. */
const Steps = ({ steps }) => (
  <ol className="space-y-1">
    {steps.map((s) => (
      <li
        key={s.step}
        className="grid grid-cols-[1.4rem_minmax(0,1fr)_auto] items-start gap-3 rounded px-2 py-1.5 text-sm odd:bg-slate-900/40"
      >
        <span className="pt-0.5 font-mono text-xs text-slate-500">{s.step}</span>
        <span className="min-w-0">
          <span className={s.ran ? "text-slate-200" : "text-slate-500"}>
            {s.name}
          </span>
          <span className="block text-xs text-slate-500">
            {s.note}
            {s.by ? <span className="ml-2 font-mono text-slate-600">{s.by}</span> : null}
          </span>
        </span>
        <span className="pt-0.5">
          {s.ran ? (
            <Check className="h-4 w-4 text-emerald-400" aria-label="ran" />
          ) : (
            <Minus className="h-4 w-4 text-slate-600" aria-label="not reached" />
          )}
        </span>
      </li>
    ))}
  </ol>
);

/**
 * Every question asked. The dropped rows are the point of this page: a card
 * shows the one sentence that won, and nothing anywhere shows the five that
 * lost or why.
 */
const Asked = ({ asked }) => (
  <div className="space-y-1">
    {asked.map((a, i) => (
      <div
        key={`${a.concept}-${i}`}
        className="grid grid-cols-[minmax(0,13rem)_5.5rem_4rem_minmax(0,1fr)] items-start gap-3 rounded px-2 py-1.5 text-sm odd:bg-slate-900/40"
      >
        <span className="min-w-0 truncate font-mono text-xs text-slate-300">
          {a.concept}
        </span>
        <Pill className={TIER_STYLE[a.tier] || ""}>{TIER_NAME[a.tier] || a.tier}</Pill>
        <span className={`text-xs font-medium ${VERDICT_STYLE[a.verdict] || ""}`}>
          {a.verdict}
        </span>
        <span className="min-w-0 text-xs text-slate-400">
          {a.subject ? (
            <span className="mr-2 font-mono text-slate-300">{a.subject}</span>
          ) : null}
          {a.reason}
        </span>
      </div>
    ))}
  </div>
);

const MoveTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [raw, setRaw] = useState(false);
  const [form, setForm] = useState({ fen: "", played: "", best: "" });

  const load = useCallback(async (params = "") => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/admin/reasoning-trace${params}`, {
        credentials: "include",
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.detail || `HTTP ${res.status}`);
      setData(body);
    } catch (e) {
      setError(String(e.message || e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submitFen = (e) => {
    e.preventDefault();
    if (!form.fen.trim() || !form.played.trim()) return;
    const q = new URLSearchParams({
      fen: form.fen.trim(),
      played: form.played.trim(),
    });
    if (form.best.trim()) q.set("best", form.best.trim());
    load(`?${q.toString()}`);
  };

  const pos = data?.position;
  const where = data?.where;
  const out = data?.outcome;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => load()} disabled={loading} size="sm">
          {loading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Random faulted move
        </Button>
        <form onSubmit={submitFen} className="flex flex-wrap items-center gap-2">
          <input
            value={form.fen}
            onChange={(e) => setForm({ ...form, fen: e.target.value })}
            placeholder="paste a FEN"
            className="w-[22rem] rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-xs text-slate-200"
          />
          <input
            value={form.played}
            onChange={(e) => setForm({ ...form, played: e.target.value })}
            placeholder="played"
            className="w-20 rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-xs text-slate-200"
          />
          <input
            value={form.best}
            onChange={(e) => setForm({ ...form, best: e.target.value })}
            placeholder="best"
            className="w-20 rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-xs text-slate-200"
          />
          <Button type="submit" variant="secondary" size="sm" disabled={loading}>
            Trace it
          </Button>
        </form>
      </div>

      {error ? (
        <div className="flex items-start gap-2 rounded border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {pos ? (
        <>
          <p className="text-xs text-slate-400">
            {where?.source === "corpus" ? (
              <>
                game <span className="font-mono text-slate-300">{where.game_id}</span>{" "}
                · ply {where.ply} · {where.side} ·{" "}
              </>
            ) : (
              <>pasted position · </>
            )}
            {pos.side_to_move} played{" "}
            <span className="font-mono text-rose-300">{pos.played_san}</span>
            {pos.best_san ? (
              <>
                {" "}· engine wanted{" "}
                <span className="font-mono text-emerald-300">{pos.best_san}</span>
              </>
            ) : null}
            {pos.cp_loss ? <> · {pos.cp_loss}cp</> : null}
          </p>

          <div className="grid gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="w-full max-w-[340px]">
                <LichessBoard
                  fen={pos.fen}
                  orientation={pos.side_to_move === "black" ? "black" : "white"}
                  arrows={pos.arrows}
                  viewOnly
                  interactive={false}
                />
              </div>
              {pos.pv_played?.length ? (
                <p className="text-xs text-slate-500">
                  <span className="text-slate-400">after {pos.played_san}:</span>{" "}
                  <span className="font-mono">{pos.pv_played.join(" ")}</span>
                </p>
              ) : null}
            </div>

            <div className="min-w-0 space-y-4">
              <Panel
                title="What the player would read"
                right={
                  out?.primary_concept ? (
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-slate-400">
                        {out.primary_concept}
                      </span>
                      <Pill className={TIER_STYLE[out.primary_tier] || ""}>
                        {TIER_NAME[out.primary_tier]}
                      </Pill>
                      <Pill className="border-slate-700 text-slate-400">
                        {out.confidence}
                      </Pill>
                    </span>
                  ) : null
                }
              >
                {data.caption?.available ? (
                  <p className="text-slate-100">{data.caption.text}</p>
                ) : (
                  <div className="space-y-2">
                    <p className="text-sm text-amber-200/90">
                      {data.caption?.why}
                    </p>
                    {Object.keys(data.caption?.slots || {}).length ? (
                      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
                        {Object.entries(data.caption.slots).map(([k, v]) => (
                          <div key={k} className="contents">
                            <dt className="font-mono text-slate-500">{k}</dt>
                            <dd className="min-w-0 break-words text-slate-300">
                              {typeof v === "object" ? JSON.stringify(v) : String(v)}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    ) : (
                      <p className="text-xs text-slate-500">
                        Nothing survived, so there is nothing to build a sentence
                        from. That is the engine refusing rather than failing.
                      </p>
                    )}
                  </div>
                )}
              </Panel>

              <Panel title="The eight steps">
                <Steps steps={data.steps || []} />
              </Panel>

              <Panel
                title="Every question asked, and what became of it"
                right={
                  <span className="text-[11px] text-slate-500">
                    {(data.asked || []).filter((a) => a.verdict === "kept").length} kept
                    {" · "}
                    {(data.asked || []).filter((a) => a.verdict === "dropped").length} dropped
                    {" · "}
                    {(data.asked || []).filter((a) => a.verdict === "no answer").length} silent
                  </span>
                }
              >
                <Asked asked={data.asked || []} />
              </Panel>

              <button
                type="button"
                onClick={() => setRaw((r) => !r)}
                className="text-xs text-slate-500 underline hover:text-slate-300"
              >
                {raw ? "hide" : "show"} the raw trace
              </button>
              {raw ? (
                <pre className="max-h-96 overflow-auto rounded border border-slate-800 bg-slate-950 p-3 text-[11px] text-slate-400">
                  {JSON.stringify(data, null, 1)}
                </pre>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};

const SampleBoard = ({ s }) => (
  <div className="space-y-2">
    {s.fen ? (
      <div className="w-[210px]">
        <LichessBoard
          fen={s.fen}
          orientation={s.fen.split(" ")[1] === "b" ? "black" : "white"}
          arrows={s.arrows || []}
          viewOnly
          interactive={false}
        />
      </div>
    ) : (
      <div className="flex h-[210px] w-[210px] items-center justify-center rounded border border-dashed border-slate-700 p-3 text-center text-[11px] text-slate-500">
        the position was not kept, so there is no board here
      </div>
    )}
    <p className="w-[210px] text-[11px] text-slate-400">
      <span className="font-mono text-rose-300">{s.played}</span>
      {s.best ? (
        <>
          {" "}· best <span className="font-mono text-emerald-300">{s.best}</span>
        </>
      ) : null}
      {s.cp_loss ? <> · {s.cp_loss}cp</> : null}
    </p>
    <p className="w-[210px] text-[11px] leading-snug text-slate-500">{s.note}</p>
  </div>
);

const ProvenanceTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/admin/reasoning-provenance`, {
          credentials: "include",
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body?.detail || `HTTP ${res.status}`);
        setData(body);
      } catch (e) {
        setError(String(e.message || e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin" /> loading
      </p>
    );
  }
  if (error) {
    return (
      <div className="flex items-start gap-2 rounded border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <p className="text-xs text-slate-500">
        In the order the engine asks them. The procedure itself is written up in{" "}
        <span className="font-mono text-slate-400">{data.doc}</span>.
      </p>

      {(data.questions || []).map((q) => (
        <article
          key={q.concept}
          className="rounded-lg border border-slate-800 bg-slate-900/40 p-4"
        >
          <header className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h3 className="text-base font-semibold text-slate-100">{q.title}</h3>
            <span className="font-mono text-[11px] text-slate-500">{q.concept}</span>
            <Pill className={TIER_STYLE[q.tier] || ""}>{TIER_NAME[q.tier]}</Pill>
            {q.shipped ? (
              <span className="text-[11px] text-slate-500">shipped {q.shipped}</span>
            ) : null}
            {q.names_material ? (
              <Pill className="border-slate-700 text-slate-400">names material</Pill>
            ) : null}
          </header>

          {q.missing ? (
            <p className="flex items-center gap-2 text-sm text-amber-200">
              <AlertTriangle className="h-4 w-4" />
              No provenance recorded for this question. A test is meant to stop
              this — if you are seeing it, the test is not running.
            </p>
          ) : (
            <div className="space-y-4">
              {q.found_by?.length ? (
                <div>
                  <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    How it was found
                  </h4>
                  {q.found_by.map((line, i) =>
                    line ? (
                      <p key={i} className="text-sm leading-relaxed text-slate-300">
                        {line}
                      </p>
                    ) : (
                      <div key={i} className="h-2" />
                    )
                  )}
                </div>
              ) : null}

              {q.discovery_samples?.length ? (
                <div>
                  <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    The positions that showed it
                  </h4>
                  <div className="flex flex-wrap gap-4">
                    {q.discovery_samples.map((s, i) => (
                      <SampleBoard key={i} s={s} />
                    ))}
                  </div>
                </div>
              ) : null}

              {q.reach?.length ? (
                <div>
                  <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    How far it reaches
                  </h4>
                  <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
                    {q.reach.map((r, i) => (
                      <div key={i} className="contents">
                        <dt className="min-w-0 text-slate-400">{r.label}</dt>
                        <dd className="font-mono tabular-nums text-slate-200">{r.n}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ) : null}

              {q.defect ? (
                <div className="rounded border border-amber-500/25 bg-amber-500/5 p-3">
                  <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-amber-300/80">
                    What it got wrong
                  </h4>
                  <p className="text-sm text-slate-200">{q.defect.what}</p>
                  {q.defect.how_found ? (
                    <p className="mt-2 text-xs leading-relaxed text-slate-400">
                      <span className="text-slate-500">found by: </span>
                      {q.defect.how_found}
                    </p>
                  ) : null}
                  {q.defect.fix ? (
                    <p className="mt-2 text-xs leading-relaxed text-slate-400">
                      <span className="text-slate-500">fix: </span>
                      {q.defect.fix}
                    </p>
                  ) : null}
                  {q.defect_samples?.length ? (
                    <div className="mt-3 flex flex-wrap gap-4">
                      {q.defect_samples.map((s, i) => (
                        <SampleBoard key={i} s={s} />
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {q.notes?.length ? (
                <div className="border-t border-slate-800 pt-3">
                  {q.notes.map((line, i) =>
                    line ? (
                      <p key={i} className="text-xs leading-relaxed text-slate-500">
                        {line}
                      </p>
                    ) : (
                      <div key={i} className="h-2" />
                    )
                  )}
                </div>
              ) : null}
            </div>
          )}
        </article>
      ))}
    </div>
  );
};

export default function AdminReasoningTrace() {
  const [tab, setTab] = useState("move");

  return (
    <Layout>
      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        <header>
          <h1 className="text-xl font-semibold text-slate-100">Reasoning Trace</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            The engine's own account of how it decides why a move was a mistake.
            Every step below is reported by the engine as it works, so this page
            cannot show a step nothing runs, or miss one that does.
          </p>
        </header>

        <nav className="flex gap-1 border-b border-slate-800">
          {[
            ["move", "A move, step by step"],
            ["provenance", "Where each question came from"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                tab === key
                  ? "border-emerald-400 text-slate-100"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>

        {tab === "move" ? <MoveTab /> : <ProvenanceTab />}
      </div>
    </Layout>
  );
}
