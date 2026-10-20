---
name: toefl-practice-patterns
description: Design patterns and anti-slop techniques for building offline-first PWA educational apps with Web Components, empty states, onboarding, and theming
tags: []
related_skills:
  - toefl-audio-pitfalls
---

# TOEFL Practice PWA - Design Patterns Reference

## Project Context
- **Stack**: Vite + TypeScript + Web Components (no React)
- **Type**: Offline-first PWA for TOEFL practice
- **Audience**: Students preparing for TOEFL exam
- **Goal**: Fast, native-feeling app for quick practice sessions

## Key Design Patterns

### 1. Empty State Pattern
**Problem**: Dashboard showing dashes (—) for no data feels like an error.
**Solution**: Friendly message with action prompt.

```html
<!-- BAD -->
<div class="stat-card">
  <span class="stat-value">—</span>
  <span class="stat-label">Questions Done</span>
</div>

<!-- GOOD — as a card -->
<div class="empty-card">
  <div class="empty-icon"><svg><!-- book --></svg></div>
  <div class="empty-body">
    <h3>No practice yet</h3>
    <p>Start your first practice to unlock statistics.</p>
  </div>
  <a class="empty-action" href="#/listening">Start Listening</a>
</div>
```

Style: `border: 1px dashed var(--glass-border)`, flex layout with icon left, text center, CTA button right.

**Rule**: When all stats are zero/empty, replace with a friendly card that guides the user to take action. Never use floating centered text.

### 2. First-Visit Onboarding
**Problem**: Multi-user app needs user identification without account system.
**Solution**: Modal on first visit, store name in IndexedDB.

```typescript
const settings = await SettingsRepository.get();
const needsOnboarding = !settings.name;
if (needsOnboarding) {
  const name = await showOnboardingModal();
  updateProfile(name);
} else {
  updateProfile(settings.name);
}
```

**Onboarding Modal Design**: Centered modal with blur backdrop, clear title, no-signup subtitle, single name input, Continue button, "Offline-first · No account required" footer.

### 3. Light/Dark Mode CSS Variables
CSS custom properties with `.light`/`.dark` class on `<html>`. Component-specific overrides use `html.light #sidebar { ... }`.

### 4. Micro-UI Feedback Iteration
Process: Read current CSS/HTML → minimal targeted changes → build → deploy → report.

### 5. Sidebar Navigation
Fixed sidebar with active state indicator using `::before` pseudo-element (3px left bar).

### 6. Progress Ring Component
Circular SVG progress indicator for section accuracy.

### 7. Responsive Layout — Sidebar + Bottom Nav with "More" Overflow
Sidebar on desktop, bottom nav on mobile (768px breakpoint).

**Mobile nav overflow**: Sidebar has 8 items but bottom-nav can't fit all. Primary items (Home, Listen, Struct, Read, Progress) go in bottom-nav. Secondary items (Full Test, Review, Settings) go in a "More" dropup panel.

Implementation:
- Bottom-nav: 5 `<a>` items + `<button data-nav-more>` with `⋯` icon + "More" label
- Below bottom-nav: `#nav-more-overlay` (semi-transparent backdrop) + `#nav-more-panel` (bottom-sheet with `.more-inner` card containing overflow links)
- Panel slides up from bottom on tap, closes on overlay tap or navigation
- "More" button turns `--primary` color when user is on any overflow page (Full Test, Review, Settings)

```html
<!-- Bottom nav: primary items + More button -->
<a href="#/progress" data-nav="progress">Progress</a>
<button data-nav-more id="nav-more-btn">
  <svg><!-- three dots --></svg>
  <span>More</span>
</button>

<!-- Dropup panel (outside bottom-nav) -->
<div id="nav-more-overlay"></div>
<div id="nav-more-panel">
  <div class="more-inner">
    <a href="#/full-test" data-nav="full-test">Full Test</a>
    <a href="#/review" data-nav="review">Review</a>
    <a href="#/settings" data-nav="settings">Settings</a>
  </div>
</div>
```

```css
#nav-more-panel {
  position: fixed;
  bottom: calc(56px + env(safe-area-inset-bottom, 0px));
  left: 0; right: 0;
  z-index: 191;
}
#nav-more-panel .more-inner {
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
}
```

```typescript
// bootstrap.ts — toggle + active state for overflow items
document.querySelectorAll('#nav-more-panel a[data-nav]').forEach(...); // include in setActiveNav
const inMore = ['full-test', 'review', 'settings'].includes(normalized);
if (moreBtn) moreBtn.style.color = inMore ? 'var(--primary)' : '';
```

Close on navigation (afterRender hook). `setActiveNav` must also query `#nav-more-panel a[data-nav]`.

### 8. Quiz Top Bar — Progress + Score + Context Back
Back button shows section name (e.g. "← Listening"), not generic "← Back". Progress bar uses section accent color. Score is "🏆 N".

### 9. Correct/Wrong Answer Styling — Border-Based
Background 5-10% opacity max. Border carries the color. Letter uses matching tint. Never fill entire card.

### 10. Explanation as Learning Card
Card with label, body, divider, tip — not alert-box.

### 11. Letter Circle Sizing
Option letter circles: 34px, font 15px.

### 12. Listening Mode — Audio-Only Questions
Add `listening-mode` attribute to `<question-card>`. In render, if attribute present, show prompt instead of question text. Two `<audio-player>` elements: narration audio (conversation) + question audio (TTS question text, `LAXXX-Q.mp3`).

