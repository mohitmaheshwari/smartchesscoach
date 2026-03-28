import { test, expect } from '@playwright/test';
import { devLogin, dismissToasts, hideEmergentBadge } from '../fixtures/helpers';

/**
 * Cognitive Gap Intelligence Frontend E2E Tests
 * Tests the GapProgressDashboard component and Train Gap functionality
 */

test.describe('Cognitive Gap Intelligence', () => {
  test.beforeEach(async ({ page }) => {
    // Dismiss any toasts that appear
    dismissToasts(page);
  });

  test.describe('GapProgressDashboard APIs', () => {
    test('summary API returns valid response', async ({ page }) => {
      await devLogin(page);
      
      // Navigate to journey page
      await page.goto('/journey', { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('domcontentloaded');
      
      // Make API call directly to test the summary endpoint
      const response = await page.request.get('/api/cognitive-gaps/summary');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('has_data');
      
      if (data.has_data) {
        expect(data).toHaveProperty('total_gaps_tracked');
        expect(data).toHaveProperty('overall_trend');
        expect(['improving', 'worsening', 'stable']).toContain(data.overall_trend);
      } else {
        expect(data).toHaveProperty('message');
      }
    });

    test('progress API returns valid response with trends', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.get('/api/cognitive-gaps/progress?weeks=4');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('weeks_analyzed');
      expect(data).toHaveProperty('week_labels');
      expect(data).toHaveProperty('gaps');
      expect(data).toHaveProperty('overall_trend');
      expect(['improving', 'worsening', 'stable']).toContain(data.overall_trend);
      
      // Check improving_gaps and worsening_gaps arrays exist
      expect(data).toHaveProperty('improving_gaps');
      expect(data).toHaveProperty('worsening_gaps');
      expect(Array.isArray(data.improving_gaps)).toBe(true);
      expect(Array.isArray(data.worsening_gaps)).toBe(true);
    });

    test('recurring patterns API returns patterns array', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.get('/api/cognitive-gaps/recurring');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('patterns');
      expect(Array.isArray(data.patterns)).toBe(true);
      
      // If patterns exist, verify structure
      for (const pattern of data.patterns) {
        expect(pattern).toHaveProperty('gap_type');
        expect(pattern).toHaveProperty('gap_name');
        expect(pattern).toHaveProperty('occurrences');
        expect(pattern).toHaveProperty('severity');
      }
    });

    test('plan quality API returns analysis or message', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.get('/api/cognitive-gaps/plan-quality');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('has_data');
      
      if (data.has_data) {
        expect(data).toHaveProperty('total_plans_analyzed');
        expect(data).toHaveProperty('plan_quality');
        expect(data).toHaveProperty('accuracy');
        expect(data).toHaveProperty('trend');
        expect(data).toHaveProperty('insight');
      } else {
        expect(data).toHaveProperty('message');
        expect(data).toHaveProperty('plans_recorded');
      }
    });

    test('recommended drills API returns recommendations', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.get('/api/drills/recommended');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('has_data');
      
      if (data.has_data) {
        expect(data).toHaveProperty('total_gaps_analyzed');
        expect(data).toHaveProperty('recommendations');
        expect(Array.isArray(data.recommendations)).toBe(true);
        
        // Verify recommendation structure
        for (const rec of data.recommendations) {
          expect(rec).toHaveProperty('gap_type');
          expect(rec).toHaveProperty('gap_name');
          expect(rec).toHaveProperty('occurrences');
          expect(rec).toHaveProperty('priority_score');
          expect(rec).toHaveProperty('drill_category');
          expect(rec).toHaveProperty('training_focus');
        }
      }
    });
  });

  test.describe('Drills from Gap API', () => {
    test('returns drills for calculation_depth gap type', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.get('/api/drills/from-gap/calculation_depth');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data.gap_type).toBe('calculation_depth');
      expect(data.gap_name).toBe('Calculation Depth');
      expect(data.drill_category).toBe('calculation');
      expect(data.layer).toBe('precision');
      expect(data).toHaveProperty('positions');
      expect(data).toHaveProperty('drill_types');
      expect(data).toHaveProperty('training_focus');
    });

    test('returns drills for threat_blindness gap type', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.get('/api/drills/from-gap/threat_blindness');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data.gap_type).toBe('threat_blindness');
      expect(data.layer).toBe('stability');
      expect(data).toHaveProperty('drill_types');
    });

    test('returns 400 for invalid gap type', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.get('/api/drills/from-gap/invalid_gap_type');
      expect(response.status()).toBe(400);
      
      const data = await response.json();
      expect(data.detail).toContain('Unknown gap type');
    });

    const validGapTypes = [
      'calculation_depth',
      'calculation_error',
      'threat_blindness',
      'hanging_piece_blindness',
      'tactical_oversight',
      'positional_misread',
      'defensive_lapse',
      'overconfidence',
    ];

    for (const gapType of validGapTypes) {
      test(`returns valid response for ${gapType}`, async ({ page }) => {
        await devLogin(page);
        
        const response = await page.request.get(`/api/drills/from-gap/${gapType}`);
        expect(response.status()).toBe(200);
        
        const data = await response.json();
        expect(data.gap_type).toBe(gapType);
        expect(data).toHaveProperty('layer');
        expect(['precision', 'stability', 'structure', 'conversion']).toContain(data.layer);
      });
    }
  });

  test.describe('Sync Training API', () => {
    test('sync-training endpoint updates training focus', async ({ page }) => {
      await devLogin(page);
      
      const response = await page.request.post('/api/cognitive-gaps/sync-training');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('updated');
      
      if (data.updated) {
        expect(data).toHaveProperty('layer_boosts');
        expect(data).toHaveProperty('dominant_layer');
      } else {
        expect(data).toHaveProperty('reason');
      }
    });
  });

  test.describe('Navigation to Train page', () => {
    test('can navigate to train page with gap parameter', async ({ page }) => {
      await devLogin(page);
      
      // Navigate directly to train page with gap parameter
      await page.goto('/train?gap=calculation_depth', { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('domcontentloaded');
      
      // Check URL has the gap parameter
      expect(page.url()).toContain('gap=calculation_depth');
    });
  });
});
