/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F172A",
        paper: "#F7F5F0",
        clinical: {
          50: "#F0F9F6",
          100: "#DCEFE7",
          500: "#0E7C61",
          600: "#0B6650",
          700: "#095243",
        },
        amber: {
          500: "#C2790B",
        },
        rose: {
          500: "#B5423A",
        },
      },
      fontFamily: {
        display: ["'IBM Plex Serif'", "serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
    },
  },
  plugins: [],
}
