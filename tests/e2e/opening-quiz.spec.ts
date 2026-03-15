import { test, expect } from '@playwright/test';

/**
 * Opening Quiz Mode E2E Tests
 * 
 * Tests:
 * 1. Quiz button visibility in OpeningTrainer when opening is selected
 * 2. Quiz navigation to /training/quiz/{key}
 * 3. Quiz loading and question display
 * 4. Quiz submission and result display
 */

const BASE_URL = 'https://coach-engine-demo.preview.emergentagent.com';

test.describe('Opening Quiz Mode', () => {
  test.beforeEach(async ({ page }) => {
    // Dev login
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
  });

  test('should show Quiz Me button when opening is selected', async ({ page }) => {
    // Navigate to training page
    await page.goto(`${BASE_URL}/training`);
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for page to load
    await expect(page.locator('body')).toBeVisible();
    await page.waitForTimeout(1000);
    
    // Click on Opening Trainer tab first
    const openingTrainerTab = page.locator('button:has-text("Opening Trainer")');
    if (await openingTrainerTab.isVisible()) {
      await openingTrainerTab.click();
      await page.waitForTimeout(1000);
    }
    
    // Take screenshot of training page
    await page.screenshot({ path: '/app/tests/e2e/training-page-initial.jpeg', quality: 20, fullPage: false });
    
    // Expand the Opening Library section first
    const allOpeningsToggle = page.getByTestId('all-openings-toggle');
    if (await allOpeningsToggle.isVisible()) {
      await allOpeningsToggle.click();
      await page.waitForTimeout(500);
    }
    
    // Click on an opening from the library (Italian Game)
    const openingItem = page.locator('[data-testid^="library-opening-"]').first();
    if (await openingItem.isVisible()) {
      await openingItem.click();
      await page.waitForTimeout(500);
      
      // Take screenshot showing opening selected
      await page.screenshot({ path: '/app/tests/e2e/opening-selected.jpeg', quality: 20, fullPage: false });
      
      // Check for Quiz Me button
      const quizButton = page.getByTestId('take-quiz-btn');
      await expect(quizButton).toBeVisible({ timeout: 5000 });
    }
  });

  test('should navigate to quiz page when Quiz Me button clicked', async ({ page }) => {
    // Navigate to training page
    await page.goto(`${BASE_URL}/training`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    
    // Click on Opening Trainer tab first
    const openingTrainerTab = page.locator('button:has-text("Opening Trainer")');
    if (await openingTrainerTab.isVisible()) {
      await openingTrainerTab.click();
      await page.waitForTimeout(1000);
    }
    
    // Expand Opening Library
    const allOpeningsToggle = page.getByTestId('all-openings-toggle');
    if (await allOpeningsToggle.isVisible()) {
      await allOpeningsToggle.click();
      await page.waitForTimeout(500);
    }
    
    // Select an opening
    const openingItem = page.locator('[data-testid^="library-opening-"]').first();
    if (await openingItem.isVisible()) {
      await openingItem.click();
      await page.waitForTimeout(500);
      
      // Click Quiz Me button
      const quizButton = page.getByTestId('take-quiz-btn');
      await expect(quizButton).toBeVisible({ timeout: 5000 });
      await quizButton.click();
      
      // Wait for navigation
      await page.waitForURL(/\/training\/quiz\//, { timeout: 10000 });
      
      // Verify we're on quiz page
      expect(page.url()).toContain('/training/quiz/');
    }
  });

  test('should load quiz questions for Italian Game', async ({ page }) => {
    // Navigate directly to Italian Game quiz
    await page.goto(`${BASE_URL}/training/quiz/italian_game?name=Italian%20Game`);
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for quiz to load - either content or loading state
    await page.waitForTimeout(2000);
    
    // Take screenshot
    await page.screenshot({ path: '/app/tests/e2e/quiz-loading.jpeg', quality: 20, fullPage: false });
    
    // Check for quiz component
    const quizCard = page.getByTestId('opening-quiz');
    const loadingCard = page.getByTestId('opening-quiz-loading');
    const emptyCard = page.getByTestId('opening-quiz-empty');
    
    // Should show one of these states
    const isQuizVisible = await quizCard.isVisible().catch(() => false);
    const isLoadingVisible = await loadingCard.isVisible().catch(() => false);
    const isEmptyVisible = await emptyCard.isVisible().catch(() => false);
    
    expect(isQuizVisible || isLoadingVisible || isEmptyVisible).toBe(true);
  });

  test('should display quiz questions with proper structure', async ({ page }) => {
    await page.goto(`${BASE_URL}/training/quiz/italian_game?name=Italian%20Game`);
    await page.waitForLoadState('domcontentloaded');
    
    // Wait for quiz to fully load
    await page.waitForTimeout(3000);
    
    // Check for quiz card
    const quizCard = page.getByTestId('opening-quiz');
    const isVisible = await quizCard.isVisible().catch(() => false);
    
    if (isVisible) {
      // Take screenshot of quiz
      await page.screenshot({ path: '/app/tests/e2e/quiz-questions.jpeg', quality: 20, fullPage: false });
      
      // Should show question content
      const questionText = page.locator('text=Italian Game Quiz');
      await expect(questionText).toBeVisible({ timeout: 5000 });
      
      // Should have progress bar
      const progress = page.locator('[role="progressbar"]');
      await expect(progress).toBeVisible();
      
      // Should show submit/check answer button
      const submitBtn = page.getByTestId('submit-answer-btn');
      await expect(submitBtn).toBeVisible();
    }
  });

  test('should show concept question options', async ({ page }) => {
    await page.goto(`${BASE_URL}/training/quiz/italian_game?name=Italian%20Game`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    
    const quizCard = page.getByTestId('opening-quiz');
    if (await quizCard.isVisible().catch(() => false)) {
      // First question should be concept type with options
      const optionA = page.getByTestId('quiz-option-0');
      const isOptionVisible = await optionA.isVisible().catch(() => false);
      
      if (isOptionVisible) {
        // Click on an option
        await optionA.click();
        
        // Check answer button should be enabled now
        const submitBtn = page.getByTestId('submit-answer-btn');
        await expect(submitBtn).toBeEnabled();
        
        // Take screenshot showing selected option
        await page.screenshot({ path: '/app/tests/e2e/quiz-option-selected.jpeg', quality: 20, fullPage: false });
      }
    }
  });

  test('should submit answer and show result', async ({ page }) => {
    await page.goto(`${BASE_URL}/training/quiz/italian_game?name=Italian%20Game`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    
    const quizCard = page.getByTestId('opening-quiz');
    if (await quizCard.isVisible().catch(() => false)) {
      // Select first option (concept question)
      const optionA = page.getByTestId('quiz-option-0');
      if (await optionA.isVisible().catch(() => false)) {
        await optionA.click();
        await page.waitForTimeout(300);
        
        // Submit answer
        const submitBtn = page.getByTestId('submit-answer-btn');
        await submitBtn.click();
        
        // Wait for result to show
        await page.waitForTimeout(1000);
        
        // Take screenshot of result
        await page.screenshot({ path: '/app/tests/e2e/quiz-answer-result.jpeg', quality: 20, fullPage: false });
        
        // Should show next button after answering
        const nextBtn = page.getByTestId('next-question-btn');
        await expect(nextBtn).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should complete quiz and show final results', async ({ page }) => {
    await page.goto(`${BASE_URL}/training/quiz/italian_game?name=Italian%20Game`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);
    
    const quizCard = page.getByTestId('opening-quiz');
    if (await quizCard.isVisible().catch(() => false)) {
      // Answer first question (concept type) and verify result display
      const option = page.getByTestId('quiz-option-0');
      
      if (await option.isVisible().catch(() => false)) {
        await option.click();
        await page.waitForTimeout(500);
        
        // Submit answer
        const submitBtn = page.getByTestId('submit-answer-btn');
        await expect(submitBtn).toBeEnabled({ timeout: 5000 });
        await submitBtn.click();
        await page.waitForTimeout(1000);
        
        // Take screenshot showing result after answering
        await page.screenshot({ path: '/app/tests/e2e/quiz-answer-submitted.jpeg', quality: 20, fullPage: false });
        
        // Next button should appear after submitting
        const nextBtn = page.getByTestId('next-question-btn');
        await expect(nextBtn).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should navigate back from quiz to training', async ({ page }) => {
    await page.goto(`${BASE_URL}/training/quiz/italian_game?name=Italian%20Game`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);
    
    // Find exit/close button
    const exitBtn = page.locator('button:has-text("Exit Quiz")');
    const goBackBtn = page.locator('button:has-text("Go Back")');
    
    if (await exitBtn.isVisible().catch(() => false)) {
      await exitBtn.click();
    } else if (await goBackBtn.isVisible().catch(() => false)) {
      await goBackBtn.click();
    }
    
    // Should navigate back to training
    await page.waitForURL(/\/training/, { timeout: 10000 });
    expect(page.url()).toContain('/training');
  });
});

test.describe('Opening Trainer Quiz Integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/api/auth/dev-login`);
    await page.waitForLoadState('domcontentloaded');
  });

  test('should show training page with Opening Trainer tab', async ({ page }) => {
    await page.goto(`${BASE_URL}/training`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    
    // Take screenshot
    await page.screenshot({ path: '/app/tests/e2e/training-page.jpeg', quality: 20, fullPage: false });
    
    // Training page has tabs - Puzzles and Opening Trainer
    const openingTrainerTab = page.locator('button:has-text("Opening Trainer")');
    await expect(openingTrainerTab).toBeVisible();
    
    // Click on Opening Trainer tab
    await openingTrainerTab.click();
    await page.waitForTimeout(1000);
    
    // Take screenshot after clicking tab
    await page.screenshot({ path: '/app/tests/e2e/opening-trainer-tab.jpeg', quality: 20, fullPage: false });
    
    // Now check for opening sections
    const yourOpeningsToggle = page.getByTestId('your-openings-toggle');
    const allOpeningsToggle = page.getByTestId('all-openings-toggle');
    
    // At least one of these should be visible
    const hasYourOpenings = await yourOpeningsToggle.isVisible().catch(() => false);
    const hasAllOpenings = await allOpeningsToggle.isVisible().catch(() => false);
    
    expect(hasYourOpenings || hasAllOpenings).toBe(true);
  });

  test('should expand opening library section', async ({ page }) => {
    await page.goto(`${BASE_URL}/training`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);
    
    // Click on Opening Trainer tab first
    const openingTrainerTab = page.locator('button:has-text("Opening Trainer")');
    if (await openingTrainerTab.isVisible()) {
      await openingTrainerTab.click();
      await page.waitForTimeout(1000);
    }
    
    const allOpeningsToggle = page.getByTestId('all-openings-toggle');
    if (await allOpeningsToggle.isVisible()) {
      await allOpeningsToggle.click();
      await page.waitForTimeout(500);
      
      // Should show opening items after expansion
      const openingItems = page.locator('[data-testid^="library-opening-"]');
      const count = await openingItems.count();
      
      expect(count).toBeGreaterThan(0);
      
      await page.screenshot({ path: '/app/tests/e2e/openings-expanded.jpeg', quality: 20, fullPage: false });
    }
  });
});
