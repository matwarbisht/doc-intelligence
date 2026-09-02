# Design System

The Stage 1 design system is intentionally lightweight. It uses Inter, Radix Colors, CSS custom properties, SCSS Modules, and native React elements.

## Architecture

```text
Radix Olive / Amber / Red / Green scales
                    ↓
primitive aliases in styles/tokens/_colors.scss
                    ↓
semantic colors in styles/tokens/_semantic.scss
                    ↓
SCSS Modules
                    ↓
React components and product screens
```

Components should normally use semantic color tokens such as `--color-surface`, `--color-text-primary`, and `--color-primary`. They may use the shared spacing, typography, radius, shadow, motion, and z-index scales directly.

Do not use raw Radix variables, arbitrary colors, Tailwind classes, shadcn components, or CSS-in-JS in normal application components.

## Token files

```text
apps/web/src/styles/
├── globals.scss
└── tokens/
    ├── _colors.scss
    ├── _semantic.scss
    ├── _spacing.scss
    ├── _typography.scss
    ├── _radius.scss
    ├── _shadows.scss
    ├── _motion.scss
    └── _z-index.scss
```

Add a semantic token when a stable UI meaning appears in multiple places. Avoid component-specific token proliferation.

## Components

The v1 component set contains:

- `Button`: primary, secondary, ghost, and danger variants
- `Input`: a styled native input that accepts native props
- `Card`: a minimal surface container

These primitives live under `apps/web/src/components/` and use SCSS Modules. Complex future primitives such as dialogs, selects, popovers, and tooltips should use Base UI for accessible behavior, but Base UI should not be installed until one is needed.

## Theme behavior

The supported preferences are `light`, `dark`, and `system`.

- Explicit preferences persist in `localStorage` under `doc-intelligence-theme`.
- Dark mode is represented by a `.dark` class on the root `<html>` element.
- System mode follows `prefers-color-scheme` and listens for OS changes.
- A small script in `index.html` applies the initial theme before React renders.

The theme utility lives at `apps/web/src/theme/theme.ts`. No global state library or React context is required solely for theme switching.

## Playground

Run the application and open `/style-guide` to inspect:

- semantic colors;
- typography sizes, weights, and hierarchy;
- Button variants and disabled states;
- Input normal, focus, and disabled states;
- Card styling; and
- light, dark, and system themes.

Use the playground to tune shared tokens before adding local component overrides.
