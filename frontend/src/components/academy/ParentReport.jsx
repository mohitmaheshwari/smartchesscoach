/**
 * The weekly parent report: words and boards exactly as the server rendered
 * them (services/academy_service.render_report). Nothing is computed here, so
 * the coach's preview and the parent's page can never disagree.
 *
 * docs/academy_pilot_scope.md, section 2. The sample it follows:
 * https://claude.ai/artifact/RhJwgmp5ZdPjRcdL4331mY
 */
import LichessBoard from "@/components/LichessBoard";

const TONE = {
  habit: "bg-amber-50 border-amber-200 dark:bg-amber-950/40 dark:border-amber-900",
  good: "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/40 dark:border-emerald-900",
};

const KEY_COLOUR = { red: "bg-red-500", green: "bg-emerald-500" };

function ReportBoard({ board }) {
  const circles = board.ring ? [[board.ring, "red"]] : [];
  return (
    <figure className="grid gap-2">
      <div className="w-full max-w-[340px]">
        <LichessBoard
          fen={board.fen}
          orientation={board.orientation || "white"}
          arrows={board.arrows || []}
          circles={circles}
          viewOnly
          interactive={false}
          showCoordinates={false}
        />
      </div>
      {board.caption && <figcaption className="text-[15px]">{board.caption}</figcaption>}
    </figure>
  );
}

export default function ParentReport({ report, homeworkLink }) {
  if (!report) return null;
  const title = `${report.child_name}'s week`;
  return (
    <article className="mx-auto grid w-full max-w-[460px] gap-3.5" data-testid="parent-report">
      <header>
        <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Weekly chess report{report.batch_name ? ` · ${report.batch_name}` : ""}
        </p>
        <h1 className="text-3xl font-extrabold leading-tight">{title}</h1>
      </header>
      {report.sections.map((section, i) => (
        <section
          key={`${section.kind}-${i}`}
          className={`grid gap-3 rounded-2xl border p-[18px] ${TONE[section.kind] || "bg-card"}`}
        >
          {section.eyebrow && (
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              {section.eyebrow}
            </p>
          )}
          {section.headline && (
            <h2 className={section.kind === "question" ? "text-2xl font-semibold" : "text-xl font-semibold"}>
              {section.kind === "question" ? `“${section.headline}”` : section.headline}
            </h2>
          )}
          {(section.lines || []).map((line, j) => (
            <p key={j} className={section.kind === "week" ? "text-lg" : section.kind === "note" ? "italic" : ""}>
              {line}
            </p>
          ))}
          {section.key && section.boards?.length > 0 && (
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
              {section.key.map(([colour, label]) => (
                <span key={label} className="inline-flex items-center gap-1.5">
                  <span className={`inline-block h-1 w-5 rounded ${KEY_COLOUR[colour]}`} />
                  {label}
                </span>
              ))}
            </div>
          )}
          {(section.boards || []).map((board, j) => (
            <ReportBoard key={j} board={board} />
          ))}
          {section.kind === "homework" && homeworkLink && (
            <a
              href={homeworkLink}
              className="inline-flex w-fit items-center rounded-full bg-foreground px-4 py-2 font-semibold text-background"
            >
              Play the homework
            </a>
          )}
        </section>
      ))}
      {report.footer && <p className="text-sm text-muted-foreground">{report.footer}</p>}
    </article>
  );
}
