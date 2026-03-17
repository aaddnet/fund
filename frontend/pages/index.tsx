import Layout from '../components/Layout';
import { API_BASE } from '../lib/api';

export default function Home() {
  return (
    <Layout title='Fund Management Dashboard'>
      <p>V1 frontend initialized.</p>
      <ul>
        <li>Backend API: {API_BASE}</li>
        <li>Use the navigation links above to inspect dashboard, NAV, shares, accounts, clients, and imports.</li>
      </ul>
    </Layout>
  );
}
