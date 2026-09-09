import { useCallback, useEffect, useMemo, useState } from "react";
import { Chess } from "chess.js";
import {
  AlertTriangle,
  Check,
  Copy,
  Loader2,
  RefreshCw,
  ShieldCheck,
  SkipForward,
} from "lucide-react";
import { API } from "@/App";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import LichessBoard from "@/components/LichessBoard";

const EMPTY_FORM = {
  disposition: "eligible_positional",
  concept_label: "",
  canonical_concept_id: "",
  better_move_fact: "",
  played_move_fact: "",
  contrast: "",
  transferable_lesson: "",
  notes: "",
};

const DISPOSITIONS = [
  {
    id: "eligible_positional",
    label: "Teach this",
    description: "A reusable positional lesson is proved by the board.",
  },
  {
    id: "not_mistake",
    label: "Not a mistake",
    description: "The played move is acceptable after review.",
  },
  {
    id: "already_decided",
    label: "Already decided",
    description: "The move did not meaningfully change the game.",
  },
  {
    id: "tactical_or_forced",
    label: "Tactical / forced",
    description: "A concrete tactic explains the engine difference.",
  },
  {
    id: "unstable_engine_choice",
    label: "Engine unstable",
    description: "A deeper run does not preserve the claimed best move.",
  },
  {
    id: "duplicate",
    label: "Duplicate",
    description: "This adds no new evidence to an existing example.",
  },
  {
    id: "insufficient_evidence",
    label: "Not enough proof",
    description: "The board does not support a confident explanation.",
  },
];

const sanToArrow = (fen, san, color) => {
  if (!fen || !san) return null;
  try {
    const game = new Chess(fen);
    const move = game.move(san, { sloppy: true });
    return move ? [move.from, move.to, color] : null;
  } catch {
    return null;
  }
};

