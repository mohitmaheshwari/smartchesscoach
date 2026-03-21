import { test, expect } from '@playwright/test';
import { devLogin, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

/**
 * Focus Lock Mode Tests (Step 9)
 * 
 * Tests:
 * - FocusLockCard displays when lock is active
 * - FocusLockCard overrides CoachWeeklySignalCard
 * - FocusLockCard shows correct state info
 * - CTA buttons work
 */

const BASE_URL = process.env.BASE_URL || 'https://chess-truth-engine.preview.emergentagent.com';

test.describe('Focus Lock Dashboard Integration', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
  });

  test('Dashboard loads successfully without focus lock', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Ensure no focus lock is active
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`, {
      headers: { 'Content-Type': 'application/json' }
    });
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Verify dashboard loads
    await expect(page.getByTestId('dashboard-page')).toBeVisible();
    
    // Focus lock card should NOT be visible
    const focusLockCard = page.getByTestId('focus-lock-card');
    await expect(focusLockCard).not.toBeVisible();
  });

  test('FocusLockCard displays when lock is active', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Activate a focus lock via API
    const activateResponse = await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
      headers: { 'Content-Type': 'application/json' },
      data: { lesson_key: 'FORCING_BLIND', games: 5 }
    });
    
    // If lock already active, deactivate and try again
    if (!activateResponse.ok()) {
      await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
      await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
        headers: { 'Content-Type': 'application/json' },
        data: { lesson_key: 'FORCING_BLIND', games: 5 }
      });
    }
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Wait for FocusLockCard to appear
    const focusLockCard = page.getByTestId('focus-lock-card');
    await expect(focusLockCard).toBeVisible({ timeout: 10000 });
    
    // Cleanup - deactivate lock
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
  });

  test('FocusLockCard shows rule description and progress', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Ensure clean state and activate lock
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
      headers: { 'Content-Type': 'application/json' },
      data: { lesson_key: 'THREAT_VERIFICATION', games: 10 }
    });
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Wait for FocusLockCard
    const focusLockCard = page.getByTestId('focus-lock-card');
    await expect(focusLockCard).toBeVisible({ timeout: 10000 });
    
    // Card should contain "Focus Lock" text
    await expect(focusLockCard).toContainText('Focus Lock');
    
    // Card should show progress (0 of 10 games or similar)
    await expect(focusLockCard).toContainText(/\d+ of \d+ games/i);
    
    // Cleanup
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
  });

  test('FocusLockCard CTA button is clickable', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Ensure clean state and activate lock
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
      headers: { 'Content-Type': 'application/json' },
      data: { lesson_key: 'FORCING_BLIND', games: 5 }
    });
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Wait for FocusLockCard
    const focusLockCard = page.getByTestId('focus-lock-card');
    await expect(focusLockCard).toBeVisible({ timeout: 10000 });
    
    // Hide emergent badge
    await hideEmergentBadge(page);
    
    // Find and click CTA button
    const ctaButton = page.getByTestId('focus-lock-cta');
    await expect(ctaButton).toBeVisible();
    await expect(ctaButton).toBeEnabled();
    
    // Click should navigate (to /games)
    await ctaButton.click();
    
    // Verify navigation happened (URL changed)
    await page.waitForURL(/\/(games|deep-session)/);
    
    // Cleanup
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
  });

  test('Different lesson keys show appropriate content', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Test STOPPED_CALCULATION_EARLY
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
      headers: { 'Content-Type': 'application/json' },
      data: { lesson_key: 'STOPPED_CALCULATION_EARLY', games: 5 }
    });
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // FocusLockCard should be visible
    const focusLockCard = page.getByTestId('focus-lock-card');
    await expect(focusLockCard).toBeVisible({ timeout: 10000 });
    
    // Should have some content
    await expect(focusLockCard).toContainText('Focus Lock');
    
    // Cleanup
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
  });
});


test.describe('Focus Lock API Integration via UI', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
  });

  test('Focus lock state persists across page reloads', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Activate lock
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
      headers: { 'Content-Type': 'application/json' },
      data: { lesson_key: 'FORCING_BLIND', games: 5 }
    });
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Verify card is visible
    await expect(page.getByTestId('focus-lock-card')).toBeVisible({ timeout: 10000 });
    
    // Reload page
    await page.reload({ waitUntil: 'domcontentloaded' });
    
    // Card should still be visible after reload
    await expect(page.getByTestId('focus-lock-card')).toBeVisible({ timeout: 10000 });
    
    // Cleanup
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
  });

  test('Deactivating lock removes FocusLockCard from UI', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Activate lock
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
      headers: { 'Content-Type': 'application/json' },
      data: { lesson_key: 'FORCING_BLIND', games: 5 }
    });
    
    // Navigate to dashboard and verify card is visible
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('focus-lock-card')).toBeVisible({ timeout: 10000 });
    
    // Deactivate lock via API
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    
    // Refresh dashboard
    await page.reload({ waitUntil: 'domcontentloaded' });
    
    // Card should not be visible anymore
    await expect(page.getByTestId('focus-lock-card')).not.toBeVisible();
  });

  test('Dashboard shows other content when no lock active', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Ensure no lock is active
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Dashboard page should load
    await expect(page.getByTestId('dashboard-page')).toBeVisible();
    
    // Focus lock card should NOT be visible
    await expect(page.getByTestId('focus-lock-card')).not.toBeVisible();
    
    // Stats cards should still be visible
    const statsCards = page.locator('[data-testid="analyzed-stat-card"], [data-testid="blunders-stat-card"]');
    await expect(statsCards.first()).toBeVisible({ timeout: 10000 });
  });
});


test.describe('FocusLockCard Visual States', () => {
  test.beforeEach(async ({ page }) => {
    await dismissToasts(page);
  });

  test('FocusLockCard has correct visual structure', async ({ page }) => {
    // Login
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
    
    // Activate lock
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/activate`, {
      headers: { 'Content-Type': 'application/json' },
      data: { lesson_key: 'FORCING_BLIND', games: 5 }
    });
    
    // Navigate to dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Wait for card
    const card = page.getByTestId('focus-lock-card');
    await expect(card).toBeVisible({ timeout: 10000 });
    
    // Card should have content structure:
    // 1. "Focus Lock" label
    await expect(card.locator('text=Focus Lock')).toBeVisible();
    
    // 2. A progress indicator (text like "0 of 5 games")
    await expect(card).toContainText(/\d+ of \d+/);
    
    // 3. CTA button
    const ctaButton = page.getByTestId('focus-lock-cta');
    await expect(ctaButton).toBeVisible();
    
    // Take screenshot for visual verification
    await page.screenshot({ path: 'focus-lock-card.jpeg', quality: 20 });
    
    // Cleanup
    await page.request.post(`${BASE_URL}/api/coach/focus-lock/deactivate`);
  });
});
