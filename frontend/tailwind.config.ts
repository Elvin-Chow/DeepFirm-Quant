import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "df-bg": "#0b0c10",
        "df-surface": "#1f2833",
        "df-accent": "#66fcf1",
        "df-accent-dim": "#45a29e",
        "df-danger": "#ff6b6b",
        "df-text": "#c5c6c7",
      },
    },
  },
  plugins: [],
};

export default config;
