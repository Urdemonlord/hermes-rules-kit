# Internalizing third-party resource content for Meow Labs

Use this when a Meow Labs resource page is built from third-party discovery/tutorial sources and the product goal is to keep the user inside Meow Labs.

## Rule

If the user wants Meow Labs to be the final destination, do **not** leave UI routes or CTA buttons that send users out to source sites like AppVerse, tokengratis, or public Drive folders.

## Preferred pattern

1. Ingest source metadata/content.
2. Map it into Meow Labs-native routes.
3. Host mirrored/supporting files under the app itself when legally/operationally acceptable, e.g. `public/resources/<collection>-files/...`.
4. Point detail-page CTAs to those internal files/routes.
5. Rewrite labels/copy so they say `Meow Labs`, `arsip internal`, or equivalent — not the upstream source brand.
6. Keep source provenance as internal implementation detail unless the product explicitly wants attribution visible.

## Practical trigger

This is especially relevant after a public Google Drive folder bypass: once files are successfully downloaded and packaged, the next step is not just "show a download button" — it is to replace external Drive/AppVerse links with Meow Labs-hosted paths.

## Verification

- Search the resource page code for upstream brand strings and outbound CTA copy.
- Verify the HTML no longer contains phrases like `Buka sumber AppVerse`.
- Verify the file/button href points to an internal path such as `/resources/...` or `/resources/...-files/...`.
- Verify the internally hosted file actually serves over HTTP.
