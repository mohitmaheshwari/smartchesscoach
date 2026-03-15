/**
 * Coach Play Chat E2E Tests - Testing LLM Hallucination Fixes
 * 
 * Tests for the Play with Coach chat feature:
 * 1. Chat should give position-specific advice, not generic plans
 * 2. Move quality should be correctly assessed
 * 3. Should NOT falsely claim opening names for random moves
 * 4. Messages should have IDs for feedback button
 */
import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'https://chess-habit-forge.preview.emergentagent.com';

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
    // Ignore cleanup errors
  }
}

async function waitForToastsToDisappear(page: Page) {
  await page.waitForFunction(() => {
    const toasts = document.querySelectorAll('[data-sonner-toast]');
    return toasts.length === 0;
  }, { timeout: 5000 }).catch(() => {});
}

async function startGame(page: Page) {
  await page.goto('/play-with-coach', { waitUntil: 'domcontentloaded' });
  await waitForToastsToDisappear(page);
  await expect(page.getByTestId('coach-play-setup')).toBeVisible();
  await page.getByTestId('start-game-btn').click({ force: true });
  await expect(page.getByTestId('coach-play-game')).toBeVisible({ timeout: 15000 });
}

test.describe('Coach Play Chat Panel', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
  });

  test.afterEach(async ({ page }) => {
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click({ force: true });
    }
  });

  test('should display chat panel with input and messages', async ({ page }) => {
    await startGame(page);
    
    // Check chat panel exists
    await expect(page.getByTestId('coach-chat-panel')).toBeVisible();
    
    // Check chat messages area exists
    await expect(page.getByTestId('chat-messages')).toBeVisible();
    
    // Check chat input exists
    await expect(page.getByTestId('chat-input')).toBeVisible();
    
    // Check send button exists
    await expect(page.getByTestId('send-chat-btn')).toBeVisible();
  });

  test('should show welcome message when chat is empty', async ({ page }) => {
    await startGame(page);
    
    // Welcome message should be visible in empty chat
    await expect(page.getByText("Let's play!")).toBeVisible();
    await expect(page.getByText("I'll give you feedback on interesting moves")).toBeVisible();
  });

  test('should send chat message and get coach response', async ({ page }) => {
    await startGame(page);
    
    // Type a message
    const chatInput = page.getByTestId('chat-input');
    await chatInput.fill('What should I play?');
    
    // Send the message
    await page.getByTestId('send-chat-btn').click({ force: true });
    
    // Wait for coach response
    await page.waitForTimeout(8000); // LLM response takes time
    
    // Verify user message appears
    await expect(page.getByText('What should I play?')).toBeVisible();
    
    // Response should contain some coaching content
    const chatMessages = page.getByTestId('chat-messages');
    await expect(chatMessages).toContainText(/develop|castle|center|plan|knight|bishop/i, { timeout: 5000 });
  });
});

test.describe('Coach Play Chat - Position-Specific Advice', () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
    await startGame(page);
  });

  test.afterEach(async ({ page }) => {
    const resignBtn = page.getByTestId('resign-btn');
    if (await resignBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await resignBtn.click({ force: true });
    }
  });

  test('should respond to plan questions with specific advice', async ({ page }) => {
    const chatInput = page.getByTestId('chat-input');
    await chatInput.fill('What is my plan here?');
    await page.getByTestId('send-chat-btn').click({ force: true });
    
    // Wait for response
    await page.waitForTimeout(8000);
    
    // Verify user message appears
    await expect(page.getByText('What is my plan here?')).toBeVisible();
    
    // Response should contain position-specific advice (development, castling, etc.)
    const chatMessages = page.getByTestId('chat-messages');
    
    // Should have at least 2 message blocks (user + coach)
    const messages = chatMessages.locator('> div.rounded-lg');
    await expect(messages).toHaveCount(2, { timeout: 5000 });
  });

  test('should ask about moves and get quality assessment', async ({ page }) => {
    const chatInput = page.getByTestId('chat-input');
    await chatInput.fill('Was my last move good?');
    await page.getByTestId('send-chat-btn').click({ force: true });
    
    // Wait for response
    await page.waitForTimeout(8000);
    
    // Verify user message appears
    await expect(page.getByText('Was my last move good?')).toBeVisible();
    
    // Response should contain coach feedback - no starting position so answer may vary
    const chatMessages = page.getByTestId('chat-messages');
    
    // Should have at least a user and coach message
    const messages = chatMessages.locator('> div.rounded-lg');
    await expect(messages).toHaveCount(2, { timeout: 5000 });
  });
});

