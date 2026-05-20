---
name: frontend-tailwind
description: Tailwind CSS mastery - v3 and v4, design tokens, responsive design, component patterns, performance optimization, advanced techniques, and production deployment
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: frontend
  paradigm: utility-first
  capabilities:
    - utility-first-principles
    - responsive-design
    - design-tokens
    - component-patterns
    - custom-configuration
    - performance-optimization
    - animation-transition
    - dark-mode
    - accessibility
    - tailwind-v4
  integrates_with:
    - frontend-react
    - frontend-svelte
    - frontend-animation
---

## Frontend Tailwind CSS Skill

### Core Philosophy & Mental Model

#### Utility-First vs Component CSS

```
Traditional CSS (component)              Tailwind CSS (utility-first)
─────────────────────────────            ─────────────────────────────

.btn {                                    <button class="
  display: inline-flex;                     inline-flex
  align-items: center;                      items-center
  padding: 0.5rem 1rem;                    px-4 py-2
  border-radius: 0.375rem;                 rounded-md
  background: #3b82f6;                     bg-blue-500
  color: white;                            text-white
  font-weight: 600;                        font-semibold
}                                         ">

Naming problem                            No naming overhead
Context switching                          Co-located styles
Dead code risk                            Zero unused CSS
Specificity wars                          No specificity issues
File hopping                              Style in same file
```

When you write `.btn-primary { @apply bg-blue-500 text-white px-4 py-2 }` you are just recreating CSS classes - you lose the utility-first advantage.

#### Decision Tree: When to Use What

```
Need to style something?

  |
  v
Is it a SHARED design system component?     Tailwind utility classes
  (Button, Input, Modal, Badge)             are ALWAYS the first
        |                                   choice. Start here.
   -----+-----
   YES       NO
   |          |
   v          v
Use Tailwind   Tailwind handles EVERYTHING
+ @apply for   you used to write CSS for.
the component  Just use utility classes
shell.         directly in your JSX/HTML.
Keep utilities
for variants
        |
        v
Can it be done with Tailwind utilities?    --> YES -> use utilities
        |
        NO - is it one-off?                --> YES -> use arbitrary value w-[32rem]
        |
        NO - is it repeatable pattern?     --> YES -> extract to component
        |
        NO - truly dynamic CSS?            --> CSS-in-JS (rare)
```

#### The Infinite Combinations Mental Model

Tailwind gives you primitive atoms. Every combination creates a unique style.

```
Atoms:                                    Combinations:
  bg-{color}-{shade}                        bg-blue-500 hover:bg-blue-600
  text-{color}-{shade}                       text-white font-bold
  p-{size}                                  p-4 rounded-lg shadow-md
  m-{size}                                  mx-auto max-w-7xl
  flex / grid                               flex items-center gap-4
  rounded-{size}                            rounded-full
  shadow-{size}                             shadow-xl
  border-{color}-{shade}                    border border-gray-200

10 color shades x 5 sizes x 5 variants x 5 layout props
= ~10,000+ design possibilities per component
```

You never write `.profile-card { ... }` again. You compose:
```html
<div class="rounded-xl bg-white p-6 shadow-sm hover:shadow-md transition-shadow">
```

---

### Tailwind v3 Deep Dive

#### Core Concepts

**Utility Classes** - single-purpose classes that do one thing:
```
w-4      -> width: 1rem      (16px)
p-3      -> padding: 0.75rem  (12px)
text-lg  -> font-size: 1.125rem; line-height: 1.75rem
bg-red-500 -> background-color: #ef4444
```

**Modifiers** - conditional variants applied with colon syntax:
```
hover:bg-blue-600      -> applies on hover
md:text-center         -> applies at >=768px
dark:bg-gray-800       -> applies in dark mode
focus:ring-2           -> applies on focus
```

**Variants** - combine modifiers with utilities:
```
lg:dark:hover:bg-gray-700
   ^     ^    ^     ^
breakpoint  mode  state  utility
```

#### Spacing System

Tailwind uses a 4-point rem scale (0.25rem = 4px increments):

```
Size  rem    px    Usage
0     0      0     reset
px    px     1px   borders, dividers
0.5   0.125  2px   tightest spacing
1     0.25   4px   icon padding
1.5   0.375  6px   tight spacing
2     0.5    8px   small padding
2.5   0.625  10px  x-small
3     0.75   12px  default padding
3.5   0.875  14px  between default and 4
4     1      16px  standard padding
5     1.25   20px  medium padding
6     1.5    24px  large padding
7     1.75   28px  between 6 and 8
8     2      32px  x-large padding
9     2.25   36px  between 8 and 10
10    2.5    40px  xx-large
11    2.75   44px  between 10 and 12
12    3      48px  section spacing, cards
14    3.5    56px  wide spacing
16    4      64px  layout gap
20    5      80px  section margin
24    6      96px  max spacing
28    7      112px page margins
32    8      128px extreme
36    9      144px extreme
40    10     160px hero spacing
44    11     176px jumbo
48    12     192px jumbo
52    13     208px mega
56    14     224px mega
60    15     240px ultra
64    16     256px ultra
72    18     288px hero
80    20     320px hero
96    24     384px page
```

**Key insight**: The spacing system is consistent across ALL properties - `p-4`, `m-4`, `gap-4`, `w-4`, `h-4`, `inset-4` all refer to the same `1rem = 16px`.

#### Breakpoint System (Mobile-First)

```
Default  < 640px        No prefix      base styles (mobile)
sm       >= 640px        @media (min-width: 640px)
md       >= 768px        @media (min-width: 768px)
lg       >= 1024px       @media (min-width: 1024px)
xl       >= 1280px       @media (min-width: 1280px)
2xl      >= 1536px       @media (min-width: 1536px)
```

**Mobile-first means**: Start with base styles for smallest screens, then override upwards:
```html
<div class="flex flex-col md:flex-row lg:grid lg:grid-cols-3">
```

**Max-width breakpoints** (use sparingly): `max-sm:`, `max-md:`, `max-lg:`, `max-xl:`, `max-2xl:`

#### Custom Values with Square Bracket Notation

```html
<div class="w-[32rem] top-[37%] bg-[#1da1f1]">
<div class="text-[clamp(1rem,5vw,3rem)] gap-[calc(100%-20rem)]">
<div class="grid-cols-[1fr_2fr_1fr]">
<div class="shadow-[0_10px_40px_rgba(0,0,0,0.12)]">
<div class="bg-[oklch(0.5_0.2_240)] text-[rgb(255_0_0_/_50%)]">
```

#### Arbitrary Properties

Set ANY CSS property with square brackets - no plugin needed:
```html
<div class="[--scrollbar-width:5px] [scrollbar-width:var(--scrollbar-width)]">
<div class="[accent-color:#c96442] [column-count:2]">
<div class="[view-transition-name:hero] [object-view-box:inset(10%)]">
<div class="[color:theme(colors.blue.500)] [border-color:theme(colors.gray.200/50%)]">
```

#### Dark Mode

Two strategies:
```js
// tailwind.config.js
module.exports = {
  darkMode: 'class',   // RECOMMENDED: toggle class on <html>
  // darkMode: 'media' // Alternative: follows OS preference
}
```

