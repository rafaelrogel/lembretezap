import type { Config } from "tailwindcss";

const config: Config = {
  // Watched by Next.js in dev; any change here triggers CSS rebuild and HMR.
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      screens: {
        // max 1079px = mobile; min 1080px = desktop
        mobile: { max: "1079px" },
        desktop: "1080px",
      },
      colors: {
        brand: {
          50: "var(--color-brand-50)",
          100: "var(--color-brand-100)",
          200: "var(--color-brand-200)",
          300: "var(--color-brand-300)",
          400: "var(--color-brand-400)",
          500: "var(--color-brand-500)",
          600: "var(--color-brand-600)",
          700: "var(--color-brand-700)",
          800: "var(--color-brand-800)",
          900: "var(--color-brand-900)",
        },
        neutral: {
          50: "var(--color-neutral-50)",
          100: "var(--color-neutral-100)",
          200: "var(--color-neutral-200)",
          300: "var(--color-neutral-300)",
          400: "var(--color-neutral-400)",
          500: "var(--color-neutral-500)",
          600: "var(--color-neutral-600)",
          700: "var(--color-neutral-700)",
          800: "var(--color-neutral-800)",
          900: "var(--color-neutral-900)",
        },
        /* Semantic aliases */
        surface: "var(--color-surface)",
        "surface-elevated": "var(--color-surface-elevated)",
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-muted": "var(--color-text-muted)",
        border: "var(--color-border)",
        "border-strong": "var(--color-border-strong)",
      },
      spacing: {
        /* Numeric scale */
        0: "var(--space-0)",
        1: "var(--space-1)",
        2: "var(--space-2)",
        3: "var(--space-3)",
        4: "var(--space-4)",
        5: "var(--space-5)",
        6: "var(--space-6)",
        8: "var(--space-8)",
        10: "var(--space-10)",
        12: "var(--space-12)",
        16: "var(--space-16)",
        20: "var(--space-20)",
        24: "var(--space-24)",
        /* Semantic */
        "page-x": "var(--spacing-page-x)",
        "page-y": "var(--spacing-page-y)",
        section: "var(--spacing-section)",
        block: "var(--spacing-block)",
        element: "var(--spacing-element)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius-md)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        full: "var(--radius-full)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      fontSize: {
        "display-xl": ["var(--text-display-xl)", { lineHeight: "var(--leading-display-xl)" }],
        "display-lg": ["var(--text-display-lg)", { lineHeight: "var(--leading-display-lg)" }],
        "display-md": ["var(--text-display-md)", { lineHeight: "var(--leading-display-md)" }],
        "display-sm": ["var(--text-display-sm)", { lineHeight: "var(--leading-display-sm)" }],
        "heading-lg": ["var(--text-heading-lg)", { lineHeight: "var(--leading-heading-lg)" }],
        "heading-md": ["var(--text-heading-md)", { lineHeight: "var(--leading-heading-md)" }],
        "heading-sm": ["var(--text-heading-sm)", { lineHeight: "var(--leading-heading-sm)" }],
        "body-lg": ["var(--text-body-lg)", { lineHeight: "var(--leading-body-lg)" }],
        "body-md": ["var(--text-body-md)", { lineHeight: "var(--leading-body-md)" }],
        "body-sm": ["var(--text-body-sm)", { lineHeight: "var(--leading-body-sm)" }],
        caption: ["var(--text-caption)", { lineHeight: "var(--leading-caption)" }],
      },
      maxWidth: {
        container: "var(--container-max)",
        "container-sm": "var(--container-sm)",
        "container-lg": "var(--container-lg)",
      },
      transitionDuration: {
        fast: "var(--duration-fast)",
        normal: "var(--duration-normal)",
        slow: "var(--duration-slow)",
      },
      transitionTimingFunction: {
        token: "var(--ease-out)",
        "token-expo": "var(--ease-out-expo)",
      },
      animationDelay: {
        100: "100ms",
        200: "200ms",
        2000: "2s",
        4000: "4s",
        6000: "6s",
      },
      keyframes: {
        "ambient-drift": {
          "0%, 100%": { transform: "translate(0, 0)" },
          "33%": { transform: "translate(6px, -4px)" },
          "66%": { transform: "translate(-4px, 6px)" },
        },
      },
      animation: {
        "ambient-drift": "ambient-drift 18s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
