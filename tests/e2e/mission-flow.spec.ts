import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://thinking-sim.preview.emergentagent.com';

test.describe('Mission System - Dashboard and Mission Flow', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    
    // Set up toast dismissal
    await dismissToasts(page);
  });

  test('Dashboard displays DailyMissionCard when user has games', async ({ page }) => {
    // Navigate to dashboard
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for dashboard to load
    await expect(page.getByTestId('dashboard-page')).toBeVisible({ timeout: 15000 });
    
    // DailyMissionCard should be present
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 10000 });
    
    // Take screenshot for verification
    await page.screenshot({ path: '.screenshots/dashboard-with-mission-card.jpeg', quality: 20 });
  });

  test('DailyMissionCard shows focus, duration, and protocol steps', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for mission card
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    // Check for "Today's Mission" text
    await expect(missionCard.getByText("Today's Mission")).toBeVisible();
    
    // Check for duration badge (e.g., "7 min")
    await expect(missionCard.getByText(/\d+ min/)).toBeVisible();
    
    // Check for Focus label (contains "Focus:")
    await expect(missionCard.getByText(/Focus:/)).toBeVisible();
    
    // Check for protocol steps (bullet points)
    const protocolSteps = missionCard.locator('.w-1.h-1.rounded-full');
    const stepCount = await protocolSteps.count();
    expect(stepCount).toBeGreaterThan(0);
    
    // Check for goal section
    await expect(missionCard.getByText(/Goal:/)).toBeVisible();
    await expect(missionCard.getByText(/Pass:/)).toBeVisible();
  });

  test('Start Mission button navigates to MissionRunner page', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for mission card
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    // Hide emergent badge if present
    await hideEmergentBadge(page);
    
    // Click Start Mission or Continue button
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await expect(startButton).toBeVisible();
    await startButton.click({ force: true });
    
    // Wait for navigation to mission page
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    
    // Verify we're on the MissionRunner page
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    await page.screenshot({ path: '.screenshots/mission-runner-page.jpeg', quality: 20 });
  });

  test('MissionRunner shows briefing phase with protocol steps', async ({ page }) => {
    // Navigate directly to mission page
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    // Wait for mission runner
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    const missionPage = page.getByTestId('mission-runner-page');
    await expect(missionPage).toBeVisible({ timeout: 10000 });
    
    // Check for briefing content
    // Focus label should be visible
    await expect(page.locator('h1')).toBeVisible();
    
    // Protocol steps should be present ("Before Each Move" section)
    await expect(page.getByText('Before Each Move')).toBeVisible();
    
    // Start Mission button in briefing should be visible
    const startDrillBtn = page.getByTestId('start-drill-btn');
    await expect(startDrillBtn).toBeVisible();
    
    // Pass threshold info should be visible
    await expect(page.getByText(/Pass by getting/)).toBeVisible();
  });

  test('MissionRunner Start Mission transitions to drill phase', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    // Click Start Mission button to enter drill phase
    const startDrillBtn = page.getByTestId('start-drill-btn');
    await startDrillBtn.click({ force: true });
    
    // Wait for drill phase UI
    // Position counter should appear (e.g., "1 / 5")
    await expect(page.getByText(/\d+ \/ \d+/)).toBeVisible({ timeout: 10000 });
    
    // Timer should be visible (format 0:05 or similar)
    await expect(page.locator('text=/\\d+:\\d+/')).toBeVisible();
    
    // Progress bar should be visible
    await expect(page.locator('.h-1\\.5.bg-muted.rounded-full')).toBeVisible();
    
    // "Position X" header should be visible
    await expect(page.getByText(/Position \d+/)).toBeVisible();
    
    // Chess board should be visible
    await expect(page.locator('.cg-wrap, .cg-board')).toBeVisible();
    
    // "Your turn - Find the best move" prompt should be visible
    await expect(page.getByText(/Your turn|Find the best move/i)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/mission-drill-phase.jpeg', quality: 20 });
  });

  test('Exit button returns to home from MissionRunner', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    // Click Exit button
    const exitButton = page.getByRole('button', { name: /Exit/i });
    await expect(exitButton).toBeVisible();
    await exitButton.click();
    
    // Should navigate back to /home (not /dashboard)
    await page.waitForURL(/\/home/, { timeout: 10000 });
  });

  test('Drill phase shows score tracking after using Show Answer', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    // Start drill
    const startDrillBtn = page.getByTestId('start-drill-btn');
    await startDrillBtn.click({ force: true });
    
    // Wait for drill phase - "Position X" header
    await expect(page.getByText(/Position \d+/)).toBeVisible({ timeout: 10000 });
    
    // Drill phase uses board interaction - check for score display at bottom
    await expect(page.getByText('Correct')).toBeVisible();
    await expect(page.getByText('Missed')).toBeVisible();
    
    // Initial score should show 0 for correct
    const correctScore = page.locator('.text-emerald-500.font-bold.text-xl').first();
    await expect(correctScore).toHaveText('0');
    
    // Click "Show Answer" button to see the best move
    const showAnswerBtn = page.locator('button').filter({ hasText: /Show Answer/i });
    await showAnswerBtn.click();
    
    // Feedback should appear showing the best move
    await expect(page.getByText(/Best move:/)).toBeVisible({ timeout: 5000 });
    
    // "Next Position" button should appear
    const nextBtn = page.getByTestId('next-position-btn');
    await expect(nextBtn).toBeVisible();
  });

  test('Dashboard displays loading state, then mission card', async ({ page }) => {
    // Don't wait for networkidle to catch loading state
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Check for dashboard page
    await expect(page.getByTestId('dashboard-page')).toBeVisible({ timeout: 15000 });
    
    // Mission card should eventually appear
    await expect(page.getByTestId('daily-mission-card')).toBeVisible({ timeout: 15000 });
  });
});
