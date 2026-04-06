/**
 * EvalBadge — Shows position evaluation as a colored badge
 *
 * Props:
 *   evalLabel: { label, short, category, sentiment, description }
 *   size: "sm" | "md" (default: "sm")
 *   showDescription: boolean (default: false)
 */

const CATEGORY_STYLES = {
  completely_winning: "bg-emerald-500/15 text-emerald-500 border-emerald-500/25",
  winning: "bg-emerald-500/15 text-emerald-500 border-emerald-500/25",
  clear_advantage: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  solid_edge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/15",
  slight_edge: "bg-blue-500/10 text-blue-400 border-blue-500/15",
  equal: "bg-muted text-muted-foreground border-border",
  slightly_worse: "bg-orange-500/10 text-orange-400 border-orange-500/15",
  under_pressure: "bg-orange-500/15 text-orange-500 border-orange-500/20",
  losing: "bg-red-500/10 text-red-400 border-red-500/20",
  badly_losing: "bg-red-500/15 text-red-500 border-red-500/25",
  lost: "bg-red-500/15 text-red-500 border-red-500/25",
};

const EvalBadge = ({ evalLabel, size = "sm", showDescription = false }) => {
  if (!evalLabel) return null;

  const { label, short, category, description } = evalLabel;
  const style = CATEGORY_STYLES[category] || CATEGORY_STYLES.equal;

  if (size === "md") {
    return (
      <div className={`rounded-lg border p-3 ${style.replace(/text-\S+/, "").trim()}`}>
        <div className="flex items-center justify-between mb-1">
          <span className={`text-sm font-semibold ${style.match(/text-\S+/)?.[0] || "text-muted-foreground"}`}>
            {label}
          </span>
          <span className={`text-xs font-mono font-bold ${style.match(/text-\S+/)?.[0] || "text-muted-foreground"}`}>
            {short}
          </span>
        </div>
        {showDescription && description && (
          <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
        )}
      </div>
    );
  }

  // Small badge (inline)
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-semibold rounded border ${style}`}
      title={description || label}
    >
      {label}
      <span className="font-mono text-[10px] opacity-70">{short}</span>
    </span>
  );
};

export default EvalBadge;