**Class-based** (recommended - you control when dark mode activates):
```html
<html class="dark">
  <body class="bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100">
    <div class="bg-gray-100 dark:bg-gray-800">
      <h1 class="text-gray-900 dark:text-white">Title</h1>
      <p class="text-gray-600 dark:text-gray-400">Body text</p>
    </div>
  </body>
</html>
```

**Media-based** (simpler, follows OS):
```html
<body class="bg-white dark:bg-black">
```

JS toggle for class-based:
```js
document.documentElement.classList.toggle('dark')
localStorage.setItem('theme', 'dark')
document.documentElement.classList.toggle('dark',
  localStorage.getItem('theme') === 'dark' ||
  (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)
)
```

#### State Variants

```html
<button class="
  bg-blue-500
  hover:bg-blue-600          /* hover state */
  focus:outline-none          /* remove default outline */
  focus:ring-2                /* custom focus ring */
  focus:ring-blue-400
  focus:ring-offset-2
  active:bg-blue-700          /* click moment */
  disabled:opacity-50         /* disabled state */
  disabled:cursor-not-allowed
">
```

```html
<input class="
  border border-gray-300
  focus:border-blue-500
  invalid:border-red-500       /* :invalid pseudo-class */
  valid:border-green-500       /* :valid pseudo-class */
  required:border-l-4          /* :required pseudo-class */
  read-only:bg-gray-50         /* :read-only pseudo-class */
  disabled:bg-gray-100
  placeholder:text-gray-400    /* ::placeholder */
  autofill:shadow-[inset_0_0_0_100px_white] /* :autofill */
">
```

```html
<input type="file" class="
  file:mr-4                    /* ::file-selector-button */
  file:rounded-full
  file:border-0
  file:bg-blue-50
  file:px-4
  file:py-2
  file:text-sm
  file:font-semibold
  file:text-blue-700
  hover:file:bg-blue-100
">
```

#### Group and Peer Modifiers

**Group** - style parent based on its state:
```html
<div class="group relative">
  <div class="opacity-0 group-hover:opacity-100 transition-opacity">
  <div class="scale-95 group-hover:scale-100 transition-transform">
  <div class="group-focus-within:border-blue-500">
  <div class="group-active:bg-gray-100">
```

**Named groups** (Tailwind v3.3+):
```html
<div class="group/item">
  <button class="opacity-0 group-hover/item:opacity-100">Show</button>
</div>
<div class="group/card">
  <h3 class="group-hover/card:text-blue-600">Title</h3>
</div>
```

**Peer** - style a sibling based on another sibling's state:
```html
<input type="email" class="peer" />
<div class="peer-invalid:block hidden">Invalid email</div>
<div class="peer-disabled:opacity-50">Label</div>
<div class="peer-placeholder-shown:hidden">Clear button</div>
```

**Named peers** (Tailwind v3.3+):
```html
<input type="radio" name="plan" class="peer/plan1" />
<label class="peer-checked/plan1:border-blue-500 ...">Plan 1</label>
```

#### Pseudo-Elements

```html
<div class="
  before:content-['star']
  before:text-yellow-400
  before:mr-1
  after:content-['_->_']
  after:text-gray-400
  after:ml-1
">
  Starred Item
</div>

<div class="selection:bg-blue-200 selection:text-blue-900">
  Select this text to see custom styling.
</div>

<input class="placeholder:text-gray-400 placeholder:italic" />

<details class="marker:text-blue-500 open:bg-gray-50">
  <summary>Click me</summary>
</details>

<p class="first-line:uppercase first-line:tracking-widest
          first-letter:text-7xl first-letter:font-bold first-letter:float-left">
  Once upon a time...
</p>
```

#### Media Query Variants

```html
<div class="grid grid-cols-2 portrait:grid-cols-1">
<div class="landscape:flex-row portrait:flex-col">
<div class="no-print:shadow-lg print:text-black print:bg-white">
<div class="motion-safe:animate-bounce motion-reduce:animate-none">
<div class="contrast-more:border-2 contrast-more:border-gray-800">
<div class="forced-colors:border-[ButtonText] forced-colors:outline-none">
```

#### Container Queries (Tailwind v3.4+)

Requires `@tailwindcss/container-queries` plugin:
```js
module.exports = {
  plugins: [require('@tailwindcss/container-queries')],
}
```

```html
<div class="@container">
  <div class="grid @sm:grid-cols-2 @md:grid-cols-3 @lg:grid-cols-4">

  </div>
</div>

<div class="@container/sidebar">
  <div class="@min-[400px]/sidebar:text-lg">Fluid text</div>
</div>

<div class="@[30rem]:text-2xl">
```

---

### Tailwind v4 Deep Dive

#### CSS-Based Configuration (No JS Config File)

Tailwind v4 removes `tailwind.config.js`. Everything is configured in CSS:

```css
/* app.css */
@import "tailwindcss";

/* That is it. No config file needed. */
```

The entire framework is configured via CSS directives:
```css
@import "tailwindcss";
@theme {
  /* Everything goes here */
}
```

#### @theme Directive - Design Tokens in CSS

```css
@import "tailwindcss";

@theme {
  /* Colors */
  --color-primary: #c96442;
  --color-primary-light: #e08b6e;
  --color-primary-dark: #a14a30;
  --color-secondary: #4a7c8c;
  --color-surface: #ffffff;
  --color-surface-secondary: #f4f4f5;
  --color-text-primary: #18181b;
  --color-text-secondary: #52525b;
  --color-border: #e4e4e7;

  /* Spacing */
  --spacing-section: 5rem;
  --spacing-gutter: 1.25rem;

  /* Typography */
  --font-heading: "Inter", sans-serif;
  --font-body: "Inter", sans-serif;
  --font-mono: "JetBrains Mono", monospace;

  /* Font sizes with line height */
  --text-xs: 0.75rem;
  --text-xs--line-height: 1rem;
  --text-sm: 0.875rem;
  --text-sm--line-height: 1.25rem;
  --text-base: 1rem;
  --text-base--line-height: 1.5rem;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1);

  /* Breakpoints */
  --breakpoint-sm: 40rem;
  --breakpoint-md: 48rem;
  --breakpoint-lg: 64rem;
  --breakpoint-xl: 80rem;
  --breakpoint-2xl: 96rem;

  /* Border radius */
  --radius-sm: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-xl: 0.75rem;
  --radius-2xl: 1rem;
  --radius-3xl: 1.5rem;

  /* Animations */
  --animate-fade-in: fade-in 0.2s ease-out;
  --animate-slide-up: slide-up 0.3s ease-out;
  --animate-scale: scale 0.2s ease-out;

  /* Z-index scale */
  --z-dropdown: 100;
  --z-sticky: 200;
  --z-overlay: 300;
  --z-modal: 400;
  --z-toast: 500;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes scale {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
```

**All @theme variables become Tailwind utilities automatically:**
```
--color-primary          -> bg-primary, text-primary, border-primary
--spacing-section       -> p-section, m-section, gap-section
--font-heading          -> font-heading
--text-xs               -> text-xs
--shadow-lg             -> shadow-lg
--animate-fade-in       -> animate-fade-in
--z-modal               -> z-modal
```

#### @variant / @custom-variant

