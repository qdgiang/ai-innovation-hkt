import type { Config } from "tailwindcss";

// Palette lifted from frontend_ref/styles.css tokens (coral/blue project colors,
// warning amber for blockers) — kept as the visual reference for DSH-1..8.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        brand: {
          coral: "#e8674b",
          blue: "#3b6bd6",
        },
        surface: {
          DEFAULT: "#ffffff",
          sunken: "#f6f7f9",
          dark: "#14161a",
          "dark-sunken": "#1c1f26",
        },
      },
    },
  },
  plugins: [],
};

export default config;
