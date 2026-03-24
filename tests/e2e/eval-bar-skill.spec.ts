/**
 * Eval Bar and Skill Level E2E Tests
 * 
 * Tests:
 * 1. Evaluation bar visibility and display
 * 2. Coach skill level badge display
 * 3. Eval bar shows correct values
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://thinking-simulator.preview.emergentagent.com';

async function devLogin(page: Page) {
  await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
}

async function cleanupActiveSessions(page: Page) {
  try {
    const response = await page.request.get(`${BASE_URL}/api/coach/play/active`);
    if (response.ok()) {
      const data = await response.json();
      for (const session of data.active_sessions || []) {
        await page.request.post(`${BASE_URL}/api/coach/play/end`, {
          data: { session_id: session.session_id, reason: 'resigned' }
        });
      }
    }
  } catch (e) {
    // Ignore errors during cleanup
  }
}

async function waitForToastsToDisappear(page: Page) {
  await page.waitForFunction(() => {
    const toasts = document.querySelectorAll('[data-sonner-toast]');
    return toasts.length === 0;
  }, { timeout: 5000 }).catch(() => {});
}

test.describe('Evaluation Bar Display', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('should display eval bar when game starts', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    
    // Wait for game interface
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check eval bar is visible
    await expect(page.getByTestId('eval-bar')).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('should display eval text with numeric value', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check eval text is visible
    await expect(page.getByTestId('eval-text')).toBeVisible();
    
    // Eval text should contain a number or "0.0"
    const evalText = await page.getByTestId('eval-text').textContent();
    expect(evalText).toBeTruthy();
    // Should match a pattern like "0.0", "+0.5", "-1.2", or "M3" for mate
    expect(evalText).toMatch(/^[+-]?\d+\.?\d*$|^M\d+$/);
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('should have eval bar with valid dimensions', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check eval bar has proper dimensions (min-h-[400px] defined in component)
    const evalBar = page.getByTestId('eval-bar');
    await expect(evalBar).toBeVisible();
    
    // Get bounding box to verify it has visual dimensions
    const box = await evalBar.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.height).toBeGreaterThan(200); // Should be tall like a chess board
    expect(box!.width).toBeGreaterThan(10); // Should have some width (w-6 = 24px)
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('eval bar should have title attribute with evaluation', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check eval bar has title attribute
    const evalBar = page.getByTestId('eval-bar');
    await expect(evalBar).toHaveAttribute('title', /Evaluation:/);
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });
});

test.describe('Coach Skill Level Badge Display', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('should display coach skill level badge', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check for "Level X" badge in the coach info area
    // The badge shows "Level {session?.coach_skill_level || 8}"
    const levelBadge = page.getByText(/Level \d+/);
    await expect(levelBadge).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('skill level badge should show valid level (0-20)', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Find the Level badge
    const levelBadge = page.getByText(/Level \d+/).first();
    await expect(levelBadge).toBeVisible();
    
    // Extract the level number
    const text = await levelBadge.textContent();
    const match = text?.match(/Level (\d+)/);
    expect(match).toBeTruthy();
    
    const level = parseInt(match![1], 10);
    expect(level).toBeGreaterThanOrEqual(0);
    expect(level).toBeLessThanOrEqual(20);
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('coach info bar should show Coach label with skill badge', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check Coach label is visible
    await expect(page.getByText('Coach', { exact: true })).toBeVisible();
    
    // Check Level badge is nearby (in the same info bar)
    await expect(page.getByText(/Level \d+/)).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });
});

test.describe('Evaluation Bar Behavior', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('eval bar should show approximately equal position at start (white)', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Select white and start game
    await page.getByTestId('select-white').click({ force: true });
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Get eval text
    const evalText = await page.getByTestId('eval-text').textContent();
    
    // At starting position, eval should be close to 0 (±0.5 at most)
    if (evalText && !evalText.startsWith('M')) {
      const evalValue = parseFloat(evalText.replace('+', ''));
      expect(Math.abs(evalValue)).toBeLessThanOrEqual(0.5);
    }
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('eval bar persists during game', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Eval bar should be visible
    await expect(page.getByTestId('eval-bar')).toBeVisible();
    
    // Take a screenshot for verification
    await page.screenshot({ path: 'eval-bar-visible.jpeg', quality: 20, fullPage: false });
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
    
    // After game over, eval bar might still be visible
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
  });
});
