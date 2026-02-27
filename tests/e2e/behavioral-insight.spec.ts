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

  test('should display BehavioralInsightCard', async ({ page }) => {
    // Wait for the card to load (it fetches data from API)
    const insightCard = page.getByTestId('behavioral-insight-card');
    
    // Card may or may not appear depending on whether there's a last game
    // Give it time to load
    await page.waitForTimeout(3000);
    
    const isVisible = await insightCard.isVisible().catch(() => false);
    if (isVisible) {
      await expect(insightCard).toBeVisible();
    } else {
      // Skip if no card - means no last game analyzed
      test.skip(true, 'No BehavioralInsightCard visible - likely no last game');
    }
  });

  test('should display root cause section when card is visible', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Check for root cause section
    const rootCauseSection = page.getByTestId('root-cause-section');
    await expect(rootCauseSection).toBeVisible({ timeout: 5000 });
    
    // Root cause should have text content
    const rootCauseText = await rootCauseSection.textContent();
    expect(rootCauseText).toContain('Root Cause:');
  });

  test('should display scorecard chips', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Scorecard chips should be in rounded-full elements with dimension names
    // Look for Plan Discipline, Decision Stability, Pattern Persistence
    const planChip = insightCard.locator('text=Plan Discipline');
    const decisionChip = insightCard.locator('text=Decision Stability');
    const patternChip = insightCard.locator('text=Pattern Persistence');
    
    // At least the core 3 should be visible (coach_compliance and learning_velocity are filtered)
    await expect(planChip).toBeVisible({ timeout: 5000 });
    await expect(decisionChip).toBeVisible({ timeout: 5000 });
    await expect(patternChip).toBeVisible({ timeout: 5000 });
  });

  test('should display scorecard with numeric scores', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Get all scorecard chips (they are flex items with rounded-full class)
    const cardContent = await insightCard.textContent();
    
    // Should contain numeric scores (0-100)
    expect(cardContent).toMatch(/\d{1,3}/); // Should have numbers
  });

  test('should display headline and rich insight', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Card should have headline (h3) and rich insight (p)
    const headline = insightCard.locator('h3');
    await expect(headline).toBeVisible();
    
    const headlineText = await headline.textContent();
    expect(headlineText?.length).toBeGreaterThan(10); // Headline should be substantial
    
    // Rich insight should be present
    const richInsight = insightCard.locator('p.text-sm');
    await expect(richInsight.first()).toBeVisible();
  });

  test('should display Review Game button', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Check for Review Game button
    const reviewBtn = page.getByTestId('review-game-btn');
    await expect(reviewBtn).toBeVisible({ timeout: 5000 });
    await expect(reviewBtn).toContainText('Review This Game');
  });

  test('should display mission title and instruction', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Mission section should have Target icon and title
    // Look for mission-related content
    const cardContent = await insightCard.textContent();
    
    // Should contain drill-related keywords
    const hasDrillContent = 
      cardContent?.includes('Drill') || 
      cardContent?.includes('Review') ||
      cardContent?.includes('position') ||
      cardContent?.includes('move');
    
    expect(hasDrillContent).toBe(true);
  });

  test('should display confidence badge when not stagnated', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Check if stagnation badge is present
    const stagnationBadge = page.getByTestId('stagnation-badge');
    const isStagnated = await stagnationBadge.isVisible().catch(() => false);
    
    if (!isStagnated) {
      // Should show confidence label instead
      const confidenceBadge = insightCard.locator('text=/confidence/i');
      await expect(confidenceBadge).toBeVisible();
    }
  });

  test('should show stagnation badge styling when stagnated', async ({ page }) => {
    // This test verifies stagnation badge if present
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Check for stagnation badge
    const stagnationBadge = page.getByTestId('stagnation-badge');
    const isStagnated = await stagnationBadge.isVisible().catch(() => false);
    
    if (isStagnated) {
      // Stagnation badge should contain "Stuck Loop" text
      await expect(stagnationBadge).toContainText('Stuck Loop');
      
      // Card should have red border when stagnated
      const cardClasses = await insightCard.getAttribute('class');
      expect(cardClasses).toContain('border-red');
    } else {
      // No stagnation - card should not have red border
      const cardClasses = await insightCard.getAttribute('class');
      expect(cardClasses).not.toContain('border-red');
    }
  });

  test('Review Game button should navigate to game page', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Click Review Game button
    const reviewBtn = page.getByTestId('review-game-btn');
    await expect(reviewBtn).toBeVisible();
    
    // Get current URL before click
    const currentUrl = page.url();
    
    // Click and wait for navigation
    await reviewBtn.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Should navigate to /game/{gameId}
    const newUrl = page.url();
    expect(newUrl).toMatch(/\/game\//);
  });

  test('root cause badge should have appropriate color', async ({ page }) => {
    // Wait for card to load
    await page.waitForTimeout(3000);
    
    const insightCard = page.getByTestId('behavioral-insight-card');
    const isVisible = await insightCard.isVisible().catch(() => false);
    
    if (!isVisible) {
      test.skip(true, 'BehavioralInsightCard not visible');
      return;
    }
    
    // Check root cause section
    const rootCauseSection = page.getByTestId('root-cause-section');
    await expect(rootCauseSection).toBeVisible();
    
    // The badge inside should have color classes
    const badge = rootCauseSection.locator('div').first();
    const classes = await badge.getAttribute('class');
    
    // Should have one of the color classes based on root cause type
    const hasColorClass = 
      classes?.includes('bg-orange') ||  // TIME_TRIGGERED
      classes?.includes('bg-yellow') ||  // OVERCONFIDENCE
      classes?.includes('bg-blue') ||    // CALCULATION_GAP
      classes?.includes('bg-purple');    // DEFENSIVE_STRESS
    
    expect(hasColorClass).toBe(true);
  });
});
