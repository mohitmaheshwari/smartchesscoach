/**
 * AdminLlmCost - what the LLM is costing, by day, surface and user.
 *
 * Mohit asked for the money side. The honest starting point was that nothing
 * was recorded: both provider calls in llm_service received a `usage` object
 * from the API and returned only the message text, so there was no collection,
 * no counter, and no way to recover a single past call.
 *
 * Two things this page refuses to do, because both would make it look like it
 * was working while understating the bill.
 *
 * It never shows an unpriced model as $0. `gpt-6-luna` has no published rate
 * in this repo; until one is filled into backend/data/llm_prices.json its
 * tokens are shown and its cost reads "price not set", and the headline total
 * carries a warning that it excludes those models.
 *
 * It never implies the figures cover all time. The recorder shipped on a date
 * and the page states it, so an empty week reads as "not recorded" rather than
 * "nothing spent".
 *
 * Cost is computed on the server from the live price table at read time, so
 * correcting a price fixes the whole history rather than only new rows.
 */
import { useCallback, useEffect, useState } from "react";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw, AlertTriangle } from "lucide-react";

const WINDOWS = [7, 30, 90];

const money = (v) =>
  v === null || v === undefined ? null : `$${Number(v).toFixed(2)}`;

const tokens = (v) => {
  const n = Number(v || 0);
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
};

/** A cost cell that distinguishes "nothing spent" from "no rate set". */
function Cost({ row }) {
  const unpriced = (row.unpriced_models || []).length > 0;
  return (
    <span className="tabular-nums">
      {money(row.cost_usd) ?? "—"}
      {unpriced && (
        <span
          className="ml-1 text-amber-600 dark:text-amber-400"
          title={`No price set for: ${row.unpriced_models.join(", ")}`}
        >
          +?
        </span>
      )}
    </span>
  );
}

