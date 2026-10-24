/**
 * What Stockfish wants, beside what a human of that rating would actually play.
 *
 * Mohit: "can you build a page on chessguru, so I can see those games and
 * then what stockfish suggest and what maia2 suggest, you know so we can
 * build this feature well?"
 *
 * Every position here is one where NOTHING WENT WRONG -- the move played
 * cost under 50cp. The interesting thing is the move that was NOT played:
 * Maia2 says a player of this rating would probably choose it, and Stockfish
 * says it loses. A trap walked past rather than a blunder made.
 *
 * Three arrows, and the colours are the point:
 *   green  what Stockfish wants
 *   blue   what was actually played
 *   red    what Maia2 says they would probably play, and what it costs
 *
 * Read-only. The rows come from scripts/maia_likely_moves_local.py, which
 * runs on Mohit's machine; nothing on the server loads the model.
 */
import { useCallback, useEffect, useState } from "react";
import { API } from "@/App";
import Layout from "@/components/Layout";
import LichessBoard from "@/components/LichessBoard";
import ErrorBoundary from "../components/ErrorBoundary";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw } from "lucide-react";

const SORTS = [
  { id: "pct", label: "Most tempting" },
  { id: "cp", label: "Most costly" },
  { id: "recent", label: "Newest" },
];

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-100 tabular-nums">{value}</div>
      {hint ? <div className="mt-0.5 text-xs text-slate-500">{hint}</div> : null}
    </div>
  );
}

function arrowsFor(p) {
  const pair = (uci, colour) =>
    uci && uci.length >= 4
      ? [uci.slice(0, 2), uci.slice(2, 4), colour]
      : null;
  // Drawn worst-last so the likely move sits on top of the others when two
  // moves share a square.
  return [
    pair(p.best_uci, "green"),
    pair(p.played_uci, "blue"),
    pair(p.likely_uci, "red"),
  ].filter(Boolean);
}

