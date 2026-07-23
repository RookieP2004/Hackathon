import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { AppProviders } from '@/components/providers/app-providers';

// UI_UX_SPECIFICATION.md §0.2: Inter for UI text, JetBrains Mono for every
// tabular/numeric sensor readout (fixed-width digits so live values don't
// jitter the layout as they tick over).
const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'AEGIS AI — Autonomous Industrial Safety Operating System',
  description:
    'Continuous plant monitoring, predictive risk reasoning, and orchestrated emergency response.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
