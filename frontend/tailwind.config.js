/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        risk: {
          low: "#22c55e",
          "low-bg": "#f0fdf4",
          medium: "#eab308",
          "medium-bg": "#fefce8",
          high: "#ef4444",
          "high-bg": "#fef2f2",
          critical: "#a855f7",
          "critical-bg": "#faf5ff",
        },
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a5f",
        },
      },
    },
  },
  plugins: [],
};
