# Production-readiness checklist for generated web apps

Use when a product generates web apps from a prompt and the output "looks finished" but is not
shippable — the gap a user notices as "it's missing things". Covers the item list, which items a
machine can verify, and why the durable fix is scaffolding rather than prompting or gating.

## Principle: climb prompt → gate → scaffold, and expect the gate to be weak

Three ways to make required content actually appear, in increasing strength:

1. **Prompt.** State the requirements in the system prompt. Advisory only. Measured: a 20-item
   checklist in the prompt produced **0 of the 10 machine-checkable items** — the model wrote the
   core files and called `finish`.
2. **Gate.** Reject the completion call while items are missing, feeding back exactly what to
   write. Better, but not deterministic: repeated runs of the same gate on the same prompt ranged
   from **7/8 items (1 retry)** to **1/8 items (all retries burned)**, and the bad run was worse
   than no gate at all. A single-retry version was consumed on every run and still left an average
   of **7.7 items missing**.
3. **Scaffold.** Inject the fixed artifacts as project files **before** the model runs — a template
   it starts from and may edit. Their presence becomes a property of the harness instead of the
   model's compliance. This is the only rung that is deterministic.

Prompting is for taste; scaffolding is for requirements. When a user asks for "output as good as
<product X>", the first useful question is whether X scaffolds its template and which model tier
it runs on — not how to phrase the prompt better. A mid-tier model plus scaffolding beats a
mid-tier model plus a stricter prompt.

## Implementing the scaffold

The scaffold is a set of files placed into the generation state **before** the model's first turn,
so they exist whether or not the model cooperates. Measured outcome: the same three prompts that
left an average of **7.7 items missing** under a one-retry gate left **0.0 missing** with a
scaffold — deterministic across runs, with no reliance on model compliance.

Rules that make it work:

- **Seed the state, not the prompt.** Put the files into the generation state's file map before
  the loop starts (e.g. in the function that creates fresh generation state). Writing them into
  the system prompt as text just returns you to rung 1.
- **Announce the seeded paths in the user message, or the model rewrites them.** A scaffold the
  model cannot see is a scaffold it duplicates: it emits its own `package.json`, `index.html`,
  and entry point, burning the turns the scaffold was meant to save and reintroducing the
  non-determinism it was meant to remove. List the existing paths and say explicitly not to
  rewrite them.
- **Name the one thing the model must still wire up.** Seeded pages are inert until something
  routes to them. Tell the model to import the scaffold's pages into its own entry component and
  render the scaffold's global component (banner, layout) once — otherwise you ship a privacy
  page nothing links to, and the gate/checklist will read it as present while users can never
  reach it.
- **Seed only what is identical in every project.** Build config, entry point, global styles,
  legal pages, SEO files, 404. Anything derived from the user's request stays the model's job —
  that is where its output actually differentiates.
- **Skip the scaffold on refinement.** When the project already has files (a follow-up request),
  re-seeding overwrites the user's own edits. Return nothing when existing files are supplied.
- **Gate the scaffold by stack, and make non-matches a no-op.** A React+Vite scaffold handed to a
  Flutter, Python, CLI, or Vue request is worse than no scaffold. Detect the target stack from the
  request and return an empty list otherwise, so behaviour is strictly additive for stacks you do
  not cover. Exclude the stack by *negative* match too (an explicit `python`/`flutter`/`cli` word
  in the request should veto the web scaffold even if a framework word also appears).
- **Leave the conditional items to the model.** Form-error states, thank-you screens, and loading
  states depend on what the app does, so they cannot be seeded as fixed files. Keep the gate (a
  single retry) as the safety net for exactly those, now that the fixed items no longer depend on
  the model.
- **A seeded manifest must declare every package the prompt advertises as available.** If the
  system prompt tells the model it may "use `<lib>` freely", the scaffold's dependency manifest
  has to list that library. Otherwise the install step never fetches it, the generated app fails
  to build, and the failure surfaces far from its cause — the prompt and the manifest are the two
  halves of one promise. Grep the system prompt for every library it names and check each one
  appears in the seeded manifest.

## Pitfall: the prompt and the runner can contradict each other

Instructions and harness drift apart when they are edited separately. A prompt that says
"DO NOT generate `package.json`" while the run harness **requires** one (it bails out with
"no package.json found, nothing to run") means every generated project fails at the run step,
with nothing pointing back at the prompt. When seeding a file the prompt previously forbade,
update the prompt in the same change: state that the file is **already provided** and must not
be rewritten. Any time a scaffold adds or removes a file the prompt has an opinion about, fix
both sides together — a contradiction between them reads as a code bug and is expensive to
trace.

**Verify the model used the scaffold, not just that it exists.** Read the generated entry
component and confirm it imports the seeded pages and renders the seeded global component. A
file-count increase alone does not prove the scaffold was adopted — the model can add its own
files and ignore the seeded ones entirely.