### 13. Manual Next Button — No Auto-Advance
Never auto-advance after answer. Remove `autoTimer`/`setTimeout`. Show "Next →" button after answer submitted. User clicks to advance.

Implementation:
```html
<question-card></question-card>
<div class="next-row">
  <toefl-button variant="primary" class="next-btn" style="display:none">Next →</toefl-button>
</div>
```
```css
.next-row { display: flex; justify-content: flex-end; padding-top: var(--space-xs); }
```
```typescript
// After answer event:
const next = el.querySelector('.next-btn') as HTMLElement;
next.style.display = '';

// goNext function calls engine.next() or finishQuiz on last question.
// renderQuestion() resets Next button to hidden.
```

**Edge cases**: Last question → Next button triggers finish. `renderQuestion()` hides Next on each new question. Back handlers no longer need `clearTimeout`.

### 14. Click Handler Delegation — data-action Pattern
Every interactive button MUST have `data-action="start"` (or appropriate action). Buttons without it silently fail in delegated click handlers.

### 15. Container Width for Quiz Content
Question/answer UI needs 720-900px max-width (860px ideal). 1280px hurts readability.

### 16. Dashboard Layout Composition — Compact Hero + Action + 2×2 Grid
| Section | Height | Purpose |
|---------|--------|---------|
| Hero | ~80px | Greeting + streak badge |
| Continue CTA | ~70px | Action banner with play icon |
| Section grid (2×2) | ~240px | Listening, Structure, Reading, Full Test |
| Stats row | ~90px | 4 stat cards |

### 17. Audio Player — CSS Variable Pitfall
Must use app tokens (`--glass-bg`, `--accent-listening`, `--glass-border`), not external design system vars (`--bg-secondary`, `--color-primary`). SVG icons for play/pause, not text.

### 18. Build Step — tsc Strict Mode Traps
Build: `tsc && vite build`. Common failures: unused imports, wrong `SectionProgress` fields, missing `--lib es2017` for `Object.entries()`.
Pitfall: `SVGSVGElement as HTMLElement` fails under strict TS — use `as unknown as HTMLElement` double-cast.

### 19. Content Area Padding — Match Sidebar
`#app` padding-top = `--space-md` (16px), not `--space-xl` (32px).

### 20. Mock-Test Start Screen — Visual Hierarchy
Full Test landing page needs clear visual hierarchy, not just content dumped in a card:
- **Title area**: Large title (24-28px) + subtitle with stats (e.g. "140 Questions · 150 Minutes")
- **Info cards row**: 3 cards with icon + name + detail (e.g. "Listening · 50 Questions · 30 min")
- **Checklist**: Small checklist of prep items (timer, session, auto-save, duration)
- **Primary CTA**: Full-width solid color button with icon (not gradient)
- **Secondary info**: Small info line below button, not a warning card
- **Empty states**: Per-section "No X attempted yet" instead of all-zero summary
- `max-width: 640px` centered content with consistent spacing rhythm (12→28→20px)

## Anti-Patterns to Avoid
1. Dashes for empty data — use friendly actionable cards
2. Hardcoded user names — always fetch from `SettingsRepository.get()`
3. Missing light mode — design both themes from start
4. Generic empty states — make them contextual with CTA
5. Complex onboarding — just name input
6. Silent click handler failures — always add `data-action`
7. Flat color fill for correct/wrong — use border + subtle tint
8. Alert-box explanations — use learning card pattern
9. Written question text in listening mode — audio-only prompt
10. Wide quiz container — cap at 860px
11. Audio player using wrong CSS vars — use app design tokens
12. Tall empty hero on dashboard — shrink to 80px or fill with content
13. Sidebar profile bloated with XP/streak — keep compact, gamification on dashboard
14. Floating text empty state — use card with icon + description + CTA
15. Excessive vertical gap sidebar→content — 16px padding-top
16. **Auto-advance after quiz answer** — never auto-advance. Show Next → button.
17. **All sidebar items in mobile bottom-nav** — won't fit >5 items. Use "More" dropup.
18. **Gradient buttons everywhere** — one solid accent CTA, rest neutral
19. **Same border-radius everywhere** — vary by component (cards 10px, buttons 8px, modals 16px, avatars 50%)
20. **Warning card for minor info** — use small info icon line, not yellow block

## Files to Reference
- `src/pages/listening.ts` — Dual audio players, manual Next button, listening-mode quiz
- `src/pages/structure.ts` — Diff-card data-action, quiz top bar, manual Next button
- `src/pages/reading.ts` — Same as structure, manual Next button
- `src/pages/mock-test.ts` — Full test with start screen, section routing
- `src/components/audio-player.ts` — Audio player with app design tokens
- `src/components/question-card.ts` — listening-mode attribute, explanation card
- `src/components/choice-button.ts` — Border-based correct/wrong
- `src/app/onboarding.ts` — First-visit modal
- `src/app/theme.ts` — Light/dark toggle
- `src/app/bootstrap.ts` — Route registration, nav active state, More menu toggle
- `src/pages/home.ts` — Dashboard compact hero, empty card state
- `src/pages/progress.ts` — Section cards with progress rings
- `index.html` — Sidebar, bottom-nav, More dropup panel, design tokens
- `scripts/generate-audio.py` — Narration TTS (per-line + ffmpeg concat)
- `scripts/generate-question-audio.py` — Question TTS from JSON