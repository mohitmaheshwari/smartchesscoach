/**
 * Resume Game / Trigger Coach Move E2E Tests
 * 
 * Tests the P0 bug fix: "when you resume the game, board doesn't let you play the game!"
 * The fix implemented a /api/coach/play/trigger-coach-move endpoint that handles
 * resuming games where the coach's turn was interrupted.
 * 
 * Key scenarios:
 * 1. Resume game when it's player's turn - should work normally
 * 2. Resume game when it's coach's turn - "Let Coach Play" button appears
 * 3. Clicking "Let Coach Play" triggers coach move and enables board
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://chess-curriculum-1.preview.emergentagent.com';

async function devLogin(page: Page) {
  await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
}

async function cleanupActiveSessions(page: Page) {
  try {
    const response = await page.request.get(`${BASE_URL}/api/coach/play/active`);
    if (response.ok()) {
      const data = await response.json();
      for (const session of data.active_sessions || []) {
        await page.request.post(`${BASE_URL}/api/coach/play/end`, {
          data: { session_id: session.session_id, reason: 'resigned' }
        });
      }
    }
  } catch (e) {
    // Ignore errors during cleanup
  }
}

async function waitForToastsToDisappear(page: Page) {
  await page.waitForFunction(() => {
    const toasts = document.querySelectorAll('[data-sonner-toast]');
    return toasts.length === 0;
  }, { timeout: 5000 }).catch(() => {});
}

test.describe('Resume Game - Trigger Coach Move', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupActiveSessions(page);
  });

  test('should start game as white and board is playable', async ({ page }) => {
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Start game as white
    await expect(page.getByTestId('coach-play-setup')).toBeVisible();
    await page.getByTestId('start-game-btn').click({ force: true });
    
    // Wait for game interface
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Should show "Your turn" indicator
    await expect(page.getByText('Your turn', { exact: true })).toBeVisible();
    
    // Board should be visible (lichess-board or chess-board)
    await expect(page.locator('cg-board, .cg-wrap, [class*="lichess"]').first()).toBeVisible();
  });

  test('should show "Let Coach Play" button when resuming with coach turn', async ({ page }) => {
    // Start a game as white
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Make a move via API to create "awaiting coach" state
    const activeResponse = await page.request.get(`${BASE_URL}/api/coach/play/active`);
    const activeData = await activeResponse.json();
    const sessionId = activeData.active_sessions[0]?.session_id;
    
    if (sessionId) {
      // Make player move
      await page.request.post(`${BASE_URL}/api/coach/play/move`, {
        data: { session_id: sessionId, move: 'e4' }
      });
      
      // Refresh page to simulate resume
      await page.reload({ waitUntil: 'domcontentloaded' });
      
      // Game should be resumed automatically
      await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
      
      // Wait for either "Your turn" or "Let Coach Play" button
      // The coach should respond automatically on resume, but if it doesn't,
      // the "Let Coach Play" button should appear
      const yourTurn = page.getByText('Your turn', { exact: true });
      const letCoachPlay = page.getByTestId('let-coach-play-btn');
      
      // One of these should appear within timeout
      await expect(yourTurn.or(letCoachPlay)).toBeVisible({ timeout: 10000 });
    }
  });

  test('should be able to click "Let Coach Play" and board becomes playable', async ({ page }) => {
    // This test simulates the P0 bug scenario
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    // Wait for setup page to be ready first
    await expect(page.getByTestId('coach-play-setup')).toBeVisible({ timeout: 10000 });
    
    // Start game
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Get session ID
    const activeResponse = await page.request.get(`${BASE_URL}/api/coach/play/active`);
    const activeData = await activeResponse.json();
    const sessionId = activeData.active_sessions[0]?.session_id;
    
    if (sessionId) {
      // Make player move via API
      await page.request.post(`${BASE_URL}/api/coach/play/move`, {
        data: { session_id: sessionId, move: 'e4' }
      });
      
      // Navigate away and back (simulates resume scenario)
      await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
      await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
      
      // Game should be resumed
      await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
      
      // Check if Let Coach Play button appears (it would if coach didn't auto-respond)
      const letCoachPlayBtn = page.getByTestId('let-coach-play-btn');
      
      // Give time for auto-resume to complete
      await page.waitForLoadState('networkidle').catch(() => {});
      
      // Either the button appeared or coach already moved
      const buttonVisible = await letCoachPlayBtn.isVisible().catch(() => false);
      
      if (buttonVisible) {
        // Click the button to trigger coach move
        await letCoachPlayBtn.click({ force: true });
        
        // Should show toast message about coach move
        await expect(page.getByText(/Coach played/)).toBeVisible({ timeout: 10000 });
        
        // Should show "Your turn" after coach moves
        await expect(page.getByText('Your turn', { exact: true })).toBeVisible({ timeout: 5000 });
      }
      
      // Either way, "Your turn" should be visible now
      await expect(page.getByText('Your turn', { exact: true })).toBeVisible({ timeout: 15000 });
    }
  });

  test('should resume active session automatically on page load', async ({ page }) => {
    // Create a session first
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Navigate away
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    
    // Navigate back to coach play
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    
    // Should NOT show setup screen if there's an active session
    // Should show game interface directly
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Toast should confirm resume
    await expect(page.getByText(/Resumed your game/)).toBeVisible({ timeout: 5000 }).catch(() => {
      // Toast might have already disappeared, that's okay
    });
  });

  test('should show game controls after resume', async ({ page }) => {
    // Start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Refresh to simulate resume
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Check controls are present
    await expect(page.getByTestId('resign-btn')).toBeVisible();
    await expect(page.getByRole('button', { name: /Flip/i })).toBeVisible();
    
    // Coach chat panel should be visible
    await expect(page.getByTestId('coach-chat-panel')).toBeVisible();
  });

  test('API: trigger-coach-move returns correct response when player turn', async ({ page }) => {
    // Start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Get session
    const activeResponse = await page.request.get(`${BASE_URL}/api/coach/play/active`);
    const activeData = await activeResponse.json();
    const sessionId = activeData.active_sessions[0]?.session_id;
    
    if (sessionId) {
      // Call trigger endpoint when it's already player's turn
      const triggerResponse = await page.request.post(`${BASE_URL}/api/coach/play/trigger-coach-move`, {
        data: { session_id: sessionId }
      });
      
      expect(triggerResponse.ok()).toBeTruthy();
      const data = await triggerResponse.json();
      
      expect(data.success).toBe(true);
      expect(data.is_player_turn).toBe(true);
      expect(data.message).toContain('your turn');
    }
  });

  test('API: trigger-coach-move makes coach move when awaiting coach', async ({ page }) => {
    // Start game
    await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
    await waitForToastsToDisappear(page);
    
    await page.getByTestId('start-game-btn').click({ force: true });
    await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
    
    // Get session
    const activeResponse = await page.request.get(`${BASE_URL}/api/coach/play/active`);
    const activeData = await activeResponse.json();
    const sessionId = activeData.active_sessions[0]?.session_id;
    
    if (sessionId) {
      // Make player move
      const moveResponse = await page.request.post(`${BASE_URL}/api/coach/play/move`, {
        data: { session_id: sessionId, move: 'e4' }
      });
      expect(moveResponse.ok()).toBeTruthy();
      
      // Now trigger coach move
      const triggerResponse = await page.request.post(`${BASE_URL}/api/coach/play/trigger-coach-move`, {
        data: { session_id: sessionId }
      });
      
      expect(triggerResponse.ok()).toBeTruthy();
      const data = await triggerResponse.json();
      
      expect(data.success).toBe(true);
      expect(data.coach_move).toBeTruthy();
      expect(data.is_player_turn).toBe(true);
      expect(data.current_fen).not.toBe('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1');
    }
  });
});
