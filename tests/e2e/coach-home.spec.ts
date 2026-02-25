import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://loss-recovery.preview.emergentagent.com';

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
    
    // Either mission hero or no-mission card should be visible
    const missionHero = page.getByTestId('mission-hero');
    const noMissionCard = page.getByTestId('no-mission-card');
    const postLossHero = page.getByTestId('post-loss-hero');
    
    // One of these should be visible
    const heroVisible = await missionHero.isVisible().catch(() => false);
    const noMissionVisible = await noMissionCard.isVisible().catch(() => false);
    const postLossVisible = await postLossHero.isVisible().catch(() => false);
    
    expect(heroVisible || noMissionVisible || postLossVisible).toBe(true);
  });

  test('Mission card shows focus label, duration, and protocol steps', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionHero = page.getByTestId('mission-hero');
    
    // Check if mission exists
    const hasMission = await missionHero.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasMission) {
      // Focus label should be visible as h1
      await expect(missionHero.locator('h1')).toBeVisible();
      
      // Duration info (e.g., "7 min")
      await expect(missionHero.getByText(/\d+ min/)).toBeVisible();
      
      // Positions info (e.g., "5 positions")
      await expect(missionHero.getByText(/\d+ position/)).toBeVisible();
      
      // Protocol steps (Before each move section)
      await expect(missionHero.getByText(/Before each move/i)).toBeVisible();
    } else {
      // If no mission, skip but note in console
      console.log('No active mission - skipping mission card content test');
    }
  });

  test('Start Mission button is visible and clickable', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionHero = page.getByTestId('mission-hero');
    
    // Check if mission exists
    const hasMission = await missionHero.isVisible({ timeout: 5000 }).catch(() => false);
    
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

  test('Weekly Proof card displays below mission', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Weekly proof card should be visible
    const weeklyProof = page.getByTestId('weekly-proof');
    await expect(weeklyProof).toBeVisible({ timeout: 10000 });
    
    // Should show "This week" text
    await expect(weeklyProof.getByText(/This week/)).toBeVisible();
  });

  test('Quick action buttons are visible and functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Import Games button
    const importBtn = page.getByTestId('quick-import');
    await expect(importBtn).toBeVisible();
    await expect(importBtn).toHaveText(/Import Games/);
    
    // View Progress button
    const progressBtn = page.getByTestId('quick-progress');
    await expect(progressBtn).toBeVisible();
    await expect(progressBtn).toHaveText(/View Progress/);
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

  test('View Progress quick action navigates to progress page', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    const progressBtn = page.getByTestId('quick-progress');
    await progressBtn.click({ force: true });
    
    // Should navigate to progress page
    await page.waitForURL(/\/progress/, { timeout: 10000 });
  });

  test('Recent Games section is collapsible', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const recentGames = page.getByTestId('recent-games');
    
    // Recent games might not be visible if user has no games
    const hasRecentGames = await recentGames.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasRecentGames) {
      // Should show header with count
      await expect(recentGames.getByText(/Recent Games/)).toBeVisible();
      
      // Click to expand
      await recentGames.locator('button').first().click();
      
      // After expanding, should show game list
      await expect(recentGames.locator('motion.div')).toBeVisible({ timeout: 3000 });
      
      // Click again to collapse
      await recentGames.locator('button').first().click();
    }
  });

  test('Greeting shows correct time-of-day message', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for greeting text (Good morning/afternoon/evening)
    const greeting = page.locator('p').filter({ hasText: /Good (morning|afternoon|evening)/ });
    await expect(greeting).toBeVisible();
  });

  test('Color system applies Electric Blue for primary accent', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Primary buttons should have blue color
    const startBtn = page.getByTestId('start-mission-btn');
    const hasMission = await startBtn.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasMission) {
      // Check that button has blue-ish background
      // We use regex because computed colors vary slightly
      const bgColor = await startBtn.evaluate(el => getComputedStyle(el).backgroundColor);
      // Electric Blue #3B82F6 is approximately rgb(59, 130, 246)
      expect(bgColor).toMatch(/rgb\(5[0-9], 1[23][0-9], 2[45][0-9]\)/);
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
