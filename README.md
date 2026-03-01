# Zappelin

Modern web app foundation with Next.js (App Router), TypeScript, and Tailwind CSS. Set up for a component-based, responsive layout system and ready to plug in Figma design tokens.

## Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS** with design tokens (colors, spacing, radius, typography)
- Component-based layout and UI structure

## Folder structure

```
├── app/
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home
│   ├── globals.css         # Design tokens (CSS variables)
│   └── about/
│       └── page.tsx        # Example secondary page
├── components/
│   ├── layout/             # Layout primitives
│   │   ├── Container.tsx
│   │   ├── Grid.tsx
│   │   ├── Stack.tsx
│   │   └── index.ts
│   └── ui/                 # Reusable UI components
│       ├── Typography.tsx
│       └── index.ts
├── tailwind.config.ts      # Token → Tailwind mapping
├── postcss.config.js
└── next.config.js
```

## Design tokens

- **Colors:** `brand.*` and `neutral.*` in `app/globals.css`; override with Figma palette.
- **Spacing:** `--spacing-page-x`, `--spacing-section`, `--spacing-block`, `--spacing-element`.
- **Radius:** `--radius-sm` through `--radius-full`.
- **Typography:** scale from `display-lg` to `caption`; sizes and line heights in `globals.css`, mapped in `tailwind.config.ts`.

## Layout & typography

- **Container:** `size="default" | "sm" | "lg"`, responsive horizontal padding.
- **Grid:** `cols`, `gap`, and optional `sm` / `md` / `lg` for breakpoints.
- **Stack:** vertical or horizontal flex with `gap`, `align`, `justify`.
- **Typography:** `variant` for display, heading, body, caption; optional `as` to override the rendered element.

## Requirements

- Node.js **18.17+** (recommended 20.x LTS)

## Live development (visual iteration)

Optimized so you can edit components in the editor and see changes instantly in the browser without restarting.

### Start the preview

1. **Install and run the dev server**
   ```bash
   npm install
   npm run dev
   ```
2. **Open the app in your browser**
   - Dev server runs at: **http://localhost:3000**
   - The terminal will show: `▲ Next.js ... Local: http://localhost:3000`
3. **Edit and see changes**
   - Save any file in `app/` or `components/` — the browser updates automatically.
   - **Fast Refresh** keeps component state when you edit React components (no full page reload).
   - **Tailwind** watches `app/` and `components/`; style and class changes apply immediately.
   - CSS (e.g. `globals.css`) and layout updates also hot-reload without a full refresh.

### Tips

- **Keep the dev server running** — leave `npm run dev` in a terminal; no need to restart on file changes.
- **Fix errors to keep HMR working** — syntax or runtime errors can force a full reload; fixing them restores instant updates.
- **Faster rebuilds (optional)** — run `npm run dev:turbo` to use Turbopack for quicker refresh on large projects.

## Scripts

| Script         | Command           | Description                    |
|----------------|-------------------|--------------------------------|
| `npm run dev`  | `next dev`        | Start dev server with HMR      |
| `npm run dev:turbo` | `next dev --turbo` | Dev server with Turbopack |
| `npm run build`| `next build`      | Production build               |
| `npm run start`| `next start`      | Run production server          |
| `npm run lint` | `next lint`       | Run ESLint                     |

## Adding Figma designs

1. Replace CSS variables in `app/globals.css` with your Figma colors, spacing, and radius.
2. Update typography scale in `globals.css` and any font families in `app/layout.tsx`.
3. Add new components under `components/ui/` and export from `components/ui/index.ts`.
4. Use route groups under `app/` (e.g. `app/(marketing)/`, `app/(dashboard)/`) if you need different layouts per section.
