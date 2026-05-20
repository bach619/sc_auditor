---
name: frontend-animation
description: Advanced animation patterns: Framer Motion, GSAP, Rive, Canvas/WebGL, 60fps performance, animation design system, motion tokens, accessibility, testing
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: frontend
  paradigm: animation-first
  capabilities:
    - motion-design-tokens
    - framer-motion
    - gsap
    - rive-runtime
    - canvas-webgl
    - 60fps-performance
    - animation-accessibility
    - visual-regression-testing
  integrates_with:
    - frontend-react
    - frontend-svelte
    - mobile-flutter
    - mobile-tauri
---

## Frontend Animation Skill

### Animation Architecture

#### Motion Design Tokens
Design these BEFORE writing any animation code. Tokens enforce consistency:

```
DURATION:   --dur-micro:75ms  --dur-small:150ms  --dur-medium:300ms  --dur-large:500ms  --dur-xlarge:800ms
EASING:     --ease-enter: cubic-bezier(0,0,0.2,1)     --ease-exit: cubic-bezier(0.4,0,1,1)
            --ease-standard: cubic-bezier(0.4,0,0.2,1) --ease-emphasized: cubic-bezier(0.05,0.7,0.1,1)
            --ease-bounce: cubic-bezier(0.175,0.885,0.32,1.275)
SPRINGS:    Gentle:{stiffness:100,damping:15,mass:1}  Precise:{stiffness:500,damping:40,mass:1}
            Wobbly:{stiffness:180,damping:12,mass:1}  Stiff:{stiffness:260,damping:20,mass:1}
OFFSETS:    --offset-micro:4px  --offset-small:8px  --offset-medium:16px  --offset-large:32px  --offset-xlarge:64px
```

#### Enter / Exit / Steady State Principle
Every element must define three states:

```
┌───────────────────────────────────────────────────────────┐
│              ANIMATION LIFECYCLE                           │
│                                                            │
│  [ENTER]  ───────>  [STEADY]  ───────>  [EXIT]            │
│   opacity:0          opacity:1          opacity:0          │
│   scale:0.95         scale:1            scale:0.95         │
│   translateY:20px    translateY:0       translateY:-20px   │
│                                                            │
│  Enter = ease-out (decelerating)  Steady = ease-in-out     │
│  Exit  = ease-in (accelerating)                            │
└───────────────────────────────────────────────────────────┘
```

#### Compositor-Only Properties & 60fps Frame Budget

```
Browser Pipeline: JS → Style → Layout → Paint → Composite
                                                   ▲
                            Compositor-only: ──────┘
                            transform, opacity, filter (skip layout+paint)

ONE FRAME = 16.67ms budget
┌──────────┬───────────┬──────────┬─────────────┐
│ JS <3ms  │Style <1ms │Layout<2ms│Paint+Comp   │
│          │           │          │<8ms         │
└──────────┴───────────┴──────────┴─────────────┘
  Any phase over budget → frame drop → jank → <60fps
```

- **Safe to animate**: `transform` (translate/scale/rotate/skew), `opacity`, `filter`
- **Never animate**: `width`, `height`, `top`, `left`, `margin`, `padding`, `border-width` (triggers layout)
- **Triggers paint** (expensive): `color`, `background-color`, `box-shadow`

#### prefers-reduced-motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

```tsx
// JS guard for programmatic animations
import { useReducedMotion } from 'framer-motion'

function AnimatedHero() {
  if (useReducedMotion()) return <div>Static version</div>
  return <motion.div initial={{opacity:0,y:32}} animate={{opacity:1,y:0}} transition={{duration:0.5}}>Hero</motion.div>
}
```

```js
// Vanilla JS: const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
```

---

### Framer Motion (React)

#### Core Patterns

