import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts } from '../fixtures/helpers';

const BASE_URL = 'https://self-learn-chess.preview.emergentagent.com';

/**
 * AlternateTimeline Component Tests
 * 
 * Tests for the "What if you played X?" feature that shows the engine's
 * expected continuation if the user had played the better move.
 * 
 * Features tested:
 * 1. AlternateTimeline renders with 'What if you played X?' header
 * 2. Shows 'Saved X pawns' badge from cpLoss data
 * 3. Shows PV move sequence when expanded
 * 4. Mini board displays the position
 * 5. 'Play through' button cycles through positions
 * 6. Only shows when pv_after_best data is available
 */

// Test game with pv_after_best data for move 20 where better_move='Nxd4'
// pv_after_best=['Rd5', 'Rad8', 'Rxd8', 'Rxd8']
const TEST_GAME_ID = '42932bfa-24e8-4aff-9068-0b476cb6f4fc';

test.describe('AlternateTimeline Component', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login to access the Lab page
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('AlternateTimeline renders with "What if you played X?" header', async ({ page }) => {
    // Navigate to Lab page with test game
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Verify lab page loads
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // Verify AlternateTimeline component is visible
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await expect(alternateTimeline).toBeVisible({ timeout: 5000 });
    
    // Verify header shows "What if you played Nxd4?"
    await expect(alternateTimeline.locator('text=What if you played Nxd4?')).toBeVisible();
  });

  test('AlternateTimeline shows "Saved X pawns" badge from cpLoss data', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // Verify AlternateTimeline component is visible
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await expect(alternateTimeline).toBeVisible({ timeout: 5000 });
    
    // Verify cpLoss badge shows "Saved X pawns" (should show ~6.3 pawns for this move)
    // The badge format is "Saved {cpLoss/100}.toFixed(1) pawns"
    await expect(alternateTimeline.locator('text=/Saved \\d+\\.\\d+ pawns/')).toBeVisible();
  });

  test('AlternateTimeline shows PV move sequence when expanded', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // Click on AlternateTimeline to expand
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await alternateTimeline.click();
    await page.waitForTimeout(500);
    
    // Verify PV moves are visible
    // pv_after_best=['Rd5', 'Rad8', 'Rxd8', 'Rxd8']
    // The better move appears in the PV sequence (use .first() as Nxd4 appears in header too)
    await expect(alternateTimeline.locator('span.text-emerald-400.font-medium', { hasText: 'Nxd4' }).first()).toBeVisible();
    await expect(alternateTimeline.locator('button:has-text("Rd5")')).toBeVisible();  // First PV move
    await expect(alternateTimeline.locator('button:has-text("Rad8")')).toBeVisible(); // Second PV move
    await expect(alternateTimeline.locator('button:has-text("Rxd8")').first()).toBeVisible(); // Third PV move (appears twice)
  });

  test('AlternateTimeline mini board displays the position', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // Click on AlternateTimeline to expand
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await alternateTimeline.click();
    await page.waitForTimeout(500);
    
    // Verify mini board is visible (react-chessboard renders as a div with specific structure)
    // The mini board is in a 140x140px container
    const miniBoard = alternateTimeline.locator('[class*="w-\\[140px\\]"]').or(
      alternateTimeline.locator('div').filter({ has: page.locator('[data-testid="chessboard"]') })
    );
    
    // Verify board content exists (squares or pieces)
    // Check for the chessboard wrapper or any chess pieces
    const boardExists = await alternateTimeline.evaluate((el) => {
      // Look for react-chessboard rendered content
      const boardContainer = el.querySelector('[class*="140px"]');
      return boardContainer !== null;
    });
    expect(boardExists).toBeTruthy();
    
    // Also verify the description text next to the board
    await expect(alternateTimeline.locator('text=This was the position')).toBeVisible();
  });

  test('AlternateTimeline "Play through" button cycles through positions', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // Click on AlternateTimeline to expand
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await alternateTimeline.click();
    await page.waitForTimeout(500);
    
    // Verify "Play through" button is visible initially
    await expect(alternateTimeline.locator('text=Play through')).toBeVisible();
    
    // Click "Play through" button
    await alternateTimeline.locator('text=Play through').click();
    await page.waitForTimeout(500);
    
    // After clicking, button text should change to "Next move"
    await expect(alternateTimeline.locator('text=Next move')).toBeVisible();
    
    // Description should change to show we're after the better move
    await expect(alternateTimeline.locator('text=/solid advantage|continue naturally/')).toBeVisible();
    
    // Click "Next move" to cycle through
    await alternateTimeline.locator('text=Next move').click();
    await page.waitForTimeout(500);
    
    // Description should mention "continue naturally"
    await expect(alternateTimeline.locator('text=continue naturally')).toBeVisible();
  });

  test('AlternateTimeline clicking on a PV move updates the board preview', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // Click on AlternateTimeline to expand
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await alternateTimeline.click();
    await page.waitForTimeout(500);
    
    // Initial state: "This was the position" text
    await expect(alternateTimeline.locator('text=This was the position')).toBeVisible();
    
    // Click on a PV move (Rd5)
    await alternateTimeline.locator('button:has-text("Rd5")').click();
    await page.waitForTimeout(500);
    
    // Description should change (no longer "This was the position")
    const positionText = await alternateTimeline.locator('text=This was the position').count();
    expect(positionText).toBe(0); // Text should be different now
    
    // The Rd5 button should now be highlighted
    const rd5Button = alternateTimeline.locator('button:has-text("Rd5")');
    const rd5Classes = await rd5Button.getAttribute('class');
    expect(rd5Classes).toMatch(/emerald-500|emerald-300/); // Should have emerald highlight class
  });

  test('AlternateTimeline expands and collapses on header click', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await expect(alternateTimeline).toBeVisible({ timeout: 5000 });
    
    // Initially collapsed - "Play through" should not be visible
    const playThroughInitial = await alternateTimeline.locator('text=Play through').count();
    expect(playThroughInitial).toBe(0);
    
    // Click to expand
    await alternateTimeline.click();
    await page.waitForTimeout(500);
    
    // Now expanded - "Play through" should be visible
    await expect(alternateTimeline.locator('text=Play through')).toBeVisible();
    
    // Click header again to collapse
    await alternateTimeline.locator('button').first().click();
    await page.waitForTimeout(500);
    
    // Collapsed again - "Play through" should not be visible
    const playThroughFinal = await alternateTimeline.locator('text=Play through').count();
    expect(playThroughFinal).toBe(0);
  });

  test('AlternateTimeline shows coaching insight when expanded', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // Click on AlternateTimeline to expand
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await alternateTimeline.click();
    await page.waitForTimeout(500);
    
    // Verify coaching insight text at the bottom
    await expect(alternateTimeline.locator('text=This is the line the engine expected')).toBeVisible();
  });
});

