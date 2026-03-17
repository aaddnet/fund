import { useEffect } from 'react';
import type { GetServerSidePropsContext } from 'next';
import { useRouter } from 'next/router';
import { getServerLocale } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { styles } from '../../lib/ui';

export default function AuthCompletePage() {
  const router = useRouter();
  const { refresh } = useAuth();

  useEffect(() => {
    let active = true;

    async function finalizeLogin() {
      const ok = await refresh();
      if (!active) return;
      const next = typeof router.query.next === 'string' ? router.query.next : '/';
      if (ok) {
        window.location.replace(next);
      } else {
        window.location.replace(`/login?next=${encodeURIComponent(next)}`);
      }
    }

    finalizeLogin();
    return () => {
      active = false;
    };
  }, [refresh, router]);

  return (
    <div style={{ ...styles.page, display: 'grid', placeItems: 'center' }}>
      <div style={styles.card}>Finalizing sign-in...</div>
    </div>
  );
}

export async function getServerSideProps(context: GetServerSidePropsContext) {
  return { props: { initialLocale: getServerLocale(context) } };
}
