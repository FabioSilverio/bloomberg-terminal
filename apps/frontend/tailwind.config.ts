import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#06080c',
          panel: '#0f131b',
          line: '#1b2433',
          muted: '#7b8494',
          accent: '#ff8a00',
          up: '#35d07f',
          down: '#ff5b5b'
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
      },
      spacing: {
        18: '4.5rem'
      },
      boxShadow: {
        terminal: '0 0 0 1px rgba(255, 138, 0, 0.15), 0 10px 24px rgba(0,0,0,0.35)'
      }
    }
  },
  plugins: []
};

export default config;
