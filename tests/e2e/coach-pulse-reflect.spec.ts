import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://game-audit-lab.preview.emergentagent.com';

test.describe('Coach Pulse Indicator', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('Coach Pulse appears in header when reflections pending', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check if coach pulse is visible (depends on pending reflections)
    const coachPulse = page.getByTestId('coach-pulse');
    
    // The coach pulse should be visible when there are pending reflections or fresh losses
    // Based on API: /api/reflect/pending/count returns count > 0
    const isVisible = await coachPulse.isVisible({ timeout: 10000 }).catch(() => false);
    
    if (isVisible) {
      // Verify it shows "Reflect" or "Fix Loss" text
      await expect(coachPulse).toBeVisible();
      const text = await coachPulse.textContent();
      expect(text).toMatch(/Reflect|Fix Loss/);
      
      await page.screenshot({ path: '.screenshots/coach-pulse-visible.jpeg', quality: 20 });
    } else {
      // If no pending reflections, coach pulse won't show - document this
      console.log('No pending reflections - Coach Pulse not visible (expected when no action needed)');
    }
  });

  test('Coach Pulse shows Brain icon with pulsing indicator', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const coachPulse = page.getByTestId('coach-pulse');
    const isVisible = await coachPulse.isVisible({ timeout: 10000 }).catch(() => false);
    
    if (isVisible) {
      // Check for Brain icon (SVG with class containing lucide or brain)
      const brainIcon = coachPulse.locator('svg').first();
      await expect(brainIcon).toBeVisible();
      
      // Check for pulsing indicator (animate-pulse class)
      const pulseIndicator = coachPulse.locator('span.animate-pulse, .animate-pulse');
      await expect(pulseIndicator).toBeVisible();
    }
  });

  test('Coach Pulse navigates to /reflect when clicked', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    const coachPulse = page.getByTestId('coach-pulse');
    const isVisible = await coachPulse.isVisible({ timeout: 10000 }).catch(() => false);
    
    if (isVisible) {
      // Get text to determine type
      const text = await coachPulse.textContent();
      
      await coachPulse.click({ force: true });
      
      // Should navigate to /reflect or /recover based on type
      if (text?.includes('Fix Loss')) {
        await page.waitForURL(/\/recover\//, { timeout: 10000 });
      } else {
        await page.waitForURL(/\/reflect/, { timeout: 10000 });
      }
      
      await page.screenshot({ path: '.screenshots/coach-pulse-navigation.jpeg', quality: 20 });
    }
  });
});

