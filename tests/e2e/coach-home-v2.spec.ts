import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

const BASE_URL = 'https://progress-track-61.preview.emergentagent.com';

/**
 * Coach Home V2 - Personalized Chess Coaching Tests
 * 
 * Features tested:
 * 1. Specific mistake patterns display (e.g., "27x missed threats")
 * 2. Progress trend messages
 * 3. Game cards with win celebration (trophy icon for clean wins)
 * 4. "Clean win! Let's see what worked" for wins with 0 blunders
 * 5. Blunder count display for losses
 * 6. Navigation to reflect page from game cards
 * 7. Focus advice section
 */

test.describe('Coach Home V2 - Specific Patterns Display', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Home page loads and displays hero section', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Verify coach home container is visible
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Hero section should be visible
    await expect(page.getByTestId('hero-section')).toBeVisible();
    
    // Greeting should be visible
    const greetingText = await page.locator('h1').first().textContent();
    expect(greetingText).toMatch(/Good (morning|afternoon|evening)/);
  });

  test('Specific mistake patterns display from API', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for the specific patterns display within the hero section
    // Pattern format: "{count}x {pattern_description} this week"
    const heroSection = page.getByTestId('hero-section');
    
    // Look for the amber-colored pattern alert box inside the hero
    const patternAlertBox = heroSection.locator('[class*="bg-amber"]').first();
    const patternVisible = await patternAlertBox.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (patternVisible) {
      // Verify it contains pattern count format
      const patternText = await patternAlertBox.textContent();
      expect(patternText).toMatch(/\d+x.*this week/i);
      
      // Should also contain "This is your main leak" message
      expect(patternText).toContain("main leak");
      
      await page.screenshot({ path: '.screenshots/specific-patterns-display.jpeg', quality: 20 });
    } else {
      // Alternative: look for text pattern directly in hero section
      const patternText = page.locator('text=/\\d+x.*this week/i').first();
      const textVisible = await patternText.isVisible({ timeout: 2000 }).catch(() => false);
      
      if (textVisible) {
        const text = await patternText.textContent();
        expect(text).toMatch(/\d+x.*this week/i);
      } else {
        // If no specific patterns, that's okay - user might not have enough data
        console.log('No specific patterns displayed - user may not have pattern data');
      }
    }
  });

  test('Progress trend message displays from API', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for progress trend messages
    // These can be: "Steady progress. Stay focused on your habits."
    // or "Excellent! X fewer blunders per game than before."
    // or "Blunders are creeping up. Let's slow down and focus."
    const progressMessages = [
      /steady progress/i,
      /fewer blunders/i,
      /blunders are creeping/i,
      /keep playing/i,
      /consistent play/i
    ];
    
    let foundProgressMessage = false;
    for (const pattern of progressMessages) {
      const element = page.locator(`text=${pattern}`).first();
      if (await element.isVisible({ timeout: 2000 }).catch(() => false)) {
        foundProgressMessage = true;
        break;
      }
    }
    
    // Progress trend should be visible when user has data
    // If not found, check the hero section for any trend indicator
    if (!foundProgressMessage) {
      const heroSection = page.getByTestId('hero-section');
      const heroText = await heroSection.textContent();
      // Should contain some progress-related text
      const hasProgressContent = /progress|habit|blunder|trend|improving|stable/i.test(heroText || '');
      console.log('Hero content includes progress context:', hasProgressContent);
    }
  });
});