```tsx
import { motion, AnimatePresence } from 'framer-motion'

// animate prop (implicit initial from animate values)
<motion.div animate={{ x: 100 }} transition={{ duration: 0.5 }} />

// Full lifecycle
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0, y: -20 }}
  transition={{ duration: 0.3, ease: 'easeOut' }}
>
  Content
</motion.div>
```

#### Variants & Orchestration

```tsx
const listVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,    // delay between each child
      delayChildren: 0.2,       // delay before children start
      when: 'beforeChildren',   // animate parent BEFORE children
    },
  },
}
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

<motion.ul variants={listVariants} initial="hidden" animate="visible">
  {items.map(item => <motion.li key={item.id} variants={itemVariants}>{item.name}</motion.li>)}
</motion.ul>
```

| Orchestration Prop | Description |
|---|---|
| `staggerChildren` | Delay (seconds) between each child |
| `staggerDirection` | 1 (forward, default) or -1 (reverse) |
| `delayChildren` | Delay before children start |
| `when` | `"beforeChildren"` or `"afterChildren"` |

#### AnimatePresence

```tsx
<AnimatePresence mode="popLayout">
  {items.map(n => (
    <motion.div key={n.id} initial={{opacity:0,x:300}} animate={{opacity:1,x:0}}
      exit={{opacity:0,x:300}} transition={{type:'spring',stiffness:300,damping:30}}>
      {n.message}
    </motion.div>
  ))}
</AnimatePresence>
```

**Modes**: `"wait"` (exit finishes then enter), `"popLayout"` (simultaneous, exiting pops out), `"sync"` (default simultaneous), `initial={false}` (skip first mount enter)

#### Layout Animations

```tsx
// Automatic layout transitions — layout prop
<motion.div layout />

// Shared element between components — layoutId
function App() {
  const [selectedId, setSelectedId] = useState(null)
  return (<>
    {items.map(item => <motion.div key={item.id} layoutId={item.id} onClick={() => setSelectedId(item.id)} />)}
    <AnimatePresence>
      {selectedId && <motion.div layoutId={selectedId}>...</motion.div>}
    </AnimatePresence>
  </>)
}
```

Gotchas: `layout` uses `transform` internally (compositor-safe). Use `layout="position"` for position-only (faster). `layoutId` elements MUST share same tag name for correct morphing.

#### Scroll Animations

```tsx
import { useScroll, useTransform, useSpring } from 'framer-motion'

// Scroll-linked
const { scrollYProgress } = useScroll()
const scale = useTransform(scrollYProgress, [0, 0.5], [1, 1.2])
const smoothScale = useSpring(scale, { stiffness: 100, damping: 30 })

// Scroll-triggered (whileInView)
<motion.div whileInView={{ opacity: 1, y: 0 }} initial={{ opacity: 0, y: 40 }}
  viewport={{ once: true, margin: '-50px' }} transition={{ duration: 0.6 }} />

// Scoped: useScroll({ container: ref }) or useScroll({ target: ref, offset: ['start end','end start'] })
```

#### Gestures & Imperative Control

```tsx
<motion.button whileHover={{scale:1.05}} whileTap={{scale:0.95}}
  whileFocus={{boxShadow:'0 0 0 3px var(--color-focus-ring)'}}
  transition={{type:'spring',stiffness:400,damping:17}} />

<motion.div drag dragConstraints={{left:0,right:300,top:0,bottom:200}}
  dragElastic={0.1} whileDrag={{scale:1.1}} />

// Imperative sequence
const controls = useAnimationControls()
async function play() {
  await controls.start({ x: 100, transition: { duration: 0.3 } })
  await controls.start({ scale: 0 })
}
// <motion.div animate={controls} /> <button onClick={play}>Play</button>
```

#### Motion Values (no re-renders)

```tsx
const x = useMotionValue(0)
const scale = useTransform(x, [-200, 200], [0.5, 2])
const bg = useTransform(x, [-200, 0, 200], ['#f00', '#00f', '#0f0'])
// <motion.div style={{ x, scale, background: bg }} drag="x" />
```

