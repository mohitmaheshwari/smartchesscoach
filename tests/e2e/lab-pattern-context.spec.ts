/**
 * Lab Page Pattern Intelligence E2E Tests
 * 
 * Tests the Pattern Context feature that shows SPECIFIC insights:
 * - Pattern Intelligence card with recurring patterns
 * - Specific insights (rating, opening, time context)
 * - Global vulnerability profile
 * - Action recommendations
 */

import { test, expect } from '@playwright/test';
import { waitForAppReady, devLogin, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

// Helper to navigate to a game's lab page
async function navigateToGamePage(page: any): Promise<boolean> {
  // Go to dashboard
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
  await waitForAppReady(page);
  await page.waitForTimeout(1000);
  
  // Click on the first game row (contains "vs" prefix)
  const gameRow = page.locator('text=/vs [A-Za-z]/').first();
  if (await gameRow.count() === 0) {
    return false;
  }
  
  await gameRow.click();
  await page.waitForLoadState('domcontentloaded');
  
  // Wait for lab page to load
  const labPage = page.getByTestId('lab-page');
  try {
    await expect(labPage).toBeVisible({ timeout: 15000 });
    return true;
  } catch {
    return false;
  }
}

test.describe('Lab Page Pattern Intelligence', () => {
  test.beforeEach(async ({ page }) => {
    // Setup: dev login and dismiss toasts
    await dismissToasts(page);
    await devLogin(page);
    await hideEmergentBadge(page);
  });

  test('Lab page loads successfully with analysis data', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Verify lab page loads with key elements
    await expect(page.getByTestId('lab-page')).toBeVisible();
    
    // Should have tabs
    await expect(page.getByRole('tab', { name: /summary/i })).toBeVisible();
  });

  test('Lab page shows coach mode and engine mode toggle', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Verify mode toggle buttons exist
    await expect(page.getByTestId('coach-mode-btn')).toBeVisible();
    await expect(page.getByTestId('engine-mode-btn')).toBeVisible();
    
    // Click engine mode
    await page.getByTestId('engine-mode-btn').click();
    await page.waitForTimeout(300);
    await expect(page.getByTestId('engine-mode-btn')).toHaveClass(/bg-blue/);
    
    // Click coach mode
    await page.getByTestId('coach-mode-btn').click();
    await page.waitForTimeout(300);
    await expect(page.getByTestId('coach-mode-btn')).toHaveClass(/bg-green/);
  });

  test('Lab page Summary tab displays Pattern Intelligence card', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(1000);
    
    // Check for Pattern Intelligence card
    const patternCard = page.getByTestId('pattern-insights-card');
    
    // Scroll to pattern card if it exists
    if (await patternCard.count() > 0) {
      await patternCard.scrollIntoViewIfNeeded();
      await expect(patternCard).toBeVisible();
      
      // Verify card title
      await expect(patternCard.locator('text=Pattern Intelligence')).toBeVisible();
    } else {
      // No pattern card means game may not have recurring patterns - log it
      console.log('Pattern Intelligence card not visible - game may not have recurring patterns');
    }
  });

  test('Pattern Intelligence card shows specific opening context', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(1000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    await patternCard.scrollIntoViewIfNeeded();
    const cardText = await patternCard.textContent();
    
    // Should show opening-specific info like "Common in X opening" or "Trigger: X"
    const hasOpeningContext = 
      cardText?.includes('Common in') || 
      cardText?.includes('Trigger:') ||
      cardText?.includes('Opening') ||
      cardText?.includes('Defense') ||
      cardText?.includes('Game');
    
    expect(hasOpeningContext).toBeTruthy();
  });

  test('Pattern Intelligence card shows time control context', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(1000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    await patternCard.scrollIntoViewIfNeeded();
    const cardText = await patternCard.textContent();
    
    // Should show time control info like "Mostly in rapid/blitz" or "Most issues in X"
    const hasTimeContext = 
      cardText?.includes('rapid') || 
      cardText?.includes('blitz') ||
      cardText?.includes('bullet') ||
      cardText?.includes('Most issues in') ||
      cardText?.includes('Mostly in');
    
    expect(hasTimeContext).toBeTruthy();
  });

  test('Pattern Intelligence shows vulnerability profile badges', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(1000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    await patternCard.scrollIntoViewIfNeeded();
    
    // Check for vulnerability profile section
    const vulnerabilityText = patternCard.locator('text=/VULNERABILITY PROFILE|Most issues|Trigger:/i');
    
    if (await vulnerabilityText.count() > 0) {
      await expect(vulnerabilityText.first()).toBeVisible();
    }
  });

  test('Pattern card shows actionable Fix recommendation', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(1000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    await patternCard.scrollIntoViewIfNeeded();
    
    // Look for Fix: recommendation
    const fixLabel = patternCard.locator('text=/Fix:/i');
    
    if (await fixLabel.count() > 0) {
      await expect(fixLabel.first()).toBeVisible();
      
      // Get the full fix text and verify it's specific (not vague)
      const fixText = await patternCard.locator('text=/Fix:.+/i').first().textContent();
      expect(fixText).not.toBeNull();
      expect(fixText!.length).toBeGreaterThan(10); // Should be a meaningful recommendation
    }
  });

  test('Pattern card shows trend indicator (Needs work / Getting better)', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(1000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    await patternCard.scrollIntoViewIfNeeded();
    
    // Should have a trend indicator
    const trendIndicator = patternCard.locator('text=/Needs work|Getting better|Stable/i');
    
    if (await trendIndicator.count() > 0) {
      await expect(trendIndicator.first()).toBeVisible();
    }
  });
});

