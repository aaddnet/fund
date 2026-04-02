import Layout from '../components/Layout';
import { useI18n } from '../lib/i18n';
import { requirePageAuth } from '../lib/pageAuth';
import { colors, styles } from '../lib/ui';

type Props = {
  error?: string;
};

export default function Page({ error }: Props) {
  const { t } = useI18n();

  return (
    <Layout title={t('reportsTitle')} subtitle={t('reportsSubtitle')} requiredPermission='reports.read'>
      {error ? <div style={{ ...styles.card, marginBottom: 16, color: colors.danger }}>{t('backendWarning')}: {error}</div> : null}

      <div style={styles.card}>
        <h3 style={{ marginTop: 0 }}>Reports</h3>
        <p style={{ color: colors.muted }}>
          Report module is being restructured. Please use the dashboard and account detail pages for current data.
        </p>
      </div>
    </Layout>
  );
}

export async function getServerSideProps(context: any) {
  const auth = await requirePageAuth(context);
  if ('redirect' in auth) {
    return auth;
  }

  return {
    props: {
      initialUser: auth.initialUser,
      initialLocale: auth.initialLocale,
    },
  };
}