### Animation Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Animating layout-triggering properties | Animating `width`, `height`, `top`, `left`, `margin`, or `padding` triggers layout recalculations every frame (jank) | Only animate compositor-only properties: `transform` (translate/scale/rotate), `opacity`, `filter` |
| `will-change` on everything | `* { will-change: transform; }` wastes GPU memory; each element gets its own compositor layer | Apply `will-change` only during animation, remove immediately after. Use JS to toggle a class |
| No `prefers-reduced-motion` support | Users with vestibular disorders get sick from animations | Always respect `@media (prefers-reduced-motion: reduce)`. Set durations to 0.01ms or skip programmatic animations entirely |
| Infinite animations without pause | Auto-playing animations violate WCAG 2.2.2; no way for users to stop motion | Add pause/stop controls for any animation lasting > 5 seconds. Use `animation-play-state: paused` |
| Animating hundreds of elements simultaneously | Each animated element creates a compositor layer; GPU memory exhaustion on mobile | Use CSS `@keyframes` over JS animation for large sets; batch with `will-change`; reduce count via virtualization |
| Nesting `AnimatePresence` incorrectly | Nested exit animations break when parent unmounts first; children never animate out | Keep `AnimatePresence` only on the direct parent of conditionally rendered elements. Nest with `mode="wait"` |
| GSAP `ScrollTrigger` not cleaned up | Multiple ScrollTrigger instances accumulate on route changes; memory leaks; scroll listeners persist | Use `gsap.context()` or `useGSAP()` with cleanup; always `ScrollTrigger.kill()` on unmount |
| Canvas not handling pixel ratio | Canvas renders at 1x on Retina displays; blurry output | `canvas.width = canvas.clientWidth * devicePixelRatio; ctx.scale(devicePixelRatio, devicePixelRatio)` |
| Layout thrashing in animation loops | Interleaving reads (offsetHeight) and writes (style.left) in the same frame forces synchronous reflow | Batch all reads first, then all writes. Use `requestAnimationFrame` with FLIP technique |
| Oversized Lottie/Rive files | 5MB animation file blocks rendering; poor LCP | Compress Lottie JSON; use dotLottie format (smaller); lazy-load animations below the fold |
| Framer Motion `layout` prop on static elements | Every element with `layout` triggers layout animations on ANY parent change | Only use `layout` on elements that actually change position/size between renders. Use `layout="position"` for position-only tracking |
| `delay` on every stagger child | Using `transition={{ delay: index * 0.1 }}` instead of `staggerChildren` creates N separate transitions | Use `staggerChildren` on the parent variant's transition; children inherit automatically |

---

### GSAP (Framework-Agnostic)

#### Core API & Timelines

```js
import gsap from 'gsap'

gsap.to('.box', { x: 200, duration: 1, ease: 'power2.out' })
gsap.from('.box', { opacity: 0, y: 50, duration: 0.6 })
gsap.fromTo('.box', { opacity: 0, scale: 0.5 }, { opacity: 1, scale: 1, duration: 0.8 })
gsap.set('.box', { x: 0, y: 0 })  // immediate, no animation

// Timeline: [==== tween1 ====][===== tween2 =====][== tween3 ==]
const tl = gsap.timeline({ defaults: { duration: 0.5, ease: 'power2.out' } })
tl.to('.a', { x: 100 })
  .to('.b', { y: 50 }, '+=0.2')   // 0.2s after previous ends
  .to('.c', { scale: 2 }, '-=0.1') // 0.1s before previous ends (overlap)
  .to('.d', { opacity: 0 }, '<')   // AT SAME TIME as previous start
  .to('.e', { rotate: 45 }, '>')   // AT SAME TIME as previous end

// Labels & nesting
tl.addLabel('intro', 0).to('.logo', { scale: 1.2 }, 'intro+=0.3')
tlParent.add(tlChild, '+=0.5')  // insert nested timeline
```

