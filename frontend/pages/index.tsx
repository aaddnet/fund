import Layout from '../components/Layout';
import StatCard from '../components/StatCard';
import { PUBLIC_API_BASE } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { styles } from '../lib/ui';

export default function Home() {
  const { t } = useI18n();

  return (
    <Layout title={t('homeTitle')} subtitle={t('homeSubtitle')}>
      <div style={styles.grid3}>
        <StatCard label={t('environment')} value={t('localDev')} hint='Docker + FastAPI + Next.js' />
        <StatCard label={t('backendApi')} value={t('backendReady')} tone='success' hint={PUBLIC_API_BASE} />
        <StatCard label={t('workflow')} value={t('workflowManual')} tone='warning' hint='Supports smoke tests and seeded demo data' />
      </div>
      <div style={{ ...styles.card, marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t('whatYouCanDo')}</h3>
        <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
          <li>{t('homeBullet1')}</li>
          <li>{t('homeBullet2')}</li>
          <li>{t('homeBullet3')}</li>
          <li>{t('homeBullet4')}</li>
          <li>{t('homeBullet5')}</li>
          <li>{t('homeBullet6')}</li>
        </ul>
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  return 'redirect' in auth ? auth : { props: { initialUser: auth.initialUser, initialLocale: auth.initialLocale } };
}