```css
@variant dark (&:where(.dark, .dark *));
@variant reduced (&:where(.reduced-motion, .reduced-motion *));

/* Use: dark:bg-black reduced:animate-none */

/* Complex variants */
@variant not-first (&:not(:first-child)) {
  margin-top: 1rem;
}

@variant landscape (&:where(@media (orientation: landscape))) {
  flex-direction: row;
}

@custom-variant peer-checked (&:where(.peer:checked ~ &)) {
  background: blue;
}
```

#### The New Default Scales (v4 vs v3)

**Colors**: v4 uses OKLCH color space - more perceptually uniform:
```
v3: bg-blue-500    -> #3b82f6  (hex, sRGB)
v4: bg-blue-500    -> oklch(0.62 0.19 261.3)  (perceptually uniform)
```

**v4 default color palette** is refined - some shades shifted:
```
v3: 22 colors x 11 shades = 242 color classes
v4: Core palette reduced, focus on custom via @theme
```

#### Migration v3 -> v4: What Changed

```
v3                               v4
tailwind.config.js               @import "tailwindcss" + @theme
module.exports = { theme: {} }   @theme { --color-*: ... }
darkMode: 'class'                @variant dark (...)
@apply bg-blue-500               Same (still works)
w-[32rem]                        Same (still works)
plugins: [require(...)]          @plugin "..."
safelist: ['bg-red-500']         @utility with !important
@tailwind base/components/...    @import "tailwindcss"
```

**What broke in v4**:
- `tailwind.config.js` is IGNORED - must migrate to CSS
- Custom `theme.extend` becomes `@theme { --color-* }`
- `@tailwind` directives removed, just `@import "tailwindcss"`
- `safelist` becomes `@utility` with important
- `variants` config becomes `@variant` in CSS
- `screens` config becomes `@theme { --breakpoint-* }`
- `darkMode: 'class'` becomes `@custom-variant dark`
- Some class names changed (OKLCH color shifts)

**Migration approach**:
```
1. Remove tailwind.config.js
2. Replace @tailwind directives with @import "tailwindcss"
3. Move theme config to @theme { } block
4. Add @variant dark if you used darkMode: 'class'
5. Add @plugin for PostCSS plugins
6. Run build, fix changed class names
7. Check for color differences (OKLCH vs sRGB)
```

---

### Design System Architecture

#### Design Tokens Structure

```js
// tailwind.config.js (v3)
module.exports = {
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: '#ffffff',
      black: '#000000',
      primary: {
        50:  '#fef5ee',
        100: '#fde8d4',
        200: '#fbcfa7',
        300: '#f9b07a',
        400: '#f79252',
        500: '#c96442',
        600: '#a14a30',
        700: '#7a3622',
        800: '#542516',
        900: '#2e140b',
      },
      secondary: {
        50:  '#f0f7f9',
        100: '#d9ebf0',
        200: '#b3d7e1',
        300: '#8dc3d2',
        400: '#67afc3',
        500: '#4a7c8c',
        600: '#3b6370',
        700: '#2c4a54',
        800: '#1d3138',
        900: '#0e181c',
      },
      gray: {
        50:  '#fafafa',
        100: '#f4f4f5',
        200: '#e4e4e7',
        300: '#d4d4d8',
        400: '#a1a1aa',
        500: '#71717a',
        600: '#52525b',
        700: '#3f3f46',
        800: '#27272a',
        900: '#18181b',
        950: '#09090b',
      },
    },
    fontFamily: {
      heading: ['Inter', 'system-ui', 'sans-serif'],
      body: ['Inter', 'system-ui', 'sans-serif'],
      mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
    },
    fontSize: {
      'xs':    ['0.75rem',  { lineHeight: '1rem' }],
      'sm':    ['0.875rem', { lineHeight: '1.25rem' }],
      'base':  ['1rem',     { lineHeight: '1.5rem' }],
      'lg':    ['1.125rem', { lineHeight: '1.75rem' }],
      'xl':    ['1.25rem',  { lineHeight: '1.75rem' }],
      '2xl':   ['1.5rem',   { lineHeight: '2rem' }],
      '3xl':   ['1.875rem', { lineHeight: '2.25rem' }],
      '4xl':   ['2.25rem',  { lineHeight: '2.5rem' }],
      '5xl':   ['3rem',     { lineHeight: '1.16' }],
      '6xl':   ['3.75rem',  { lineHeight: '1.1' }],
      '7xl':   ['4.5rem',   { lineHeight: '1.05' }],
      '8xl':   ['6rem',     { lineHeight: '1' }],
      '9xl':   ['8rem',     { lineHeight: '1' }],
    },
    extend: {
      boxShadow: {
        'xs':  '0 1px 2px 0 rgb(0 0 0 / 0.03)',
        'soft': '0 2px 15px -3px rgb(0 0 0 / 0.07), 0 10px 20px -2px rgb(0 0 0 / 0.04)',
        'glow': '0 0 15px rgb(59 130 246 / 0.5)',
      },
    },
  },
}
```

#### Shadow/Elevation System

```js
// Design system - map shadows to elevation levels
const shadows = {
  'none':    '0 0 transparent',
  'sm':      '0 1px 2px 0 rgb(0 0 0 / 0.03)',
  'DEFAULT': '0 1px 3px 0 rgb(0 0 0 / 0.05)',
  'md':      '0 4px 6px -1px rgb(0 0 0 / 0.07)',
  'lg':      '0 10px 15px -3px rgb(0 0 0 / 0.08)',
  'xl':      '0 20px 25px -5px rgb(0 0 0 / 0.1)',
  '2xl':     '0 25px 50px -12px rgb(0 0 0 / 0.15)',
}
```

---

### Responsive Design Patterns

#### Mobile-First Workflow

```html
<div class="
  grid
  grid-cols-1             /* mobile: single column */
  sm:grid-cols-2          /* >=640px: two columns */
  md:grid-cols-3          /* >=768px: three columns */
  lg:grid-cols-4          /* >=1024px: four columns */
  gap-4
  sm:gap-6
  lg:gap-8
  p-4
  sm:p-6
  lg:p-8
">
```

#### Responsive Flex Layouts

```html
<nav class="
  flex
  flex-col                /* mobile: stacked */
  md:flex-row             /* desktop: horizontal */
  items-center
  justify-between
  gap-4
  p-4
">

<div class="
  flex
  flex-wrap
  gap-4
  justify-center          /* mobile: centered */
  md:justify-start        /* desktop: left-aligned */
">
```

#### Container Queries for Component-Level Responsiveness

```html
<div class="@container">
  <div class="
    p-4
    @sm:p-6
    @md:p-8
    @lg:grid-cols-2
  ">
```

#### Hide/Show Patterns

```html
<nav class="
  hidden                    /* hidden on mobile */
  md:flex                   /* flex on desktop */
  items-center gap-6
">

<button class="
  block                     /* visible on mobile */
  md:hidden                 /* hidden on desktop */
  p-2
">

<div class="
  fixed inset-0 bg-black/50 z-50
  md:static md:inset-auto md:bg-transparent md:z-auto
  hidden
  data-[open=true]:block
  md:data-[open=true]:block
">
```

---

### Component Patterns

#### Button System

