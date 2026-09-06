import React, { act } from "react";
import { createRoot } from "react-dom/client";

import AdminOpenings from "./AdminOpenings";
import Lab from "./Lab";


let mockGameId = "game-1";
const mockNavigate = jest.fn();

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ gameId: mockGameId }),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/GameDecryptionV5", () => () => <div>decryption</div>, { virtual: true });
jest.mock("@/pages/LabClassic", () => () => <div>classic</div>, { virtual: true });
jest.mock("@/components/Lab/CoachInsightPanel", () => () => <div>insight</div>, { virtual: true });
jest.mock("@monaco-editor/react", () => () => <div>editor</div>, { virtual: true });
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}), { virtual: true });
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }) => <button {...props}>{children}</button>,
}), { virtual: true });
jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }) => <span>{children}</span>,
}), { virtual: true });
jest.mock("@/components/ui/card", () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
  CardHeader: ({ children }) => <div>{children}</div>,
  CardTitle: ({ children }) => <div>{children}</div>,
}), { virtual: true });


const response = (body, ok = true) => ({
  ok,
  json: () => Promise.resolve(body),
});


describe("load and explicit-refetch callback identities", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockGameId = "game-1";
    mockNavigate.mockReset();
    global.fetch = jest.fn((url) => {
      if (url === "https://api.test/games/game-1" || url === "https://api.test/games/game-2") {
        return Promise.resolve(response({ user_plays_as: "white" }));
      }
      if (url === "https://api.test/analysis/game-1" || url === "https://api.test/analysis/game-2") {
        return Promise.resolve(response({}));
      }
      if (url === "https://api.test/admin/openings") {
        return Promise.resolve(response({ openings: [{ opening_key: "italian" }] }));
      }
      if (url === "https://api.test/admin/openings/italian") {
        return Promise.resolve(response({ feedback: { opening_name: "Italian Game" } }));
      }
      return Promise.resolve(response({}, false));
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete global.fetch;
  });

  const flush = () => act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  test("Lab loads once per game identity and not per unrelated rerender", async () => {
    await act(async () => root.render(<Lab user={{ username: "student" }} />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(2);

    await act(async () => root.render(<Lab user={{ username: "student" }} />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(2);

    mockGameId = "game-2";
    await act(async () => root.render(<Lab user={{ username: "student" }} />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(4);
    expect(global.fetch.mock.calls[2][0]).toBe("https://api.test/games/game-2");
  });

  test("Admin openings list is not fetched again when its first selection lands", async () => {
    await act(async () => root.render(<AdminOpenings user={{ role: "admin" }} />));
    await flush();

    expect(global.fetch.mock.calls.filter(
      ([url]) => url === "https://api.test/admin/openings"
    )).toHaveLength(1);

    await act(async () => root.render(<AdminOpenings user={{ role: "admin" }} />));
    await flush();
    expect(global.fetch.mock.calls.filter(
      ([url]) => url === "https://api.test/admin/openings"
    )).toHaveLength(1);
  });
});
