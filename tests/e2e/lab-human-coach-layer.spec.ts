/**
 * Lab Human Coach Layer - E2E Tests
 * 
 * Tests the new features added to the Lab page:
 * - Behavioral insights (WHY THIS HAPPENED section)
 * - Coach voice summary in Game Story
 * - Cross-game pattern detection
 * - Memory tab with deep memory profile
 */

import { test, expect } from '@playwright/test';

// Test game ID that has behavioral analysis
const ANALYZED_GAME_ID = '6adb0528-677d-446f-a90d-31a5df0c45b3';

test.describe('Lab Page - Human Coach Layer Features', () => {
  
  test.beforeEach(async ({ page }) => {
    // Login via Dev Login button
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);
    
    const devLoginBtn = page.getByText('Dev Login', { exact: true });
    await devLoginBtn.click();
    await page.waitForTimeout(1500);
  });

  test('should load Lab page with Game Summary', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify basic page structure
    await expect(page.getByText('Game Review')).toBeVisible();
    await expect(page.getByText('Summary')).toBeVisible();
    
    // Verify Game Story section exists
    await expect(page.getByText('GAME STORY')).toBeVisible();
  });

  test('should display TURNING POINT section with mistake details', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify Turning Point section
    await expect(page.getByText('TURNING POINT')).toBeVisible();
    await expect(page.getByText('Move 45')).toBeVisible();
    
    // Verify move played vs better move
    await expect(page.getByText('You played:')).toBeVisible();
    await expect(page.getByText('Better:')).toBeVisible();
    
    // Verify explain button exists
    await expect(page.getByText('Explain this move')).toBeVisible();
  });

  test('should display WHY THIS HAPPENED behavioral insight section', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify behavioral insight section exists
    await expect(page.getByText('WHY THIS HAPPENED')).toBeVisible();
    
    // Verify behavioral tag is displayed (e.g., "positional neglect")
    await expect(page.getByText('positional neglect')).toBeVisible();
    
    // Verify behavioral explanation
    await expect(page.getByText('You ignored positional factors')).toBeVisible();
    
    // Verify detailed explanation
    await expect(page.getByText(/This move looked active but weakened your position/)).toBeVisible();
  });

  test('should display reflection question in behavioral insight', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify reflection question (quoted text box)
    await expect(page.getByText(/What did this move do to your pawn structure/)).toBeVisible();
  });

  test('should display KEY LESSON section', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify Key Lesson section exists
    await expect(page.getByText('KEY LESSON')).toBeVisible();
    
    // Verify lesson content (use first() to avoid strict mode)
    await expect(page.getByText(/What is my opponent threatening/).first()).toBeVisible();
  });

  test('should have working View Position button', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Find and verify View Position button exists
    const viewPositionBtn = page.getByText('View position', { exact: false }).first();
    await expect(viewPositionBtn).toBeVisible();
  });

  test('should display accuracy percentage', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify accuracy display
    await expect(page.getByText('Your accuracy')).toBeVisible();
    await expect(page.getByText('76%').first()).toBeVisible();
  });

  test('should switch to Memory tab and show coach memory data', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click Memory tab
    const memoryTab = page.getByText('Memory', { exact: true });
    await memoryTab.click();
    await page.waitForTimeout(2000);
    
    // Verify Memory tab content
    await expect(page.getByText('Coach Memory')).toBeVisible();
    await expect(page.getByText('15 games')).toBeVisible();
  });

  test('should display blunder profile in Memory tab', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click Memory tab
    const memoryTab = page.getByText('Memory', { exact: true });
    await memoryTab.click();
    await page.waitForTimeout(2000);
    
    // Verify Blunder Profile section
    await expect(page.getByText('Blunder Profile')).toBeVisible();
    await expect(page.getByText('Worst phase:')).toBeVisible();
    await expect(page.getByText('Endgame')).toBeVisible();
    await expect(page.getByText('Most common:')).toBeVisible();
  });

  test('should display playing style in Memory tab', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click Memory tab
    const memoryTab = page.getByText('Memory', { exact: true });
    await memoryTab.click();
    await page.waitForTimeout(2000);
    
    // Verify playing style info
    await expect(page.getByText('Universal Player')).toBeVisible();
    await expect(page.getByText('Still learning your style')).toBeVisible();
  });

  test('should have all tabs visible and clickable', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify all tabs exist
    await expect(page.getByText('Summary')).toBeVisible();
    await expect(page.getByText('Moments')).toBeVisible();
    await expect(page.getByText('Ideas')).toBeVisible();
    await expect(page.getByText('Habits')).toBeVisible();
    await expect(page.getByText('Memory')).toBeVisible();
    
    // Click through tabs to verify they work
    await page.getByText('Moments').click();
    await page.waitForTimeout(500);
    
    await page.getByText('Ideas').click();
    await page.waitForTimeout(500);
    
    await page.getByText('Habits').click();
    await page.waitForTimeout(500);
    
    await page.getByText('Summary').click();
    await page.waitForTimeout(500);
    
    // Should be back on Summary tab
    await expect(page.getByText('GAME STORY')).toBeVisible();
  });

  test('should show game result badge', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify game result is displayed - use exact match for just "Won" badge
    await expect(page.getByText('Won', { exact: true })).toBeVisible();
    await expect(page.getByText('76% accuracy')).toBeVisible();
  });

  test('should show time-based warning when won on time', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // This specific game was won on time while losing
    await expect(page.getByText(/Won on Time/)).toBeVisible();
    await expect(page.getByText(/You were losing when opponent/)).toBeVisible();
  });

  test('should display move list at bottom', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify move list is visible
    await expect(page.getByText('Move 0 / 201')).toBeVisible();
    
    // Verify first move is shown - use exact match and first()
    await expect(page.getByRole('button', { name: 'b3', exact: true })).toBeVisible();
  });

  test('should have playback controls', async ({ page }) => {
    await page.goto(`/lab/game/${ANALYZED_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Verify playback controls exist (navigation buttons)
    const playButton = page.locator('button').filter({ has: page.locator('svg') }).nth(2); // Play button
    await expect(playButton).toBeVisible();
  });
});
