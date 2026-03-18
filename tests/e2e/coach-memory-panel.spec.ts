/**
 * Coach Memory Panel E2E Tests
 * 
 * Tests the CoachMemoryPanel component that shows real personalized data
 * from the coach_memory system. Tests data-testid attributes, API integration,
 * and display of personalized coaching data.
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://chess-lab-sync.preview.emergentagent.com';

test.describe('Coach Memory Panel - UI Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Login via landing page Dev Login button, then navigate via sidebar
    await page.goto(`${BASE_URL}/`);
    await page.waitForLoadState('domcontentloaded');
    
    // Click Dev Login
    await page.locator('text=Dev Login').click();
    await page.waitForTimeout(1500);
    
    // Wait for dashboard to load
    await expect(page.locator('text=Welcome back')).toBeVisible({ timeout: 10000 });
  });

  test('CoachMemoryPanel renders with data-testid on Coach Play page', async ({ page }) => {
    // Click Play with Coach in sidebar
    await page.locator('text=Play with Coach').click();
    await page.waitForTimeout(2000);
    
    // Check for the coach memory panel with data-testid
    const memoryPanel = page.getByTestId('coach-memory-panel');
    await expect(memoryPanel).toBeVisible({ timeout: 10000 });
    
    await page.screenshot({ path: 'coach-memory-panel-visible.jpeg', quality: 20 });
  });

  test('Panel shows games together count', async ({ page }) => {
    // Navigate to Play with Coach
    await page.locator('text=Play with Coach').click();
    await page.waitForTimeout(2000);
    
    // Check for the coach memory panel
    const memoryPanel = page.getByTestId('coach-memory-panel');
    await expect(memoryPanel).toBeVisible({ timeout: 10000 });
    
    // The panel should show "X games together" text in the stats footer
    const gamesText = memoryPanel.locator('text=/\\d+ games together/');
    await expect(gamesText).toBeVisible({ timeout: 5000 });
  });

  test('Panel shows watch_for patterns with improvement indicators', async ({ page }) => {
    // Navigate to Play with Coach
    await page.locator('text=Play with Coach').click();
    await page.waitForTimeout(2000);
    
    // Check for watch-for-patterns section
    const watchForSection = page.getByTestId('watch-for-patterns');
    
    // This section should be visible if user has patterns
    const isVisible = await watchForSection.isVisible().catch(() => false);
    
    if (isVisible) {
      // Should show "I'm Watching For" header
      await expect(watchForSection).toContainText(/Watching For/i);
      
      // Should show pattern items with counts - use .first() for strict mode
      await expect(watchForSection.locator('text=/\\d+x/').first()).toBeVisible();
      
      await page.screenshot({ path: 'watch-for-patterns.jpeg', quality: 20 });
    }
  });

  test('Panel shows focus_suggestion from API', async ({ page }) => {
    // Navigate to Play with Coach
    await page.locator('text=Play with Coach').click();
    await page.waitForTimeout(2000);
    
    // Check for focus-today section
    const focusSection = page.getByTestId('focus-today');
    
    // This section may or may not be visible depending on user data
    const isVisible = await focusSection.isVisible().catch(() => false);
    
    if (isVisible) {
      // Should show "Today's Focus" header
      await expect(focusSection).toContainText(/Today's Focus/i);
      
      await page.screenshot({ path: 'focus-today.jpeg', quality: 20 });
    }
  });

  test('Panel shows last_game_insights', async ({ page }) => {
    // Navigate to Play with Coach
    await page.locator('text=Play with Coach').click();
    await page.waitForTimeout(2000);
    
    // Check for last-insight section  
    const insightSection = page.getByTestId('last-insight');
    
    // This section may or may not be visible depending on user data
    const isVisible = await insightSection.isVisible().catch(() => false);
    
    if (isVisible) {
      // Should contain some text (the insight)
      const text = await insightSection.textContent();
      expect(text?.length).toBeGreaterThan(5);
      
      await page.screenshot({ path: 'last-insight.jpeg', quality: 20 });
    }
  });

  test('Panel shows Game # count', async ({ page }) => {
    // Navigate to Play with Coach
    await page.locator('text=Play with Coach').click();
    await page.waitForTimeout(2000);
    
    // Check for coach memory panel
    const memoryPanel = page.getByTestId('coach-memory-panel');
    await expect(memoryPanel).toBeVisible({ timeout: 10000 });
    
    // Should show Game #X indicator
    await expect(memoryPanel.locator('text=/Game #\\d+/')).toBeVisible();
  });

  test('Panel shows average accuracy', async ({ page }) => {
    // Navigate to Play with Coach
    await page.locator('text=Play with Coach').click();
    await page.waitForTimeout(2000);
    
    // Check for coach memory panel
    const memoryPanel = page.getByTestId('coach-memory-panel');
    await expect(memoryPanel).toBeVisible({ timeout: 10000 });
    
    // Should show accuracy percentage (e.g., 97% avg) - text shows "97%" followed by "avg"
    // Use .first() since there may be multiple percentage mentions
    await expect(memoryPanel.locator('text=/\\d+%/').first()).toBeVisible();
  });
});

test.describe('Coach Memory API Integration', () => {
  test('GET /api/coach/memory returns context with required fields', async ({ page }) => {
    // Dev login first via API
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    
    // Fetch memory API
    const response = await page.request.get(`${BASE_URL}/api/coach/memory`);
    
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    
    // Verify structure
    expect(data).toHaveProperty('greeting');
    expect(data).toHaveProperty('context');
    
    const ctx = data.context;
    expect(ctx).toHaveProperty('games_played');
    expect(ctx).toHaveProperty('avg_accuracy');
    expect(ctx).toHaveProperty('watch_for');
    expect(ctx).toHaveProperty('focus_suggestion');
    expect(ctx).toHaveProperty('last_game_insights');
    expect(ctx).toHaveProperty('openings_known');
    expect(ctx).toHaveProperty('improving');
  });

  test('watch_for patterns have correct structure', async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    
    const response = await page.request.get(`${BASE_URL}/api/coach/memory`);
    const data = await response.json();
    
    const watchFor = data.context.watch_for;
    expect(Array.isArray(watchFor)).toBe(true);
    
    // If there are patterns, verify each has required fields
    for (const pattern of watchFor) {
      expect(pattern).toHaveProperty('name');
      expect(pattern).toHaveProperty('count');
      expect(pattern).toHaveProperty('improving');
      
      expect(typeof pattern.name).toBe('string');
      expect(typeof pattern.count).toBe('number');
      expect(typeof pattern.improving).toBe('boolean');
    }
  });
});
