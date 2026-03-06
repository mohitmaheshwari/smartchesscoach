import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://self-learning-coach.preview.emergentagent.com';

test.describe('PostLossRecoveryCard Component', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('Post-loss message API endpoint returns valid data', async ({ page }) => {
    // Get a game ID from dashboard stats
    const statsResponse = await page.request.get(`${BASE_URL}/api/dashboard-stats`);
    expect(statsResponse.ok()).toBeTruthy();
    
    const stats = await statsResponse.json();
    const analyzedList = stats.analyzed_list || [];
    
    if (analyzedList.length === 0) {
      test.skip();
      return;
    }
    
    const gameId = analyzedList[0].game_id;
    
    // Test post-loss message endpoint
    const messageResponse = await page.request.get(
      `${BASE_URL}/api/rewards/post-loss-message?game_id=${gameId}`
    );
    expect(messageResponse.ok()).toBeTruthy();
    
    const message = await messageResponse.json();
    
    // Validate response structure
    expect(message).toHaveProperty('headline');
    expect(message).toHaveProperty('subtext');
    expect(message).toHaveProperty('focus_label');
    expect(message).toHaveProperty('cta_text');
    expect(message).toHaveProperty('minutes');
    expect(typeof message.minutes).toBe('number');
  });

  test('Post-loss message contains appropriate recovery copy', async ({ page }) => {
    const statsResponse = await page.request.get(`${BASE_URL}/api/dashboard-stats`);
    const stats = await statsResponse.json();
    const analyzedList = stats.analyzed_list || [];
    
    if (analyzedList.length === 0) {
      test.skip();
      return;
    }
    
    const gameId = analyzedList[0].game_id;
    
    const messageResponse = await page.request.get(
      `${BASE_URL}/api/rewards/post-loss-message?game_id=${gameId}`
    );
    const message = await messageResponse.json();
    
    // Headline should be recovery-focused
    expect(message.headline).toBeTruthy();
    expect(message.headline.length).toBeGreaterThan(0);
    
    // CTA should mention minutes
    expect(message.cta_text).toContain(String(message.minutes));
    
    // Focus label should exist
    expect(message.focus_label).toBeTruthy();
  });
});

test.describe('Missions API Endpoints', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
  });

  test('Mission history endpoint returns mission list', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/missions/history`);
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data).toHaveProperty('missions');
    expect(Array.isArray(data.missions)).toBeTruthy();
  });

  test('Mission focus mastery endpoint returns data', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/missions/focus-mastery`);
    expect(response.ok()).toBeTruthy();
  });

  test('Mission step recording works correctly', async ({ page }) => {
    // Get today's mission
    const missionResponse = await page.request.get(`${BASE_URL}/api/missions/today`);
    expect(missionResponse.ok()).toBeTruthy();
    
    const mission = await missionResponse.json();
    const missionId = mission.mission_id;
    
    // Start mission
    const startResponse = await page.request.post(`${BASE_URL}/api/missions/${missionId}/start`);
    expect(startResponse.ok()).toBeTruthy();
    
    // Record a step
    const stepResponse = await page.request.post(
      `${BASE_URL}/api/missions/${missionId}/step`,
      {
        data: {
          step_type: 'drill_result',
          payload: {
            step_index: 0,
            correct: true,
            time_taken_ms: 3000
          }
        }
      }
    );
    expect(stepResponse.ok()).toBeTruthy();
  });
});

test.describe('Dashboard Mission Integration', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('Dashboard stats include game counts', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/dashboard-stats`);
    expect(response.ok()).toBeTruthy();
    
    const stats = await response.json();
    expect(stats).toHaveProperty('total_games');
    expect(stats).toHaveProperty('analyzed_games');
    expect(stats.total_games).toBeGreaterThan(0);
  });

  test('Dashboard shows mission card with correct structure', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for dashboard to load
    await expect(page.getByTestId('dashboard-page')).toBeVisible({ timeout: 15000 });
    
    // Check for daily mission card
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 10000 });
    
    // Validate card content
    await expect(missionCard.getByText("Today's Mission")).toBeVisible();
    
    // Check for focus label
    await expect(missionCard.getByText(/Focus:/)).toBeVisible();
    
    // Check for Start Mission or Continue button
    const actionButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await expect(actionButton).toBeVisible();
  });

  test('Mission card displays estimated time', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    // Should show time estimate (e.g., "7 min")
    await expect(missionCard.getByText(/\d+ min/)).toBeVisible();
  });
});
