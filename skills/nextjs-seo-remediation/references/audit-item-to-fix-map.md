# Audit item → Next.js App Router fix map

Use this when a user provides an SEO audit screenshot/PDF and wants direct remediation in code.

## Common mappings

### "Add a H1 heading to this page"
Check:
- `app/page.tsx`
- hero component used by the page
- dynamic page wrapper vs child component

Fix:
- ensure exactly one visible H1 on the page
- make the H1 target the real search intent, not just a generic brand slogan

### "Use good headings on the page"
Fix:
- convert decorative text blocks into real H2/H3 section headings
- make section titles descriptive, not vague CTA copy
- avoid accidentally nesting multiple H1s through reusable components

### "This page has only very few internal links"
Fix:
- add a homepage or landing-page internal-link section
- include links to money pages, trust/help pages, and high-value dynamic pages
- for data-backed sites, derive a short list from existing top entities (for example popular games/products)

### "Try to make the page title match the content"
Fix:
- update metadata title/description and hero copy together
- make sure the primary keyword in the title is visibly reinforced by H1 and intro copy
- avoid a generic homepage title if the page is actually a focused money page

### "Add a favicon markup to the HTML code"
Fix:
- create `app/icon.png`
- create `app/apple-icon.png` when possible
- wire `icons` in shared metadata
- verify build output includes the icon route

### "Domain should not be present in the title"
Fix:
- avoid stuffing raw domain names into page titles
- use brand name only when it reads naturally and supports recognition

## Reporting pattern

When the user wants a quick status answer, report each visible audit item as:
- Done
- Partial
- Not done

That format is faster and clearer than a long prose recap.
