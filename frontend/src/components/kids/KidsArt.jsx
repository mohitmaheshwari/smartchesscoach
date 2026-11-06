/**
 * The kids look's drawings, all in code: chess pieces with faces, Guru the owl
 * coach, stars and the class medal. No image files.
 */

const BASE = '<path d="M20 80 Q20 72 30 72 H70 Q80 72 80 80 V86 Q80 90 76 90 H24 Q20 90 20 86 Z"/>';
const SHAPES = {
  r: BASE + '<path d="M28 20 H38 V28 H45 V20 H55 V28 H62 V20 H72 V40 Q72 43 69 43 H31 Q28 43 28 40 Z"/><path d="M33 43 H67 L64 72 H36 Z"/>',
  b: BASE + '<circle cx="50" cy="13" r="5"/><path d="M50 18 C62 27 67 37 67 45 C67 53 60 58 50 58 C40 58 33 53 33 45 C33 37 38 27 50 18 Z"/><path d="M38 58 H62 L66 72 H34 Z"/>',
  n: BASE + '<path d="M32 72 C30 58 38 50 45 45 L35 47 C28 43 28 35 34 30 C41 21 53 15 63 17 L66 10 L70 19 C78 27 78 44 73 56 C71 62 69 67 68 72 Z"/>',
  p: BASE + '<circle cx="50" cy="32" r="13"/><path d="M38 46 H62 Q64 46 64 48 Q64 50 62 50 H38 Q36 50 36 48 Q36 46 38 46 Z"/><path d="M41 50 H59 L65 72 H35 Z"/>',
  q: BASE + '<path d="M27 30 L36 46 L44 26 L50 44 L56 26 L64 46 L73 30 L68 58 H32 Z"/><circle cx="27" cy="27" r="4.5"/><circle cx="44" cy="23" r="4.5"/><circle cx="56" cy="23" r="4.5"/><circle cx="73" cy="27" r="4.5"/><path d="M33 58 H67 L71 72 H29 Z"/>',
  k: BASE + '<rect x="46.5" y="6" width="7" height="18" rx="2"/><rect x="41" y="11.5" width="18" height="7" rx="2"/><path d="M33 46 C33 33 41 26 50 26 C59 26 67 33 67 46 Z"/><path d="M32 46 H68 L72 72 H28 Z"/>',
};
const FACE_AT = { r: [50, 56], b: [50, 42], n: [55, 34], p: [50, 32], q: [50, 64], k: [50, 56] };
export const PIECE_NAME = { k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" };

function face(x, y, scale, eye, glint) {
  return `<g transform="translate(${x} ${y}) scale(${scale})">
    <circle cx="-8" cy="0" r="4.2" fill="${eye}"/><circle cx="8" cy="0" r="4.2" fill="${eye}"/>
    <circle cx="-6.6" cy="-1.4" r="1.4" fill="${glint}"/><circle cx="9.4" cy="-1.4" r="1.4" fill="${glint}"/>
    <path d="M-5 7 Q0 11 5 7" fill="none" stroke="${eye}" stroke-width="2.6" stroke-linecap="round"/>
    <ellipse cx="-14" cy="6" rx="4" ry="2.4" fill="#ff9d8a" opacity=".55"/><ellipse cx="14" cy="6" rx="4" ry="2.4" fill="#ff9d8a" opacity=".55"/></g>`;
}

export function pieceMarkup(type, white = true) {
  const fill = white ? "#fff8ec" : "#33406a";
  const stroke = white ? "#2a3352" : "#141b33";
  const eye = white ? "#2a3352" : "#fff8ec";
  const [fx, fy] = FACE_AT[type] || FACE_AT.p;
  const scale = type === "n" ? 0.8 : type === "p" ? 0.85 : 1;
  return `<g fill="${fill}" stroke="${stroke}" stroke-width="4" stroke-linejoin="round">${SHAPES[type] || SHAPES.p}</g>
    <path d="M30 76 H70" stroke="${white ? "#ead9b8" : "#4a5a8c"}" stroke-width="4" stroke-linecap="round" opacity=".9"/>
    ${face(fx, fy, scale, eye, white ? "#fff" : "#33406a")}`;
}

export function Piece({ type, white = true, size }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: pieceMarkup(type, white) }} />
  );
}

const STAR_PATH = '<path d="M50 6 L62 36 L95 38 L69 59 L78 92 L50 74 L22 92 L31 59 L5 38 L38 36 Z" fill="#ffc23d" stroke="#e69a12" stroke-width="6" stroke-linejoin="round"/><path d="M50 20 L57 39 L77 40" fill="none" stroke="#fff3c4" stroke-width="6" stroke-linecap="round" opacity=".9"/>';
export function starMarkup() { return STAR_PATH; }
export function Star({ size, style }) {
  return <svg viewBox="0 0 100 100" width={size} height={size} style={style} aria-hidden="true" dangerouslySetInnerHTML={{ __html: STAR_PATH }} />;
}

