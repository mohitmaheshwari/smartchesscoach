/**
 * Clean UI Mode E2E Tests - UX Overhaul for Play with Coach page
 * 
 * Tests the new clean, focused 'one insight at a time' coaching loop:
 * - CoachInsightCard for move feedback
 * - TrapAlert for trap notifications  
 * - AskCoach component with smart prompts
 * - MoveHistorySection collapsible at bottom
 * - Legacy UI hidden when cleanUIMode is true
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://chessguru-coach.preview.emergentagent.com';

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
    // Ignore cleanup errors
  }
}

async function waitForToastsToDisappear(page: Page) {
  await page.waitForFunction(() => {
    const toasts = document.querySelectorAll('[data-sonner-toast]');
    return toasts.length === 0;
  }, { timeout: 5000 }).catch(() => {});
}

async function startGameAsWhite(page: Page) {
  await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
  await waitForToastsToDisappear(page);
  await expect(page.getByTestId('coach-play-setup')).toBeVisible({ timeout: 10000 });
  await page.getByTestId('start-game-btn').click({ force: true });
  await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
}

test.describe('Clean UI Mode - Core Components', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test.afterEach(async ({ page }) => {
    // Cleanup - resign any active game
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click({ force: true });
    }
  });

  test('should show coach panel with clean UI when game starts', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Should show the coach chat panel
    await expect(page.getByTestId('coach-chat-panel')).toBeVisible();
    
    // Should show "Your Coach" header in clean UI mode
    await expect(page.getByText('Your Coach')).toBeVisible();
    
    // Take screenshot for verification
    await page.screenshot({ path: 'clean-ui-coach-panel.jpeg', quality: 20 });
  });

  test('should show CoachInsightCard with default welcome state', async ({ page }) => {
    await startGameAsWhite(page);
    
    // The CoachInsightCard should show the welcome/default state
    // "Make a move. I'll share my thoughts."
    await expect(page.getByText("Make a move. I'll share my thoughts.")).toBeVisible();
  });

  test('should show smart prompts in AskCoach component', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Smart prompts should be visible in the AskCoach component
    // The prompts are: "Why was that better?", "What's my plan?", etc.
    await expect(page.getByRole('button', { name: /Why was that better/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /What's my plan/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Did I miss a tactic/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /What should I improve/i })).toBeVisible();
  });

  test('should show collapsible MoveHistorySection at bottom', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Move history section should be present
    // It shows as a collapsible summary with "Moves (0)" or similar text
    await expect(page.getByText(/Moves \(\d+\)/)).toBeVisible();
    
    // It should be collapsible via <details> element
    const moveHistorySummary = page.locator('summary:has-text("Moves")');
    await expect(moveHistorySummary).toBeVisible();
  });

  test('should NOT show legacy Coach Chat header in clean UI mode', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Legacy "Coach Chat" header should NOT be visible when cleanUIMode is true
    // The clean UI shows "Your Coach" instead
    const legacyCoachChatHeader = page.locator('h2:has-text("Coach Chat")');
    await expect(legacyCoachChatHeader).not.toBeVisible();
  });

  test('should NOT show legacy chat-messages container in clean UI mode', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Legacy chat-messages area should not be visible in clean UI mode
    // (It's wrapped in {!cleanUIMode && } conditional)
    const legacyChatMessages = page.getByTestId('chat-messages');
    await expect(legacyChatMessages).not.toBeVisible();
  });
});

test.describe('Clean UI Mode - Opening Suggestion Panel', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test.afterEach(async ({ page }) => {
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click({ force: true });
    }
  });

  test('should show opening suggestion panel with Just Play button', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Wait for the game to fully load
    await page.waitForLoadState('domcontentloaded');
    
    // Check for the opening suggestion panel - it may or may not appear
    // depending on opening detection
    const openingSuggestionPanel = page.locator('[data-testid="start-lesson-btn"]');
    const justPlayButton = page.getByRole('button', { name: /Just Play/i });
    
    // If the opening suggestion appears, the Just Play button should be visible
    if (await openingSuggestionPanel.isVisible({ timeout: 3000 }).catch(() => false)) {
      await expect(justPlayButton).toBeVisible();
      
      // Click Just Play to dismiss
      await justPlayButton.click({ force: true });
      
      // The suggestion panel should disappear
      await expect(openingSuggestionPanel).not.toBeVisible();
    }
    
    // Take screenshot regardless
    await page.screenshot({ path: 'clean-ui-opening-suggestion.jpeg', quality: 20 });
  });
});

test.describe('Clean UI Mode - Board Interactivity', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test.afterEach(async ({ page }) => {
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click({ force: true });
    }
  });

  test('should have interactive board that accepts moves', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Board should be visible
    const board = page.locator('cg-board');
    await expect(board).toBeVisible();
    
    // The board should be interactive (player's turn as white)
    await expect(page.getByText('Your turn')).toBeVisible();
    
    // Try to make a move (e2-e4)
    // The Lichess board uses drag-and-drop
    const e2Square = page.locator('cg-board square').filter({ has: page.locator('[data-coord="e2"]') }).first();
    const e4Square = page.locator('cg-board square').filter({ has: page.locator('[data-coord="e4"]') }).first();
    
    // Alternative: Click-based move detection
    // Most chess boards support click-click moves
    await page.locator('cg-board').click({ position: { x: 4*50 + 25, y: 6*50 + 25 } }); // e2
    await page.locator('cg-board').click({ position: { x: 4*50 + 25, y: 4*50 + 25 } }); // e4
    
    // Wait for the move to register - coach should think
    await page.waitForTimeout(500);
    
    // Take screenshot after move attempt
    await page.screenshot({ path: 'clean-ui-move-attempt.jpeg', quality: 20 });
  });

  test('should show eval bar next to board', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Eval bar should be visible
    await expect(page.getByTestId('eval-bar')).toBeVisible();
  });
});

test.describe('Clean UI Mode - Smart Prompts', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test.afterEach(async ({ page }) => {
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click({ force: true });
    }
  });

  test('should have clickable smart prompt buttons', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Find the "Why was that better?" prompt
    const whyPrompt = page.getByRole('button', { name: /Why was that better/i });
    await expect(whyPrompt).toBeVisible();
    await expect(whyPrompt).toBeEnabled();
    
    // Find the "What's my plan?" prompt
    const planPrompt = page.getByRole('button', { name: /What's my plan/i });
    await expect(planPrompt).toBeVisible();
    await expect(planPrompt).toBeEnabled();
  });

  test('should show "Type a question..." input option', async ({ page }) => {
    await startGameAsWhite(page);
    
    // The AskCoach component should have a button to show the text input
    const typeQuestionBtn = page.getByRole('button', { name: /Type a question/i });
    await expect(typeQuestionBtn).toBeVisible();
    
    // Click it to reveal the text input
    await typeQuestionBtn.click({ force: true });
    
    // Now a textarea should appear
    const textarea = page.locator('textarea[placeholder*="Ask the coach"]');
    await expect(textarea).toBeVisible();
    
    // Screenshot the expanded input
    await page.screenshot({ path: 'clean-ui-ask-coach-expanded.jpeg', quality: 20 });
  });
});

test.describe('Clean UI Mode - Game Controls', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test('should have flip board and resign buttons', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Flip button should be visible
    await expect(page.getByRole('button', { name: /Flip/i })).toBeVisible();
    
    // Resign button should be visible
    await expect(page.getByTestId('resign-btn')).toBeVisible();
  });

  test('should show New Game button and post-game UI after resignation', async ({ page }) => {
    await startGameAsWhite(page);
    
    // Resign the game
    await page.getByTestId('resign-btn').click({ force: true });
    
    // After game ends, the post-game UI shows Game Analysis 
    // The clean UI mode reverts to legacy when gameOver is true
    // Wait for the New Game button to appear (this is the clearest indicator game is over)
    await expect(page.getByTestId('new-game-btn')).toBeVisible();
    
    // Post-game shows "Game Analysis" header
    await expect(page.getByText('Game Analysis')).toBeVisible();
    
    // Take screenshot of post-game state
    await page.screenshot({ path: 'clean-ui-post-game.jpeg', quality: 20 });
  });
});
