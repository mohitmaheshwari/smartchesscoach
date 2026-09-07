/**
 * ChessLoader — the one loading animation for ChessGuru.
 *
 * A pawn promotes: pawn → knight → bishop → rook → queen, over and over, on a
 * board square that breathes under it. The metaphor is the product's whole
 * premise — you start as a pawn and you get promoted — so a wait becomes a
 * statement instead of a spinner.
 *
 * Pieces are inline SVG built from primitives rather than a font, because
 * Unicode chess glyphs render differently on every platform and would look
 * broken on exactly the machine we least control.
 *
 * Everything is theme-aware via currentColor, and the whole sequence collapses
 * to a single static queen under prefers-reduced-motion (keyframes live in
 * index.css) so it never becomes a vestibular problem.
 */

const SIZES = {
  sm: { box: 34, label: "text-xs" },
  md: { box: 60, label: "text-sm" },
  lg: { box: 92, label: "text-base" },
};

// Every piece shares a plinth so the silhouette stays planted while the top
// morphs — without it the promotion reads as five unrelated shapes.
const Base = () => (
  <>
    <rect x="5.2" y="19.1" width="13.6" height="2.9" rx="1.3" />
    <path d="M7.4 19.1 L8.7 16.1 H15.3 L16.6 19.1 Z" />
  </>
);

const Pawn = () => (
  <g>
    <circle cx="12" cy="6.6" r="3.05" />
    <path d="M9.5 10.2 H14.5 L15.3 16.1 H8.7 Z" />
    <Base />
  </g>
);

const Knight = () => (
  <g>
    <path d="M13.4 3.3 L10.6 5.1 L10.9 6.6 C9.2 7.6 7.9 9.4 7.6 11.9 L9.4 12.7
             L10.4 11.2 L11.2 12.4 C12.9 11.1 13.9 11.2 14.6 12.2
             C15.4 13.4 15.6 14.7 15.4 16.1 H9.1 L8.9 16.1 H15.3
             C16.4 13.1 16.9 10.2 16.2 7.6 C15.8 5.9 14.8 4.3 13.4 3.3 Z" />
    <Base />
  </g>
);

const Bishop = () => (
  <g>
    <circle cx="12" cy="4.5" r="1.5" />
    <path d="M12 6.1 C15 7.9 16.2 10.6 15.4 13.2 L15.3 16.1 H8.7 L8.6 13.2
             C7.8 10.6 9 7.9 12 6.1 Z" />
    <rect x="11.4" y="8.4" width="1.2" height="4.2" rx="0.6" fill="#fff" opacity="0.5" />
    <Base />
  </g>
);

const Rook = () => (
  <g>
    <path d="M7.2 3.6 H9.6 V5.4 H11 V3.6 H13 V5.4 H14.4 V3.6 H16.8 V8.1
             L15.4 9.4 L15.3 16.1 H8.7 L8.6 9.4 L7.2 8.1 Z" />
    <Base />
  </g>
);

const Queen = () => (
  <g>
    <circle cx="6.4" cy="4.6" r="1.35" />
    <circle cx="12" cy="3.3" r="1.5" />
    <circle cx="17.6" cy="4.6" r="1.35" />
    <path d="M6.4 5.6 L8.9 10.4 H15.1 L17.6 5.6 L15.4 9 L12 4.6 L8.6 9 Z" />
    <path d="M8.9 11.2 H15.1 L15.3 16.1 H8.7 Z" />
    <Base />
  </g>
);

const SEQUENCE = [Pawn, Knight, Bishop, Rook, Queen];

const ChessLoader = ({
  size = "md",
  label,
  fullPage = false,
  className = "",
  "data-testid": testId = "chess-loader",
}) => {
  const { box, label: labelSize } = SIZES[size] || SIZES.md;

  const loader = (
    <div
      className={`cg-chessloader flex flex-col items-center justify-center gap-3 ${className}`}
      role="status"
      aria-live="polite"
      data-testid={testId}
    >
      <div className="cg-chessloader__stage" style={{ width: box, height: box }}>
        <span className="cg-chessloader__square" aria-hidden="true" />
        {SEQUENCE.map((Piece, i) => (
          <svg
            key={i}
            className="cg-chessloader__piece"
            style={{ animationDelay: `${i * 0.86}s` }}
            viewBox="0 0 24 24"
            width={box}
            height={box}
            fill="currentColor"
            aria-hidden="true"
          >
            <Piece />
          </svg>
        ))}
      </div>
      {label ? (
        <p className={`${labelSize} text-muted-foreground text-center`}>{label}</p>
      ) : null}
      <span className="sr-only">{label || "Loading"}</span>
    </div>
  );

  if (!fullPage) return loader;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-6">
      {loader}
    </div>
  );
};

export default ChessLoader;