Position params: `+=0.5` (after), `-=0.3` (before), `<` (same start), `>` (same end), `label+=0.2` (after label), `0.5` (absolute time).

#### ScrollTrigger

```js
import { ScrollTrigger } from 'gsap/ScrollTrigger'
gsap.registerPlugin(ScrollTrigger)

gsap.to('.box', {
  scrollTrigger: {
    trigger: '.section',
    start: 'top bottom',         // trigger-top meets viewport-bottom
    end: 'bottom top',           // trigger-bottom meets viewport-top
    scrub: true,                 // link to scroll (1 = 1:1, 0.5 = smoothed)
    pin: true,                   // pin trigger during scroll
    toggleActions: 'play none none reverse',
    // onEnter onLeave onEnterBack onLeaveBack | play|pause|resume|reverse|restart|reset|none
    once: true,                  // fire only once
    markers: false,              // dev debugging
  },
  y: 100, opacity: 0,
})

// Batch elements
gsap.utils.toArray('.reveal').forEach(el => {
  gsap.from(el, { scrollTrigger: { trigger: el, start: 'top 80%' }, opacity: 0, y: 50 })
})
```

#### Flip Plugin & MorphSVG

```js
import { Flip } from 'gsap/Flip'
gsap.registerPlugin(Flip)

// Layout animation — capture state, change DOM, animate
function reorderList() {
  const state = Flip.getState('.list-item')
  list.prepend(list.lastElementChild)  // DOM change
  Flip.from(state, { duration: 0.6, ease: 'power2.inOut', stagger: 0.05, absolute: true })
}

// MorphSVG (paid GSAP)
gsap.to('#path1', { morphSVG: '#path2', duration: 1, shapeIndex: 'auto' })
```

#### GSAP Context (React/Svelte cleanup)

```tsx
// React
useEffect(() => {
  const ctx = gsap.context(() => {
    gsap.to('.box', { x: 100 })
    gsap.to('.circle', { scale: 1.5, scrollTrigger: { trigger: '.circle' } })
  }, containerRef)
  return () => ctx.revert()  // kills ALL animations on unmount
}, [])

// Svelte 5
$effect(() => {
  const ctx = gsap.context(() => { gsap.to('.box', { x: 100 }) }, container)
  return () => ctx.revert()
})
```

#### Easing & matchMedia

```js
// Built-in: 'power2.out', 'back.out(1.7)', 'elastic.out(1,0.5)', 'bounce.out', 'steps(5)'
// RoughEase: organic/jittery
gsap.to('.box', { x: 100, ease: RoughEase.ease.config({template:'power2.out',strength:1,points:20,randomize:true}) })
// ExpoScaleEase: scale start/end for large value ranges

// Responsive animations
const mm = gsap.matchMedia()
mm.add('(min-width: 768px)', () => {
  gsap.to('.box', { x: 200 })
  return () => {}  // cleanup
})
mm.add('(max-width: 767px)', () => { gsap.to('.box', { x: 50 }) })
mm.revert()  // clean all
```

---

### Rive (Runtime-Driven)

```
[Rive Editor] ──> .riv file ──> Runtime (WebGL/Canvas)
  State machines       binary       off-main-thread rendering
  Artboards/Bones
```

```tsx
import { useRive, useStateMachineInput } from '@rive-app/react-canvas'

function AnimatedCharacter() {
  const { rive, RiveComponent } = useRive({
    src: '/character.riv', stateMachines: 'State Machine 1', autoplay: true, artboard: 'Main',
  })
  const moodInput = useStateMachineInput(rive, 'State Machine 1', 'mood', 0)
  return (<>
    <RiveComponent style={{ width: 400, height: 400 }} />
    <button onClick={() => moodInput!.value = 1}>Happy</button>
    <button onClick={() => moodInput!.value = 0}>Sad</button>
  </>)
}
```