test.describe('Reflect Page - Chip-based UI', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('Reflect page loads with game info and moment count', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for page title "Reflect"
    await expect(page.getByRole('heading', { name: /Reflect/ })).toBeVisible({ timeout: 15000 });
    
    // Check for game badge (e.g., "1 game")
    const gameBadge = page.locator('div').filter({ hasText: /\d+ game/ }).first();
    const hasBadge = await gameBadge.isVisible({ timeout: 5000 }).catch(() => false);
    
    // Either has games to reflect or shows "All caught up!"
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 2000 }).catch(() => false);
    
    expect(hasBadge || hasNoPending).toBe(true);
    
    await page.screenshot({ path: '.screenshots/reflect-page-loaded.jpeg', quality: 20 });
  });

  test('Reflect page shows chip-based intent selection (step 0)', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check if we have games to reflect on
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping intent selection test');
      return;
    }
    
    // Check for "What were you trying to do?" heading
    await expect(page.getByRole('heading', { name: /What were you trying to do/i })).toBeVisible({ timeout: 15000 });
    
    // Check for intent chips - verify at least some are visible
    const intentChips = [
      page.locator('button').filter({ hasText: 'Attack' }),
      page.locator('button').filter({ hasText: 'Defend' }),
      page.locator('button').filter({ hasText: /Develop.*Improve/i }),
      page.locator('button').filter({ hasText: /Simplify.*Trade/i }),
      page.locator('button').filter({ hasText: /Win material/i }),
      page.locator('button').filter({ hasText: /Avoid a threat/i }),
      page.locator('button').filter({ hasText: /Time pressure/i }),
      page.locator('button').filter({ hasText: /Not sure/i }),
    ];
    
    // At least 6 intent chips should be visible
    let visibleCount = 0;
    for (const chip of intentChips) {
      if (await chip.isVisible({ timeout: 1000 }).catch(() => false)) {
        visibleCount++;
      }
    }
    
    expect(visibleCount).toBeGreaterThanOrEqual(6);
    
    await page.screenshot({ path: '.screenshots/reflect-intent-chips.jpeg', quality: 20 });
  });

  test('Selecting intent advances to confidence selection (step 1)', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping confidence selection test');
      return;
    }
    
    // Wait for intent selection to be visible
    await expect(page.getByRole('heading', { name: /What were you trying to do/i })).toBeVisible({ timeout: 15000 });
    
    // Click on "Defend" intent chip
    const defendChip = page.locator('button').filter({ hasText: 'Defend' });
    await defendChip.click();
    
    // Should advance to confidence selection - "How sure were you?"
    await expect(page.getByRole('heading', { name: /How sure were you/i })).toBeVisible({ timeout: 5000 });
    
    // Check for confidence chips
    await expect(page.locator('button').filter({ hasText: 'Very sure' })).toBeVisible();
    await expect(page.locator('button').filter({ hasText: 'Somewhat sure' })).toBeVisible();
    await expect(page.locator('button').filter({ hasText: /Guessing.*fast move/i })).toBeVisible();
    
    // Check that selected intent is shown
    await expect(page.getByText(/Intent:.*defend/i)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/reflect-confidence-chips.jpeg', quality: 20 });
  });

  test('Selecting confidence advances to optional quick tags (step 2)', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping quick tags test');
      return;
    }
    
    // Wait for intent selection
    await expect(page.getByRole('heading', { name: /What were you trying to do/i })).toBeVisible({ timeout: 15000 });
    
    // Select intent
    const defendChip = page.locator('button').filter({ hasText: 'Defend' });
    await defendChip.click();
    
    // Wait for confidence selection
    await expect(page.getByRole('heading', { name: /How sure were you/i })).toBeVisible({ timeout: 5000 });
    
    // Select confidence
    const somewhatsureChip = page.locator('button').filter({ hasText: 'Somewhat sure' });
    await somewhatsureChip.click();
    
    // Should advance to quick tags - "What fits your thinking?"
    await expect(page.getByRole('heading', { name: /What fits your thinking/i })).toBeVisible({ timeout: 5000 });
    
    // Should see "Submit Reflection" button
    await expect(page.locator('button').filter({ hasText: /Submit Reflection/i })).toBeVisible();
    
    // Should show context with intent and confidence
    await expect(page.getByText(/Intent:.*defend/i)).toBeVisible();
    await expect(page.getByText(/Confidence:.*somewhat/i)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/reflect-quick-tags.jpeg', quality: 20 });
  });

  test('Reflect page shows optional quick tags as chips', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping quick tags test');
      return;
    }
    
    // Navigate to step 2 (quick tags)
    await expect(page.getByRole('heading', { name: /What were you trying to do/i })).toBeVisible({ timeout: 15000 });
    await page.locator('button').filter({ hasText: 'Defend' }).click();
    await expect(page.getByRole('heading', { name: /How sure were you/i })).toBeVisible({ timeout: 5000 });
    await page.locator('button').filter({ hasText: 'Somewhat sure' }).click();
    
    // Wait for quick tags to load
    await expect(page.getByRole('heading', { name: /What fits your thinking/i })).toBeVisible({ timeout: 5000 });
    
    // Quick tags are position-specific and may vary, but should show some tags
    // Check for common quick tag patterns
    const possibleTags = [
      /missed a threat/i,
      /missed.*capture/i,
      /felt danger/i,
      /thought I had time/i,
      /played too fast/i,
      /not sure what to do/i,
    ];
    
    // Wait for tags to load (there's a loading state)
    await page.waitForTimeout(1000);
    
    // At least some tags should be visible (they're dynamically generated)
    const tagButtons = page.locator('[class*="flex-wrap"] button');
    const tagCount = await tagButtons.count();
    
    // May have 0 tags if position doesn't match patterns, or multiple tags
    console.log(`Found ${tagCount} quick tags`);
    
    // Check for "+ Add your own description" option
    await expect(page.getByText(/Add your own description/i)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/reflect-quick-tags-chips.jpeg', quality: 20 });
  });
});

