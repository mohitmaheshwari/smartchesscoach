import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://move-intelligence.preview.emergentagent.com';

test.describe('Coach Home - UX Overhaul', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    
    // Set up toast dismissal
    await dismissToasts(page);
  });

  test('Coach Home loads at /home route', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Verify coach home container is visible
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    await page.screenshot({ path: '.screenshots/coach-home-page.jpeg', quality: 20 });
  });

  test('Navigation shows 4 items: Home, Analyze, Train, Progress', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for 4 navigation items
    await expect(page.getByTestId('nav-home')).toBeVisible();
    await expect(page.getByTestId('nav-analyze')).toBeVisible();
    await expect(page.getByTestId('nav-train')).toBeVisible();
    await expect(page.getByTestId('nav-progress')).toBeVisible();
    
    // Verify text content
    await expect(page.getByTestId('nav-home')).toHaveText(/Home/);
    await expect(page.getByTestId('nav-analyze')).toHaveText(/Analyze/);
    await expect(page.getByTestId('nav-train')).toHaveText(/Train/);
    await expect(page.getByTestId('nav-progress')).toHaveText(/Progress/);
  });

  test('Today\'s Mission card displays when user has mission', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Either active mission card or no-mission card should be visible
    const activeMissionCard = page.getByTestId('active-mission-card');
    const noMissionCard = page.getByTestId('no-mission-card');
    const postLossHero = page.getByTestId('post-loss-hero');
    
    // One of these should be visible
    const missionVisible = await activeMissionCard.isVisible().catch(() => false);
    const noMissionVisible = await noMissionCard.isVisible().catch(() => false);
    const postLossVisible = await postLossHero.isVisible().catch(() => false);
    
    expect(missionVisible || noMissionVisible || postLossVisible).toBe(true);
  });

  test('Mission card shows focus label, duration, and protocol steps', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const activeMissionCard = page.getByTestId('active-mission-card');
    
    // Check if mission exists
    const hasMission = await activeMissionCard.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasMission) {
      // Focus label should be visible as h3
      await expect(activeMissionCard.locator('h3')).toBeVisible();
      
      // Duration info (e.g., "7 min")
      await expect(activeMissionCard.getByText(/\d+ min/)).toBeVisible();
      
      // Positions info (e.g., "5 positions")
      await expect(activeMissionCard.getByText(/\d+ position/)).toBeVisible();
      
      // Protocol steps (Before each move section)
      await expect(activeMissionCard.getByText(/Before each move/i)).toBeVisible();
    } else {
      // If no mission, skip but note in console
      console.log('No active mission - skipping mission card content test');
    }
  });

  test('Start Mission button is visible and clickable', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const activeMissionCard = page.getByTestId('active-mission-card');
    
    // Check if mission exists
    const hasMission = await activeMissionCard.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasMission) {
      // Start Mission or Continue button should be visible
      const startBtn = page.getByTestId('start-mission-btn');
      await expect(startBtn).toBeVisible();
      await expect(startBtn).toBeEnabled();
      
      // Button should have appropriate text
      await expect(startBtn).toHaveText(/Start Mission|Continue/);
    }
  });

  test('Start Mission navigates to mission runner', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    const startBtn = page.getByTestId('start-mission-btn');
    const hasMission = await startBtn.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasMission) {
      await startBtn.click({ force: true });
      
      // Wait for navigation to mission page
      await page.waitForURL(/\/mission\//, { timeout: 10000 });
      await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    }
  });

  test('Active Advice card displays when user has data', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Active advice card should be visible when user has data
    const activeAdviceCard = page.getByTestId('active-advice-card');
    const hasAdvice = await activeAdviceCard.isVisible({ timeout: 10000 }).catch(() => false);
    
    if (hasAdvice) {
      // Should show "YOUR FOCUS" text
      await expect(activeAdviceCard.getByText(/YOUR FOCUS/i)).toBeVisible();
      // Should have primary advice text
      await expect(activeAdviceCard.locator('p').first()).toBeVisible();
    }
  });

  test('Quick action buttons are visible and functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Import Games button
    const importBtn = page.getByTestId('quick-import');
    await expect(importBtn).toBeVisible();
    await expect(importBtn).toHaveText(/Import Games/);
    
    // View Journey button (renamed from View Progress)
    const journeyBtn = page.getByTestId('quick-progress');
    await expect(journeyBtn).toBeVisible();
    await expect(journeyBtn).toHaveText(/View Journey/);
  });

  test('Import Games quick action navigates to import page', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    const importBtn = page.getByTestId('quick-import');
    await importBtn.click({ force: true });
    
    // Should navigate to import page
    await page.waitForURL(/\/import/, { timeout: 10000 });
  });

  test('View Journey quick action navigates to progress page', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    const journeyBtn = page.getByTestId('quick-progress');
    await journeyBtn.click({ force: true });
    
    // Should navigate to progress page
    await page.waitForURL(/\/progress/, { timeout: 10000 });
  });

  test('Recommended Drill card displays when user has data', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const recommendedDrillCard = page.getByTestId('recommended-drill-card');
    
    // Recommended drill might not be visible if user has no data
    const hasDrill = await recommendedDrillCard.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasDrill) {
      // Should show "Recommended Drill" text
      await expect(recommendedDrillCard.getByText(/Recommended Drill/i)).toBeVisible();
      
      // Should have Start Training button
      const startDrillBtn = page.getByTestId('start-drill-btn');
      await expect(startDrillBtn).toBeVisible();
      await expect(startDrillBtn).toHaveText(/Start Training/);
    }
  });

  test('Greeting shows correct time-of-day message', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for greeting text (Good morning/afternoon/evening)
    const greeting = page.locator('p').filter({ hasText: /Good (morning|afternoon|evening)/ });
    await expect(greeting).toBeVisible();
  });

  test('Development Phase Banner displays when user has data', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Development phase banner should be visible when user has analyzed games
    const phaseBanner = page.getByTestId('development-phase-banner');
    const hasBanner = await phaseBanner.isVisible({ timeout: 10000 }).catch(() => false);
    
    if (hasBanner) {
      // Should show "Your Focus Stage" text
      await expect(phaseBanner.getByText(/Your Focus Stage/i)).toBeVisible();
      // Should show a phase name (one of the valid phases)
      const phaseText = await phaseBanner.locator('p.font-semibold').textContent();
      expect(phaseText).toBeTruthy();
    }
  });

  test('Color system applies Primary color for accent', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Primary buttons should have primary color
    const startBtn = page.getByTestId('start-mission-btn');
    const hasMission = await startBtn.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasMission) {
      // Check that button has a colored background (not transparent/white)
      const bgColor = await startBtn.evaluate(el => getComputedStyle(el).backgroundColor);
      // Should have some color (not transparent or white)
      expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
      expect(bgColor).not.toBe('rgb(255, 255, 255)');
    }
  });
});

