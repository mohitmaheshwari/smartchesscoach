import { test, expect } from '@playwright/test';

/**
 * Critical Moments Feature Tests
 * 
 * Tests for the interactive Critical Moments feature in the game review page.
 * Uses game ID: ae58fb15-ca1d-43e7-a46f-12dce04959bb which has 5 critical moments.
 */

const GAME_ID = 'ae58fb15-ca1d-43e7-a46f-12dce04959bb';
const BASE_URL = 'https://deep-memory-chess.preview.emergentagent.com';

test.describe('Critical Moments Feature', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to the game review page
    await page.goto(`/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
    // Wait for the page to load
    await expect(page.getByText('Game Review')).toBeVisible({ timeout: 10000 });
  });

  test('should display Critical Moments tab with moments count', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Verify Critical Moments header is visible
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Verify moment count badge shows "5 to review"
    await expect(page.getByText('5 to review')).toBeVisible();
    
    // Verify navigation counter shows "1 / 5"
    await expect(page.getByText('1 / 5')).toBeVisible();
  });

  test('should display position hint before user attempt', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for the critical moments section to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Verify the Socratic prompt is shown
    await expect(page.getByText('Pause here.')).toBeVisible();
    await expect(page.getByText('Look at the board. What would you play?')).toBeVisible();
    
    // Verify position hint is displayed (yellow/amber box with hint)
    // The hint should mention the undefended Queen
    const hintBox = page.locator('text=Opponent');
    await expect(hintBox.first()).toBeVisible();
  });

  test('should have Try Move on Board and Reveal Best Move buttons', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Verify "Try Move on Board" button exists
    await expect(page.getByRole('button', { name: /Try Move on Board/i })).toBeVisible();
    
    // Verify "Reveal Best Move" button exists
    await expect(page.getByRole('button', { name: /Reveal Best Move/i })).toBeVisible();
  });

  test('should activate interactive mode when clicking Try Move on Board', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Click "Try Move on Board" button
    await page.click('button:has-text("Try Move on Board")');
    
    // Verify interactive mode indicator appears
    await expect(page.getByText('Your turn - find the best move!')).toBeVisible({ timeout: 5000 });
  });

  test('should reveal best move with arrows and explanation', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Click "Reveal Best Move" button
    await page.click('button:has-text("Reveal Best Move")');
    
    // Wait for the reveal animation
    await page.waitForTimeout(1000);
    
    // Verify "BEST MOVE" section is visible
    await expect(page.getByText('BEST MOVE')).toBeVisible();
    
    // Verify the best move Qf4 is shown
    await expect(page.getByText('Qf4').first()).toBeVisible();
    
    // Verify "Why it works" explanation is shown
    await expect(page.getByText('Why it works')).toBeVisible();
    await expect(page.getByText(/Queen becomes more active/i)).toBeVisible();
    
    // Verify "YOUR MOVE" section is visible
    await expect(page.getByText('YOUR MOVE')).toBeVisible();
    
    // Verify the user's move Qe5 is shown (use label to scope to Moments tab panel)
    await expect(page.getByLabel('Moments').getByText('Qe5')).toBeVisible();
  });

  test('should show Play Line button after revealing', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Click "Reveal Best Move"
    await page.click('button:has-text("Reveal Best Move")');
    
    // Wait for reveal
    await page.waitForTimeout(1000);
    
    // Verify "Play Line" button appears
    await expect(page.getByRole('button', { name: /Play Line/i })).toBeVisible();
  });

  test('should show Yes I get it and Still confused feedback buttons after reveal', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Click "Reveal Best Move"
    await page.click('button:has-text("Reveal Best Move")');
    
    // Wait for reveal animation
    await page.waitForTimeout(1000);
    
    // Verify feedback buttons
    await expect(page.getByRole('button', { name: /Yes, I get it/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Still confused/i })).toBeVisible();
  });

  test('should navigate to next moment with prev/next buttons', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('1 / 5')).toBeVisible();
    
    // Click the next button (arrow right)
    await page.getByTestId('moment-next-btn').click();
    
    // Verify we're now on moment 2
    await expect(page.getByText('2 / 5')).toBeVisible();
    
    // Click back (prev button)
    await page.getByTestId('moment-prev-btn').click();
    
    // Verify we're back on moment 1
    await expect(page.getByText('1 / 5')).toBeVisible();
  });

  test('should disable prev button on first moment and next on last', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('1 / 5')).toBeVisible();
    
    // Verify prev button is disabled on first moment
    const prevBtn = page.getByTestId('moment-prev-btn');
    await expect(prevBtn).toBeDisabled();
    
    // Navigate to the last moment (click next 4 times)
    const nextBtn = page.getByTestId('moment-next-btn');
    await nextBtn.click();
    await page.waitForTimeout(300);
    await nextBtn.click();
    await page.waitForTimeout(300);
    await nextBtn.click();
    await page.waitForTimeout(300);
    await nextBtn.click();
    
    // Verify we're on moment 5
    await expect(page.getByText('5 / 5')).toBeVisible();
    
    // Verify next button is disabled on last moment
    await expect(nextBtn).toBeDisabled();
  });

  test('should advance to next moment when clicking Yes I get it', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('1 / 5')).toBeVisible();
    
    // Reveal the best move
    await page.click('button:has-text("Reveal Best Move")');
    await page.waitForTimeout(1000);
    
    // Click "Yes, I get it"
    await page.click('button:has-text("Yes, I get it")');
    
    // Verify we advanced to moment 2
    await expect(page.getByText('2 / 5')).toBeVisible({ timeout: 5000 });
  });

  test('should show Next Moment button after revealing', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Reveal the best move
    await page.click('button:has-text("Reveal Best Move")');
    await page.waitForTimeout(1000);
    
    // Verify "Next Moment" button is visible (at bottom of panel)
    await expect(page.getByRole('button', { name: /Next Moment/i })).toBeVisible();
  });

  test('should show move number badge for current moment', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // First moment should show Move 34 badge (based on API data)
    await expect(page.getByText('Move 34')).toBeVisible();
    
    // Click next
    await page.getByTestId('moment-next-btn').click();
    await page.waitForTimeout(500);
    
    // Second moment should show Move 33 badge
    await expect(page.getByText('Move 33')).toBeVisible();
  });

  test('should show severity label for each moment', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // First moment has cp_loss of 1282, which should be "Serious mistake"
    await expect(page.getByText('Serious mistake')).toBeVisible();
  });

  test('should have See on board button', async ({ page }) => {
    // Click on the Moments tab
    await page.click('button:has-text("Moments")');
    
    // Wait for moments to load
    await expect(page.getByText('Critical Moments')).toBeVisible();
    
    // Verify "See on board" button exists
    await expect(page.getByRole('button', { name: /See on board/i })).toBeVisible();
  });

});
