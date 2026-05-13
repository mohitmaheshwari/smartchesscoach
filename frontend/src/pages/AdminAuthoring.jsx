/**
 * AdminAuthoring — caption-template authoring queue page.
 *
 * Lists the games picked by scripts/pick_authoring_games.py --persist
 * for the active authoring round. Author (Parth) opens each game in
 * fact-dump mode (?show_facts=1) to write replacement captions inline
 * via the flag dialog's "Authoring (optional)" field.
 *
 * Submission count per game is shown so the author can track progress
 * without redoing work.
 */
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, Loader2, CheckCircle2, Circle } from "lucide-react";

const BUCKET_LABEL = {
  TACTICAL_BLUNDER: "Tactical blunder",
  POSITIONAL_MISTAKE: "Positional mistake",
  ENDGAME: "Endgame",
  OPENING_DRIFT: "Opening drift",
  WON_WITH_BLUNDER: "Won despite blunder",
};

const BUCKET_COLOUR = {
  TACTICAL_BLUNDER: "bg-red-500/10 text-red-300 border-red-500/30",
  POSITIONAL_MISTAKE: "bg-orange-500/10 text-orange-300 border-orange-500/30",
  ENDGAME: "bg-blue-500/10 text-blue-300 border-blue-500/30",
  OPENING_DRIFT: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  WON_WITH_BLUNDER: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
};

const AdminAuthoring = ({ user }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/admin/authoring-queue`, {
          credentials: "include",
        });
        if (!res.ok) {
          if (res.status === 403) {
            setError("Admin access required.");
          } else {
            setError(`Failed to load queue (HTTP ${res.status}).`);
          }
          return;
        }
        setData(await res.json());
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <Layout user={user}>
        <div className="flex items-center justify-center h-[60vh]">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout user={user}>
        <div className="max-w-[720px] mx-auto px-6 py-12">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      </Layout>
    );
  }

  const items = data?.items || [];
  const total = data?.total || 0;
  const completed = data?.completed || 0;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <Layout user={user}>
      <div className="max-w-[860px] mx-auto px-6 md:px-10 py-10">
        <div className="mb-8">
          <p className="text-[10.5px] uppercase tracking-[0.22em] text-violet-300 font-semibold mb-2">
            Caption authoring · {data?.round_id || "no active round"}
          </p>
          <h1 className="text-2xl md:text-3xl font-serif text-foreground mb-3">
            Authoring queue
          </h1>
          <p className="text-sm text-muted-foreground max-w-[560px] leading-relaxed">
            Each game opens with the fact-dump panel ON. For every caption you want to fix, click the flag icon, describe what's wrong, and paste your suggested replacement in the "Authoring (optional)" field. The submission count below tracks how many authoring submissions you've already filed per game.
          </p>
        </div>

        {/* Progress bar */}
        {total > 0 && (
          <div className="mb-6">
            <div className="flex items-baseline justify-between mb-2">
              <p className="text-xs text-muted-foreground">
                {completed} of {total} games have at least one authoring submission
              </p>
              <p className="text-xs tabular-nums text-muted-foreground">{pct}%</p>
            </div>
            <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
              <div
                className="h-full bg-emerald-500/60 rounded-full transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}

        {/* Empty state */}
        {total === 0 && (
          <div className="rounded-lg border border-dashed border-zinc-700 p-8 text-center">
            <p className="text-sm text-muted-foreground mb-2">No authoring round active.</p>
            <p className="text-xs text-muted-foreground/70 font-mono">
              docker exec -it chess-coach-backend python scripts/pick_authoring_games.py --persist
            </p>
          </div>
        )}

        {/* Game cards */}
        <div className="space-y-3">
          {items.map((it) => {
            const has = (it.authoring_submission_count || 0) > 0;
            return (
              <Link
                key={it.game_id}
                to={`/game/${it.game_id}?show_facts=1`}
                className="block rounded-lg border border-zinc-700/60 bg-card hover:bg-zinc-900/40 transition-colors p-4"
              >
                <div className="flex items-center gap-4">
                  <div className="flex-shrink-0">
                    {has ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : (
                      <Circle className="w-5 h-5 text-zinc-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded border ${
                          BUCKET_COLOUR[it.bucket] || "bg-zinc-500/10 text-zinc-300 border-zinc-500/30"
                        }`}
                      >
                        {BUCKET_LABEL[it.bucket] || it.bucket}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        #{it.order_in_round}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-foreground">
                      <span className="font-mono text-zinc-400 truncate">
                        {it.game_id.substring(0, 13)}…
                      </span>
                      {it.opening && (
                        <span className="text-zinc-300 truncate">{it.opening}</span>
                      )}
                      {it.result && (
                        <span className="text-muted-foreground">· {it.result}</span>
                      )}
                      {it.user_color && (
                        <span className="text-muted-foreground">· {it.user_color}</span>
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      {it.authoring_submission_count || 0} authoring{" "}
                      {(it.authoring_submission_count || 0) === 1 ? "submission" : "submissions"} so far
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </Layout>
  );
};

export default AdminAuthoring;
