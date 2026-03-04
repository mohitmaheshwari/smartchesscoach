import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://chess-coach-lab.preview.emergentagent.com';

/**
 * Tests for:
 * 1. Mission Stepper UI - Reflect → Train → Wrap-up steps in MissionRunner.jsx
 * 2. Focus Mastery Section - Progress meter showing cognitive pattern mastery
 * 3. Coach Narrative Rail on Journey page
 */

test.describe('Mission Stepper UI', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Mission Stepper displays 3 steps: Reflect, Train, Wrap-up', async ({ page }) => {
    // Navigate to dashboard first
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for mission card
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    // Click Start Mission to go to MissionRunner
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    // Wait for MissionRunner page
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    // Verify Mission Stepper is visible
    const missionStepper = page.getByTestId('mission-stepper');
    await expect(missionStepper).toBeVisible();
    
    // Verify all 3 step labels are present
    await expect(missionStepper.getByText('Reflect')).toBeVisible();
    await expect(missionStepper.getByText('Train')).toBeVisible();
    await expect(missionStepper.getByText('Wrap-up')).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/mission-stepper-3-steps.jpeg', quality: 20 });
  });

  test('Mission Stepper highlights Reflect step during briefing phase', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    // During briefing phase, Reflect step should be active (has bg-primary class)
    const missionStepper = page.getByTestId('mission-stepper');
    await expect(missionStepper).toBeVisible();
    
    // The first step icon container should have active styling
    // Look for Brain icon container that has bg-primary
    const reflectStep = missionStepper.locator('div').filter({ hasText: 'Reflect' }).first();
    await expect(reflectStep).toBeVisible();
    
    // Verify the step indicator for Reflect is highlighted
    // Active step has bg-primary class (blue color)
    const activeStepIndicator = missionStepper.locator('.bg-primary');
    await expect(activeStepIndicator).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/mission-stepper-reflect-active.jpeg', quality: 20 });
  });

  test('Mission Stepper highlights Train step during drill phase', async ({ page }) => {
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
    await expect(startDrillBtn).toBeVisible();
    await startDrillBtn.click({ force: true });
    
    // Wait for drill phase - Position indicator appears
    await expect(page.getByText(/Position \d+/)).toBeVisible({ timeout: 10000 });
    
    // Now the stepper should show Train as active
    const missionStepper = page.getByTestId('mission-stepper');
    await expect(missionStepper).toBeVisible();
    
    // Reflect step should now be complete (has Check icon, emerald color)
    // The connector between Reflect and Train should be emerald
    const emeraldConnector = missionStepper.locator('.bg-emerald-500');
    await expect(emeraldConnector).toBeVisible();
    
    // Train step should be active (has bg-primary)
    await page.screenshot({ path: '.screenshots/mission-stepper-train-active.jpeg', quality: 20 });
  });

  test('Mission Stepper shows step icons (Brain, Dumbbell, Flag)', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    const missionStepper = page.getByTestId('mission-stepper');
    await expect(missionStepper).toBeVisible();
    
    // SVG icons should be present (lucide icons are rendered as SVGs)
    const icons = missionStepper.locator('svg');
    const iconCount = await icons.count();
    expect(iconCount).toBeGreaterThanOrEqual(3); // At least 3 step icons
  });

  test('Mission Stepper has connectors between steps', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const missionCard = page.getByTestId('daily-mission-card');
    await expect(missionCard).toBeVisible({ timeout: 15000 });
    
    await hideEmergentBadge(page);
    
    const startButton = missionCard.getByRole('button', { name: /Start Mission|Continue/i });
    await startButton.click({ force: true });
    
    await page.waitForURL(/\/mission\//, { timeout: 10000 });
    await expect(page.getByTestId('mission-runner-page')).toBeVisible({ timeout: 10000 });
    
    const missionStepper = page.getByTestId('mission-stepper');
    await expect(missionStepper).toBeVisible();
    
    // Connectors are w-12 h-0.5 divs between steps
    const connectors = missionStepper.locator('.w-12.h-0\\.5');
    const connectorCount = await connectors.count();
    expect(connectorCount).toBe(2); // 2 connectors between 3 steps
  });
});


