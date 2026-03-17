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
