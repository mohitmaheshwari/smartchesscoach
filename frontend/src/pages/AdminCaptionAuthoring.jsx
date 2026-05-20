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
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";
import { Loader2, X, RefreshCw } from "lucide-react";

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
  const [editingTarget, setEditingTarget] = useState(null);
  // editingTarget = { position, template (the current variant string),
  //                   file, variant_key }

  const fetchAudit = async (sampleSize = 50) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API}/admin/captions/audit?sample=${sampleSize}`,
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
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-400">Sample:</label>
            <input
              type="number"
              min={10}
              max={200}
              value={sample}
              onChange={(e) => setSample(Number(e.target.value) || 50)}
              className="w-20 px-2 py-1 rounded bg-zinc-800 text-zinc-200 border border-zinc-700 text-sm"
            />
            <Button onClick={() => fetchAudit(sample)} variant="outline" size="sm">
              <RefreshCw className="w-4 h-4 mr-1" />
              Re-audit
            </Button>
          </div>
        </div>

        {/* Tier bars */}
        <CoverageBars auditData={auditData} />

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

const TemplateCard = ({ tpl, total, onEdit }) => {
  const [expanded, setExpanded] = useState(false);
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
        onClick={() => setExpanded(!expanded)}
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
              No sample positions captured for this template (only LOW/NONE
              tiers retain examples — HIGH/MID firings are counted but not
              sampled).
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {tpl.sample_positions.map((p, i) => (
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
  return (
    <div className="border border-zinc-800 rounded p-3 bg-zinc-900/30">
      <div className="flex gap-3">
        <div className="w-40 h-40 flex-shrink-0">
          <LichessBoard
            fen={fen}
            orientation={orient}
            interactive={false}
            viewOnly={true}
          />
        </div>
        <div className="flex-1 min-w-0 space-y-2">
          <div className="text-xs text-zinc-400 font-mono">
            game {position.game_id?.slice(0, 8)} · move {position.move_number}{" "}
            · {position.move_san}{" "}
            <span className="text-zinc-500">(cp_loss {position.cp_loss})</span>
          </div>
          <div className="text-sm text-zinc-200 leading-relaxed">
            {position.caption || (
              <span className="italic text-zinc-500">(no caption)</span>
            )}
          </div>
          {position.best_move_san && (
            <div className="text-xs text-zinc-500">
              best: {position.best_move_san}
            </div>
          )}
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
  const [parsed] = useState(() => parseJsonPath(target.json_path));
  const [current, setCurrent] = useState("");
  const [draft, setDraft] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

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

  const runCommit = async () => {
    if (!window.confirm(`Commit new template to ${parsed.file} → ${parsed.variant}?`))
      return;
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`${API}/admin/captions/commit`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file: parsed.file,
          variant: parsed.variant,
          template: draft,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        setErr(text);
        return;
      }
      onCommitted();
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
        </div>

        <div className="flex gap-4">
          <div className="w-56 h-56 flex-shrink-0">
            <LichessBoard
              fen={target.position.fen_before}
              orientation={target.position.is_white ? "white" : "black"}
              interactive={false}
              viewOnly={true}
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
                onClick={runCommit}
                disabled={busy || draft === current}
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                Commit to JSON
              </Button>
            </div>
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
