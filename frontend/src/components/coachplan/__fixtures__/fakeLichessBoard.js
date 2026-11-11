// Test stand-in for @/components/LichessBoard. jsdom has no layout, so
// chessground cannot map a click to a square; this renders the 64 squares as
// buttons named like "e4 white pawn" and forwards a click to onSquareClick,
// which is the only channel ReflectFlow uses. Rings and marks are exposed as
// class names so a test can see what the board was asked to draw.
//
//   jest.mock("@/components/LichessBoard", () => require("./__fixtures__/fakeLichessBoard").default);
const React = require("react");

const FILES = "abcdefgh";
const NAME = { k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn" };

function placement(fen) {
  const pos = {};
  String(fen || "").split(" ")[0].split("/").forEach((row, i) => {
    let f = 0;
    for (const c of row) {
      if (/\d/.test(c)) f += Number(c);
      else { pos[FILES[f] + (8 - i)] = c; f += 1; }
    }
  });
  return pos;
}

const FakeLichessBoard = React.forwardRef(function FakeLichessBoard(
  { fen, onSquareClick, circles = [], highlights = [], arrows = [], orientation },
  _ref,
) {
  const pos = placement(fen);
  const squares = [];
  for (let r = 8; r >= 1; r -= 1) {
    for (const f of FILES) {
      const sq = f + r;
      const p = pos[sq];
      const cls = [
        ...circles.filter(([s]) => s === sq).map(([, c]) => `ring ring-${c}`),
        ...highlights.filter((h) => h.square === sq).map((h) => `mark-${h.kind}`),
      ].join(" ");
      squares.push(React.createElement("button", {
        key: sq,
        type: "button",
        className: cls,
        "aria-label": `${sq}${p ? ` ${p === p.toUpperCase() ? "white" : "black"} ${NAME[p.toLowerCase()]}` : ""}`,
        onClick: () => onSquareClick && onSquareClick(sq),
      }));
    }
  }
  return React.createElement("div", {
    "data-testid": "lichess-board",
    "data-orientation": orientation,
    "data-arrows": JSON.stringify(arrows),
  }, squares);
});

module.exports = { __esModule: true, default: FakeLichessBoard };
