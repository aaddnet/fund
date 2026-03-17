import { ReactNode } from 'react';
import { styles } from '../lib/ui';

export default function FormField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label style={styles.label}>{label}</label>
      {children}
    </div>
  );
}
