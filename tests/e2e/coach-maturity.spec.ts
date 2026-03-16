/**
 * Coach State & Behavioral Maturity E2E Tests
 * 
 * Tests:
 * 1. Progress page displays coach focus and maturity level
 * 2. API endpoints for coach state and maturity
 * 3. Deep session flow
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'https://coaching-moments.preview.emergentagent.com';

// Helper to login via dev login API
async function devLogin(page) {
  await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
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

test.describe('Progress Page - Coach Focus Display', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should display coach focus card with theme and rules', async ({ page }) => {
    await page.goto('/progress', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Check for Coach Focus card
    const pageContent = await page.textContent('body');
    
    // Should show coach focus this week
    expect(pageContent).toContain('Coach Focus');
    
    // Should show Your Rules (not case sensitive)
    expect(pageContent.toLowerCase()).toContain('your rules');
    
    await page.screenshot({ path: 'progress-coach-focus.jpeg', quality: 20 });
  });

  test('should display maturity level badge in coach focus card', async ({ page }) => {
    await page.goto('/progress', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    const pageContent = await page.textContent('body');
    
    // Should show Coach Style
    expect(pageContent).toContain('Coach Style');
    
    // Should show one of the maturity levels
    const hasMaturityLevel = 
      pageContent.includes('Novice') ||
      pageContent.includes('Developing') ||
      pageContent.includes('Disciplined') ||
      pageContent.includes('Advanced');
    
    expect(hasMaturityLevel).toBeTruthy();
  });

  test('should show theme name in focus card', async ({ page }) => {
    await page.goto('/progress', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    const pageContent = await page.textContent('body');
    
    // Should show one of the valid themes
    const hasValidTheme = 
      pageContent.includes('ThreatVerification') ||
      pageContent.includes('CalculationDepth') ||
      pageContent.includes('ConversionDiscipline') ||
      pageContent.includes('PieceSafety') ||
      pageContent.includes('TimeManagement') ||
      pageContent.includes('OpeningRepertoire') ||
      pageContent.includes('EndgameTechnique') ||
      pageContent.includes('PositionalPatience') ||
      pageContent.includes('Threat Verification') ||
      pageContent.includes('Calculation Depth') ||
      pageContent.includes('Conversion Discipline') ||
      pageContent.includes('Piece Safety');
    
    expect(hasValidTheme).toBeTruthy();
  });

  test('should show micro-rules in focus card', async ({ page }) => {
    await page.goto('/progress', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    const pageContent = await page.textContent('body');
    
    // Should have Your Rules section with at least one rule
    expect(pageContent.toLowerCase()).toContain('your rules');
    
    // Rules should include coaching-related text
    const hasRules = 
      pageContent.includes('Before') ||
      pageContent.includes('When') ||
      pageContent.includes('scan') ||
      pageContent.includes('check') ||
      pageContent.includes('pause');
    
    expect(hasRules).toBeTruthy();
  });
});

test.describe('Dashboard Page', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should load dashboard after login', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Check for dashboard content
    const pageContent = await page.textContent('body');
    
    // Should show welcome message or games/analyzed stats
    const hasDashboardContent = 
      pageContent.includes('Welcome') ||
      pageContent.includes('GAMES') ||
      pageContent.includes('ANALYZED') ||
      pageContent.includes('BLUNDERS');
    
    expect(hasDashboardContent).toBeTruthy();
    
    await page.screenshot({ path: 'dashboard-loaded.jpeg', quality: 20 });
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
    expect(data.micro_rules.length).toBeGreaterThanOrEqual(1);
    
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

test.describe('Behavioral Maturity API', () => {
  test('should return maturity level with tone config', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/maturity`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.maturity_level).toBeDefined();
    expect(['Novice', 'Developing', 'Disciplined', 'Advanced']).toContain(data.maturity_level);
    
    expect(data.tone_config).toBeDefined();
    expect(data.tone_config.emotion_intensity).toBeDefined();
    expect(data.tone_config.max_lines).toBeDefined();
    expect(data.tone_config.explanation_depth).toBeDefined();
    
    expect(data.metrics).toBeDefined();
    expect(data.description).toBeDefined();
  });

  test('should update maturity when called', async ({ page }) => {
    const response = await page.request.post(`${BASE_URL}/api/coach/maturity/update`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.maturity_level).toBeDefined();
    expect(data.tone_mode).toBeDefined();
    expect(typeof data.transitioned).toBe('boolean');
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
    
    // Adapted message should have emotion or explanation
    const adapted = data.adapted_message;
    expect(adapted.emotion || adapted.explanation).toBeTruthy();
  });
});

test.describe('Deep Session API', () => {
  test('should check deep session trigger status', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/deep-session/check`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(typeof data.should_trigger).toBe('boolean');
  });

  test('should start deep session', async ({ page }) => {
    const response = await page.request.post(`${BASE_URL}/api/coach/deep-session/start`, {
      data: { trigger: "manual" },
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.session_id).toBeDefined();
    expect(data.current_step).toBe(1);
    expect(data.content).toBeDefined();
    expect(data.content.title).toBeDefined();
    expect(data.content.step).toBe(1);
  });

  test('should complete full deep session flow', async ({ page }) => {
    // Start session
    const startRes = await page.request.post(`${BASE_URL}/api/coach/deep-session/start`, {
      data: { trigger: "manual" },
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(startRes.ok()).toBeTruthy();
    const startData = await startRes.json();
    const sessionId = startData.session_id;
    expect(startData.current_step).toBe(1);
    
    // Advance to step 2
    const adv1Res = await page.request.post(`${BASE_URL}/api/coach/deep-session/${sessionId}/advance`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    expect(adv1Res.ok()).toBeTruthy();
    expect((await adv1Res.json()).current_step).toBe(2);
    
    // Submit reflection at step 2
    const reflectRes = await page.request.post(`${BASE_URL}/api/coach/deep-session/${sessionId}/reflection`, {
      data: { answer: "momentum" },
      headers: { 'Cookie': 'dev_login=true' }
    });
    expect(reflectRes.ok()).toBeTruthy();
    expect((await reflectRes.json()).current_step).toBe(3);
    
    // Advance through remaining steps
    for (const expectedStep of [4, 5, 6]) {
      const advRes = await page.request.post(`${BASE_URL}/api/coach/deep-session/${sessionId}/advance`, {
        headers: { 'Cookie': 'dev_login=true' }
      });
      expect(advRes.ok()).toBeTruthy();
      expect((await advRes.json()).current_step).toBe(expectedStep);
    }
    
    // Complete session
    const completeRes = await page.request.post(`${BASE_URL}/api/coach/deep-session/${sessionId}/complete`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    expect(completeRes.ok()).toBeTruthy();
    
    const completeData = await completeRes.json();
    expect(completeData.completed).toBe(true);
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
    expect(data.period_days).toBe(30);
    expect(data.event_counts).toBeDefined();
    expect(typeof data.total_events).toBe('number');
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

  test('should return theme history', async ({ page }) => {
    const response = await page.request.get(`${BASE_URL}/api/coach/analytics/theme-history`, {
      headers: { 'Cookie': 'dev_login=true' }
    });
    
    expect(response.ok()).toBeTruthy();
    
    const data = await response.json();
    expect(data.theme_switches).toBeDefined();
    expect(Array.isArray(data.theme_switches)).toBeTruthy();
  });
});

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
    await devLogin(page);
  });

  test('should navigate to Progress from sidebar', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Click Progress in sidebar
    const progressLink = page.getByRole('link', { name: 'Progress' });
    await progressLink.click();
    
    await page.waitForURL(/\/progress/, { timeout: 10000 });
    await page.waitForTimeout(2000);
    
    // Verify we're on progress page
    const pageContent = await page.textContent('body');
    expect(pageContent.toLowerCase()).toContain('coach focus');
  });
});
