import type { AppProps } from 'next/app';
import type { ReactNode } from 'react';
import { useRouter } from 'next/router';
import { AuthProvider, useAuth } from '../lib/auth';
import { I18nProvider, useI18n } from '../lib/i18n';
import { ToastProvider } from '../components/Toast';
import { styles } from '../lib/ui';

const PUBLIC_ROUTES = new Set(['/login', '/auth/complete']);

function RouteGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { ready, user } = useAuth();
  const { t } = useI18n();

  if (!ready) {
    return (
      <div style={{ ...styles.page, display: 'grid', placeItems: 'center' }}>
        <div style={styles.card}>{t('loadingSession')}</div>
      </div>
    );
  }

  if (!PUBLIC_ROUTES.has(router.pathname) && !user && typeof window !== 'undefined') {
    router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
    return null;
  }

  return children;
}

export default function App({ Component, pageProps }: AppProps<{ initialUser?: any; initialLocale?: 'en' | 'zh' }>) {
  return (
    <I18nProvider initialLocale={pageProps.initialLocale}>
      <AuthProvider initialUser={pageProps.initialUser}>
        <ToastProvider>
          <RouteGuard>
            <Component {...pageProps} />
          </RouteGuard>
        </ToastProvider>
      </AuthProvider>
    </I18nProvider>
  );
}
