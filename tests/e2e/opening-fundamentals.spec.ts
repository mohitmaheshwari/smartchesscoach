import { test, expect } from '@playwright/test';

/**
 * Opening Fundamentals Bug Fix Verification
 * 
 * Bug: OpeningFundamentals component was using incorrect API URL (missing /api prefix)
 * Fix: Changed to import API from @/App instead of local constant
 * 
 * Tests verify:
 * 1. Opening fundamentals API endpoint returns correct data
 * 2. OpeningFundamentals component renders in Habits tab
 * 3. Lab page tabs are functional
 */

test.describe('Opening Fundamentals Bug Fix', () => {
  // Get a game ID for testing
  const testGameId = '017161e5-cae3-47cb-89a3-9d774b16d2ca';
  
  test.beforeEach(async ({ page }) => {
    // Login via dev endpoint
    await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
  });

  test('Opening fundamentals API returns valid data', async ({ request }) => {
    // First login to get session
    const loginRes = await request.get('/api/auth/dev-login');
    expect(loginRes.ok()).toBeTruthy();
    
    // Call the opening fundamentals endpoint
    const res = await request.get(`/api/analysis/${testGameId}/opening-fundamentals`);
    expect(res.ok()).toBeTruthy();
    
    const data = await res.json();
    
    // Verify response structure
    expect(data).toHaveProperty('score');
    expect(data).toHaveProperty('violations');
    expect(data).toHaveProperty('adherences');
    expect(data).toHaveProperty('summary');
    expect(data).toHaveProperty('total_violations');
    
    // Score should be a number between 0 and 100
    expect(typeof data.score).toBe('number');
    expect(data.score).toBeGreaterThanOrEqual(0);
    expect(data.score).toBeLessThanOrEqual(100);
    
    // Arrays should exist
    expect(Array.isArray(data.violations)).toBeTruthy();
    expect(Array.isArray(data.adherences)).toBeTruthy();
  });

  test('Lab page loads with all tabs visible', async ({ page }) => {
    await page.goto(`/lab/game/${testGameId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Verify tab triggers are visible (using role="tab" for Radix tabs)
    await expect(page.getByRole('tab', { name: /summary/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /moments/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /ideas/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /habits/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /memory/i })).toBeVisible();
  });

  test('OpeningFundamentals component renders in Habits tab', async ({ page }) => {
    await page.goto(`/lab/game/${testGameId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Click on Habits tab
    await page.getByRole('tab', { name: /habits/i }).click();
    await page.waitForTimeout(2000);
    
    // Verify Opening Fundamentals component renders
    await expect(page.getByTestId('opening-fundamentals')).toBeVisible();
    
    // The component should show "Opening Fundamentals" title
    await expect(page.getByText('Opening Fundamentals')).toBeVisible();
    
    // Should show a score percentage
    const scoreElement = page.locator('text=/\\d+%/').first();
    await expect(scoreElement).toBeVisible();
  });

  test('Opening Fundamentals displays principles correctly', async ({ page }) => {
    await page.goto(`/lab/game/${testGameId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Click on Habits tab
    await page.getByRole('tab', { name: /habits/i }).click();
    await page.waitForTimeout(2000);
    
    // Wait for the component to load
    await expect(page.getByTestId('opening-fundamentals')).toBeVisible();
    
    // For this test game with 100% score, it should show "Principles Followed"
    // (adherences list) or "Principles to Work On" (violations list)
    const followedSection = page.getByText('Principles Followed');
    const violationsSection = page.getByText('Principles to Work On');
    
    // At least one of these should be visible
    const hasFollowed = await followedSection.isVisible().catch(() => false);
    const hasViolations = await violationsSection.isVisible().catch(() => false);
    
    expect(hasFollowed || hasViolations).toBeTruthy();
    
    // Should show coach advice
    await expect(page.getByText(/Coach's Advice/i)).toBeVisible();
  });

  test('All Lab page tabs are functional', async ({ page }) => {
    await page.goto(`/lab/game/${testGameId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Test each tab
    const tabs = ['Summary', 'Moments', 'Ideas', 'Habits', 'Memory'];
    
    for (const tab of tabs) {
      await page.getByRole('tab', { name: new RegExp(tab, 'i') }).click();
      await page.waitForTimeout(1000);
      
      // Verify the tab is selected (has aria-selected or data-state="active")
      const tabElement = page.getByRole('tab', { name: new RegExp(tab, 'i') });
      const dataState = await tabElement.getAttribute('data-state');
      expect(dataState).toBe('active');
    }
  });

  test('Lab page shows game information correctly', async ({ page }) => {
    await page.goto(`/lab/game/${testGameId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Should show "Game Review" heading
    await expect(page.getByText('Game Review')).toBeVisible();
    
    // Should show accuracy percentage using first() to avoid strict mode
    await expect(page.getByText(/\d+% accuracy/i).first()).toBeVisible();
    
    // Should show Back button
    await expect(page.locator('text=Back').first()).toBeVisible();
  });
});
