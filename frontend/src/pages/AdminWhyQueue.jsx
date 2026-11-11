/**
 * AdminWhyQueue - every position the Why button sent to be studied.
 *
 * Mohit 2026-11-11: "a page on admin to show up positions that have been set
 * up for queue; if Claude has processed them then Claude's caption there, if
 * not processed then To Be processed, gameId and the position with board."
 * Scope: docs/why_queue_admin_page_scope.md.
 *
 * Read-only. Agree / Disagree stays on /admin/geometry-gaps (Claude tab),
 * which this page links to. The board is the position BEFORE the move, seen
 * from the side of whoever asked: red arrow the move played, green the move
 * the engine prefers.
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw } from "lucide-react";

const STATUS_STYLE = {
  queued: "bg-amber-50 text-amber-800 border-amber-200",
  running: "bg-amber-50 text-amber-800 border-amber-200",
  held_for_review: "bg-sky-50 text-sky-800 border-sky-200",
  held: "bg-red-50 text-red-800 border-red-200",
  published: "bg-emerald-50 text-emerald-800 border-emerald-200",
  rejected: "bg-gray-100 text-gray-700 border-gray-200",
  no_lesson: "bg-gray-100 text-gray-700 border-gray-200",
  done: "bg-gray-100 text-gray-700 border-gray-200",
  failed: "bg-red-50 text-red-800 border-red-200",
};

const when = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? String(iso)
    : d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};

/** "6.e5" / "18...Rf7" from the side to move and the first game's move number. */
const moveLabel = (p) => {
  const n = p.games?.[0]?.move_number;
  if (!n) return p.played_san;
  return p.side_to_move === "white" ? `${n}.${p.played_san}` : `${n}...${p.played_san}`;
};

function PositionRow({ p }) {
  // Seen from the asker's side: they moved when side is "user", so the board
  // faces the side to move; for an opponent's move it faces the other way.
  const asker =
    p.side === "opponent"
      ? (p.side_to_move === "white" ? "black" : "white")
      : p.side_to_move;
  const arrows = [];
  if (p.played_squares) arrows.push([p.played_squares.from, p.played_squares.to, "red"]);
  if (p.better_squares) arrows.push([p.better_squares.from, p.better_squares.to, "green"]);

  return (
    <div
      className="rounded-xl border border-gray-200 bg-white p-4 flex flex-col sm:flex-row gap-4"
      data-testid="why-queue-row"
    >
      <div className="w-full sm:w-60 shrink-0">
        <LichessBoard fen={p.fen_before} orientation={asker} viewOnly arrows={arrows} />
      </div>
      <div className="min-w-0 flex-1 space-y-2 text-sm text-gray-800">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-base font-semibold text-gray-900">{moveLabel(p)}</span>
          <span className="text-gray-500">
            {p.side === "opponent" ? "opponent's move" : "player's move"}
          </span>
          <span
            className={`ml-auto rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLE[p.status] || STATUS_STYLE.done}`}
            data-testid="why-queue-status"
          >
            {p.status_words}
          </span>
        </div>

        <div className="text-gray-600">
          {p.better_san && (
            <>Engine prefers <span className="font-mono font-semibold text-emerald-700">{p.better_san}</span></>
          )}
          {p.stored_class && <> · graded {p.stored_class}</>}
          {" · "}asked {p.times_asked}× · last {when(p.last_asked_at)}
        </div>

        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {(p.games || []).map((g) => (
            <Link
              key={`${g.game_id}-${g.move_number}`}
              to={`/game/${g.game_id}`}
              className="font-mono text-xs text-sky-700 underline underline-offset-2"
            >
              {g.game_id} · move {g.move_number}
            </Link>
          ))}
        </div>

        {p.processed ? (
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-1">
            <div className="text-[11px] uppercase tracking-wide text-gray-500 font-semibold">Claude</div>
            <p className="text-[15px] leading-relaxed text-gray-900" data-testid="why-queue-claude">
              {p.claude_text || p.no_lesson_why || "No text was saved for this study."}
            </p>
            <div className="text-xs text-gray-500">
              {p.gate_passed === true && "gate passed"}
              {p.gate_passed === false && `gate failed: ${p.gate_failures?.[0] || "?"}`}
              {p.cost_usd != null && ` · $${Number(p.cost_usd).toFixed(2)}`}
              {p.model && ` · ${p.model}`}
              {p.studied_at && ` · studied ${when(p.studied_at)}`}
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-amber-300 bg-amber-50/60 p-3 text-amber-900" data-testid="why-queue-pending">
            To be processed. The study runs on Mohit's PC every 15 minutes.
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminWhyQueue() {
  const [state, setState] = useState({ loading: true, error: null, rows: [] });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const r = await fetch(`${API}/admin/why-queue/positions`, { credentials: "include" });
      if (r.status === 403) throw new Error("Admin only.");
      if (!r.ok) throw new Error(`Could not load the queue (HTTP ${r.status}).`);
      const data = await r.json();
      setState({ loading: false, error: null, rows: data.positions || [] });
    } catch (e) {
      setState({ loading: false, error: e.message, rows: [] });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <Layout>
      <div className="mx-auto max-w-4xl px-4 py-6 space-y-4">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">
            Why queue{!state.loading && !state.error && ` — ${state.rows.length} position${state.rows.length === 1 ? "" : "s"}`}
          </h1>
          <Button variant="outline" size="sm" className="ml-auto" onClick={load} disabled={state.loading}>
            {state.loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span className="ml-1.5">Refresh</span>
          </Button>
        </div>
        <p className="text-sm text-gray-600">
          Positions the Why button could not explain, sent to Claude to study. Rule on them in{" "}
          <Link to="/admin/geometry-gaps" className="text-sky-700 underline underline-offset-2">
            Geometry gaps → Claude
          </Link>.
        </p>
        {state.error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{state.error}</div>
        )}
        {!state.loading && !state.error && state.rows.length === 0 && (
          <div className="text-sm text-gray-600">Nothing has been queued yet.</div>
        )}
        <div className="space-y-4">
          {state.rows.map((p) => <PositionRow key={p.key} p={p} />)}
        </div>
      </div>
    </Layout>
  );
}
