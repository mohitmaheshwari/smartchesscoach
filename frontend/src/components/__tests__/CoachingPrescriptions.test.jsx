/**
 * CoachingPrescriptions Component Tests
 *
 * Tests for:
 * - Loading, error, and empty states
 * - Prescription card rendering with progress
 * - Next recommendation display and interaction
 * - API integration
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import CoachingPrescriptions from "../CoachingPrescriptions";

// Mock the API
global.fetch = jest.fn();

const mockPrescriptionsResponse = {
  current_prescriptions: [
    {
      prescription_id: "pres-1",
      plan_id: "plan-1",
      plan_name: "Piece Safety Fundamentals",
      status: "active",
      issue_detected: "piece_safety",
      reasoning: "You left pieces hanging in 4 games this week",
      baseline_metric: 2.5,
      current_metric: 1.8,
      improvement_pct: 28,
      puzzles_completed: 12,
      puzzle_accuracy: 0.85,
      expected_completion_date: "2026-07-24",
      modules_completed: ["mod-1", "mod-2"],
    },
  ],
  total_active: 1,
  highest_priority: null,
};

const mockRecommendationResponse = {
  recommended_plan_id: "plan-2",
  plan_name: "Tactical Vision Advanced",
  reasoning:
    "Coach detected 3 occurrences of missed_tactic in your last 10 games.",
  issue_severity: "missed_tactic",
  occurrence_count: 3,
  trend: "stable",
  duration_weeks: 4,
  weekly_commitment_hours: 3,
  alternatives: [
    {
      plan_id: "plan-3",
      name: "King Safety Essentials",
      cognitive_gap: "king_safety",
    },
  ],
  urgency: "medium",
  current_prescriptions_count: 1,
  can_add_parallel: true,
};

describe("CoachingPrescriptions Component", () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  test("renders loading state initially", () => {
    fetch.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                json: () => Promise.resolve(mockPrescriptionsResponse),
              }),
            100
          )
        )
    );

    render(
      <BrowserRouter>
        <CoachingPrescriptions />
      </BrowserRouter>
    );

    // Check for skeleton loaders
    const spinners = document.querySelectorAll(".animate-pulse");
    expect(spinners.length).toBeGreaterThan(0);
  });

  test("renders active prescriptions", async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockPrescriptionsResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRecommendationResponse),
      });

    render(
      <BrowserRouter>
        <CoachingPrescriptions />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Piece Safety Fundamentals")).toBeInTheDocument();
    });

    expect(screen.getByText(/piece_safety/i)).toBeInTheDocument();
    expect(screen.getByText(/12 puzzles completed/i)).toBeInTheDocument();
  });

  test("renders next recommendation when available", async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockPrescriptionsResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRecommendationResponse),
      });

    render(
      <BrowserRouter>
        <CoachingPrescriptions />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText("Tactical Vision Advanced")
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/Coach's recommendation/i)).toBeInTheDocument();
  });

  test("renders empty state when no prescriptions", async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ current_prescriptions: [], total_active: 0 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(null),
      });

    render(
      <BrowserRouter>
        <CoachingPrescriptions />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/No active coaching plans yet/i)
      ).toBeInTheDocument();
    });
  });

  test("renders error state on fetch failure", async () => {
    fetch
      .mockRejectedValueOnce(new Error("Network error"))
      .mockRejectedValueOnce(new Error("Network error"));

    render(
      <BrowserRouter>
        <CoachingPrescriptions />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Error loading prescriptions/i)
      ).toBeInTheDocument();
    });
  });

  test("handles API response errors gracefully", async () => {
    fetch
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: "Server error" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

    render(
      <BrowserRouter>
        <CoachingPrescriptions />
      </BrowserRouter>
    );

    await waitFor(() => {
      // Component should still render empty state
      expect(
        screen.getByText(/No active coaching plans yet/i)
      ).toBeInTheDocument();
    });
  });
});
