# Visual design language

The WebApp dashboard (Phase 3+) is built against this aesthetic. The HTML mockups in this directory are the source of truth — when the spec and the mockups disagree, the mockups win.

- `home.html` — Home tab (locked v9: hero net worth, KPI strip, daily-spend heatmap, categories donut + ranking, Today block, accounts, goals)
- `tabs.html` — Transactions, Budgets, Goals, Ask
- `secondary-screens.html` — Edit transaction, Accounts, Categories, Settings

## Typography

- UI sans: **Geist** (400/500/600/700) via Google Fonts.
- All numeric data: **Geist Mono** (400/500/600), with `font-variant-numeric: tabular-nums` and slightly tightened tracking (`letter-spacing: -0.01em`).
- Section labels: 10px, uppercase, `letter-spacing: 0.12em`, color `#737373`, weight 500.
- Page section headers (e.g. "Today"): 15px Geist Sans semibold, optional muted date suffix in 12px.
- No Instrument Serif anywhere — we tried it and rolled back.

## Color

Monochrome only.

| Token             | Hex      |
|-------------------|----------|
| background        | `#fafafa` |
| foreground        | `#0a0a0a` |
| muted             | `#f4f4f5` |
| muted-foreground  | `#737373` |
| border            | `#e5e5e5` |
| border-soft       | `#f0f0f1` |

For data viz we use 5 grayscale stops: `#0a0a0a`, `#404040`, `#737373`, `#a3a3a3`, `#d4d4d4`. No semantic color (red for negative, green for income) — sign is conveyed by `−` / `+` prefixes.

## Layout

- **Sections separated by 1px hairline dividers**, never bordered cards. Cards (`.acct`) are reserved for inline grids of small things (account tiles, fields).
- Page padding: 20px horizontal (`px-5`).
- Phone-sized first; same components scale up to wider breakpoints.
- Bottom nav: 56px, lucide icons + label, active item gets a thin 2px×18px underline indicator.

## Components

- **Pill** — 10px, `bg-muted`, `border-border`, `rounded-md`, mono. Used for currency codes, status, dates, version tags.
- **Button (primary)** — `bg-foreground` `text-background`, `rounded-md`, padding 8/12.
- **Button (ghost)** — `border-border` only.
- **Input/Field** — `bg-muted` (when standalone) or `bg-white` inside a bordered group, no inner border between rows except `1px #f0f0f1` divider.
- **Heatmap** — 18px cells, `space-between` flex inside a 1fr column, 42px date label column on the left.
- **Donut** — monochrome 5-stop, 9px stroke, center label in mono.
- **Ring** (goal progress) — 56px, 6px stroke, rounded line cap, percentage in center mono.
- **Sparkbar / sparkline** — last bar in `#0a0a0a`, prior bars in stepped grayscale.
- **No shadows.** Tile borders are `1px #e5e5e5`. Dividers are `1px #e5e5e5`.

## Icons

Lucide via inline SVG. Standard size 18×18px, `stroke-width: 1.75`. Smaller variants `ico-sm` (14px) and `ico-xs` (11px). All icons inherit `currentColor`.

## Anti-patterns

- ❌ Tailwind shadow utilities (`shadow-sm` etc.)
- ❌ Saturated colors for amounts (red/green/blue)
- ❌ Stock shadcn `<Card>` look (rounded-xl, border, padding-6, ring-on-focus)
- ❌ Decorative gradients
- ❌ Quick-action grids on Home (Send/Receive/Transfer tiles)
- ❌ Floating bottom buttons that aren't a single primary action

## When implementing

1. Open the matching mockup HTML (`home.html`, `tabs.html`, `secondary-screens.html`).
2. Inspect with browser devtools to find the exact spacing/sizes/colors.
3. Translate to React + Tailwind, configuring `tailwind.config.ts` to expose Geist + Geist Mono and the color tokens above.
4. The tokens deviate from default Tailwind — see Phase 3 Task 7 for the config snippet.
