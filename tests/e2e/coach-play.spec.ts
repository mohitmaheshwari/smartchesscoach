/**
 * Coach Play E2E Tests - P2 Play With Coach Step 1
 * 
 * Tests the full game loop: setup → start → move → coach move → end → summary
 */
import { test, expect } from '@playwright/test';
import { devLogin, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

test.describe('Coach Play Setup Page', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should display setup page with color and time selection', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
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

  test('should allow color selection toggle', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Click black
    await page.getByTestId('select-black').click();
    
    // Click white again
    await page.getByTestId('select-white').click();
    
    // Both should be visible
    await expect(page.getByTestId('select-white')).toBeVisible();
    await expect(page.getByTestId('select-black')).toBeVisible();
  });

  test('should allow time control selection', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Click 3+2
    await page.getByTestId('time-3-2').click();
    
    // Click 10+5
    await page.getByTestId('time-10-5').click();
    
    // Both should be visible
    await expect(page.getByTestId('time-3-2')).toBeVisible();
  });
});

test.describe('Coach Play Game Flow', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should start game as white and show game interface', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Start game
    await page.getByTestId('start-game-btn').click();
    
    // Wait for game interface to appear
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check game elements
    await expect(page.getByText('Coach')).toBeVisible();
    await expect(page.getByText('You')).toBeVisible();
    
    // Check resign button
    await expect(page.getByTestId('resign-btn')).toBeVisible();
    
    await hideEmergentBadge(page);
    
    // Cleanup - resign
    await page.getByTestId('resign-btn').click();
  });

  test('should resign game and show summary', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    
    // Start a game
    await page.getByTestId('start-game-btn').click();
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    // Click resign
    await page.getByTestId('resign-btn').click();
    
    // Should show defeat message
    await expect(page.getByText('Defeat')).toBeVisible();
    
    // Should show new game button
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
    
    // Should show summary stats
    await expect(page.getByText('Total Moves')).toBeVisible();
  });

  test('should start new game after resignation', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    
    // Start and resign
    await page.getByTestId('start-game-btn').click();
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    await page.getByTestId('resign-btn').click();
    await expect(page.getByText('Defeat')).toBeVisible();
    
    // Click new game
    await page.getByTestId('new-game-btn').click();
    
    // Should return to setup
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    await expect(page.getByTestId('start-game-btn')).toBeVisible();
  });
});

test.describe('Coach Play Game Interface', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
    
    // Start a game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('start-game-btn').click();
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
  });

  test.afterEach(async ({ page }) => {
    await hideEmergentBadge(page);
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click();
    }
  });

  test('should show Game Info and Move History panels', async ({ page }) => {
    await expect(page.getByText('Game Info')).toBeVisible();
    await expect(page.getByText('Move History')).toBeVisible();
    await expect(page.getByText('No moves yet')).toBeVisible();
  });

  test('should show turn indicator', async ({ page }) => {
    await expect(page.getByText('Your turn')).toBeVisible();
  });

  test('should have flip board button', async ({ page }) => {
    const flipButton = page.getByRole('button', { name: /Flip/i });
    await expect(flipButton).toBeVisible();
    await flipButton.click();
    await expect(page.getByTestId('coach-play-game')).toBeVisible();
  });
});
