import { test, expect } from '@playwright/test';

/**
 * Improvement Engine Tests - P1 Features
 * 
 * Tests for the Thinking Coach Improvement Engine features:
 * 1. ThoughtProcessWalkthrough - Shows step-by-step thinking in Moments tab
 * 2. PrincipleFeedback - Shows principle-based feedback in Summary tab
 * 3. BehavioralIntervention - Shows behavioral interventions in Summary tab
 * 4. Enhanced PreMoveChecklist - Personalized checks in Play with Coach
 * 
 * Uses game ID: 017161e5-cae3-47cb-89a3-9d774b16d2ca which has critical moments
 */

const GAME_ID = '017161e5-cae3-47cb-89a3-9d774b16d2ca';

test.describe('Improvement Engine - Thinking Coach Features', () => {
  
  test.beforeEach(async ({ page }) => {
    // Login via dev endpoint
    await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
  });

  test.describe('ThoughtProcessWalkthrough in Moments Tab', () => {
    
    test('ThoughtProcessWalkthrough button is visible in REVEAL stage', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Click on Moments tab
      await page.getByText('Moments', { exact: true }).click();
      await page.waitForTimeout(2000);
      
      // Click "Start Thinking" to go to THINKING stage
      const startThinkingBtn = page.getByTestId('continue-to-thinking-btn');
      if (await startThinkingBtn.isVisible()) {
        await startThinkingBtn.click();
        await page.waitForTimeout(1000);
      }
      
      // Click "Reveal" to go to REVEAL stage
      const revealBtn = page.getByTestId('reveal-btn');
      if (await revealBtn.isVisible()) {
        await revealBtn.click();
        await page.waitForTimeout(1500);
      }
      
      // Verify "How Should I Have Thought Here?" button is visible
      await expect(page.getByTestId('show-thought-process-btn')).toBeVisible();
      await expect(page.getByText('How Should I Have Thought Here?')).toBeVisible();
    });

    test('ThoughtProcessWalkthrough expands when button is clicked', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Navigate to REVEAL stage
      await page.getByText('Moments', { exact: true }).click();
      await page.waitForTimeout(2000);
      
      const startThinkingBtn = page.getByTestId('continue-to-thinking-btn');
      if (await startThinkingBtn.isVisible()) {
        await startThinkingBtn.click();
        await page.waitForTimeout(1000);
      }
      
      const revealBtn = page.getByTestId('reveal-btn');
      if (await revealBtn.isVisible()) {
        await revealBtn.click();
        await page.waitForTimeout(1500);
      }
      
      // Click "How Should I Have Thought Here?"
      await page.getByTestId('show-thought-process-btn').click();
      await page.waitForTimeout(2000);
      
      // Verify ThoughtProcessWalkthrough component is visible
      await expect(page.getByTestId('thought-process-walkthrough')).toBeVisible();
      await expect(page.getByText('How Strong Players Think')).toBeVisible();
    });

    test('ThoughtProcessWalkthrough shows thinking steps', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Navigate to REVEAL stage and show ThoughtProcessWalkthrough
      await page.getByText('Moments', { exact: true }).click();
      await page.waitForTimeout(2000);
      
      const startThinkingBtn = page.getByTestId('continue-to-thinking-btn');
      if (await startThinkingBtn.isVisible()) {
        await startThinkingBtn.click();
        await page.waitForTimeout(1000);
      }
      
      const revealBtn = page.getByTestId('reveal-btn');
      if (await revealBtn.isVisible()) {
        await revealBtn.click();
        await page.waitForTimeout(1500);
      }
      
      await page.getByTestId('show-thought-process-btn').click();
      await page.waitForTimeout(2500);
      
      // Verify thinking steps are visible
      // Should show phases like "Check Threats", "King Safety", etc.
      const checkThreats = page.getByText(/Check Threats|assess_threats/i);
      const kingSafety = page.getByText(/King Safety|check_king_safety/i);
      
      const hasCheckThreats = await checkThreats.isVisible().catch(() => false);
      const hasKingSafety = await kingSafety.isVisible().catch(() => false);
      
      expect(hasCheckThreats || hasKingSafety).toBeTruthy();
      
      // Verify first thinking step (step 0) is visible
      await expect(page.getByTestId('thinking-step-0')).toBeVisible();
    });
  });

  test.describe('PrincipleFeedback in Summary Tab', () => {
    
    test('PrincipleFeedback component is visible in Summary tab', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Summary tab should be visible by default
      await expect(page.getByText('Summary', { exact: true })).toBeVisible();
      
      // Look for PrincipleFeedback expand button or expanded card
      const principleExpandBtn = page.getByTestId('principle-feedback-expand');
      const principleCard = page.getByTestId('principle-feedback');
      
      const hasExpandBtn = await principleExpandBtn.isVisible().catch(() => false);
      const hasCard = await principleCard.isVisible().catch(() => false);
      
      expect(hasExpandBtn || hasCard).toBeTruthy();
    });

    test('PrincipleFeedback expands to show principle details', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Click expand button if visible
      const principleExpandBtn = page.getByTestId('principle-feedback-expand');
      if (await principleExpandBtn.isVisible()) {
        await principleExpandBtn.click();
        await page.waitForTimeout(1000);
      }
      
      // Verify PrincipleFeedback card is visible
      await expect(page.getByTestId('principle-feedback')).toBeVisible();
      
      // Should show "Fundamental Principle" text
      await expect(page.getByText('Fundamental Principle')).toBeVisible();
    });

    test('PrincipleFeedback shows principle name badge', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Expand PrincipleFeedback
      const principleExpandBtn = page.getByTestId('principle-feedback-expand');
      if (await principleExpandBtn.isVisible()) {
        await principleExpandBtn.click();
        await page.waitForTimeout(1000);
      }
      
      // Should show one of the principle names
      const possiblePrinciples = [
        'Safety First',
        'Checks, Captures, Threats',
        'Piece Activity',
        'Time Management',
        'Respect the Position',
        'Defense is Offense',
        'Develop with Purpose',
        'King Safety is Priority'
      ];
      
      let foundPrinciple = false;
      for (const principle of possiblePrinciples) {
        const isVisible = await page.getByText(principle).isVisible().catch(() => false);
        if (isVisible) {
          foundPrinciple = true;
          break;
        }
      }
      
      expect(foundPrinciple).toBeTruthy();
    });
  });

  test.describe('Game Summary Structure', () => {
    
    test('Summary tab shows Key Lesson section', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Verify Key Lesson is visible
      await expect(page.getByText('KEY LESSON')).toBeVisible();
    });

    test('Summary tab shows Game Story section', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Verify Game Story is visible
      await expect(page.getByText('GAME STORY')).toBeVisible();
    });

    test('Summary tab shows accuracy percentage', async ({ page }) => {
      // Navigate to Lab game page
      await page.goto(`/lab/game/${GAME_ID}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(3000);
      
      // Verify accuracy is shown
      await expect(page.getByText('Your accuracy')).toBeVisible();
      // Should show a percentage like 69%
      await expect(page.getByText(/%$/)).toBeVisible();
    });
  });
});


test.describe('Thinking Coach API Endpoints', () => {
  
  test('Walkthrough API returns valid structure', async ({ request }) => {
    const res = await request.post('/api/thinking-coach/walkthrough', {
      data: {
        fen: 'rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2',
        best_move: 'e5'
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // Verify required fields
    expect(data).toHaveProperty('phase');
    expect(data).toHaveProperty('focus');
    expect(data).toHaveProperty('walkthrough');
    expect(data).toHaveProperty('conclusion');
    expect(data).toHaveProperty('key_takeaway');
    
    // Verify phase is valid
    expect(['opening', 'middlegame', 'endgame']).toContain(data.phase);
    
    // Verify walkthrough is an array with steps
    expect(Array.isArray(data.walkthrough)).toBeTruthy();
    expect(data.walkthrough.length).toBeGreaterThan(0);
    
    // Each step should have phase, question, observation
    for (const step of data.walkthrough) {
      expect(step).toHaveProperty('phase');
      expect(step).toHaveProperty('question');
      expect(step).toHaveProperty('observation');
    }
  });

  test('Principle feedback API returns valid structure', async ({ request }) => {
    const res = await request.post('/api/thinking-coach/principle-feedback', {
      data: {
        mistake_type: 'hanging_piece',
        fen: 'rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2',
        move_played: 'Qh5',
        best_move: 'e5'
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // Verify required fields
    expect(data).toHaveProperty('principle');
    expect(data).toHaveProperty('explanation');
    expect(data).toHaveProperty('thinking_habit');
    expect(data).toHaveProperty('applied_to_position');
    expect(data).toHaveProperty('what_to_do_instead');
    
    // For hanging_piece mistake, principle should be "Safety First"
    expect(data.principle).toBe('Safety First');
  });

  test('Behavioral intervention API returns valid structure', async ({ request }) => {
    const res = await request.post('/api/thinking-coach/behavioral-intervention', {
      data: {
        behavioral_pattern: 'hope_chess'
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // Verify required fields
    expect(data).toHaveProperty('pattern');
    expect(data).toHaveProperty('diagnosis');
    expect(data).toHaveProperty('intervention');
    expect(data).toHaveProperty('practice_rule');
    
    expect(data.pattern).toBe('hope_chess');
    expect(data.diagnosis).toContain('opponent');
  });

  test('Mindset prompt API returns valid structure', async ({ request }) => {
    const res = await request.post('/api/thinking-coach/mindset-prompt', {
      data: {
        fen: 'rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2',
        position_characteristics: {
          back_rank_weakness: true
        }
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // Verify required fields
    expect(data).toHaveProperty('fen');
    expect(data).toHaveProperty('prompts');
    expect(data).toHaveProperty('recommended_thinking_time');
    
    // Prompts should be an array
    expect(Array.isArray(data.prompts)).toBeTruthy();
  });

  test('Pre-move checklist API returns valid structure', async ({ request }) => {
    const loginRes = await request.get('/api/auth/dev-login');
    expect(loginRes.ok()).toBeTruthy();
    
    const res = await request.get('/api/thinking-coach/pre-move-checklist', {
      params: {
        move_number: 5,
        has_castled: false,
        developed_pieces: 2
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // Verify required fields
    expect(data).toHaveProperty('checklist');
    expect(data).toHaveProperty('player_weaknesses');
    
    // Checklist should be an array
    expect(Array.isArray(data.checklist)).toBeTruthy();
    expect(data.checklist.length).toBeGreaterThan(0);
    expect(data.checklist.length).toBeLessThanOrEqual(3); // Limited to 3 items
    
    // Each item should have required fields
    for (const item of data.checklist) {
      expect(item).toHaveProperty('id');
      expect(item).toHaveProperty('question');
      expect(item).toHaveProperty('priority');
      expect(item).toHaveProperty('explanation');
    }
  });

  test('Pre-move checklist returns castling reminder at move 8+', async ({ request }) => {
    const loginRes = await request.get('/api/auth/dev-login');
    expect(loginRes.ok()).toBeTruthy();
    
    const res = await request.get('/api/thinking-coach/pre-move-checklist', {
      params: {
        move_number: 8,
        has_castled: false,
        developed_pieces: 4
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // At move 8 without castling, should have castle_check with high priority
    const castleCheck = data.checklist.find((item: any) => item.id === 'castle_check');
    expect(castleCheck).toBeTruthy();
    expect(castleCheck.priority).toBe('high');
  });

  test('Pre-move checklist prioritizes high priority items', async ({ request }) => {
    const loginRes = await request.get('/api/auth/dev-login');
    expect(loginRes.ok()).toBeTruthy();
    
    const res = await request.get('/api/thinking-coach/pre-move-checklist', {
      params: {
        move_number: 10,
        has_castled: false,
        developed_pieces: 2
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // First item should be high priority (castling at move 10 without castling)
    expect(data.checklist.length).toBeGreaterThan(0);
    
    // Check that items are sorted by priority (high first)
    const priorities = data.checklist.map((item: any) => item.priority);
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    
    for (let i = 0; i < priorities.length - 1; i++) {
      expect(priorityOrder[priorities[i] as keyof typeof priorityOrder])
        .toBeLessThanOrEqual(priorityOrder[priorities[i + 1] as keyof typeof priorityOrder]);
    }
  });
});
