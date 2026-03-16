const API_BASE = process.env.NEXT_PUBLIC_API || 'http://localhost:8000';

export async function getNav() {
  const r = await fetch(`${API_BASE}/nav`);
  return r.json();
}