**Key**: State machines define transitions visually (no JS logic). Inputs: Number, Boolean, Trigger. Runtimes: WebGL (~2MB, high-perf) or Canvas (~150KB fallback).

---

### Canvas / WebGL Animation

#### Three.js Basics

```tsx
const scene = new THREE.Scene()
const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000)
camera.position.z = 5
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

const geometry = new THREE.BoxGeometry(1, 1, 1)
const material = new THREE.MeshStandardMaterial({ color: 0x3b82f6 })
const cube = new THREE.Mesh(geometry, material)
scene.add(cube)

const light = new THREE.DirectionalLight(0xffffff, 1)
light.position.set(5, 5, 5)
scene.add(light, new THREE.AmbientLight(0x404040))

function animate() {
  requestAnimationFrame(animate)
  cube.rotation.x += 0.01; cube.rotation.y += 0.01
  renderer.render(scene, camera)
}
animate()

// Cleanup: cancelAnimationFrame, observer.disconnect(), renderer/dispose(), geometry.dispose(), material.dispose()
```

#### Lottie / dotLottie

```tsx
// dotLottie (newer, smaller, WASM-powered — recommended)
<DotLottieReact src="/animation.lottie" loop autoplay style={{ width: 200, height: 200 }} />

// Traditional react-lottie (SVG/Canvas, larger payloads)
<Lottie options={{ animationData, loop: true, autoplay: true }} height={200} width={200} />
```

#### Particle Systems & Shaders (GLSL)

```js
// Canvas particle system
const particles = Array.from({ length: 100 }, () => ({
  x: Math.random() * canvas.width, y: Math.random() * canvas.height,
  vx: (Math.random() - 0.5) * 2, vy: (Math.random() - 0.5) * 2,
  radius: Math.random() * 3 + 1, alpha: Math.random() * 0.5 + 0.5,
}))
function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  for (const p of particles) {
    p.x += p.vx; p.y += p.vy
    ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(59,130,246,${p.alpha})`; ctx.fill()
  }
  requestAnimationFrame(draw)
}

// Three.js ShaderMaterial
const fragmentShader = `
  uniform float uTime; varying vec2 vUv;
  void main() {
    gl_FragColor = vec4(vec3(
      0.5+0.5*sin(vUv.x*10.0+uTime),
      0.5+0.5*cos(vUv.y*8.0+uTime*0.7),
      0.5+0.5*sin((vUv.x+vUv.y)*6.0+uTime*1.3)
    ), 1.0);
  }`
const mat = new THREE.ShaderMaterial({ vertexShader, fragmentShader, uniforms: { uTime: { value: 0 } } })
// Update: mat.uniforms.uTime.value += 0.016 in render loop
```

---

### 60fps Guarantee

#### requestAnimationFrame & FLIP Technique

```js
// Basic rAF loop
function animate(timestamp) {
  const delta = timestamp - lastTimestamp
  lastTimestamp = timestamp
  requestAnimationFrame(animate)
}
requestAnimationFrame(animate)

// Fixed-timestep (deterministic physics)
const FIXED_DT = 1000 / 60; let accumulator = 0
function fixedLoop(timestamp) {
  const frameTime = Math.min(timestamp - lastTimestamp, 100) // cap
  accumulator += frameTime
  while (accumulator >= FIXED_DT) { update(FIXED_DT); accumulator -= FIXED_DT }
  render(accumulator / FIXED_DT)
  requestAnimationFrame(fixedLoop)
}
```

**FLIP** (First, Last, Invert, Play) — animate layout changes without thrashing:

```
FIRST:  record element.getBoundingClientRect()
LAST:   make DOM change, record again
INVERT: apply inverse delta as transform. style.transform = `translate(${dx}px,${dy}px) scale(${dw},${dh})`
PLAY:   requestAnimationFrame(() => { style.transition = 'transform 0.3s'; style.transform = '' })
```

#### will-change, contain & Layout Thrashing

```css
/* will-change: hint GPU layer creation — apply BEFORE, remove AFTER */
.animating { will-change: transform, opacity; }  /* remove class when animation ends */