const OWL = `<g class="bodyg">
  <path class="wing l" d="M24 58 C10 64 10 86 24 96 C30 84 32 72 30 60 Z" fill="#d98a3d" stroke="#1f2a44" stroke-width="3.5" stroke-linejoin="round"/>
  <path class="wing r" d="M96 58 C110 64 110 86 96 96 C90 84 88 72 90 60 Z" fill="#d98a3d" stroke="#1f2a44" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M28 40 L24 14 L44 28 C54 24 66 24 76 28 L96 14 L92 40 C100 54 100 80 92 96 C84 110 36 110 28 96 C20 80 20 54 28 40 Z" fill="#f2a65a" stroke="#1f2a44" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M40 74 C40 62 80 62 80 74 C80 96 72 104 60 104 C48 104 40 96 40 74 Z" fill="#fde7c4"/>
  <path d="M48 80 q4 4 8 0 M64 80 q4 4 8 0 M52 90 q4 4 8 0 M60 90 q4 4 8 0" fill="none" stroke="#e7b980" stroke-width="2.4" stroke-linecap="round"/>
  <g class="open-eyes">
    <circle cx="44" cy="50" r="15" fill="#fff" stroke="#1f2a44" stroke-width="3"/><circle cx="76" cy="50" r="15" fill="#fff" stroke="#1f2a44" stroke-width="3"/>
    <g class="pupil"><circle cx="46" cy="51" r="7" fill="#1f2a44"/><circle cx="48.5" cy="48.5" r="2.4" fill="#fff"/></g>
    <g class="pupil"><circle cx="74" cy="51" r="7" fill="#1f2a44"/><circle cx="76.5" cy="48.5" r="2.4" fill="#fff"/></g>
    <ellipse class="lid" cx="44" cy="43" rx="15.5" ry="15" fill="#f2a65a"/><ellipse class="lid" cx="76" cy="43" rx="15.5" ry="15" fill="#f2a65a"/>
  </g>
  <g class="happy-eyes" fill="none" stroke="#1f2a44" stroke-width="4" stroke-linecap="round"><path d="M34 52 Q44 40 54 52"/><path d="M66 52 Q76 40 86 52"/></g>
  <path class="think-brow" d="M64 32 L88 28" stroke="#1f2a44" stroke-width="4" stroke-linecap="round"/>
  <path d="M54 60 L66 60 L60 71 Z" fill="#ff9f43" stroke="#1f2a44" stroke-width="3" stroke-linejoin="round"/>
  <ellipse cx="32" cy="66" rx="5" ry="3" fill="#ff8f7a" opacity=".55"/><ellipse cx="88" cy="66" rx="5" ry="3" fill="#ff8f7a" opacity=".55"/>
  <path d="M46 108 v6 M52 108 v6 M68 108 v6 M74 108 v6" stroke="#ff9f43" stroke-width="4" stroke-linecap="round"/>
</g>`;

/** Guru the owl. mood: "" | "happy" | "cheer" | "think" | "wow". `bump` restarts the animation. */
export function Owl({ mood = "", bump = 0, small = false }) {
  return (
    <svg key={`${mood}-${bump}`} className={`kids-owl ${small ? "small" : ""} ${mood}`} viewBox="0 0 120 120"
      role="img" aria-label="Guru the owl, your coach" dangerouslySetInnerHTML={{ __html: OWL }} />
  );
}

// The class each badge belongs to, and the piece on it.
export const CLASS_ART = {
  rook: { piece: "r", badge: "Rook Rider" },
  bishop: { piece: "b", badge: "Bishop Explorer" },
  queen: { piece: "q", badge: "Queen's Champion" },
  knight: { piece: "n", badge: "Knight Jumper" },
  pawn: { piece: "p", badge: "Pawn Hero" },
  king: { piece: "k", badge: "King's Guard" },
  check: { piece: "k", badge: "Check Spotter" },
  checkmate: { piece: "q", badge: "Checkmate Master" },
};

export function Medal({ piece = "r", label }) {
  return (
    <div className="kids-medal">
      <div className="kids-rays" />
      <svg viewBox="0 0 170 170" width="170" height="170" role="img" aria-label={label}>
        <defs>
          <clipPath id="kids-mclip"><circle cx="85" cy="85" r="66" /></clipPath>
          <linearGradient id="kids-mg" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#ffe08a" /><stop offset=".55" stopColor="#ffc23d" /><stop offset="1" stopColor="#e69a12" />
          </linearGradient>
        </defs>
        <path d="M50 120 L35 165 L60 152 L72 170 L82 128 Z M120 120 L135 165 L110 152 L98 170 L88 128 Z" fill="#ff7a59" stroke="#1f2a44" strokeWidth="3" strokeLinejoin="round" />
        <circle cx="85" cy="85" r="74" fill="url(#kids-mg)" stroke="#1f2a44" strokeWidth="4" />
        <circle cx="85" cy="85" r="60" fill="#fffaf0" stroke="#e69a12" strokeWidth="4" />
        <g transform="translate(45 42) scale(.8)" dangerouslySetInnerHTML={{ __html: pieceMarkup(piece) }} />
        <g clipPath="url(#kids-mclip)"><rect className="shine" x="0" y="-20" width="26" height="220" fill="#fff" opacity=".55" /></g>
      </svg>
    </div>
  );
}

export function SpeakerIcon({ muted }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="#1f2a44" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 9h4l5-4v14l-5-4H4z" fill="#ffc23d" />
      {muted ? <path d="M17 9l5 6M22 9l-5 6" /> : <path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" />}
    </svg>
  );
}

export function World() {
  return (
    <div className="kids-world" aria-hidden="true">
      <div className="kids-cloud" style={{ top: "6%", width: 140, height: 44, animationDuration: "70s", animationDelay: "-20s" }} />
      <div className="kids-cloud" style={{ top: "16%", width: 90, height: 30, animationDuration: "52s", animationDelay: "-40s", opacity: 0.7 }} />
      <div className="kids-cloud" style={{ top: "28%", width: 180, height: 52, animationDuration: "95s", animationDelay: "-5s", opacity: 0.6 }} />
      <div className="kids-hill" style={{ left: "-10%", width: "60%", height: "18%" }} />
      <div className="kids-hill" style={{ right: "-15%", width: "70%", height: "22%", background: "#86cf78" }} />
    </div>
  );
}
