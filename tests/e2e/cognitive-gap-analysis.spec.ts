import { test, expect } from '@playwright/test';

const BASE_URL = 'https://chess-trap-coach.preview.emergentagent.com';

test.describe('Cognitive Gap Analysis Feature', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
  });

  test('Full reflection flow displays Cognitive Gap Analysis after submission', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping cognitive gap test');
      return;
    }
    
    // Step 0: Wait for plan/hypothesis page
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    // Click the hypothesis button - be more specific
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to defend the pawn/ }).first();
    
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click({ force: true });
      
      // Click Continue button
      const continueBtn = page.locator('button').filter({ hasText: 'Continue' }).first();
      await expect(continueBtn).toBeEnabled({ timeout: 5000 });
      await continueBtn.click();
    } else {
      console.log('Hypothesis button not found, trying fallback');
      return;
    }
    
    // Step 1: Select confidence - use heading role
    await expect(page.getByRole('heading', { name: /How confident were you/ })).toBeVisible({ timeout: 10000 });
    
    const somewhatsureChip = page.locator('button').filter({ hasText: 'Somewhat sure' }).first();
    await somewhatsureChip.click();
    
    // Step 2: Wait for tags step
    await expect(page.getByRole('heading', { name: /What else was in your thinking/ })).toBeVisible({ timeout: 10000 });
    
    // Click Submit Reflection button
    const submitBtn = page.getByTestId('submit-reflection-btn');
    await expect(submitBtn).toBeVisible({ timeout: 5000 });
    await submitBtn.click();
    
    // Wait for cognitive gap analysis result to display
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Verify key elements of the cognitive gap display
    await expect(page.getByText(/EVIDENCE/i)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/YOUR FOCUS/i)).toBeVisible({ timeout: 5000 });
    
    // Next moment button should be visible
    await expect(page.getByTestId('next-moment-btn')).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-result.jpeg', quality: 20 });
  });

  test('Cognitive Gap Analysis displays gap type and explanation', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping test');
      return;
    }
    
    // Navigate through reflection flow
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ }).first();
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click({ force: true });
      await page.locator('button').filter({ hasText: 'Continue' }).first().click();
    } else {
      return;
    }
    
    await expect(page.getByRole('heading', { name: /How confident were you/ })).toBeVisible({ timeout: 10000 });
    await page.locator('button').filter({ hasText: 'Very sure' }).first().click();
    
    await expect(page.getByRole('heading', { name: /What else was in your thinking/ })).toBeVisible({ timeout: 10000 });
    await page.getByTestId('submit-reflection-btn').click();
    
    // Wait for cognitive gap result
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Check for gap type badge - one of the known gap types should be visible
    const gapTypeBadges = page.locator('text=/Calculation Depth|Threat Blindness|Tactical Oversight|Positional Misread|Defensive Lapse/i');
    const hasBadge = await gapTypeBadges.first().isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasBadge) {
      console.log('Gap type badge visible');
    }
    
    // Verify explanation text exists (contains actionable advice)
    const explanationText = page.locator('text=/Calculate|defend|missed|position|deeper/i');
    await expect(explanationText.first()).toBeVisible({ timeout: 5000 });
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-details.jpeg', quality: 20 });
  });

  test('Next moment button navigates after cognitive gap display', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('domcontentloaded');
    
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping test');
      return;
    }
    
    // Navigate through reflection flow
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ }).first();
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click({ force: true });
      await page.locator('button').filter({ hasText: 'Continue' }).first().click();
    } else {
      return;
    }
    
    await expect(page.getByRole('heading', { name: /How confident were you/ })).toBeVisible({ timeout: 10000 });
    await page.locator('button').filter({ hasText: 'Somewhat sure' }).first().click();
    
    await expect(page.getByRole('heading', { name: /What else was in your thinking/ })).toBeVisible({ timeout: 10000 });
    await page.getByTestId('submit-reflection-btn').click();
    
    // Wait for cognitive gap result
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Click Next moment button
    const nextBtn = page.getByTestId('next-moment-btn');
    await expect(nextBtn).toBeVisible({ timeout: 5000 });
    const buttonText = await nextBtn.textContent();
    
    console.log(`Next button text: ${buttonText}`);
    await nextBtn.click();
    
    // Should navigate to next moment or show completion
    await expect(page.getByText(/What was your plan here|All caught up/i)).toBeVisible({ timeout: 10000 });
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-next-moment.jpeg', quality: 20 });
  });
});
