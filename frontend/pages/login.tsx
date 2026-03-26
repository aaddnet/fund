import { useEffect, useState } from 'react';
import type { GetServerSidePropsContext } from 'next';
import FormField from '../components/FormField';
import { useAuth } from '../lib/auth';
import { clearSessionCookies, getServerLocale } from '../lib/api';
import { useI18n } from '../lib/i18n';
import { colors, styles } from '../lib/ui';

export default function LoginPage() {
  const { signIn } = useAuth();
  const { locale, setLocale, t } = useI18n();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // 登录页不应该因为浏览器里残留的坏 token / refresh cookie 进入重定向死循环。
    // 进入登录页时先清掉本地会话 cookie，让用户总能回到一个可操作的干净状态。
    clearSessionCookies();
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await signIn({ username, password });
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : t('authRequired'));
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
  return { props: { initialLocale: getServerLocale(context) } };
}