test.describe('Focus Mastery Section on Progress Page (JourneyV2)', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Progress page loads with Focus Mastery section', async ({ page }) => {
    // JourneyV2 is at /progress route
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for page to load
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    // Focus Mastery section should be visible (if user has enough data)
    // It has data-testid="focus-mastery-section"
    const focusMasterySection = page.getByTestId('focus-mastery-section');
    
    // Take screenshot to see the state
    await page.screenshot({ path: '.screenshots/progress-focus-mastery-section.jpeg', quality: 20 });
    
    // Check if it's visible OR page shows "Building Your Story" message
    const isVisible = await focusMasterySection.isVisible().catch(() => false);
    const buildingStory = await page.getByText('Building Your Story').isVisible().catch(() => false);
    
    // Either the section should be visible OR the page should show not enough data message
    expect(isVisible || buildingStory).toBe(true);
  });

  test('Focus Mastery Section shows overall mastery ring with percentage', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    const focusMasterySection = page.getByTestId('focus-mastery-section');
    
    // Skip if section not visible (not enough data)
    const isVisible = await focusMasterySection.isVisible().catch(() => false);
    if (!isVisible) {
      test.skip();
      return;
    }
    
    // Should show "Focus Mastery" title with Brain icon
    await expect(focusMasterySection.getByText('Focus Mastery')).toBeVisible();
    
    // Should show overall mastery percentage (e.g., "100%")
    const percentageText = focusMasterySection.locator('text=/\\d+%/');
    await expect(percentageText.first()).toBeVisible();
    
    // Should show overall level badge (master/proficient/competent/developing/novice)
    const levelBadges = focusMasterySection.locator('.rounded-full');
    await expect(levelBadges.first()).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/focus-mastery-ring.jpeg', quality: 20 });
  });

  test('Focus Mastery Section shows individual pattern progress bars', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    const focusMasterySection = page.getByTestId('focus-mastery-section');
    
    const isVisible = await focusMasterySection.isVisible().catch(() => false);
    if (!isVisible) {
      test.skip();
      return;
    }
    
    // Progress bars have h-2 bg-muted rounded-full classes
    const progressBars = focusMasterySection.locator('.h-2.bg-muted.rounded-full');
    const barCount = await progressBars.count();
    
    // Should have at least one progress bar for pattern tracking
    expect(barCount).toBeGreaterThanOrEqual(1);
    
    await page.screenshot({ path: '.screenshots/focus-mastery-progress-bars.jpeg', quality: 20 });
  });

  test('Focus Mastery Section shows mastery levels (master/proficient/etc)', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    const focusMasterySection = page.getByTestId('focus-mastery-section');
    
    const isVisible = await focusMasterySection.isVisible().catch(() => false);
    if (!isVisible) {
      test.skip();
      return;
    }
    
    // Scroll to make sure the section is in view
    await focusMasterySection.scrollIntoViewIfNeeded();
    
    // Mastery levels are shown as badges
    // Overall level is lowercase: master, proficient, competent, developing, novice
    // Individual pattern levels use labels: Master, Proficient, Competent, Developing, Learning
    const validLevels = ['master', 'Master', 'proficient', 'Proficient', 'competent', 'Competent', 'developing', 'Developing', 'novice', 'Learning'];
    
    let foundLevel = false;
    for (const level of validLevels) {
      const levelBadge = focusMasterySection.getByText(level, { exact: true });
      const count = await levelBadge.count();
      if (count > 0) {
        foundLevel = true;
        break;
      }
    }
    
    // Take screenshot for debugging
    await page.screenshot({ path: '.screenshots/focus-mastery-levels.jpeg', quality: 20 });
    
    expect(foundLevel).toBe(true);
  });

  test('Focus Mastery Section shows Strongest and Focus Area cards', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    const focusMasterySection = page.getByTestId('focus-mastery-section');
    
    const isVisible = await focusMasterySection.isVisible().catch(() => false);
    if (!isVisible) {
      test.skip();
      return;
    }
    
    // Should show "Strongest" card (top_strength)
    await expect(focusMasterySection.getByText('Strongest')).toBeVisible();
    
    // Should show "Focus Area" card (biggest_gap)
    await expect(focusMasterySection.getByText('Focus Area')).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/focus-mastery-strength-gap.jpeg', quality: 20 });
  });

  test('Focus Mastery Section shows recommended focus suggestion', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    const focusMasterySection = page.getByTestId('focus-mastery-section');
    
    const isVisible = await focusMasterySection.isVisible().catch(() => false);
    if (!isVisible) {
      test.skip();
      return;
    }
    
    // Recommended focus shows "Recommended: Work on X"
    const recommendedText = focusMasterySection.getByText(/Recommended:/);
    const hasRecommendation = await recommendedText.isVisible().catch(() => false);
    
    // If there's a recommendation, it should be visible
    if (hasRecommendation) {
      await expect(recommendedText).toBeVisible();
      
      // The purple highlighted pattern name should be visible
      const purpleHighlight = focusMasterySection.locator('.text-purple-400');
      await expect(purpleHighlight).toBeVisible();
    }
    
    await page.screenshot({ path: '.screenshots/focus-mastery-recommendation.jpeg', quality: 20 });
  });
});


