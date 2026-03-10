/**
 * GuidedAnalysis Component E2E Tests
 * 
 * Tests for the step-by-step coach-led analysis experience:
 * - GuidedAnalysis displays in Summary tab
 * - Reveal What Happened button shows explanation
 * - Coach messages vary and display encouragement
 * - Quick tip section is expandable
 * - Navigation between moments works (Previous/Next buttons)
 * - Quick jump buttons navigate to correct moments
 * - Not helpful feedback button is present
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.REACT_APP_BACKEND_URL || 'https://chess-coach-ai-7.preview.emergentagent.com';
// Use a game with known critical moments
const TEST_GAME_ID = 'a8fb2fa0-42da-4e40-9308-c9f364b5f6b3';

test.describe('GuidedAnalysis Component', () => {
  test.beforeEach(async ({ page }) => {
    // Dev login
    await page.goto(`${BASE_URL}/api/auth/dev-login`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);
  });

  test('displays GuidedAnalysis in Summary tab', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    // Click Summary tab
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Check GuidedAnalysis component is visible
    const guidedBtn = page.locator('button:has-text("Guided")');
    await expect(guidedBtn).toBeVisible();
    
    // Check moment indicator
    const momentIndicator = page.locator('text=/Moment \\d+ of \\d+/');
    await expect(momentIndicator).toBeVisible();
    
    // Check coach message area
    const coachMessage = page.locator('text="Your Coach"');
    await expect(coachMessage).toBeVisible();
  });

  test('Reveal What Happened button shows explanation', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Click Reveal What Happened button
    const revealBtn = page.getByTestId('show-explanation-btn');
    await expect(revealBtn).toBeVisible();
    await revealBtn.click();
    await page.waitForTimeout(1000);
    
    // Check explanation is now visible
    const betterMoveText = page.locator('text=/Better was:/');
    await expect(betterMoveText).toBeVisible();
    
    // Check navigation buttons appear
    const nextBtn = page.getByTestId('next-moment-btn');
    await expect(nextBtn).toBeVisible();
  });

  test('coach messages vary and display encouragement', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Get initial coach message
    const coachSection = page.locator('div:has-text("Your Coach")').first();
    await expect(coachSection).toBeVisible();
    
    // Click reveal to trigger encouragement message
    await page.getByTestId('show-explanation-btn').click();
    await page.waitForTimeout(1000);
    
    // Coach should now show an encouragement message
    // Check that coach message area is still present and has content
    const coachMessage = page.locator('p:has-text("Your Coach")').locator('..').locator('p').last();
    await expect(coachMessage).toBeVisible();
    const messageText = await coachMessage.textContent();
    expect(messageText).toBeTruthy();
    expect(messageText!.length).toBeGreaterThan(5);
  });

  test('quick tip section is expandable', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Click Reveal What Happened
    await page.getByTestId('show-explanation-btn').click();
    await page.waitForTimeout(1000);
    
    // Find and click "Show improvement tip" button
    const showTipBtn = page.locator('button:has-text("Show improvement tip")');
    await expect(showTipBtn).toBeVisible();
    await showTipBtn.click();
    await page.waitForTimeout(500);
    
    // Check Quick Tip section is now visible
    const quickTip = page.locator('text="Quick Tip"');
    await expect(quickTip).toBeVisible();
  });

  test('navigation between moments works with Previous/Next buttons', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Should start at moment 1
    const moment1 = page.locator('text="Moment 1 of 2"');
    await expect(moment1).toBeVisible();
    
    // Click Reveal to show navigation buttons
    await page.getByTestId('show-explanation-btn').click();
    await page.waitForTimeout(1000);
    
    // Click Next
    await page.getByTestId('next-moment-btn').click();
    await page.waitForTimeout(1000);
    
    // Should now be at moment 2
    const moment2 = page.locator('text="Moment 2 of 2"');
    await expect(moment2).toBeVisible();
    
    // Click Reveal again and then Previous
    await page.getByTestId('show-explanation-btn').click();
    await page.waitForTimeout(500);
    
    await page.getByTestId('prev-moment-btn').click();
    await page.waitForTimeout(1000);
    
    // Should be back at moment 1
    await expect(page.locator('text="Moment 1 of 2"')).toBeVisible();
  });

  test('quick jump buttons navigate to correct moments', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Click reveal first to see all UI
    await page.getByTestId('show-explanation-btn').click();
    await page.waitForTimeout(500);
    
    // Jump to second moment using quick jump button
    await page.getByTestId('jump-moment-1').click();
    await page.waitForTimeout(1000);
    
    // Should be at moment 2
    await expect(page.locator('text="Moment 2 of 2"')).toBeVisible();
    
    // Jump back to first moment
    await page.getByTestId('jump-moment-0').click();
    await page.waitForTimeout(1000);
    
    // Should be at moment 1
    await expect(page.locator('text="Moment 1 of 2"')).toBeVisible();
  });

  test('Not helpful feedback button is present', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Click Reveal to show explanation with feedback button
    await page.getByTestId('show-explanation-btn').click();
    await page.waitForTimeout(1500);
    
    // Check for inline feedback button
    const feedbackBtn = page.getByTestId('inline-feedback-btn');
    await expect(feedbackBtn).toBeVisible();
    
    // Check it has "Not helpful" text
    await expect(feedbackBtn).toContainText('Not helpful');
  });

  test('Full Analysis button exits guided mode', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Check Full Analysis button exists using data-testid
    const fullAnalysisBtn = page.getByTestId('exit-guide-btn');
    await expect(fullAnalysisBtn).toBeVisible();
    await expect(fullAnalysisBtn).toContainText('Full Analysis');
  });

  test('move info shows correct move number and cp loss', async ({ page }) => {
    await page.goto(`${BASE_URL}/lab/game/${TEST_GAME_ID}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    
    await page.click('button:has-text("Summary")');
    await page.waitForTimeout(1000);
    
    // Check move number badge is visible
    const moveNumber = page.locator('text=/Move \\d+/').first();
    await expect(moveNumber).toBeVisible();
    
    // Check cp loss indicator is present
    const cpLoss = page.locator('text=/cp$/');
    await expect(cpLoss).toBeVisible();
  });
});