export default function AdminPositionalReasons() {
  const [position, setPosition] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [concepts, setConcepts] = useState([]);
  const [similar, setSimilar] = useState([]);
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setForm(EMPTY_FORM);
    setSimilar([]);
    try {
      const res = await fetch(`${API}/admin/positional-reasons/next`, {
        credentials: "include",
      });
      if (res.status === 404) {
        setPosition(null);
        setError("Every queued position has been reviewed.");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPosition(data);
      setProgress(data.progress || null);
    } catch (fetchError) {
      setPosition(null);
      setError(`Could not load a position: ${fetchError.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    fetch(`${API}/admin/positional-reasons/concepts`, {
      credentials: "include",
    })
      .then((res) => (res.ok ? res.json() : { concepts: [] }))
      .then((data) => setConcepts(data.concepts || []))
      .catch(() => setConcepts([]));
  }, [load]);

  useEffect(() => {
    if (!position?.structural_signature) return;
    const params = new URLSearchParams({
      structural_signature: position.structural_signature,
      exclude_fen: position.fen,
    });
    fetch(`${API}/admin/positional-reasons/similar?${params.toString()}`, {
      credentials: "include",
    })
      .then((res) => (res.ok ? res.json() : { submissions: [] }))
      .then((data) => setSimilar(data.submissions || []))
      .catch(() => setSimilar([]));
  }, [position]);

  const setField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  // The route still exposes POST /admin/positional-reasons/skip, and a queue
  // you cannot step past stalls on the first board you cannot read.
  const skip = async () => {
    if (!position) return;
    setSaving(true);
    try {
      await fetch(`${API}/admin/positional-reasons/skip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ fen: position.fen }),
      });
      await load();
    } catch (e) {
      setError(`Could not skip: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const copy = async (kind) => {
    if (!position) return;
    const text =
      kind === "fen"
        ? position.fen
        : [
            `FEN: ${position.fen}`,
            `${position.side_to_move} to move.`,
            `The reviewed alternative is ${position.best_san}; the player chose ${position.played_san}.`,
            "",
            "For a 900-1500 player, decide first whether this is a real positional lesson.",
            "If it is, explain what changes on the board, why it matters, what the better move preserves or achieves, and what to check next time.",
            "If it is already decided, not a mistake, tactical, duplicated, unstable, or unclear, choose that disposition instead.",
          ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      window.setTimeout(() => setCopied(""), 1200);
    } catch {
      setCopied("");
    }
  };

  const eligibleComplete = useMemo(
    () =>
      Boolean(
        form.concept_label.trim() &&
          form.better_move_fact.trim() &&
          form.played_move_fact.trim() &&
          form.contrast.trim() &&
          form.transferable_lesson.trim()
      ),
    [form]
  );

  const save = async (disposition = form.disposition) => {
    if (!position) return;
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`${API}/admin/positional-reasons`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ...form, disposition, fen: position.fen }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setProgress(data.progress || progress);
      await load();
    } catch (saveError) {
      setError(`Could not save: ${saveError.message}`);
    } finally {
      setSaving(false);
    }
  };

  const arrows = position
    ? [
        sanToArrow(position.fen, position.best_san, "green"),
        sanToArrow(position.fen, position.played_san, "red"),
      ].filter(Boolean)
    : [];

  const previewTitle =
    form.concept_label ||
    concepts.find((item) => item.id === form.canonical_concept_id)?.name ||
    "Teaching idea";
  const previewBody = [
    form.played_move_fact,
    form.better_move_fact,
    form.contrast,
    form.transferable_lesson,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Layout>
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
              Positional reasons
            </p>
            <h1 className="text-2xl font-semibold">Decide whether this teaches anything</h1>
            <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
              Green is the reviewed engine move and red is what was played.
              First classify the position. Only a proved positional lesson
              enters the detector-authoring corpus.
            </p>
          </div>
          {progress && (
            <div className="max-w-xl text-right text-xs text-muted-foreground">
              <div className="text-lg font-semibold text-foreground">
                {progress.resolved}
                <span className="text-muted-foreground">/{progress.total}</span>
              </div>
              <div>{progress.pending} still to review</div>
              <div className="mt-2 flex flex-wrap justify-end gap-1.5">
                {Object.entries(progress.by_disposition || {})
                  .filter(([, count]) => count > 0)
                  .map(([id, count]) => (
                    <span
                      key={id}
                      className="rounded-full border border-border px-2 py-1 text-[10px]"
                    >
                      {DISPOSITIONS.find((item) => item.id === id)?.label || id}: {count}
                    </span>
                  ))}
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm">
            {error}
            <Button variant="ghost" size="sm" className="ml-2" onClick={load}>
              <RefreshCw className="mr-1 h-3 w-3" /> Retry
            </Button>
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 py-16 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading a position...
          </div>
        ) : position ? (
          <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
            <div>
              <div className="aspect-square w-full">
                <LichessBoard
                  fen={position.fen}
                  orientation={position.side_to_move === "black" ? "black" : "white"}
                  interactive={false}
                  viewOnly
                  arrows={arrows}
                />
              </div>
              <div className="mt-3 space-y-1 font-mono text-xs text-muted-foreground">
                <div>
                  <span className="text-red-400">played {position.played_san}</span>
                  {"  /  "}
                  <span className="text-emerald-400">reviewed {position.best_san}</span>
                </div>
                <div>
                  {position.side_to_move} to move / {position.men} pieces /{" "}
                  {position.cp_loss}cp difference / {position.bucket}
                </div>
                {position.already_explained_by?.length > 0 && (
                  <div className="text-amber-400">
                    existing detectors: {position.already_explained_by.join(", ")}
                  </div>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => copy("fen")}>
                  <Copy className="mr-1 h-3 w-3" />
                  {copied === "fen" ? "Copied" : "Copy FEN"}
                </Button>
                <Button variant="outline" size="sm" onClick={() => copy("prompt")}>
                  <Copy className="mr-1 h-3 w-3" />
                  {copied === "prompt" ? "Copied" : "Copy review prompt"}
                </Button>
              </div>

              {similar.length > 0 && (
                <div className="mt-4 rounded-lg border border-border p-3">
                  <p className="text-xs font-semibold">Structurally similar reviews</p>
                  <div className="mt-2 space-y-2">
                    {similar.map((item, index) => (
                      <div key={`${item.fen}-${index}`} className="text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">
                          {item.concept_label || item.canonical_concept_id || item.disposition}
                        </span>
                        {": "}
                        {item.reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-5">
              <section>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  1. Classify the position
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {DISPOSITIONS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setField("disposition", item.id)}
                      className={`rounded-lg border p-3 text-left transition ${
                        form.disposition === item.id
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/40"
                      }`}
                    >
                      <span className="block text-sm font-medium">{item.label}</span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {item.description}
                      </span>
                    </button>
                  ))}
                </div>
              </section>

              {form.disposition === "eligible_positional" ? (
                <>
                  <section className="grid gap-3 sm:grid-cols-2">
                    <label className="text-xs font-medium text-muted-foreground">
                      Existing canonical concept (optional)
                      <select
                        value={form.canonical_concept_id}
                        onChange={(event) =>
                          setField("canonical_concept_id", event.target.value)
                        }
                        className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                      >
                        <option value="">New candidate or unsure</option>
                        {concepts.map((concept) => (
                          <option key={concept.id} value={concept.id}>
                            {concept.name} ({concept.id})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-xs font-medium text-muted-foreground">
                      Teaching-idea headline
                      <input
                        value={form.concept_label}
                        onChange={(event) => setField("concept_label", event.target.value)}
                        placeholder="Choose the piece with fewer jobs"
                        className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                      />
                    </label>
                  </section>

                  {[
                    [
                      "better_move_fact",
                      `What does ${position.best_san} achieve or preserve?`,
                      "Name the piece, square, line, pawn, or defensive job.",
                    ],
                    [
                      "played_move_fact",
                      `What does ${position.played_san} give up or fail to do?`,
                      "Describe the resulting board, not the engine score.",
                    ],
                    [
                      "contrast",
                      "Why does that difference matter?",
                      "The claim must be true for the better move and false or weaker for the played move.",
                    ],
                    [
                      "transferable_lesson",
                      "What should the player check next time?",
                      "Write a plain rule a 900 player can use in another game.",
                    ],
                  ].map(([field, label, placeholder]) => (
                    <label key={field} className="block text-xs font-medium text-muted-foreground">
                      {label}
                      <textarea
                        value={form[field]}
                        onChange={(event) => setField(field, event.target.value)}
                        rows={2}
                        placeholder={placeholder}
                        className="mt-1 w-full resize-y rounded-lg border border-border bg-background p-3 text-sm text-foreground outline-none focus:border-primary/60"
                      />
                    </label>
                  ))}

                  <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <ShieldCheck className="h-4 w-4 text-emerald-500" />
                      900-1500 teaching preview
                    </div>
                    <p className="mt-2 text-xs font-bold uppercase tracking-wide">
                      {previewTitle}
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {previewBody || "Complete the four proof fields to preview the lesson."}
                    </p>
                    <p className="mt-2 font-mono text-xs text-muted-foreground">
                      Played: {position.played_san} / Better: {position.best_san}
                    </p>
                  </div>
                </>
              ) : (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
                  <div className="flex items-center gap-2 font-medium">
                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                    This position will not affect captions or mastery.
                  </div>
                </div>
              )}

              <label className="block text-xs font-medium text-muted-foreground">
                Reviewer notes (optional)
                <textarea
                  value={form.notes}
                  onChange={(event) => setField("notes", event.target.value)}
                  rows={2}
                  className="mt-1 w-full resize-y rounded-lg border border-border bg-background p-3 text-sm text-foreground"
                />
              </label>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  onClick={() => save()}
                  disabled={
                    saving ||
                    (form.disposition === "eligible_positional" && !eligibleComplete)
                  }
                >
                  {saving ? (
                    <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="mr-1 h-4 w-4" />
                  )}
                  Save disposition and next
                </Button>
                <Button variant="ghost" onClick={skip} disabled={saving}>
                  <SkipForward className="mr-1 h-4 w-4" />
                  Skip this one
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <p className="py-16 text-muted-foreground">Nothing to review.</p>
        )}
      </div>
    </Layout>
  );
}
