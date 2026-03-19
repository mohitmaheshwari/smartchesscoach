import { test, expect } from '@playwright/test';

/**
 * Pre-Move Checklist Tests
 * 
 * Tests for the PreMoveChecklist component in Play with Coach page.
 * This component shows contextual prompts before each move to reinforce
 * good thinking habits.
 */

test.describe('Pre-Move Checklist', () => {
  test.beforeEach(async ({ page }) => {
    // Login via dev endpoint
    await page.goto('/api/auth/dev-login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
  });

  test('Pre-Move Checklist expand button is visible in Play with Coach', async ({ page }) => {
    // Navigate to Play with Coach via dashboard
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    
    // Click Play with Coach
    await page.getByText('Play with Coach').click();
    await page.waitForTimeout(2500);
    
    // Look for the Pre-Move Checklist expand button or expanded state
    const expandButton = page.getByTestId('pre-move-checklist-expand');
    const expandedChecklist = page.getByTestId('pre-move-checklist');
    
    // Either the expand button or expanded checklist should be visible
    const hasExpandButton = await expandButton.isVisible().catch(() => false);
    const hasExpandedChecklist = await expandedChecklist.isVisible().catch(() => false);
    
    expect(hasExpandButton || hasExpandedChecklist).toBeTruthy();
  });

  test('Pre-Move Checklist expands when clicked', async ({ page }) => {
    // Navigate to Play with Coach
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.getByText('Play with Coach').click();
    await page.waitForTimeout(2500);
    
    // Click expand button if visible
    const expandButton = page.getByTestId('pre-move-checklist-expand');
    if (await expandButton.isVisible().catch(() => false)) {
      await expandButton.click();
      await page.waitForTimeout(500);
    }
    
    // The expanded checklist should be visible
    await expect(page.getByTestId('pre-move-checklist')).toBeVisible();
    
    // Should show "Before You Move" header
    await expect(page.getByText('Before You Move')).toBeVisible();
  });

  test('Pre-Move Checklist shows contextual checklist items', async ({ page }) => {
    // Navigate to Play with Coach
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.getByText('Play with Coach').click();
    await page.waitForTimeout(2500);
    
    // Expand checklist
    const expandButton = page.getByTestId('pre-move-checklist-expand');
    if (await expandButton.isVisible().catch(() => false)) {
      await expandButton.click();
      await page.waitForTimeout(500);
    }
    
    // Verify checklist items are displayed
    // In opening phase (move 1), should show development or center questions
    const developmentCheck = page.getByText(/piece I haven't developed/i);
    const centerCheck = page.getByText(/fighting for the center/i);
    const threatCheck = page.getByText(/opponent threatening/i);
    
    // At least one checklist item should be visible
    const hasDevelopment = await developmentCheck.isVisible().catch(() => false);
    const hasCenter = await centerCheck.isVisible().catch(() => false);
    const hasThreat = await threatCheck.isVisible().catch(() => false);
    
    expect(hasDevelopment || hasCenter || hasThreat).toBeTruthy();
  });

  test('Pre-Move Checklist items can be checked', async ({ page }) => {
    // Navigate to Play with Coach
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.getByText('Play with Coach').click();
    await page.waitForTimeout(2500);
    
    // Expand checklist
    const expandButton = page.getByTestId('pre-move-checklist-expand');
    if (await expandButton.isVisible().catch(() => false)) {
      await expandButton.click();
      await page.waitForTimeout(500);
    }
    
    // Find a checklist item and click it
    const checklistItems = page.locator('[data-testid^="checklist-item-"]');
    const count = await checklistItems.count();
    
    expect(count).toBeGreaterThan(0);
    
    // Click first item
    if (count > 0) {
      await checklistItems.first().click();
      await page.waitForTimeout(300);
      
      // The item should show checked state (green background or checkmark)
      // Look for green styling or CheckCircle2 icon visibility
      const firstItem = checklistItems.first();
      const classes = await firstItem.getAttribute('class');
      
      // After clicking, it should have green styling
      expect(classes).toContain('green');
    }
  });

  test('Pre-Move Checklist can be collapsed', async ({ page }) => {
    // Navigate to Play with Coach
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.getByText('Play with Coach').click();
    await page.waitForTimeout(2500);
    
    // Expand checklist first
    const expandButton = page.getByTestId('pre-move-checklist-expand');
    if (await expandButton.isVisible().catch(() => false)) {
      await expandButton.click();
      await page.waitForTimeout(500);
    }
    
    // Find collapse button (ChevronUp)
    const collapseButton = page.locator('[data-testid="pre-move-checklist"] button').first();
    await collapseButton.click();
    await page.waitForTimeout(500);
    
    // The expand button should be visible again
    await expect(page.getByTestId('pre-move-checklist-expand')).toBeVisible();
  });

  test('Pre-Move Checklist shows all items checked message', async ({ page }) => {
    // Navigate to Play with Coach
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.getByText('Play with Coach').click();
    await page.waitForTimeout(2500);
    
    // Expand checklist
    const expandButton = page.getByTestId('pre-move-checklist-expand');
    if (await expandButton.isVisible().catch(() => false)) {
      await expandButton.click();
      await page.waitForTimeout(500);
    }
    
    // Click all checklist items
    const checklistItems = page.locator('[data-testid^="checklist-item-"]');
    const count = await checklistItems.count();
    
    for (let i = 0; i < count; i++) {
      await checklistItems.nth(i).click();
      await page.waitForTimeout(200);
    }
    
    // Should show "Good thinking" message
    await expect(page.getByText(/Good thinking/i)).toBeVisible();
  });
});


test.describe('Thinking Coach API Integration', () => {
  test('Pre-move checklist API returns valid data', async ({ request }) => {
    // Login first
    const loginRes = await request.get('/api/auth/dev-login');
    expect(loginRes.ok()).toBeTruthy();
    
    // Call the pre-move checklist endpoint
    const res = await request.get('/api/thinking-coach/pre-move-checklist', {
      params: {
        move_number: 5,
        has_castled: false,
        developed_pieces: 2
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    // Verify structure
    expect(data).toHaveProperty('checklist');
    expect(data).toHaveProperty('player_weaknesses');
    expect(Array.isArray(data.checklist)).toBeTruthy();
    
    // Should have items
    expect(data.checklist.length).toBeGreaterThan(0);
    
    // Each item should have required fields
    for (const item of data.checklist) {
      expect(item).toHaveProperty('id');
      expect(item).toHaveProperty('question');
      expect(item).toHaveProperty('priority');
      expect(item).toHaveProperty('explanation');
    }
  });

  test('Thinking coach walkthrough API works', async ({ request }) => {
    const res = await request.post('/api/thinking-coach/walkthrough', {
      data: {
        fen: 'rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2',
        best_move: 'e5'
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    expect(data).toHaveProperty('phase');
    expect(data).toHaveProperty('walkthrough');
    expect(data).toHaveProperty('conclusion');
    expect(data.phase).toBe('opening');
  });

  test('Thinking coach principle feedback API works', async ({ request }) => {
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
    
    expect(data).toHaveProperty('principle');
    expect(data).toHaveProperty('thinking_habit');
    expect(data.principle).toBe('Safety First');
  });

  test('Thinking coach behavioral intervention API works', async ({ request }) => {
    const res = await request.post('/api/thinking-coach/behavioral-intervention', {
      data: {
        behavioral_pattern: 'hope_chess'
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    expect(data).toHaveProperty('pattern');
    expect(data).toHaveProperty('diagnosis');
    expect(data).toHaveProperty('intervention');
    expect(data.pattern).toBe('hope_chess');
  });

  test('Thinking coach mindset prompt API works', async ({ request }) => {
    const res = await request.post('/api/thinking-coach/mindset-prompt', {
      data: {
        fen: 'rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2'
      }
    });
    
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    
    expect(data).toHaveProperty('fen');
    expect(data).toHaveProperty('prompts');
    expect(data).toHaveProperty('recommended_thinking_time');
    expect(Array.isArray(data.prompts)).toBeTruthy();
  });
});
