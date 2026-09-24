/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "#6366f1", // Indigo
          hover: "#4f46e5",
          foreground: "#ffffff",
        },
        secondary: {
          DEFAULT: "#06b6d4", // Cyan
          foreground: "#ffffff",
        },
        accent: {
          DEFAULT: "#ec4899", // Pink
          foreground: "#ffffff",
        },
        dark: {
          900: "#090d16",
          800: "#0f172a",
          700: "#1e293b",
          600: "#334155",
        }
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "studio-glow": "radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.15), transparent 70%)",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.8", transform: "scale(1.02)" },
        },
      },
      animation: {
        "pulse-glow": "pulse-glow 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
