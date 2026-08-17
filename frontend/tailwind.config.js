/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        gruvbox: {
          bg0: '#1d2021',
          bg0_hard: '#1d2021',
          bg1: '#282828',
          bg2: '#32302f',
          bg3: '#3c3836',
          bg4: '#504945',
          fg: '#ebdbb2',
          fg0: '#fbf1c7',
          gray: '#a89984',
          dim: '#928374',
          red: '#fb4934',
          green: '#b8bb26',
          yellow: '#fabd2f',
          yellowDark: '#d79921',
          blue: '#83a598',
          purple: '#d3869b',
          aqua: '#8ec07c',
          orange: '#fe8019',
          lcd_gold: '#d79921',
          lcd_bg: '#946e19',
          lcd_dark: '#282100'
        }
      },
      fontFamily: {
        pixel: ['"Silkscreen"', '"Press Start 2P"', 'monospace'],
        arcade: ['"Press Start 2P"', 'monospace'],
        pixelify: ['"Pixelify Sans"', 'sans-serif'],
        vt: ['"VT323"', 'monospace'],
        mono: ['"VT323"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}