/* contain: isolate element from rest of layout */
.animated-list-item { contain: layout style paint; }

/* NEVER: * { will-change: transform; } — wastes GPU memory */
/* NEVER: .sidebar { will-change: transform; } — persistent GPU layer waste */
```

Layout thrashing: interleaving reads and writes forces synchronous layout calculations.

```js
// BAD (thrashing)
el.style.width = parent.offsetWidth + 'px'    // WRITE
const h = el.offsetHeight                     // READ (forces layout)
el.style.top = (h / 2) + 'px'                // WRITE

// GOOD (batched)
const pw = parent.offsetWidth  // READ all
const eh = el.offsetHeight     // READ all
const ew = el.offsetWidth      // READ all
el.style.width = pw + 'px'     // WRITE all
el.style.top = (eh / 2) + 'px' // WRITE all

// FastDOM pattern
fastdom.measure(() => {
  const w = el.offsetWidth
  fastdom.mutate(() => { el.style.left = (w / 2) + 'px' })
})
```

#### Chrome DevTools Performance Guide
1. Performance tab → Record → interact → Stop
2. Check Frames for red triangles (dropped frames)
3. Expand long frame: Scripting → Rendering → Painting
4. Enable "Rendering" → "Paint Flashing" (green = repaint regions)
5. Enable "Rendering" → "Layer Borders" (orange = GPU layers)
6. Enable "Rendering" → "FPS Meter" for real-time overlay

---

### Motion Design System

#### Token System

Define tokens once as CSS custom properties + JS constants:

```css
:root {
  --dur-micro: 75ms; --dur-small: 150ms; --dur-medium: 300ms; --dur-large: 500ms; --dur-xlarge: 800ms;
  --ease-enter: cubic-bezier(0,0,0.2,1); --ease-exit: cubic-bezier(0.4,0,1,1);
  --ease-standard: cubic-bezier(0.4,0,0.2,1); --ease-emphasized: cubic-bezier(0.05,0.7,0.1,1);
  --offset-micro: 4px; --offset-small: 8px; --offset-medium: 16px; --offset-large: 32px; --offset-xlarge: 64px;
  --blur-micro: 2px; --blur-small: 4px; --blur-medium: 8px; --blur-large: 16px;
}

.modal-enter {
  animation: modal-in var(--dur-medium) var(--ease-emphasized);
}
@keyframes modal-in {
  from { opacity: 0; transform: translateY(var(--offset-medium)) scale(0.97); }
}
```

```ts
// tokens/motion.ts — for Framer Motion/GSAP
export const tokens = {
  duration: { micro: 0.075, small: 0.15, medium: 0.3, large: 0.5, xlarge: 0.8 },
  ease: {
    enter: [0, 0, 0.2, 1], exit: [0.4, 0, 1, 1],
    standard: [0.4, 0, 0.2, 1], emphasized: [0.05, 0.7, 0.1, 1],
  } as const,
  spring: {
    gentle: { stiffness: 100, damping: 15, mass: 1 },
    precise: { stiffness: 500, damping: 40, mass: 1 },
    wobbly: { stiffness: 180, damping: 12, mass: 1 },
    stiff: { stiffness: 260, damping: 20, mass: 1 },
  },
  offset: { micro: 4, small: 8, medium: 16, large: 32, xlarge: 64 },
  blur: { micro: 2, small: 4, medium: 8, large: 16 },
} as const
```

#### Spring vs Duration-Based Easing

```
PREFER SPRINGS when: animation can be interrupted, physics feels more natural, AnimatePresence exits
PREFER DURATION EASING when: precise timing needed, must complete in guaranteed window, simple opacity-only
```

---

### Accessibility

#### prefers-reduced-motion

```
TIER 1: Global CSS kill switch (@media query, 0.01ms durations)
TIER 2: JS guard — check window.matchMedia before programmatic animations
TIER 3: Provide static equivalent for functional animations (page transitions → instant)
```

```tsx
// Framer Motion hook
function PageTransition({ children }) {
  if (useReducedMotion()) return <>{children}</>
  return <motion.div initial={{opacity:0,y:32}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-32}} children={children} />
}
```

#### Duration Limits & Focus Management

- Decorative: max 3s/cycle. Functional transitions: max 500ms
- Loading indicators: `aria-label="Loading"`, may loop. Auto-play: must have pause/stop (WCAG 2.2.2)

```tsx
// Focus into modal AFTER enter animation completes
useEffect(() => {
  if (isOpen) { const t = setTimeout(() => closeRef.current?.focus(), 400); return () => clearTimeout(t) }
}, [isOpen])