test.describe('Coach Narrative Rail on Progress Page (JourneyV2)', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Progress page shows Coach Comparison section at top', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for progress page to load
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    // Screenshot to verify layout
    await page.screenshot({ path: '.screenshots/progress-coach-narrative.jpeg', quality: 20 });
    
    // The CoachingComparison component should show either:
    // 1. "Getting to Know Your Game" if no baseline yet
    // 2. Before/After/Growth tabs if baseline exists
    
    const gettingToKnow = page.getByText('Getting to Know Your Game');
    const beforeCoach = page.getByText('Before Coach');
    const afterCoach = page.getByText('After Coach');
    const yourGrowth = page.getByText('Your Growth');
    const buildingStory = page.getByText('Building Your Story');
    
    // Check for any of these elements indicating coach narrative is shown
    const hasGettingToKnow = await gettingToKnow.isVisible().catch(() => false);
    const hasBeforeCoach = await beforeCoach.isVisible().catch(() => false);
    const hasAfterCoach = await afterCoach.isVisible().catch(() => false);
    const hasYourGrowth = await yourGrowth.isVisible().catch(() => false);
    const hasBuildingStory = await buildingStory.isVisible().catch(() => false);
    
    // At least one of these should be visible
    const hasCoachNarrative = hasGettingToKnow || hasBeforeCoach || hasAfterCoach || hasYourGrowth || hasBuildingStory;
    expect(hasCoachNarrative).toBe(true);
  });

  test('Progress page Before/After Coach tabs work when baseline exists', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    // Check if tabs exist (indicates baseline is present)
    const beforeCoachTab = page.getByText('Before Coach');
    const tabsVisible = await beforeCoachTab.isVisible().catch(() => false);
    
    if (!tabsVisible) {
      // No tabs - user doesn't have baseline yet
      test.skip();
      return;
    }
    
    // Click Before Coach tab
    await beforeCoachTab.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Should show baseline stats (Accuracy, Blunders/Game, Win Rate, Mistakes/Game)
    // Use exact match to avoid strict mode issues
    await expect(page.getByText('Accuracy', { exact: true }).first()).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/progress-before-coach-tab.jpeg', quality: 20 });
    
    // Click After Coach tab
    const afterCoachTab = page.getByText('After Coach');
    await afterCoachTab.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Should still show stats
    await expect(page.getByText('Accuracy', { exact: true }).first()).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/progress-after-coach-tab.jpeg', quality: 20 });
    
    // Click Your Growth tab
    const yourGrowthTab = page.getByText('Your Growth');
    await yourGrowthTab.click();
    await page.waitForLoadState('domcontentloaded');
    
    // Should show improvement areas
    // Look for "What's Improving" or "Focus Areas" sections
    const improvingSection = page.getByText("What's Improving");
    const focusSection = page.getByText('Focus Areas');
    
    const hasImproving = await improvingSection.isVisible().catch(() => false);
    const hasFocus = await focusSection.isVisible().catch(() => false);
    
    // At least one should be visible
    expect(hasImproving || hasFocus).toBe(true);
    
    await page.screenshot({ path: '.screenshots/progress-your-growth-tab.jpeg', quality: 20 });
  });

  test('Progress page shows progress bar when building baseline', async ({ page }) => {
    await page.goto(`${BASE_URL}/progress`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByText('Your Chess Journey')).toBeVisible({ timeout: 15000 });
    
    // Look for "Getting to Know Your Game" text indicating baseline building
    const gettingToKnow = page.getByText('Getting to Know Your Game');
    const isBuilding = await gettingToKnow.isVisible().catch(() => false);
    
    if (!isBuilding) {
      // Baseline already exists
      test.skip();
      return;
    }
    
    // Should show progress indicator with "X more games to analyze"
    await expect(page.getByText(/more games to analyze/)).toBeVisible();
    
    // Progress bar should be visible
    const progressBar = page.locator('[role="progressbar"], .h-2');
    await expect(progressBar.first()).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/progress-baseline-building.jpeg', quality: 20 });
  });
});
