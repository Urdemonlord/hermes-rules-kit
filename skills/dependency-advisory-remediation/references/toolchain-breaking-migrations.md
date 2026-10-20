# Toolchain breaking-change migrations

When an advisory forces a major bump, the tool's config schema may have changed. These
are the recurring shapes and the reliable way to find the correct replacement option.

## Find the correct new option by grepping the installed type definitions

Do not guess the new option name from memory or a blog post — the installed package
tells you. Locate the config type, then read the field you need.

```bash
# 1. Find where the option type lives in the installed package
#    (adjust path to the tool: vite, vitest, rollup, tailwind, etc.)
grep -rn 'interface .*Options' node_modules/<tool>/dist/**/*.d.ts | head

# 2. Print the interface body to see the accepted fields
sed -n '/interface <Name>Options/,/^}/p' node_modules/<tool>/dist/<file>.d.ts

# 3. If a field references another type, print THAT type too (nesting)
sed -n '/^interface JsxOptions/,/^}/p' node_modules/<tool>/dist/<file>.d.ts
```

A type error like `'jsx' does not exist in type 'ESBuildOptions'` is telling you the
whole option object was **replaced**, not renamed field-by-field. Grep the top-level
config type for the new object name (e.g. `oxc?:` next to the old `esbuild?:`).

## Worked case: Vite 8 replaced esbuild with oxc (Vitest 3 → 4)

Vite 8 transforms with **oxc** instead of esbuild. The old option silently stops
applying, so JSX is no longer transformed and tests fail with a parse error
(`RolldownError: Unexpected JSX expression`) rather than a clear config error.

```ts
// before
import { defineConfig } from 'vitest/config';
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  test: { /* ... */ },
});

// after — the option moved to `oxc`, and the value is an object, not a string
import { defineConfig } from 'vitest/config';
export default defineConfig({
  // Vite 8 transforms with oxc (not esbuild), so JSX is configured here.
  oxc: { jsx: { runtime: 'automatic' } },
  test: { /* ... */ },
});
```

The `OxcOptions.jsx` field accepts `'preserve' | JsxOptions`, and `JsxOptions.runtime`
is `'classic' | 'automatic'` — that is why the value is `{ runtime: 'automatic' }`, not
the bare string `'automatic'`.

## A bundled binary can disappear on a major bump

Vitest 4 no longer bundles `vite-node`. A `scripts/` command that called `vite-node`
still runs after the upgrade fails at execution, not at build/test time. Reinstall the
standalone package:

```bash
npm install -D vite-node@^6.0.0 -w <workspace>
```

Match the standalone version to the tool's peer (`vite-node@6` pairs with vite 8).

## Silence the config-loader warning by renaming the config

A warning like *"Your Vite config uses features unsupported by `configLoader: 'native'`
… ESM syntax in a file loaded as CommonJS"* is fixed by renaming the config to `.mts`
(no `"type": "module"` needed in package.json). Remember to update every reference to
the old filename — the `scripts` entry that passes `--config <file>` is the one that is
easy to miss.

## Worked case: Tailwind 3 → 4 (framework config moves into CSS)

The official codemod (`npx @tailwindcss/upgrade@latest`) can stall on a large repo.
The migration is small enough to do by hand and far more predictable that way:

```css
/* before: three directives + tailwind.config.ts */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* after: one import, config lives in CSS */
@import 'tailwindcss';

@theme {
  --color-primary: hsl(var(--primary));
  /* ...every theme.extend entry becomes a CSS variable here */
}
```

```js
// postcss.config.js — plugin renamed, autoprefixer removed (v4 prefixes itself)
module.exports = { plugins: { '@tailwindcss/postcss': {} } };
```

Four traps that a mechanical rename gets wrong:

1. **Custom scale overrides are silently lost.** If v3's config rebound a scale to a
   token (`--radius-sm: calc(var(--radius) - 4px)`), re-declare it inside `@theme`.
   Without it, `rounded-sm/md/lg` snap back to v4's defaults and every radius shifts.
2. **A `next/font` variable collides with the theme variable of the same name.**
   Passing `variable: '--font-sans'` to `next/font` clashes with v4's own `--font-sans`.
   Rename the font variable (`--font-jakarta`) and map it back in `@theme`
   (`--font-sans: var(--font-jakarta), ui-sans-serif, …`).
3. **Gradient utilities switch colour space.** `bg-linear-to-r` (the v4 rename of
   `bg-gradient-to-r`) interpolates in `oklab`, which visibly shifts a brand gradient.
   For exact parity, write the plain `linear-gradient(to right, hsl(var(--a)), hsl(var(--b)))`
   in a `@layer components` class instead of the utility.
4. **Renames that pass type-check but change rendering:** `outline-none` →
   `outline-hidden`, `shadow-sm` → `shadow-xs`, bare `shadow` → `shadow-sm`.

Keyframes move into `@theme` too (`--animate-<name>` plus the `@keyframes` block).

5. **A v3 plugin has no v4 home — replace it, do not delete its classes.** Tailwind 4
   removed the `plugins: []` array, so a plugin like `tailwindcss-animate` cannot be
   registered any more. Its utility classes (`animate-in`, `animate-out`,
   `fade-out-80`, `slide-in-from-*`, `zoom-in-95`) will silently generate nothing. Swap
   to the v4-native successor and import it from CSS:
   ```bash
   npm uninstall tailwindcss-animate -w <workspace>
   npm install tw-animate-css -w <workspace>
   ```
   ```css
   @import 'tailwindcss';
   @import 'tw-animate-css';
   ```
   Deleting the classes instead "fixes" the build while removing the animation — the
   correct action is to make them real again.

## A class can be present in source and absent from the built CSS

A utility whose plugin was never registered (or whose name was renamed) sits in the JSX
looking active but generates no CSS. Grep the **built** stylesheet, never the source, to
prove a class is real:

```bash
grep -o 'animate-in\|animate-out\|slide-in-from-top-full' apps/web/.next/static/css/*.css | sort -u
```

Check the variants too — a utility used as `data-[state=open]:animate-in` appears as
`.data-\[state\=open\]\:animate-in[data-state=open]{…}`. If the utility is missing from
the build, that is a functional bug in the shipped UI (the toast pops with no
animation), not cosmetic debt.

## Verify a CSS migration by diffing the BUILT stylesheet, not the source

Compiled CSS is the ground truth for "did the visuals change". Save the built CSS from
`main` **before** starting, then compare class-by-class against the post-migration build:

```bash
# before touching anything
cp apps/web/.next/static/css/*.css /tmp/baseline.css
# after `npm run build`, extract and compare the rules for the classes you renamed
python3 - <<'PY'
old = open('/tmp/baseline.css').read(); new = open('<new>.css').read()
for c in ['.rounded-sm{', '.shadow-sm', '.outline-hidden', ':focus-visible']:
    print(c, '| v3:', (old[old.find(c):old.find(c)+120] or 'NONE'), '| v4:', (new[new.find(c):new.find(c)+120] or 'NONE'))
PY
```

Then take the set difference of class names in each file — anything present in the old
build and absent from the new one is a candidate regression. Expect noise from escaped
selectors and `color-mix(in oklab, …)` opacity forms; what matters is that the
*semantic* rules (`rounded-*`, ring/focus, `divide-border`, `border-border`) resolve to
equivalent values.

## Verify the migration did not change OUTPUT, only the toolchain

After a tooling bump, re-run any codegen/asset script and check the generated files are
unchanged: `git status -s <output-dir>` should be empty. Byte-identical output proves
the migration is behaviour-preserving, which is far stronger evidence than "tests pass".