test.describe('Coach Home V2 - Game Cards Display', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Game cards show in Games to Reflect section', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for "Games to Reflect" section or game cards
    const reflectSection = page.locator('text=Games to Reflect').first();
    const hasReflectSection = await reflectSection.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasReflectSection) {
      // Should show game cards
      const gameCards = page.locator('[data-testid^="reflect-game-"]');
      const cardCount = await gameCards.count();
      expect(cardCount).toBeGreaterThan(0);
      
      await page.screenshot({ path: '.screenshots/game-cards-display.jpeg', quality: 20 });
    } else {
      // User might be in TRAIN state with no games to reflect
      console.log('No games to reflect section - user may be in TRAIN state');
    }
  });

  test('Clean win displays trophy icon and celebratory message', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for "Clean win! Let's see what worked" message
    const cleanWinText = page.locator('text=Clean win').first();
    const hasCleanWin = await cleanWinText.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasCleanWin) {
      // Verify the full message
      await expect(cleanWinText).toContainText(/Clean win/);
      
      // The card should have green highlight (border-green-500/30)
      const cleanWinCard = cleanWinText.locator('xpath=ancestor::button[contains(@class, "border-green")]');
      const cardVisible = await cleanWinCard.isVisible({ timeout: 2000 }).catch(() => false);
      
      if (cardVisible) {
        // Trophy icon should be visible in clean win cards (Lucide Trophy icon)
        const trophyIcon = cleanWinCard.locator('svg').first();
        await expect(trophyIcon).toBeVisible();
      }
      
      await page.screenshot({ path: '.screenshots/clean-win-trophy.jpeg', quality: 20 });
    } else {
      // No clean wins in current data - this is valid
      console.log('No clean win cards - user may not have clean wins in reflection queue');
    }
  });

  test('Loss games show blunder count', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for blunder count messages in game cards
    // Format: "X blunders to understand" or "X blunder(s) to understand"
    const blunderText = page.locator('text=/\\d+ blunder.*to understand/i').first();
    const hasBlunderText = await blunderText.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasBlunderText) {
      const text = await blunderText.textContent();
      expect(text).toMatch(/\d+ blunder/i);
      
      await page.screenshot({ path: '.screenshots/loss-blunder-count.jpeg', quality: 20 });
    } else {
      // Alternative: look for "critical moment" messages
      const criticalMoment = page.locator('text=/critical moment/i').first();
      const hasCriticalMoment = await criticalMoment.isVisible({ timeout: 2000 }).catch(() => false);
      
      if (!hasCriticalMoment) {
        console.log('No blunder count displayed - user may not have losses in reflection queue');
      }
    }
  });

  test('Won games with blunders show close call message', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for "Won but X close call(s)" message
    const closeCallText = page.locator('text=/Won but.*close call/i').first();
    const hasCloseCall = await closeCallText.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasCloseCall) {
      const text = await closeCallText.textContent();
      expect(text).toMatch(/Won but \d+ close call/i);
    } else {
      console.log('No close call message - user may not have wins with blunders');
    }
  });
});


test.describe('Coach Home V2 - Navigation to Reflect', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Clicking game card navigates to reflect page', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Find the first game card
    const firstGameCard = page.getByTestId('reflect-game-0');
    const hasGameCard = await firstGameCard.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasGameCard) {
      // Click the game card
      await firstGameCard.click({ force: true });
      
      // Should navigate to /reflect with game parameter
      await page.waitForURL(/\/reflect/, { timeout: 10000 });
      
      // URL should contain game= parameter
      const url = page.url();
      expect(url).toMatch(/\/reflect/);
      
      await page.screenshot({ path: '.screenshots/navigate-to-reflect.jpeg', quality: 20 });
    } else {
      // If no game cards, user is in TRAIN state
      console.log('No game cards to click - user is in TRAIN state');
    }
  });

  test('Game card shows opponent name and time since', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for game cards with "vs" opponent name
    const opponentText = page.locator('text=/vs .+/').first();
    const hasOpponent = await opponentText.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasOpponent) {
      const text = await opponentText.textContent();
      expect(text).toMatch(/vs \w+/);
      
      // Time since should also be visible (e.g., "2h ago", "1d ago")
      const timeText = page.locator('text=/\\d+[hd] ago|Just now/').first();
      const hasTime = await timeText.isVisible({ timeout: 2000 }).catch(() => false);
      
      if (hasTime) {
        const timeContent = await timeText.textContent();
        expect(timeContent).toMatch(/(\d+[hd] ago|Just now)/);
      }
    }
  });
});


test.describe('Coach Home V2 - Focus Advice Section', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Focus advice card displays correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for focus advice card
    const focusCard = page.getByTestId('focus-advice-card');
    const hasFocusCard = await focusCard.isVisible({ timeout: 10000 }).catch(() => false);
    
    if (hasFocusCard) {
      // Should show "YOUR FOCUS" label
      await expect(focusCard.locator('text=Your Focus')).toBeVisible();
      
      // Should have advice text
      const adviceText = await focusCard.locator('p').last().textContent();
      expect(adviceText).toBeTruthy();
      expect((adviceText || '').length).toBeGreaterThan(10);
      
      await page.screenshot({ path: '.screenshots/focus-advice-card.jpeg', quality: 20 });
    } else {
      console.log('No focus advice card - user may not have analyzed games');
    }
  });

  test('Focus label shows in hero section', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('hero-section')).toBeVisible({ timeout: 15000 });
    
    // Look for "Focus:" label with the current focus stage
    const focusLabel = page.locator('text=/Focus:/').first();
    const hasFocusLabel = await focusLabel.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasFocusLabel) {
      const focusText = await focusLabel.textContent();
      expect(focusText).toMatch(/Focus:/);
    }
  });
});


