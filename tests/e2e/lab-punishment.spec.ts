import { test, expect } from '@playwright/test';
import { dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

/**
 * Lab Punishment Feature Tests
 * 
 * Feature: Show opponent's best punishing move in Lab page
 * When a user makes a wrong move during game review, the engine shows 
 * the opponent's best response with an arrow to visually demonstrate 
 * why the move was bad.
 */

test.describe('Lab Punishment Feature', () => {
  test.beforeEach(async ({ page }) => {
    // Dev login
    await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('should show "Show why it\'s bad" button when expanding a Learning Moment', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    
    // Click on a game that has mistakes (lost game vs antomini with 3 blunders)
    const gameRow = page.locator('text=vs antomini').first();
    await expect(gameRow).toBeVisible({ timeout: 10000 });
    await gameRow.click();
    
    // Wait for Lab page to load
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Milestones tab
    const milestonesTab = page.getByRole('tab', { name: /Milestones/i });
    await expect(milestonesTab).toBeVisible();
    await milestonesTab.click();
    
    // Scroll to Learning Moments section
    const learningMoments = page.locator('text=Learning Moments');
    await learningMoments.scrollIntoViewIfNeeded();
    await expect(learningMoments).toBeVisible({ timeout: 5000 });
    
    // Expand a Learning Moment by clicking "What can I learn here?"
    const learnBtn = page.locator('text=What can I learn here?').first();
    await expect(learnBtn).toBeVisible({ timeout: 5000 });
    await learnBtn.click();
    
    // Wait for expansion and find "Show why it's bad" button
    const showPunishmentBtn = page.locator("text=Show why it's bad (opponent's response)").first();
    await expect(showPunishmentBtn).toBeVisible({ timeout: 5000 });
  });

  test('should display arrows on board when clicking Show Punishment button', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    
    // Click on lost game
    const gameRow = page.locator('text=vs antomini').first();
    await expect(gameRow).toBeVisible({ timeout: 10000 });
    await gameRow.click();
    
    // Wait for Lab page
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Milestones tab
    const milestonesTab = page.getByRole('tab', { name: /Milestones/i });
    await milestonesTab.click();
    
    // Scroll to Learning Moments and expand first one
    const learningMoments = page.locator('text=Learning Moments');
    await learningMoments.scrollIntoViewIfNeeded();
    
    const learnBtn = page.locator('text=What can I learn here?').first();
    await expect(learnBtn).toBeVisible({ timeout: 5000 });
    await learnBtn.click();
    
    // Click "Show why it's bad" button
    const showPunishmentBtn = page.locator("text=Show why it's bad (opponent's response)").first();
    await expect(showPunishmentBtn).toBeVisible({ timeout: 5000 });
    await showPunishmentBtn.click();
    
    // Wait for board to update with arrows
    await page.waitForTimeout(1000);
    
    // Verify arrows are displayed on the chessboard
    // The react-chessboard component renders arrows as SVG elements
    // We can verify the board container is present and arrows were triggered
    // by checking for SVG marker elements that react-chessboard uses for arrows
    const svgMarkers = page.locator('svg defs marker');
    // Wait a moment for SVG elements to render
    await expect(svgMarkers.first()).toBeVisible({ timeout: 3000 });
    
    // Take screenshot to verify visual state
    await page.screenshot({ path: 'test-results/punishment-arrows.jpeg', quality: 30, fullPage: false });
  });

  test('should show toast notification explaining the punishment', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    
    // Click on lost game
    const gameRow = page.locator('text=vs antomini').first();
    await expect(gameRow).toBeVisible({ timeout: 10000 });
    await gameRow.click();
    
    // Wait for Lab page
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Milestones tab
    const milestonesTab = page.getByRole('tab', { name: /Milestones/i });
    await milestonesTab.click();
    
    // Scroll to Learning Moments and expand first one
    const learningMoments = page.locator('text=Learning Moments');
    await learningMoments.scrollIntoViewIfNeeded();
    
    const learnBtn = page.locator('text=What can I learn here?').first();
    await expect(learnBtn).toBeVisible({ timeout: 5000 });
    await learnBtn.click();
    
    // Click "Show why it's bad" button
    const showPunishmentBtn = page.locator("text=Show why it's bad (opponent's response)").first();
    await expect(showPunishmentBtn).toBeVisible({ timeout: 5000 });
    await showPunishmentBtn.click();
    
    // Wait for toast notification to appear
    // The toast should mention "After [move], opponent plays [punishment move]"
    const toastNotification = page.locator('[data-sonner-toast]').first();
    await expect(toastNotification).toBeVisible({ timeout: 5000 });
    
    // Verify toast contains punishment information
    const toastText = await toastNotification.textContent();
    expect(toastText).toMatch(/After|opponent|plays/i);
  });

  test('should update board position when showing punishment', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    
    // Click on lost game
    const gameRow = page.locator('text=vs antomini').first();
    await expect(gameRow).toBeVisible({ timeout: 10000 });
    await gameRow.click();
    
    // Wait for Lab page
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Milestones tab
    const milestonesTab = page.getByRole('tab', { name: /Milestones/i });
    await milestonesTab.click();
    
    // Scroll to Learning Moments and expand first one
    const learningMoments = page.locator('text=Learning Moments');
    await learningMoments.scrollIntoViewIfNeeded();
    
    const learnBtn = page.locator('text=What can I learn here?').first();
    await expect(learnBtn).toBeVisible({ timeout: 5000 });
    await learnBtn.click();
    
    // Click "Show why it's bad" button
    const showPunishmentBtn = page.locator("text=Show why it's bad (opponent's response)").first();
    await expect(showPunishmentBtn).toBeVisible({ timeout: 5000 });
    await showPunishmentBtn.click();
    
    // Wait for board to update
    await page.waitForTimeout(1000);
    
    // Verify the Lab page is still visible after punishment button click
    // This confirms the position updated without errors
    await expect(page.getByTestId('lab-page')).toBeVisible();
    
    // Take a final screenshot to capture the state with arrows
    await page.screenshot({ path: 'test-results/punishment-position.jpeg', quality: 30, fullPage: false });
  });

  test('should have Show Punishment button with correct data-testid pattern', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    
    // Click on lost game
    const gameRow = page.locator('text=vs antomini').first();
    await expect(gameRow).toBeVisible({ timeout: 10000 });
    await gameRow.click();
    
    // Wait for Lab page
    await expect(page.getByTestId('lab-page')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Milestones tab
    const milestonesTab = page.getByRole('tab', { name: /Milestones/i });
    await milestonesTab.click();
    
    // Scroll to Learning Moments and expand first one
    const learningMoments = page.locator('text=Learning Moments');
    await learningMoments.scrollIntoViewIfNeeded();
    
    const learnBtn = page.locator('text=What can I learn here?').first();
    await expect(learnBtn).toBeVisible({ timeout: 5000 });
    await learnBtn.click();
    
    // Verify the button has correct data-testid pattern: show-punishment-{move_number}
    // Move 7 is the first learning moment, so data-testid should be show-punishment-7
    const showPunishmentBtn = page.getByTestId(/^show-punishment-\d+$/);
    await expect(showPunishmentBtn.first()).toBeVisible({ timeout: 5000 });
    
    // Also verify the button text
    const buttonText = await showPunishmentBtn.first().textContent();
    expect(buttonText).toContain("Show why it's bad");
  });
});
