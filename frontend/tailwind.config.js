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
          bg1: '#282828',
          bg2: '#32302f',
          bg3: '#3c3836',
          bg4: '#504945',
          fg: '#ebdbb2',
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
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}
