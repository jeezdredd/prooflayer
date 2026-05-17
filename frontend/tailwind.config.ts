import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Instrument Serif"', "Times New Roman", "serif"],
        mono: ['"JetBrains Mono"', "SF Mono", "Menlo", "monospace"],
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
      },
      colors: {
        ink: {
          50: "var(--ink-50)",
          100: "var(--ink-100)",
          200: "var(--ink-200)",
          300: "var(--ink-300)",
          400: "var(--ink-400)",
          500: "var(--ink-500)",
          600: "var(--ink-600)",
          700: "var(--ink-700)",
          800: "var(--ink-800)",
          850: "var(--ink-850)",
          900: "var(--ink-900)",
          950: "var(--ink-950)",
        },
        signal: {
          amber: "var(--signal-amber)",
          cyan: "var(--signal-cyan)",
          blood: "var(--signal-blood)",
          sage: "var(--signal-sage)",
          violet: "var(--signal-violet)",
          lime: "var(--signal-lime)",
          fuchsia: "var(--signal-fuchsia)",
        },
        paper: "var(--paper)",
      },
      keyframes: {
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "scan-bar": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(200%)" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(20px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
        "check-pop": {
          "0%": { transform: "scale(0)", opacity: "0" },
          "60%": { transform: "scale(1.15)", opacity: "1" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "ticker-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "rise": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "aurora": {
          "0%, 100%": { transform: "translate(-10%, -10%) rotate(0deg) scale(1)" },
          "33%": { transform: "translate(15%, 5%) rotate(30deg) scale(1.15)" },
          "66%": { transform: "translate(-5%, 15%) rotate(-20deg) scale(0.95)" },
        },
        "gradient-pan": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        "tilt": {
          "0%, 100%": { transform: "rotate(-0.3deg)" },
          "50%": { transform: "rotate(0.3deg)" },
        },
        "marquee-x": {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "border-spin": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "blur-in": {
          "0%": { opacity: "0", filter: "blur(12px)", transform: "translateY(12px)" },
          "100%": { opacity: "1", filter: "blur(0)", transform: "translateY(0)" },
        },
        "grain": {
          "0%, 100%": { transform: "translate(0,0)" },
          "10%": { transform: "translate(-5%,-5%)" },
          "20%": { transform: "translate(-10%,5%)" },
          "30%": { transform: "translate(5%,-10%)" },
          "40%": { transform: "translate(-5%,15%)" },
          "50%": { transform: "translate(-10%,5%)" },
          "60%": { transform: "translate(15%,0)" },
          "70%": { transform: "translate(0,10%)" },
          "80%": { transform: "translate(-15%,0)" },
          "90%": { transform: "translate(10%,5%)" },
        },
        "count-up": {
          "0%": { opacity: "0", transform: "translateY(50%)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.8)", opacity: "0.8" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
      },
      animation: {
        "pulse-soft": "pulse-soft 1.5s ease-in-out infinite",
        "scan-bar": "scan-bar 1.8s linear infinite",
        "fade-in-up": "fade-in-up 0.35s ease-out",
        "fade-in": "fade-in 0.25s ease-out",
        "slide-in-right": "slide-in-right 0.25s ease-out",
        "shimmer": "shimmer 2s linear infinite",
        "check-pop": "check-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)",
        "spin-slow": "spin-slow 1s linear infinite",
        "ticker-up": "ticker-up 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
        "rise": "rise 0.6s cubic-bezier(0.16, 1, 0.3, 1)",
        "aurora": "aurora 18s ease-in-out infinite",
        "aurora-slow": "aurora 28s ease-in-out infinite",
        "gradient-pan": "gradient-pan 8s ease infinite",
        "float": "float 6s ease-in-out infinite",
        "tilt": "tilt 9s ease-in-out infinite",
        "marquee-x": "marquee-x 30s linear infinite",
        "border-spin": "border-spin 6s linear infinite",
        "blur-in": "blur-in 0.7s cubic-bezier(0.16, 1, 0.3, 1) both",
        "grain": "grain 8s steps(10) infinite",
        "count-up": "count-up 0.8s cubic-bezier(0.16, 1, 0.3, 1)",
        "pulse-ring": "pulse-ring 1.6s cubic-bezier(0.215, 0.61, 0.355, 1) infinite",
      },
      backgroundImage: {
        "skeleton-shimmer":
          "linear-gradient(90deg, var(--ink-900) 0%, var(--ink-850) 50%, var(--ink-900) 100%)",
        "grid-fine":
          "linear-gradient(rgba(7,6,10,0.06) 1px, transparent 1px), linear-gradient(to right, rgba(7,6,10,0.06) 1px, transparent 1px)",
        "iris": "linear-gradient(135deg, var(--signal-violet), var(--signal-cyan), var(--signal-amber))",
      },
      backgroundSize: {
        "grid-fine": "32px 32px",
        "200%": "200% 200%",
      },
      boxShadow: {
        "glow-amber": "0 0 40px -10px var(--signal-amber)",
        "glow-cyan": "0 0 40px -10px var(--signal-cyan)",
        "glow-violet": "0 0 40px -10px var(--signal-violet)",
        "glass": "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 24px 48px -16px rgba(0,0,0,0.6)",
      },
    },
  },
  plugins: [],
} satisfies Config;
