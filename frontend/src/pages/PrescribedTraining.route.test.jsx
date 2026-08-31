/**
 * Guards the /training?personalized=1 route against render-time crashes.
 *
 * 2026-08-31: the inner-product redesign added `user={user}` inside
 * PrescribedTraining while the component still took NO props. `user` was
 * undeclared, every render threw a ReferenceError, and the route rendered
 * blank in production.
 *
 * All 71 frontend tests passed on that code, because
 * PersonalizedLessonWorkspace.test.jsx renders the CHILD directly with its
 * own props, and nothing exercised the parent's call site. This file tests
 * the call site.
 *
 * The router is mocked rather than wrapped in MemoryRouter: react-router-dom
 * v7 ships ESM exports that this Jest config cannot resolve, and the subject
 * under test is the component's props contract, not routing.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
  // Constructed inside the factory: jest.mock() may not close over
  // out-of-scope variables.
  useSearchParams: () => [
    new URLSearchParams(
      "personalized=1&kind=endgame&lesson=king_and_pawn%2Fkey_squares"
    ),
    jest.fn(),
  ],
  useParams: () => ({}),
  Link: ({ children }) => children,
}), { virtual: true });

jest.mock("@/App", () => ({ API: "https://api.test/api" }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => ({ children }) => children }),
}), { virtual: true });
jest.mock("@/components/LichessBoard", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/PICPieceSafetyLesson", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/components/training/CanonicalTrainingAssignment", () => ({
  __esModule: true, default: () => null,
}), { virtual: true });
jest.mock("@/hooks/useMoveCaption", () => ({
  __esModule: true, default: () => ({}),
}), { virtual: true });

// The workspace does its own network work; this test is about the parent.
jest.mock("@/components/training/PersonalizedLessonWorkspace", () => ({
  __esModule: true,
  default: ({ user }) => (
    <div data-testid="workspace">{user ? "with-user" : "no-user"}</div>
  ),
}), { virtual: true });

const PrescribedTraining = require("./PrescribedTraining").default;

let container;
let root;

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  window.posthog = { capture: jest.fn() };
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: false, json: () => Promise.resolve({}) })
  );
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  delete window.posthog;
  delete global.fetch;
});

test("the personalized lesson route renders without throwing", () => {
  expect(() =>
    act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />))
  ).not.toThrow();
});

test("the personalized route is not blank", () => {
  act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />));
  expect(container.innerHTML.length).toBeGreaterThan(0);
});

test("the user prop reaches the workspace", () => {
  act(() => root.render(<PrescribedTraining user={{ id: "u1" }} />));
  expect(container.textContent).toContain("with-user");
});

test("a missing user prop degrades instead of blanking the route", () => {
  // ProtectedRoute always supplies one, but absence must not throw.
  expect(() => act(() => root.render(<PrescribedTraining />))).not.toThrow();
  expect(container.innerHTML.length).toBeGreaterThan(0);
});

test("PrescribedTraining declares a props parameter", () => {
  // The regression was a propless signature beside a `user={user}` usage.
  expect(PrescribedTraining.length).toBeGreaterThan(0);
});
