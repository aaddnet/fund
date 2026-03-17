import type { GetServerSidePropsContext } from 'next';
import { getMe, getServerAccessToken, getServerLocale } from './api';

export async function requirePageAuth(context: GetServerSidePropsContext) {
  const accessToken = getServerAccessToken(context);
  if (!accessToken) {
    return {
      redirect: {
        destination: `/login?next=${encodeURIComponent(context.resolvedUrl || '/')}`,
        permanent: false,
      },
    } as const;
  }

  try {
    const me = await getMe(accessToken);
    return {
      accessToken,
      initialUser: me.user,
      initialLocale: getServerLocale(context),
    } as const;
  } catch {
    return {
      redirect: {
        destination: `/login?next=${encodeURIComponent(context.resolvedUrl || '/')}`,
        permanent: false,
      },
    } as const;
  }
}
