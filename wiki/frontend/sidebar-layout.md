---
type: frontend
created: 2026-05-14
source: frontend/src/components/Layout.tsx
---

# Sidebar Layout

240px slim left rail. Desktop fixed; mobile drawer.

## Structure

```
+---------+------------------+
|         | <header>         |  (no top nav in Layout - sidebar only)
| logo    +------------------+
|         |                  |
| Landing |                  |
|  ↗      |     <main>       |
| ----    |                  |
| 01 ⬆ Verify           |   page content    |
| 02 ▦ Dashboard        |                   |
| 03 📜 Fact Check      |                   |
| 04 👥 Community       |                   |
| 05 ⚖ Compare          |                   |
| 06 </> Embed          |                   |
| 07 📈 Status          |                   |
| 08 🛡 Review (staff)  |                   |
| ----    |                  |
| agent: email           |                   |
| CASE/ID · 12:34 UTC    |                   |
| [logout]               |                   |
+---------+------------------+
```

## Active indicator

`motion.span layoutId="nav-indicator"` - 1px amber bar at left edge slides between active items via Framer Motion shared layout. Spring stiffness 400 / damping 30.

## Icons

`lucide-react`:
- `Upload` (Verify)
- `LayoutDashboard`
- `ScrollText` (Fact Check)
- `Users` (Community)
- `GitCompareArrows` (Compare)
- `Code2` (Embed)
- `Activity` (Status)
- `Shield` (Review, staff)
- `Home` (Landing escape)
- `LogOut`

Size 16, strokeWidth 1.5.

## Mobile

Below `lg` breakpoint, sidebar hidden. Sticky top bar with hamburger (Menu / X icon). Click toggles drawer:

```tsx
<motion.aside
  initial={{ x: -260 }}
  animate={{ x: 0 }}
  exit={{ x: -260 }}
  transition={{ type: "spring", stiffness: 260, damping: 28 }}
>
```

Backdrop `bg-ink-950/60 backdrop-blur-sm` covers main when open. Tap outside closes.

## Content area

`<main className="lg:pl-[240px]">` offsets for sidebar. Inner container `max-w-[1280px] mx-auto px-6 lg:px-12 py-10 lg:py-14`. AnimatePresence wraps Outlet with route-keyed blur-in transition.

## See also

- [[frontend/routes]]
- [[services/frontend]]
- [[frontend/shader-bg]]
