import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "df-bg": "var(--df-bg)",
        "df-surface": "var(--df-surface)",
        "df-surface-solid": "var(--df-surface-solid)",
        "df-accent": "var(--df-accent)",
        "df-accent-dim": "var(--df-accent-dim)",
        "df-accent-secondary": "var(--df-accent-secondary)",
        "df-danger": "var(--df-danger)",
        "df-text": "var(--df-text)",
        "df-text-secondary": "var(--df-text-secondary)",
        "df-border": "var(--df-border)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["Merriweather", "ui-serif", "Georgia", "serif"],
      },
      boxShadow: {
        df: "var(--df-shadow)",
      },
      borderRadius: {
        "df-card": "1.5rem",
        "df-input": "1rem",
      },
    },
  },
  plugins: [],
};

export default config;
