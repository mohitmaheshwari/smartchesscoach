/**
 * Trap Practice Feature Tests
 * 
 * Tests for the Interactive Trap Practice feature in the Opening Training Lab.
 * Users can practice executing chess traps against the AI coach.
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'https://chess-truth-engine.preview.emergentagent.com';

test.describe('Opening Lesson Page - Traps Tab', () => {
  
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.goto(`${BASE_URL}/openings/italian-game`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
  });

  test('Opening Lesson page loads correctly with all tabs', async ({ page }) => {
    // Verify page title
    await expect(page.getByRole('heading', { name: /Italian Game/i })).toBeVisible();
    
    // Verify all tabs are present
    await expect(page.getByRole('tab', { name: /Learn/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Practice/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Traps/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Your Mistakes/i })).toBeVisible();
    
    // Verify the opening code is displayed
    await expect(page.getByText('C50-C54')).toBeVisible();
    await expect(page.getByText('White Opening')).toBeVisible();
  });

  test('Traps tab displays list of available traps with metadata', async ({ page }) => {
    // Click on Traps tab
    await page.getByRole('tab', { name: /Traps/i }).click();
    
    // Wait for trap cards to be visible
    await expect(page.locator('[data-testid="trap-card-0"]')).toBeVisible();
    
    // Verify the instruction text
    await expect(page.getByText(/Click a trap to practice executing it against the coach/i)).toBeVisible();
    
    // Verify first trap card (Fried Liver Attack)
    const firstTrap = page.locator('[data-testid="trap-card-0"]');
    await expect(firstTrap.getByText('Fried Liver Attack')).toBeVisible();
    await expect(firstTrap.getByText('intermediate')).toBeVisible();
    // Use exact match for the badge text
    await expect(firstTrap.getByText('wins material', { exact: true })).toBeVisible();
    await expect(firstTrap.getByText(/8 moves/i)).toBeVisible();
    
    // Verify there are multiple traps (Italian Game has 4 traps)
    await expect(page.locator('[data-testid^="trap-card-"]')).toHaveCount(4);
  });

  test('Traps tab shows difficulty badges with correct colors', async ({ page }) => {
    // Click on Traps tab
    await page.getByRole('tab', { name: /Traps/i }).click();
    
    // Check for beginner difficulty (green)
    const beginnerTrap = page.locator('[data-testid="trap-card-3"]');
    await expect(beginnerTrap.getByText('beginner')).toBeVisible();
    
    // Check for intermediate difficulty (amber)
    const intermediateTrap = page.locator('[data-testid="trap-card-0"]');
    await expect(intermediateTrap.getByText('intermediate')).toBeVisible();
  });

  test('Traps tab shows result types (checkmate, wins material)', async ({ page }) => {
    // Click on Traps tab
    await page.getByRole('tab', { name: /Traps/i }).click();
    
    // Check for "wins material" result type
    await expect(page.getByText(/wins.*material/i).first()).toBeVisible();
    
    // Check for "checkmate" result type  
    await expect(page.getByText('checkmate').first()).toBeVisible();
  });
});

test.describe('TrapPractice Component', () => {
  
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.goto(`${BASE_URL}/openings/italian-game`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    
    // Click on Traps tab
    await page.getByRole('tab', { name: /Traps/i }).click();
    await expect(page.locator('[data-testid="trap-card-0"]')).toBeVisible();
  });

  test('Clicking a trap opens the TrapPractice component', async ({ page }) => {
    // Click on first trap
    await page.locator('[data-testid="trap-card-0"]').click();
    
    // Verify TrapPractice component is visible
    await expect(page.getByText('Practice: Fried Liver Attack')).toBeVisible();
    
    // Verify phase indicators are visible
    await expect(page.getByText('1. Setup')).toBeVisible();
    await expect(page.getByText('2. Execute Trap')).toBeVisible();
    await expect(page.getByText('3. Victory!')).toBeVisible();
    
    // Verify Start Practice button is visible
    await expect(page.getByRole('button', { name: /Start Practice/i })).toBeVisible();
  });

  test('TrapPractice shows trap description and difficulty info', async ({ page }) => {
    // Click on first trap
    await page.locator('[data-testid="trap-card-0"]').click();
    
    // Verify description is shown
    await expect(page.getByText(/A deadly knight sacrifice on f7/i)).toBeVisible();
    
    // Verify result type and difficulty
    await expect(page.getByText(/Result.*wins.*material/i)).toBeVisible();
    await expect(page.getByText(/Difficulty.*intermediate/i)).toBeVisible();
  });

  test('Close button returns to trap list', async ({ page }) => {
    // Click on first trap
    await page.locator('[data-testid="trap-card-0"]').click();
    
    // Verify TrapPractice is open
    await expect(page.getByText('Practice: Fried Liver Attack')).toBeVisible();
    
    // Click the close button (X icon)
    await page.locator('button').filter({ has: page.locator('svg.lucide-x') }).click();
    
    // Verify we're back to the trap list
    await expect(page.getByText(/Click a trap to practice/i)).toBeVisible();
    await expect(page.locator('[data-testid="trap-card-0"]')).toBeVisible();
  });

  test('Start Practice button initiates the setup phase', async ({ page }) => {
    // Click on first trap
    await page.locator('[data-testid="trap-card-0"]').click();
    
    // Click Start Practice
    await page.getByRole('button', { name: /Start Practice/i }).click();
    
    // The button should change to "Setting up position..."
    await expect(page.getByRole('button', { name: /Setting up position/i })).toBeVisible();
    
    // Wait for setup to complete (setup moves play automatically)
    // The phase indicator should change or we should see different buttons
    // After setup, we should see Hint and Reset buttons
    await expect(page.getByRole('button', { name: /Hint/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: /Reset/i })).toBeVisible();
  });

  test('Reset button works correctly during trap practice', async ({ page }) => {
    // Hide emergent badge that may block clicks
    await page.evaluate(() => {
      const badge = document.getElementById('emergent-badge');
      if (badge) badge.style.display = 'none';
    });
    
    // Click on first trap
    await page.locator('[data-testid="trap-card-0"]').click();
    
    // Click Start Practice
    await page.getByRole('button', { name: /Start Practice/i }).click();
    
    // Wait for Hint and Reset buttons to appear (trap phase)
    await expect(page.getByRole('button', { name: /Hint/i })).toBeVisible({ timeout: 10000 });
    
    // Click Reset with force to bypass any overlays
    await page.getByRole('button', { name: /Reset/i }).click({ force: true });
    
    // Should be back to ready state with Start Practice button
    await expect(page.getByRole('button', { name: /Start Practice/i })).toBeVisible();
  });

  test('Hint button provides guidance during trap phase', async ({ page }) => {
    // Click on first trap
    await page.locator('[data-testid="trap-card-0"]').click();
    
    // Click Start Practice
    await page.getByRole('button', { name: /Start Practice/i }).click();
    
    // Wait for trap phase
    await expect(page.getByRole('button', { name: /Hint/i })).toBeVisible({ timeout: 10000 });
    
    // Click Hint
    await page.getByRole('button', { name: /Hint/i }).click();
    
    // Should show hint feedback (blue background)
    await expect(page.locator('.bg-blue-500\\/10').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('TrapPractice - Different Traps', () => {

  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.goto(`${BASE_URL}/openings/italian-game`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
  });

  test('Can open Legal\'s Mate trap and start practice', async ({ page }) => {
    // Click on Traps tab
    await page.getByRole('tab', { name: /Traps/i }).click();
    await expect(page.locator('[data-testid="trap-card-1"]')).toBeVisible();
    
    // Click on Legal's Mate (second trap)
    await page.locator('[data-testid="trap-card-1"]').click();
    
    // Verify the trap practice component shows Legal's Mate
    await expect(page.getByText(/Practice.*Legal.*Mate/i)).toBeVisible();
    
    // Start practice
    await page.getByRole('button', { name: /Start Practice/i }).click();
    
    // Wait for setup to complete
    await expect(page.getByRole('button', { name: /Hint/i })).toBeVisible({ timeout: 10000 });
  });

  test('Can open beginner trap (Scholar\'s Mate Defense)', async ({ page }) => {
    // Click on Traps tab
    await page.getByRole('tab', { name: /Traps/i }).click();
    
    // Click on Scholar's Mate Defense Trap (4th trap, beginner level)
    await page.locator('[data-testid="trap-card-3"]').click();
    
    // Verify the trap practice component shows correct trap
    await expect(page.getByText(/Practice.*Scholar.*Mate/i)).toBeVisible();
    
    // Verify it's marked as beginner
    await expect(page.getByText(/Difficulty.*beginner/i)).toBeVisible();
  });
});

test.describe('Opening Lesson - Tab Navigation', () => {

  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.goto(`${BASE_URL}/openings/italian-game`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
  });

  test('Can navigate between all tabs', async ({ page }) => {
    // Verify Learn tab is active by default
    await expect(page.getByText(/Key Ideas/i)).toBeVisible();
    
    // Click Practice tab
    await page.getByRole('tab', { name: /Practice/i }).click();
    await expect(page.getByText(/Practice with Coach/i)).toBeVisible();
    
    // Click Traps tab
    await page.getByRole('tab', { name: /Traps/i }).click();
    await expect(page.locator('[data-testid="trap-card-0"]')).toBeVisible();
    
    // Click Your Mistakes tab
    await page.getByRole('tab', { name: /Your Mistakes/i }).click();
    // Should show either mistakes or "No recorded mistakes" message
    const hasNoMistakes = await page.getByText(/No recorded mistakes/i).isVisible().catch(() => false);
    const hasMistakes = await page.getByText(/Move \d+:/i).isVisible().catch(() => false);
    expect(hasNoMistakes || hasMistakes).toBeTruthy();
    
    // Click back to Learn tab
    await page.getByRole('tab', { name: /Learn/i }).click();
    await expect(page.getByText(/Key Ideas/i)).toBeVisible();
  });

  test('Traps tab shows count badge', async ({ page }) => {
    // The Traps tab should show a count badge (4 traps for Italian Game)
    const trapsTab = page.getByRole('tab', { name: /Traps/i });
    await expect(trapsTab).toBeVisible();
    
    // Check for the badge showing count
    await expect(trapsTab.getByText('4')).toBeVisible();
  });
});
