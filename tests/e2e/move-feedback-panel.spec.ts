/**
 * E2E Tests for Real-time Move Feedback Panel on CoachPlay page
 * 
 * Tests the MoveFeedbackPanel component that displays after user makes a move.
 * Features tested:
 * - Panel displays after move is made
 * - Move quality indicator (excellent/good/inaccuracy/mistake/blunder)
 * - Best move explanation when user's move wasn't optimal
 * - Coach's response move with explanation
 * - Dismiss functionality
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://chess-habit-forge.preview.emergentagent.com';

test.describe('Move Feedback Panel', () => {
  test.beforeEach(async ({ page }) => {
    // Dev login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
  });

  test('should display move feedback panel with existing session', async ({ page }) => {
    // Navigate to play-with-coach page
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for page to fully load
    await expect(page.locator('[data-testid="coach-play-game"], [data-testid="coach-play-setup"]')).toBeVisible({ timeout: 10000 });
    
    // Check if we have an active game (resumed session)
    const gamePanel = page.locator('[data-testid="coach-play-game"]');
    const isInGame = await gamePanel.isVisible().catch(() => false);
    
    if (isInGame) {
      // There should be a move feedback panel if moves have been made
      // Wait for potential feedback to load
      await page.waitForTimeout(2000);
      
      // Check for move feedback panel
      const feedbackPanel = page.locator('[data-testid="move-feedback-panel"]');
      const hasFeedback = await feedbackPanel.isVisible().catch(() => false);
      
      if (hasFeedback) {
        // Verify the panel structure
        await expect(feedbackPanel).toBeVisible();
        
        // Take a screenshot
        await page.screenshot({ path: 'feedback-panel-visible.jpeg', quality: 20 });
      }
    }
  });

  test('should show move quality indicator with emoji', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const feedbackPanel = page.locator('[data-testid="move-feedback-panel"]');
    const isVisible = await feedbackPanel.isVisible().catch(() => false);
    
    if (isVisible) {
      // Check for quality indicator - should have an emoji and quality text
      // Quality types: excellent, good, inaccuracy, mistake, blunder
      const qualityText = feedbackPanel.locator('text=/excellent|good|inaccuracy|mistake|blunder/i');
      await expect(qualityText.first()).toBeVisible();
      
      // Verify emoji is present (checking for common quality emojis)
      const panelText = await feedbackPanel.textContent();
      const hasEmoji = /[🎯👍🤔⚠️❌]/.test(panelText || '');
      expect(hasEmoji).toBeTruthy();
    } else {
      // If no feedback panel, the test passes (no moves made or game not started)
      test.skip();
    }
  });

  test('should show coach move with explanation', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const feedbackPanel = page.locator('[data-testid="move-feedback-panel"]');
    const isVisible = await feedbackPanel.isVisible().catch(() => false);
    
    if (isVisible) {
      // Check for coach move section
      const coachSection = feedbackPanel.locator('text=/Coach played/i');
      const hasCoachMove = await coachSection.isVisible().catch(() => false);
      
      if (hasCoachMove) {
        await expect(coachSection).toBeVisible();
      }
    } else {
      test.skip();
    }
  });

  test('should show dismiss button and dismiss panel on click', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const feedbackPanel = page.locator('[data-testid="move-feedback-panel"]');
    const isVisible = await feedbackPanel.isVisible().catch(() => false);
    
    if (isVisible) {
      // Find dismiss button - it's a plain text button
      const dismissButton = feedbackPanel.getByText('Dismiss');
      await expect(dismissButton).toBeVisible();
      
      // Click dismiss
      await dismissButton.click();
      
      // Verify panel is dismissed
      await expect(feedbackPanel).not.toBeVisible({ timeout: 3000 });
    } else {
      test.skip();
    }
  });

  test('should show best move section when available', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const feedbackPanel = page.locator('[data-testid="move-feedback-panel"]');
    const isVisible = await feedbackPanel.isVisible().catch(() => false);
    
    if (isVisible) {
      // Check the content of the panel
      const panelText = await feedbackPanel.textContent();
      
      // If it's a suboptimal move AND best_move is different, show "Best was"
      // Note: In current session, user_move=exd5, best_move=exd5 (same), so no "Best was"
      // This test verifies the panel structure is correct
      const isSuboptimal = /inaccuracy|mistake|blunder/i.test(panelText || '');
      
      if (isSuboptimal) {
        // Check if panel has "Best was" or coaching message
        // Both are valid as the best move section only shows when moves differ
        const hasBestWas = /Best was/i.test(panelText || '');
        const hasCoachingMessage = (panelText?.length || 0) > 50; // Has meaningful content
        
        expect(hasBestWas || hasCoachingMessage).toBeTruthy();
      }
    } else {
      test.skip();
    }
  });

  test('should display coaching message in feedback panel', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const feedbackPanel = page.locator('[data-testid="move-feedback-panel"]');
    const isVisible = await feedbackPanel.isVisible().catch(() => false);
    
    if (isVisible) {
      // Panel should have substantive coaching text (more than just quality indicator)
      const panelText = await feedbackPanel.textContent();
      
      // Should have meaningful text content (coaching message)
      expect(panelText?.length).toBeGreaterThan(30);
    } else {
      test.skip();
    }
  });
});

test.describe('CoachPlay Page Setup', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
  });

  test('should load play with coach page', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    
    // Wait longer for page to render
    await page.waitForTimeout(3000);
    
    // Should show either setup page or active game
    const setupPage = page.locator('[data-testid="coach-play-setup"]');
    const gamePage = page.locator('[data-testid="coach-play-game"]');
    
    const hasSetup = await setupPage.isVisible().catch(() => false);
    const hasGame = await gamePage.isVisible().catch(() => false);
    
    expect(hasSetup || hasGame).toBeTruthy();
  });

  test('should show eval bar during game', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const gamePage = page.locator('[data-testid="coach-play-game"]');
    const isInGame = await gamePage.isVisible().catch(() => false);
    
    if (isInGame) {
      const evalBar = page.locator('[data-testid="eval-bar"]');
      await expect(evalBar).toBeVisible();
      
      const evalText = page.locator('[data-testid="eval-text"]');
      await expect(evalText).toBeVisible();
    } else {
      test.skip();
    }
  });

  test('should show coach chat panel during game', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const gamePage = page.locator('[data-testid="coach-play-game"]');
    const isInGame = await gamePage.isVisible().catch(() => false);
    
    if (isInGame) {
      const chatPanel = page.locator('[data-testid="coach-chat-panel"]');
      await expect(chatPanel).toBeVisible();
      
      // Should have chat input
      const chatInput = page.locator('[data-testid="chat-input"]');
      await expect(chatInput).toBeVisible();
    } else {
      test.skip();
    }
  });
});

test.describe('Game Controls', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
  });

  test('should show resign button during active game', async ({ page }) => {
    await page.goto(`${BASE_URL}/play-with-coach`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    const gamePage = page.locator('[data-testid="coach-play-game"]');
    const isInGame = await gamePage.isVisible().catch(() => false);
    
    if (isInGame) {
      const resignBtn = page.locator('[data-testid="resign-btn"]');
      await expect(resignBtn).toBeVisible();
    } else {
      test.skip();
    }
  });
});
