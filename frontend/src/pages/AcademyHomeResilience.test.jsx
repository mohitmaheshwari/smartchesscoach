/**
 * /academy must not white-screen because a reply was not the shape it wanted.
 *
 * 2026-11-27, live: the page crashed with "Cannot read properties of
 * undefined (reading 'length')" and showed an error boundary instead of the
 * academy. The chain was:
 *
 *   1. /academy2 (the set-up preview) replaces window.fetch with a stub, and
 *      its cleanup did not put the real one back.
 *   2. The finish screen's "Open my academy" client-navigates to /academy,
 *      unmounting the preview and leaving the stub installed.
 *   3. The stub answered every unknown path with {}.
 *   4. AcademyHome read `state.data.academies.length` off that {}.
 *
 * The leak is fixed where it was made, but step 4 is a fault of its own:
 * `call()` in Academy.jsx turns ANY unparseable 200 body into {} and returns
 * it as data, so a proxy error page, a truncated response or a future API
 * change lands here the same way. A page should degrade, not disappear.
 */

import { createRoot } from "react-dom/client";
import { act } from "react";
import { AcademyHome } from "@/pages/Academy";

jest.mock("react-router-dom", () => ({
  useParams: () => ({}),
  useNavigate: () => jest.fn(),
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@/components/Layout", () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="layout">{children}</div>,
  rememberAcademyStaff: () => {},
}));
// Academy.jsx pulls in ParentReport -> LichessBoard -> chessground, which
// jest cannot parse. Same mock the sibling smoke test uses.
jest.mock("@/components/LichessBoard", () => (props) => (
  <div data-testid="board" data-fen={props.fen} />
));

let container;
let root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  delete global.fetch;
});

const renderWith = async (body, coaches) => {
  // Per path. One body for every request is how the first version of this
  // test accidentally found the SAME bug a second time, in CoachesThisWeek.
  global.fetch = jest.fn((url) =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(String(url).includes("/coaches") ? (coaches || {}) : body),
    })
  );
  await act(async () => { root.render(<AcademyHome />); });
  await act(async () => { await Promise.resolve(); });
};

test("survives a reply with no academies key at all", async () => {
  // The exact body that crashed it: the stub's {} fallback.
  await renderWith({});

  expect(container.textContent).not.toMatch(/failed to render/i);
  // Falls back to the empty state, which is the truthful reading of "we were
  // not told about any academy".
  expect(container.querySelector('[data-testid="academy-start-setup"]')).not.toBeNull();
});

test("survives a reply that is not even an object of the right shape", async () => {
  await renderWith({ detail: "Something else entirely" });

  expect(container.textContent).not.toMatch(/failed to render/i);
});

test("still renders a real academy normally", async () => {
  // The guard must not have turned the page into the empty state for
  // everybody -- a fix that breaks the working case is not a fix.
  await renderWith({
    academies: [
      {
        academy_id: "acad_1",
        name: "Knight School Pune",
        city: "Pune",
        my_role: "owner",
        batches: [{ batch_id: "b1", name: "Saturday batch", coach_name: "Coach Priya", children: 8 }],
        staff: [{ user_id: "u1", name: "Priya Nair", role: "owner" }],
      },
    ],
  });

  expect(container.textContent).toContain("Knight School Pune");
  expect(container.textContent).toContain("Saturday batch");
  expect(container.querySelector('[data-testid="academy-start-setup"]')).toBeNull();
});
