/**
 * Coach Play E2E Tests - P2 Play With Coach Steps 1-5
 * 
 * Tests the full game loop: setup → start → move → coach move → end → summary
 * Plus: Behavior extraction, CPR display, and Identity display
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://chess-coach-lab.preview.emergentagent.com';

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
    
    // Should show defeat message
    await expect(page.getByText('Defeat')).toBeVisible();
    
    // Should show new game button
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
    
    // Should show summary stats
    await expect(page.getByText('Total Moves')).toBeVisible();
  });

  test('should start new game after resignation', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start and resign
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    await page.getByTestId('resign-btn').click({ force: true });
    await expect(page.getByText('Defeat')).toBeVisible();
    
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

  test('should show Game Info and Move History panels', async ({ page }) => {
    await expect(page.getByText('Game Info')).toBeVisible();
    await expect(page.getByText('Move History')).toBeVisible();
    await expect(page.getByText('No moves yet')).toBeVisible();
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

  test('should display CPR score and interpretation on game end', async ({ page }) => {
    // Navigate and start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Resign to end the game
    await page.getByTestId('resign-btn').click({ force: true });
    
    // Wait for game to end
    await expect(page.getByText('Defeat')).toBeVisible({ timeout: 10000 });
    
    // CPR score should be displayed
    await expect(page.getByText('Cognitive Performance Rating')).toBeVisible({ timeout: 5000 });
    
    // Should have a CPR score badge (number between 0-100)
    const cprSection = page.locator('[class*="bg-primary"]').filter({ hasText: 'Cognitive Performance Rating' });
    await expect(cprSection).toBeVisible();
  });

  test('should display player identity on game end', async ({ page }) => {
    // Navigate and start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Resign to end the game
    await page.getByTestId('resign-btn').click({ force: true });
    
    // Wait for game to end
    await expect(page.getByText('Defeat')).toBeVisible({ timeout: 10000 });
    
    // Identity should be displayed (one of the valid identity labels)
    const validIdentityLabels = [
      'The Calculator', 'The Warrior', 'The Strategist', 'The Risk-Taker',
      'The Fortress', 'The Phoenix', 'The Improviser', 'The Perfectionist', 'The Learner'
    ];
    
    // Check for any of the identity labels
    let identityFound = false;
    for (const label of validIdentityLabels) {
      if (await page.getByText(label).isVisible({ timeout: 1000 }).catch(() => false)) {
        identityFound = true;
        break;
      }
    }
    expect(identityFound).toBe(true);
  });

  test('should show CPR interpretation text', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    await page.getByTestId('resign-btn').click({ force: true });
    await expect(page.getByText('Defeat')).toBeVisible({ timeout: 10000 });
    
    // Should have CPR interpretation (one of the valid interpretations)
    const interpretations = [
      'Elite cognitive control',
      'Strong mental game',
      'Developing well',
      'Room for improvement',
      'Significant issues'
    ];
    
    let interpretationFound = false;
    for (const interp of interpretations) {
      if (await page.getByText(interp, { exact: false }).isVisible({ timeout: 500 }).catch(() => false)) {
        interpretationFound = true;
        break;
      }
    }
    expect(interpretationFound).toBe(true);
  });

  test('should show sessions_analyzed count for identity', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    await page.getByTestId('resign-btn').click({ force: true });
    await expect(page.getByText('Defeat')).toBeVisible({ timeout: 10000 });
    
    // Should show session count text
    await expect(page.getByText(/Based on \d+ session/)).toBeVisible({ timeout: 5000 });
  });

  test('should show guardian status with interventions remaining', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Guardian status should be visible
    await expect(page.getByText(/Guardian active/)).toBeVisible();
    await expect(page.getByText(/intervention/)).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });
});