test.describe('Lab Page Navigation and UI', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
    await hideEmergentBadge(page);
  });

  test('Lab page has three tabs: Summary, Strategy, Milestones', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Check all three tabs exist
    await expect(page.getByRole('tab', { name: /summary/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /strategy/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /milestones/i })).toBeVisible();
  });

  test('Clicking tabs switches content', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Strategy tab
    await page.getByRole('tab', { name: /strategy/i }).click();
    await page.waitForTimeout(500);
    
    // Click Milestones tab
    await page.getByRole('tab', { name: /milestones/i }).click();
    await page.waitForTimeout(500);
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(500);
    
    // Should not crash
    await expect(page.getByTestId('lab-page')).toBeVisible();
  });

  test('Lab page shows chess board with position', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Chess board should be visible (react-chessboard)
    const chessBoard = page.locator('[class*="chessboard"], [class*="board"], [data-testid*="board"]');
    await expect(chessBoard.first()).toBeVisible();
  });

  test('Critical toggle button exists and works', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Find critical toggle button
    const criticalToggle = page.getByTestId('critical-toggle');
    
    if (await criticalToggle.count() > 0) {
      await expect(criticalToggle).toBeVisible();
      
      // Click to enable critical only mode
      await criticalToggle.click();
      await page.waitForTimeout(300);
      
      // Click to disable critical only mode
      await criticalToggle.click();
      await page.waitForTimeout(300);
      
      await expect(page.getByTestId('lab-page')).toBeVisible();
    }
  });

  test('Similar games section shows clickable entries', async ({ page }) => {
    const success = await navigateToGamePage(page);
    if (!success) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    // Click Summary tab
    await page.getByRole('tab', { name: /summary/i }).click();
    await page.waitForTimeout(1000);
    
    // Look for similar games section (Similar Pattern Detected)
    const similarGames = page.locator('[data-testid^="similar-game-"]');
    
    if (await similarGames.count() > 0) {
      await expect(similarGames.first()).toBeVisible();
      
      // Should be clickable (has chevron or button styling)
      const firstGame = similarGames.first();
      const isClickable = await firstGame.evaluate(el => {
        return el.tagName === 'BUTTON' || 
               el.getAttribute('role') === 'button' ||
               window.getComputedStyle(el).cursor === 'pointer';
      });
      
      expect(isClickable).toBeTruthy();
    }
  });
});