function PositionCard({ p }) {
  const samePlayedAsBest = p.played_san === p.best_move_san;
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-4">
      <div className="flex flex-col gap-4 md:flex-row">
        <div className="w-full max-w-[320px] shrink-0">
          <LichessBoard
            fen={p.fen}
            orientation={p.side_to_move === "black" ? "black" : "white"}
            arrows={arrowsFor(p)}
            viewOnly={true}
            interactive={false}
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-sm text-slate-400">
              {p.side_to_move === "white" ? "White" : "Black"} to move
            </span>
            <span className="text-sm text-slate-400">rated {p.elo_self}</span>
            {p.mover_is_user ? (
              <span className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-200">
                their move
              </span>
            ) : (
              <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                opponent to move
              </span>
            )}
          </div>

          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex items-start gap-2">
              <span className="mt-1 h-3 w-3 shrink-0 rounded-sm bg-red-500" />
              <div>
                <dt className="font-medium text-slate-100">
                  Maia2 says they would play {p.likely_move_san}
                </dt>
                <dd className="text-slate-400">
                  <span className="font-semibold text-red-400">
                    {p.likely_move_pct}%
                  </span>{" "}
                  of players at {p.elo_self} choose it, and Stockfish says it
                  loses{" "}
                  <span className="font-semibold text-red-400">
                    {p.likely_move_cp_loss}
                  </span>{" "}
                  centipawns.
                </dd>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <span className="mt-1 h-3 w-3 shrink-0 rounded-sm bg-green-500" />
              <div>
                <dt className="font-medium text-slate-100">
                  Stockfish wants {p.best_move_san}
                </dt>
                <dd className="text-slate-400">depth {p.engine_depth}</dd>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <span className="mt-1 h-3 w-3 shrink-0 rounded-sm bg-blue-500" />
              <div>
                <dt className="font-medium text-slate-100">
                  Actually played {p.played_san}
                  {samePlayedAsBest ? " — the engine's move" : ""}
                </dt>
                <dd className="text-slate-400">
                  cost {p.played_cp_loss} cp, so nothing went wrong here
                </dd>
              </div>
            </div>
          </dl>

          <div className="mt-3 border-t border-slate-800 pt-2 text-xs text-slate-500">
            <a
              className="underline hover:text-slate-300"
              href={`/game/${p.game_id}`}
              target="_blank"
              rel="noreferrer"
            >
              open the game
            </a>
            <span className="mx-2">·</span>
            ply {p.ply}
            {p.game?.platform ? (
              <>
                <span className="mx-2">·</span>
                {p.game.platform}
              </>
            ) : null}
            <span className="mx-2">·</span>
            <code className="text-[11px]">{p.fen}</code>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AdminMaiaReview() {
  const [results, setResults] = useState(null);
  const [positions, setPositions] = useState([]);
  const [sort, setSort] = useState("pct");
  const [minPct, setMinPct] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, p] = await Promise.all([
        fetch(`${API}/admin/maia-review/results`, { credentials: "include" }),
        fetch(
          `${API}/admin/maia-review/positions?sort=${sort}&min_pct=${minPct}&limit=40`,
          { credentials: "include" }
        ),
      ]);
      if (!r.ok || !p.ok) throw new Error(`HTTP ${r.status}/${p.status}`);
      setResults(await r.json());
      setPositions((await p.json()).positions || []);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [sort, minPct]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Layout>
      <ErrorBoundary>
        <div className="mx-auto max-w-5xl px-4 py-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-slate-100">
                Stockfish vs Maia2
              </h1>
              <p className="mt-1 max-w-2xl text-sm text-slate-400">
                Positions where nothing went wrong — but a player at this
                rating would probably have played a losing move. The engine
                says what is best; Maia2 says what a human actually does.
              </p>
            </div>
            <Button variant="outline" onClick={load} disabled={loading}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              <span className="ml-2">Refresh</span>
            </Button>
          </div>

          {results && results.total > 0 ? (
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Stat
                label="Positions"
                value={results.total}
                hint={`from ${results.games} games`}
              />
              <Stat
                label="Typical temptation"
                value={`${Math.round(results.pct_median)}%`}
                hint={`p90 ${Math.round(results.pct_p90)}%, max ${Math.round(
                  results.pct_max
                )}%`}
              />
              <Stat
                label="Typical cost"
                value={`${results.cp_median} cp`}
                hint={`p90 ${results.cp_p90} cp`}
              />
              <Stat
                label="80%+ would err"
                value={results.buckets?.["80%+"] ?? 0}
                hint="the strongest questions"
              />
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap items-center gap-2">
            {SORTS.map((s) => (
              <Button
                key={s.id}
                size="sm"
                variant={sort === s.id ? "default" : "outline"}
                onClick={() => setSort(s.id)}
              >
                {s.label}
              </Button>
            ))}
            <span className="ml-2 text-sm text-slate-400">at least</span>
            {[0, 40, 60, 80].map((v) => (
              <Button
                key={v}
                size="sm"
                variant={minPct === v ? "default" : "outline"}
                onClick={() => setMinPct(v)}
              >
                {v === 0 ? "any" : `${v}%`}
              </Button>
            ))}
          </div>

          {error ? (
            <div className="mt-6 rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm text-red-300">
              {error}
            </div>
          ) : null}

          {!loading && !error && positions.length === 0 ? (
            <div className="mt-6 rounded-lg border border-slate-700 bg-slate-900/40 p-6 text-sm text-slate-400">
              Nothing here yet. These rows are written by{" "}
              <code className="text-slate-300">
                scripts/maia_likely_moves_local.py
              </code>
              , which runs on Mohit&rsquo;s machine — the model needs about
              800&nbsp;MB and the server has none spare until mongodb is capped.
            </div>
          ) : null}

          <div className="mt-5 space-y-4">
            {positions.map((p) => (
              <PositionCard key={`${p.game_id}-${p.ply}`} p={p} />
            ))}
          </div>
        </div>
      </ErrorBoundary>
    </Layout>
  );
}
