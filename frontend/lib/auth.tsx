import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { AuthSessionResponse, AuthUser, clearSessionCookies, getMe, login, logout, persistSessionCookies, refreshSession, REFRESH_TOKEN_COOKIE } from './api';

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.split(';').map((item) => item.trim()).find((item) => item.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null;
}

type AuthState = {
  user: AuthUser | null;
  permissions: string[];
  ready: boolean;
  error: string;
  signIn: (payload: { username: string; password: string }) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<boolean>;
  hasPermission: (...required: string[]) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children, initialUser }: { children: ReactNode; initialUser?: AuthUser | null }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(initialUser || null);
  const [permissions, setPermissions] = useState<string[]>(initialUser?.permissions || []);
  const [ready, setReady] = useState(Boolean(initialUser));
  const [error, setError] = useState('');

  const applySession = useCallback((session: AuthSessionResponse) => {
    persistSessionCookies(session);
    setUser(session.user);
    setPermissions(session.user.permissions || []);
    setError('');
    setReady(true);
  }, []);

  const refresh = useCallback(async () => {
    const refreshToken = getCookie(REFRESH_TOKEN_COOKIE);
    if (!refreshToken) {
      clearSessionCookies();
      setUser(null);
      setPermissions([]);
      setReady(true);
      return false;
    }
    try {
      const session = await refreshSession(refreshToken);
      applySession(session);
      return true;
    } catch (refreshError) {
      clearSessionCookies();
      setUser(null);
      setPermissions([]);
      setError(refreshError instanceof Error ? refreshError.message : 'Session refresh failed');
      setReady(true);
      return false;
    }
  }, [applySession]);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (initialUser) {
        setReady(true);
        return;
      }
      try {
        const me = await getMe();
        if (!active) return;
        setUser(me.user);
        setPermissions(me.actor.permissions || me.user?.permissions || []);
      } catch {
        if (!active) return;
        await refresh();
      } finally {
        if (active) setReady(true);
      }
    }
    bootstrap();
    return () => {
      active = false;
    };
  }, [initialUser, refresh]);

  const signIn = useCallback(async (payload: { username: string; password: string }) => {
    const session = await login(payload);
    applySession(session);
    const next = typeof router.query.next === 'string' ? router.query.next : '/';

    // 先进入一个公开的登录完成页，等浏览器把 cookie 稳定带上后，再进入受保护页面。
    if (typeof window !== 'undefined') {
      window.location.assign(`/auth/complete?next=${encodeURIComponent(next)}`);
      return;
    }

    await router.replace(`/auth/complete?next=${encodeURIComponent(next)}`);
  }, [applySession, router]);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } catch {
      // 这里吞掉 logout 网络错误，前端仍然要把本地会话清掉，避免坏状态卡住。
    }
    clearSessionCookies();
    setUser(null);
    setPermissions([]);
    setReady(true);
    await router.replace('/login');
  }, [router]);

  const hasPermission = useCallback((...required: string[]) => {
    if (required.length === 0) return true;
    return required.every((permission) => permissions.includes(permission));
  }, [permissions]);

  const value = useMemo<AuthState>(
    () => ({ user, permissions, ready, error, signIn, signOut, refresh, hasPermission }),
    [user, permissions, ready, error, signIn, signOut, refresh, hasPermission],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used within AuthProvider');
  return value;
}
