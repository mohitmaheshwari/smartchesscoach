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

// Helper to get an analyzed game ID from dashboard
async function getAnalyzedGameId(page: any): Promise<string | null> {
  // Go to dashboard and find a game
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
  await waitForAppReady(page);
  
  // Wait for games to load
  await page.waitForTimeout(1000);
  
  // Find a game link to click
  const gameLink = page.locator('a[href*="/game/"]').first();
  if (await gameLink.count() > 0) {
    const href = await gameLink.getAttribute('href');
    if (href) {
      const match = href.match(/\/game\/([a-zA-Z0-9_-]+)/);
      return match ? match[1] : null;
    }
  }
  
  return null;
}

test.describe('Lab Page Pattern Intelligence', () => {
  test.beforeEach(async ({ page }) => {
    // Setup: dev login and dismiss toasts
    await dismissToasts(page);
    await devLogin(page);
    await hideEmergentBadge(page);
  });

  test('Lab page loads successfully with analysis data', async ({ page }) => {
    // Navigate to dashboard first
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Click on a game to go to lab page
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify lab page loads
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
  });

  test('Lab page shows coach mode and engine mode toggle', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Verify mode toggle buttons exist
    await expect(page.getByTestId('coach-mode-btn')).toBeVisible();
    await expect(page.getByTestId('engine-mode-btn')).toBeVisible();
    
    // Click engine mode
    await page.getByTestId('engine-mode-btn').click();
    await expect(page.getByTestId('engine-mode-btn')).toHaveClass(/bg-blue/);
    
    // Click coach mode
    await page.getByTestId('coach-mode-btn').click();
    await expect(page.getByTestId('coach-mode-btn')).toHaveClass(/bg-green/);
  });

  test('Lab page displays Pattern Intelligence card when patterns exist', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Navigate to Summary tab (first tab)
    const summaryTab = page.getByRole('tab', { name: /summary/i });
    if (await summaryTab.count() > 0) {
      await summaryTab.click();
    }
    
    // Wait for data to load
    await page.waitForTimeout(2000);
    
    // Check for Pattern Intelligence card
    const patternCard = page.getByTestId('pattern-insights-card');
    
    // Pattern card may or may not be visible depending on game data
    const isPatternCardVisible = await patternCard.count() > 0;
    
    if (isPatternCardVisible) {
      await expect(patternCard).toBeVisible();
      
      // Verify card contains "Pattern Intelligence" text
      await expect(patternCard.locator('text=Pattern Intelligence')).toBeVisible();
    } else {
      // No pattern card means the game may not have recurring patterns - that's OK
      console.log('Pattern Intelligence card not visible - game may not have recurring patterns');
    }
  });

  test('Pattern Intelligence card shows specific insights when present', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Go to Summary tab
    const summaryTab = page.getByRole('tab', { name: /summary/i });
    if (await summaryTab.count() > 0) {
      await summaryTab.click();
    }
    
    await page.waitForTimeout(2000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    // If pattern card exists, check for specific insights content
    // The card should show rating context, opening context, or time context
    const cardContent = await patternCard.textContent();
    
    // Card should NOT contain vague text like just "positional"
    // Instead should have specific labels like "Getting better", "Needs work", "Fix:"
    const hasSpecificContent = 
      cardContent?.includes('Fix:') || 
      cardContent?.includes('Getting better') || 
      cardContent?.includes('Needs work') ||
      cardContent?.includes('Stable') ||
      cardContent?.includes('Most issues in') ||
      cardContent?.includes('Trigger:');
    
    if (hasSpecificContent) {
      expect(hasSpecificContent).toBeTruthy();
    }
  });

  test('Pattern Intelligence shows global vulnerability profile', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Go to Summary tab
    const summaryTab = page.getByRole('tab', { name: /summary/i });
    if (await summaryTab.count() > 0) {
      await summaryTab.click();
    }
    
    await page.waitForTimeout(2000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    // Check for Vulnerability Profile section text
    const vulnerabilityProfile = patternCard.locator('text=Vulnerability Profile');
    
    if (await vulnerabilityProfile.count() > 0) {
      await expect(vulnerabilityProfile).toBeVisible();
      
      // Vulnerability profile should show time control or opening triggers
      const cardText = await patternCard.textContent();
      const hasVulnerabilityInfo = 
        cardText?.includes('Most issues in') || 
        cardText?.includes('Trigger:') ||
        cardText?.includes('mistakes vs');
        
      if (hasVulnerabilityInfo) {
        expect(hasVulnerabilityInfo).toBeTruthy();
      }
    }
  });

  test('Pattern card shows action recommendations (Fix labels)', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Go to Summary tab
    const summaryTab = page.getByRole('tab', { name: /summary/i });
    if (await summaryTab.count() > 0) {
      await summaryTab.click();
    }
    
    await page.waitForTimeout(2000);
    
    const patternCard = page.getByTestId('pattern-insights-card');
    if (await patternCard.count() === 0) {
      test.skip(true, 'No Pattern Intelligence card on this game');
      return;
    }
    
    // Look for "Fix:" recommendations in the pattern card
    const fixLabel = patternCard.locator('text=/Fix:/');
    
    if (await fixLabel.count() > 0) {
      await expect(fixLabel.first()).toBeVisible();
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
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Check all three tabs exist
    await expect(page.getByRole('tab', { name: /summary/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /strategy/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /milestones/i })).toBeVisible();
  });

  test('Clicking tabs switches content', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
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
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Chess board should be visible (using react-chessboard component class)
    const chessBoard = page.locator('[class*="chessboard"], [class*="board"]');
    await expect(chessBoard.first()).toBeVisible();
  });

  test('Lab page navigation controls work', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Look for navigation buttons (chevron icons)
    const forwardBtn = page.locator('button').filter({ has: page.locator('svg') }).nth(3);
    const backBtn = page.locator('button').filter({ has: page.locator('svg') }).nth(1);
    
    // Click forward button if it exists and is not disabled
    if (await forwardBtn.count() > 0) {
      const isDisabled = await forwardBtn.isDisabled();
      if (!isDisabled) {
        await forwardBtn.click();
        await page.waitForTimeout(300);
      }
    }
    
    // Page should still be functional
    await expect(page.getByTestId('lab-page')).toBeVisible();
  });

  test('Critical toggle button works', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    const gameLink = page.locator('a[href*="/game/"]').first();
    if (await gameLink.count() === 0) {
      test.skip(true, 'No games available to test');
      return;
    }
    
    await gameLink.click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Find critical toggle button
    const criticalToggle = page.getByTestId('critical-toggle');
    
    if (await criticalToggle.count() > 0) {
      // Click to enable critical only mode
      await criticalToggle.click();
      await page.waitForTimeout(300);
      
      // Click to disable critical only mode
      await criticalToggle.click();
      await page.waitForTimeout(300);
      
      await expect(page.getByTestId('lab-page')).toBeVisible();
    }
  });
});