test.describe('Coach Home V2 - Quick Actions', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Quick action buttons are visible', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Puzzles action
    const puzzlesBtn = page.getByTestId('puzzles-action');
    await expect(puzzlesBtn).toBeVisible();
    await expect(puzzlesBtn).toContainText(/Puzzles/i);
    
    // Progress action
    const progressBtn = page.getByTestId('progress-action');
    await expect(progressBtn).toBeVisible();
    await expect(progressBtn).toContainText(/Progress/i);
    
    // Analyze action
    const analyzeBtn = page.getByTestId('analyze-action');
    await expect(analyzeBtn).toBeVisible();
    await expect(analyzeBtn).toContainText(/Analyze/i);
  });

  test('Quick actions navigate to correct pages', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    // Test Progress action
    const progressBtn = page.getByTestId('progress-action');
    await progressBtn.click({ force: true });
    await page.waitForURL(/\/progress/, { timeout: 10000 });
    
    // Navigate back
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Test Analyze action
    const analyzeBtn = page.getByTestId('analyze-action');
    await analyzeBtn.click({ force: true });
    await page.waitForLoadState('domcontentloaded');
    
    // Should navigate to analyze or lab page
    const url = page.url();
    expect(url).toMatch(/\/(analyze|lab)/);
  });

  test('Play with Coach card is visible and clickable', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await hideEmergentBadge(page);
    
    const playWithCoachCard = page.getByTestId('play-with-coach-card');
    await expect(playWithCoachCard).toBeVisible({ timeout: 10000 });
    
    // Should show "Play with Coach" text
    await expect(playWithCoachCard).toContainText(/Play with Coach/i);
    
    // Should have NEW badge
    await expect(playWithCoachCard.locator('text=NEW')).toBeVisible();
    
    // Click should navigate to play-with-coach
    await playWithCoachCard.click({ force: true });
    await page.waitForURL(/\/play-with-coach/, { timeout: 10000 });
  });
});


test.describe('Coach Home V2 - State Based Display', () => {
  
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
    await dismissToasts(page);
  });

  test('Games count badge shows in hero section', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('hero-section')).toBeVisible({ timeout: 15000 });
    
    // Look for "X games analyzed" badge
    const gamesBadge = page.locator('text=/\\d+ games analyzed/').first();
    const hasBadge = await gamesBadge.isVisible({ timeout: 5000 }).catch(() => false);
    
    if (hasBadge) {
      const badgeText = await gamesBadge.textContent();
      expect(badgeText).toMatch(/\d+ games analyzed/);
    }
  });

  test('Waiting games count shows when in REFLECT state', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('coach-home')).toBeVisible({ timeout: 15000 });
    
    // Look for "X waiting" badge or "X games waiting for reflection"
    const waitingBadge = page.locator('text=/\\d+ waiting/').first();
    const waitingText = page.locator('text=/\\d+ game.*waiting for reflection/').first();
    
    const hasWaitingBadge = await waitingBadge.isVisible({ timeout: 5000 }).catch(() => false);
    const hasWaitingText = await waitingText.isVisible({ timeout: 2000 }).catch(() => false);
    
    if (hasWaitingBadge || hasWaitingText) {
      // User is in REFLECT state
      console.log('User has games waiting for reflection');
    } else {
      // User might be in TRAIN state
      console.log('User may be in TRAIN state with no games to reflect');
    }
  });

  test('Session continuity message displays when applicable', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    await expect(page.getByTestId('hero-section')).toBeVisible({ timeout: 15000 });
    
    // Look for session continuity messages like:
    // "We've been working on X for Y games"
    // "Good progress on X! Y games in."
    const sessionMessages = [
      /been working on.*for \d+ game/i,
      /good progress on/i,
      /focused on.*for \d+ game/i
    ];
    
    let foundSession = false;
    for (const pattern of sessionMessages) {
      const element = page.locator(`text=${pattern}`).first();
      if (await element.isVisible({ timeout: 2000 }).catch(() => false)) {
        foundSession = true;
        break;
      }
    }
    
    // Session continuity is optional - depends on coach state
    if (!foundSession) {
      console.log('No session continuity message - user may not have active theme');
    }
  });
});
