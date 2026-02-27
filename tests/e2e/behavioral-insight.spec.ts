import { test, expect } from '@playwright/test';

/**
 * BehavioralInsightCard Frontend Tests
 * 
 * Tests P1 upgrade features:
 * - Root cause badge display
 * - Scorecard chips display
 * - Stagnation styling (when applicable)
 * - Mission CTA
 */

test.describe('BehavioralInsightCard', () => {
  test.beforeEach(async ({ page }) => {
    // Remove Emergent preview badge
    await page.addInitScript(() => {
      const observer = new MutationObserver(() => {
        const badge = document.querySelector('[class*="emergent"], [id*="emergent-badge"]');
        if (badge) badge.remove();
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });
    });
    
    // Navigate to landing page and login
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    
    // Click Dev Login button
    const devLoginBtn = page.getByRole('button', { name: /Dev Login/i });
    await devLoginBtn.click();
    
    // Wait for home page to load
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
  });

  test('should display card with root cause badge', async ({ page }) => {
    // Wait for the behavioral card to load
    const insightCard = page.getByTestId('behavioral-insight-card');
    await expect(insightCard).toBeVisible({ timeout: 10000 });
    
    // Check for root cause section
    const rootCauseSection = page.getByTestId('root-cause-section');
    await expect(rootCauseSection).toBeVisible({ timeout: 5000 });
    
    // Root cause should have text content
    const rootCauseText = await rootCauseSection.textContent();
    expect(rootCauseText).toContain('Root Cause:');
  });

  test('should display scorecard chips with dimensions', async ({ page }) => {
    const insightCard = page.getByTestId('behavioral-insight-card');
    await expect(insightCard).toBeVisible({ timeout: 10000 });
    
    // Scorecard chips should show dimension names
    const planChip = insightCard.locator('text=Plan Discipline');
    const decisionChip = insightCard.locator('text=Decision Stability');
    const patternChip = insightCard.locator('text=Pattern Persistence');
    
    await expect(planChip).toBeVisible({ timeout: 5000 });
    await expect(decisionChip).toBeVisible({ timeout: 5000 });
    await expect(patternChip).toBeVisible({ timeout: 5000 });
  });

  test('should display headline and Review Game button', async ({ page }) => {
    const insightCard = page.getByTestId('behavioral-insight-card');
    await expect(insightCard).toBeVisible({ timeout: 10000 });
    
    // Card should have headline
    const headline = insightCard.locator('h3');
    await expect(headline).toBeVisible();
    const headlineText = await headline.textContent();
    expect(headlineText?.length).toBeGreaterThan(10);
    
    // Check for Review Game button
    const reviewBtn = page.getByTestId('review-game-btn');
    await expect(reviewBtn).toBeVisible();
    await expect(reviewBtn).toContainText('Review This Game');
  });

  test('should show confidence or stagnation badge', async ({ page }) => {
    const insightCard = page.getByTestId('behavioral-insight-card');
    await expect(insightCard).toBeVisible({ timeout: 10000 });
    
    // Check if stagnation badge is present
    const stagnationBadge = page.getByTestId('stagnation-badge');
    const isStagnated = await stagnationBadge.isVisible().catch(() => false);
    
    if (isStagnated) {
      await expect(stagnationBadge).toContainText('Stuck Loop');
    } else {
      // Should show confidence label instead
      const confidenceBadge = insightCard.locator('text=/confidence/i');
      await expect(confidenceBadge).toBeVisible();
    }
  });

  test('Review Game button navigates to game page', async ({ page }) => {
    const insightCard = page.getByTestId('behavioral-insight-card');
    await expect(insightCard).toBeVisible({ timeout: 10000 });
    
    // Click Review Game button
    const reviewBtn = page.getByTestId('review-game-btn');
    await expect(reviewBtn).toBeVisible();
    await reviewBtn.click();
    
    await page.waitForLoadState('domcontentloaded');
    
    // Should navigate to /game/{gameId}
    const newUrl = page.url();
    expect(newUrl).toMatch(/\/game\//);
  });
});
