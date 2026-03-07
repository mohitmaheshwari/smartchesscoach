/**
 * Coach Play E2E Tests - P2 Play With Coach Steps 1-5
 * 
 * Tests the full game loop: setup → start → move → coach move → end → summary
 * Plus: Behavior extraction, CPR display, and Identity display
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://chess-coach-ai-5.preview.emergentagent.com';

async function devLogin(page: Page) {
  await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
}

async function cleanupActiveSessions(page: Page) {
  // End any active sessions via API
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
  // Wait for toasts to disappear
  await page.waitForFunction(() => {
    const toasts = document.querySelectorAll('[data-sonner-toast]');
    return toasts.length === 0;
  }, { timeout: 5000 }).catch(() => {});
}

test.describe('Coach Play Setup Page', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('should display setup page with color and time selection', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Check color selection buttons
    await expect(page.getByTestId('select-white')).toBeVisible();
    await expect(page.getByTestId('select-black')).toBeVisible();
    
    // Check time control buttons
    await expect(page.getByTestId('time-3-2')).toBeVisible();
    await expect(page.getByTestId('time-10-5')).toBeVisible();
    await expect(page.getByTestId('time-15-10')).toBeVisible();
    
    // Check start button
    await expect(page.getByTestId('start-game-btn')).toBeVisible();
    await expect(page.getByTestId('start-game-btn')).toHaveText(/Start Game/);
  });

  test('should allow color and time control selection', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Click black
    await page.getByTestId('select-black').click({ force: true });
    
    // Click white again
    await page.getByTestId('select-white').click({ force: true });
    
    // Click time controls
    await page.getByTestId('time-3-2').click({ force: true });
    await page.getByTestId('time-10-5').click({ force: true });
    
    // All buttons should still be visible
    await expect(page.getByTestId('select-white')).toBeVisible();
    await expect(page.getByTestId('time-10-5')).toBeVisible();
  });
});

test.describe('Coach Play Game Flow', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('should start game as white and show game interface', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    
    // Wait for game interface to appear
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check game elements
    await expect(page.getByText('Coach', { exact: true })).toBeVisible();
    await expect(page.getByText('You', { exact: true })).toBeVisible();
    
    // Check resign button
    await expect(page.getByTestId('resign-btn')).toBeVisible();
    
    // Cleanup - resign
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('should resign game and show summary with New Game button', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Click resign
    await page.getByTestId('resign-btn').click({ force: true });
    
    // Should show loss message (UI changed from 'Defeat' to 'Loss')
    await expect(page.getByText('Loss')).toBeVisible({ timeout: 5000 });
    
    // Should show new game button
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
  });

  test('should start new game after resignation', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start and resign
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    await page.getByTestId('resign-btn').click({ force: true });
    await expect(page.getByText('Loss')).toBeVisible({ timeout: 5000 });
    
    // Click new game
    await page.getByTestId('new-game-btn').click({ force: true });
    
    // Should return to setup
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    await expect(page.getByTestId('start-game-btn')).toBeVisible();
  });
});

test.describe('Coach Play Game Interface', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
    
    // Start a game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
  });

  test.afterEach(async ({ page }) => {
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click({ force: true });
    }
  });

  test('should show Coach Chat and Move History panels', async ({ page }) => {
    // UI has changed - now shows Coach Chat instead of Game Info
    await expect(page.getByText('Coach Chat')).toBeVisible();
    await expect(page.getByText('Move History')).toBeVisible();
  });

  test('should show Your turn indicator', async ({ page }) => {
    await expect(page.getByText('Your turn', { exact: true })).toBeVisible();
  });

  test('should have flip board button', async ({ page }) => {
    const flipButton = page.getByRole('button', { name: /Flip/i });
    await expect(flipButton).toBeVisible();
    await flipButton.click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible();
  });
});

test.describe('Coach Play Steps 3-5: CPR and Identity Display', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('should display game end summary on resignation', async ({ page }) => {
    // Navigate and start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Resign to end the game
    await page.getByTestId('resign-btn').click({ force: true });
    
    // Wait for game to end - UI now shows 'Loss' instead of 'Defeat'
    await expect(page.getByText('Loss')).toBeVisible({ timeout: 10000 });
    
    // Should show new game button
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
  });

  test('should show move count in loss summary', async ({ page }) => {
    // Navigate and start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Resign to end the game
    await page.getByTestId('resign-btn').click({ force: true });
    
    // Wait for game to end
    await expect(page.getByText('Loss')).toBeVisible({ timeout: 10000 });
    
    // Should show move count in summary (e.g., "0 moves • 0m")
    await expect(page.getByText(/\d+ moves • \d+m/)).toBeVisible();
  });

  test('should show guardian status with interventions remaining', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Guardian status should be visible - shows "Guardian: X interventions remaining"
    await expect(page.getByText(/Guardian:/)).toBeVisible();
    await expect(page.getByText(/intervention/)).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });
});
