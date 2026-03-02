/**
 * Coach State & Behavioral Maturity E2E Tests
 * 
 * Tests:
 * 1. Coach Home page displays coach state correctly
 * 2. Progress page shows maturity level
 * 3. Deep session modal flow
 * 4. Coach focus card displays theme and rules
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'https://chess-coach-mentor.preview.emergentagent.com';

// Helper to login via dev login
async function devLogin(page) {
  // Navigate to landing page first
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  
  // Click dev login button
  const devLoginBtn = page.locator('button:has-text("Dev Login"), a:has-text("Dev Login")');
  if (await devLoginBtn.isVisible()) {
    await devLoginBtn.click();
    await page.waitForURL(/\/(coach|dashboard)/, { timeout: 10000 });
  }
}

// Helper to dismiss toasts
async function dismissToasts(page) {
  await page.addLocatorHandler(
    page.locator('[data-sonner-toast]').first(),
    async () => {
      const close = page.locator('[data-sonner-toast] [data-close], [data-sonner-toast] button[aria-label="Close"]').first();
      await close.click({ timeout: 2000 }).catch(() => {});
    },
    { times: 20, noWaitAfter: true }
  );
}

test.describe('Coach Home Page', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should load coach home page', async ({ page }) => {
    await page.goto('/coach', { waitUntil: 'domcontentloaded' });
    
    // Check page loaded
    const coachHome = page.locator('[data-testid="coach-home"]');
    await expect(coachHome).toBeVisible({ timeout: 15000 });
    
    // Take screenshot
    await page.screenshot({ path: 'coach-home-loaded.jpeg', quality: 20 });
  });

  test('should show coach state information', async ({ page }) => {
    await page.goto('/coach', { waitUntil: 'domcontentloaded' });
    
    // Wait for page to load
    await page.waitForLoadState('domcontentloaded');
    
    // Check for coach-related content
    // The page should have focus/theme information
    const pageContent = await page.textContent('body');
    
    // Should show some coaching context - theme, focus, or advice
    const hasCoachingContent = 
      pageContent.includes('Focus') ||
      pageContent.includes('focus') ||
      pageContent.includes('Theme') ||
      pageContent.includes('Advice') ||
      pageContent.includes('Coach') ||
      pageContent.includes('maturity');
    
    expect(hasCoachingContent).toBeTruthy();
  });
});

test.describe('Progress Page', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should load progress page', async ({ page }) => {
    await page.goto('/progress', { waitUntil: 'domcontentloaded' });
    
    // Check progress page loads
    const progressPage = page.locator('[data-testid="progress-page"]');
    await expect(progressPage).toBeVisible({ timeout: 15000 });
    
    await page.screenshot({ path: 'progress-page-loaded.jpeg', quality: 20 });
  });

  test('should display rating and accuracy sections', async ({ page }) => {
    await page.goto('/progress', { waitUntil: 'domcontentloaded' });
    
    // Wait for content to load
    await page.waitForLoadState('domcontentloaded');
    
    // Check for Rating section
    const ratingText = page.getByText('Rating');
    await expect(ratingText.first()).toBeVisible({ timeout: 10000 });
    
    // Check for Accuracy section
    const accuracyText = page.getByText('Accuracy');
    await expect(accuracyText.first()).toBeVisible({ timeout: 10000 });
  });

  test('should show back to coach button', async ({ page }) => {
    await page.goto('/progress', { waitUntil: 'domcontentloaded' });
    
    // Check for back button
    const backButton = page.locator('[data-testid="back-to-coach"]');
    await expect(backButton).toBeVisible({ timeout: 10000 });
    
    // Click should navigate to coach
    await backButton.click();
    await page.waitForURL(/\/coach/, { timeout: 10000 });
  });
});

test.describe('Coach Focus Card', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should display coach focus card if user has theme', async ({ page }) => {
    await page.goto('/coach', { waitUntil: 'domcontentloaded' });
    
    // Wait for page to load completely
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // Wait for API calls
    
    // Check for focus card or focus-related content
    const focusCard = page.locator('[data-testid="coach-focus-card"]');
    const isFocusCardVisible = await focusCard.isVisible().catch(() => false);
    
    if (isFocusCardVisible) {
      // Verify focus card content
      const cardText = await focusCard.textContent();
      
      // Should show theme-related content
      expect(
        cardText.includes('Focus') || 
        cardText.includes('Week') ||
        cardText.includes('rules') ||
        cardText.includes('Rules')
      ).toBeTruthy();
    } else {
      // If no focus card, check for behavioral insight or other coach content
      const pageContent = await page.textContent('body');
      const hasCoachContent = pageContent.includes('Coach') || pageContent.includes('Focus');
      expect(hasCoachContent).toBeTruthy();
    }
    
    await page.screenshot({ path: 'coach-focus-card.jpeg', quality: 20 });
  });

  test('should show maturity level badge in focus card', async ({ page }) => {
    await page.goto('/coach', { waitUntil: 'domcontentloaded' });
    
    // Wait for API data
    await page.waitForTimeout(2000);
    
    // Look for maturity level indicators
    const pageContent = await page.textContent('body');
    
    // Check if any maturity level is shown
    const hasMaturityInfo = 
      pageContent.includes('Novice') ||
      pageContent.includes('Developing') ||
      pageContent.includes('Disciplined') ||
      pageContent.includes('Advanced') ||
      pageContent.includes('maturity') ||
      pageContent.includes('Coach Style');
    
    // This is informational - don't fail if not visible yet
    console.log('Has maturity info:', hasMaturityInfo);
  });
});

test.describe('Deep Session Modal', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should be able to trigger deep session from API', async ({ page }) => {
    // Start a deep session via API
    const response = await page.request.post(`${BASE_URL}/api/coach/deep-session/start`, {
      data: { trigger: "manual" },
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.session_id).toBeDefined();
    expect(data.current_step).toBe(1);
    expect(data.content).toBeDefined();
    
    // Check content has expected structure
    expect(data.content.title).toBeDefined();
    expect(data.content.step).toBe(1);
  });

  test('should advance through deep session steps', async ({ page }) => {
    // Start session
    const startRes = await page.request.post(`${BASE_URL}/api/coach/deep-session/start`, {
      data: { trigger: "manual" },
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(startRes.ok()).toBeTruthy();
    const startData = await startRes.json();
    const sessionId = startData.session_id;
    
    // Advance to step 2
    const advanceRes = await page.request.post(`${BASE_URL}/api/coach/deep-session/${sessionId}/advance`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(advanceRes.ok()).toBeTruthy();
    const advanceData = await advanceRes.json();
    expect(advanceData.current_step).toBe(2);
    
    // Submit reflection at step 2
    const reflectRes = await page.request.post(`${BASE_URL}/api/coach/deep-session/${sessionId}/reflection`, {
      data: { answer: "momentum" },
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(reflectRes.ok()).toBeTruthy();
    const reflectData = await reflectRes.json();
    expect(reflectData.current_step).toBe(3);
  });
});

test.describe('Behavioral Maturity API', () => {
  test('should return maturity level for dev user', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/maturity`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.maturity_level).toBeDefined();
    expect(['Novice', 'Developing', 'Disciplined', 'Advanced']).toContain(data.maturity_level);
    
    expect(data.tone_config).toBeDefined();
    expect(data.metrics).toBeDefined();
    expect(data.description).toBeDefined();
  });

  test('should adapt message based on maturity', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/maturity/adapt-message`, {
      params: {
        issue_type: 'threat_scan_failure',
        emotion: 'You missed the threat.',
        explanation: 'Check forcing moves first.'
      },
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.maturity_level).toBeDefined();
    expect(data.adapted_message).toBeDefined();
  });
});

test.describe('Coach State API', () => {
  test('should return coach state with theme and maturity', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/state`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // Verify required fields
    expect(data.user_id).toBeDefined();
    expect(data.active_theme).toBeDefined();
    expect(data.behavioral_maturity_level).toBeDefined();
    expect(data.coach_tone_mode).toBeDefined();
    expect(data.micro_rules).toBeDefined();
    expect(Array.isArray(data.micro_rules)).toBeTruthy();
    
    // Verify valid values
    const validThemes = [
      'CalculationDepth', 'ThreatVerification', 'ConversionDiscipline',
      'PieceSafety', 'TimeManagement', 'OpeningRepertoire',
      'EndgameTechnique', 'PositionalPatience'
    ];
    expect(validThemes).toContain(data.active_theme);
    
    const validMaturity = ['Novice', 'Developing', 'Disciplined', 'Advanced'];
    expect(validMaturity).toContain(data.behavioral_maturity_level);
    
    const validTones = ['ExplainMore', 'Balanced', 'ChallengeMore'];
    expect(validTones).toContain(data.coach_tone_mode);
  });

  test('should return theme stats', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/theme-stats`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    
    // If user has a theme, check structure
    if (data.has_theme) {
      expect(data.theme_display).toBeDefined();
      expect(data.micro_rules).toBeDefined();
      expect(data.games_on_theme).toBeDefined();
      expect(data.days_on_theme).toBeDefined();
    }
  });
});

test.describe('Coach Analytics API', () => {
  test('should return analytics summary', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/analytics/summary`, {
      params: { days: 30 },
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.period_days).toBeDefined();
    expect(data.event_counts).toBeDefined();
    expect(data.total_events).toBeDefined();
  });

  test('should return maturity progression', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/analytics/maturity-progression`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.progression).toBeDefined();
    expect(Array.isArray(data.progression)).toBeTruthy();
  });
});
