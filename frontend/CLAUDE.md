# AI Collections Assistant

## Project Overview

AI-powered collections management assistant built with Next.js. Provides a real-time call interface with live transcript, AI insight flash cards, sentiment analysis, and auto-filled disposition forms. Designed for bank telecaller workflows.

## Tech Stack

- **Framework:** Next.js 16.1.6 (App Router, Turbopack)
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS 4 + shadcn/ui + inline styles (prototype-faithful)
- **Animations:** Framer Motion 12 (declarative motion variants)
- **Icons:** Lucide React
- **i18n:** next-intl v4 (locale-based routing, 3 locales: en, hi, mr)
- **UI Components:** shadcn/ui (Radix UI primitives)
- **Utilities:** clsx, tailwind-merge, class-variance-authority
- **React:** 19.2

## Commands

- `npm run dev` — Start dev server (Turbopack)
- `npm run build` — Production build
- `npm run start` — Start production server
- `npm run lint` — Run ESLint

## Project Structure

```
messages/
  en.json                     # English UI strings (default locale)
  hi.json                     # Hindi UI strings
  mr.json                     # Marathi UI strings
src/
  i18n/
    routing.ts                # Supported locales (en, hi, mr) + default locale config
    request.ts                # Server-side message loading for next-intl
    navigation.ts             # Locale-aware useRouter, usePathname, Link via createNavigation
  proxy.ts                    # Locale detection + redirect proxy (Next.js 16 convention)
  app/
    [locale]/
      layout.tsx              # Root layout: DM Sans font + NextIntlClientProvider
      globals.css             # Live-dot pulse (lp), scrollbar, focus styles, shadcn theme vars
      page.tsx                # Home page with link to /collections-assistant
      collections-assistant/
        page.tsx              # Server wrapper for CollectionsAssistant
  components/
    domain/
      collections/
        CollectionsAssistant.tsx  # Main 'use client' component (3-pane layout)
    ui/
      dropdown-menu.tsx       # shadcn DropdownMenu component (Radix)
  data/
    mock-data.ts              # Mock customer, loan, transcript, insights data
  config/
    theme.ts                  # Color tokens (T), sentiment colors (SC), card types, result config
  types/
    collections.types.ts      # All TypeScript interfaces and type aliases
  lib/
    utils.ts                  # cn() for Tailwind merging, formatCallTime()
```

## Architecture Patterns

- **Locale routing:** All pages under `src/app/[locale]/`. Proxy (`src/proxy.ts`) redirects `/` to `/en/`. Uses Next.js 16 `proxy.ts` convention (not deprecated `middleware.ts`).
- **Server vs Client components:** Pages are server components. `CollectionsAssistant.tsx` is the main `'use client'` component.
- **i18n strings:** All UI text lives in `messages/{locale}.json`. Components use `useTranslations()` hook. Locale switching uses `useRouter`/`usePathname` from `@/i18n/navigation`.
- **Animations:** Framer Motion `motion.div` with declarative variants (`fadeInUp`, `cardSlideIn`, `segmentFadeIn`). CSS keyframes only for the `.live-dot` pulse. No CSS keyframe animations in the component — all handled by Framer Motion.
- **Icons:** Lucide React for all icons. Theme config uses string icon keys (e.g. `"info"`, `"lightbulb"`), mapped to Lucide components via `CARD_ICON_MAP` in the component.
- **UI components:** shadcn/ui for complex interactive elements (e.g. DropdownMenu for language switcher). Initialized with `npx shadcn@canary` for Tailwind v4 compatibility.
- **Theme tokens:** Centralized in `src/config/theme.ts` — not Tailwind config. Used as inline style values.
- **Mock data:** Extracted to `src/data/mock-data.ts`, typed with interfaces from `src/types/collections.types.ts`.
- **Path alias:** `@/*` maps to `./src/*`.

## Adding a New Language

1. Create `messages/{locale}.json` (copy `en.json`, translate values)
2. Add locale to `src/i18n/routing.ts`: `locales: ["en", "hi", "mr", "{new}"]`
3. Add locale config to `LOCALE_CONFIG` in `CollectionsAssistant.tsx`
4. App auto-serves at `/{locale}/...` routes

## Key Component Behavior

The `CollectionsAssistant` component simulates a live collections call:
- Transcript items stream in every 2 seconds (Framer Motion `fadeInUp` entrance)
- AI insight flash cards appear every 2.8 seconds (Framer Motion `cardSlideIn` entrance)
- High-priority cards have infinite `borderColor` pulse via Framer Motion
- Disposition form auto-fills after 8+ transcript items
- Call timer ticks while call is active
- Waveform canvas animates based on call state
- Sentiment bar tracks customer mood across utterances (Framer Motion `segmentFadeIn`)
- Language switcher dropdown in header (shadcn DropdownMenu)

## Conventions

- Always use latest library documentation and APIs — avoid deprecated patterns
- Next.js 16: Use `proxy.ts` (not `middleware.ts`), named `proxy` export
- Use Framer Motion for all component animations — no CSS `animation` properties in JSX
- Use Lucide React for icons — no emoji icons in the UI
- Use shadcn/ui for complex interactive UI elements (dropdowns, dialogs, etc.)
- Use inline styles for the collections assistant (matches pixel-precise prototype)
- Use Tailwind classes for page-level layouts (home page, wrappers) and shadcn components
- Keep all translatable strings in `messages/{locale}.json`, never hardcode UI text in components
- Types go in `src/types/`, mock data in `src/data/`, theme config in `src/config/`
- Use `as const` on Framer Motion transition `ease` values for proper TypeScript typing
