import { test, expect } from '@playwright/test';
import { waitForAppReady, dismissToasts } from '../fixtures/helpers';

const BASE_URL = 'https://thinking-simulator.preview.emergentagent.com';

test.describe('HomePage Bug Fixes Verification', () => {
  
  test.beforeEach(async ({ page }) => {
    // Dev login first
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('networkidle');
    await dismissToasts(page);
  });

  test('All 4 sections render with correct data-testid attributes', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    
    // Wait for page to fully load
    await page.waitForLoadState('networkidle');
    
    // Verify all 4 sections are present
    await expect(page.getByTestId('biggest-weakness-card')).toBeVisible();
    await expect(page.getByTestId('improvement-tracker-card')).toBeVisible();
    await expect(page.getByTestId('training-task-card')).toBeVisible();
    await expect(page.getByTestId('reflection-games-card')).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-all-sections.jpeg', quality: 20 });
  });

  test('Progress Check shows empty state message when no analyzed_list data', async ({ page }) => {
    // Dev user has no data, so Progress Check should show empty state
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    // Progress Check section should show "Analyze more games" message
    const progressCard = page.getByTestId('improvement-tracker-card');
    await expect(progressCard).toBeVisible();
    
    // Verify empty state message (not "No patterns detected" which is wrong field)
    await expect(progressCard.getByText(/Analyze more games/)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-progress-empty.jpeg', quality: 20 });
  });

  test('Games to Reflect shows empty state when no reflection games', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    // Games to Reflect section should show empty state
    const reflectionCard = page.getByTestId('reflection-games-card');
    await expect(reflectionCard).toBeVisible();
    await expect(reflectionCard.getByText(/No games ready for reflection/)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-reflect-empty.jpeg', quality: 20 });
  });

  test('Today\'s Training shows default task when no weakness detected', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    const trainingCard = page.getByTestId('training-task-card');
    await expect(trainingCard).toBeVisible();
    
    // Default task should be "Practice Your Mistakes"
    await expect(trainingCard.getByText(/Practice Your Mistakes/)).toBeVisible();
    await expect(page.getByTestId('start-training-btn')).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-training-default.jpeg', quality: 20 });
  });

  test('Start Training button navigates to /lab', async ({ page }) => {
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    // Click Start Training button
    await page.getByTestId('start-training-btn').click();
    
    // Should navigate to /lab
    await expect(page).toHaveURL(/\/lab/);
    
    await page.screenshot({ path: '.screenshots/homepage-training-navigate.jpeg', quality: 20 });
  });

  test('BUG FIX: Progress Check uses analyzed_list (not analyzed_games) - with mock data', async ({ page }) => {
    // Mock the dashboard-stats API to return analyzed_list
    await page.route('**/api/dashboard-stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_games: 5,
          analyzed_games: 3,
          queued_games: 0,
          not_analyzed_games: 2,
          top_weaknesses: [],
          recent_games: [],
          analyzed_list: [
            {
              game_id: 'game_1',
              user_color: 'white',
              white_player: 'TestUser',
              black_player: 'Opponent1',
              opponent: 'Opponent1',
              blunders: 2,
              mistakes: 3,
              accuracy: 75.5,
              result: '1-0'
            },
            {
              game_id: 'game_2',
              user_color: 'black',
              white_player: 'Opponent2',
              black_player: 'TestUser',
              opponent: 'Opponent2',
              blunders: 1,
              mistakes: 2,
              accuracy: 82.3,
              result: '0-1'
            },
            {
              game_id: 'game_3',
              user_color: 'white',
              white_player: 'TestUser',
              black_player: 'Opponent3',
              opponent: 'Opponent3',
              blunders: 3,
              mistakes: 4,
              accuracy: 68.0,
              result: '0-1'
            }
          ],
          in_queue_list: [],
          not_analyzed_list: [],
          stats: {
            total_blunders: 6,
            total_mistakes: 9,
            total_best_moves: 0
          }
        })
      });
    });
    
    // Also mock reflect/pending to return empty
    await page.route('**/api/reflect/pending', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ games: [] })
      });
    });
    
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    const progressCard = page.getByTestId('improvement-tracker-card');
    await expect(progressCard).toBeVisible();
    
    // Should show game data, NOT "Analyze more games" empty state
    // Progress Check should display the games with blunder/mistake counts
    await expect(progressCard.getByText(/vs Opponent1/)).toBeVisible();
    await expect(progressCard.getByText(/vs Opponent2/)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-progress-with-data.jpeg', quality: 20 });
  });

  test('BUG FIX: Games to Reflect uses opponent_name from API - with mock data', async ({ page }) => {
    // Mock dashboard-stats to return empty analyzed_list
    await page.route('**/api/dashboard-stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_games: 0,
          analyzed_games: 0,
          queued_games: 0,
          not_analyzed_games: 0,
          top_weaknesses: [],
          recent_games: [],
          analyzed_list: [],
          in_queue_list: [],
          not_analyzed_list: [],
          stats: {}
        })
      });
    });
    
    // Mock reflect/pending to return games with opponent_name
    await page.route('**/api/reflect/pending', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          games: [
            {
              game_id: 'reflect_game_1',
              user_color: 'white',
              opponent_name: 'TestOpponent123',
              result: 'loss',
              blunders_count: 3
            },
            {
              game_id: 'reflect_game_2',
              user_color: 'black',
              opponent_name: 'AnotherPlayer456',
              result: 'win',
              blunders_count: 1
            }
          ]
        })
      });
    });
    
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    const reflectionCard = page.getByTestId('reflection-games-card');
    await expect(reflectionCard).toBeVisible();
    
    // Should display opponent_name from API (not generic "Opponent")
    await expect(reflectionCard.getByText(/vs TestOpponent123/)).toBeVisible();
    await expect(reflectionCard.getByText(/vs AnotherPlayer456/)).toBeVisible();
    
    // Game cards should be visible
    await expect(page.getByTestId('reflection-game-0')).toBeVisible();
    await expect(page.getByTestId('reflection-game-1')).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-reflect-with-opponents.jpeg', quality: 20 });
  });

  test('BUG FIX: Fallback to analyzed_list when no reflection games - with mock data', async ({ page }) => {
    // Mock dashboard-stats to return analyzed_list (used as fallback)
    await page.route('**/api/dashboard-stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_games: 2,
          analyzed_games: 2,
          queued_games: 0,
          not_analyzed_games: 0,
          top_weaknesses: [],
          recent_games: [],
          analyzed_list: [
            {
              game_id: 'analyzed_game_1',
              user_color: 'white',
              opponent: 'FallbackOpponent1',
              blunders: 2,
              mistakes: 1,
              accuracy: 80
            },
            {
              game_id: 'analyzed_game_2',
              user_color: 'black',
              opponent: 'FallbackOpponent2',
              blunders: 1,
              mistakes: 2,
              accuracy: 75
            }
          ],
          in_queue_list: [],
          not_analyzed_list: [],
          stats: {}
        })
      });
    });
    
    // Mock reflect/pending to return empty (triggers fallback)
    await page.route('**/api/reflect/pending', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ games: [] })
      });
    });
    
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    const reflectionCard = page.getByTestId('reflection-games-card');
    await expect(reflectionCard).toBeVisible();
    
    // Should fallback to showing analyzed_list games
    await expect(reflectionCard.getByText(/vs FallbackOpponent1/)).toBeVisible();
    await expect(reflectionCard.getByText(/vs FallbackOpponent2/)).toBeVisible();
    
    // Fallback games use analyzed-game-${i} testid
    await expect(page.getByTestId('analyzed-game-0')).toBeVisible();
    await expect(page.getByTestId('analyzed-game-1')).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-reflect-fallback.jpeg', quality: 20 });
  });

  test('BUG FIX: Training task is contextual to user weakness - with mock data', async ({ page }) => {
    // Mock dashboard-stats to return a specific weakness
    await page.route('**/api/dashboard-stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_games: 10,
          analyzed_games: 8,
          queued_games: 0,
          not_analyzed_games: 2,
          top_weaknesses: [
            {
              pattern_type: 'missed_threat',
              occurrences: 15
            }
          ],
          recent_games: [],
          analyzed_list: [
            { game_id: 'g1', opponent: 'Op1', blunders: 1, mistakes: 2, accuracy: 70 },
            { game_id: 'g2', opponent: 'Op2', blunders: 2, mistakes: 1, accuracy: 65 }
          ],
          in_queue_list: [],
          not_analyzed_list: [],
          stats: {}
        })
      });
    });
    
    await page.route('**/api/reflect/pending', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ games: [] })
      });
    });
    
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    const trainingCard = page.getByTestId('training-task-card');
    await expect(trainingCard).toBeVisible();
    
    // Should show contextual training for "missed_threat" weakness
    await expect(trainingCard.getByText(/Threat Detection Practice/)).toBeVisible();
    await expect(trainingCard.getByText(/Solve positions where you missed opponent threats/)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-training-contextual.jpeg', quality: 20 });
  });

  test('Biggest Weakness section displays weakness info correctly', async ({ page }) => {
    // Mock with weakness data
    await page.route('**/api/dashboard-stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_games: 5,
          analyzed_games: 5,
          queued_games: 0,
          not_analyzed_games: 0,
          top_weaknesses: [
            {
              pattern_type: 'tactical_error',
              occurrences: 12
            }
          ],
          recent_games: [],
          analyzed_list: [
            { game_id: 'g1', opponent: 'Op1', blunders: 1, mistakes: 2, accuracy: 70 },
            { game_id: 'g2', opponent: 'Op2', blunders: 2, mistakes: 1, accuracy: 65 }
          ],
          in_queue_list: [],
          not_analyzed_list: [],
          stats: {}
        })
      });
    });
    
    await page.route('**/api/reflect/pending', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ games: [] })
      });
    });
    
    await page.goto(`${BASE_URL}/home`, { waitUntil: 'domcontentloaded' });
    await waitForAppReady(page);
    await page.waitForLoadState('networkidle');
    
    const weaknessCard = page.getByTestId('biggest-weakness-card');
    await expect(weaknessCard).toBeVisible();
    
    // Should show mapped weakness name for 'tactical_error'
    await expect(weaknessCard.getByText(/Tactical Errors/)).toBeVisible();
    await expect(weaknessCard.getByText(/calculation mistakes/i)).toBeVisible();
    
    await page.screenshot({ path: '.screenshots/homepage-weakness-display.jpeg', quality: 20 });
  });

});
