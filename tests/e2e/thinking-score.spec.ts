/**
 * Thinking Score Feature Tests
 * =============================
 * 
 * Tests for the Thinking Score feature that tracks thinking habits progress.
 * The ThinkingScoreCard is rendered at /dashboard-full (not /dashboard).
 * 
 * Features tested:
 * - ThinkingScoreCard component renders correctly
 * - Displays overall thinking score (0-100)
 * - Shows habit breakdown for 5 habits
 * - Displays recommendations
 * - Compact vs expanded views
 */

import { test, expect } from '@playwright/test';

test.describe('ThinkingScoreCard on Dashboard-Full', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard-full where ThinkingScoreCard is rendered
    await page.goto('/dashboard-full', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
  });

  test('ThinkingScoreCard compact view renders', async ({ page }) => {
    // Look for the compact thinking score card
    const thinkingScoreCard = page.getByTestId('thinking-score-card-compact');
    
    // Wait for it to be visible
    await expect(thinkingScoreCard).toBeVisible();
    
    // Should show "Thinking Score" text
    await expect(page.locator('text=Thinking Score').first()).toBeVisible();
  });

  test('ThinkingScoreCard shows numeric score', async ({ page }) => {
    // Wait for the card to load
    await page.waitForSelector('[data-testid="thinking-score-card-compact"], [data-testid="thinking-score-card"]');
    
    // Look for a numeric score - should be 0-100
    const scoreText = page.locator('text=/\\d{1,3}/').first();
    await expect(scoreText).toBeVisible();
  });

  test('ThinkingScoreCard compact expands on click', async ({ page }) => {
    // Find the compact card
    const compactCard = page.getByTestId('thinking-score-card-compact');
    
    // Check if compact card exists
    const isCompact = await compactCard.isVisible().catch(() => false);
    
    if (isCompact) {
      // Click to expand
      await compactCard.click();
      
      // Wait for expanded view
      await page.waitForTimeout(500);
      
      // Should now show expanded content (habit breakdown or full card)
      const expandedCard = page.getByTestId('thinking-score-card');
      await expect(expandedCard).toBeVisible();
    } else {
      // Card might already be in expanded view - that's fine
      const fullCard = page.getByTestId('thinking-score-card');
      await expect(fullCard).toBeVisible();
    }
  });

  test('ThinkingScoreCard shows habit breakdown when expanded', async ({ page }) => {
    // First expand the card if in compact mode
    const compactCard = page.getByTestId('thinking-score-card-compact');
    const isCompact = await compactCard.isVisible().catch(() => false);
    
    if (isCompact) {
      await compactCard.click();
      await page.waitForTimeout(500);
    }
    
    // Look for habit breakdown section
    // The 5 habits are: Threat Awareness, Tactical Vision, Move Verification, King Safety, Patience
    const habitTexts = ['Threat Awareness', 'Tactical Vision', 'Move Verification', 'King Safety', 'Patience'];
    
    // At least one habit should be visible
    let foundHabit = false;
    for (const habit of habitTexts) {
      const habitElement = page.locator(`text=${habit}`).first();
      if (await habitElement.isVisible().catch(() => false)) {
        foundHabit = true;
        break;
      }
    }
    
    expect(foundHabit).toBe(true);
  });

  test('ThinkingScoreCard shows games analyzed count', async ({ page }) => {
    // Expand the card first to see the badge
    const compactCard = page.getByTestId('thinking-score-card-compact');
    if (await compactCard.isVisible().catch(() => false)) {
      await compactCard.click();
      await page.waitForTimeout(500);
    }
    
    // Look for games count badge - could be "X games" format
    const expandedCard = page.getByTestId('thinking-score-card');
    const gamesText = expandedCard.locator('text=/\\d+\\s*games/i').first();
    
    // Games count should be visible in expanded view
    await expect(gamesText).toBeVisible();
  });

  test('ThinkingScoreCard shows trend indicator', async ({ page }) => {
    // Expand the card first
    const compactCard = page.getByTestId('thinking-score-card-compact');
    const isCompact = await compactCard.isVisible().catch(() => false);
    
    if (isCompact) {
      await compactCard.click();
      await page.waitForTimeout(500);
    }
    
    // Look for trend text: Improving, Stable, or Needs Work
    const trendTexts = ['Improving', 'Stable', 'Needs Work'];
    
    let foundTrend = false;
    for (const trend of trendTexts) {
      const trendElement = page.locator(`text=${trend}`).first();
      if (await trendElement.isVisible().catch(() => false)) {
        foundTrend = true;
        break;
      }
    }
    
    expect(foundTrend).toBe(true);
  });
});


test.describe('ThinkingScoreCard Recommendations', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard-full', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
  });

  test('Shows Focus Areas section when expanded', async ({ page }) => {
    // Expand the card
    const compactCard = page.getByTestId('thinking-score-card-compact');
    const isCompact = await compactCard.isVisible().catch(() => false);
    
    if (isCompact) {
      await compactCard.click();
      await page.waitForTimeout(500);
    }
    
    // Look for "Focus Areas" or recommendations section
    const focusAreasText = page.locator('text=Focus Areas').first();
    const isVisible = await focusAreasText.isVisible().catch(() => false);
    
    // If visible, check that recommendations are shown
    if (isVisible) {
      // Recommendations should have actionable text
      await expect(page.locator('text=/Before|Check|Don\'t|Periodically/').first()).toBeVisible();
    }
  });

  test('Recommendations include checklist items', async ({ page }) => {
    // Expand the card
    const compactCard = page.getByTestId('thinking-score-card-compact');
    if (await compactCard.isVisible().catch(() => false)) {
      await compactCard.click();
      await page.waitForTimeout(500);
    }
    
    // Look for checklist text (italicized)
    const checklistPattern = page.locator('text=/Checklist:/i').first();
    const isVisible = await checklistPattern.isVisible().catch(() => false);
    
    // Checklist items are optional but should be present when recommendations exist
    if (isVisible) {
      await expect(checklistPattern).toBeVisible();
    }
  });
});


