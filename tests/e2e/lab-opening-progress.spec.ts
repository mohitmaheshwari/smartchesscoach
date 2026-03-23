/**
 * Lab Page Opening Progress E2E Tests
 * 
 * Tests the new Opening Progress section in the Habits tab:
 * 1. Opening Progress section shows in Habits tab
 * 2. Shows mastery levels correctly
 * 3. Shows coach-taught vs not-taught openings
 * 4. Show All button expands the list
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://move-intent-engine.preview.emergentagent.com';

async function devLogin(page: Page) {
  await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
}

test.describe('Lab Page Habits Tab - Opening Progress', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
  });

  test('should navigate to game analysis and see Habits tab', async ({ page }) => {
    // Navigate to Analyze page
    await page.click('text=Analyze');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    // Click on Analyzed games to open modal
    await page.click('text=Analyzed');
    await page.waitForTimeout(1000);
    
    // Click on first game (with force to handle modal overlay)
    const firstGame = page.locator('[data-state="open"] .cursor-pointer').first();
    await firstGame.click({ force: true });
    
    // Wait for game analysis to load
    await page.waitForTimeout(3000);
    
    // Click on Habits tab
    await page.click('text=Habits');
    await page.waitForTimeout(1000);
    
    // Verify Habits to Improve section is visible
    await expect(page.getByText('Habits to Improve')).toBeVisible();
    
    // Take screenshot
    await page.screenshot({ path: '/app/tests/e2e/lab-habits-tab-view.jpeg', quality: 20 });
  });

  test('should show Opening Progress section in Habits tab', async ({ page }) => {
    // Navigate directly to a game via URL
    await page.goto('/lab/game/9fbf5515-148b-4a0b-8d5e-38b6b06c164d', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click on Habits tab
    await page.click('text=Habits');
    await page.waitForTimeout(2000);
    
    // Verify Opening Progress section is visible
    await expect(page.getByText('Opening Progress')).toBeVisible({ timeout: 10000 });
    
    // Take screenshot
    await page.screenshot({ path: '/app/tests/e2e/opening-progress-section.jpeg', quality: 20 });
  });

  test('should display opening mastery levels correctly', async ({ page }) => {
    // Navigate directly to a game
    await page.goto('/lab/game/9fbf5515-148b-4a0b-8d5e-38b6b06c164d', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click on Habits tab
    await page.click('text=Habits');
    await page.waitForTimeout(2000);
    
    // Check for mastery level badges - they appear in Badge components
    // Valid levels: unknown, introduced, learning, practiced, mastered
    // The UI displays "Introduced" or "Unknown" etc. inside badge elements
    
    // Look for badges within the Opening Progress section
    const openingProgressSection = page.locator('text=Opening Progress').locator('..');
    
    // Check that we can see at least one of the level texts
    const introText = page.getByText('Introduced');
    const unknownText = page.getByText('Unknown');
    const learningText = page.getByText('Learning');
    const practicedText = page.getByText('Practiced');
    const masteredText = page.getByText('Mastered');
    
    const foundIntro = await introText.isVisible({ timeout: 2000 }).catch(() => false);
    const foundUnknown = await unknownText.isVisible({ timeout: 2000 }).catch(() => false);
    const foundLearning = await learningText.isVisible({ timeout: 2000 }).catch(() => false);
    const foundPracticed = await practicedText.isVisible({ timeout: 2000 }).catch(() => false);
    const foundMastered = await masteredText.isVisible({ timeout: 2000 }).catch(() => false);
    
    const foundLevel = foundIntro || foundUnknown || foundLearning || foundPracticed || foundMastered;
    
    expect(foundLevel).toBe(true);
  });

  test('should show learned count in Opening Progress header', async ({ page }) => {
    // Navigate directly to a game
    await page.goto('/lab/game/9fbf5515-148b-4a0b-8d5e-38b6b06c164d', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click on Habits tab
    await page.click('text=Habits');
    await page.waitForTimeout(2000);
    
    // Check for "X learned" text in the Opening Progress section
    const learnedText = page.getByText(/\d+ learned/);
    await expect(learnedText).toBeVisible({ timeout: 5000 });
  });

  test('should show Show All button when more than 3 openings', async ({ page }) => {
    // Navigate directly to a game
    await page.goto('/lab/game/9fbf5515-148b-4a0b-8d5e-38b6b06c164d', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click on Habits tab
    await page.click('text=Habits');
    await page.waitForTimeout(2000);
    
    // Check for Show All button (appears when > 3 openings)
    const showAllBtn = page.getByText(/Show All \(\d+\)/);
    const isVisible = await showAllBtn.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (isVisible) {
      // Click to expand
      await showAllBtn.click();
      await page.waitForTimeout(500);
      
      // Should now show "Show Less"
      await expect(page.getByText('Show Less')).toBeVisible();
    }
  });
});

test.describe('Opening Progress API Integration', () => {
  test('API should return opening progress data', async ({ page }) => {
    // Dev login first
    await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
    
    // Make API request
    const response = await page.request.get(`${BASE_URL}/api/training/opening-progress`);
    expect(response.ok()).toBe(true);
    
    const data = await response.json();
    
    // Verify structure
    expect(data).toHaveProperty('progress');
    expect(data).toHaveProperty('total_taught');
    expect(data).toHaveProperty('needs_attention');
    expect(Array.isArray(data.progress)).toBe(true);
  });

  test('API should return loss_phases for coach-taught openings', async ({ page }) => {
    await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
    
    const response = await page.request.get(`${BASE_URL}/api/training/opening-progress`);
    expect(response.ok()).toBe(true);
    
    const data = await response.json();
    const coachTaught = data.progress.filter((p: any) => p.coach_taught);
    
    if (coachTaught.length > 0) {
      const opening = coachTaught[0];
      expect(opening).toHaveProperty('loss_phases');
      expect(opening).toHaveProperty('total_losses');
      expect(opening).toHaveProperty('dominant_loss_phase');
    }
  });
});
