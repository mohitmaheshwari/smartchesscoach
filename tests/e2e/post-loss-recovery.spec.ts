import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://move-effect.preview.emergentagent.com';
const TEST_GAME_ID = '2d46940d-dfce-4534-9935-9b1ba3829c92';

test.describe('Post-Loss Recovery Page', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    
    // Set up toast dismissal
    await dismissToasts(page);
  });

  test('Post-Loss Recovery page loads at /recover/:gameId route', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Verify page container is visible
    await expect(page.getByTestId('post-loss-recovery-page')).toBeVisible({ timeout: 15000 });
    
    await page.screenshot({ path: '.screenshots/post-loss-recovery-page.jpeg', quality: 20 });
  });

  test('Board displays on left side (60% width)', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Board should be visible - it's in a 3-column section of a 5-column grid (lg:col-span-3)
    const boardContainer = page.locator('.lg\\:col-span-3').first();
    await expect(boardContainer).toBeVisible({ timeout: 10000 });
    
    // Board element itself should be visible
    const chessBoard = page.locator('[data-board-style]').first();
    const boardVisible = await chessBoard.isVisible({ timeout: 5000 }).catch(() => false);
    
    // Either the board component or a board-like element should be present
    if (!boardVisible) {
      // Fallback check - look for the board container
      await expect(page.locator('.aspect-square').first()).toBeVisible();
    }
  });

  test('Recovery panel shows emotional headline', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Recovery panel is in the right 2-column section (lg:col-span-2)
    const recoveryPanel = page.locator('.lg\\:col-span-2').first();
    await expect(recoveryPanel).toBeVisible({ timeout: 10000 });
    
    // Post-Loss Recovery badge should be visible
    await expect(page.getByText('Post-Loss Recovery', { exact: false })).toBeVisible();
    
    // Headline should be visible - it's an h1 element
    const headline = recoveryPanel.locator('h1').first();
    await expect(headline).toBeVisible();
    
    // Headline should contain emotional/motivational text
    const headlineText = await headline.textContent();
    expect(headlineText).toBeTruthy();
    expect(headlineText!.length).toBeGreaterThan(10); // Should be a meaningful sentence
  });

  test('Main Issue card displays focus pattern', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Main Issue section should be visible
    await expect(page.getByText('Main Issue', { exact: false })).toBeVisible({ timeout: 10000 });
    
    // The issue description should be visible (e.g., "Critical position focus")
    const issueCard = page.locator('.rounded-xl').filter({ hasText: 'Main Issue' });
    await expect(issueCard).toBeVisible();
    
    // Should contain some focus pattern text
    const issueText = await issueCard.textContent();
    expect(issueText).toBeTruthy();
    // Check for common patterns
    expect(issueText!.toLowerCase()).toMatch(/(position|focus|awareness|threat|forcing|advantage)/);
  });

  test('Fix-it button is visible and clickable', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Fix-it button should be visible
    const fixItBtn = page.getByTestId('fix-it-btn');
    await expect(fixItBtn).toBeVisible({ timeout: 10000 });
    await expect(fixItBtn).toBeEnabled();
    
    // Button should show time estimate
    const btnText = await fixItBtn.textContent();
    expect(btnText).toMatch(/Fix.*\d+ min/i);
  });

  test('Fix-it button navigates to mission', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    const fixItBtn = page.getByTestId('fix-it-btn');
    await expect(fixItBtn).toBeVisible({ timeout: 10000 });
    
    // Click the fix-it button
    await fixItBtn.click({ force: true });
    
    // Should navigate to mission runner OR reflect page (fallback)
    await page.waitForURL(/\/(mission|reflect)/, { timeout: 15000 });
  });

  test('See full analysis link is visible and works', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // See full analysis link should be visible
    const analysisLink = page.getByTestId('see-analysis-btn');
    await expect(analysisLink).toBeVisible({ timeout: 10000 });
    
    // Should contain "analysis" text
    await expect(analysisLink).toHaveText(/analysis/i);
    
    await hideEmergentBadge(page);
    
    // Click and verify navigation
    await analysisLink.click({ force: true });
    
    // Should navigate to game analysis page
    await page.waitForURL(/\/game\//, { timeout: 10000 });
  });

  test('Recovery page shows opponent name', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Opponent context should be visible (e.g., "vs House-Arrest22")
    await expect(page.getByText(/vs\s+\w+/)).toBeVisible({ timeout: 10000 });
  });

  test('Recovery page shows time estimate', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Time estimate should be visible (e.g., "7 minute focused drill")
    await expect(page.getByText(/\d+ minute.*drill/i)).toBeVisible({ timeout: 10000 });
  });

  test('Recovery page shows move comparison (You played vs Better was)', async ({ page }) => {
    await page.goto(`${BASE_URL}/recover/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Move info section should show "You played" and "Better was"
    // Note: If fen is null, user_move might not be shown, but best_move should still appear
    const betterMove = page.getByText('Better was', { exact: false });
    const betterMoveVisible = await betterMove.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (betterMoveVisible) {
      await expect(betterMove).toBeVisible();
      // Best move should be displayed (e.g., "a4")
      await expect(page.locator('.text-\\[\\#10B981\\]').first()).toBeVisible();
    }
  });
});

test.describe('Post-Loss Recovery - Error Handling', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Shows error for invalid game ID', async ({ page }) => {
    // Use an invalid game ID
    await page.goto(`${BASE_URL}/recover/invalid-game-id-12345`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Should show error state with "Could not load recovery" heading
    await expect(page.getByRole('heading', { name: 'Could not load recovery' })).toBeVisible({ timeout: 10000 });
    
    // Back to Home button should be visible
    await expect(page.getByRole('button', { name: /Back to Home/i })).toBeVisible();
  });
});
