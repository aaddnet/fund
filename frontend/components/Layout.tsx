import { ReactNode } from 'react';

export default function Layout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main style={{ maxWidth: 960, margin: '0 auto', fontFamily: 'sans-serif' }}>
      <h1>{title}</h1>
      {children}
    </main>
  );
}
