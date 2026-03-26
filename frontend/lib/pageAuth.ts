import type { GetServerSidePropsContext } from 'next';
import { buildSessionCookies, getMe, getServerAccessToken, getServerLocale, getServerRefreshToken, refreshSession } from './api';

function appendSetCookie(context: GetServerSidePropsContext, cookies: string[]) {
  const current = context.res.getHeader('Set-Cookie');
  const existing = Array.isArray(current) ? current : current ? [String(current)] : [];
  context.res.setHeader('Set-Cookie', [...existing, ...cookies]);
}

export async function requirePageAuth(context: GetServerSidePropsContext) {
  let accessToken = getServerAccessToken(context);
  const refreshToken = getServerRefreshToken(context);

  if (!accessToken && refreshToken) {
    try {
      const session = await refreshSession(refreshToken);
      accessToken = session.access_token;
      appendSetCookie(context, buildSessionCookies(session));
      return {
        accessToken,
        initialUser: session.user,
        initialLocale: getServerLocale(context),
      } as const;
    } catch {
      appendSetCookie(context, [
        'invest_access_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax',
        'invest_refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax',
      ]);
    }
  }

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
    if (refreshToken) {
      try {
        const session = await refreshSession(refreshToken);
        appendSetCookie(context, buildSessionCookies(session));
        return {
          accessToken: session.access_token,
          initialUser: session.user,
          initialLocale: getServerLocale(context),
        } as const;
      } catch {
        appendSetCookie(context, [
          'invest_access_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax',
          'invest_refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax',
        ]);
      }
    }

    return {
      redirect: {
        destination: `/login?next=${encodeURIComponent(context.resolvedUrl || '/')}`,
        permanent: false,
      },
    } as const;
  }
}