test.describe('Coach Home - Navigation Integration', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('Home nav item is active on /home route', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const homeNav = page.getByTestId('nav-home');
    await expect(homeNav).toBeVisible();
    
    // Should have active state (bg-muted class)
    await expect(homeNav).toHaveClass(/bg-muted/);
  });

  test('Navigation items navigate to correct routes', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    // Test Analyze navigation
    await page.getByTestId('nav-analyze').click({ force: true });
    await page.waitForURL(/\/lab/, { timeout: 10000 });
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for nav to be visible before Train navigation
    await expect(page.getByTestId('nav-train')).toBeVisible({ timeout: 10000 });
    
    // Test Train navigation
    await page.getByTestId('nav-train').click({ force: true });
    await page.waitForURL(/\/training/, { timeout: 10000 });
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for nav to be visible before Progress navigation
    await expect(page.getByTestId('nav-progress')).toBeVisible({ timeout: 10000 });
    
    // Test Progress navigation
    await page.getByTestId('nav-progress').click({ force: true });
    await page.waitForURL(/\/progress/, { timeout: 10000 });
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for progress page to fully load before clicking Home
    await expect(page.getByTestId('nav-home')).toBeVisible({ timeout: 10000 });
    
    // Test Home navigation (back)
    await page.getByTestId('nav-home').click({ force: true });
    await page.waitForURL(/\/home/, { timeout: 10000 });
  });
});
