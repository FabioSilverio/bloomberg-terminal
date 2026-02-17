import type { Metadata } from 'next';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import './globals.css';
import { QueryProvider } from '@/components/QueryProvider';

export const metadata: Metadata = {
  title: 'OpenBloom Terminal',
  description: 'Bloomberg-style market terminal workspace'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