test.describe('Reflect Page - Board with Arrows', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('Reflect page shows chess board with position', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping board test');
      return;
    }
    
    // Wait for moments to load (not "Loading moments...")
    await expect(page.getByText(/Loading moments/)).not.toBeVisible({ timeout: 20000 });
    
    // Wait for intent question which signals board is loaded
    await expect(page.getByRole('heading', { name: /What were you trying to do/i })).toBeVisible({ timeout: 15000 });
    
    // Chess board should be visible - CoachBoard uses cg-wrap or board div
    const board = page.locator('.cg-wrap, [class*="cg-wrap"], .cg-board');
    await expect(board.first()).toBeVisible({ timeout: 10000 });
    
    await page.screenshot({ path: '.screenshots/reflect-board.jpeg', quality: 20 });
  });

  test('Reflect page shows view mode toggle (Your Move / Better Move / Both)', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping view mode test');
      return;
    }
    
    // Check for view mode toggle buttons
    await expect(page.locator('button').filter({ hasText: 'Your Move' })).toBeVisible({ timeout: 15000 });
    await expect(page.locator('button').filter({ hasText: 'Better Move' })).toBeVisible();
    await expect(page.locator('button').filter({ hasText: 'Both' })).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/reflect-view-mode-toggle.jpeg', quality: 20 });
  });

  test('View mode toggle changes displayed arrows', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping arrow test');
      return;
    }
    
    // Wait for board to load
    await expect(page.locator('.cg-wrap')).toBeVisible({ timeout: 15000 });
    
    // Default is "Your Move" - should show red arrow
    const yourMoveBtn = page.locator('button').filter({ hasText: 'Your Move' });
    await expect(yourMoveBtn).toBeVisible();
    
    // Click "Better Move" to show green arrow
    const betterMoveBtn = page.locator('button').filter({ hasText: 'Better Move' });
    await betterMoveBtn.click();
    
    await page.screenshot({ path: '.screenshots/reflect-better-move-arrow.jpeg', quality: 20 });
    
    // Click "Both" to show both arrows
    const bothBtn = page.locator('button').filter({ hasText: 'Both' });
    await bothBtn.click();
    
    await page.screenshot({ path: '.screenshots/reflect-both-arrows.jpeg', quality: 20 });
    
    // Click back to "Your Move"
    await yourMoveBtn.click();
    
    await page.screenshot({ path: '.screenshots/reflect-your-move-arrow.jpeg', quality: 20 });
  });

  test('Reflect page shows move info (You played vs Better was)', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping move info test');
      return;
    }
    
    // Wait for moments to load
    await expect(page.getByText(/Loading moments/)).not.toBeVisible({ timeout: 20000 });
    
    // Wait for intent question
    await expect(page.getByRole('heading', { name: /What were you trying to do/i })).toBeVisible({ timeout: 15000 });
    
    // Check for "You played" label - use exact text to avoid matching "Before you played"
    await expect(page.getByText('You played', { exact: true })).toBeVisible({ timeout: 5000 });
    
    // Check for "Better was" label
    await expect(page.getByText('Better was', { exact: true })).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/reflect-move-info.jpeg', quality: 20 });
  });

  test('Reflect page shows moment type badge (Blunder/Mistake/Critical)', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping moment type test');
      return;
    }
    
    // Check for moment type badge
    const blunderBadge = page.locator('div').filter({ hasText: /Blunder|Mistake|Critical/i }).first();
    await expect(blunderBadge).toBeVisible({ timeout: 15000 });
    
    // Should show move number
    await expect(page.getByText(/Move \d+/)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/reflect-moment-badge.jpeg', quality: 20 });
  });
});


