import React, { act } from "react";
import { createRoot } from "react-dom/client";

import Layout from "./Layout";


let mockCurrentNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  Link: ({ children }) => <>{children}</>,
  useLocation: () => ({ pathname: "/home" }),
  useNavigate: () => mockCurrentNavigate,
}), { virtual: true });
jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children }) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
}), { virtual: true });
jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("@/context/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: jest.fn() }),
}), { virtual: true });
jest.mock("@/lib/personalCurriculum", () => ({
  CURRICULUM_ROUTES: { gameReview: "/game-review" },
  loadPersonalCurriculum: () => Promise.resolve({ enabled: false }),
}), { virtual: true });
jest.mock("@/lib/experience", () => ({ EXPERIENCE_V1_ENABLED: false }), { virtual: true });
jest.mock("@/lib/analytics", () => ({ resetAnalyticsContext: jest.fn() }), { virtual: true });
jest.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => false } }), { virtual: true });
jest.mock("framer-motion", () => ({
  motion: { div: ({ children, ...props }) => <div {...props}>{children}</div> },
  AnimatePresence: ({ children }) => <>{children}</>,
}));


const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};


describe("Layout notification polling", () => {
  let container;
  let root;

  beforeEach(() => {
    jest.useFakeTimers();
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockCurrentNavigate = jest.fn();
    window.focus = jest.fn();
    window.Notification = jest.fn(() => ({ close: jest.fn(), onclick: null }));
    window.Notification.permission = "granted";

    global.fetch = jest.fn((url) => {
      if (url.includes("/notifications?")) {
        return Promise.resolve(response({
          unread_count: 1,
          notifications: [{ id: "notice-1", title: "Coach", message: "Your review is ready", read: false, action_url: "/game/1" }],
        }));
      }
      if (url.endsWith("/loss-streak-status")) {
        return Promise.resolve(response({ show_plateau_breaker: false, consecutive_losses: 0 }));
      }
      if (url.endsWith("/reflect/pending/count")) return Promise.resolve(response({ count: 0 }));
      if (url.endsWith("/coach/fresh-loss")) return Promise.resolve(response({ has_fresh_loss: false }));
      return Promise.resolve(response({}));
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    jest.useRealTimers();
    delete global.fetch;
    delete window.Notification;
  });

  const flush = () => act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });

  test("an unread-count update does not restart or immediately duplicate the poll", async () => {
    await act(async () => root.render(
      <Layout user={{ user_id: "user-1", name: "Student" }}>
        <div>Page</div>
      </Layout>
    ));
    await flush();

    const notificationCalls = () => global.fetch.mock.calls
      .filter(([url]) => url.includes("/notifications?"));

    expect(notificationCalls()).toHaveLength(1);
    expect(window.Notification).toHaveBeenCalledTimes(1);

    await act(async () => {
      jest.advanceTimersByTime(29999);
      await Promise.resolve();
    });
    expect(notificationCalls()).toHaveLength(1);

    await act(async () => {
      jest.advanceTimersByTime(1);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(notificationCalls()).toHaveLength(2);
    expect(window.Notification).toHaveBeenCalledTimes(1);
  });

  test("navigation identity changes neither restart polling nor stale notification routing", async () => {
    await act(async () => root.render(
      <Layout user={{ user_id: "user-1", name: "Student" }}><div>Page</div></Layout>
    ));
    await flush();
    const notificationGets = () => global.fetch.mock.calls.filter(([url]) => url.includes("/notifications?"));
    expect(notificationGets()).toHaveLength(1);

    const latestNavigate = jest.fn();
    mockCurrentNavigate = latestNavigate;
    await act(async () => root.render(
      <Layout user={{ user_id: "user-1", name: "Student" }}><div>Other page</div></Layout>
    ));
    await flush();
    expect(notificationGets()).toHaveLength(1);

    window.Notification.mock.results[0].value.onclick();
    expect(latestNavigate).toHaveBeenCalledWith("/game/1");
  });

  test("mark all read invalidates an older in-flight unread response", async () => {
    const stalePoll = deferred();
    let notificationGetCount = 0;
    global.fetch = jest.fn((url) => {
      if (url.includes("/notifications?")) {
        notificationGetCount += 1;
        if (notificationGetCount === 2) return stalePoll.promise;
        return Promise.resolve(response({
          unread_count: 1,
          notifications: [{ id: "notice-1", title: "Coach", message: "Review ready", read: false }],
        }));
      }
      if (url.endsWith("/notifications/read")) return Promise.resolve(response({ ok: true }));
      if (url.endsWith("/loss-streak-status")) return Promise.resolve(response({ show_plateau_breaker: false }));
      if (url.endsWith("/reflect/pending/count")) return Promise.resolve(response({ count: 0 }));
      if (url.endsWith("/coach/fresh-loss")) return Promise.resolve(response({ has_fresh_loss: false }));
      return Promise.resolve(response({}));
    });

    await act(async () => root.render(
      <Layout user={{ user_id: "user-1", name: "Student" }}><div>Page</div></Layout>
    ));
    await flush();
    await act(async () => { jest.advanceTimersByTime(30000); await Promise.resolve(); });

    const markRead = Array.from(container.querySelectorAll("button"))
      .find((button) => button.textContent.includes("Mark all read"));
    expect(markRead).toBeTruthy();
    await act(async () => markRead.click());
    await flush();

    stalePoll.resolve(response({
      unread_count: 1,
      notifications: [{ id: "notice-1", title: "Coach", message: "Stale unread", read: false }],
    }));
    await flush();

    expect(window.Notification).toHaveBeenCalledTimes(1);
    expect(container.textContent).not.toContain("Mark all read");
    expect(container.textContent).not.toContain("Stale unread");
  });
});
