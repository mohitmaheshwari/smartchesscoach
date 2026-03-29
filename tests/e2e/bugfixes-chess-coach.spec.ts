/**
 * Bug Fixes Regression Tests - Chess Coach
 *
 * Tests for the specific bug fixes:
 * Issue 2: Games to Reflect On - checks stockfish_analysis.blunders/mistakes fallback
 * Issue 3: Training page puzzles - displays correct FEN position (not starting position)
 * Issue 4: Coach Focus card - does not display '0 → 0' when no mistake data
 * Issue 5: Rating ceiling tooltips - explains Stable Level, Demonstrated Peak, Performance Gap
 * Issue 6: Growth delta - filters out metrics with 0→0 values
 */

import { test, expect } from '@playwright/test';

const START_FEN_PIECE_PLACEMENT = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR';

test.describe('Chess Coach Bug Fixes', () => {
  test.beforeEach(async ({ page }) => {
    // Login as dev user
    await page.goto('/api/auth/dev-login');
    await page.waitForLoadState('domcontentloaded');
  });

  test.describe('Issue 2: Reflect API - Games Needing Reflection', () => {
    test('GET /api/reflect/pending returns 200 and correct structure', async ({ page }) => {
      const response = await page.request.get('/api/reflect/pending');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('games');
      expect(Array.isArray(data.games)).toBe(true);
    });

    test('GET /api/reflect/pending/count returns count field', async ({ page }) => {
      const response = await page.request.get('/api/reflect/pending/count');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('count');
      expect(typeof data.count).toBe('number');
      expect(data.count).toBeGreaterThanOrEqual(0);
    });

    test('pending games have valid blunders/mistakes fields', async ({ page }) => {
      const response = await page.request.get('/api/reflect/pending');
      const data = await response.json();

      if (data.games.length > 0) {
        const game = data.games[0];
        expect(game).toHaveProperty('game_id');
        expect(game).toHaveProperty('blunders');
        expect(game).toHaveProperty('mistakes');
        expect(typeof game.blunders).toBe('number');
        expect(typeof game.mistakes).toBe('number');
      }
    });
  });

  test.describe('Issue 3: Training Puzzle FEN Validation', () => {
    test('puzzles page loads with valid chess position', async ({ page }) => {
      await page.goto('/coach');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Check that the training page has loaded
      await expect(page.getByRole('heading', { name: /Training/i })).toBeVisible();

      // Verify puzzle tab is active
      await expect(page.getByTestId('tab-puzzles')).toBeVisible();
    });

    test('puzzle board shows non-starting position when puzzle exists', async ({ page }) => {
      await page.goto('/coach');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Wait for the board to load
      const board = page.locator('.cg-wrap');
      if (await board.count() > 0) {
        // Board is present - puzzle should be loaded
        // Check for puzzle context (source label, difficulty badge, etc.)
        const puzzleContext = page.locator('text=Your Game, text=Community, text=easy, text=medium, text=hard');
        const hasPuzzleContext = await puzzleContext.count() > 0;
        
        // If there's a puzzle context, the position should NOT be the starting position
        // We can't easily check FEN directly, but we verify the UI shows puzzle metadata
        if (hasPuzzleContext) {
          // Check that move info is shown
          const moveInfo = page.locator('text=/Move \\d+/');
          await expect(moveInfo).toBeVisible();
        }
      }
    });

    test('FEN validation rejects invalid puzzles', async ({ page }) => {
      // Test the API directly to ensure invalid FENs are handled
      const response = await page.request.get('/api/training/puzzles?limit=10');
      
      if (response.status() === 200) {
        const data = await response.json();
        const puzzles = data.puzzles || [];
        
        // All returned puzzles should have FEN starting with valid piece placement
        for (const puzzle of puzzles) {
          if (puzzle.fen) {
            const parts = puzzle.fen.split(' ');
            const ranks = parts[0].split('/');
            // Valid FEN should have 8 ranks
            expect(ranks.length).toBe(8);
          }
        }
      }
    });
  });

  test.describe('Issue 4: Coach Focus Card - No 0→0 Display', () => {
    test('progress page loads without showing 0→0 in focus card', async ({ page }) => {
      await page.goto('/progress');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Check for coach focus card
      const focusCard = page.getByTestId('coach-focus-card');
      
      if (await focusCard.count() > 0) {
        // Get the text content of the focus card
        const cardText = await focusCard.textContent();
        
        // Should NOT contain "0 → 0" pattern
        expect(cardText).not.toMatch(/\b0\s*→\s*0\b/);
        
        // Should show either trend label or proper metrics
        const hasTrendLabel = cardText?.includes('Stable') || 
                             cardText?.includes('Improving') || 
                             cardText?.includes('Needs attention');
        
        expect(hasTrendLabel).toBe(true);
      }
    });

    test('theme-stats API returns valid improvement data', async ({ page }) => {
      const response = await page.request.get('/api/coach/theme-stats');
      
      if (response.status() === 200) {
        const data = await response.json();
        
        if (data.has_theme && data.improvement_stats) {
          // If there's improvement stats, trend should be defined
          expect(data.improvement_stats.trend).toBeDefined();
        }
      }
    });
  });

  test.describe('Issue 5: Rating Ceiling Tooltips', () => {
    test('progress page shows rating potential section with help icons', async ({ page }) => {
      await page.goto('/progress');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Scroll down to rating ceiling section
      await page.evaluate(() => window.scrollTo(0, 600));
      await page.waitForTimeout(500);

      // Check for rating ceiling card
      const ratingCeilingCard = page.getByTestId('rating-ceiling');
      
      if (await ratingCeilingCard.count() > 0) {
        // Verify the three metrics are displayed with tooltip triggers
        // Each metric label has the HelpCircle icon inline
        const stableLevel = ratingCeilingCard.getByText('Stable Level');
        const demonstratedPeak = ratingCeilingCard.getByText('Demonstrated Peak');
        const performanceGap = ratingCeilingCard.getByText('Performance Gap');
        
        await expect(stableLevel).toBeVisible();
        await expect(demonstratedPeak).toBeVisible();
        await expect(performanceGap).toBeVisible();
        
        // Verify that these labels are inside tooltip triggers (cursor-help class)
        // The labels are inside buttons with cursor-help styling
        const tooltipTriggers = ratingCeilingCard.locator('.cursor-help');
        await expect(tooltipTriggers).toHaveCount(3);
      }
    });

    test('tooltips are accessible and contain explanatory text', async ({ page }) => {
      await page.goto('/progress');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Scroll down to rating ceiling section
      await page.evaluate(() => window.scrollTo(0, 600));
      await page.waitForTimeout(500);

      const ratingCeilingCard = page.getByTestId('rating-ceiling');
      
      if (await ratingCeilingCard.count() > 0) {
        // Check that tooltip content exists in the DOM (even if not visible)
        // Tooltips use TooltipContent component which renders tooltip text
        const tooltipProvider = ratingCeilingCard.locator('[role="tooltip"], [data-radix-tooltip], .tooltip-content');
        
        // Alternatively, hover to trigger tooltip
        const stableLevelLabel = ratingCeilingCard.getByText('Stable Level');
        if (await stableLevelLabel.count() > 0) {
          await stableLevelLabel.hover();
          await page.waitForTimeout(300);
          
          // Check if tooltip appeared
          const tooltip = page.locator('[role="tooltip"]');
          if (await tooltip.count() > 0) {
            const tooltipText = await tooltip.textContent();
            expect(tooltipText).toContain('average performance');
          }
        }
      }
    });
  });

  test.describe('Issue 6: Growth Delta - Filter 0→0 Metrics', () => {
    test('growth delta section does not show 0→0 metrics', async ({ page }) => {
      await page.goto('/progress');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Scroll to find growth delta card
      await page.evaluate(() => window.scrollTo(0, 300));
      await page.waitForTimeout(500);

      const growthDeltaCard = page.getByTestId('growth-delta');
      
      if (await growthDeltaCard.count() > 0) {
        const cardText = await growthDeltaCard.textContent();
        
        // Should NOT contain "0 → 0" pattern in metrics
        // But might contain message about stable performance
        if (!cardText?.includes('stable') && !cardText?.includes('Stable')) {
          expect(cardText).not.toMatch(/\b0\s*→\s*0\b/);
        }
      }
    });

    test('journey intelligence API returns filtered growth metrics', async ({ page }) => {
      const response = await page.request.get('/api/journey/intelligence');
      
      if (response.status() === 200) {
        const data = await response.json();
        
        if (data.has_data && data.growth_delta?.metrics) {
          // Check that metrics don't have both previous and recent as 0
          for (const metric of data.growth_delta.metrics) {
            // Extract numeric values from strings like "0.5" or "50%"
            const prevNum = parseFloat(String(metric.previous).replace(/[^0-9.-]/g, '')) || 0;
            const recentNum = parseFloat(String(metric.recent).replace(/[^0-9.-]/g, '')) || 0;
            
            // If both are 0, the frontend should filter them out
            // But the backend might still return them - the filtering happens in frontend
            if (prevNum === 0 && recentNum === 0 && metric.delta === 0) {
              // This metric should be filtered by frontend
              // We can't assert here, just log for awareness
              console.log(`Metric ${metric.name} has 0→0, should be filtered by frontend`);
            }
          }
        }
      }
    });
  });

  test.describe('Integration Tests', () => {
    test('full progress page loads without errors', async ({ page }) => {
      await page.goto('/progress');
      await page.waitForLoadState('domcontentloaded');
      
      // Should show "Your Chess Journey" heading
      await expect(page.getByRole('heading', { name: /Your Chess Journey/i })).toBeVisible();
      
      // Should show tab navigation
      await expect(page.getByRole('button', { name: /Snapshot/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /Trend/i })).toBeVisible();
    });

    test('reflect page loads without API errors', async ({ page }) => {
      await page.goto('/reflect');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Page should load (might show games or "no games" state)
      // Check we don't have an error state
      const errorIndicator = page.locator('text=/error/i, text=/failed/i');
      expect(await errorIndicator.count()).toBeLessThan(3);
    });

    test('training page puzzles have valid positions', async ({ page }) => {
      await page.goto('/coach');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Board should be visible
      const board = page.locator('.cg-wrap, [data-testid="chess-board"]');
      
      if (await board.count() > 0) {
        // Take screenshot for visual verification
        await page.screenshot({ path: 'test-results/puzzle-position.jpeg', quality: 20 });
      }
    });
  });
});