```html
<button class="
  inline-flex items-center justify-center gap-2
  font-medium
  rounded-lg
  transition-all duration-200
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2
  disabled:pointer-events-none disabled:opacity-50
">

<!-- Size variants -->
<button class="px-2.5 py-1.5 text-xs rounded">XS</button>
<button class="px-3 py-1.5 text-sm">SM</button>
<button class="px-4 py-2 text-sm">MD</button>
<button class="px-5 py-2.5 text-base">LG</button>
<button class="px-6 py-3 text-base">XL</button>

<!-- Color variants -->
<button class="bg-blue-600 text-white hover:bg-blue-700 focus-visible:ring-blue-500">
  Primary
</button>
<button class="bg-gray-100 text-gray-900 hover:bg-gray-200 focus-visible:ring-gray-400">
  Secondary
</button>
<button class="border border-gray-300 text-gray-700 hover:bg-gray-50">
  Outline
</button>
<button class="text-gray-700 hover:bg-gray-100">
  Ghost
</button>
<button class="bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500">
  Danger
</button>
<button class="text-blue-600 hover:text-blue-700 underline underline-offset-4">
  Link
</button>

<!-- Loading state -->
<button disabled class="bg-blue-600 text-white opacity-70 cursor-not-allowed">
  <svg class="animate-spin -ml-1 h-4 w-4" viewBox="0 0 24 24">
    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
  Loading...
</button>

<!-- Full width on mobile -->
<button class="w-full sm:w-auto px-6 py-3 bg-blue-600 text-white rounded-lg font-medium">
  Full width mobile, auto desktop
</button>
```

#### Card Component

```html
<!-- Base card -->
<div class="rounded-xl border border-gray-200 bg-white shadow-sm">

<!-- Card with header, body, footer -->
<div class="rounded-xl border border-gray-200 bg-white shadow-sm divide-y divide-gray-200">
  <div class="p-6">
    <h3 class="text-lg font-semibold text-gray-900">Card Title</h3>
    <p class="text-sm text-gray-500">Card description</p>
  </div>
  <div class="p-6">
    <p class="text-gray-700">Main content goes here.</p>
  </div>
  <div class="px-6 py-4 flex items-center justify-between">
    <span class="text-sm text-gray-500">Footer</span>
    <button class="text-sm font-medium text-blue-600 hover:text-blue-700">Action</button>
  </div>
</div>

<!-- Interactive hover card -->
<div class="
  rounded-xl border border-gray-200 bg-white
  shadow-sm hover:shadow-md hover:-translate-y-0.5
  transition-all duration-200
  cursor-pointer
">
  <div class="p-6">
    <h3 class="font-semibold">Interactive</h3>
    <p class="text-sm text-gray-500 mt-1">Hover me</p>
  </div>
</div>

<!-- Stats card -->
<div class="rounded-xl border border-gray-200 bg-white p-6">
  <dt class="text-sm font-medium text-gray-500 truncate">Revenue</dt>
  <dd class="mt-1 text-3xl font-semibold text-gray-900">$45,200</dd>
  <dd class="mt-1 flex items-center gap-1 text-sm font-medium text-green-600">
    +12.5% from last month
  </dd>
</div>
```

#### Modal/Dialog

```html
<div class="relative z-50" role="dialog" aria-modal="true">
  <!-- Overlay -->
  <div class="fixed inset-0 bg-black/50 backdrop-blur-sm"></div>

  <!-- Panel -->
  <div class="fixed inset-0 z-10 flex items-center justify-center p-4">
    <div class="relative w-full max-w-lg rounded-xl bg-white shadow-xl">
      <!-- Close -->
      <button class="absolute top-4 right-4 p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100" aria-label="Close">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      <!-- Header -->
      <div class="px-6 pt-6 pb-4">
        <h2 class="text-lg font-semibold text-gray-900">Modal Title</h2>
        <p class="mt-1 text-sm text-gray-500">Description</p>
      </div>
      <!-- Body -->
      <div class="px-6 py-4">
        <p class="text-gray-700">Content here.</p>
      </div>
      <!-- Footer -->
      <div class="px-6 py-4 flex items-center justify-end gap-3 border-t border-gray-200">
        <button class="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg">Cancel</button>
        <button class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg">Confirm</button>
      </div>
    </div>
  </div>
</div>
```

#### Form Inputs

```html
<label class="block text-sm font-medium text-gray-700">Email</label>
<input type="email" class="
  block w-full
  rounded-lg border border-gray-300
  px-3 py-2
  text-sm text-gray-900
  placeholder:text-gray-400
  focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
  disabled:bg-gray-50 disabled:text-gray-500
  transition-colors
" placeholder="you@example.com" />

<select class="
  block w-full rounded-lg border border-gray-300
  px-3 py-2 pr-10
  text-sm text-gray-900 bg-white
  focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
  appearance-none
">
  <option>Option 1</option>
</select>

<label class="inline-flex items-center gap-3 cursor-pointer">
  <input type="checkbox" class="
    h-4 w-4 rounded border-gray-300 text-blue-600
    focus:ring-2 focus:ring-blue-500/20
  " />
  <span class="text-sm text-gray-700">Remember me</span>
</label>

<textarea rows="4" class="
  block w-full rounded-lg border border-gray-300
  px-3 py-2 text-sm text-gray-900
  placeholder:text-gray-400
  focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
  resize-y min-h-[80px]
" placeholder="Message..."></textarea>
```

#### Navigation Patterns

```html
<nav class="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-200">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <div class="flex items-center gap-8">
        <a href="/" class="text-xl font-bold text-gray-900">Logo</a>
        <div class="hidden md:flex items-center gap-6">
          <a href="/" class="text-sm font-medium text-gray-900">Home</a>
          <a href="/about" class="text-sm font-medium text-gray-500 hover:text-gray-900">About</a>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <button class="hidden sm:inline-flex px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg">Sign in</button>
        <button class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg">Get started</button>
      </div>
    </div>
  </div>
</nav>

<!-- Tabs -->
<div class="border-b border-gray-200">
  <nav class="flex gap-0 -mb-px" role="tablist">
    <button role="tab" aria-selected="true" class="px-4 py-3 text-sm font-medium border-b-2 border-blue-600 text-blue-600">
      Active
    </button>
    <button role="tab" aria-selected="false" class="px-4 py-3 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300">
      Inactive
    </button>
  </nav>
</div>

<!-- Breadcrumbs -->
<nav class="flex items-center gap-1 text-sm text-gray-500" aria-label="Breadcrumb">
  <a href="/" class="hover:text-gray-700">Home</a>
  <span>/</span>
  <a href="/products" class="hover:text-gray-700">Products</a>
  <span>/</span>
  <span class="text-gray-900 font-medium">Current</span>
</nav>

<!-- Pagination -->
<nav class="flex items-center justify-center gap-1" aria-label="Pagination">
  <button class="px-3 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100">Previous</button>
  <button class="px-3 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg">1</button>
  <button class="px-3 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100">2</button>
  <span class="px-2 text-gray-400">...</span>
  <button class="px-3 py-2 text-sm font-medium text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100">Next</button>
</nav>
```

#### Badges, Tags, Pills

```html
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Default</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">Blue</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Success</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">Error</span>
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">Warning</span>

<!-- Badge with dot -->
<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
  <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
  Online
</span>

<!-- Removable tag -->
<span class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800">
  React
  <button class="hover:bg-blue-200 rounded-full p-0.5" aria-label="Remove">
    <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"/></svg>
  </button>
</span>
```