test.describe('AlternateTimeline - Conditional Rendering', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('AlternateTimeline only shows when pv_after_best data is available', async ({ page }) => {
    // Navigate to the test game which has pv_after_best data
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    // For this test game (with pv_after_best=['Rd5', 'Rad8', 'Rxd8', 'Rxd8']),
    // the component should be visible
    const alternateTimeline = page.getByTestId('alternate-timeline');
    const isVisible = await alternateTimeline.isVisible({ timeout: 5000 }).catch(() => false);
    
    // Based on the game data, AlternateTimeline should be visible
    // because biggestEvalSwing.pv_after_best should have data
    expect(isVisible).toBeTruthy();
  });
});

test.describe('AlternateTimeline - Visual Verification', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('AlternateTimeline has correct visual styling', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 15000 });
    
    // Click Summary tab
    await page.locator('button:has-text("Summary")').first().click();
    await page.waitForTimeout(1000);
    
    // Scroll to see AlternateTimeline
    const scrollArea = page.locator('[data-radix-scroll-area-viewport]').last();
    await scrollArea.evaluate(el => el.scrollTop = 250);
    await page.waitForTimeout(500);
    
    const alternateTimeline = page.getByTestId('alternate-timeline');
    await expect(alternateTimeline).toBeVisible({ timeout: 5000 });
    
    // Verify it has emerald/green styling (the border and background)
    const classes = await alternateTimeline.getAttribute('class');
    expect(classes).toMatch(/emerald|green/);
    
    // Verify it has rounded corners
    expect(classes).toMatch(/rounded/);
  });
});