function Table({ title, rows, label, onPick }) {
  if (!rows?.length) {
    return (
      <section className="mb-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-2">
          {title}
        </h2>
        <p className="text-sm opacity-60">Nothing recorded in this window.</p>
      </section>
    );
  }
  return (
    <section className="mb-8">
      <h2 className="text-sm font-semibold uppercase tracking-wide mb-2">
        {title}
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left opacity-60">
            <tr>
              <th className="py-1 pr-4">{label}</th>
              <th className="py-1 pr-4 text-right">Calls</th>
              <th className="py-1 pr-4 text-right">In</th>
              <th className="py-1 pr-4 text-right">Cached</th>
              <th className="py-1 pr-4 text-right">Out</th>
              <th className="py-1 text-right">Cost</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.key)} className="border-t border-black/5 dark:border-white/10">
                <td className="py-1 pr-4">
                  {onPick ? (
                    <button
                      className="underline underline-offset-2"
                      onClick={() => onPick(r.key)}
                    >
                      {r.key === null ? "(unattributed)" : String(r.key)}
                    </button>
                  ) : (
                    <>{r.key === null ? "(unattributed)" : String(r.key)}</>
                  )}
                </td>
                <td className="py-1 pr-4 text-right tabular-nums">{r.calls}</td>
                <td className="py-1 pr-4 text-right tabular-nums">
                  {tokens(r.input_tokens)}
                </td>
                <td className="py-1 pr-4 text-right tabular-nums opacity-60">
                  {tokens(r.cached_input_tokens)}
                </td>
                <td className="py-1 pr-4 text-right tabular-nums">
                  {tokens(r.output_tokens)}
                </td>
                <td className="py-1 text-right">
                  <Cost row={r} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function AdminLlmCost() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [who, setWho] = useState(null);
  const [whoData, setWhoData] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(`${API}/admin/llm-cost/summary?days=${days}`, {
        credentials: "include",
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const pickUser = useCallback(async (uid) => {
    setWho(uid);
    setWhoData(null);
    try {
      const r = await fetch(
        `${API}/admin/llm-cost/user/${encodeURIComponent(uid)}?days=${days}`,
        { credentials: "include" },
      );
      if (r.ok) setWhoData(await r.json());
    } catch {
      /* the drill-down is a nicety; the summary above still stands */
    }
  }, [days]);

  return (
    <Layout>
      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
          <h1 className="text-xl font-semibold">LLM cost</h1>
          <div className="flex items-center gap-2">
            {WINDOWS.map((d) => (
              <Button
                key={d}
                variant={d === days ? "default" : "outline"}
                size="sm"
                onClick={() => setDays(d)}
              >
                {d}d
              </Button>
            ))}
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {loading && (
          <p className="flex items-center gap-2 text-sm opacity-70">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </p>
        )}
        {err && <p className="text-sm text-red-600">Could not load: {err}</p>}

        {data && (
          <>
            <div className="rounded-lg border border-black/10 dark:border-white/15 p-4 mb-4">
              <div className="text-3xl font-semibold tabular-nums">
                {money(data.total_cost_usd)}
                {data.total_cost_inr !== null &&
                  data.total_cost_inr !== undefined && (
                    <span className="ml-3 text-xl opacity-70">
                      ₹{Number(data.total_cost_inr).toFixed(2)}
                    </span>
                  )}
              </div>
              <div className="text-sm opacity-70">
                {data.total_calls} calls in the last {data.window_days} days
              </div>
              {data.inr_incomplete && (
                <p className="mt-2 text-sm text-amber-700 dark:text-amber-400">
                  No rupee total: a day with spend has no exchange rate yet.
                  The per-day rows below show which. A part-total shown as
                  the total would be worse than none.
                </p>
              )}
              {data.cost_excludes_unpriced_models && (
                <p className="mt-3 flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>
                    This total <strong>excludes</strong>{" "}
                    {data.models_without_a_price.join(", ")} — no price is set,
                    so those calls are counted in tokens only. Add the rate to{" "}
                    <code>backend/data/llm_prices.json</code> and this page will
                    reprice the whole history.
                  </span>
                </p>
              )}
              <p className="mt-2 text-sm opacity-60">
                {data.recording_since
                  ? `Recording since ${new Date(
                      data.recording_since,
                    ).toLocaleString()}. Calls made before then were never logged.`
                  : "Nothing recorded yet. Until an LLM call runs on this build, there is no spend to show — this is not a zero bill."}
              </p>
            </div>

            <section className="mb-8">
              <h2 className="text-sm font-semibold uppercase tracking-wide mb-2">
                By day
              </h2>
              {!data.by_day?.length ? (
                <p className="text-sm opacity-60">
                  Nothing recorded in this window.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left opacity-60">
                      <tr>
                        <th className="py-1 pr-4">Day</th>
                        <th className="py-1 pr-4 text-right">Calls</th>
                        <th className="py-1 pr-4 text-right">In</th>
                        <th className="py-1 pr-4 text-right">Out</th>
                        <th className="py-1 pr-4 text-right">USD</th>
                        <th className="py-1 pr-4 text-right">Rate</th>
                        <th className="py-1 text-right">INR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.by_day.map((r) => (
                        <tr
                          key={r.key}
                          className="border-t border-black/5 dark:border-white/10"
                        >
                          <td className="py-1 pr-4">{r.key}</td>
                          <td className="py-1 pr-4 text-right tabular-nums">
                            {r.calls}
                          </td>
                          <td className="py-1 pr-4 text-right tabular-nums">
                            {tokens(r.input_tokens)}
                          </td>
                          <td className="py-1 pr-4 text-right tabular-nums">
                            {tokens(r.output_tokens)}
                          </td>
                          <td className="py-1 pr-4 text-right">
                            <Cost row={r} />
                          </td>
                          <td
                            className="py-1 pr-4 text-right tabular-nums opacity-60"
                            title={
                              r.usd_inr_date && r.usd_inr_date !== r.key
                                ? `No rate published on ${r.key} (weekend or holiday); using ${r.usd_inr_date}`
                                : undefined
                            }
                          >
                            {r.usd_inr
                              ? `${Number(r.usd_inr).toFixed(2)}${
                                  r.usd_inr_date && r.usd_inr_date !== r.key
                                    ? "*"
                                    : ""
                                }`
                              : "—"}
                          </td>
                          <td className="py-1 text-right tabular-nums">
                            {r.cost_inr === null || r.cost_inr === undefined
                              ? "—"
                              : `₹${Number(r.cost_inr).toFixed(2)}`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 text-xs opacity-60">
                    Each day is converted at that day&apos;s published rate,
                    so the rupee total is the sum of the days and not the
                    dollar total times one number. An asterisk means no rate
                    was published that day — a weekend or holiday — so the
                    last published rate before it was used. Source:{" "}
                    {data.fx_source}.
                  </p>
                </div>
              )}
            </section>
            <Table title="By surface" rows={data.by_surface} label="Surface" />
            <Table title="By model" rows={data.by_model} label="Model" />
            <Table
              title="Top users"
              rows={data.top_users}
              label="User"
              onPick={pickUser}
            />

            {who && (
              <section className="rounded-lg border border-black/10 dark:border-white/15 p-4">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-sm font-semibold">{who}</h2>
                  <Button variant="outline" size="sm" onClick={() => setWho(null)}>
                    Close
                  </Button>
                </div>
                {!whoData && (
                  <p className="text-sm opacity-70">Loading…</p>
                )}
                {whoData && (
                  <>
                    <p className="text-sm mb-3">
                      {money(whoData.total_cost_usd)} over{" "}
                      {whoData.total_calls} calls in {whoData.window_days} days
                    </p>
                    <Table
                      title="Their surfaces"
                      rows={whoData.by_surface}
                      label="Surface"
                    />
                  </>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </Layout>
  );
}
