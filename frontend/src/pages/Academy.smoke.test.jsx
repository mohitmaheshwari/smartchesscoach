import { createRoot } from "react-dom/client";
import { act } from "react";
import { AcademyBatch, AcademyStudent } from "@/pages/Academy";
import { FamilyConsent, FamilyReport, FamilyHomework, FamilyClassGame } from "@/pages/AcademyFamily";

let mockParams = {};
jest.mock("react-router-dom", () => ({
  useParams: () => mockParams,
  useNavigate: () => jest.fn(),
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="layout">{children}</div>,
  rememberAcademyStaff: () => {},
}));
jest.mock("@/components/LichessBoard", () => (props) => (
  <div data-testid="board" data-fen={props.fen} data-arrows={JSON.stringify(props.arrows || [])} />
));

const REPORT = {
  child_name: "Rohan", batch_name: "Saturday batch", coach_name: "Coach Priya",
  sections: [
    { kind: "week", lines: ["Rohan played most days this week.", "Wins and losses were about even."] },
    { kind: "habit", eyebrow: "The habit we saw this week",
      headline: "Rohan moves a piece to a square where it can be taken.",
      lines: ["The idea is often good. The new square is not checked first."],
      key: [["red", "Rohan's move"], ["green", "A safe move"]],
      boards: [{ fen: "8/8/8/8/8/8/8/K6k w - - 0 1", arrows: [["g6", "f4", "red"]], caption: "The knight moved here." }] },
    { kind: "question", eyebrow: "One question to ask at home", headline: "Before you move, can that piece be taken?", lines: [] },
  ],
  footer: "This report shows habits we can see in the games. It is not a score or a test.",
};

let container; let root;
beforeEach(() => { container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container); });
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

async function render(params, element, body) {
  mockParams = params;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body });
  await act(async () => { root.render(element); });
  await act(async () => { await Promise.resolve(); });
}

test("the parent sees the coach-approved report with its boards and no digits", async () => {
  await render({ token: "tok" }, <FamilyReport />, {
    status: "ready", report: REPORT, homework_link: "https://x/homework/h", stop_link: "https://x/consent/c",
  });
  const text = container.textContent;
  expect(text).toContain("Rohan's week");
  expect(text).toContain("Rohan moves a piece to a square where it can be taken.");
  expect(container.querySelectorAll("[data-testid=board]").length).toBe(1);
  expect(text).toContain("Stop the reports and delete the data");
  expect(global.fetch.mock.calls[0][0]).toBe("http://test/api/academy/report/tok");
});

test("a report not yet approved says it is on its way", async () => {
  await render({ token: "tok" }, <FamilyReport />, { status: "none", child_name: "Rohan" });
  expect(container.textContent).toContain("Rohan's report is on its way");
});

test("the consent page lists what we collect before the parent agrees", async () => {
  await render({ token: "tok" }, <FamilyConsent />, {
    status: "pending", academy: "Sunrise Chess", child_name: "Rohan",
    accounts: ["Lichess: rohan_plays"], points: ["We read the chess games your child plays online."],
  });
  const text = container.textContent;
  expect(text).toContain("Add Rohan to ChessGuru");
  expect(text).toContain("I am Rohan's parent or guardian.");
  expect(container.querySelector("#consent-agree")).not.toBeNull();
});

test("homework opens on the position with a start button", async () => {
  await render({ token: "tok" }, <FamilyHomework />, {
    status: "ready", child_name: "Rohan", fen: "1r6/1p1k1p1r/1Q1p3q/p7/1PP5/P7/2P2PP1/3RR1K1 w - - 2 31",
    color: "white", attempt: null, lines: ["You were winning here. Then one move let it slip."],
  });
  expect(container.textContent).toContain("Win it back");
  expect(container.querySelector("[data-testid=board]").dataset.fen).toContain("1r6/1p1k1p1r");
  expect(container.textContent).toContain("Start");
});

test("the class view shows each child and who needs the coach", async () => {
  await render({ batchId: "b1" }, <AcademyBatch />, {
    batch: { batch_id: "b1", name: "Saturday batch" }, academy: { academy_id: "a1", name: "Sunrise Chess" },
    summary: "One child needs you this week.",
    topic: { headline: "Check the new square before you move.", line: "Two children showed this habit this week." },
    rows: [
      { student_id: "k1", name: "Rohan", consent: "given", habit: "Moves a piece where it can be taken",
        trend: "same", trend_words: "About the same", games_words: "Many", homework: "not_started",
        homework_words: "Not started", needs_you: "Homework not started" },
      { student_id: "k2", name: "Ananya", consent: "pending", needs_you: "Waiting for the parent to agree" },
    ],
  });
  const text = container.textContent;
  expect(text).toContain("One child needs you this week.");
  expect(text).toContain("Check the new square before you move.");
  expect(text).toContain("Yes. Homework not started");
  expect(text).toContain("Yes. Waiting for the parent to agree");
});

test("a child waiting for consent shows the WhatsApp consent button, not a report", async () => {
  await render({ studentId: "k2" }, <AcademyStudent />, {
    student: { student_id: "k2", display_name: "Ananya", consent: { status: "pending" } },
    batch: { batch_id: "b1", name: "Saturday batch" }, academy: { academy_id: "a1", name: "Sunrise Chess" },
    row: {}, preview: null, links: { consent: "https://x/consent/c", report: "r", homework: "h" },
    whatsapp_consent: "https://wa.me/919876543210?text=Hello",
  });
  const link = [...container.querySelectorAll("a")].find((a) => a.textContent.includes("WhatsApp"));
  expect(link.getAttribute("href")).toBe("https://wa.me/919876543210?text=Hello");
  expect(container.querySelector("[data-testid=parent-report]")).toBeNull();
});

test("a class game shows whose move it is and lets the child resign", async () => {
  await render({ token: "tok" }, <FamilyClassGame />, {
    class_game_id: "cg1", fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    moves: [], ply: 0, turn: "white", status: "playing", my_color: "white",
    opponent_name: "Ananya", white_name: "Rohan", black_name: "Ananya", last_move: null,
  });
  const text = container.textContent;
  expect(text).toContain("You are playing Ananya");
  expect(text).toContain("Your move.");
  expect(text).toContain("Resign");
});
