const API_BASE = process.env.NEXT_PUBLIC_API || 'http://127.0.0.1:8000';

type ApiListResponse<T> = {
  items?: T[];
  pagination?: {
    page: number;
    size: number;
    total: number;
  };
};

export type NavRecord = {
  id: number;
  fund_id: number;
  nav_date: string;
  total_assets_usd: number;
  total_shares: number;
  nav_per_share: number;
  is_locked: boolean;
};

export type ShareTransaction = {
  id: number;
  fund_id: number;
  client_id: number;
  tx_date: string;
  tx_type: string;
  amount_usd: number;
  shares: number;
  nav_at_date: number;
};

export type FeeRecord = {
  id: number;
  fund_id: number;
  fee_date: string;
  gross_return: number;
  fee_rate: number;
  fee_amount_usd: number;
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `API ${path} failed with ${response.status}`);
  }
  return response.json();
}

export async function getHealth() {
  return fetchJson<{ status: string }>('/health');
}

export async function getHealthDb() {
  return fetchJson<{ db: string }>('/health/db');
}

export async function getNav() {
  return fetchJson<NavRecord[]>('/nav');
}

export async function getShareHistory() {
  return fetchJson<ShareTransaction[]>('/share/history');
}

export async function getFees() {
  return fetchJson<FeeRecord[]>('/fee');
}

export async function getPlaceholderResource(path: string) {
  return fetchJson<ApiListResponse<Record<string, unknown>>>(path);
}

export async function createNav(payload: { fund_id: number; nav_date: string }) {
  return fetchJson<NavRecord>('/nav/calc', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createShareSubscription(payload: { fund_id: number; client_id: number; tx_date: string; amount_usd: number }) {
  return fetchJson<ShareTransaction>('/share/subscribe', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export { API_BASE };