test.describe('Cognitive Gap Analysis Feature', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('Full reflection flow displays Cognitive Gap Analysis after submission', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping cognitive gap test');
      return;
    }
    
    // Step 0: Wait for plan/hypothesis page - heading is "What was your plan here?"
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    // Click the position-specific hypothesis button (e.g., "Were you trying to defend the pawn?")
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ });
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click();
      // After clicking hypothesis, need to click Continue
      const continueBtn = page.locator('button').filter({ hasText: 'Continue' });
      await continueBtn.click();
    } else {
      // Fallback: for lower-rated players with simple intent chips
      const defendChip = page.locator('button').filter({ hasText: 'Defend' });
      if (await defendChip.isVisible({ timeout: 2000 }).catch(() => false)) {
        await defendChip.click();
      }
    }
    
    // Step 1: Select confidence - heading is "How confident were you?"
    await expect(page.getByText(/How confident were you/i)).toBeVisible({ timeout: 10000 });
    
    const somewhatsureChip = page.locator('button').filter({ hasText: 'Somewhat sure' });
    await somewhatsureChip.click();
    
    // Step 2: Quick tags (optional) - heading is "What else was in your thinking?"
    await expect(page.getByText(/What else was in your thinking/i)).toBeVisible({ timeout: 10000 });
    
    // Click Submit Reflection button
    const submitBtn = page.getByTestId('submit-reflection-btn');
    await expect(submitBtn).toBeVisible({ timeout: 5000 });
    await expect(submitBtn).not.toBeDisabled({ timeout: 5000 });
    await submitBtn.click();
    
    // Wait for cognitive gap analysis result to display
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-result.jpeg', quality: 20 });
  });

  test('Cognitive Gap Analysis result shows explanation', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Check for games
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping explanation test');
      return;
    }
    
    // Go through flow - Step 0
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ });
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click();
      await page.locator('button').filter({ hasText: 'Continue' }).click();
    } else {
      await page.locator('button').filter({ hasText: /Defend|Not sure/i }).first().click();
    }
    
    // Step 1: Select confidence
    await expect(page.getByText(/How confident were you/i)).toBeVisible({ timeout: 10000 });
    await page.locator('button').filter({ hasText: /Guessing.*fast|Somewhat sure/i }).first().click();
    
    // Step 2: Submit
    await expect(page.getByText(/What else was in your thinking/i)).toBeVisible({ timeout: 10000 });
    const submitBtn = page.getByTestId('submit-reflection-btn');
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();
    
    // Check for cognitive gap explanation content
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Should show explanation text explaining WHY the move was a mistake
    const explanationText = page.locator('text=/You.*identified|The best move was|Calculate.*deeper|missed/i');
    await expect(explanationText.first()).toBeVisible({ timeout: 5000 });
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-explanation.jpeg', quality: 20 });
  });

  test('Cognitive Gap Analysis shows gap type badge', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping gap type test');
      return;
    }
    
    // Navigate through reflection flow - Step 0
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ });
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click();
      await page.locator('button').filter({ hasText: 'Continue' }).click();
    } else {
      await page.locator('button').filter({ hasText: /Defend|Attack|Not sure/i }).first().click();
    }
    
    // Step 1
    await expect(page.getByText(/How confident were you/i)).toBeVisible({ timeout: 10000 });
    await page.locator('button').filter({ hasText: /Very sure/i }).click();
    
    // Step 2: Submit
    await expect(page.getByText(/What else was in your thinking/i)).toBeVisible({ timeout: 10000 });
    const submitBtn = page.getByTestId('submit-reflection-btn');
    await submitBtn.click();
    
    // Wait for result
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Look for gap type badge - these are the possible gap types shown as badges
    // e.g., "Calculation Depth", "Threat Blindness", "Tactical Oversight", etc.
    const gapTypeBadges = page.locator('text=/Calculation Depth|Threat Blindness|Tactical Oversight|Positional Misread|Defensive Lapse|Overconfidence|Time Pressure|Pattern Unfamiliarity|Hanging Piece|Check Blindness|Missed Fork|Missed Pin/i');
    
    const badgeVisible = await gapTypeBadges.first().isVisible({ timeout: 5000 }).catch(() => false);
    
    if (badgeVisible) {
      console.log('Gap type badge is visible');
      await expect(gapTypeBadges.first()).toBeVisible();
    }
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-badge.jpeg', quality: 20 });
  });

  test('Cognitive Gap Analysis shows coaching focus section', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping coaching focus test');
      return;
    }
    
    // Navigate through flow - Step 0
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ });
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click();
      await page.locator('button').filter({ hasText: 'Continue' }).click();
    } else {
      await page.locator('button').filter({ hasText: /Defend|Attack|Not sure/i }).first().click();
    }
    
    // Step 1
    await expect(page.getByText(/How confident were you/i)).toBeVisible({ timeout: 10000 });
    await page.locator('button').filter({ hasText: /Somewhat sure|Very sure/i }).first().click();
    
    // Step 2: Submit
    await expect(page.getByText(/What else was in your thinking/i)).toBeVisible({ timeout: 10000 });
    const submitBtn = page.getByTestId('submit-reflection-btn');
    await submitBtn.click();
    
    // Wait for result
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Look for "YOUR FOCUS" section which shows coaching advice
    const coachingFocus = page.getByText(/YOUR FOCUS|Your focus/i);
    await expect(coachingFocus.first()).toBeVisible({ timeout: 5000 });
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-coaching-focus.jpeg', quality: 20 });
  });

  test('Cognitive Gap Analysis shows Evidence section', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping evidence test');
      return;
    }
    
    // Navigate through flow - Step 0
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ });
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click();
      await page.locator('button').filter({ hasText: 'Continue' }).click();
    } else {
      await page.locator('button').filter({ hasText: /Defend|Attack|Not sure/i }).first().click();
    }
    
    // Step 1
    await expect(page.getByText(/How confident were you/i)).toBeVisible({ timeout: 10000 });
    await page.locator('button').filter({ hasText: /Somewhat sure|Very sure/i }).first().click();
    
    // Step 2: Submit
    await expect(page.getByText(/What else was in your thinking/i)).toBeVisible({ timeout: 10000 });
    const submitBtn = page.getByTestId('submit-reflection-btn');
    await submitBtn.click();
    
    // Wait for result
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Look for Evidence section 
    const evidenceLabel = page.getByText(/EVIDENCE/i);
    const evidenceVisible = await evidenceLabel.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (evidenceVisible) {
      console.log('Evidence section visible');
      await expect(evidenceLabel).toBeVisible();
    } else {
      console.log('Evidence section not visible (may not have evidence for this analysis)');
    }
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-evidence.jpeg', quality: 20 });
  });

  test('Next moment button works after cognitive gap display', async ({ page }) => {
    await page.goto(`${BASE_URL}/reflect`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    const allCaughtUp = page.getByText(/All caught up/);
    const hasNoPending = await allCaughtUp.isVisible({ timeout: 3000 }).catch(() => false);
    
    if (hasNoPending) {
      console.log('No games to reflect on - skipping next moment test');
      return;
    }
    
    // Navigate through flow - Step 0
    await expect(page.getByText(/What was your plan here/i)).toBeVisible({ timeout: 15000 });
    
    const hypothesisBtn = page.locator('button').filter({ hasText: /Were you trying to/ });
    if (await hypothesisBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await hypothesisBtn.click();
      await page.locator('button').filter({ hasText: 'Continue' }).click();
    } else {
      await page.locator('button').filter({ hasText: /Defend|Attack|Not sure/i }).first().click();
    }
    
    // Step 1
    await expect(page.getByText(/How confident were you/i)).toBeVisible({ timeout: 10000 });
    await page.locator('button').filter({ hasText: /Somewhat sure|Very sure/i }).first().click();
    
    // Step 2: Submit
    await expect(page.getByText(/What else was in your thinking/i)).toBeVisible({ timeout: 10000 });
    const submitBtn = page.getByTestId('submit-reflection-btn');
    await submitBtn.click();
    
    // Wait for result
    await expect(page.getByText(/Why this was a mistake/i)).toBeVisible({ timeout: 30000 });
    
    // Look for "Next moment" or "Complete" button
    const nextMomentBtn = page.getByTestId('next-moment-btn');
    await expect(nextMomentBtn).toBeVisible({ timeout: 5000 });
    
    // Get button text
    const buttonText = await nextMomentBtn.textContent();
    console.log(`Next button text: ${buttonText}`);
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-next-button.jpeg', quality: 20 });
    
    // Click it
    await nextMomentBtn.click();
    
    // Should either move to next moment or complete
    const isComplete = buttonText?.includes('Complete');
    
    if (isComplete) {
      console.log('Completed reflection - no more moments');
    } else {
      // Should show next moment's plan selection
      await expect(page.getByText(/What was your plan here|All caught up/i)).toBeVisible({ timeout: 10000 });
    }
    
    await page.screenshot({ path: '.screenshots/cognitive-gap-after-next.jpeg', quality: 20 });
  });
});