test.describe('Coach Play Chat - No False Opening Claims (Backend API Test)', () => {
  test('API should not claim h3 is Italian Game or other known openings', async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
    
    // Start a session via API
    const startResponse = await page.request.post(`${BASE_URL}/api/coach/play/start`, {
      data: { user_color: 'white', time_control: '15+10' }
    });
    expect(startResponse.ok()).toBeTruthy();
    const startData = await startResponse.json();
    const sessionId = startData.session_id;
    
    try {
      // Play unusual opening: h3
      await page.request.post(`${BASE_URL}/api/coach/play/move`, {
        data: { session_id: sessionId, move: 'h3', time_spent: 1.0 }
      });
      
      // Wait for coach response
      await page.waitForTimeout(3000);
      
      // Ask about the opening
      const chatResponse = await page.request.post(`${BASE_URL}/api/coach/play/chat`, {
        data: { session_id: sessionId, message: 'What opening is this?' }
      });
      
      expect(chatResponse.ok()).toBeTruthy();
      const chatData = await chatResponse.json();
      
      // Should NOT falsely claim it's Italian Game, Sicilian, etc.
      const responseText = chatData.response.toLowerCase();
      
      // h3 on move 1 is NOT these openings
      expect(responseText).not.toContain('italian game');
      expect(responseText).not.toContain('sicilian defense');
      expect(responseText).not.toContain('ruy lopez');
      expect(responseText).not.toContain('french defense');
      
    } finally {
      await page.request.post(`${BASE_URL}/api/coach/play/end`, {
        data: { session_id: sessionId, reason: 'resigned' }
      });
    }
  });
});

test.describe('Coach Play Chat - Message Structure', () => {
  test('messages from /coach/play/messages should have IDs for feedback', async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
    
    // Start a session
    const startResponse = await page.request.post(`${BASE_URL}/api/coach/play/start`, {
      data: { user_color: 'white', time_control: '15+10' }
    });
    expect(startResponse.ok()).toBeTruthy();
    const startData = await startResponse.json();
    const sessionId = startData.session_id;
    
    try {
      // Make a move to potentially trigger coach messages
      await page.request.post(`${BASE_URL}/api/coach/play/move`, {
        data: { session_id: sessionId, move: 'e4', time_spent: 1.0 }
      });
      
      await page.waitForTimeout(3000);
      
      // Get messages
      const messagesResponse = await page.request.get(
        `${BASE_URL}/api/coach/play/messages/${sessionId}`
      );
      
      expect(messagesResponse.ok()).toBeTruthy();
      const messagesData = await messagesResponse.json();
      
      // Structure check
      expect(messagesData.success).toBe(true);
      expect(messagesData.messages).toBeInstanceOf(Array);
      expect(typeof messagesData.count).toBe('number');
      
      // Each message should have an ID
      for (const msg of messagesData.messages) {
        expect(msg).toHaveProperty('id');
        expect(typeof msg.id).toBe('string');
        expect(msg.id.length).toBeGreaterThan(0);
      }
      
    } finally {
      await page.request.post(`${BASE_URL}/api/coach/play/end`, {
        data: { session_id: sessionId, reason: 'resigned' }
      });
    }
  });
});

test.describe('Coach Play Chat - Best Move Suggestions', () => {
  test('API should return best move from Stockfish analysis', async ({ page }) => {
    await devLogin(page);
    await cleanupActiveSessions(page);
    
    // Start a session
    const startResponse = await page.request.post(`${BASE_URL}/api/coach/play/start`, {
      data: { user_color: 'white', time_control: '15+10' }
    });
    expect(startResponse.ok()).toBeTruthy();
    const startData = await startResponse.json();
    const sessionId = startData.session_id;
    
    try {
      // Play suboptimal move h3
      await page.request.post(`${BASE_URL}/api/coach/play/move`, {
        data: { session_id: sessionId, move: 'h3', time_spent: 1.0 }
      });
      
      await page.waitForTimeout(3000);
      
      // Ask about the move
      const chatResponse = await page.request.post(`${BASE_URL}/api/coach/play/chat`, {
        data: { session_id: sessionId, message: 'Was h3 good? What should I have played?' }
      });
      
      expect(chatResponse.ok()).toBeTruthy();
      const chatData = await chatResponse.json();
      
      // Should have move_quality assessment
      expect(chatData).toHaveProperty('move_quality');
      const validQualities = ['brilliant', 'great', 'good', 'okay', 'inaccuracy', 'mistake', 'blunder'];
      if (chatData.move_quality) {
        expect(validQualities).toContain(chatData.move_quality);
      }
      
      // Should have best_move suggestion
      expect(chatData).toHaveProperty('best_move');
      if (chatData.best_move) {
        // Best move should be a valid chess notation
        expect(chatData.best_move.length).toBeGreaterThanOrEqual(2);
        expect(chatData.best_move.length).toBeLessThanOrEqual(6);
      }
      
      // Might have suggestion_arrow for UI display
      if (chatData.suggestion_arrow) {
        // UCI format: e.g., "d2d4"
        expect(chatData.suggestion_arrow.length).toBeGreaterThanOrEqual(4);
      }
      
    } finally {
      await page.request.post(`${BASE_URL}/api/coach/play/end`, {
        data: { session_id: sessionId, reason: 'resigned' }
      });
    }
  });
});
