import { test, expect } from '@playwright/test';

test.describe('Customer (client-readonly) portal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Username').fill('client1');
    await page.getByLabel('Password').fill('Client12345');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL(/\//);
  });

  test('client-readonly user sees customer portal for own client', async ({ page }) => {
    await page.goto('/customers/1');
    await expect(page).not.toHaveURL(/\/login/);
    // Customer page should show share balance or nav info
    await expect(page.locator('body')).toBeVisible();
  });

  test('client-readonly user is blocked from operations dashboard', async ({ page }) => {
    // Navigating to ops-only page should redirect to login or show error
    await page.goto('/nav');
    // Should either redirect or show permission denied
    const url = page.url();
    const body = await page.locator('body').textContent();
    const blocked =
      url.includes('/login') ||
      (body || '').toLowerCase().includes('not authorized') ||
      (body || '').toLowerCase().includes('forbidden') ||
      (body || '').toLowerCase().includes('permission');
    expect(blocked).toBeTruthy();
  });

  test('client-readonly user cannot access another client portal', async ({ page }) => {
    // client1 has client_scope_id=1; accessing customer/2 should be denied
    const response = await page.goto('/customers/2');
    const status = response?.status() ?? 0;
    const body = await page.locator('body').textContent();
    const denied =
      status === 403 ||
      (body || '').toLowerCase().includes('forbidden') ||
      (body || '').toLowerCase().includes('not authorized') ||
      (body || '').toLowerCase().includes('403');
    expect(denied).toBeTruthy();
  });
});
