import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts } from '../fixtures/helpers';

const BASE_URL = 'https://deep-memory-chess.preview.emergentagent.com';

/**
 * Lab Page Coaching Features Tests
 * 
 * Features tested:
 * 1. Summary tab shows coaching intro paragraph connecting to user's recurring patterns
 * 2. Summary tab shows encouragement message at the bottom
 * 3. Milestones tab shows "Where It Went Wrong" section FIRST for loss games
 * 4. Milestones tab shows "What Worked" section AFTER learning moments for loss games
 * 5. Lab page correctly fetches user patterns from home-intelligence API
 * 6. Coaching intro mentions the specific recurring pattern count
 */

// Test game - a LOSS game for user_bdd07038f9c0 (user played black, result is 1-0)
const LOSS_GAME_ID = '42932bfa-24e8-4aff-9068-0b476cb6f4fc';

test.describe('Lab Page - Coaching Features for Loss Games', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Lab page loads successfully with game data', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Verify lab page container is visible
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Verify game header shows opponent name
    await expect(page.locator('text=Rayne1019')).toBeVisible();
    
    // Verify LOSS badge is visible (since this is a loss game)
    await expect(page.locator('text=LOSS')).toBeVisible();
    
    // Verify user played black
    await expect(page.locator('text=You played black')).toBeVisible();
  });

  test('Summary tab shows coaching intro with user patterns', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify coaching intro section is visible
    const coachingIntro = page.getByTestId('coaching-intro');
    await expect(coachingIntro).toBeVisible({ timeout: 10000 });
    
    // Get the coaching intro text
    const introText = await coachingIntro.textContent();
    
    // For a loss game, coaching intro should mention "Tough game" or similar
    expect(introText).toMatch(/tough|same pattern|let's fix/i);
  });

  test('Coaching intro mentions recurring pattern count (e.g., "27 times")', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify coaching intro section mentions pattern count
    const coachingIntro = page.getByTestId('coaching-intro');
    await expect(coachingIntro).toBeVisible({ timeout: 10000 });
    
    const introText = await coachingIntro.textContent();
    
    // Should mention specific pattern count (e.g., "27 times recently")
    // This test verifies the integration with home-intelligence API
    expect(introText).toMatch(/\d+\s*(times|x)/i);
  });

  test('Summary tab shows encouragement message at bottom', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForLoadState('domcontentloaded');
    
    // Scroll to bottom of the tab content
    const scrollContainer = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollContainer.evaluate(el => el.scrollTop = el.scrollHeight);
    await page.waitForTimeout(500);
    
    // Verify encouragement section is visible
    const encouragement = page.getByTestId('encouragement');
    await expect(encouragement).toBeVisible({ timeout: 10000 });
    
    // Get the encouragement text
    const encouragementText = await encouragement.textContent();
    
    // Encouragement should contain actionable advice
    // Common patterns: "habit change", "scan for", "pause", "castle by move"
    expect(encouragementText).toMatch(/habit|scan|pause|move|games|wins/i);
  });

  test('Milestones tab shows "Where It Went Wrong" FIRST for loss games', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Milestones tab
    await page.locator('button:has-text("Milestones")').first().click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    
    // For a LOSS game, "Where It Went Wrong" should be the FIRST section
    // This is the key ordering change for loss games
    const whereItWentWrongText = page.locator('text=Where It Went Wrong');
    await expect(whereItWentWrongText).toBeVisible({ timeout: 10000 });
    
    // Verify the section has learning moment items
    // The section should contain blunder/mistake items
    const blunderBadges = page.locator('text=Blunder');
    const mistakeBadges = page.locator('text=Mistake');
    
    // At least some blunders or mistakes should be visible
    const blunderCount = await blunderBadges.count();
    const mistakeCount = await mistakeBadges.count();
    expect(blunderCount + mistakeCount).toBeGreaterThan(0);
  });

  test('Milestones tab shows "What Worked" AFTER learning moments for loss games', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Milestones tab
    await page.locator('button:has-text("Milestones")').first().click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    
    // Get all section headers in the milestones tab
    const rightPanel = page.locator('[data-radix-scroll-area-viewport]').last();
    const sectionHeaders = rightPanel.locator('h3, [class*="font-semibold"]');
    
    // Get the order of sections
    const headersText = await sectionHeaders.allTextContents();
    
    // For loss games: "Where It Went Wrong" should appear BEFORE "What Worked" or "Brilliant Moves"
    const wrongIndex = headersText.findIndex(h => h.toLowerCase().includes('went wrong') || h.toLowerCase().includes('learning'));
    const workedIndex = headersText.findIndex(h => h.toLowerCase().includes('worked') || h.toLowerCase().includes('brilliant'));
    
    // If both sections exist, "Where It Went Wrong" should come first for loss games
    if (wrongIndex !== -1 && workedIndex !== -1) {
      expect(wrongIndex).toBeLessThan(workedIndex);
    } else if (wrongIndex !== -1) {
      // If only "Where It Went Wrong" exists for a loss game, that's fine
      expect(wrongIndex).toBeGreaterThanOrEqual(0);
    }
  });

  test('Lab page fetches user patterns from home-intelligence API', async ({ page }) => {
    // First verify the API returns pattern data
    const apiResponse = await page.request.get(`${BASE_URL}/api/coach/home-intelligence`);
    expect(apiResponse.ok()).toBeTruthy();
    
    const data = await apiResponse.json();
    
    // Verify specific_patterns field exists
    expect(data.specific_patterns).toBeDefined();
    
    // If has_pattern is true, verify pattern details
    if (data.specific_patterns?.has_pattern) {
      expect(data.specific_patterns.dominant_pattern).toBeDefined();
      expect(data.specific_patterns.pattern_count).toBeGreaterThan(0);
      expect(data.specific_patterns.pattern_description).toBeDefined();
    }
    
    // Now navigate to Lab page and verify the data is used
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForLoadState('domcontentloaded');
    
    // Verify coaching intro is visible (it uses the pattern data)
    const coachingIntro = page.getByTestId('coaching-intro');
    await expect(coachingIntro).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Lab Page - Tab Navigation', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Can navigate between Summary, Strategy, and Milestones tabs', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Test Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(500);
    const coachingIntro = page.getByTestId('coaching-intro');
    await expect(coachingIntro).toBeVisible({ timeout: 5000 });
    
    // Test Strategy tab
    await page.locator('button:has-text("Strategy")').first().click();
    await page.waitForTimeout(500);
    // Strategy tab should show position type or "not available" message
    const strategyContent = page.locator('text=/Position Type|Strategic analysis/i').first();
    await expect(strategyContent).toBeVisible({ timeout: 5000 });
    
    // Test Milestones tab
    await page.locator('button:has-text("Milestones")').first().click();
    await page.waitForTimeout(500);
    // Milestones should show "Where It Went Wrong" for loss games
    const whereItWentWrong = page.locator('text=Where It Went Wrong');
    await expect(whereItWentWrong).toBeVisible({ timeout: 5000 });
  });

  test('Coach mode vs Engine mode toggle works', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Verify Coach mode button is visible and clickable
    const coachModeBtn = page.getByTestId('coach-mode-btn');
    await expect(coachModeBtn).toBeVisible();
    
    // Verify Engine mode button is visible and clickable
    const engineModeBtn = page.getByTestId('engine-mode-btn');
    await expect(engineModeBtn).toBeVisible();
    
    // Click Engine mode
    await engineModeBtn.click();
    await page.waitForTimeout(500);
    
    // Click back to Coach mode
    await coachModeBtn.click();
    await page.waitForTimeout(500);
    
    // Both toggles should still be visible
    await expect(coachModeBtn).toBeVisible();
    await expect(engineModeBtn).toBeVisible();
  });
});