#### Tables

```html
<div class="overflow-x-auto rounded-lg border border-gray-200">
  <table class="min-w-full divide-y divide-gray-200">
    <thead class="bg-gray-50">
      <tr>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
      </tr>
    </thead>
    <tbody class="bg-white divide-y divide-gray-200">
      <tr class="hover:bg-gray-50 transition-colors">
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-full bg-gray-200"></div>
            <div class="text-sm font-medium text-gray-900">John Doe</div>
          </div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">Developer</td>
        <td class="px-6 py-4 whitespace-nowrap">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Active</span>
        </td>
      </tr>
    </tbody>
  </table>
</div>

<!-- Striped table rows -->
<tbody class="bg-white divide-y divide-gray-200">
  <tr class="bg-white">  <!-- even -->
  <tr class="bg-gray-50"> <!-- odd -->
```

#### Loading Skeletons

```html
<!-- Card skeleton -->
<div class="rounded-xl border border-gray-200 bg-white p-6 space-y-4">
  <div class="w-12 h-12 rounded-full bg-gray-200 animate-pulse"></div>
  <div class="space-y-3">
    <div class="h-4 bg-gray-200 rounded animate-pulse w-3/4"></div>
    <div class="h-4 bg-gray-200 rounded animate-pulse w-1/2"></div>
  </div>
  <div class="flex gap-2 pt-2">
    <div class="h-8 w-20 bg-gray-200 rounded-lg animate-pulse"></div>
    <div class="h-8 w-20 bg-gray-200 rounded-lg animate-pulse"></div>
  </div>
</div>

<!-- Text block skeleton -->
<div class="space-y-2">
  <div class="h-4 bg-gray-200 rounded animate-pulse w-full"></div>
  <div class="h-4 bg-gray-200 rounded animate-pulse w-5/6"></div>
  <div class="h-4 bg-gray-200 rounded animate-pulse w-4/6"></div>
</div>
```

#### Toast Notifications

```html
<div class="fixed top-4 right-4 z-[60] flex flex-col gap-2 pointer-events-none">
  <div class="pointer-events-auto flex items-center gap-3 w-80 px-4 py-3 rounded-lg shadow-lg bg-white border border-gray-200" role="status">
    <div class="w-2 h-2 rounded-full bg-green-500 shrink-0"></div>
    <p class="text-sm text-gray-900 flex-1">Message sent!</p>
    <button class="text-gray-400 hover:text-gray-600" aria-label="Close">
      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"/></svg>
    </button>
  </div>
</div>
```

---

### Advanced Techniques

#### Group Selectors Deep Dive

```html
<div class="group relative rounded-xl border border-gray-200 bg-white p-6 hover:shadow-md transition-shadow">
  <h3 class="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
    Card Title
  </h3>
  <p class="text-sm text-gray-500 group-hover:text-gray-700 transition-colors">
    Content that changes on hover
  </p>
  <button class="
    opacity-0 group-hover:opacity-100
    translate-y-1 group-hover:translate-y-0
    transition-all duration-200
    mt-3 text-sm text-blue-600 font-medium
  ">
    Learn more ->
  </button>
</div>

<ul class="space-y-1">
  <li class="group/item flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50">
    <span class="text-sm text-gray-700">Item 1</span>
    <button class="opacity-0 group-hover/item:opacity-100 ml-auto text-xs text-blue-600">
      Edit
    </button>
  </li>
</ul>
```

#### Peer Modifiers Deep Dive

```html
<div class="relative">
  <input
    type="email"
    class="peer w-full rounded-lg border border-gray-300 px-3 py-2 text-sm
           focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
    placeholder="you@example.com"
    required
  />
  <p class="mt-1 text-xs text-red-500 hidden peer-invalid:peer-focus:block">
    Please enter a valid email
  </p>
</div>

<label class="relative flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer
              peer-checked/plan:border-blue-500 peer-checked/plan:bg-blue-50">
  <input type="radio" name="plan" class="peer/plan absolute opacity-0" />
  <div class="flex items-center h-5">
    <div class="w-4 h-4 rounded-full border-2
                peer-checked/plan:border-blue-500 peer-checked/plan:bg-blue-500"></div>
  </div>
  <div class="flex-1">
    <p class="text-sm font-medium text-gray-900 peer-checked/plan:text-blue-600">Pro Plan</p>
    <p class="text-sm text-gray-500">Everything in Free plus priority support</p>
  </div>
</label>
```

#### Arbitrary Selectors

```html
<!-- Style all child paragraphs -->
<div class="[&_p]:text-gray-600 [&_p]:leading-relaxed">
  <p>Styled paragraph.</p>
</div>

<!-- Direct children only -->
<div class="[&>p]:mt-4">
  <p>Direct child - styled</p>
  <div><p>Nested - NOT styled</p></div>
</div>

<!-- First/last child -->
<div class="[&_li:first-child]:font-bold [&_li:last-child]:text-gray-500">
  <li>First - bold</li>
  <li>Last - gray</li>
</div>

<!-- Data attribute -->
<div class="[&[data-active=true]]:border-blue-500" data-active="true">

<!-- Container query in arbitrary selector -->
<div class="[@container(min-width:400px)]:grid-cols-2">

<!-- !important override -->
<div class="[&]:!m-0 [&]:!p-0">
```

#### Before/After Pseudo-Elements

```html
<label class="before:content-['*'] before:text-red-500 before:mr-0.5 text-sm font-medium text-gray-700">
  Email
</label>

<a href="https://example.com" target="_blank" class="
  text-blue-600 hover:text-blue-700
  after:content-['_\2197'] after:inline-block after:text-xs after:opacity-60
">

<div class="relative before:absolute before:inset-x-0 before:top-1/2 before:h-px before:bg-gray-200
            flex items-center justify-center">
  <span class="relative bg-white px-3 text-sm text-gray-500">or continue with</span>
</div>

<blockquote class="relative pl-8
  before:absolute before:left-0 before:top-0
  before:text-4xl before:text-gray-300 before:leading-none
  before:content-['\201C']
  italic text-gray-700">
  The best way to predict the future is to create it.
</blockquote>
```

#### CSS @apply Pattern (Use With Caution)

```css
/* ANTI-PATTERN: creating CSS classes from utility classes */
.btn-primary {
  @apply bg-blue-500 text-white px-4 py-2 rounded-lg font-semibold;
}
/* This loses the utility-first advantage entirely. */

/* WHEN @apply IS ACCEPTABLE: */
/* 1. Third-party wrapper (can't change HTML) */
.custom-select {
  @apply block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm;
}

/* 2. Global base layer */
@layer base {
  h1 { @apply text-2xl font-bold text-gray-900; }
  a { @apply text-blue-600 hover:text-blue-800 underline-offset-2 hover:underline; }
}
```

#### Functions in Arbitrary Values

```html
<div class="bg-[theme(colors.blue.500)] p-[theme(spacing.4)]">
<div class="text-[theme(colors.gray.400/50%)]">
<div class="shadow-[theme(boxShadow.lg)]">
<div class="w-[calc(100%-2rem)] h-[calc(100vh-4rem)]">
<div class="min-h-[calc(100dvh-var(--navbar-height))]">
<div class="text-[clamp(1rem,3vw,2rem)]">
<div class="grid-cols-[repeat(auto-fit,minmax(250px,1fr))]">
<div class="bg-[color-mix(in_oklch,theme(colors.blue.500)_50%,white)]">
```

