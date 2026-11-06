/**
 * The weekly parent report: words and boards exactly as the server rendered
 * them (services/academy_service.render_report). Nothing is computed here, so
 * the coach's preview and the parent's page can never disagree.
 *
 * docs/academy_pilot_scope.md, section 2. Drawn in the kids look
 * (components/kids); the "kids-vars" wrapper carries its colours, so the
 * coach's preview on the staff page looks the same as the parent's page.
 */
import "@/components/kids/kids.css";
import KidsBoard from "@/components/kids/KidsBoard";
import { Owl } from "@/components/kids/KidsArt";

const KEY_COLOUR = { red: "#e2543a", green: "#2f9e6d" };
const BADGE = { habit: true, good: true, homework: true };

function ReportBoard({ board }) {
  const circles = board.ring ? [[board.ring, "red"]] : [];
  return (
    <figure className="kr-board" style={{ margin: 0 }}>
      <div style={{ width: "100%", maxWidth: 360 }}>
        <KidsBoard fen={board.fen} flip={board.orientation === "black"} arrows={board.arrows || []} circles={circles} coordinates={false} />
      </div>
      {board.caption && <figcaption>{board.caption}</figcaption>}
    </figure>
  );
}

export default function ParentReport({ report, homeworkLink }) {
  if (!report) return null;
  const title = `${report.child_name}'s week`;
  return (
    <article className="kids-vars kr" data-testid="parent-report">
      <header className="kr-head">
        <Owl small mood="happy" />
        <div style={{ minWidth: 0 }}>
          <p className="kids-eyebrow" style={{ margin: 0 }}>Weekly chess report{report.batch_name ? ` · ${report.batch_name}` : ""}</p>
          <h1>{title}</h1>
        </div>
      </header>
      {report.sections.map((section, i) => (
        <section key={`${section.kind}-${i}`} className={`kr-sec ${section.kind}`}>
          {/* The server's own eyebrow words; a badge on the coloured sections, a label on the rest. */}
          {section.eyebrow && (BADGE[section.kind]
            ? <span className="kr-badge">{section.eyebrow}</span>
            : <p className="kids-eyebrow">{section.eyebrow}</p>)}
          {section.headline && (
            <h2>{section.kind === "question" ? `“${section.headline}”` : section.headline}</h2>
          )}
          {(section.lines || []).map((line, j) => <p key={j}>{line}</p>)}
          {section.key && section.boards?.length > 0 && (
            <div className="kr-key">
              {section.key.map(([colour, label]) => (
                <span key={label}><i style={{ background: KEY_COLOUR[colour] }} />{label}</span>
              ))}
            </div>
          )}
          {(section.boards || []).map((board, j) => <ReportBoard key={j} board={board} />)}
          {section.kind === "homework" && homeworkLink && (
            <a href={homeworkLink} className="kids-btn" style={{ justifySelf: "start", textDecoration: "none" }}>Play the homework</a>
          )}
        </section>
      ))}
      {report.footer && <p className="kr-foot">{report.footer}</p>}
    </article>
  );
}