<AnimatePresence>
  {isOpen && <motion.div role="dialog" aria-modal="true" aria-label="Modal dialog" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} />}
</AnimatePresence>
```

#### ARIA During Transitions

```tsx
{/* Live region for content changing during animation */}
<div aria-live="polite" aria-atomic="true">{dynamicContent}</div>

{/* Carousel / animated lists */}
<div role="region" aria-roledescription="carousel" aria-label="Featured items">
  <div role="group" aria-roledescription="slide" aria-label={`Slide ${i+1} of ${total}`}>{slideContent}</div>
</div>
```

---

### Testing Animations

#### Mocking requestAnimationFrame (vitest)

```ts
let rafCallbacks: Array<(time: number) => void> = []; let now = 0

beforeEach(() => {
  rafCallbacks = []; now = 0
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(cb => { rafCallbacks.push(cb); return rafCallbacks.length })
  vi.spyOn(performance, 'now').mockImplementation(() => now)
})

function advanceTimers(ms: number) {
  now += ms
  const cbs = [...rafCallbacks]; rafCallbacks = []
  cbs.forEach(cb => cb(now))
}

it('animates opacity from 0 to 1', () => {
  render(<FadeIn><p>Hello</p></FadeIn>)
  expect(screen.getByText('Hello')).toHaveStyle({ opacity: '0' })
  advanceTimers(500)
  expect(screen.getByText('Hello')).toHaveStyle({ opacity: '1' })
})
```

#### Testing Reduced Motion

```ts
it('skips animation when prefers-reduced-motion', () => {
  window.matchMedia = vi.fn().mockImplementation(query => ({
    matches: query === '(prefers-reduced-motion: reduce)',
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }))
  render(<AnimatedHero />)
  expect(screen.getByText('Hero')).toHaveStyle({ opacity: '1' })
})
```

#### Visual Regression Testing

```
STRATEGY: Capture at final state, not during motion.
1. Disable CSS animations in test env: el.style.animationPlayState = 'paused'
2. Wait for animation completion: waitForFunction(() => getComputedStyle(el).opacity === '1')
3. Take screenshot and compare
```

```tsx
// RTL: wait for animationend
await waitFor(() => {
  expect(screen.getByRole('dialog')).toHaveStyle({ opacity: '1' })
})
```

```js
// Playwright
await page.evaluate(() => {
  document.querySelectorAll('*').forEach(el => { el.style.animationPlayState = 'paused' })
})
await expect(page).toHaveScreenshot()