---

### Animation & Transitions

#### Transition Properties

```html
<button class="transition-all duration-200 ease-out hover:scale-105 hover:shadow-lg active:scale-95">
<div class="transition-opacity duration-300 hover:opacity-80">
<div class="transition-transform duration-150 ease-in-out group-hover:translate-x-1">

<div class="transition-colors">       <!-- color, bg, border-color -->
<div class="transition-opacity">      <!-- opacity -->
<div class="transition-shadow">        <!-- box-shadow -->
<div class="transition-transform">     <!-- transform -->
<div class="transition-all">           <!-- everything (use sparingly) -->

<div class="transition duration-75">    <!-- 75ms -->
<div class="transition duration-150">   <!-- 150ms -->
<div class="transition duration-200">   <!-- 200ms (default) -->
<div class="transition duration-500">   <!-- 500ms -->
<div class="transition duration-1000">  <!-- 1000ms -->

<div class="transition ease-linear">    <!-- cubic-bezier(0,0,1,1) -->
<div class="transition ease-in">        <!-- cubic-bezier(0.4,0,1,1) -->
<div class="transition ease-out">       <!-- cubic-bezier(0,0,0.2,1) -->
<div class="transition ease-in-out">    <!-- cubic-bezier(0.4,0,0.2,1) -->
```

#### Animation Utilities

```html
<div class="animate-spin">     <!-- rotating spinner -->
<div class="animate-ping">     <!-- radar ping -->
<div class="animate-pulse">    <!-- skeleton shimmer -->
<div class="animate-bounce">   <!-- bouncing -->

<div class="animate-spin duration-500">
<div class="animate-pulse animate-once"> <!-- run once (v3.4+) -->
```

#### Custom Keyframes in Config

```js
// tailwind.config.js (v3)
module.exports = {
  theme: {
    extend: {
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-down': {
          from: { opacity: '0', transform: 'translateY(-10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-left': {
          from: { opacity: '0', transform: 'translateX(-10px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-in-right': {
          from: { opacity: '0', transform: 'translateX(10px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'slide-down': {
          from: { opacity: '0', transform: 'translateY(-10px) scaleY(0.95)' },
          to: { opacity: '1', transform: 'translateY(0) scaleY(1)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'wiggle': {
          '0%, 100%': { transform: 'rotate(-3deg)' },
          '50%': { transform: 'rotate(3deg)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
        'fade-in-up': 'fade-in-up 0.3s ease-out',
        'fade-in-down': 'fade-in-down 0.3s ease-out',
        'fade-in-left': 'fade-in-left 0.3s ease-out',
        'fade-in-right': 'fade-in-right 0.3s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
        'slide-down': 'slide-down 0.2s ease-out',
        'shimmer': 'shimmer 2s infinite linear',
        'wiggle': 'wiggle 0.3s ease-in-out',
        'float': 'float 3s ease-in-out infinite',
      },
    },
  },
}
```

---

### Typography with @tailwindcss/typography

```js
module.exports = {
  plugins: [require('@tailwindcss/typography')],
}
```

```html
<article class="prose prose-lg mx-auto">
  <h1>Article Title</h1>
  <p>Content with automatic styling for headings, links, lists, code.</p>
  <blockquote>Blockquotes styled automatically</blockquote>
</article>

<!-- Custom prose modifiers -->
<article class="prose prose-gray prose-lg dark:prose-invert
              prose-headings:text-blue-600
              prose-a:text-blue-600 prose-a:no-underline
              prose-code:text-pink-500
              prose-pre:bg-gray-900
              prose-img:rounded-xl
              prose-li:marker:text-gray-400">

<!-- Text balancing -->
<h1 class="text-balance">This heading breaks naturally without orphan words</h1>

<!-- Truncation -->
<p class="truncate">Single line truncation with ellipsis...</p>
<p class="line-clamp-2">Clamped to 2 lines with ellipsis...</p>
<p class="line-clamp-3">Clamped to 3 lines</p>
```

---

### Performance Optimization

#### How the JIT Engine Works

```
JIT Engine Pipeline:

1. Scan content files for class names
   (glob patterns from content config)

2. Extract all unique class names
   bg-blue-500, p-4, text-lg, hover:bg-blue-600

3. Parse modifiers
   lg:dark:hover:bg-gray-700
   -> breakpoint(lg) -> dark -> hover -> bg-gray-700

4. Generate CSS rules (only for what is found)
   .bg-blue-500 { background-color: #3b82f6; }

5. Output CSS file (typically < 10KB for prod)
```

**What triggers a rebuild**: saving a content file, changing config, adding new classes.

#### Content Paths Configuration

```js
// tailwind.config.js - CRITICAL for production
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './public/**/*.html',
    // Include component libraries
    './node_modules/@shadcn/ui/dist/**/*.js',
    './node_modules/@radix-ui/**/*.js',
  ],
}
```

#### File Size Budget Recommendations

```
Application Type        Max CSS Budget
Landing page            < 10KB
Blog / Docs             5-15KB
Dashboard / SaaS       10-25KB
Large enterprise app   15-40KB

If CSS > 50KB:
  - Check for dynamic class names
  - Review content glob patterns
  - Check for unused @apply rules
```

#### Dynamic Class Construction (Anti-Pattern)

```jsx
// BAD: JIT cannot scan these template literals
function BadButton({ color, size }) {
  return <button className={`bg-${color}-500 p-${size}`}>Click</button>
}

// GOOD: use complete class names
function GoodButton({ color = 'blue' }) {
  const colorMap = {
    blue: 'bg-blue-500 text-white hover:bg-blue-600',
    red: 'bg-red-500 text-white hover:bg-red-600',
    green: 'bg-green-500 text-white hover:bg-green-600',
  }
  return <button className={colorMap[color]}>Click</button>
}

// GOOD: data attributes
function DataButton({ variant }) {
  return (
    <button
      data-variant={variant}
      className="data-[variant=primary]:bg-blue-500 data-[variant=primary]:text-white
                 data-[variant=secondary]:bg-gray-100 data-[variant=secondary]:text-gray-900"
    >Click</button>
  )
}

// GOOD: cn() helper
import { cn } from '@/lib/utils'

function CtaButton({ variant = 'primary', className }) {
  return (
    <button className={cn(
      'px-4 py-2 rounded-lg font-medium transition-colors',
      variant === 'primary' && 'bg-blue-500 text-white hover:bg-blue-600',
      variant === 'secondary' && 'bg-gray-100 text-gray-900 hover:bg-gray-200',
      className
    )}>Click</button>
  )
}
```

#### Safelist Patterns

```js
module.exports = {
  safelist: [
    'bg-red-500',
    'text-center',
    {
      pattern: /^bg-(red|blue|green|yellow)-(400|500|600)$/,
      variants: ['hover', 'dark'],
    },
    {
      pattern: /^(border|bg|text)-(slate|gray|zinc)-(50|100|200|300|400|500|600|700|800|900)$/,
      variants: ['dark', 'hover'],
    },
  ],
}
```

#### Class Extraction Order Optimization

