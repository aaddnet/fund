import { useState } from 'react';
import type { GetServerSidePropsContext } from 'next';
import FormField from '../components/FormField';
import { useAuth } from '../lib/auth';
import { getServerLocale, getServerRefreshToken } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { colors, styles } from '../lib/ui';

export default function LoginPage() {
  const { signIn } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const [username, setUsername] = useState('ops');
  const [password, setPassword] = useState('Ops1234567');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await signIn({ username, password });
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={styles.page}>
      <div style={{ ...styles.shell, maxWidth: 540 }}>
        <div style={styles.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 12, color: colors.primary, fontWeight: 800, letterSpacing: 1.2 }}>{t('appName').toUpperCase()}</div>
              <h1 style={{ margin: '8px 0 6px', fontSize: 28 }}>{t('loginTitle')}</h1>
              <p style={{ margin: 0, color: colors.muted }}>{t('loginSubtitle')}</p>
            </div>
            <select aria-label={t('language')} style={styles.input} value={locale} onChange={(event) => setLocale(event.target.value as 'en' | 'zh')}>
              <option value='en'>{t('english')}</option>
              <option value='zh'>{t('chinese')}</option>
            </select>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14, marginTop: 24 }}>
            <FormField label={t('username')}>
              <input style={styles.input} value={username} onChange={(event) => setUsername(event.target.value)} autoComplete='username' />
            </FormField>
            <FormField label={t('password')}>
              <input style={styles.input} type='password' value={password} onChange={(event) => setPassword(event.target.value)} autoComplete='current-password' />
            </FormField>
            <button style={styles.buttonPrimary} disabled={submitting} type='submit'>
              {submitting ? t('loggingIn') : t('login')}
            </button>
            {error ? <div style={{ color: colors.danger }}>{error}</div> : null}
          </form>
        </div>
      </div>
    </div>
  );
}

export async function getServerSideProps(context: GetServerSidePropsContext) {
  if (getServerRefreshToken(context)) {
    return {
      redirect: {
        destination: '/',
        permanent: false,
      },
    };
  }
  return { props: { initialLocale: getServerLocale(context) } };
}
