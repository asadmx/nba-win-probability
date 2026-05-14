/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0B0D12",
          panel: "#15171F",
          elevated: "#1A1D27",
        },
        border: {
          subtle: "#1F2230",
          strong: "#2A2E3D",
        },
        text: {
          primary: "#E8EAF0",
          secondary: "#7A7F8E",
          muted: "#4A4E5C",
        },
        prob: {
          win: "#22C55E",
          loss: "#EF4444",
          neutral: "#F59E0B",
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        "data-xl": ["3rem", { lineHeight: "1", letterSpacing: "-0.02em" }],
        "data-lg": ["2rem", { lineHeight: "1", letterSpacing: "-0.01em" }],
        "data-md": ["1.25rem", { lineHeight: "1" }],
      },
      animation: {
        "pulse-slow": "pulse 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
};