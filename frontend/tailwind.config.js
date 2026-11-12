/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
        extend: {
                fontFamily: {
                        sans: ['Manrope', 'system-ui', 'sans-serif'],
                        heading: ['Outfit', 'system-ui', 'sans-serif'],
                        serif: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
                        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
                },
                letterSpacing: {
                        tighter: '-0.02em',
                },
                // ─── Type scale (2026-11-12) ────────────────────────────
                // There was no fontSize scale here at all, which is why src
                // carries 38 distinct arbitrary sizes including text-[10.5px]
                // (72 uses) and text-[12.5px] (53). A half-pixel size is not a
                // decision, it is someone nudging until one component looked
                // right; do that 38 times and nothing aligns, which reads as
                // cheap even when no single screen looks wrong.
                //
                // Six steps, each with its line height. The floor is 12px on
                // purpose: 10-11px body text is admin-tool density and was the
                // biggest single reason the product did not feel premium.
                fontSize: {
                        meta: ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.06em' }],   // 12 — eyebrows, labels
                        // NOT named sm/base: those are Tailwind defaults and
                        // src already uses text-sm 1,468 times and text-base
                        // 112 times. Overriding them would silently reflow the
                        // whole app with no visual regression cover. The scale
                        // is additive; existing classes keep their meaning.
                        note: ['0.875rem', { lineHeight: '1.375rem' }],                        // 14 — secondary
                        body: ['1rem', { lineHeight: '1.625rem' }],                            // 16 — body
                        lead: ['1.25rem', { lineHeight: '1.875rem' }],                         // 20 — lead paragraph
                        title: ['1.75rem', { lineHeight: '2.125rem', letterSpacing: '-0.02em' }], // 28 — section
                        display: ['2.5rem', { lineHeight: '2.75rem', letterSpacing: '-0.03em' }], // 40 — page title
                },
                // Three radii. rounded-full stays available for pills: that is
                // a shape, not a step on this scale.
                borderRadius: {
                        lg: 'var(--radius)',
                        md: 'calc(var(--radius) - 2px)',
                        sm: 'calc(var(--radius) - 4px)',
                        control: '0.5rem',   // 8  — buttons, inputs, chips
                        card: '0.875rem',    // 14 — cards, list rows
                        panel: '1.5rem',     // 24 — hero panels, sheets
                },
                colors: {
                        background: 'hsl(var(--background))',
                        foreground: 'hsl(var(--foreground))',
                        card: {
                                DEFAULT: 'hsl(var(--card))',
                                foreground: 'hsl(var(--card-foreground))'
                        },
                        popover: {
                                DEFAULT: 'hsl(var(--popover))',
                                foreground: 'hsl(var(--popover-foreground))'
                        },
                        primary: {
                                DEFAULT: 'hsl(var(--primary))',
                                foreground: 'hsl(var(--primary-foreground))'
                        },
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))'
                        },
                        muted: {
                                DEFAULT: 'hsl(var(--muted))',
                                foreground: 'hsl(var(--muted-foreground))'
                        },
                        accent: {
                                DEFAULT: 'hsl(var(--accent))',
                                foreground: 'hsl(var(--accent-foreground))'
                        },
                        destructive: {
                                DEFAULT: 'hsl(var(--destructive))',
                                foreground: 'hsl(var(--destructive-foreground))'
                        },
                        border: 'hsl(var(--border))',
                        input: 'hsl(var(--input))',
                        ring: 'hsl(var(--ring))',
                        chart: {
                                '1': 'hsl(var(--chart-1))',
                                '2': 'hsl(var(--chart-2))',
                                '3': 'hsl(var(--chart-3))',
                                '4': 'hsl(var(--chart-4))',
                                '5': 'hsl(var(--chart-5))'
                        },
                        // Brand colors
                        wine: 'hsl(var(--wine))',
                        gold: {
                                DEFAULT: 'hsl(var(--gold))',
                                muted: 'hsl(var(--gold-muted))',
                        },
                        // Chess semantic colors
                        chess: {
                                growth: '#10B981',
                                focus: '#F59E0B',
                                neutral: '#71717A',
                                blunder: '#EF4444',
                                mistake: '#F97316',
                                inaccuracy: '#EAB308',
                                good: '#3B82F6',
                                excellent: '#10B981',
                                brilliant: '#14B8A6',
                        },
                        // Locked palette additions (2026-06-12) — premium UX redesign
                        "teal-500": "#14B8A6",
                        "teal-200": "#CDF2F8", // hover variant
                        "teal-700": "#0D9488", // darker variant
                        "emerald-500": "#10B981",
                        "emerald-200": "#D1FAE5",
                        "emerald-700": "#047857",
                        "rose-500": "#F43F5E",
                        "rose-200": "#FEE2E2",
                        "rose-700": "#BE123C",
                },
                boxShadow: {
                        // Three neutral elevations. The only shadows defined
                        // here were four COLOURED glows, so plain depth had no
                        // name and src reached for shadow-sm/md/lg/2xl plus
                        // four one-off arbitrary values.
                        e1: '0 1px 2px rgb(0 0 0 / 0.16)',
                        e2: '0 6px 20px -6px rgb(0 0 0 / 0.34)',
                        e3: '0 24px 60px -24px rgb(0 0 0 / 0.55)',
                        // Glow effects for premium feel (premium UX redesign 2026-06-12)
                        "glow-amber": "0 0 20px rgba(251, 191, 36, 0.5)",
                        "glow-teal": "0 0 20px rgba(20, 184, 166, 0.4)",
                        "glow-emerald": "0 0 20px rgba(16, 185, 129, 0.4)",
                        "glow-rose": "0 0 20px rgba(244, 63, 94, 0.3)",
                        "glow-sm": "0 0 10px rgba(251, 191, 36, 0.3)",
                },
                keyframes: {
                        'accordion-down': {
                                from: { height: '0' },
                                to: { height: 'var(--radix-accordion-content-height)' }
                        },
                        'accordion-up': {
                                from: { height: 'var(--radix-accordion-content-height)' },
                                to: { height: '0' }
                        },
                        'fade-in': {
                                from: { opacity: '0', transform: 'translateY(8px)' },
                                to: { opacity: '1', transform: 'translateY(0)' }
                        },
                        'scale-in': {
                                from: { opacity: '0', transform: 'scale(0.95)' },
                                to: { opacity: '1', transform: 'scale(1)' }
                        },
                        'pulse-glow': {
                                '0%, 100%': { opacity: '1' },
                                '50%': { opacity: '0.7' }
                        },
                },
                animation: {
                        'accordion-down': 'accordion-down 0.2s ease-out',
                        'accordion-up': 'accordion-up 0.2s ease-out',
                        'fade-in': 'fade-in 0.3s ease-out',
                        'scale-in': 'scale-in 0.2s ease-out',
                        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
                }
        }
  },
  plugins: [require("tailwindcss-animate")],
};
