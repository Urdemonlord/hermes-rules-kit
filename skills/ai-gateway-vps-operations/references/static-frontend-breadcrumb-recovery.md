# Static Frontend Breadcrumb Recovery on Shared VPS

Use this when a public domain is back online only because a placeholder `index.html` was recreated, but the original frontend source/build appears missing.

## Signal pattern
- Reverse proxy and container are healthy.
- Static web root (`web/dist`, `/var/www/...`, or bind-mounted directory) was empty or missing.
- You can recover service availability with a placeholder page, but user asks to restore the previous real frontend.

## Recovery goal
Determine whether the original frontend can be restored exactly from surviving breadcrumbs, or whether the honest path is a rebuild.

## Breadcrumb search order
1. **Current runtime mount metadata**
   - `docker inspect` or service unit to identify the real host source path.
   - Example class: `host_path -> /usr/share/nginx/html` bind mount.
2. **Current disk state**
   - Check whether source tree still exists: `web/package.json`, `web/src/`, `scripts/deploy-prod.sh`, `.deploy-backups/`, `dist/assets/*`.
3. **Repo currently on disk**
   - Verify whether the active repo even contains the frontend. Do not assume the gateway repo includes the web app.
4. **Session breadcrumbs / operator history**
   - Search prior sessions for deploy output proving the old frontend existed.
   - High-value breadcrumbs:
     - `web/package.json` was read previously
     - `bash scripts/deploy-prod.sh web`
     - build output with concrete asset names/sizes
     - backup path output such as `.deploy-backups/<timestamp>`
     - `curl -I https://domain` returning `200` immediately after deploy
5. **Shell history**
   - Look for repeated `cd <project>` / editor usage around the project, but treat this only as supporting evidence.
6. **Remote Git reality**
   - Check whether the current upstream repo/branch includes the frontend. If not, do not promise exact restore from Git.

## Decision rule
- If you have actual source/build artifacts or a deploy backup: restore from those.
- If you only have breadcrumbs proving the frontend once existed, but no surviving source/build/backup on disk or remote: say clearly that exact restore is not possible from current VPS state.
- Then propose the fastest honest fallback: rebuild from remaining references (demo page, screenshots, product copy, old asset fingerprints) rather than pretending the original files can be recovered.

## Important wording rule
Do **not** blur these two states:
- `frontend existed before`
- `frontend is recoverable now`

They are different. Breadcrumbs can prove historical existence without giving enough material for exact recovery.

## Practical output shape
Report in 3 buckets:
1. **What definitely existed before** (with evidence)
2. **What still exists now**
3. **What is missing, therefore exact restore is impossible from current server state**

Then give restore options ordered by honesty and speed:
- exact restore from found backup/source
- restore from remote branch/tag if found
- rebuild a proper homepage from surviving references

## Example breadcrumb types worth preserving in notes
- old build output names: `dist/assets/index-*.js`, `index-*.css`
- deploy script names: `scripts/deploy-prod.sh web`
- backup paths: `.deploy-backups/...`
- nginx/container topology: static nginx container on `127.0.0.1:<port>` behind public reverse proxy

This pattern is especially useful on multi-app VPS hosts where containers survive longer than the repo or deploy scripts that originally produced their mounted content.
