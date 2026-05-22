/**
 * AdminCaptionAuthoring — caption coverage dashboard + per-position
 * board-based authoring UI.
 *
 * Built so Mohit + Parth can:
 *   1. See the coverage breakdown (HIGH/MID/LOW/NONE) at a glance.
 *   2. Browse LOW/NONE positions WITH BOARD RENDERED — the gap CLI
 *      audit had.
 *   3. Edit the JSON template inline, preview the new caption
 *      rendered against the same facts, commit when satisfied.
 *
 * Auth: admin-only (backend enforces require_admin on every route).
 */
import { useState, useEffect, useMemo } from "react";
import { Chess } from "chess.js";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, X, RefreshCw, Search } from "lucide-react";


// Resolve a SAN move on a FEN to a [from, to, color] arrow tuple.
// Returns null when the SAN can't be parsed against the position.
const sanToArrow = (fen, san, color) => {
  if (!fen || !san) return null;
  try {
    const game = new Chess(fen);
    const move = game.move(san, { sloppy: true });
    if (!move) return null;
    return [move.from, move.to, color];
  } catch {
    return null;
  }
};

// Build the two arrows for a position: red on the played move,
// green on the engine's recommended move.
const buildPositionArrows = (position) => {
  const arrows = [];
  const played = sanToArrow(position.fen_before, position.move_san, "red");
  if (played) arrows.push(played);
  const best = sanToArrow(position.fen_before, position.best_move_san, "green");
  if (best) arrows.push(best);
  return arrows;
};

const TIER_COLOURS = {
  HIGH: "bg-emerald-500",
  MID:  "bg-amber-500",
  LOW:  "bg-orange-500",
  NONE: "bg-red-500",
};

const TIER_TEXT = {
  HIGH: "text-emerald-300",
  MID:  "text-amber-300",
  LOW:  "text-orange-300",
  NONE: "text-red-300",
};


