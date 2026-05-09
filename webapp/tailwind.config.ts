import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#fafafa",
        foreground: "#0a0a0a",
        muted: "#f4f4f5",
        "muted-foreground": "#737373",
        border: "#e5e5e5",
        "border-soft": "#f0f0f1",
      },
      fontFamily: {
        sans: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "monospace"],
      },
      borderRadius: { md: "6px", lg: "8px" },
      boxShadow: {
        // disable default shadows; design uses borders instead.
        DEFAULT: "none",
        sm: "none",
        md: "none",
        lg: "none",
      },
      fontSize: {
        // tighten label / pill sizes used in the mockups
      },
    },
  },
  plugins: [],
} satisfies Config;
