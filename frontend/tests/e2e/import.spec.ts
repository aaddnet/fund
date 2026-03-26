import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import os from 'os';

// Helper: create a minimal valid CSV in a temp file
function createTestCsv(): string {
  const content = [
    'trade_date,asset_code,quantity,price,currency,tx_type,fee,snapshot_date',
    '2026-03-31,AAPL,5,190.00,USD,buy,0.50,2026-03-31',
    '2026-03-31,BTC,0.1,75000.00,USD,buy,1.00,2026-03-31',
  ].join('\n');
  const tmpFile = path.join(os.tmpdir(), `invest-e2e-${Date.now()}.csv`);
  fs.writeFileSync(tmpFile, content, 'utf-8');
  return tmpFile;
}

test.describe('Import flow', () => {
  let tmpCsv: string;

  test.beforeAll(() => {
    tmpCsv = createTestCsv();
  });

  test.afterAll(() => {
    fs.unlinkSync(tmpCsv);
  });

  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Username').fill('ops');
    await page.getByLabel('Password').fill('Ops1234567');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL(/\/$/);
  });

  test('import page is accessible from nav', async ({ page }) => {
    await page.getByRole('link', { name: 'Import' }).click();
    await expect(page).toHaveURL(/\/import/);
    await expect(page.getByRole('heading', { name: /import/i })).toBeVisible();
  });

  test('upload CSV and preview rows before confirming', async ({ page }) => {
    await page.goto('/import');

    // Attach the CSV file to the file input
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(tmpCsv);

    // Click Upload/Parse button
    await page.getByRole('button', { name: /upload|parse/i }).click();

    // Preview should appear with at least one data row
    await expect(page.getByText('AAPL')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('BTC')).toBeVisible();
  });

  test('read-only user cannot upload CSV', async ({ page }) => {
    // Log out and in as viewer
    await page.getByRole('button', { name: /logout|退出/i }).click();
    await expect(page).toHaveURL(/\/login/);

    await page.getByLabel('Username').fill('viewer');
    await page.getByLabel('Password').fill('Viewer12345');
    await page.getByRole('button', { name: 'Login' }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.goto('/import');
    // Upload button should be disabled for readonly users
    await expect(page.getByRole('button', { name: /upload|parse/i })).toBeDisabled();
  });
});
