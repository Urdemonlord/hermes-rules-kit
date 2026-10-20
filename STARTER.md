# Starter Presets

Pick the one that matches the work you do this week. Install it, use it for a week, then add individual skills.

Every preset starts with the framework layer, because the procedures are only as good as the discipline around them.

## `default` — SvelteKit / Next.js product work on a VPS, with Android on the side

The workflow this repo was built from: ship a web product, verify it on the host it actually runs on, keep the mobile client in the same discipline.

- `hermes-agentic-coding-20-80`
- `hermes-verifier-mode`
- `hermes-multimodal-proof`
- `hermes-deep-research-loop`
- `web-app-lifecycle-ops`
- `sveltekit-runtime-patterns`
- `docker-compose-operations`
- `vps-hardening-optimization`
- `android-kotlin-cli-build`
- `release-documentation`

```bash
./scripts/install-skills.sh default
```

## `web-app` — front-end product, deployed to a PaaS

- `hermes-agentic-coding-20-80`
- `hermes-verifier-mode`
- `hermes-multimodal-proof`
- `web-app-lifecycle-ops`
- `nextjs-vercel-operations`
- `sveltekit-runtime-patterns`
- `production-launch-readiness`
- `nextjs-seo-remediation`
- `test-proof-discipline`

## `vps-ops` — you own the box

- `hermes-agentic-coding-20-80`
- `hermes-verifier-mode`
- `destructive-action-safety-gates`
- `docker-compose-operations`
- `vps-hardening-optimization`
- `vps-zero-down-recovery`
- `vps-node-cleanup-recovery`
- `production-launch-readiness`
- `domain-redirect-and-hostname-routing`
- `edge-proxied-asset-delivery`

## `agent-research` — evaluation, classifiers, security review

- `hermes-deep-research-loop`
- `hermes-verifier-mode`
- `hermes-multimodal-proof`
- `injection-ood-classifier-evaluation`
- `text-classifier-training-deployment`
- `academic-paper-metadata-research`
- `third-party-tool-vetting`
- `reverse-engineer-anything`

## `android` — Kotlin app, built and shipped without an IDE

- `hermes-agentic-coding-20-80`
- `hermes-verifier-mode`
- `android-kotlin-cli-build`
- `android-ci-only-feature-development`
- `android-home-screen-widget`
- `android-ota-inapp-update`
- `android-third-party-integration`
- `release-documentation`

---

## After install

```bash
./scripts/install-skills.sh --list
./scripts/install-skills.sh default --dry-run
```

Then start a session and ask the agent to list its skills. If it cannot name them, the install path is wrong, not the skill.
