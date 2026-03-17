import { defineConfig } from '@playwright/test';

const backendPort = 8001;
const frontendPort = 3001;
const databaseUrl = 'sqlite:////tmp/invest_e2e.sqlite3';
const authUsers = '[{"username":"admin","password":"Admin12345","role":"admin"},{"username":"ops","password":"Ops1234567","role":"ops"},{"username":"viewer","password":"Viewer12345","role":"ops-readonly"},{"username":"client1","password":"Client12345","role":"client-readonly","client_scope_id":1}]';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || `http://127.0.0.1:${frontendPort}`,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: [
        'rm -f /tmp/invest_e2e.sqlite3',
        `cd ../backend && DATABASE_URL=${databaseUrl} SCHEDULER_ENABLED=false AUTH_MODE=token AUTH_ALLOW_DEV_FALLBACK=false AUTH_BOOTSTRAP_USERS_JSON='${authUsers}' .venv312/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      ].join(' && '),
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: [
        `(cd ../backend && DATABASE_URL=${databaseUrl} SCHEDULER_ENABLED=false AUTH_MODE=token AUTH_ALLOW_DEV_FALLBACK=false AUTH_BOOTSTRAP_USERS_JSON='${authUsers}' .venv312/bin/python scripts/seed_e2e.py)`,
        `NEXT_PUBLIC_API=http://127.0.0.1:${backendPort} INTERNAL_API_BASE=http://127.0.0.1:${backendPort} npm run dev -- -p ${frontendPort}`,
      ].join(' && '),
      url: `http://127.0.0.1:${frontendPort}/login`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
