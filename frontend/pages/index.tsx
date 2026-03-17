import Layout from '../components/Layout';
import StatCard from '../components/StatCard';
import { API_BASE } from '../lib/api';
import { styles } from '../lib/ui';

export default function Home() {
  return (
    <Layout title='Fund Management Dashboard' subtitle='A local operations workspace for NAV, share flows, accounts, and imports.'>
      <div style={styles.grid3}>
        <StatCard label='Environment' value='Local Dev' hint='Docker + FastAPI + Next.js' />
        <StatCard label='Backend API' value='Ready' tone='success' hint={API_BASE} />
        <StatCard label='Workflow' value='Manual V1' tone='warning' hint='Supports smoke tests and seeded demo data' />
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>What you can do now</h3>
        <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
          <li>Review live NAV and share records on the dashboard.</li>
          <li>Create NAV calculations from the NAV page.</li>
          <li>Submit share subscriptions from the Shares page.</li>
          <li>Filter live account and client operational views from real backend data.</li>
          <li>Open a minimal read-only customer view for balances, share history, and NAV history.</li>
          <li>Run month / quarter / year operational reports with fund and client filters.</li>
        </ul>
      </div>
    </Layout>
  );
}