```jsx
// Use prettier-plugin-tailwindcss for auto-sorting
// Order: Layout -> Flex/Grid -> Spacing -> Sizing -> Typography -> Visual -> Effects -> Modifiers
//
// BEFORE: "px-4 py-2 bg-blue-500 text-white rounded-lg flex items-center"
// AFTER:  "flex items-center rounded-lg bg-blue-500 px-4 py-2 text-white"
```

---

### Dark Mode Strategy

#### Class-Based vs Media-Based

```
Decision: Which dark mode strategy?

Do users need to toggle? --> YES --> class-based
  (sun/moon button)
        |
        NO
        v
Does the app follow OS preference? --> YES --> media-based
        |
        NO
        v
Use class-based (most flexible)
```

#### Component Dark Mode Patterns

```html
<!-- Cards -->
<div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
            shadow-sm dark:shadow-gray-900/50">

<!-- Text -->
<p class="text-gray-900 dark:text-gray-100">Primary text</p>
<p class="text-gray-600 dark:text-gray-400">Secondary text</p>

<!-- Buttons -->
<button class="bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-600 dark:hover:bg-blue-700">

<!-- Overlays -->
<div class="bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm">

<!-- Code blocks -->
<pre class="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
```

#### Color System for Dark Mode

```
Light Background      -> Dark Background
bg-white              -> bg-gray-950
bg-gray-50            -> bg-gray-900
bg-gray-100           -> bg-gray-800
text-gray-900         -> text-gray-100
text-gray-600         -> text-gray-400
border-gray-200       -> border-gray-700
```

#### Images in Dark Mode

```html
<picture>
  <source srcset="/logo-dark.svg" media="(prefers-color-scheme: dark)" />
  <img src="/logo-light.svg" alt="Logo" class="h-8" />
</picture>

<!-- Or, with class-based toggle -->
<img src="/logo.svg" class="dark:hidden" alt="Logo" />
<img src="/logo-dark.svg" class="hidden dark:block" alt="Logo" />
```

---

### Accessibility with Tailwind

#### Focus Ring Patterns

```html
<button class="
  px-4 py-2 rounded-lg font-medium
  bg-blue-500 text-white
  transition-all duration-150
  hover:bg-blue-600
  focus-visible:outline-none focus-visible:ring-2
  focus-visible:ring-blue-500 focus-visible:ring-offset-2
  active:bg-blue-700
  disabled:opacity-50 disabled:cursor-not-allowed
">

<a href="#" class="
  text-blue-600 hover:text-blue-700 underline-offset-2 hover:underline
  focus-visible:outline-none focus-visible:ring-2
  focus-visible:ring-blue-500 focus-visible:rounded
">
```

#### Color Contrast with Tailwind Colors

```
Background    Text Color      Contrast Ratio   WCAG
bg-white      text-gray-900   17.4:1           AAA
bg-white      text-gray-700   10.3:1           AAA
bg-white      text-gray-500   6.1:1            AA
bg-white      text-gray-400   4.1:1            AA (large only)
bg-white      text-gray-300   2.5:1            FAIL
bg-blue-500   text-white      4.6:1            AA
bg-blue-600   text-white      5.3:1            AA
```

#### Reduced Motion

```html
<div class="animate-bounce motion-reduce:animate-none">
<button class="transition-transform hover:scale-105 motion-reduce:transition-none motion-reduce:hover:scale-100">
<div class="motion-safe:animate-fade-in-up motion-reduce:animate-fade-in">
```

#### Screen Reader Only

```html
<span class="sr-only">Only for screen readers</span>

<!-- Skip navigation link -->
<a href="#main" class="
  sr-only focus:not-sr-only
  focus:absolute focus:top-4 focus:left-4
  focus:z-50 focus:px-4 focus:py-2
  focus:bg-white focus:text-blue-600 focus:rounded-lg
  focus:shadow-lg focus:ring-2 focus:ring-blue-500
">
  Skip to main content
</a>
```

---

### Integration with Frameworks

#### Next.js + Tailwind

```css
/* v3: app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* v4: app/globals.css */
@import "tailwindcss";
```

#### Vite + Tailwind

```js
// vite.config.js (v4)
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss()],
})
```

#### shadcn/ui Compatibility

```js
module.exports = {
  darkMode: ['class'],
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: { '2xl': '1400px' },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
```

#### Radix UI + Tailwind

```html
<Dialog.Root>
  <Dialog.Trigger class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">
    Open
  </Dialog.Trigger>
  <Dialog.Portal>
    <Dialog.Overlay class="fixed inset-0 bg-black/50 backdrop-blur-sm data-[state=open]:animate-fade-in" />
    <Dialog.Content class="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
                          w-full max-w-md rounded-xl bg-white p-6 shadow-xl
                          data-[state=open]:animate-fade-in-up">
      <Dialog.Title class="text-lg font-semibold text-gray-900">Title</Dialog.Title>
      <Dialog.Description class="mt-2 text-sm text-gray-500">Description</Dialog.Description>
      <div class="mt-4 flex justify-end gap-3">
        <Dialog.Close class="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg">
          Cancel
        </Dialog.Close>
      </div>
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>
```

---

### Testing Tailwind Components

#### Visual Regression Testing

```tsx
// Button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './Button'

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
  argTypes: {
    variant: { control: 'select', options: ['primary', 'secondary', 'outline', 'ghost'] },
    size: { control: 'select', options: ['sm', 'md', 'lg'] },
  },
}

export const AllVariants: StoryObj = {
  render: () => (
    <div class="flex gap-4">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="outline">Outline</Button>
    </div>
  ),
}

export const DarkMode: StoryObj = {
  parameters: { themes: { themeOverride: 'dark' } },
  args: { variant: 'primary', children: 'In dark mode' },
}
```

#### Snapshot Testing

```tsx
import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Button } from './Button'

describe('Button', () => {
  it('renders with Tailwind classes', () => {
    const { container } = render(<Button variant="primary">Click</Button>)
    const button = container.firstChild as HTMLElement
    expect(button.className).toContain('bg-blue-500')
    expect(button.className).toContain('rounded-lg')
  })

  it('matches snapshot for variants', () => {
    const { container } = render(<Button variant="primary">Primary</Button>)
    expect(container.firstChild).toMatchSnapshot('primary')
  })
})
```

#### Testing Responsive Behavior

```ts
import { test, expect } from '@playwright/test'

test('sidebar hidden on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/dashboard')
  await expect(page.locator('[data-testid="sidebar"]')).toBeHidden()

  await page.setViewportSize({ width: 1280, height: 800 })
  await expect(page.locator('[data-testid="sidebar"]')).toBeVisible()
})
```

---

### File Convention

```
src/
+-- components/
|   +-- ui/                     # Reusable UI primitives
|   |   +-- Button/
|   |   |   +-- Button.tsx      # Component with Tailwind classes
|   |   |   +-- Button.stories.tsx
|   |   |   +-- Button.test.tsx
|   |   |   +-- index.ts
|   |   +-- Card/
|   |   +-- Input/
|   |   +-- Modal/
|   +-- layout/                  # Layout components
|   |   +-- Sidebar.tsx
|   |   +-- Navbar.tsx
|   +-- features/                # Feature-specific components
|       +-- dashboard/
|           +-- StatsCard.tsx
+-- styles/
|   +-- globals.css             # Tailwind imports + @theme
|   +-- components.css          # @apply (only if really needed)
+-- lib/
|   +-- utils.ts                # cn() helper
+-- tailwind.config.js          # v3 only - v4 uses globals.css
```