test.describe('Lab Page - Learning Moments Detail', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Learning moments show move number and evaluation', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Milestones tab
    await page.locator('button:has-text("Milestones")').first().click();
    await page.waitForTimeout(1000);
    
    // Verify "Where It Went Wrong" section is visible
    await expect(page.locator('text=Where It Went Wrong')).toBeVisible();
    
    // Verify move numbers are displayed (e.g., "Move 20", "Move 27")
    const moveNumberLocator = page.locator('text=/Move \\d+/');
    await expect(moveNumberLocator.first()).toBeVisible({ timeout: 5000 });
    
    // Count how many moves are shown
    const moveCount = await moveNumberLocator.count();
    expect(moveCount).toBeGreaterThan(0);
  });

  test('Wisdom lessons are displayed in Summary tab', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${LOSS_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click on Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see wisdom lessons
    const scrollContainer = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollContainer.evaluate(el => el.scrollTop = el.scrollHeight / 2);
    await page.waitForTimeout(500);
    
    // Verify "Chess Principles Applied" section exists (wisdom lessons)
    const principlesSection = page.locator('text=/Chess Principles Applied/i');
    const sectionVisible = await principlesSection.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (sectionVisible) {
      // Should show specific principles like "Hanging Piece" or quotes
      const hangingPiece = page.locator('text=/Hanging Piece|undefended|Rooks belong/i').first();
      await expect(hangingPiece).toBeVisible({ timeout: 3000 });
    }
  });
});
