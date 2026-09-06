import React, { act } from "react";
import { createRoot } from "react-dom/client";

import MissionRunner from "./MissionRunner";


let mockMissionId = "mission-1";
let mockLocationState = {
  mission: { mission_id: "mission-1", focus_label: "Piece safety" },
  session_id: "session-1",
};
const mockNavigate = jest.fn();

jest.mock("@/App", () => ({ API: "https://api.test" }), { virtual: true });
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ missionId: mockMissionId }),
  useLocation: () => ({ state: mockLocationState }),
}), { virtual: true });
jest.mock("@/components/Layout", () => ({ children }) => <div>{children}</div>, { virtual: true });
jest.mock("@/components/CoachBoard", () => () => <div>board</div>, { virtual: true });
jest.mock("@/components/ui/premium", () => ({ ProgressRing: () => <div>progress</div> }), { virtual: true });


const response = (body) => ({ ok: true, json: () => Promise.resolve(body) });

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};


describe("MissionRunner route-owned loading", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    mockMissionId = "mission-1";
    mockLocationState = {
      mission: { mission_id: "mission-1", focus_label: "Piece safety" },
      session_id: "session-1",
    };
    mockNavigate.mockReset();
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

  test("uses matching route state once and never fetches today's mission", async () => {
    global.fetch = jest.fn((url) => Promise.resolve(response({
      positions: [],
      focus_label: url.includes("mission-1") ? "Piece safety" : "Unexpected",
    })));

    await act(async () => root.render(<MissionRunner user={{ user_id: "student-1" }} />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/missions/mission-1/positions",
      { credentials: "include" }
    );

    await act(async () => root.render(<MissionRunner user={{ user_id: "student-1" }} />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test("rejects stale route state and loads the mission for the new route", async () => {
    global.fetch = jest.fn((url) => {
      if (url === "https://api.test/missions/today") {
        return Promise.resolve(response({ mission_id: "mission-2", focus_label: "King safety" }));
      }
      return Promise.resolve(response({ positions: [] }));
    });

    await act(async () => root.render(<MissionRunner user={{ user_id: "student-1" }} />));
    await flush();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    mockMissionId = "mission-2";
    mockLocationState = {
      mission: { mission_id: "mission-1", focus_label: "Stale mission" },
      session_id: "stale-session",
    };
    await act(async () => root.render(<MissionRunner user={{ user_id: "student-1" }} />));
    await flush();

    expect(global.fetch.mock.calls.slice(1).map(([url]) => url)).toEqual([
      "https://api.test/missions/today",
      "https://api.test/missions/mission-2/positions",
    ]);
  });

  test("a superseded response cannot request positions for the old route", async () => {
    const oldToday = deferred();
    global.fetch = jest.fn((url) => {
      if (url === "https://api.test/missions/today") return oldToday.promise;
      return Promise.resolve(response({ positions: [] }));
    });
    mockLocationState = null;

    await act(async () => root.render(<MissionRunner user={{ user_id: "student-1" }} />));
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/missions/today",
      { credentials: "include" }
    );

    mockMissionId = "mission-2";
    mockLocationState = {
      mission: { mission_id: "mission-2", focus_label: "King safety" },
      session_id: "session-2",
    };
    await act(async () => root.render(<MissionRunner user={{ user_id: "student-1" }} />));
    await flush();
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/missions/mission-2/positions",
      { credentials: "include" }
    );

    oldToday.resolve(response({ mission_id: "mission-1" }));
    await flush();
    expect(global.fetch.mock.calls.map(([url]) => url)).not.toContain(
      "https://api.test/missions/mission-1/positions"
    );
  });

  test("fails closed when today's mission does not match the route", async () => {
    mockMissionId = "mission-2";
    mockLocationState = null;
    global.fetch = jest.fn(() => Promise.resolve(response({
      mission_id: "mission-3",
      focus_label: "Different mission",
    })));

    await act(async () => root.render(<MissionRunner user={{ user_id: "student-1" }} />));
    await flush();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.test/missions/today",
      { credentials: "include" }
    );
    expect(global.fetch.mock.calls.map(([url]) => url)).not.toContain(
      "https://api.test/missions/mission-3/positions"
    );
    expect(container.textContent).toContain("This mission is no longer active");
  });
});
