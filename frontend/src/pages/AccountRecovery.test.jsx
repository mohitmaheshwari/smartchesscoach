import { createRoot } from "react-dom/client";
import { act } from "react";
import Login from "@/pages/Login";
import ResetPassword from "@/pages/ResetPassword";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "http://test/api" }));
jest.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => false } }), { virtual: true });
jest.mock("@capacitor/browser", () => ({ Browser: { open: jest.fn() } }), { virtual: true });

let container; let root;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  window.history.pushState({}, "", "/login");
});
afterEach(() => { act(() => root.unmount()); container.remove(); delete global.fetch; });

const reply = (body, ok = true) => Promise.resolve({ ok, status: ok ? 200 : 400, json: async () => body });
const setValue = (el, value) => {
  const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  set.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
};
const submit = (form) => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

test("forgot password asks only for an email and gives the same answer either way", async () => {
  global.fetch = jest.fn(() => reply({ ok: true, signups_open: true }));
  await act(async () => { root.render(<Login />); });
  await act(async () => { container.querySelector("[data-testid=login-forgot]").click(); });
  expect(container.querySelector("[data-testid=login-password]")).toBeNull();
  expect(container.textContent).toContain("Reset your password");
  await act(async () => { setValue(container.querySelector("[data-testid=login-email]"), "a@example.com"); });
  await act(async () => { submit(container.querySelector("form")); });
  const call = global.fetch.mock.calls.find(([url]) => url.endsWith("/auth/forgot-password"));
  expect(JSON.parse(call[1].body)).toEqual({ email: "a@example.com" });
  expect(container.querySelector("[data-testid=login-sent]").textContent)
    .toBe("If that email has an account, a message is on its way.");
});

test("the coach link opens straight on sign-up with the academy words", async () => {
  window.history.pushState({}, "", "/login?signup=1&redirect_to=/academy");
  global.fetch = jest.fn(() => reply({ signups_open: true }));
  await act(async () => { root.render(<Login />); });
  expect(container.textContent).toContain("Create your account");
  expect(container.textContent).toContain("Next you set up your child or your academy.");
});

test("a reset link saves the new password with its token", async () => {
  window.history.pushState({}, "", "/reset-password?code=abc");
  global.fetch = jest.fn(() => reply({ ok: true }));
  await act(async () => { root.render(<ResetPassword />); });
  await act(async () => { setValue(container.querySelector("[data-testid=reset-password]"), "new-password"); });
  await act(async () => { submit(container.querySelector("form")); });
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({ token: "abc", password: "new-password" });
  expect(container.textContent).toContain("Password changed");
});

test("an expired link says so and how to go back", async () => {
  window.history.pushState({}, "", "/reset-password?code=old");
  global.fetch = jest.fn(() => reply({ detail: "This link has expired. Ask for a new one." }, false));
  await act(async () => { root.render(<ResetPassword />); });
  await act(async () => { setValue(container.querySelector("[data-testid=reset-password]"), "new-password"); });
  await act(async () => { submit(container.querySelector("form")); });
  expect(container.textContent).toContain("This link has expired.");
  expect(container.querySelector('a[href="/login"]')).not.toBeNull();
});

test("a link with no token cannot be submitted", async () => {
  window.history.pushState({}, "", "/reset-password");
  await act(async () => { root.render(<ResetPassword />); });
  expect(container.querySelector("[data-testid=reset-submit]").disabled).toBe(true);
});
