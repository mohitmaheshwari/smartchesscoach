import React, { act } from "react";
import { createRoot } from "react-dom/client";

import Layout from "./Layout";


const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  Link: ({ children }) => <>{children}</>,
  useLocation: () => ({ pathname: "/home" }),
  useNavigate: () => mockNavigate,
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


describe("Layout notification polling", () => {
  let container;
  let root;

  beforeEach(() => {
    jest.useFakeTimers();
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockNavigate.mockReset();
    window.focus = jest.fn();
    window.Notification = jest.fn(() => ({ close: jest.fn(), onclick: null }));
    window.Notification.permission = "granted";

    global.fetch = jest.fn((url) => {
      if (url.includes("/notifications?")) {
        return Promise.resolve(response({
          unread_count: 1,
          notifications: [{ id: "notice-1", title: "Coach", message: "Your review is ready", read: false }],
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
});
