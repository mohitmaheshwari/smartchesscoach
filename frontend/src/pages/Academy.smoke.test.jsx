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

test("the class view shows each child's coach plan and approves a draft", async () => {
  await render({ batchId: "b1" }, <AcademyBatch />, {
    batch: { batch_id: "b1", name: "Saturday batch" }, academy: { academy_id: "a1", name: "Sunrise Chess" },
    summary: "", topic: null,
    rows: [
      { student_id: "k1", name: "Rohan", consent: "given", habit: "-", trend_words: "-", games_words: "-",
        homework_words: "-", plan: { status: "draft", problem_label: "Leaving a piece where it can be taken",
          cause_words: "Not looking: finds it when asked" } },
    ],
  });
  expect(container.textContent).toContain("Leaving a piece where it can be taken");
  expect(container.textContent).toContain("Approve all drafts");
  const approve = [...container.querySelectorAll("[data-testid=plan-cell] button")].find((b) => b.textContent === "Approve");
  await act(async () => { approve.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  const call = global.fetch.mock.calls.find((c) => String(c[0]).endsWith("/academy/student/k1/plan/approve"));
  expect(call[1].method).toBe("POST");
});

test("one child's coach plan shows the problem, reflections, cause, sign and rule", async () => {
  await render({ studentId: "k1" }, <AcademyStudent />, {
    student: { student_id: "k1", display_name: "Rohan", consent: { status: "given" } },
    batch: { batch_id: "b1", name: "Saturday batch" }, academy: { academy_id: "a1", name: "Sunrise Chess", kind: "academy" },
    row: { habit: "-", trend_words: "-", homework_words: "-" }, preview: null, week_built_at: "x",
    links: { consent: "c", report: "r", homework: "h", class: "k" },
    plan: {
      status: "draft",
      problem: { quality_id: "gap:piece_safety:destination_safety_exact", label: "Leaving a piece where it can be taken", games_lost: 2, games: 6, moments: 4 },
      runners_up: [{ label: "Missed forks", games_lost: 1, moments: 2 }],
      moments: [
        { key: "m1", san: "Qf3", date: "2026-11-05", kind: "landing", taker_words: "His knight on e5, a knight jump", done: true,
          answers: { wanted: ["bring my queen into play"], found_when_asked: true, seen_in_game: "no" } },
        { key: "m2", san: "Rc7", date: "2026-10-31", kind: "landing", taker_words: "His bishop on h2, a long line", done: false },
      ],
      cause: { kind: "not_looking", words: "Mostly not looking: finds the piece when asked." },
      warning_sign: { title: "The three looks", text: "Before any piece lands: pieces close by, knight jumps, long lines to the edge." },
      rule: { id: "three_looks", text: "Do the three looks before every move." },
      rule_options: [{ id: "three_looks", text: "Do the three looks before every move." }, { id: "knight_look", text: "Look for knight jumps first." }],
      last_check: null,
    },
  });
  const text = container.textContent;
  expect(text).toContain("Costliest problem");
  expect(text).toContain("Lost 2 games that were level or better");
  expect(text).toContain("Found it when asked: yes");
  expect(text).toContain("In the game: didn't see it");
  expect(text).toContain("Not reflected yet.");
  expect(text).toContain("Mostly not looking");
  expect(container.querySelector("select#plan-rule-k1")).not.toBeNull();
  expect(text).toContain("Approve and send");
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