// Or wait for specific state
await page.waitForFunction(() => {
  return getComputedStyle(document.querySelector('[data-testid="animated-box"]')).opacity === '1'
})
await expect(page).toHaveScreenshot()
```

---

### Animation Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| Animation doesn't fire / invisible | `display: none` or zero dimensions prevent animation evaluation | DevTools: check computed styles for `display` and dimensions | Use `visibility` + `opacity` instead of `display: none`. Animate `max-height` as escape hatch |
| `AnimatePresence` exit not working | Missing unique `key` prop on exiting elements; `mode="wait"` blocking exit | React DevTools: check that each child has a stable, unique `key` | Always provide unique `key` to children of `AnimatePresence`. Use `mode="popLayout"` or `mode="sync"` |
| GSAP timeline doesn't play | Target elements not in DOM when timeline created; `from` tweens use pre-render values | `console.log(gsap.getProperty(el, 'opacity'))` to verify element state | Use `gsap.fromTo()` instead of `gsap.from()` for predictable starting values. Create timelines after DOM mount |
| ScrollTrigger not activating | Trigger element is above/below viewport at init time; `start`/`end` markers misconfigured | Enable `markers: true` and `pin: true` to visualize trigger area | Adjust `start` and `end` values; check `trigger` selector matches; call `ScrollTrigger.refresh()` after layout changes |
| Framer Motion `layoutId` breaks | Elements with `layoutId` have different tag names (e.g., `<div>` in one place, `<span>` in another) | Check rendered HTML for tag mismatch | Use the same HTML tag type for all elements sharing a `layoutId` |
| Janky/stuttering animations | Non-compositor property being animated; GC pause; layout recalculation mid-frame | Chrome DevTools Performance tab: look for purple (recalc style) or green (paint) bars in animation frames | Switch to compositor-only properties; use `contain: layout style paint` on animated element; pre-calculate values |
| Three.js scene renders black | Missing light source; camera pointing wrong direction; material needs light (MeshStandardMaterial) | Add `AmbientLight` (always visible) + `DirectionalLight`; check `camera.lookAt(scene.position)` | Add lighting; use `MeshBasicMaterial` temporarily for debugging; verify camera position |
| WebGL context lost / not restored | GPU process crash; too many contexts; tab backgrounded | Check `canvas.addEventListener('webglcontextlost', ...)` events | Implement context restoration handler; call `renderer.setAnimationLoop(null)` on lost, re-initialize on restore |
| CSS `@keyframes` not smooth | Using `left`/`top`/`margin` in keyframes (layout-triggering) | Chrome DevTools Performance: green paint bars every frame | Use `transform: translate()` instead of `left`/`top`. Use `opacity` instead of `visibility` |
| Rive animation janks | State machine transitions during heavy main thread work | Profile main thread; Rive runs on `requestAnimationFrame` | Reduce JS workload during Rive playback; use WebGL renderer over Canvas renderer (better GPU offloading) |
| `requestAnimationFrame` firing too many times | Multiple `rAF` loops started without cleanup | `console.count('rAF')` inside loop | Track and cancel rAF IDs on unmount: `cancelAnimationFrame(rafId)`. Use a single rAF loop for all animations |
| Mobile animations lag | GPU overdraw; too many compositor layers; thermal throttling | Chrome DevTools: Rendering → Layer borders (orange = GPU layers) | Reduce `will-change` usage; combine layers; reduce animation complexity on mobile via `matchMedia` |

### Implementation Checklist

- [ ] Motion tokens defined (duration, easing, spring, distance, blur)
- [ ] Every animated element has enter + exit states defined
- [ ] `prefers-reduced-motion` respected at CSS and JS levels
- [ ] Only compositor-only properties animated (transform, opacity)
- [ ] `will-change` used sparingly and removed after animation
- [ ] `AnimatePresence` wraps all components with exit animations
- [ ] GSAP Context used for cleanup in React/Svelte components
- [ ] ScrollTrigger instances cleaned up on route change
- [ ] `contain` applied to animated elements isolated from layout
- [ ] Layout thrashing prevented (batch reads then writes)
- [ ] Focus managed during modal/page transitions
- [ ] ARIA attributes on animated regions (aria-live, aria-modal, role)
- [ ] Animation duration under 5 seconds for functional content
- [ ] Pause/stop controls on auto-playing animations
- [ ] rAF mocked in test environment for deterministic tests
