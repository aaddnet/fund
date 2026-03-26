import { Children, cloneElement, isValidElement, ReactNode, useId, type ReactElement } from 'react';
import { styles } from '../lib/ui';

export default function FormField({ label, children }: { label: string; children: ReactNode }) {
  const inputId = useId();
  const child = Children.only(children);
  const enhancedChild = isValidElement(child) ? cloneElement(child as ReactElement<any>, { id: inputId }) : child;

  return (
    <div>
      <label htmlFor={inputId} style={styles.label}>{label}</label>
      {enhancedChild}
    </div>
  );
}
