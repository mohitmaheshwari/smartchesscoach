/**
 * REVIEW QUEUE — reviewer-only page for browsing every beta user's
 * games and clicking into the lab page to flag content-quality bugs.
 *
 * Hits /api/reviewer/games (paginated, filterable, lightweight).
 * Bypasses /api/lab-coach-pick which is the heavy personal-coaching
 * dashboard not suited for browsing thousands of games.
 *
 * Access: server returns 403 unless user.is_reviewer === true.
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { ChevronRight, Flag, Search } from "lucide-react";

const PAGE_SIZE = 50;

const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString();
};

const resultLabel = (r) => {
  const s = String(r || "").toLowerCase().trim();
  if (s === "win" || s === "w") return { text: "W", className: "text-green-600" };
  if (s === "loss" || s === "l") return { text: "L", className: "text-red-600" };
  if (s === "draw" || s === "d" || s === "1/2-1/2") return { text: "D", className: "text-yellow-600" };
  return { text: s || "—", className: "text-muted-foreground" };
};

const ReviewQueue = ({ user }) => {
  const navigate = useNavigate();

  // Server data
  const [data, setData] = useState(null);
  const [owners, setOwners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [accessError, setAccessError] = useState(null);

  // Filters
  const [page, setPage] = useState(1);
  const [ownerFilter, setOwnerFilter] = useState("");
  const [openingFilter, setOpeningFilter] = useState("");
  const [hasBugsFilter, setHasBugsFilter] = useState("all"); // all | yes | no
  const [openingDraft, setOpeningDraft] = useState("");
  const [regeneratedOnly, setRegeneratedOnly] = useState(true);

  const fetchGames = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
        regenerated_only: String(regeneratedOnly),
      });
      if (ownerFilter) params.set("user_id", ownerFilter);
      if (openingFilter) params.set("opening", openingFilter);
      if (hasBugsFilter !== "all") params.set("has_bugs", hasBugsFilter);

      const res = await fetch(`${API}/reviewer/games?${params}`, {
        credentials: "include",
      });
      if (res.status === 403) {
        setAccessError("This page is only available to content-quality reviewers.");
        setData(null);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setAccessError(null);
    } catch (e) {
      console.error("review games fetch failed", e);
    } finally {
      setLoading(false);
    }
  }, [page, ownerFilter, openingFilter, hasBugsFilter, regeneratedOnly]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(
          `${API}/reviewer/owners?regenerated_only=${regeneratedOnly}`,
          { credentials: "include" }
        );
        if (res.ok) {
          const j = await res.json();
          setOwners(j.owners || []);
        }
      } catch (e) {
        console.error("owners fetch failed", e);
      }
    })();
  }, [regeneratedOnly]);

  useEffect(() => {
    fetchGames();
  }, [fetchGames]);

  if (accessError) {
    return (
      <Layout user={user}>
        <div className="max-w-2xl mx-auto pt-16 text-center text-muted-foreground">
          {accessError}
        </div>
      </Layout>
    );
  }

  const games = data?.games || [];
  const total = data?.total || 0;
  const hasMore = data?.has_more || false;

  return (
    <Layout user={user}>
      <div className="max-w-6xl mx-auto p-6">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-foreground">Review Queue</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Browse every beta user's games. Click a row to open it in the Lab and flag content-quality bugs.
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            {total.toLocaleString()} games match current filters · page {page} of {Math.max(1, Math.ceil(total / PAGE_SIZE))}
            {regeneratedOnly && data?.regenerated_total !== null && data?.regenerated_total !== undefined && (
              <span className="ml-2 text-amber-600">
                (showing only games regenerated with current code · {data.regenerated_total.toLocaleString()} regenerated total)
              </span>
            )}
          </p>
        </header>

        {/* Filters */}
        <div className="flex flex-wrap items-end gap-3 mb-4 p-3 rounded-xl border border-border/40 bg-card/50">
          <div>
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Owner</label>
            <select
              className="bg-background border border-border/60 rounded-md text-sm px-2 py-1 min-w-[180px]"
              value={ownerFilter}
              onChange={(e) => { setOwnerFilter(e.target.value); setPage(1); }}
            >
              <option value="">All users ({owners.reduce((s, o) => s + o.game_count, 0)})</option>
              {owners.map((o) => (
                <option key={o.user_id} value={o.user_id}>
                  {o.name} ({o.game_count})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Opening contains</label>
            <div className="flex gap-1">
              <input
                type="text"
                value={openingDraft}
                placeholder="e.g. Sicilian"
                className="bg-background border border-border/60 rounded-md text-sm px-2 py-1 min-w-[180px]"
                onChange={(e) => setOpeningDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setOpeningFilter(openingDraft.trim());
                    setPage(1);
                  }
                }}
              />
              <button
                onClick={() => { setOpeningFilter(openingDraft.trim()); setPage(1); }}
                className="px-2 py-1 rounded-md bg-primary/10 hover:bg-primary/20 text-primary text-sm"
                title="Apply opening filter"
              >
                <Search className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Flagged</label>
            <select
              className="bg-background border border-border/60 rounded-md text-sm px-2 py-1"
              value={hasBugsFilter}
              onChange={(e) => { setHasBugsFilter(e.target.value); setPage(1); }}
            >
              <option value="all">All</option>
              <option value="yes">Has flags</option>
              <option value="no">No flags</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Freshness</label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={regeneratedOnly}
                onChange={(e) => { setRegeneratedOnly(e.target.checked); setPage(1); }}
              />
              <span>Regenerated only</span>
            </label>
          </div>

          {(ownerFilter || openingFilter || hasBugsFilter !== "all" || !regeneratedOnly) && (
            <button
              onClick={() => {
                setOwnerFilter("");
                setOpeningFilter("");
                setOpeningDraft("");
                setHasBugsFilter("all");
                setRegeneratedOnly(true);
                setPage(1);
              }}
              className="ml-auto text-xs text-muted-foreground hover:text-foreground underline self-end"
            >
              clear filters
            </button>
          )}
        </div>

        {/* Table */}
        <div className="rounded-xl border border-border/40 overflow-hidden bg-card/30">
          <div className="grid grid-cols-[60px_1fr_1.2fr_1fr_70px_70px_60px_28px] gap-2 px-3 py-2 text-[10px] uppercase tracking-wide text-muted-foreground border-b border-border/40 bg-muted/30">
            <div>Result</div>
            <div>Owner</div>
            <div>Opening</div>
            <div>Opponent</div>
            <div className="text-right">Blund.</div>
            <div className="text-right">Mist.</div>
            <div className="text-right">Flags</div>
            <div></div>
          </div>

          {loading && (
            <div className="p-8 text-center text-muted-foreground text-sm">Loading…</div>
          )}

          {!loading && games.length === 0 && (
            <div className="p-8 text-center text-muted-foreground text-sm">No games match these filters.</div>
          )}

          {!loading && games.map((g) => {
            const r = resultLabel(g.result);
            return (
              <div
                key={g.game_id}
                onClick={() => navigate(`/lab/game/${g.game_id}`)}
                className="grid grid-cols-[60px_1fr_1.2fr_1fr_70px_70px_60px_28px] gap-2 px-3 py-2 text-sm items-center border-b border-border/20 hover:bg-muted/30 cursor-pointer last:border-b-0"
                title={`game_id: ${g.game_id}`}
              >
                <div className={`font-mono font-semibold ${r.className}`}>{r.text}</div>
                <div className="truncate">
                  <div className="truncate">{g.owner_name}</div>
                  <div className="text-[10px] text-muted-foreground/60 truncate">
                    {g.user_color} · {fmtDate(g.imported_at)}
                  </div>
                </div>
                <div className="truncate text-foreground/80">
                  {g.opening || <span className="text-muted-foreground/40">—</span>}
                </div>
                <div className="truncate text-muted-foreground">
                  {g.opponent}
                </div>
                <div className="text-right tabular-nums">{g.blunders}</div>
                <div className="text-right tabular-nums">{g.mistakes}</div>
                <div className="text-right tabular-nums flex items-center justify-end gap-1">
                  {g.flag_count > 0 && <Flag className="w-3 h-3 text-amber-600" />}
                  <span className={g.flag_count > 0 ? "text-amber-600 font-semibold" : "text-muted-foreground/40"}>
                    {g.flag_count}
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground/40" />
              </div>
            );
          })}
        </div>

        {/* Pagination */}
        {total > 0 && (
          <div className="flex items-center justify-between mt-4 text-sm">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="px-3 py-1.5 rounded-md border border-border/60 hover:bg-muted/40 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Previous
            </button>
            <div className="text-muted-foreground">
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total.toLocaleString()}
            </div>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore || loading}
              className="px-3 py-1.5 rounded-md border border-border/60 hover:bg-muted/40 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ReviewQueue;