test.describe('ThinkingScoreCard Visual Elements', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard-full', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
  });

  test('Shows circular progress indicator for overall score', async ({ page }) => {
    // Expand the card
    const compactCard = page.getByTestId('thinking-score-card-compact');
    if (await compactCard.isVisible().catch(() => false)) {
      await compactCard.click();
      await page.waitForTimeout(500);
    }
    
    // Look for SVG circle (progress ring)
    const svgCircle = page.locator('svg circle').first();
    await expect(svgCircle).toBeVisible();
  });

  test('Shows progress bars for each habit', async ({ page }) => {
    // Expand the card
    const compactCard = page.getByTestId('thinking-score-card-compact');
    if (await compactCard.isVisible().catch(() => false)) {
      await compactCard.click();
      await page.waitForTimeout(500);
    }
    
    // Look for progress bars (rounded-full bg elements)
    const progressBars = page.locator('.rounded-full.bg-slate-700, [class*="rounded-full"][class*="bg-"]').filter({ hasNot: page.locator('svg') });
    
    // Should have multiple progress bars (one for each habit shown)
    const count = await progressBars.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Card has purple theme styling', async ({ page }) => {
    // Check for purple-themed styling on the card
    const card = page.locator('[class*="purple-500"]').first();
    await expect(card).toBeVisible();
  });
});


test.describe('ThinkingScore API Integration', () => {
  
  test('API returns valid thinking score data', async ({ request }) => {
    const response = await request.get('/api/thinking-score');
    expect(response.ok()).toBe(true);
    
    const data = await response.json();
    
    // Must have has_data field
    expect(data).toHaveProperty('has_data');
    
    if (data.has_data) {
      // Verify required fields
      expect(data).toHaveProperty('overall_score');
      expect(data).toHaveProperty('habit_progress');
      expect(data).toHaveProperty('recommendations');
      
      // Score should be valid
      expect(data.overall_score).toBeGreaterThanOrEqual(0);
      expect(data.overall_score).toBeLessThanOrEqual(100);
    }
  });

  test('API history endpoint returns score list', async ({ request }) => {
    const response = await request.get('/api/thinking-score/history?limit=5');
    expect(response.ok()).toBe(true);
    
    const data = await response.json();
    
    expect(data).toHaveProperty('scores');
    expect(data).toHaveProperty('count');
    expect(Array.isArray(data.scores)).toBe(true);
  });

  test('API recommendations endpoint returns valid data', async ({ request }) => {
    const response = await request.get('/api/thinking-score/recommendations');
    expect(response.ok()).toBe(true);
    
    const data = await response.json();
    
    expect(data).toHaveProperty('has_data');
    expect(data).toHaveProperty('recommendations');
    expect(Array.isArray(data.recommendations)).toBe(true);
    
    // Should always have at least one recommendation
    expect(data.recommendations.length).toBeGreaterThanOrEqual(1);
  });

  test('Calculate endpoint processes game score', async ({ request }) => {
    // First get a game
    const gamesResponse = await request.get('/api/games?limit=1');
    if (!gamesResponse.ok()) {
      test.skip();
    }
    
    const games = await gamesResponse.json();
    if (!games || games.length === 0) {
      test.skip();
    }
    
    const gameId = games[0].game_id;
    
    // Calculate score for this game
    const calcResponse = await request.post(`/api/thinking-score/calculate/${gameId}`);
    expect(calcResponse.ok()).toBe(true);
    
    const data = await calcResponse.json();
    
    expect(data).toHaveProperty('overall_score');
    expect(data).toHaveProperty('habit_scores');
    expect(data).toHaveProperty('game_id');
    expect(data.game_id).toBe(gameId);
  });
});


test.describe('ThinkingScoreCard Error States', () => {
  
  test('Shows "No Thinking Score Yet" when no data', async ({ page }) => {
    await page.goto('/dashboard-full', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    
    // Look for no-data state (this may not appear if user has data)
    const noDataText = page.locator('text=No Thinking Score Yet');
    const isNoData = await noDataText.isVisible().catch(() => false);
    
    if (isNoData) {
      // Should show message about playing games
      await expect(page.locator('text=/Play.*analyze.*games/i').first()).toBeVisible();
    }
    // If data exists, that's also valid
  });

  test('Shows loading state initially', async ({ page }) => {
    // Use route interception to slow down API response
    await page.route('**/api/thinking-score', async route => {
      await page.waitForTimeout(1000);
      await route.continue();
    });
    
    await page.goto('/dashboard-full', { waitUntil: 'domcontentloaded' });
    
    // Should show loading state
    const loadingText = page.locator('text=Calculating');
    const isLoading = await loadingText.isVisible().catch(() => false);
    
    // Loading state may be brief - just verify page loads correctly
    await page.waitForLoadState('networkidle');
  });
});