---

### Anti-Patterns (with Fixes)

#### 1. Dynamic Class Concatenation

```jsx
// BAD: JIT can not scan template literals
function Bad({ color }) {
  return <div className={`bg-${color}-500`} />
}

// GOOD: complete strings - JIT can scan
function Good({ color }) {
  const colors = {
    blue: 'bg-blue-500 text-blue-50',
    red: 'bg-red-500 text-red-50',
  }
  return <div className={colors[color]} />
}

// GOOD: data attributes
function Better({ variant }) {
  return <div data-variant={variant}
              className="data-[variant=blue]:bg-blue-500" />
}
```

#### 2. Overusing @apply

```css
/* BAD: recreating a utility framework */
.card {
  @apply bg-white rounded-xl border border-gray-200 shadow-sm p-6;
}

/* GOOD: use component as the abstraction */
function Card({ children }) {
  return (
    <div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      {children}
    </div>
  )
}
```

#### 3. Not Using Content Paths Correctly

```js
// BAD: too narrow
// content: ['./src/**/*.js']

// BAD: too broad - scans node_modules
// content: ['./**/*.{html,js}']

// GOOD: specific to source
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
}
```

#### 4. Inline Styles Instead of Utilities

```jsx
// BAD: inline style when Tailwind has it
<div style={{ marginTop: '1rem' }}>
<div style={{ display: 'flex', alignItems: 'center' }}>

// GOOD: use utilities
<div class="mt-4">
<div class="flex items-center">
```

#### 5. Not Leveraging group/peer

```jsx
// BAD: JS for what CSS can do
function HoverShow({ children }) {
  const [hover, setHover] = useState(false)
  return (
    <div onMouseEnter={() => setHover(true)}
         onMouseLeave={() => setHover(false)}>
      {hover && children}
    </div>
  )
}

// GOOD: pure CSS
function HoverShow({ children }) {
  return (
    <div class="group relative">
      <div class="opacity-0 group-hover:opacity-100 transition-opacity">
        {children}
      </div>
    </div>
  )
}
```

#### 6. Not Using cn() Helper

```jsx
// BAD: manual string concatenation
function Button({ primary, className }) {
  return (
    <button class={
      'px-4 py-2 rounded-lg ' +
      (primary ? 'bg-blue-500 text-white ' : 'bg-gray-100 ') +
      (className || '')
    } />
  )
}

// GOOD: cn() helper with tailwind-merge
import { cn } from '@/lib/utils'

function Button({ variant = 'primary', className }) {
  return (
    <button class={cn(
      'px-4 py-2 rounded-lg font-medium transition-colors',
      variant === 'primary' && 'bg-blue-500 text-white hover:bg-blue-600',
      variant === 'secondary' && 'bg-gray-100 text-gray-700 hover:bg-gray-200',
      className
    )} />
  )
}
```

```ts
// lib/utils.ts - the cn() helper
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

---

### Implementation Checklist

**Setup Phase**:
- [ ] Choose version: Tailwind v3 (stable) or v4 (bleeding edge, CSS-first)
- [ ] Install: npm install -D tailwindcss @tailwindcss/postcss postcss
- [ ] Configure: npx tailwindcss init -p (v3) or @import "tailwindcss" (v4)
- [ ] Set content paths to cover ALL source files
- [ ] Add plugins: typography, forms, container-queries
- [ ] Set up cn() helper: clsx + tailwind-merge
- [ ] Set up dark mode strategy (class-based recommended)

**Design System Phase**:
- [ ] Define brand colors as theme tokens (primary, secondary, accent)
- [ ] Set typography scale (font families, sizes, weights)
- [ ] Define spacing scale (extend default if needed)
- [ ] Configure shadow/elevation system
- [ ] Set border radius scale
- [ ] Define animation/transition tokens
- [ ] Create z-index scale

**Component Phase**:
- [ ] Button system: all variants, sizes, states, loading, icon
- [ ] Form inputs: text, select, checkbox, radio, file, error states
- [ ] Card: base, interactive, with image, stats
- [ ] Modal/Dialog: overlay, centered, animation
- [ ] Navigation: navbar, sidebar, tabs, breadcrumbs, pagination
- [ ] Badges, tags, pills
- [ ] Tables: responsive, striped
- [ ] Alerts: success, error, warning, info
- [ ] Dropdown menus
- [ ] Loading skeletons
- [ ] Toast notifications

**Responsive Phase**:
- [ ] Mobile-first: all components work at smallest breakpoint first
- [ ] Breakpoints: test at 375px, 768px, 1024px, 1440px
- [ ] Responsive tables with horizontal scroll
- [ ] Responsive typography (clamp or breakpoint-based)
- [ ] Touch targets >= 44px for mobile

**Accessibility Phase**:
- [ ] Focus-visible rings on all interactive elements
- [ ] Color contrast checked (AA minimum for text)
- [ ] Reduced motion respected (motion-reduce:*)
- [ ] Screen reader utilities (sr-only)
- [ ] Keyboard navigation test (Tab, Enter, Escape, Arrow keys)

**Performance Phase**:
- [ ] Production build CSS < 20KB
- [ ] Content paths configured correctly
- [ ] No dynamic class concatenation
- [ ] Safelist configured if needed

**Tooling Phase**:
- [ ] prettier-plugin-tailwindcss for class sorting
- [ ] eslint-plugin-tailwindcss for linting
- [ ] tailwind-merge for class merging with cn()
- [ ] VS Code: Tailwind CSS IntelliSense extension
- [ ] Storybook + Chromatic for visual regression testing

---

### Common Troubleshooting

#### "My Tailwind classes are not working"

1. Check content paths - is the file in a glob-matched directory?
2. Check @tailwind / @import directive is at the top of CSS file
3. Check for typos (hover: vs hover)
4. Rebuild: npx tailwindcss -i input.css -o output.css
5. Clear cache: node_modules/.cache/tailwindcss

#### "Production CSS is huge (>100KB)"

1. Dynamic class concatenation -> switch to complete strings
2. Content paths too broad -> restrict to source files only
3. Safelist too large -> reduce safelist patterns
4. Using @apply with many variants -> use component instead

#### "Classes are conflicting"

1. Install tailwind-merge and use cn() helper
2. Never use inline styles alongside Tailwind
3. Order of classes does not matter (all same specificity)
4. If using @apply, be aware of specificity stacking

#### "Dark mode not working"

1. Check darkMode config: 'class' vs 'media'
2. If 'class': verify <html class="dark"> is applied
3. Check theme persistence (localStorage)
4. Check OS preference detection
5. Verify dark:* classes exist in production build

#### "Responsive design not working"

1. Mobile-first: base styles are mobile, breakpoints add overrides
2. Check breakpoint values: md is >=768px
3. Order: apply sm* before md* before lg*
4. Use min-width (default) not max-width
5. Container queries @sm starts at container >=16rem

Common responsive mistakes:
- <div class="flex flex-col md:flex-row"> (correct)
- <div class="md:flex-col flex-row"> (wrong order - mobile-first)