const AdminCaptionAuthoring = ({ user }) => {
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sample, setSample] = useState(50);
  // Which tiers to retain board-level sample positions for.
  // Default LOW+NONE = the authoring backlog. Toggle HIGH/MID on to
  // also browse passing-tier captions for pedagogical-quality review.
  const [sampleTiers, setSampleTiers] = useState({
    HIGH: false, MID: false, LOW: true, NONE: true,
  });
  const [searchTerm, setSearchTerm] = useState("");
  // Opt into force-regen of stale games on re-audit. Default off so the
  // page loads instantly even right after a V5_COACHING_VERSION bump
  // (regenerating 50+ games would blow past the host nginx 60s timeout
  // and return 504). When you want freshest captions, toggle this on
  // and accept the wait (or run scripts/caption_coverage_v5.py offline).
  const [forceRegen, setForceRegen] = useState(false);
  const [editingTarget, setEditingTarget] = useState(null);
  // editingTarget = { position, template (the current variant string),
  //                   file, variant_key }

  const fetchAudit = async (sampleSize = 50, tiers = sampleTiers, regen = forceRegen) => {
    setLoading(true);
    setError(null);
    try {
      const tierList = Object.entries(tiers)
        .filter(([, on]) => on)
        .map(([t]) => t)
        .join(",");
      const params = new URLSearchParams({ sample: String(sampleSize) });
      if (tierList) params.set("sample_tiers", tierList);
      if (regen) params.set("force_regen", "true");
      const res = await fetch(
        `${API}/admin/captions/audit?${params.toString()}`,
        { credentials: "include" },
      );
      if (!res.ok) {
        if (res.status === 403) {
          setError("Admin access required.");
        } else {
          setError(`Failed to load audit (HTTP ${res.status}).`);
        }
        return;
      }
      setAuditData(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit(sample);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && !auditData) {
    return (
      <Layout user={user}>
        <div className="flex flex-col items-center justify-center h-[60vh] gap-3 text-zinc-400">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span className="text-sm">Running audit (force-regenerating stale games at current V5 version)…</span>
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

  return (
    <Layout user={user}>
      <div className="max-w-[1100px] mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">
              Caption Coverage Audit
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              v{auditData?.v5_version} ·{" "}
              {auditData?.total_blunder_moves} blunder moves across{" "}
              {auditData?.games_scanned} games
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <label className="text-xs text-zinc-400">Sample:</label>
            <input
              type="number"
              min={10}
              max={500}
              value={sample}
              onChange={(e) => setSample(Number(e.target.value) || 50)}
              className="w-20 px-2 py-1 rounded bg-zinc-800 text-zinc-200 border border-zinc-700 text-sm"
            />
            <div className="flex items-center gap-1 ml-2">
              <span className="text-xs text-zinc-400 mr-1">Browse:</span>
              {["HIGH", "MID", "LOW", "NONE"].map((t) => (
                <label
                  key={t}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-xs cursor-pointer border ${
                    sampleTiers[t]
                      ? `${TIER_COLOURS[t]} text-white border-transparent`
                      : "bg-zinc-800 text-zinc-400 border-zinc-700"
                  }`}
                  title={`Retain sample positions for ${t}-tier captions in the response`}
                >
                  <input
                    type="checkbox"
                    checked={sampleTiers[t]}
                    onChange={(e) =>
                      setSampleTiers((prev) => ({ ...prev, [t]: e.target.checked }))
                    }
                    className="hidden"
                  />
                  {t}
                </label>
              ))}
            </div>
            <label
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs cursor-pointer border ${
                forceRegen
                  ? "bg-amber-500 text-white border-transparent"
                  : "bg-zinc-800 text-zinc-400 border-zinc-700"
              }`}
              title="Force-regen any game whose stored v5 version is stale. Slow after a code bump (seconds per game) — only enable when you want freshest captions."
            >
              <input
                type="checkbox"
                checked={forceRegen}
                onChange={(e) => setForceRegen(e.target.checked)}
                className="hidden"
              />
              Force regen
            </label>
            <Button onClick={() => fetchAudit(sample, sampleTiers, forceRegen)} variant="outline" size="sm">
              <RefreshCw className="w-4 h-4 mr-1" />
              Re-audit
            </Button>
          </div>
        </div>

        {/* Tier bars */}
        <CoverageBars auditData={auditData} />

        {/* Search — filters per-template sample positions by game_id /
            move SAN / FEN piece placement / caption text. When non-empty,
            templates with zero matching positions are auto-collapsed below. */}
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search game_id, move SAN, FEN, or caption…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="flex-1 px-3 py-2 rounded bg-zinc-800 text-zinc-100 border border-zinc-700 text-sm placeholder-zinc-500 focus:outline-none focus:border-zinc-500"
          />
          {searchTerm && (
            <Button onClick={() => setSearchTerm("")} variant="ghost" size="sm">
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>

        {/* Per-template list */}
        <section className="space-y-6">
          <h2 className="text-lg font-medium text-zinc-200">
            Templates by frequency
          </h2>
          {(auditData?.templates || []).map((tpl) => (
            <TemplateCard
              key={`${tpl.tier}-${tpl.key}`}
              tpl={tpl}
              total={auditData.total_blunder_moves}
              onEdit={setEditingTarget}
              searchTerm={searchTerm}
            />
          ))}
        </section>

        {/* Edit modal */}
        {editingTarget && (
          <EditModal
            target={editingTarget}
            onClose={() => setEditingTarget(null)}
            onCommitted={() => {
              setEditingTarget(null);
              fetchAudit(sample);
            }}
          />
        )}
      </div>
    </Layout>
  );
};


// ── Coverage bars ────────────────────────────────────────────────────

const CoverageBars = ({ auditData }) => {
  if (!auditData) return null;
  const { tier_pct, high_pct, fallback_pct } = auditData;
  return (
    <div className="space-y-3 bg-zinc-900/50 border border-zinc-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-zinc-300">
          Coverage by tier
        </span>
        <div className="text-xs text-zinc-400 space-x-4">
          <span>
            HIGH:{" "}
            <span className="text-emerald-300 font-semibold">
              {high_pct?.toFixed(1)}%
            </span>
          </span>
          <span>
            Fallback:{" "}
            <span className="text-orange-300 font-semibold">
              {fallback_pct?.toFixed(1)}%
            </span>
          </span>
        </div>
      </div>
      {["HIGH", "MID", "LOW", "NONE"].map((tier) => {
        const pct = tier_pct?.[tier] || 0;
        return (
          <div key={tier} className="flex items-center gap-3">
            <span
              className={`w-16 text-xs font-medium ${TIER_TEXT[tier]}`}
            >
              {tier}
            </span>
            <div className="flex-1 h-3 bg-zinc-800 rounded overflow-hidden">
              <div
                className={`h-full ${TIER_COLOURS[tier]}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-zinc-400 w-14 text-right">
              {pct.toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
};


// ── Per-template card ───────────────────────────────────────────────

// Match a sample position against the user's search term. Case-insensitive
// substring match across game_id, move_san, best_move_san, fen_before piece
// placement (first FEN field), and caption text. Empty search matches all.
const positionMatchesSearch = (position, term) => {
  if (!term) return true;
  const needle = term.trim().toLowerCase();
  if (!needle) return true;
  const fenPlacement = (position.fen_before || "").split(" ")[0].toLowerCase();
  const haystack = [
    position.game_id || "",
    position.move_san || "",
    position.best_move_san || "",
    fenPlacement,
    position.caption || "",
  ].join(" ").toLowerCase();
  return haystack.includes(needle);
};

const TemplateCard = ({ tpl, total, onEdit, searchTerm }) => {
  // When the user has a search term, the matching positions are the only
  // ones that count. We auto-expand a template if it has matches, and we
  // auto-hide templates with zero matches.
  const matchingPositions = (tpl.sample_positions || []).filter((p) =>
    positionMatchesSearch(p, searchTerm),
  );
  const hasSearch = Boolean((searchTerm || "").trim());
  const [manuallyExpanded, setManuallyExpanded] = useState(false);
  const expanded = hasSearch ? matchingPositions.length > 0 : manuallyExpanded;

  // Hide whole template card when there's a search and no matches in its
  // sample positions. (Templates without samples for the current tier are
  // also hidden when searching — they can't possibly match.)
  if (hasSearch && matchingPositions.length === 0) return null;

  const pct = ((tpl.count / total) * 100).toFixed(1);
  const tierBadge = (
    <span
      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${TIER_COLOURS[tpl.tier]} text-white`}
    >
      {tpl.tier}
    </span>
  );
  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden">
      <button
        onClick={() => { if (!hasSearch) setManuallyExpanded(!manuallyExpanded); }}
        className="w-full flex items-center justify-between p-4 hover:bg-zinc-900/50 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          {tierBadge}
          <span className="text-sm font-medium text-zinc-200">
            {tpl.key}
          </span>
          <span className="text-xs text-zinc-500 font-mono">
            {tpl.json_path || "(no JSON path — needs new detector)"}
          </span>
        </div>
        <div className="text-right">
          <span className="text-sm text-zinc-300">
            {tpl.count} ({pct}%)
            {hasSearch && matchingPositions.length > 0 && (
              <span className="ml-2 text-emerald-300 text-xs">
                · {matchingPositions.length} match
              </span>
            )}
          </span>
          <span className="ml-3 text-zinc-500 text-xs">
            {expanded ? "▾" : "▸"}
          </span>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-zinc-800 p-4 space-y-4 bg-zinc-950/30">
          {(tpl.sample_positions || []).length === 0 ? (
            <p className="text-xs text-zinc-500">
              No sample positions captured for this template. Enable the
              <span className={`mx-1 px-1 rounded text-white text-[10px] ${TIER_COLOURS[tpl.tier]}`}>{tpl.tier}</span>
              toggle in the header and re-audit to retain example positions
              for this tier.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(hasSearch ? matchingPositions : tpl.sample_positions).map((p, i) => (
                <PositionCard
                  key={i}
                  position={p}
                  template={tpl}
                  onEdit={onEdit}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};


// ── Position card with board ────────────────────────────────────────

const PositionCard = ({ position, template, onEdit }) => {
  const fen = position.fen_before;
  const orient = position.is_white ? "white" : "black";
  const arrows = useMemo(() => buildPositionArrows(position), [position]);
  return (
    <div className="border border-zinc-800 rounded p-3 bg-zinc-900/30">
      <div className="flex gap-3">
        <div className="w-64 h-64 flex-shrink-0">
          <LichessBoard
            fen={fen}
            orientation={orient}
            interactive={false}
            viewOnly={true}
            arrows={arrows}
          />
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <div className="text-xs text-zinc-400 font-mono">
            game {position.game_id?.slice(0, 8)} · move {position.move_number}{" "}
            · {position.move_san}{" "}
            <span className="text-zinc-500">(cp_loss {position.cp_loss})</span>
          </div>
          <div className="flex items-center gap-3 text-[10px]">
            <span className="flex items-center gap-1 text-red-300">
              <span className="inline-block w-3 h-1 bg-red-500" />
              played: {position.move_san}
            </span>
            {position.best_move_san && (
              <span className="flex items-center gap-1 text-emerald-300">
                <span className="inline-block w-3 h-1 bg-emerald-500" />
                best: {position.best_move_san}
              </span>
            )}
          </div>
          <div className="text-sm text-zinc-200 leading-relaxed">
            {position.caption || (
              <span className="italic text-zinc-500">(no caption)</span>
            )}
          </div>
          {template.json_path && (
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                onEdit({
                  position,
                  template_key: template.key,
                  json_path: template.json_path,
                })
              }
            >
              Edit template
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};


// ── Edit modal ──────────────────────────────────────────────────────
// json_path looks like "R12_blunder.json → variants.why_user_reply"

const parseJsonPath = (path) => {
  if (!path) return null;
  const m = path.match(/^([\w.]+\.json)\s*→\s*variants\.(\w+(?:_\*)?)/);
  if (!m) return null;
  return { file: m[1], variant: m[2] };
};

const EditModal = ({ target, onClose, onCommitted }) => {
  // ALL hooks declared up-front — React requires identical hook order
  // on every render, so we can't put any useState after a conditional
  // return.
  const [parsed] = useState(() => parseJsonPath(target.json_path));
  const [current, setCurrent] = useState("");
  const [draft, setDraft] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [submitMsg, setSubmitMsg] = useState(null);

  // Load current template text from the JSON file (via a fake preview
  // that returns the raw template). We don't have a "get variant"
  // endpoint, so use the caption seen on the position as a starting
  // point. The author edits the TEMPLATE, not the rendered caption.
  useEffect(() => {
    setCurrent(target.position.caption || "");
    setDraft(target.position.caption || "");
  }, [target]);

  if (!parsed) {
    return (
      <ModalShell onClose={onClose}>
        <div className="text-sm text-amber-400">
          Could not parse JSON path:{" "}
          <code className="font-mono">{target.json_path}</code>
        </div>
      </ModalShell>
    );
  }

  const runPreview = async () => {
    setBusy(true);
    setErr(null);
    try {
      // Best-effort facts: pull from the position itself.
      const facts = {
        played_san: target.position.move_san,
        best_move_san: target.position.best_move_san || "",
        cp_loss: target.position.cp_loss,
      };
      const res = await fetch(`${API}/admin/captions/preview`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template: draft, facts }),
      });
      const data = await res.json();
      if (data.ok) setPreview(data.rendered);
      else setErr(data.error || "Preview failed");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const runSubmit = async () => {
    setBusy(true);
    setErr(null);
    setSubmitMsg(null);
    try {
      const res = await fetch(`${API}/admin/captions/submit`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file: parsed.file,
          variant: parsed.variant,
          template: draft,
          position_context: {
            game_id: target.position.game_id,
            move_number: target.position.move_number,
            move_san: target.position.move_san,
            fen_before: target.position.fen_before,
            caption_observed: target.position.caption,
            best_move_san: target.position.best_move_san,
            cp_loss: target.position.cp_loss,
          },
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        setErr(text);
        return;
      }
      const data = await res.json();
      setSubmitMsg(`Submitted for review. Draft ID: ${data.draft_id?.slice(0, 8)}. Visit /admin/captions/drafts to approve.`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell onClose={onClose}>
      <div className="space-y-4">
        <div>
          <div className="text-xs text-zinc-500 font-mono">
            {parsed.file} → variants.{parsed.variant}
          </div>
          <div className="text-sm text-zinc-400 mt-1">
            game {target.position.game_id?.slice(0, 8)} · move{" "}
            {target.position.move_number} · {target.position.move_san}{" "}
            (cp_loss {target.position.cp_loss})
          </div>
          <div className="flex items-center gap-2 mt-2">
            <code className="text-[11px] font-mono text-zinc-300 bg-zinc-800/60 border border-zinc-700 rounded px-2 py-1 flex-1 break-all">
              {target.position.fen_before}
            </code>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                navigator.clipboard?.writeText(target.position.fen_before)
              }
            >
              Copy FEN
            </Button>
          </div>
        </div>

        <div className="flex gap-4">
          <div className="w-80 h-80 flex-shrink-0">
            <LichessBoard
              fen={target.position.fen_before}
              orientation={target.position.is_white ? "white" : "black"}
              interactive={false}
              viewOnly={true}
              arrows={buildPositionArrows(target.position)}
            />
          </div>
          <div className="flex-1 space-y-3">
            <div>
              <label className="text-xs text-zinc-400 block mb-1">
                Current caption on this position (read-only)
              </label>
              <div className="text-sm p-2 rounded bg-zinc-800/50 border border-zinc-700 text-zinc-300">
                {current || <span className="italic">(none)</span>}
              </div>
            </div>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">
                New template text — use {"{placeholders}"} that the rule
                exposes (best_move_san, played_san, etc.)
              </label>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
                className="w-full p-2 rounded bg-zinc-800 border border-zinc-700 text-sm text-zinc-200 font-mono"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={runPreview} disabled={busy} variant="outline" size="sm">
                Preview
              </Button>
              <Button
                onClick={runSubmit}
                disabled={busy || draft === current}
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                Submit for review
              </Button>
            </div>
            {submitMsg && (
              <div className="text-sm p-2 rounded bg-blue-950/30 border border-blue-800 text-blue-200">
                {submitMsg}
              </div>
            )}
            {preview && (
              <div className="text-sm p-2 rounded bg-emerald-950/30 border border-emerald-800 text-emerald-200">
                <span className="text-xs text-emerald-400 block mb-1">
                  Preview (rendered):
                </span>
                {preview}
              </div>
            )}
            {err && (
              <div className="text-sm p-2 rounded bg-red-950/30 border border-red-800 text-red-300">
                {err}
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalShell>
  );
};


const ModalShell = ({ children, onClose }) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
    onClick={onClose}
  >
    <div
      className="bg-zinc-900 border border-zinc-700 rounded-lg max-w-3xl w-full p-6 max-h-[90vh] overflow-y-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex justify-end mb-2">
        <button
          onClick={onClose}
          className="text-zinc-500 hover:text-zinc-300"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
      {children}
    </div>
  </div>
);

export default AdminCaptionAuthoring;