## The item list

`[M]` = a deterministic check can verify it. `[U]` = needs data only the operator has — **omit or
placeholder, never invent a value**.

**Error + navigation**
- `[M]` Custom 404 page — only when the app has a router
- `[M]` Per-page `<title>`
- `[M]` Per-page meta description

**Discoverability**
- `[M]` Favicon
- `[M]` `robots.txt`
- `[M]` `sitemap.xml` — list only addresses that actually resolve (see the client-side-SPA pitfall in SKILL.md)
- `[M]` Open Graph image + `og:*` tags
- `[U]` Analytics — needs a real measurement ID; leave the loader inert until one is provided rather than shipping a placeholder that sends traffic elsewhere

**Content + legal**
- `[M]` Privacy policy page
- `[M]` Terms & conditions page
- `[M]` Cookie-consent banner
- `[U]` Real contact / business address / legal entity name

**Layout + a11y**
- `[M]` `alt` text on every `<img>`
- `[M]` Mobile breakpoints / responsive classes
- `[M]` Loading states — only when the app fetches
- `[M]` Inline form error states — only when there is a `<form>`
- `[M]` Success / thank-you state after form submit
- `[U]` "CTA above the fold", "sticky mobile CTA"
- `[U]` Image compression

## Detection: apply only to web apps, and make each item conditional

Gate the whole checklist on a web-app detector (an `.html` entry point, a framework config, a
`src/App|main|index.*`, or a front-end framework in `package.json`). A Python script, a CLI, or a
Flutter app must skip it entirely — demanding `robots.txt` from a data script is noise that trains
the model to ignore the gate.

Make each item **conditional on its trigger**: a 404 page only when a router exists, loading states
only when something fetches, form-error and thank-you states only when there is a `<form>`, `alt`
text only when there is an `<img>`. An unconditional checklist produces demands that make no sense
for the project and burns compliance on the items that matter.

## Answering "what is the biggest app this can build?"

This is a recurring question about a prompt-to-app product, and it has a concrete answer: derive
it from the harness's hard limits instead of guessing.

1. **Find the state-size ceiling, not the token or time ceiling.** Time is handled by resumable
   slices, so wall-clock is not the binding constraint. The binding one is the durable store's
   document limit (see `serverless-long-task-resumability.md`): once the serialised state exceeds
   it, the job cannot be resumed across instances. Convert that limit into "files of average size"
   and state it as a range (small CRUD app / dashboard / marketplace / too big).
2. **Check whether the preview has a server.** Determine what actually renders the generated app
   before promising a category: an in-browser bundler preview means **no backend** — no server,
   no database, no API — so all state must live in client storage. A real dev-server runner that
   `spawn`s a process does not run on a serverless host, so it only helps on a long-lived box.
3. **Translate limits into an explicit can / cannot list** (multi-user, real auth, payments, and
   large data sets are the usual "cannot"). Say which categories work, which are borderline, and
   why — the reason is what lets the user judge whether a workaround exists.
4. **Name the single highest-leverage fix** rather than listing everything. If the state limit is
   the ceiling and half the state is duplicate content, trimming history is the fix that moves the
   boundary; say so plainly.

### Why the state is roughly twice the code it holds

File contents are stored **twice** in the generation state: once in the file map (the artifact the
user keeps) and once inside the message history, because each `write_file` tool call carries the full
file body in its arguments and that assistant turn must be echoed back so the next request keeps
context. Measured on a 40-file project: ~337 KB of state, ~163 KB in the file map and ~175 KB in the
history — so **state ≈ 2.1× the raw code size**, and the store's document limit binds at roughly half
the code you would otherwise expect. Report the ceiling as that derived number.

You cannot simply drop the echoed turns: the API requires every `tool` result to be paired with the
assistant turn carrying its `tool_call_id`, so deleting them makes the request invalid. The
recoverable win is to **stub the old turns** — replace the arguments of turns older than the last few
with a short marker (path + "written") while leaving recent turns intact — which roughly doubles the
file capacity without touching the store's limit. Name this trim as the highest-leverage fix when the
state limit is what binds.

## Pitfall: framework detection by exact package name silently skips items

A router-detection regex built on `"react-router"` misses the real React package
`react-router-dom`, so the app is never asked for a 404 page — the item is skipped silently on the
most common stack. Match the family, not one exact name
(`react-router(-\w+)?|vue-router|wouter|next|@solidjs/router|svelte-routing`), and unit-test the
detector against real package names rather than a hand-written example.

## Pitfall: raising a ceiling and forgetting the others

Adding required files raises file and turn counts. Every bound must move in the same change —
`MAX_FILES` and `MAX_TURNS` server-side, plus the client's continuation cap — or the new
requirement silently truncates projects that previously fit. Grep for all of them together.
