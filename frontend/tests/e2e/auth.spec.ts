import { test, expect } from '@playwright/test';

test('redirects unauthenticated users to login', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/);
});

test('supports login, language switch, and logout', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Language').selectOption('zh');
  await expect(page.getByText('登录基金运营控制台')).toBeVisible();

  await page.getByLabel('用户名').fill('ops');
  await page.getByLabel('密码').fill('Ops1234567');
  await page.getByRole('button', { name: '登录' }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText(/欢迎|Welcome/)).toBeVisible();

  await page.getByRole('button', { name: /退出登录|Logout/ }).click();
  await expect(page).toHaveURL(/\/login/);
});

test('surfaces authentication errors', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('ops');
  await page.getByLabel('Password').fill('WrongPass123');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page.getByText(/invalid username or password/i)).toBeVisible();
});

test('supports core nav and share flows end to end for ops users', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('ops');
  await page.getByLabel('Password').fill('Ops1234567');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.getByRole('link', { name: 'NAV' }).click();
  await expect(page).toHaveURL(/\/nav/);
  await page.getByLabel('NAV Date').fill('2026-06-30');
  await page.getByRole('button', { name: 'Calculate NAV' }).click();
  await expect(page.getByText(/NAV calculated successfully/i)).toBeVisible();

  await page.getByRole('link', { name: 'Shares' }).click();
  await expect(page).toHaveURL(/\/shares/);
  await page.getByLabel('Amount USD').fill('120');
  await page.getByRole('button', { name: 'Create Subscription' }).click();
  await expect(page.getByText(/booked successfully/i)).toBeVisible();
  await expect(page.getByText('120')).toBeVisible();
});

test('hides write actions for readonly users while preserving read access', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Username').fill('viewer');
  await page.getByLabel('Password').fill('Viewer12345');
  await page.getByRole('button', { name: 'Login' }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.getByRole('link', { name: 'NAV' }).click();
  await expect(page).toHaveURL(/\/nav/);
  await expect(page.getByRole('button', { name: 'Calculate NAV' })).toBeDisabled();
  await expect(page.getByText(/read-only mode/i)).toBeVisible();

  await page.getByRole('link', { name: 'Import' }).click();
  await expect(page).toHaveURL(/\/import/);
  await expect(page.getByRole('button', { name: 'Upload & Parse' })).toBeDisabled();
});
