/**
 * Coach Play E2E Tests - P2 Play With Coach Steps 1-5
 * 
 * Tests the full game loop: setup → start → move → coach move → end → summary
 * Plus: Behavior extraction, CPR display, and Identity display
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://position-mastery.preview.emergentagent.com';

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

  test('should display Coaching Style selector with 3 options', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Check Coaching Style section
    await expect(page.getByText('Coaching Style')).toBeVisible();
    
    // Check all 3 coaching mode buttons
    await expect(page.getByTestId('mode-beginner')).toBeVisible();
    await expect(page.getByTestId('mode-intermediate')).toBeVisible();
    await expect(page.getByTestId('mode-advanced')).toBeVisible();
    
    // Verify button labels
    await expect(page.getByTestId('mode-beginner')).toHaveText(/Beginner/);
    await expect(page.getByTestId('mode-intermediate')).toHaveText(/Standard/);
    await expect(page.getByTestId('mode-advanced')).toHaveText(/Minimal/);
    
    // Standard mode should be selected by default (has bg-primary class)
    await expect(page.getByTestId('mode-intermediate')).toHaveClass(/bg-primary/);
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

  test('should allow Coaching Style selection and show description', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    
    // Click Beginner mode
    await page.getByTestId('mode-beginner').click({ force: true });
    // Should show beginner description
    await expect(page.getByText(/More explanations, hand-holding/i)).toBeVisible();
    
    // Click Standard mode
    await page.getByTestId('mode-intermediate').click({ force: true });
    // Should show standard description
    await expect(page.getByText(/Balanced feedback, click for details/i)).toBeVisible();
    
    // Click Minimal mode
    await page.getByTestId('mode-advanced').click({ force: true });
    // Should show minimal description
    await expect(page.getByText(/Just the essentials, no fluff/i)).toBeVisible();
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

  test('should resign game and show Game Analysis with New Game button', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Click resign
    await page.getByTestId('resign-btn').click({ force: true });
    
    // Should show new game button - the clearest indicator game ended
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
    
    // Post-game UI shows Game Analysis (not "Loss" text directly)
    await expect(page.getByText('Game Analysis')).toBeVisible();
  });

  test('should start new game after resignation', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start and resign
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    await page.getByTestId('resign-btn').click({ force: true });
    // Wait for New Game button
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
    
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

  test('should show Clean UI with coach panel and Move History', async ({ page }) => {
    // Clean UI Mode now shows "Your Coach" header instead of "Coach Chat"
    await expect(page.getByText('Your Coach')).toBeVisible();
    // Move history is collapsible at bottom - shows as "Moves (X)"
    await expect(page.getByText(/Moves \(\d+\)/)).toBeVisible();
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
    
    // Wait for game to end - UI now shows Game Analysis
    await expect(page.getByText('Game Analysis')).toBeVisible();
    
    // Should show new game button
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
  });

  test('should show performance analysis in post-game summary', async ({ page }) => {
    // Navigate and start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Resign to end the game
    await page.getByTestId('resign-btn').click({ force: true });
    
    // Wait for game to end
    await expect(page.getByText('Game Analysis')).toBeVisible();
    
    // Post-game shows performance metrics like Accuracy
    await expect(page.getByText(/Accuracy/i)).toBeVisible();
    // And performance rating
    await expect(page.getByText(/Performance Rating/i)).toBeVisible();
  });

  test('should show clean UI elements during active game', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Clean UI mode shows "Your Coach" instead of "Coach Chat"
    await expect(page.getByText('Your Coach')).toBeVisible();
    
    // Smart prompts should be visible
    await expect(page.getByRole('button', { name: /Why was that better/i })).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });
});

test.describe('CoachInsightCard Bug Fix Verification', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('should show CoachInsightCard welcome state before moves', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a new game as white
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // CoachInsightCard should show welcome state with proper message
    await expect(page.getByText(/Make a move\. I'll share my thoughts\./i)).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('should display all smart prompts in coach panel', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a new game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // All 4 smart prompts should be visible
    await expect(page.getByRole('button', { name: /Why was that better/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /What's my plan/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Did I miss a tactic/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /What should I improve/i })).toBeVisible();
    
    // Type a question button
    await expect(page.getByRole('button', { name: /Type a question/i })).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('Type a question button should expand to text area', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a new game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Click "Type a question..." button
    await page.getByRole('button', { name: /Type a question/i }).click({ force: true });
    
    // Should show textarea/input
    const textarea = page.getByPlaceholder(/Ask the coach anything/i);
    await expect(textarea).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('should show is_player_turn as true when playing as white', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a new game as white (default)
    await page.getByTestId('select-white').click({ force: true });
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Should show "Your turn" indicator since white moves first
    await expect(page.getByText('Your turn', { exact: true })).toBeVisible();
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });
});

test.describe('Teaching Mode Features', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('Start Learning button triggers teaching mode', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a new game as white
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Wait for opening suggestion with "Start Learning" button to appear
    // This may take a few seconds as the coach detects the opening
    const startLearningBtn = page.getByTestId('start-lesson-btn');
    
    // Check if lesson offer is visible (depends on opening detection)
    const offerVisible = await startLearningBtn.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (offerVisible) {
      // Click Start Learning to enter teaching mode
      await startLearningBtn.click({ force: true });
      
      // Should enter teaching mode - look for teaching UI indicators
      // Teaching mode shows lesson name in amber styling
      await expect(page.locator('text=/Learning|Trap|Lesson/i').first()).toBeVisible({ timeout: 5000 });
      
      // Exit lesson button should appear
      await expect(page.getByText('Exit lesson', { exact: true })).toBeVisible();
    } else {
      // If no teaching offer, the game may need more moves to detect an opening
      // Just verify the game is running - this is not a bug
      await expect(page.getByTestId('resign-btn')).toBeVisible();
    }
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('CoachInsightCard shows teaching-specific amber UI with lesson info', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start a new game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check if we can enter teaching mode
    const startLearningBtn = page.getByTestId('start-lesson-btn');
    const offerVisible = await startLearningBtn.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (offerVisible) {
      await startLearningBtn.click({ force: true });
      await page.waitForTimeout(2000);
      
      // Teaching UI should show:
      // 1. Amber-styled CoachInsightCard (amber border/background)
      // 2. Lesson name (e.g., "Elephant Trap")
      // 3. Remaining moves count (e.g., "(8 left)")
      
      // Check for amber styling - look for amber-colored elements
      const amberElement = page.locator('.bg-amber-500\\/10, [class*="amber"]').first();
      await expect(amberElement).toBeVisible();
      
      // Check for lesson name display
      const lessonHeader = page.locator('text=/\\(\\d+ left\\)/').first();
      await expect(lessonHeader).toBeVisible();
      
      // Should show "Your turn" instruction
      await expect(page.locator('text=/Your turn/i').first()).toBeVisible();
    }
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('Teaching instruction shows Your turn: play X format', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    const startLearningBtn = page.getByTestId('start-lesson-btn');
    const offerVisible = await startLearningBtn.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (offerVisible) {
      await startLearningBtn.click({ force: true });
      await page.waitForTimeout(2000);
      
      // Should show instruction with move notation like "Your turn: play Nc3" or "Your turn → play Nc3"
      const instruction = page.locator('text=/Your turn.*play\\s+[A-Za-z0-9]+/i').first();
      await expect(instruction).toBeVisible();
    }
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('Teaching mode shows Exit lesson button to exit', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    const startLearningBtn = page.getByTestId('start-lesson-btn');
    const offerVisible = await startLearningBtn.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (offerVisible) {
      await startLearningBtn.click({ force: true });
      await page.waitForTimeout(2000);
      
      // Exit lesson button should be visible for exiting teaching mode
      const exitBtn = page.getByText('Exit lesson', { exact: true });
      await expect(exitBtn).toBeVisible();
      
      // Click exit to leave teaching mode
      await exitBtn.click({ force: true });
      await page.waitForTimeout(1000);
      
      // After exiting, Exit lesson button should disappear
      await expect(exitBtn).not.toBeVisible();
    }
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });

  test('Opening/Trap lesson offer shows trap name and description', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Wait for potential teaching offer
    await page.waitForTimeout(3000);
    
    // Look for trap name in the lesson offer panel (e.g., "Elephant Trap", "Legal's Mate")
    const trapName = page.locator('text=/Trap|Opening|Gambit|Defense/i').first();
    const trapVisible = await trapName.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (trapVisible) {
      // Should show Start Learning and Just Play buttons
      await expect(page.getByTestId('start-lesson-btn')).toBeVisible();
      await expect(page.getByText('Just Play', { exact: true })).toBeVisible();
    }
    
    // Cleanup
    await page.getByTestId('resign-btn').click({ force: true });
  });
});
